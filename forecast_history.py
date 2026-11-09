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


def record(data, latest, now=None):
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
    seen = {(r['revision'], r['game_id'], r['generated_utc']) for r in locks.read(data / JOURNAL)}
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
    locks.append(data / JOURNAL, added)
    validate(data)
    return len(added)
