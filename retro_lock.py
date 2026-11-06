"""Apply explicit owner-requested retro locks from immutable pre-cutoff Git snapshots.

These join the normal ATS lock journal and pooled results. The actual creation time,
original availability blockers and source commit remain in the backend record. No
candidate is backdated, and no current model, availability, line or score is read.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import re
from statistics import NormalDist
import subprocess

import ats_locks as a

REQUESTS = Path(__file__).with_name('ats_retro_requests.json')
POLICY = 'owner-requested-saved-board-retro-lock-2026-11-05-v1'
PATHS = ('data/latest/manifest.json', 'data/latest/board.csv', 'data/latest/fixed_band_rules.json')


def git(*args):
    return subprocess.check_output(['git', *args], text=True)


def source_snapshot(request):
    ref = request['source_commit']
    if not re.fullmatch(r'[a-f0-9]{40}', ref):
        raise ValueError('retro lock requires a full immutable source commit')
    try:
        git('cat-file', '-e', ref + '^{commit}')
    except subprocess.CalledProcessError:
        subprocess.run(['git', 'fetch', '--no-tags', '--depth=1', 'origin', ref], check=True)
    files = {path: git('show', f'{ref}:{path}') for path in PATHS}
    manifest = json.loads(files[PATHS[0]])
    rows = [r for r in csv.DictReader(io.StringIO(files[PATHS[1]])) if r['game_id'] == request['game_id']]
    if len(rows) != 1:
        raise ValueError('retro lock source must contain exactly one matching game')
    row = rows[0]
    rules = [r for r in json.loads(files[PATHS[2]])
             if r.get('season') == int(row['season']) and r.get('week') == int(row['week'])]
    if len(rules) != 1:
        raise ValueError('retro lock needs the saved weekly map, never a newly fitted rule')
    return dict(commit_sha=ref, committed_utc=git('show', '-s', '--format=%cI', ref).strip(),
                file_sha256={p: hashlib.sha256(text.encode()).hexdigest() for p, text in files.items()},
                manifest={k: manifest[k] for k in ('revision', 'generated_utc', 'season', 'week', 'config_signature')},
                board_row=row, fixed_rule=rules[0])


def decision(source):
    """Derive a decision entirely from the source snapshot, with no result information."""
    from schedule_gate import kickoff
    raw, manifest, rule = source['board_row'], source['manifest'], source['fixed_rule']
    ko = kickoff(raw)
    if ko is None:
        raise ValueError('retro lock source kickoff missing')
    cutoff = a.deadline(ko)
    generated, committed = a.utc(manifest['generated_utc']), a.utc(source['committed_utc'])
    if not a.ADOPTED_UTC <= generated <= committed <= cutoff:
        raise ValueError('retro lock source was not committed before the cutoff')
    if (raw.get('result', '').strip() or raw.get('home_score', '').strip()
            or raw.get('away_score', '').strip() or raw.get('ready') != 'True'):
        raise ValueError('retro lock requires a ready pregame board without scores')
    season, week = int(raw['season']), int(raw['week'])
    if ((int(manifest['season']), int(manifest['week'])) != (season, week)
            or rule.get('method') != a.POLICY_METHODS[a.POLICY_VERSION]
            or (int(rule['season']), int(rule['week'])) != (season, week)
            or (rule['training_max_season'], rule['training_max_week']) >= (season, week)):
        raise ValueError('retro lock map is not the saved pre-week production rule')
    wp, line = float(raw['model_wp']), float(raw['spread_line'])
    if not 0 < wp < 1 or not math.isfinite(line):
        raise ValueError('retro lock source has an invalid probability or line')
    x = 12.37 * NormalDist().inv_cdf(min(.995, max(.005, wp)))
    band = sum(abs(x) >= c for c in rule['cuts'])
    mapped = (1 if x > 0 else -1 if x < 0 else 0) * rule['magnitudes'][band]
    side = a.select(mapped, line, True)
    return dict(revision=manifest['revision'], game_id=raw['game_id'], season=season, week=week,
                home=raw['home'], away=raw['away'], generated_utc=generated.isoformat(),
                kickoff_utc=ko.isoformat(), lock_at_utc=cutoff.isoformat(),
                lock_lead_minutes=a.LEAD_MINUTES, policy_version=a.POLICY_VERSION,
                model_wp=wp, raw_spread=x, market_spread=line, fixed_band_spread=float(mapped),
                selected_side=side, skip_reason=None if side else 'zero_edge', fixed_rule=rule,
                config_signature=manifest['config_signature'])


def validate(row):
    if row.get('retro_lock_policy') != POLICY or row.get('retro_locked') is not True:
        raise ValueError('unknown retro lock policy')
    if row.get('retro_sha256') != a.digest({k: v for k, v in row.items() if k != 'retro_sha256'}):
        raise ValueError('retro lock hash mismatch')
    source = row['source_snapshot']
    if not re.fullmatch(r'[a-f0-9]{40}', source['commit_sha']):
        raise ValueError('retro lock source commit missing')
    if set(source['file_sha256']) != set(PATHS) or any(
            not re.fullmatch(r'[a-f0-9]{64}', v) for v in source['file_sha256'].values()):
        raise ValueError('retro lock source file hashes missing')
    if any(row.get(k) != v for k, v in decision(source).items()):
        raise ValueError('retro lock differs from its saved pregame inputs')
    if (a.utc(row['finalized_utc']) < a.utc(row['lock_at_utc'])
            or row['observed_utc'] != row['finalized_utc'] or not row.get('reason')):
        raise ValueError('retro lock creation time or reason missing')


def apply(data='data', requests=None, now=None):
    requests = json.loads(REQUESTS.read_text()) if requests is None else requests
    now = a.utc(now or dt.datetime.now(dt.timezone.utc))
    a.validate_store(data)
    existing = {a.key(r): r for r in a.read(Path(data) / a.LOCKS)}
    added = []
    for request in requests:
        # An existing lock is authoritative, including on a repeated workflow run.
        if any(r['game_id'] == request['game_id'] and r.get('source_snapshot', {}).get('commit_sha')
               == request['source_commit'] for r in existing.values()):
            continue
        source = source_snapshot(request)
        row = decision(source)
        if a.key(row) in existing:
            continue
        row.update(retro_locked=True, retro_lock_policy=POLICY, reason=request['reason'],
                   source_snapshot=source, observed_utc=now.isoformat(), finalized_utc=now.isoformat())
        row['retro_sha256'] = a.digest(row)
        validate(row)
        added.append(row)
        existing[a.key(row)] = row
    a.append(Path(data) / a.LOCKS, added)
    a.validate_store(data)
    return len(added)


if __name__ == '__main__':
    print(f'Owner-requested ATS retro locks: {apply()}')
