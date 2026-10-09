#!/usr/bin/env python3
"""Kalshi quotes at lock time: a second, timestamped market for the forward ledger.

Reporting only (v1.12.2). Nothing here feeds the model, the recipe or
data/forward_predictions.jsonl. For each game newly locked in the forward ledger,
the build captures Kalshi's public order-book top (best bid and ask) for:

  * the game-winner market for each team (series KXNFLGAME), and
  * the "<team> wins by over X.5 points" ladder (series KXNFLSPREAD),

and appends a record to data/kalshi_snapshots.jsonl, never rewritten. A game gets a
new capture whenever one of its ledger snapshots (any revision) has no capture at or
after its lock, so a revision that locks later is not priced at an older quote.
grade_ledger.py joins each snapshot to its first capture at or after its lock to grade
the model's side at the Kalshi price and the alt-line diagnostic. Public market-data endpoints need no
key. A Kalshi failure is logged and skipped; it never costs a pregame snapshot.

    python kalshi.py            # capture quotes for locked, not-yet-started games
"""

import argparse
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.elections.kalshi.com/trade-api/v2"
DATA = Path("data")
SNAPSHOTS = DATA / "kalshi_snapshots.jsonl"
LEDGER = DATA / "forward_predictions.jsonl"
GAME_SERIES, SPREAD_SERIES = "KXNFLGAME", "KXNFLSPREAD"
TO_NFLVERSE = {"JAC": "JAX", "LAR": "LA", "WSH": "WAS"}  # Kalshi code -> nflverse team code
FEE_RATE = 0.07  # Kalshi taker fee per contract ~ FEE_RATE * P * (1 - P) (rounded up per order)
EVENT_RE = re.compile(r"^(?P<series>KX[A-Z]+)-(?P<yy>\d\d)(?P<mon>[A-Z]{3})(?P<dd>\d\d)(?P<teams>[A-Z]+)$")


def fetch(path, tries=5, pause=0.25):
    """GET a public endpoint as JSON, backing off on HTTP 429."""
    req = urllib.request.Request(API + path, headers={"User-Agent": "nfl-model-ledger"})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                out = json.load(r)
            time.sleep(pause)
            return out
        except urllib.error.HTTPError as exc:
            if exc.code != 429 or i == tries - 1:
                raise
            time.sleep(2 ** i)
    raise RuntimeError("unreachable")


def team(code):
    return TO_NFLVERSE.get(code, code)


def parse_event(ticker):
    """(series, date, teams string) from e.g. KXNFLGAME-26OCT11CHIGB, or None."""
    m = EVENT_RE.match(ticker)
    if not m:
        return None
    day = dt.datetime.strptime(m["yy"] + m["mon"] + m["dd"], "%y%b%d").date()
    return m["series"], day, m["teams"]


def match_event(events, away, home, kickoff):
    """The event ticker whose teams are away+home (Kalshi order: away then home) and
    whose date is within a day of kickoff (Kalshi dates are US local). None if absent."""
    ko = dt.datetime.fromisoformat(kickoff).date()
    for e in events:
        p = parse_event(e["event_ticker"])
        if not p or abs((p[1] - ko).days) > 1:
            continue
        for a in [k for k, v in TO_NFLVERSE.items() if v == away] + [away]:
            for h in [k for k, v in TO_NFLVERSE.items() if v == home] + [home]:
                if p[2] == a + h:
                    return e["event_ticker"]
    return None


def _price(m, side):
    v = m.get(f"yes_{side}_dollars")
    if v not in (None, ""):
        return float(v)
    v = m.get(f"yes_{side}")  # older cent fields
    return float(v) / 100 if v not in (None, "") else None


def quote(m):
    """Best bid/ask in dollars, or None when either side of the book is empty."""
    bid, ask = _price(m, "bid"), _price(m, "ask")
    if bid is None or ask is None or not 0 < ask <= 1 or not 0 <= bid < ask:
        return None
    return {"ticker": m["ticker"], "bid": round(bid, 4), "ask": round(ask, 4)}


def winner_quotes(markets, away, home):
    """{'home': quote, 'away': quote} from a KXNFLGAME event's markets."""
    out = {}
    for m in markets:
        code = team(m["ticker"].rsplit("-", 1)[-1])
        side = "home" if code == home else "away" if code == away else None
        q = quote(m)
        if side and q:
            out[side] = q
    return out


def spread_ladder(markets, away, home):
    """[{'team': nflverse code, 'strike': X.5, 'bid', 'ask', 'ticker'}] sorted by team, strike."""
    rows = []
    for m in markets:
        q, strike = quote(m), m.get("floor_strike")
        code = re.match(r"([A-Z]+)\d+$", m["ticker"].rsplit("-", 1)[-1])
        if not q or strike is None or not code:
            continue
        t = team(code.group(1))
        if t in (away, home):
            rows.append({"team": t, "strike": float(strike), **q})
    return sorted(rows, key=lambda r: (r["team"], r["strike"]))


# ---------------------------------------------------------------- ladder pricing (H3)
# Frozen reference: share of past games in which the moneyline favorite's margin
# exceeded each half-point strike, by the favorite's no-vig moneyline probability.
# Built once from seasons 2006-2024 by research/ladder_pricing.py; never refit on
# the seasons it is used to price.
LADDER_TABLE = DATA / "kalshi_ladder_reference.csv"
LADDER_MIN_EDGE = 0.03  # expected profit per contract after the fee, in dollars
LADDER_MAX_STRIKE = 17.5  # deeper rungs rest on thin tails of the reference distribution


def ml_implied(ml):
    ml = float(ml)
    return -ml / (-ml + 100) if ml < 0 else 100 / (ml + 100)


