#!/usr/bin/env python3
"""Reject conflict markers, malformed rows and broken ledger invariants in data/.

Stdlib only. Runs before every ledger commit in build.yml and first in tests.yml.
"""

import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path

CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")
LEDGER_NAME = "forward_predictions.jsonl"


def validate_csv(path):
    """Raise ValueError when a CSV contains conflict markers or uneven rows."""
    path = Path(path)
    with path.open("r", encoding="utf-8-sig", newline="") as src:
        rows = csv.reader(src)
        try:
            header = next(rows)
        except StopIteration as exc:
            raise ValueError(f"{path}: empty CSV") from exc
        if not header:
            raise ValueError(f"{path}: empty header")
        expected = len(header)
        for line_number, row in enumerate(rows, start=2):
            first = row[0].strip() if row else ""
            if first.startswith(CONFLICT_MARKERS):
                raise ValueError(f"{path}:{line_number}: unresolved Git conflict marker")
            if len(row) != expected:
                raise ValueError(f"{path}:{line_number}: expected {expected} columns, found {len(row)}")


def validate_personnel_events(path):
    """Stdlib schema check for the hand-curated, dated personnel feed."""
    columns=['event_date','team','gsis_id','player','event','note']
    teams=set('ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS'.split())
    aliases={'OAK':'LV','SD':'LAC','STL':'LA'}
    events={'retired','traded','waived','released','suspended','signed','activated'}
    with Path(path).open(encoding='utf-8-sig',newline='') as src:
        rows=csv.DictReader(src)
        if rows.fieldnames!=columns:
            raise ValueError(f'{path}: personnel header must be {columns}; found {rows.fieldnames}')
        for i,row in enumerate(rows,start=2):
            try:
                if any(not (row.get(c) or '').strip() for c in ('event_date','team','gsis_id','event')):
                    raise ValueError('missing required value')
                day=row['event_date'].strip()
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day): raise ValueError('date must be YYYY-MM-DD')
                datetime.strptime(day,'%Y-%m-%d')
                team=row['team'].strip()
                if aliases.get(team,team) not in teams: raise ValueError('unrecognized team abbreviation')
                if row['event'].strip() not in events: raise ValueError('unknown event code')
            except ValueError as exc:
                raise ValueError(f'{path}:{i}: {exc}; offending row: {row}') from exc


def validate_ledger(path):
    """Every line is JSON; one snapshot per (experiment, game); written before kickoff."""
    path = Path(path)
    seen = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        if line.startswith(CONFLICT_MARKERS):
            raise ValueError(f"{path}:{line_number}: unresolved Git conflict marker")
        try:
            r = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_number}: not JSON ({exc})") from exc
        for k in ("experiment", "game_id", "generated_utc", "kickoff_utc", "model_wp"):
            if k not in r:
                raise ValueError(f"{path}:{line_number}: missing {k}")
        key = (r["experiment"], r["game_id"])
        if key in seen:
            raise ValueError(f"{path}:{line_number}: duplicate snapshot for {r['game_id']}")
        seen.add(key)
        if datetime.fromisoformat(r["generated_utc"]) >= datetime.fromisoformat(r["kickoff_utc"]):
            raise ValueError(f"{path}:{line_number}: snapshot not before kickoff")
    return len(seen)


def validate_data_dir(data_dir="data"):
    """Validate every CSV under data_dir and the forward ledger; return checked paths."""
    data_dir = Path(data_dir)
    paths = sorted(data_dir.rglob("*.csv"))
    for path in paths:
        validate_csv(path)
        if path.name=="personnel_events.csv": validate_personnel_events(path)
    ledger = data_dir / LEDGER_NAME
    if ledger.exists():
        validate_ledger(ledger)
        paths.append(ledger)
    return paths


def main():
    try:
        paths = validate_data_dir()
    except (OSError, ValueError) as exc:
        print(f"data validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"data validation: {len(paths)} files OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
