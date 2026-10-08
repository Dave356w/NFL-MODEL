#!/usr/bin/env python3
"""Kalshi quotes at lock time: a second, timestamped market for the forward ledger.

Reporting only (v1.12.2). Nothing here feeds the model, the recipe or
data/forward_predictions.jsonl. For each game newly locked in the forward ledger,
the build captures Kalshi's public order-book top (best bid and ask) for:

  * the game-winner market for each team (series KXNFLGAME), and
  * the "<team> wins by over X.5 points" ladder (series KXNFLSPREAD),

and appends ONE record per game to data/kalshi_snapshots.jsonl, the first capture
only, never rewritten. grade_ledger.py joins it to grade the model's side at the
Kalshi price and the alt-line diagnostic. Public market-data endpoints need no
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
    """Append first captures for ledger games that have kicked off later than `now` and
    have no Kalshi snapshot yet. Returns the number of records written."""
    data_dir = Path(data_dir)
    now = now or dt.datetime.now(dt.timezone.utc)
    have = {r["game_id"] for r in load(data_dir / SNAPSHOTS.name)}
    todo = {}
    for r in load(data_dir / LEDGER.name):
        if r["game_id"] in have or r["game_id"] in todo:
            continue
        if dt.datetime.fromisoformat(r["kickoff_utc"]) > now:
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
