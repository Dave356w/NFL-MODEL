"""Append-only history of pregame board refreshes, including blocked projections.

This diagnostic journal never authorizes a candidate, lock, backfill or grade.
The forward ledger remains the first gated forecast; ATS candidates and locks
remain separate immutable decisions.
"""
import datetime as dt
from pathlib import Path

import ats_locks as locks
from schedule_gate import kickoff

JOURNAL = 'forecast_refreshes.jsonl'


def timing_rows(data):
    import json
    return [json.loads(p.read_text()) for p in sorted((Path(data)/'timing_forecasts').glob('*/*.json'))]


def validate_timing(data):
    """Shadow checkpoints must reference real pre-deadline observations only."""
    data = Path(data)
    rows = timing_rows(data)
    forecasts = {r['snapshot_sha256']: r for r in rows}
    if len(forecasts) != len(rows):
        raise ValueError('duplicate timing forecast')
    for row in rows:
        if locks.digest({k: v for k, v in row.items() if k != 'snapshot_sha256'}) != row['snapshot_sha256']:
            raise ValueError('timing forecast hash mismatch')
        if not locks.utc(row['generated_utc']) <= locks.utc(row['observed_utc']) < locks.utc(row['kickoff_utc']):
            raise ValueError('timing forecast is not pregame')
    seen = set()
    for checkpoint in locks.read(data/'timing_checkpoints.jsonl'):
        identity = (checkpoint['revision'], checkpoint['game_id'], checkpoint['lead_minutes'])
        if identity in seen or checkpoint['lead_minutes'] not in (120, 90, 60, 45, 30):
            raise ValueError('invalid/duplicate timing checkpoint')
        seen.add(identity)
        deadline = locks.utc(checkpoint['deadline_utc'])
        if locks.utc(checkpoint['recorded_utc']) < deadline:
            raise ValueError('checkpoint recorded before deadline')
        if checkpoint['forecast_sha256'] is None:
            if checkpoint['fresh'] or checkpoint['age_minutes'] is not None:
                raise ValueError('missing forecast cannot be fresh')
            continue
        row = forecasts[checkpoint['forecast_sha256']]
        age = (deadline-locks.utc(row['observed_utc'])).total_seconds()/60
        if (identity[:2] != (row['revision'], row['game_id'])
                or deadline != locks.utc(row['kickoff_utc'])-dt.timedelta(minutes=identity[2])
                or age < 0 or age != checkpoint['age_minutes'] or checkpoint['fresh'] != (age <= 5)):
            raise ValueError('checkpoint differs from pre-deadline forecast')
    return len(seen)


def validate(data):
    seen = set()
    for record in locks.read(Path(data) / JOURNAL):
        payload = {k: v for k, v in record.items() if k != 'snapshot_sha256'}
        if locks.digest(payload) != record['snapshot_sha256']:
            raise ValueError('forecast refresh hash mismatch')
        key = (record['revision'], record['game_id'], record['generated_utc'])
        if key in seen:
            raise ValueError('duplicate forecast refresh')
        seen.add(key)
        generated, observed, ko = (locks.utc(record[k]) for k in ('generated_utc', 'observed_utc', 'kickoff_utc'))
        if not generated <= observed < ko:
            raise ValueError('forecast refresh was not observed before kickoff')
        row = record['board']
        if (row['game_id'] != record['game_id'] or kickoff(row) != ko
                or record['basis'] != 'diagnostic pregame refresh; not an ATS lock'):
            raise ValueError('forecast refresh identity mismatch')
    return len(seen)


def record(data, latest, now=None, sharded=False):
    """Preserve each observed pregame board once, with the map and injury evidence."""
    import json
    import pandas as pd
    import fixed_bands

    data = Path(data)
    validate(data)
    if latest is None or latest.get('board', pd.DataFrame()).empty:
        return 0
    manifest = latest['manifest']
    if not manifest.get('generated_utc'):
        return 0
    now = locks.utc(now or dt.datetime.now(dt.timezone.utc))
    generated = locks.utc(manifest['generated_utc'])
    if generated > now:
        return 0
    seen = {(r['revision'], r['game_id'], r['generated_utc']) for r in (timing_rows(data) if sharded else locks.read(data / JOURNAL))}
    # pandas serializes missing numeric values as JSON null, never NaN.
    rows = json.loads(latest['board'].to_json(orient='records', double_precision=15))
    added = []
    for row in rows:
        ko = kickoff(row)
        identity = (manifest['revision'], row['game_id'], manifest['generated_utc'])
        if identity in seen or ko is None or now >= ko or row.get('result') is not None:
            continue
        rule = fixed_bands.rule_for(latest.get('fixed_band_rules', []), int(row['season']), int(row['week']), weekly=True)
        record = dict(revision=manifest['revision'], game_id=row['game_id'],
                      generated_utc=manifest['generated_utc'], observed_utc=now.isoformat(),
                      kickoff_utc=ko.isoformat(), config_signature=manifest.get('config_signature'),
                      basis='diagnostic pregame refresh; not an ATS lock', board=row, fixed_rule=rule)
        record['snapshot_sha256'] = locks.digest(record)
        added.append(record)
        seen.add(identity)
    if sharded:
        for row in added:
            path = data/'timing_forecasts'/row['game_id']/(row['snapshot_sha256']+'.json')
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(json.dumps(row, sort_keys=True, allow_nan=False)+'\n')
    else:
        locks.append(data / JOURNAL, added)
    validate(data)
    return len(added)