def load_ladder_table(path=LADDER_TABLE):
    """{(fav_wp, strike): p_over} and {fav_wp: tie}; fav_wp on a 0.01 grid."""
    import csv
    over, tie = {}, {}
    with Path(path).open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            w = round(float(r["fav_wp"]), 2)
            over[(w, float(r["strike"]))] = float(r["p_over"])
            tie[w] = float(r["tie"])
    return over, tie


def ladder_probability(table, fav_wp, team_is_fav, strike):
    """Reference chance that `team` wins by over `strike` (0 = the game-winner market,
    where a tie pays half). The favorite's margin m: fav over X.5 = P(m > X.5); dog over
    X.5 = P(m < -X.5) = 1 - P(m > -X.5)."""
    over, tie = table
    w = min(max(round(fav_wp, 2), min(tie)), max(tie))
    if strike == 0:
        t = tie[w]
        return (over[(w, .5)] if team_is_fav else 1 - over[(w, -.5)]) + t / 2
    return over[(w, strike)] if team_is_fav else 1 - over[(w, -strike)]


def ladder_pick(snap, home_ml, away_ml, table, min_edge=LADDER_MIN_EDGE, max_strike=LADDER_MAX_STRIKE):
    """The single rung (either team's ladder or game-winner market) with the largest
    expected profit per contract after the fee, if that is at least `min_edge`; else None.
    Returns {team, side, strike, ask, mid, est, edge, ticker}."""
    try:
        ih, ia = ml_implied(home_ml), ml_implied(away_ml)
    except (TypeError, ValueError):
        return None
    hp = ih / (ih + ia)
    fav_side = "home" if hp >= .5 else "away"
    fav_wp = max(hp, 1 - hp)
    best = None
    rungs = [(side, 0., q) for side, q in snap["winner"].items()]
    rungs += [("home" if x["team"] == snap["home"] else "away", x["strike"], x) for x in snap["spread_ladder"]]
    for side, strike, q in rungs:
        if strike > max_strike:
            continue
        try:
            est = ladder_probability(table, fav_wp, side == fav_side, strike)
        except KeyError:  # a strike outside the reference table
            continue
        edge = est - q["ask"] - FEE_RATE * q["ask"] * (1 - q["ask"])
        if edge >= min_edge and (best is None or edge > best["edge"]):
            best = {"team": snap[side], "side": side, "strike": strike, "ask": q["ask"],
                    "mid": (q["bid"] + q["ask"]) / 2, "est": est, "edge": edge, "ticker": q["ticker"]}
    return best


def capture(game, events, get=fetch, now=None):
    """One snapshot record for a game, or None when Kalshi lists no winner market."""
    now = now or dt.datetime.now(dt.timezone.utc)
    away, home = game["away"], game["home"]
    gt = match_event(events.get(GAME_SERIES, []), away, home, game["kickoff_utc"])
    if not gt:
        return None
    win = winner_quotes(get(f"/markets?event_ticker={gt}").get("markets", []), away, home)
    if not win:
        return None
    st = match_event(events.get(SPREAD_SERIES, []), away, home, game["kickoff_utc"])
    ladder = spread_ladder(get(f"/markets?event_ticker={st}").get("markets", []), away, home) if st else []
    return {"game_id": game["game_id"], "season": game["season"], "week": game["week"],
            "away": away, "home": home, "kickoff_utc": game["kickoff_utc"],
            "captured_utc": now.isoformat(), "source": "kalshi public order book (best bid/ask)",
            "winner_event": gt, "winner": win, "spread_event": st, "spread_ladder": ladder}


def open_events(get=fetch):
    out = {}
    for series in (GAME_SERIES, SPREAD_SERIES):
        evs, cur = [], ""
        while True:
            d = get(f"/events?series_ticker={series}&status=open&limit=200" + (f"&cursor={cur}" if cur else ""))
            evs += d.get("events", [])
            cur = d.get("cursor") or ""
            if not cur or not d.get("events"):
                break
        out[series] = evs
    return out


def load(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def record(data_dir=DATA, now=None, get=fetch):
    """Append captures for ledger games that kick off later than `now` and have a ledger
    snapshot with no capture at or after its lock (generated_utc). Returns the number of
    records written."""
    data_dir = Path(data_dir)
    now = now or dt.datetime.now(dt.timezone.utc)
    last = {}
    for r in load(data_dir / SNAPSHOTS.name):
        t = dt.datetime.fromisoformat(r["captured_utc"])
        last[r["game_id"]] = max(last.get(r["game_id"], t), t)
    todo = {}
    for r in load(data_dir / LEDGER.name):
        if r["game_id"] in todo or dt.datetime.fromisoformat(r["kickoff_utc"]) <= now:
            continue
        if r["game_id"] not in last or last[r["game_id"]] < dt.datetime.fromisoformat(r["generated_utc"]):
            todo[r["game_id"]] = r
    if not todo:
        return 0
    events = open_events(get)
    new = []
    for g in todo.values():
        rec = capture(g, events, get, now)
        if rec:
            new.append(rec)
    if new:
        with (data_dir / SNAPSHOTS.name).open("a", encoding="utf-8") as f:
            for r in new:
                f.write(json.dumps(r, allow_nan=False) + "\n")
    return len(new)


def safe_record(data_dir=DATA, now=None, get=fetch):
    """record() that never raises: the build must not lose a pregame snapshot to Kalshi."""
    try:
        n = record(data_dir, now, get)
        print(f"kalshi: {n} quote snapshot(s) recorded")
        return n
    except Exception as exc:  # noqa: BLE001 - any network/API failure is non-fatal by design
        print(f"kalshi: skipped ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", default=str(DATA))
    args = ap.parse_args(argv)
    safe_record(args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
