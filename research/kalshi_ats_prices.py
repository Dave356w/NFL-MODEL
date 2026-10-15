"""Point-in-time Kalshi NFL winner + spread-ladder price adapter (research only).

Uses official public /events, /historical/markets, and /historical/markets/
{ticker}/candlesticks; live-market equivalents cover recent/unarchived games.
No archive is guaranteed for seasons before Kalshi listed NFL spreads in 2025.
A past quote is never inferred from a settled market's current price.
No sportsbook fallback; exact strike and explicit no-match are mandatory.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
import time
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd

import kalshi
from research import ats_cover_probability as ats

MAX_STALENESS_SECONDS = 1800
FEE_RATE = kalshi.FEE_RATE
SERIES = (kalshi.GAME_SERIES, kalshi.SPREAD_SERIES)
TEAM_RE = kalshi.re.compile(r"^([A-Z]+)(?:\d+)?$")


def as_utc(x):
    z = pd.Timestamp(x)
    if z.tzinfo is None:
        raise ValueError("Kalshi quote cutoff must be UTC-aware")
    return z.tz_convert("UTC")


def api_list(path, param, get=kalshi.fetch, limit=1000, max_pages=50):
    output, cursor = [], None
    for _ in range(max_pages):
        args = dict(param)
        args["limit"] = limit
        if cursor: args["cursor"] = cursor
        response = get(path + "?" + urlencode(args))
        if not isinstance(response, dict):
            raise ValueError("invalid Kalshi response")
        output += response.get("events" if path == "/events" else "markets", [])
        cursor = response.get("cursor")
        if not cursor: return output
    raise ValueError("Kalshi pagination safety limit reached")


def event_for_game(events, row, series):
    game = {"away": row["away"], "home": row["home"], "kickoff_utc": row["kickoff_utc"]}
    choices = []
    for e in events:
        if not e.get("event_ticker", "").startswith(series + "-"): continue
        if kalshi.match_event([e], game["away"], game["home"], game["kickoff_utc"]):
            choices.append(e["event_ticker"])
    if len(choices) > 1:
        raise ValueError(f"ambiguous {series} matchup {game}: {choices}")
    return choices[0] if choices else None


def markets_for_event(event, get=kalshi.fetch):
    """Read both partitions and explicitly deduplicate ticker. Never use settled prices."""
    if not event: return []
    archived = api_list("/historical/markets", {"event_ticker": event}, get=get, limit=1000)
    recent = api_list("/markets", {"event_ticker": event}, get=get, limit=1000)
    seen = {}
    for m in recent: seen[m["ticker"]] = (m, "live")
    for m in archived: seen[m["ticker"]] = (m, "historical")
    return list(seen.values())


def close_dollars(o):
    if not isinstance(o, dict): return None
    v = o.get("close_dollars", o.get("close"))
    try: v = float(v)
    except (ValueError, TypeError): return None
    return v if math.isfinite(v) and 0 <= v <= 1 else None


def candle_quote(candles, asof, market_open=None, max_staleness=MAX_STALENESS_SECONDS):
    """Only *completed* minute candles ending <= asof are eligible."""
    t = int(as_utc(asof).timestamp())
    available = [r for r in candles
                 if isinstance(r.get("end_period_ts"), (int, float))
                 and int(r["end_period_ts"]) <= t
                 and t - int(r["end_period_ts"]) <= max_staleness]
    if not available: return None
    r = max(available, key=lambda v: v["end_period_ts"])
    end = int(r["end_period_ts"])
    if market_open and as_utc(market_open).timestamp() > end:
        return None
    bid, ask = close_dollars(r.get("yes_bid")), close_dollars(r.get("yes_ask"))
    if bid is None or ask is None or bid >= ask or bid <= 0 or ask >= 1: return None
    return {"yes_bid": bid, "yes_ask": ask, "no_ask": 1-bid,
            "source_ts": dt.datetime.fromtimestamp(end, dt.timezone.utc).isoformat(),
            "age_seconds": t-end, "quote_kind": "last_completed_1m_candle"}


def quote_market(m, partition, asof, get=kalshi.fetch, max_staleness=MAX_STALENESS_SECONDS):
    t = int(as_utc(asof).timestamp())
    path = (f"/historical/markets/{m['ticker']}/candlesticks"
            if partition == "historical" else
            f"/series/{m['event_ticker'].split('-')[0]}/markets/{m['ticker']}/candlesticks")
    args = urlencode({"start_ts": t-max_staleness-60, "end_ts": t, "period_interval": 1})
    d = get(path+"?"+args)
    return candle_quote(d.get("candlesticks", []), asof, m.get("open_time"), max_staleness)


def spread_contracts(markets, away, home):
    """Use Kalshi's existing official floor_strike/team parsing, not ticker digits as handicap."""
    out = []
    for m, partition in markets:
        suffix = m["ticker"].rsplit("-", 1)[-1]
        match = kalshi.re.fullmatch(r"([A-Z]+)\d+", suffix)
        if not match or m.get("floor_strike") is None: continue
        team = kalshi.team(match.group(1))
        if team not in (away, home): continue
        strike = float(m["floor_strike"])
        if not math.isfinite(strike) or strike <= 0: continue
        out.append((m, partition, team, strike))
    return out


