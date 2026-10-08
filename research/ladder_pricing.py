"""H3: price Kalshi's "wins by over X.5" ladder from the historical margin distribution.
Research only for the backtest; `--build` writes the frozen reference table that the
ledger diagnostic reads (data/kalshi_ladder_reference.csv).

Reference table: for every NFL game 2006-2024 with both moneylines, the favorite is the
side with the higher no-vig moneyline probability (fav_wp). For each fav_wp on a 0.01
grid, games within +/-0.03 of it (widened to +/-0.05 if fewer than 150) give the share in
which the favorite's margin exceeded each half-point strike from -30.5 to +30.5, and the
tie share. Real margins, so 3 and 7 carry their true weight.

Backtest (--backtest): Kalshi's ladder and game-winner books from the last hourly candle
ending at least 1 hour before kickoff, 2025 onward (out of sample for the table). Rule,
per game: the one rung with the largest expected profit per contract after the fee,
est - ask - 0.07 * ask * (1 - ask), bought at the ask if that is >= $0.03.

    python research/ladder_pricing.py --build
    python research/ladder_pricing.py --backtest [--cache DIR]
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import kalshi as k  # noqa: E402

GAMES_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
FIRST, LAST = 2006, 2024
ET = ZoneInfo("America/New_York")


def favorite_frame(g):
    g = g[g.result.notna() & g.home_moneyline.notna() & g.away_moneyline.notna()].copy()
    ih = g.home_moneyline.map(k.ml_implied)
    ia = g.away_moneyline.map(k.ml_implied)
    g["hp"] = ih / (ih + ia)
    g["fav_wp"] = np.maximum(g.hp, 1 - g.hp)
    g["fav_margin"] = np.where(g.hp >= .5, g.result, -g.result)
    return g


def build_table(g):
    f = favorite_frame(g[g.season.between(FIRST, LAST) & (g.game_type != "PRE")])
    strikes = np.arange(-30.5, 31, 1.)
    rows = []
    for w in np.round(np.arange(.50, .98, .01), 2):
        for half in (.03, .05):
            near = f[(f.fav_wp - w).abs() <= half]
            if len(near) >= 150:
                break
        m = near.fav_margin.to_numpy()
        tie = float((m == 0).mean())
        for s in strikes:
            rows.append({"fav_wp": w, "strike": s, "p_over": round(float((m > s).mean()), 4),
                         "tie": round(tie, 4), "n": len(near)})
    return pd.DataFrame(rows)


def candles_mid_ask(get, ticker, end, series, historical):
    q = f"?start_ts={end - 4 * 3600}&end_ts={end}&period_interval=60"
    first, second = (f"/historical/markets/{ticker}/candlesticks{q}", f"/series/{series}/markets/{ticker}/candlesticks{q}")
    if not historical:
        first, second = second, first
    try:
        cs = get(first).get("candlesticks", [])
    except Exception:  # noqa: BLE001 - markets move to the historical endpoint after settling
        try:
            cs = get(second).get("candlesticks", [])
        except Exception:  # noqa: BLE001 - a rung with no price history counts as no quote
            return None
    c = [x for x in cs if x["end_period_ts"] <= end - 3600]
    if not c:
        return None
    f = lambda d: float(d.get("close") or d.get("close_dollars") or "nan")  # noqa: E731
    b, a = f(c[-1]["yes_bid"]), f(c[-1]["yes_ask"])
    return {"bid": b, "ask": a} if np.isfinite(a + b) and 0 <= b < a <= 1 else None


def pull_ladders(cache, get=k.fetch):
    """Historical pregame books for every game with a Kalshi ladder; cached per game as JSON."""
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    g = pd.read_csv(GAMES_URL)
    g = g[(g.season > LAST) & g.result.notna() & (g.game_type != "PRE")]
    events = {}
    for series in (k.GAME_SERIES, k.SPREAD_SERIES):
        evs, cur = [], ""
        while True:
            d = get(f"/events?series_ticker={series}&limit=200" + (f"&cursor={cur}" if cur else ""))
            evs += d.get("events", [])
            cur = d.get("cursor") or ""
            if not cur or not d.get("events"):
                break
        events[series] = evs
    for r in g.itertuples():
        out = cache / f"{r.game_id}.json"
        if out.exists():
            continue
        ko = dt.datetime.strptime(f"{r.gameday} {r.gametime}", "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(dt.timezone.utc)
        end = int(ko.timestamp())
        snap = {"game_id": r.game_id, "home": r.home_team, "away": r.away_team, "winner": {}, "spread_ladder": []}
        for series in (k.GAME_SERIES, k.SPREAD_SERIES):
            tk = k.match_event(events[series], r.away_team, r.home_team, ko.isoformat())
            if not tk:
                continue
            mk = get(f"/markets?event_ticker={tk}").get("markets", [])
            historical = not mk
            if historical:
                mk = get(f"/historical/markets?event_ticker={tk}").get("markets", [])
            for x in mk:
                code = x["ticker"].rsplit("-", 1)[-1]
                if series == k.GAME_SERIES:
                    side = "home" if k.team(code) == r.home_team else "away" if k.team(code) == r.away_team else None
                    q = candles_mid_ask(get, x["ticker"], end, series, historical) if side else None
                    if q:
                        snap["winner"][side] = {"ticker": x["ticker"], **q}
                else:
                    strike = x.get("floor_strike")
                    t = k.team(code.rstrip("0123456789"))
                    if strike is None or strike > 17.5 or t not in (r.home_team, r.away_team):
                        continue
                    q = candles_mid_ask(get, x["ticker"], end, series, historical)
                    if q:
                        snap["spread_ladder"].append({"team": t, "strike": float(strike), "ticker": x["ticker"], **q})
        out.write_text(json.dumps(snap))


def backtest(cache, table):
    g = pd.read_csv(GAMES_URL)
    g = g[(g.season > LAST) & g.result.notna()].set_index("game_id")
    rows = []
    for p in sorted(Path(cache).glob("*.json")):
        snap = json.loads(p.read_text())
        if snap["game_id"] not in g.index or len(snap["winner"]) < 2:
            continue
        r = g.loc[snap["game_id"]]
        pick = k.ladder_pick(snap, r.home_moneyline, r.away_moneyline, table)
        if not pick:
            rows.append({"game_id": snap["game_id"], "bet": False})
            continue
        margin = r.result if pick["side"] == "home" else -r.result
        won = 1. if margin > pick["strike"] else .5 if pick["strike"] == 0 and margin == 0 else 0.
        a = pick["ask"]
        rows.append({"game_id": snap["game_id"], "season": r.season, "bet": True, **pick, "won": won,
                     "units": won / a - 1 - k.FEE_RATE * (1 - a),
                     "null": pick["mid"] / a - 1 - k.FEE_RATE * (1 - a),
                     "ref_units": pick["est"] / a - 1 - k.FEE_RATE * (1 - a)})
    return pd.DataFrame(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build", action="store_true", help=f"write {k.LADDER_TABLE}")
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--cache", default="kalshi_ladder_cache")
    args = ap.parse_args(argv)
    if args.build:
        t = build_table(pd.read_csv(GAMES_URL))
        t.to_csv(ROOT / k.LADDER_TABLE, index=False)
        print(f"wrote {k.LADDER_TABLE}: {len(t)} rows, seasons {FIRST}-{LAST}")
    if args.backtest:
        pull_ladders(args.cache)
        b = backtest(args.cache, k.load_ladder_table(ROOT / k.LADDER_TABLE))
        bets = b[b.bet]
        print(f"games with both winner books: {len(b)}; bets: {len(bets)}")
        if len(bets):
            u = bets.units
            print(f"ROI {100 * u.mean():+.1f}% +/- {100 * u.std(ddof=1) / np.sqrt(len(u)):.1f} ({u.sum():+.2f}u); "
                  f"Kalshi-mid null {100 * bets.null.mean():+.1f}%; reference expected {100 * bets.ref_units.mean():+.1f}%")
            print(bets.groupby(pd.cut(bets.strike, [-1, 0, 3, 7, 10.5, 18])).units.agg(["size", "mean"]).round(3))
            print(bets.groupby("season").units.agg(["size", "mean"]).round(3))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
