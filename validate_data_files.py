#!/usr/bin/env python3
"""Reject conflict markers, malformed rows and broken ledger invariants in data/.

Stdlib only. Runs before every ledger commit in build.yml and first in tests.yml.
"""

import csv
import json
import re
import sys
import subprocess
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


def validate_availability_observations(path):
    """Audit the curated input journal before commits, without importing model dependencies."""
    from urllib.parse import urlsplit
    fields={'eligible','report_status','qb_starter','report_complete','inactives_complete'}
    required={'game_id','team','field','value','source_url','published_utc','observed_utc','effective_utc'}
    optional={'gsis_id','player','position','status','reason','source_kind','source_capture_sha256','publication_time_basis'}
    count=0
    for number,line in enumerate(Path(path).read_text(encoding='utf-8').splitlines(),1):
        if not line.strip(): continue
        try:
            r=json.loads(line)
            if not isinstance(r,dict) or not required<=r.keys() or r.keys()-required-optional:
                raise ValueError('missing or unknown observation fields')
            if any(k in r for k in ('source_kind','source_capture_sha256','publication_time_basis')):
                if (r.get('source_kind') not in ('official_injury_report','official_inactives','official_team_news')
                        or not re.fullmatch(r'[a-f0-9]{64}',str(r.get('source_capture_sha256','')))
                        or r.get('publication_time_basis') not in ('source_publication','first_capture')):
                    raise ValueError('invalid automatic source provenance')
            game=re.fullmatch(r'(\d{4})_(\d{2})_([A-Z]+)_([A-Z]+)',str(r['game_id']))
            if not game or not 1<=int(game[2])<=22 or r['team'] not in game.groups()[2:]:
                raise ValueError('game/team mismatch')
            if r['field'] not in fields: raise ValueError('unknown availability field')
            if r['field'] in ('report_complete','inactives_complete'):
                if r.get('gsis_id'): raise ValueError('completeness is a team fact')
            elif not re.fullmatch(r'00-\d{7}',str(r.get('gsis_id',''))):
                raise ValueError('invalid GSIS ID')
            if r['field']=='report_status':
                if r['value'] not in ('Available','Out','Doubtful','Questionable'): raise ValueError('invalid injury status')
            elif type(r['value']) is not bool: raise ValueError('fact requires a boolean')
            if r['field']=='qb_starter' and (r['value'] is not True or r.get('position')!='QB' or not r.get('player')):
                raise ValueError('starter requires true, QB position and player name')
            if r['field']=='eligible' and r['value'] and (not r.get('position') or not r.get('player')):
                raise ValueError('eligibility requires position and player name')
            url=urlsplit(str(r['source_url']))
            if url.scheme!='https' or not url.hostname or url.username or url.password: raise ValueError('invalid source URL')
            times={k:datetime.fromisoformat(r[k].replace('Z','+00:00')) for k in ('published_utc','observed_utc','effective_utc')}
            if any(t.tzinfo is None for t in times.values()) or times['published_utc']>times['observed_utc']:
                raise ValueError('invalid observation timing')
            if r.get('status','confirmed') not in ('confirmed','pending'): raise ValueError('invalid observation status')
        except (ValueError,TypeError,KeyError) as exc:
            raise ValueError(f'{path}:{number}: {exc}') from exc
        count+=1
    return count


def validate_data_dir(data_dir="data"):
    """Validate every CSV under data_dir, the forward ledger and Kalshi captures; return checked paths."""
    data_dir = Path(data_dir)
    json_paths = sorted(data_dir.rglob("*.json"))
    for path in json_paths:
        text = path.read_text(encoding="utf-8")
        if any(line.startswith(CONFLICT_MARKERS) for line in text.splitlines()):
            raise ValueError(f"{path}: unresolved Git conflict marker")
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: not JSON ({exc})") from exc
    paths = sorted(data_dir.rglob("*.csv"))
    for path in paths:
        validate_csv(path)
        if path.name=="personnel_events.csv": validate_personnel_events(path)
    paths.extend(json_paths)
    ledger = data_dir / LEDGER_NAME
    if ledger.exists():
        validate_ledger(ledger)
        paths.append(ledger)
    observations=data_dir/'availability_observations.jsonl'
    if observations.exists():
        validate_availability_observations(observations)
        paths.append(observations)
    import availability_collect as ac
    auto=data_dir/ac.AUTO
    if auto.exists():
        validate_availability_observations(auto)
        paths.append(auto)
    ac.validate_store(data_dir)
    import ats_locks
    ats_locks.validate_store(data_dir)
    stores = ats_locks.runtime_stores(data_dir)
    for runtime in stores:
        ac.validate_store(runtime)
        ats_locks.validate_store(runtime)
        espn = __import__('espn_spreads')
        espn.validate(runtime)
    import forecast_history
    forecast_history.validate(data_dir)
    for runtime in stores:
        forecast_history.validate(runtime)
        forecast_history.validate_timing(runtime)
    import espn_spreads
    espn_spreads.validate(data_dir)
    import score_updates
    score_updates.read(data_dir)
    paths.extend(data_dir / name for name in (ats_locks.CANDIDATES, ats_locks.LOCKS)
                 if (data_dir / name).exists())
    return paths


def main():
    try:
        # Include tracked configuration/research JSON outside data/, without
        # scanning dependency folders or generated scratch outputs.
        tracked = subprocess.run(['git', 'ls-files', '-z', '*.json'],
                                 capture_output=True, text=True, check=True)
        for name in filter(None, tracked.stdout.split('\0')):
            path = Path(name)
            if path.exists():
                text = path.read_text(encoding='utf-8')
                if any(line.lstrip().startswith(CONFLICT_MARKERS) for line in text.splitlines()):
                    raise ValueError(f'{path}: unresolved Git conflict marker')
                try:
                    json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(f'{path}: not JSON ({exc})') from exc
        paths = validate_data_dir()
    except (OSError, ValueError) as exc:
        print(f"data validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"data validation: {len(paths)} files OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