def line_quote(row, markets, asof, get=kalshi.fetch):
    """One binary market for favorite > |line|; opposite ATS side is its NO contract.

    For half-integer handicap the two sides partition all integer final margins.
    Integer lines can push and are never silently approximated by Kalshi half-lines.
    """
    line = float(row["spread_line"])
    if not math.isfinite(line) or abs(line) < 1e-9: return None, "zero_line_no_binary_equivalence"
    strike = abs(line)
    if not math.isclose(strike % 1, .5, abs_tol=1e-9):
        return None, "integer_or_nonhalfpoint_line"
    favorite = row["home"] if line > 0 else row["away"]
    candidates = [(m, part) for m, part, team, s in spread_contracts(markets,row["away"],row["home"])
                  if team == favorite and math.isclose(s, strike, abs_tol=1e-9)]
    if len(candidates) != 1: return None, "missing_or_ambiguous_exact_strike"
    m, part = candidates[0]
    q = quote_market(m, part, asof, get)
    if q is None: return None, "missing_or_stale_candlestick"
    q.update({"event_ticker": m["event_ticker"], "ticker": m["ticker"],
              "strike": strike, "favorite": favorite,
              "home_ask": q["yes_ask"] if line > 0 else q["no_ask"],
              "away_ask": q["no_ask"] if line > 0 else q["yes_ask"],
              "market_source": part})
    return q, "quoted"


def alternate_line_quote(row, markets, asof, get=kalshi.fetch):
    """Quoted Kalshi binary rung nearest ORIGINAL model-implied margin.

    Returns the model's ATS-selected side at the target half-integer handicap.
    The 'NO' quote uses 1-YES bid. A missing rung does not trigger interpolation.
    """
    model = float(row["model_spread"])
    market = float(row["spread_line"])
    if not math.isfinite(model) or not math.isfinite(market):
        return None, "missing_model_or_market_spread"
    if abs(model) < .5 or math.isclose(model, market, abs_tol=1e-9):
        return None, "no_distinct_alternate_target"
    picked = "home" if model > market else "away"
    favorite = row["home"] if model > 0 else row["away"]
    target = math.floor(abs(model))+.5
    candidates=[(m,part) for m,part,team,strike in spread_contracts(markets,row["away"],row["home"])
                if team==favorite and math.isclose(strike,target,abs_tol=1e-9)]
    if len(candidates)!=1:
        return None, "missing_or_ambiguous_alternate"
    m,part=candidates[0]
    q=quote_market(m,part,asof,get)
    if q is None: return None, "missing_or_stale_alternate_candle"
    is_yes = favorite == (row["home"] if picked=="home" else row["away"])
    q.update({"ticker":m["ticker"],"event_ticker":m["event_ticker"],
              "team":favorite,"target_strike":target,"selection_side":picked,
              "selection_contract":"YES" if is_yes else "NO",
              "selection_ask":q["yes_ask"] if is_yes else q["no_ask"],
              "source_partition":part})
    return q, "quoted"


def winner_quote(row, markets, asof, get=kalshi.fetch):
    d = {}
    for m, part in markets:
        code = kalshi.team(m["ticker"].rsplit("-",1)[-1])
        which = "home" if code == row["home"] else "away" if code == row["away"] else ""
        if not which or which in d: continue
        v = quote_market(m, part, asof, get)
        if v: d[which] = {**v,"ticker":m["ticker"],"market_source":part}
    return d


def event_catalog(games, get=kalshi.fetch):
    # Validated /events min_close_ts filter, no future asof price capture.
    earliest = min(as_utc(g["kickoff_utc"]) for g in games)
    start = int((earliest-pd.Timedelta(days=10)).timestamp())
    return {series:api_list("/events",{"series_ticker":series,"min_close_ts":start},get=get,limit=200)
            for series in SERIES}


