"""Immutable ATS decisions at kickoff minus 60 minutes.

Candidates are observed and persisted before the cutoff. A delayed build may
finalize the latest eligible candidate, but never use post-cutoff inputs or
backfill a game after kickoff. Earlier moneyline and ATS archives stay intact.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import NormalDist

POLICY_VERSION = 'median-mov-ats-t60-2026-10-19-v1'
ADOPTED_UTC = dt.datetime.fromisoformat('2026-10-19T05:05:26+00:00')
LEAD_MINUTES = 60
CANDIDATES = 'ats_lock_candidates.jsonl'
LOCKS = 'ats_locks.jsonl'
EPS = 1e-10


def utc(value):
    value = value if isinstance(value, dt.datetime) else dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('ATS timestamps must include a timezone')
    return value.astimezone(dt.timezone.utc)


def deadline(kickoff):
    return utc(kickoff) - dt.timedelta(minutes=LEAD_MINUTES)


def digest(row):
    return hashlib.sha256(json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def append(path, rows):
    if not rows:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as out:
        for row in rows:
            out.write(json.dumps(row, sort_keys=True, allow_nan=False) + '\n')
        out.flush()
        os.fsync(out.fileno())


def key(row):
    return row['revision'], row['game_id']


def validate_store(data='data'):
    """Stdlib-only validation, also used before the workflow commits data/."""
    data = Path(data)
    candidates = read(data / CANDIDATES)
    by_hash = {}
    seen = set()
    for row in candidates:
        h = row['candidate_sha256']
        payload = {k: v for k, v in row.items() if k != 'candidate_sha256'}
        if digest(payload) != h:
            raise ValueError('ATS candidate hash mismatch')
        identity = (*key(row), row['generated_utc'])
        if identity in seen:
            raise ValueError('duplicate ATS candidate')
        seen.add(identity)
        cutoff = deadline(row['kickoff_utc'])
        generated, observed = utc(row['generated_utc']), utc(row['observed_utc'])
        if not ADOPTED_UTC <= generated <= observed <= cutoff or cutoff != utc(row['lock_at_utc']):
            raise ValueError('ATS candidate is outside the pre-lock cutoff')
        if row['policy_version'] != POLICY_VERSION or row['lock_lead_minutes'] != LEAD_MINUTES:
            raise ValueError('ATS candidate timing policy mismatch')
        rule = row['fixed_rule']
        if rule['training_max_season'] >= row['season']:
            raise ValueError('ATS rule uses the forecast season')
        wp, line = float(row['model_wp']), float(row['market_spread'])
        if not 0 < wp < 1 or not math.isfinite(line):
            raise ValueError('ATS candidate has invalid probability or line')
        reference = 12.37 * NormalDist().inv_cdf(min(.995, max(.005, wp)))
        x = float(row['raw_spread'])
        if not math.isfinite(x) or abs(x - reference) > EPS:
            raise ValueError('ATS raw spread does not match its saved probability')
        band = sum(abs(x) >= cut for cut in rule['cuts'])
        mapped = (1 if x > 0 else -1 if x < 0 else 0) * rule['magnitudes'][band]
        edge = mapped - line
        side = 'home' if edge > EPS else 'away' if edge < -EPS else ''
        if abs(mapped - row['fixed_band_spread']) > EPS or side != row['selected_side']:
            raise ValueError('ATS candidate does not match the saved map and line')
        if row['skip_reason'] != ('zero_edge' if not side else None):
            raise ValueError('ATS candidate skip reason mismatch')
        by_hash[h] = row
    locks = read(data / LOCKS)
    seen = set()
    for row in locks:
        if key(row) in seen:
            raise ValueError('duplicate ATS lock')
        seen.add(key(row))
        candidate = by_hash.get(row['candidate_sha256'])
        if candidate is None or any(row.get(k) != v for k, v in candidate.items()):
            raise ValueError('ATS lock differs from its saved candidate')
        cutoff, finalized, kickoff = utc(row['lock_at_utc']), utc(row['finalized_utc']), utc(row['kickoff_utc'])
        if not cutoff <= finalized < kickoff:
            raise ValueError('ATS lock finalized outside the pregame lock window')
        eligible = [c for c in candidates if key(c) == key(row)
                    and c['kickoff_utc'] == row['kickoff_utc']]
        newest = max(eligible, key=lambda c: (utc(c['generated_utc']), utc(c['observed_utc'])))
        if newest['candidate_sha256'] != row['candidate_sha256']:
            raise ValueError('ATS lock did not use the latest pre-cutoff forecast')
    return {'candidates': len(candidates), 'locks': len(locks)}


def record(data='data', now=None):
    """Save refreshes before T−60; freeze their latest eligible decision after it."""
    import nfl_model as m
    from schedule_gate import kickoff

    data = Path(data)
    now = utc(now or dt.datetime.now(dt.timezone.utc))
    validate_store(data)
    candidates, locks = read(data / CANDIDATES), read(data / LOCKS)
    locked = {key(r) for r in locks}
    seen = {(*key(r), r['generated_utc']) for r in candidates}
    latest = data / 'latest'
    added = []
    scheduled = {}
    if (latest / 'manifest.json').exists() and (latest / 'board.csv').exists():
        manifest = json.loads((latest / 'manifest.json').read_text())
        generated = utc(manifest['generated_utc'])
        rule_path = latest / 'fixed_band_rules.json'
        # The build can derive rules before render_all has exported them.
        if rule_path.exists():
            rules = json.loads(rule_path.read_text())
        elif (latest / 'retro_ledger.csv').exists():
            import pandas as pd
            import fixed_bands
            history = pd.read_csv(latest / 'retro_ledger.csv')
            history['model_spread'] = m.implied_spread(history.model_wp)
            rule = fixed_bands.fit(history, int(manifest['season']))
            rules = [rule] if rule else []
        else:
            rules = []
        rules = {r['season']: r for r in rules}
        with (latest / 'board.csv').open(newline='') as src:
            for raw in csv.DictReader(src):
                ko = kickoff(raw)
                if ko is not None:
                    scheduled[(manifest['revision'], raw['game_id'])] = ko
                if ko is None or raw.get('result', '').strip() or raw.get('ready') != 'True':
                    continue
                cutoff = deadline(ko)
                identity = (manifest['revision'], raw['game_id'])
                candidate_id = (*identity, generated.isoformat())
                if identity in locked or candidate_id in seen or not ADOPTED_UTC <= generated <= now <= cutoff:
                    continue
                if (manifest.get('recipe') or {}).get('family') in m.AVAIL_FAMILIES and not m.injury_reports_ready(raw, ko, now):
                    continue
                try:
                    wp, line = float(raw['model_wp']), float(raw['spread_line'])
                except (KeyError, TypeError, ValueError):
                    continue
                rule = rules.get(int(raw['season']))
                if not rule or rule['training_max_season'] >= int(raw['season']) or not 0 < wp < 1 or not math.isfinite(line):
                    continue
                if rule.get('method') != 'median_signed_mov':
                    raise ValueError('ATS lock requires the production median-MOV rule')
                # Use the production conversion, including its exact floating-
                # point behavior at 3/7/10, rather than a second inverse CDF.
                x = float(m.implied_spread([wp])[0])
                band = sum(abs(x) >= cut for cut in rule['cuts'])
                mapped = (1 if x > 0 else -1 if x < 0 else 0) * rule['magnitudes'][band]
                edge = mapped - line
                side = 'home' if edge > EPS else 'away' if edge < -EPS else ''
                row = dict(revision=manifest['revision'], game_id=raw['game_id'],
                           season=int(raw['season']), week=int(raw['week']), home=raw['home'], away=raw['away'],
                           generated_utc=generated.isoformat(), observed_utc=now.isoformat(), kickoff_utc=ko.isoformat(),
                           lock_at_utc=cutoff.isoformat(), lock_lead_minutes=LEAD_MINUTES, policy_version=POLICY_VERSION,
                           model_wp=wp, raw_spread=x, market_spread=line, fixed_band_spread=float(mapped),
                           selected_side=side, skip_reason='zero_edge' if not side else None,
                           fixed_rule=rule, config_signature=manifest.get('config_signature'),
                           quote_basis='source quote has no independent capture timestamp')
                row['candidate_sha256'] = digest(row)
                added.append(row)
                seen.add(candidate_id)
    append(data / CANDIDATES, added)
    candidates.extend(added)
    grouped = {}
    for row in candidates:
        scheduled_ko = scheduled.get(key(row), utc(row['kickoff_utc']))
        if (key(row) not in locked and scheduled_ko == utc(row['kickoff_utc'])
                and utc(row['lock_at_utc']) <= now < scheduled_ko):
            grouped.setdefault(key(row), []).append(row)
    frozen = []
    for rows in grouped.values():
        # Do not change a lock if a provider later moves kickoff. Each decision
        # contains the kickoff and deadline known when its candidate was saved.
        row = max(rows, key=lambda r: (utc(r['generated_utc']), utc(r['observed_utc'])))
        frozen.append(dict(row, finalized_utc=now.isoformat()))
    append(data / LOCKS, frozen)
    validate_store(data)
    return {'candidates': len(added), 'locks': len(frozen)}


def display_records(data='data'):
    """New timed locks plus legacy archive decisions for pre-adoption deadlines."""
    data = Path(data)
    validate_store(data)
    out = {key(r): r for r in read(data / LOCKS)}
    for row in read(data / 'ats_forward_shadow.jsonl'):
        if key(row) in out or deadline(row['kickoff_utc']) >= ADOPTED_UTC:
            continue
        out[key(row)] = dict(row, model_wp=NormalDist().cdf(row['raw_spread'] / 12.37),
                             lock_at_utc=row['archived_utc'], legacy_lock=True)
    return out


def report(data='data'):
    info = validate_store(data)
    lines = ['ATS capture: latest saved forecast at or before kickoff minus 60 minutes.',
             f'Policy: {POLICY_VERSION}; adopted {ADOPTED_UTC.isoformat()}.',
             'Five-minute scheduled polls refresh forecasts near the deadline; scheduler delivery can be delayed.',
             'Both generated and observed timestamps must be at or before the cutoff. No post-cutoff input is eligible.',
             'Finalization may occur after the cutoff, but must be before kickoff. Missed games are never backfilled.',
             'The moneyline ledger and earlier ATS shadow archive retain their original timing and records.',
             f'Store validation: PASS; {info["candidates"]} saved candidates, {info["locks"]} timed locks.']
    for row in read(Path(data) / LOCKS):
        lag = (utc(row['lock_at_utc']) - utc(row['generated_utc'])).total_seconds() / 60
        lines.append(f'{row["game_id"]}: {row["selected_side"] or "skip"}; cutoff {row["lock_at_utc"]}; '
                     f'forecast {row["generated_utc"]} ({lag:.1f} min before cutoff); finalized {row["finalized_utc"]}')
    return '\n'.join(lines)
