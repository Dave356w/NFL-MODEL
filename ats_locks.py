"""Immutable ATS decisions at kickoff minus 60 minutes.

Candidates are observed and persisted before the cutoff. A delayed build may
finalize the latest eligible candidate, but never use post-cutoff inputs.
Delayed finalization can recover an existing candidate for 48 hours after
kickoff, explicitly labelled separately from pregame finalizations.
Earlier moneyline and ATS archives stay intact.

Explicit owner-requested retro locks from pre-cutoff Git snapshots join this
same journal via retro_lock.py, preserving their actual creation time and source.

v2 (owner decision 2026-10-19): a zero edge takes the market favorite. Rows saved
under v1 keep their bytes and validate against v1's skip; grading and display
backfill those saved skips as favorite bets (owner decision 2026-10-19), labelled
separately from recorded selections.
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

# v3 (owner decision 2026-11-04): the weekly decayed median map (fixed_bands map policy v2).
# v1 and v2 used the annual prior-season map; their saved locks stay valid under their own rules.
POLICY_VERSION = 'median-mov-weekly-decay-ats-t60-favtie-2026-11-04-v3'
# Policy version -> whether a zero edge takes the market favorite.
POLICIES = {'median-mov-ats-t60-2026-10-19-v1': False, 'median-mov-ats-t60-favtie-2026-10-19-v2': True,
            POLICY_VERSION: True}
# Policy version -> the map method its saved rule must declare (v1/v2 rules predate the field).
POLICY_METHODS = {POLICY_VERSION: 'weighted_median_signed_mov_weekly_decay'}
ADOPTED_UTC = dt.datetime.fromisoformat('2026-10-19T05:05:26+00:00')
LEAD_MINUTES = 60
FINALIZATION_GRACE_HOURS = 48
RECOVERY_POLICY = 'saved-candidate-recovery-2026-10-20-v1'
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


def backfilled(row):
    """A saved zero-edge skip that grading now treats as a favorite bet."""
    line, mapped = row.get('market_spread'), row.get('fixed_band_spread')
    return (not row.get('selected_side') and line is not None and mapped is not None
            and select(float(mapped), float(line), True) != '')


def select(mapped, line, favorite):
    edge = mapped - line
    if abs(edge) <= EPS:
        edge = line if favorite else 0.
    return 'home' if edge > EPS else 'away' if edge < -EPS else ''


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
        if row.get('availability_policy') is not None:
            validate_availability(row)
        if row['policy_version'] not in POLICIES or row['lock_lead_minutes'] != LEAD_MINUTES:
            raise ValueError('ATS candidate timing policy mismatch')
        rule = row['fixed_rule']
        expected_method = POLICY_METHODS.get(row['policy_version'])
        if expected_method is None:
            if rule['training_max_season'] >= row['season']:
                raise ValueError('ATS rule uses the forecast season')
        elif (rule.get('method') != expected_method or 'week' not in rule
              or int(rule['season']) != int(row['season']) or int(rule['week']) != int(row['week'])
              or (rule['training_max_season'], rule['training_max_week']) >= (int(row['season']), int(row['week']))):
            raise ValueError('ATS weekly rule is not fitted on games before the forecast week')
        wp, line = float(row['model_wp']), float(row['market_spread'])
        if not 0 < wp < 1 or not math.isfinite(line):
            raise ValueError('ATS candidate has invalid probability or line')
        reference = 12.37 * NormalDist().inv_cdf(min(.995, max(.005, wp)))
        x = float(row['raw_spread'])
        if not math.isfinite(x) or abs(x - reference) > EPS:
            raise ValueError('ATS raw spread does not match its saved probability')
        band = sum(abs(x) >= cut for cut in rule['cuts'])
        mapped = (1 if x > 0 else -1 if x < 0 else 0) * rule['magnitudes'][band]
        side = select(mapped, line, POLICIES[row['policy_version']])
        if abs(mapped - row['fixed_band_spread']) > EPS or side != row['selected_side']:
            raise ValueError('ATS candidate does not match the saved map and line')
        if row['skip_reason'] != ('zero_edge' if not side else None):
            raise ValueError('ATS candidate skip reason mismatch')
        if row.get('espn_quote') is not None:
            import espn_spreads
            q = row['espn_quote']
            if (q['game_id'] != row['game_id'] or utc(q['captured_utc']) > observed
                    or espn_spreads.match(row, [q], allow_close=False).get('espn_quote') != q):
                raise ValueError('ATS candidate ESPN price is not an exact pre-lock quote')
        by_hash[h] = row
    locks = read(data / LOCKS)
    seen = set()
    for row in locks:
        if key(row) in seen:
            raise ValueError('duplicate ATS lock')
        seen.add(key(row))
        if row.get('retro_locked'):
            import retro_lock
            retro_lock.validate(row)
            continue
        candidate = by_hash.get(row['candidate_sha256'])
        if candidate is None or any(row.get(k) != v for k, v in candidate.items()):
            raise ValueError('ATS lock differs from its saved candidate')
        cutoff, finalized, kickoff = utc(row['lock_at_utc']), utc(row['finalized_utc']), utc(row['kickoff_utc'])
        recovered = finalized >= kickoff
        if (not cutoff <= finalized <= kickoff + dt.timedelta(hours=FINALIZATION_GRACE_HOURS)
                or row.get('recovered_after_kickoff', False) != recovered
                or (recovered and row.get('finalization_policy_version') != RECOVERY_POLICY)):
            raise ValueError('ATS lock finalized outside the allowed window or missing recovery metadata')
        eligible = [c for c in candidates if key(c) == key(row)
                    and c['kickoff_utc'] == row['kickoff_utc']]
        newest = max(eligible, key=lambda c: (utc(c['generated_utc']), utc(c['observed_utc'])))
        if newest['candidate_sha256'] != row['candidate_sha256']:
            raise ValueError('ATS lock did not use the latest pre-cutoff forecast')
    return {'candidates': len(candidates), 'locks': len(locks)}


def validate_availability(row):
    """Stdlib-only timing and identity audit of the availability frozen in a candidate.

    Old candidates do not acquire new fields. Rehashing a new candidate cannot authorize
    evidence published, captured or effective after the forecast was generated.
    """
    try:
        if row['availability_policy']!='sourced-game-availability-2026-11-04-v1':
            raise ValueError('unknown policy')
        for side in ('home','away'):
            evidence=row['availability'][side]
            if (evidence['policy']!=row['availability_policy'] or evidence['game_id']!=row['game_id']
                    or evidence['team']!=row[side] or evidence['blockers'] or evidence['report_complete'] is not True
                    or utc(evidence['kickoff_utc'])!=utc(row['kickoff_utc'])
                    or utc(evidence['asof_utc'])>utc(row['generated_utc'])):
                raise ValueError('identity, completeness or cutoff mismatch')
            for fact in evidence['observations']:
                if (fact['game_id']!=row['game_id'] or fact['team']!=row[side] or fact['status']!='confirmed'
                        or utc(fact['published_utc'])>utc(fact['observed_utc'])
                        or any(utc(fact[c])>utc(evidence['asof_utc']) for c in ('published_utc','observed_utc','effective_utc'))):
                    raise ValueError('observation is not a confirmed pre-forecast fact')
            if row['revision']=='boxscore-composite-v1.21':
                import availability_collect as ac
                collection=evidence.get('collection',{})
                if (collection.get('team')!=row[side] or collection.get('game_id')!=row['game_id']
                        or not ac.collection_ready(collection,row['generated_utc'],require_inactives=True)
                        or not ac.collection_ready(collection,row['lock_at_utc'],require_inactives=True)):
                    raise ValueError('complete fresh official collection required through the cutoff')
                for kind,field in (('report','report_complete'),('inactives','inactives_complete')):
                    if not any(f['field']==field and f['value'] is True
                               and f.get('source_capture_sha256')==collection[kind]['source_capture_sha256']
                               for f in evidence['observations']):
                        raise ValueError('collection completeness has no matching sourced observation')
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError(f'ATS availability evidence invalid: {exc}') from exc


def record(data='data', now=None):
    """Save refreshes before T−60; finalize only already-persisted candidates."""
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
        # The build can derive rules before render_all has exported them, and an export written
        # before the weekly map has only annual rules: weekly rules are then fitted here.
        rules = json.loads(rule_path.read_text()) if rule_path.exists() else []
        history = None
        if (latest / 'retro_ledger.csv').exists():
            import pandas as pd
            history = pd.read_csv(latest / 'retro_ledger.csv')
            history['model_spread'] = m.implied_spread(history.model_wp)
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
                if manifest['revision'] in ('boxscore-composite-v1.20','boxscore-composite-v1.21') and raw.get('availability_policy')!=m.AVAILABILITY_POLICY:
                    continue  # no v1.20 lock from a legacy board that lost its evidence columns
                if (manifest.get('recipe') or {}).get('family') in m.AVAIL_FAMILIES and not m.injury_reports_ready(raw, ko, now):
                    continue
                availability = None
                if raw.get('availability_policy')==m.AVAILABILITY_POLICY:
                    availability=m.availability_snapshot(raw,ko,generated)
                    if availability is None: continue
                if manifest['revision']=='boxscore-composite-v1.21':
                    import availability_collect as ac
                    if not availability or any(not ac.collection_ready(e.get('collection',{}),cutoff,require_inactives=True)
                                               for e in availability.values()):continue
                try:
                    wp, line = float(raw['model_wp']), float(raw['spread_line'])
                except (KeyError, TypeError, ValueError):
                    continue
                import fixed_bands
                season, week = int(raw['season']), int(raw['week'])
                weekly = POLICY_VERSION in POLICY_METHODS
                rule = fixed_bands.rule_for(rules, season, week, weekly=weekly)
                if rule is None and history is not None:
                    rule = (fixed_bands.fit_weekly(history, season, week) if weekly
                            else fixed_bands.fit(history, season))
                if not fixed_bands.trained_before(rule, season, week) or not 0 < wp < 1 or not math.isfinite(line):
                    continue
                if rule.get('method') != POLICY_METHODS.get(POLICY_VERSION, fixed_bands.METHOD):
                    raise ValueError('ATS lock rule does not match the lock policy\'s median map')
                # Use the production conversion, including its exact floating-
                # point behavior at 3/7/10, rather than a second inverse CDF.
                x = float(m.implied_spread([wp])[0])
                band = sum(abs(x) >= cut for cut in rule['cuts'])
                mapped = (1 if x > 0 else -1 if x < 0 else 0) * rule['magnitudes'][band]
                side = select(mapped, line, POLICIES[POLICY_VERSION])
                row = dict(revision=manifest['revision'], game_id=raw['game_id'],
                           season=int(raw['season']), week=int(raw['week']), home=raw['home'], away=raw['away'],
                           generated_utc=generated.isoformat(), observed_utc=now.isoformat(), kickoff_utc=ko.isoformat(),
                           lock_at_utc=cutoff.isoformat(), lock_lead_minutes=LEAD_MINUTES, policy_version=POLICY_VERSION,
                           model_wp=wp, raw_spread=x, market_spread=line, fixed_band_spread=float(mapped),
                           selected_side=side, skip_reason='zero_edge' if not side else None,
                           fixed_rule=rule, config_signature=manifest.get('config_signature'),
                           quote_basis='source quote has no independent capture timestamp')
                import espn_spreads
                if raw.get('availability_policy')==m.AVAILABILITY_POLICY:
                    row['availability_policy']=m.AVAILABILITY_POLICY
                    row['availability']=availability
                    validate_availability(row)
                row['espn_quote'] = espn_spreads.candidate_quote(row, data)
                row['espn_quote_status'] = 'captured_prelock' if row['espn_quote'] else 'no_matching_prelock_price'
                row['candidate_sha256'] = digest(row)
                added.append(row)
                seen.add(candidate_id)
    append(data / CANDIDATES, added)
    candidates.extend(added)
    grouped = {}
    for row in candidates:
        scheduled_ko = scheduled.get(key(row), utc(row['kickoff_utc']))
        if (key(row) not in locked and scheduled_ko == utc(row['kickoff_utc'])
                and utc(row['lock_at_utc']) <= now <= scheduled_ko + dt.timedelta(hours=FINALIZATION_GRACE_HOURS)):
            grouped.setdefault(key(row), []).append(row)
    frozen = []
    for rows in grouped.values():
        # Do not change a lock if a provider later moves kickoff. Each decision
        # contains the kickoff and deadline known when its candidate was saved.
        row = max(rows, key=lambda r: (utc(r['generated_utc']), utc(r['observed_utc'])))
        lock = dict(row, finalized_utc=now.isoformat())
        if now >= utc(row['kickoff_utc']):
            lock.update(recovered_after_kickoff=True, finalization_policy_version=RECOVERY_POLICY)
        frozen.append(lock)
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
             'A zero edge takes the market favorite; a pick\'em line with a zero mapped spread skips. '
             'Rows saved under the v1 policy keep their bytes and validate as skips; grading backfills '
             'them as favorite bets, labelled separately.',
             'Five-minute scheduled polls refresh forecasts near the deadline; scheduler delivery can be delayed.',
             'Both generated and observed timestamps must be at or before the cutoff. No post-cutoff input is eligible.',
             f'An already-saved candidate may be finalized up to {FINALIZATION_GRACE_HOURS} hours after kickoff '
             f'under {RECOVERY_POLICY}; its actual finalization time and recovery flag are retained.',
             'Recovered saved forecasts are reported separately from pregame-finalized locks. '
             'Automatic recovery never reconstructs missing pre-cutoff candidates. Explicit owner-requested '
             'retro locks may use a Git snapshot committed by the cutoff; they join the same lock journal '
             'and pooled results, with source hashes, original blockers and actual creation times retained.',
             'The moneyline ledger and earlier ATS shadow archive retain their original timing and records.',
             f'Store validation: PASS; {info["candidates"]} saved candidates, {info["locks"]} finalized saved decisions.']
    for row in read(Path(data) / LOCKS):
        lag = (utc(row['lock_at_utc']) - utc(row['generated_utc'])).total_seconds() / 60
        lines.append(f'{row["game_id"]}: {row["selected_side"] or "skip"}; cutoff {row["lock_at_utc"]}; '
                     f'forecast {row["generated_utc"]} ({lag:.1f} min before cutoff); finalized {row["finalized_utc"]}; '
                     f'{"owner-requested retro lock" if row.get("retro_locked") else "recovered saved forecast" if row.get("recovered_after_kickoff") else "pregame finalization"}')
    return '\n'.join(lines)
