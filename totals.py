#!/usr/bin/env python3
"""Pre-registered H5: low-total moneyline underdogs, recorded at lock for the forward test.

Reporting only (v1.14.2). Nothing here feeds the model, the recipe or
data/forward_predictions.jsonl. For each game newly locked in the forward ledger,
the build records the nflverse schedule's total and both moneylines, once, in
data/h5_totals.jsonl (append-only). grade_ledger.py bets 1u on the moneyline
underdog (lower no-vig probability) of every recorded game whose total is
<= H5_MAX_TOTAL, beside the market-correct null and the favorite on the same rows.
A failure is logged and skipped; it never costs a pregame snapshot.

Source (research/PREREGISTRATION.md, H5): 2006-2025 regular seasons, favorites in the
lowest-total quartile (total <= 41) won 2.8 points less often than their no-vig
moneyline implied; every underdog there returned +5.8% +/- 4.9 against a -2.5% null.
The cut is that quartile's edge, chosen after looking: a hypothesis, not evidence.
"""

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

DATA = Path("data")
TOTALS = DATA / "h5_totals.jsonl"
LEDGER = DATA / "forward_predictions.jsonl"
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
H5_MAX_TOTAL = 41.0


def load(path):
    path = Path(path)
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def fetch_schedule():
    return pd.read_csv(SCHEDULE_URL, usecols=["game_id", "total_line", "home_moneyline", "away_moneyline"])


def num(v):
    v = pd.to_numeric(v, errors="coerce")
    return None if pd.isna(v) else float(v)


def record(data_dir=DATA, now=None, get=fetch_schedule):
    """Append the total and moneylines for ledger games that kick off after `now` and
    have no H5 record yet. Games without a posted total are skipped (retried next build)."""
    data_dir = Path(data_dir)
    now = now or dt.datetime.now(dt.timezone.utc)
    have = {r["game_id"] for r in load(data_dir / TOTALS.name)}
    todo = {}
    for r in load(data_dir / LEDGER.name):
        if r["game_id"] not in have and r["game_id"] not in todo and dt.datetime.fromisoformat(r["kickoff_utc"]) > now:
            todo[r["game_id"]] = r
    if not todo:
        return 0
    sched = get().drop_duplicates("game_id").set_index("game_id")
    new = []
    for gid, r in todo.items():
        if gid not in sched.index or num(sched.at[gid, "total_line"]) is None:
            continue
        s = sched.loc[gid]
        new.append({"game_id": gid, "season": int(r["season"]), "week": int(r["week"]),
                    "home": r["home"], "away": r["away"], "kickoff_utc": r["kickoff_utc"],
                    "captured_utc": now.isoformat(), "total_line": num(s.total_line),
                    "home_moneyline": num(s.home_moneyline), "away_moneyline": num(s.away_moneyline),
                    "source": "nflverse nfldata games.csv at lock"})
    if new:
        with (data_dir / TOTALS.name).open("a", encoding="utf-8") as fh:
            for r in new:
                fh.write(json.dumps(r, allow_nan=False) + "\n")
    return len(new)


def safe_record(data_dir=DATA, now=None, get=fetch_schedule):
    """record() that never raises: the build must not lose a pregame snapshot to H5."""
    try:
        n = record(data_dir, now, get)
        print(f"h5: {n} total(s) recorded")
        return n
    except Exception as exc:  # noqa: BLE001 - reporting only; never fail the build
        print(f"h5: skipped ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 0


if __name__ == "__main__":
    safe_record()