def historical_quotes(games, *, get=kalshi.fetch, cutoff_hours=2., max_games=10):
    """Research-only 2h-before-kickoff benchmark, never a native model lock."""
    games = list(games)
    if not games: return []
    if max_games and max_games < 0: raise ValueError("max_games must be >=0")
    catalog = event_catalog(games, get=get)
    rows = []
    for r in games[:max_games or len(games)]:
        kick = as_utc(r["kickoff_utc"])
        cutoff = kick-pd.Timedelta(hours=cutoff_hours)
        if cutoff >= pd.Timestamp.now(tz="UTC"):
            rows.append({"game_id":r["game_id"],"status":"future_cutoff","price_basis":"none"});continue
        events = {s:event_for_game(catalog[s],r,s) for s in SERIES}
        spreads = markets_for_event(events[kalshi.SPREAD_SERIES],get)
        winners = markets_for_event(events[kalshi.GAME_SERIES],get)
        q,why = line_quote(r, spreads, cutoff, get=get)
        alt,alt_why = (alternate_line_quote(r, spreads, cutoff, get=get)
                       if r.get("model_spread") is not None else (None,"model_spread_unavailable"))
        w = winner_quote(r,winners,cutoff,get=get)
        result = {"game_id":r["game_id"],"away":r["away"],"home":r["home"],
                  "cutoff_utc":cutoff.isoformat(),"kickoff_utc":kick.isoformat(),
                  "spread_line":float(r["spread_line"]),
                  "status":why,"alternate_status":alt_why,
                  "price_basis":"kalshi_completed_minute_2h_pregame",
                  "winner_home_ask":w.get("home",{}).get("yes_ask"),
                  "winner_away_ask":w.get("away",{}).get("yes_ask"),
                  "winner_home_ticker":w.get("home",{}).get("ticker"),
                  "winner_away_ticker":w.get("away",{}).get("ticker"),
                  "winner_home_ts":w.get("home",{}).get("source_ts"),
                  "winner_away_ts":w.get("away",{}).get("source_ts")}
        if q: result.update({k:q[k] for k in ("ticker","event_ticker","strike","favorite",
                        "home_ask","away_ask","yes_bid","yes_ask","no_ask",
                        "age_seconds","source_ts","market_source")})
        if alt:
            result.update(alt_ticker=alt["ticker"],alt_selection_side=alt["selection_side"],
                          alt_contract=alt["selection_contract"],alt_ask=alt["selection_ask"],
                          alt_target_strike=alt["target_strike"],
                          alt_quote_ts=alt["source_ts"],alt_age_seconds=alt["age_seconds"])
        rows.append(result)
    return rows


def score_kalshi_price(p_home, p_away, p_push, ask):
    if ask is None or not 0 < float(ask) < 1: return None
    cost = float(ask)
    p_win,p_loss = float(p_home),float(p_away)
    # Kalshi fee: 7% * contract price * (1-price), approximate taker rate.
    fee=FEE_RATE * cost*(1-cost)
    return p_win*(1/cost - 1) - p_loss - fee/cost


def joined_ats_results(frame, kalshi_quotes):
    """Same games/side; quote-missing games excluded, no -110 fallback."""
    d = frame.copy()
    quotes = pd.DataFrame(kalshi_quotes)
    if quotes.empty: return d.iloc[:0]
    if quotes.game_id.duplicated().any(): raise ValueError("duplicate Kalshi game quotes")
    use = quotes[(quotes.status=="quoted") & quotes.home_ask.notna() & quotes.away_ask.notna()].copy()
    d=d.merge(use, on="game_id",how="inner",validate="one_to_one",
              suffixes=("","_kalshi"))
    if d.empty: return d
    for arm in ("original","fixed_band","cover_probability"):
        s = d[arm+"_side"]
        a = np.where(s=="home",d.home_ask,np.where(s=="away",d.away_ask,np.nan))
        # In a half-point market there are no pushes; W and L are exhaustive.
        won=d[arm+"_grade"].eq("W")
        lost=d[arm+"_grade"].eq("L")
        fee=FEE_RATE*a*(1-a)
        units=np.where(won,1/a-1-fee/a,np.where(lost,-1-fee/a,0.))
        d[arm+"_kalshi_ask"]=a
        d[arm+"_kalshi_units"]=np.where(s.isin(["home","away"]),units,0.)
    return d


def joined_kalshi_moneyline(frame, kalshi_quotes):
    """Price original model outright side at historical Kalshi YES ask, not sportsbook ML.

    Kalshi winner tie resolution is $0.50 for a $1 YES contract; the
    approximate fee is charged on the entry contract, no sportsbook fallback.
    """
    d = frame.copy()
    q = pd.DataFrame(kalshi_quotes)
    if q.empty: return d.iloc[:0]
    need = ["game_id", "winner_home_ask", "winner_away_ask"]
    if not set(need).issubset(q.columns): return d.iloc[:0]
    if q.game_id.duplicated().any(): raise ValueError("duplicate Kalshi game quotes")
    q = q.dropna(subset=["winner_home_ask", "winner_away_ask"])
    d = d.merge(q[need+["cutoff_utc","price_basis"]],on="game_id",how="inner",
                validate="one_to_one")
    if d.empty: return d
    p = pd.to_numeric(d.model_wp,errors="coerce")
    outcomes=pd.to_numeric(d["home won"],errors="coerce")
    side=np.where(p>.5,"home",np.where(p<.5,"away",""))
    ask=np.where(side=="home",d.winner_home_ask,
                 np.where(side=="away",d.winner_away_ask,np.nan))
    valid=np.isfinite(ask)&(ask>0)&(ask<1)&outcomes.isin([0,.5,1])&(side!="")
    value=np.where(outcomes.eq(.5), .5,
                   np.where((outcomes.eq(1)&(side=="home"))|
                            (outcomes.eq(0)&(side=="away")),1.,0.))
    pnl=value/ask-1.-FEE_RATE*(1.-ask)
    d["kalshi_ml_side"]=side
    d["kalshi_ml_ask"]=np.where(valid,ask,np.nan)
    d["kalshi_ml_units"]=np.where(valid,pnl,np.nan)
    return d[d.kalshi_ml_units.notna()].copy()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--games-csv",type=Path,
                   help="Game rows with exact kickoff_utc, away, home, game_id, spread_line")
    p.add_argument("--auto-season",type=int,choices=[2025,2026],
                   help="Resolve kickoff from nflverse schedules; select games in retro ledger")
    p.add_argument("--week",type=int,
                   help="Optional NFL week within auto-season")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--limit",type=int,default=10)
    p.add_argument("--hours-before-kickoff",type=float,default=2.)
    p.add_argument("--research-predictions",type=Path,
                   help="Optional Test 48 game-level predictions CSV to grade on matched Kalshi quotes")
    args=p.parse_args(argv)
    if bool(args.games_csv) == bool(args.auto_season):
        raise ValueError("provide exactly one of --games-csv or --auto-season")
    if args.auto_season:
        import nfl_model as model
        schedules = model.load_schedule(args.auto_season)
        quotes = pd.read_csv(Path("data/latest/retro_ledger.csv"))
        quotes = quotes.loc[quotes.season.eq(args.auto_season)]
        if args.week is not None: quotes = quotes.loc[quotes.week.eq(args.week)]
        sched = schedules[["game_id", "away_team", "home_team", "gameday", "gametime"]].copy()
        sched["kickoff_utc"] = [model.kickoff_utc(r).isoformat() for r in sched.to_dict("records")]
        games = quotes[["game_id", "home", "away", "spread_line", "model_spread"]].merge(
            sched[["game_id","kickoff_utc"]],on="game_id",validate="one_to_one")
        games = games.sort_values("game_id")
    else:
        games=pd.read_csv(args.games_csv)
    required={"game_id","kickoff_utc","home","away","spread_line"}
    if not required.issubset(games.columns): raise ValueError(f"missing {sorted(required-set(games.columns))}")
    if args.limit < 1: raise ValueError("--limit must be positive")
    # Kalshi NFL spread contracts only began in 2025.
    games=games[games.game_id.str[:4].astype(int)>=2025]
    records=historical_quotes(games.to_dict("records"),cutoff_hours=args.hours_before_kickoff,
                              max_games=args.limit)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    pd.DataFrame(records).to_csv(args.out,index=False)
    if args.research_predictions:
        source = pd.read_csv(args.research_predictions)
        d=joined_ats_results(source,records)
        d.to_csv(args.out.with_name(args.out.stem+"_graded.csv"),index=False)
        print(f"Matched Kalshi ATS offers: {len(d)} / {len(records)}")
        # Graded Test 48 predictions have model_wp absent: join via retro_ledger.
        retro = pd.read_csv(Path("data/latest/retro_ledger.csv"))
        ml = joined_kalshi_moneyline(retro,records)
        ml.to_csv(args.out.with_name(args.out.stem+"_moneyline.csv"),index=False)
        print(f"Matched Kalshi ML asks: {len(ml)} / {len(records)}")
    print(json.dumps({"games_requested":len(records),
                      "spread_quotes":sum(r.get("status")=="quoted" for r in records),
                      "alt_spread_quotes":sum(r.get("alternate_status")=="quoted" for r in records),
                      "with_both_winners":sum(r.get("winner_home_ask") is not None and r.get("winner_away_ask") is not None for r in records)},indent=2))


if __name__=="__main__":
    main()
