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
WATCHER_POLICY = 'median-mov-weekly-decay-ats-t60-durable-2026-11-10-v4'
POLICIES[WATCHER_POLICY] = True
POLICY_METHODS[WATCHER_POLICY] = 'weighted_median_signed_mov_weekly_decay'
REPLACEMENT_POLICY = 'median-mov-weekly-decay-ats-t60-durable-replacement-minus2-2026-11-13-v5'
QB_REPLACEMENT_POLICY = 'replacement-team-margin-minus2-2026-11-13-v1'
POLICIES[REPLACEMENT_POLICY] = True
POLICY_METHODS[REPLACEMENT_POLICY] = 'weighted_median_signed_mov_weekly_decay'
DURABLE_POLICIES = (WATCHER_POLICY, REPLACEMENT_POLICY)
REPLACEMENT_FIELDS = ('home_qb_replacement','away_qb_replacement',
    'qb_replacement_base_margin','qb_replacement_margin_adjustment','qb_replacement_policy')
REPLACEMENT_TEAM_FIELDS = ('qb_replacement','qb_replacement_status','qb_projected_id',
    'qb_incumbent_id','qb_incumbent_starts','qb_incumbent_last_week',
    'qb_replacement_reference_week','qb_replacement_policy')


def policy_for_revision(revision):
    # The active controller policy; old decisions retain their saved version.
    return REPLACEMENT_POLICY if revision=='boxscore-composite-v1.24' else WATCHER_POLICY

RECEIPTS = 'candidate_receipts.jsonl'
MAX_FORECAST_AGE_MINUTES = 10
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


def runtime_stores(data):
    root = Path(data)/'lock_runtime'
    return ([root] + sorted(p for p in root.glob('*_week??') if p.is_dir())) if root.exists() else []


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


def _replacement_value(value):
    if value is None or str(value).strip().lower() in ('','nan','none','null'): return None
    if isinstance(value,bool):return float(value)
    number=float(value)
    if not math.isfinite(number):return None
    return number


def replacement_payload(raw, base):
    """Freeze the exact overlay metadata rather than reapplying a possibly rounded map."""
    payload={}
    for side in ('home','away'):
        for field in REPLACEMENT_TEAM_FIELDS:
            value=raw.get(side+'_'+field)
            if field in ('qb_replacement','qb_incumbent_starts','qb_incumbent_last_week','qb_replacement_reference_week'):
                value=_replacement_value(value)
            elif value is None or str(value).strip().lower() in ('','nan','none','null'):
                value=None
            payload[side+'_'+field]=value
    for field in REPLACEMENT_FIELDS[2:]:
        payload[field]=(raw.get(field) if field=='qb_replacement_policy' else _replacement_value(raw.get(field)))
    payload['fixed_band_spread']=_replacement_value(raw.get('fixed_band_spread'))
    nested=dict(home=payload['home_qb_replacement'],away=payload['away_qb_replacement'],
                base_margin=payload['qb_replacement_base_margin'],
                margin_adjustment=payload['qb_replacement_margin_adjustment'],
                policy=payload['qb_replacement_policy'])
    for side in ('home','away'):
        nested[side+'_metadata']={field:payload[side+'_'+field] for field in REPLACEMENT_TEAM_FIELDS}
    payload['qb_replacement']=nested
    validate_replacement(dict(payload,revision='boxscore-composite-v1.24',week=raw.get('week')),base)
    return {k:v for k,v in payload.items() if k!='fixed_band_spread'}


def validate_replacement(row, base):
    """Recompute one final-margin overlay and require nested/flat provenance agreement."""
    try:
        if row.get('qb_replacement_policy')!=QB_REPLACEMENT_POLICY:
            raise ValueError('unknown replacement margin policy')
        home=_replacement_value(row['home_qb_replacement'])
        away=_replacement_value(row['away_qb_replacement'])
        if home not in (None,0.,1.) or away not in (None,0.,1.):
            raise ValueError('replacement flags must be binary or unresolved')
        adjustment=-2.*home+2.*away if home is not None and away is not None else 0.
        saved_base=_replacement_value(row['qb_replacement_base_margin'])
        saved_adjustment=_replacement_value(row['qb_replacement_margin_adjustment'])
        if saved_base is None or abs(saved_base-base)>EPS or saved_adjustment is None or abs(saved_adjustment-adjustment)>EPS:
            raise ValueError('replacement base map or two-point adjustment mismatch')
        if abs(float(row['fixed_band_spread'])-(base+adjustment))>EPS:
            raise ValueError('replacement overlay must be applied exactly once after the map')
        nested=row['qb_replacement']
        expected=dict(home=home,away=away,base_margin=saved_base,margin_adjustment=saved_adjustment,policy=QB_REPLACEMENT_POLICY)
        if any(nested.get(k)!=v for k,v in expected.items()):
            raise ValueError('nested and flat replacement metadata differ')
        for side in ('home','away'):
            metadata=nested.get(side+'_metadata',{})
            for field in REPLACEMENT_TEAM_FIELDS:
                if metadata.get(field)!=row.get(side+'_'+field):
                    raise ValueError('nested and flat replacement team evidence differ')
            flag=home if side=='home' else away
            if row.get(side+'_qb_replacement_policy')!=QB_REPLACEMENT_POLICY:
                raise ValueError('replacement team policy missing')
            if flag is not None and not row.get(side+'_qb_projected_id'):
                raise ValueError('resolved replacement flag has no projected QB identity')
            if flag==1.:
                if (not row.get(side+'_qb_incumbent_id') or float(row.get(side+'_qb_incumbent_starts') or 0)<2
                        or row.get(side+'_qb_projected_id')==row.get(side+'_qb_incumbent_id')):
                    raise ValueError('replacement flag has no different established incumbent')
                week=int(row['week'])
                last=_replacement_value(row.get(side+'_qb_incumbent_last_week'))
                reference=_replacement_value(row.get(side+'_qb_replacement_reference_week'))
                if last is None or reference is None or not last<week or not reference<week:
                    raise ValueError('replacement incumbent evidence is not strictly before the game')
        return base+adjustment
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError(f'ATS replacement margin invalid: {exc}') from exc


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
        if row['revision']=='boxscore-composite-v1.24':
            if row['policy_version']!=REPLACEMENT_POLICY or row.get('availability_policy') is None:
                raise ValueError('v1.24 requires replacement policy and availability evidence')
            mapped = validate_replacement(row, mapped)
        elif row['policy_version']==REPLACEMENT_POLICY:
            raise ValueError('Replacement lock policy requires v1.24')
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
        if row['policy_version'] in DURABLE_POLICIES:
            q = row.get('espn_quote')
            if (not q or not dt.timedelta(0) <= cutoff-generated <= dt.timedelta(minutes=MAX_FORECAST_AGE_MINUTES)
                    or not dt.timedelta(0) <= generated-utc(q['captured_utc']) <= dt.timedelta(minutes=5)):
                raise ValueError('Watcher candidate needs fresh forecast and captured price')
            audit = row.get('scoring_audit')
            if row['revision'] in ('boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24') and not audit:
                raise ValueError('Watcher candidate is missing its prepared scoring audit')
            if audit is not None:
                import nfl_model as m
                import pandas as pd
                check = pd.DataFrame([audit['inputs']])
                check['q'] = m.market_ml_wp(check)
                fit = audit['fit']
                if ((fit['fit_season'], fit['fit_week']) != (row['season'], row['week'])
                        or (fit['training_max_season'], fit['training_max_week_in_latest_season']) >= (row['season'], row['week'])):
                    raise ValueError('Watcher scoring fit uses current/future weeks')
                if abs(float(m.apply_fit(check, audit['fit'])[0])-wp) > 1e-10:
                    raise ValueError('Watcher probability differs from its prepared fit and quote')
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
        if row['policy_version'] in DURABLE_POLICIES:
            eligible = durable_candidates(data, eligible)
            receipt = next((r for r in read(data / RECEIPTS)
                            if r['candidate_sha256'] == row['candidate_sha256']), None)
            if receipt is None or row.get('durable_commit') != receipt['commit'] or row.get('durable_utc') != receipt['committed_utc']:
                raise ValueError('Watcher lock has no confirmed pre-cutoff save')
        if not eligible:
            raise ValueError('No eligible persisted candidate')
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
            if row['revision'] in ('boxscore-composite-v1.21','boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24'):
                import availability_collect as ac
                collection=evidence.get('collection',{})
                expected_policy=ac.REPORTS_POLICY if row['revision'] in ('boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24') else ac.POLICY
                if collection.get('policy')!=expected_policy:
                    raise ValueError('collection policy does not match the saved revision')
                if row['revision'] in ('boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24') and any(
                        f.get('source_kind')=='official_team_news' for f in evidence['observations']):
                    raise ValueError('RSS/news is retired for v1.22')
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


def durable_candidates(data, candidates):
    receipts = {r['candidate_sha256']: r for r in read(Path(data) / RECEIPTS)}
    return [c for c in candidates if c['policy_version'] not in DURABLE_POLICIES or (
        c['candidate_sha256'] in receipts
        and utc(c['observed_utc']) <= utc(receipts[c['candidate_sha256']]['committed_utc']) <= utc(c['lock_at_utc'])
        and len(receipts[c['candidate_sha256']]['commit']) == 40)]


def record(data='data', now=None, policy_version=None, finalize=True):
    """Save refreshes before T−60; finalize only already-persisted candidates."""
    import nfl_model as m
    from schedule_gate import kickoff

    data = Path(data)
    requested_policy = policy_version
    policy_version = policy_version or POLICY_VERSION
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
        policy_version = requested_policy or (policy_for_revision(manifest['revision']) if manifest['revision']=='boxscore-composite-v1.24' else POLICY_VERSION)
        if manifest['revision']=='boxscore-composite-v1.24' and policy_version!=REPLACEMENT_POLICY:
            raise ValueError('v1.24 candidates must use the replacement lock policy')
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
                if manifest['revision'] in ('boxscore-composite-v1.20','boxscore-composite-v1.21','boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24') and raw.get('availability_policy')!=m.AVAILABILITY_POLICY:
                    continue  # no v1.20 lock from a legacy board that lost its evidence columns
                if (manifest.get('recipe') or {}).get('family') in m.AVAIL_FAMILIES and not m.injury_reports_ready(raw, ko, now):
                    continue
                availability = None
                if raw.get('availability_policy')==m.AVAILABILITY_POLICY:
                    availability=m.availability_snapshot(raw,ko,generated)
                    if availability is None: continue
                if manifest['revision'] in ('boxscore-composite-v1.21','boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24'):
                    import availability_collect as ac
                    if not availability or any(not ac.collection_ready(e.get('collection',{}),cutoff,require_inactives=True)
                                               for e in availability.values()):continue
                    expected=ac.REPORTS_POLICY if manifest['revision'] in ('boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24') else ac.POLICY
                    if any(e.get('collection',{}).get('policy')!=expected for e in availability.values()):continue
                try:
                    wp, line = float(raw['model_wp']), float(raw['spread_line'])
                except (KeyError, TypeError, ValueError):
                    continue
                import fixed_bands
                season, week = int(raw['season']), int(raw['week'])
                weekly = policy_version in POLICY_METHODS
                rule = fixed_bands.rule_for(rules, season, week, weekly=weekly)
                if rule is None and history is not None:
                    rule = (fixed_bands.fit_weekly(history, season, week) if weekly
                            else fixed_bands.fit(history, season))
                if not fixed_bands.trained_before(rule, season, week) or not 0 < wp < 1 or not math.isfinite(line):
                    continue
                if rule.get('method') != POLICY_METHODS.get(policy_version, fixed_bands.METHOD):
                    raise ValueError('ATS lock rule does not match the lock policy\'s median map')
                # Use the production conversion, including its exact floating-
                # point behavior at 3/7/10, rather than a second inverse CDF.
                x = float(m.implied_spread([wp])[0])
                band = sum(abs(x) >= cut for cut in rule['cuts'])
                mapped = (1 if x > 0 else -1 if x < 0 else 0) * rule['magnitudes'][band]
                replacement = None
                if manifest['revision']=='boxscore-composite-v1.24':
                    try:
                        replacement = replacement_payload(raw, mapped)
                        mapped = float(replacement['qb_replacement_base_margin'])+float(replacement['qb_replacement_margin_adjustment'])
                    except (KeyError,TypeError,ValueError):
                        continue
                side = select(mapped, line, POLICIES[policy_version])
                row = dict(revision=manifest['revision'], game_id=raw['game_id'],
                           season=int(raw['season']), week=int(raw['week']), home=raw['home'], away=raw['away'],
                           generated_utc=generated.isoformat(), observed_utc=now.isoformat(), kickoff_utc=ko.isoformat(),
                           lock_at_utc=cutoff.isoformat(), lock_lead_minutes=LEAD_MINUTES, policy_version=policy_version,
                           model_wp=wp, raw_spread=x, market_spread=line, fixed_band_spread=float(mapped),
                           selected_side=side, skip_reason='zero_edge' if not side else None,
                           fixed_rule=rule, config_signature=manifest.get('config_signature'),
                           quote_basis='source quote has no independent capture timestamp')
                if replacement is not None:
                    row.update(replacement)
                    validate_replacement(row, float(replacement['qb_replacement_base_margin']))
                import espn_spreads
                if raw.get('availability_policy')==m.AVAILABILITY_POLICY:
                    row['availability_policy']=m.AVAILABILITY_POLICY
                    row['availability']=availability
                    validate_availability(row)
                row['espn_quote'] = espn_spreads.candidate_quote(row, data)
                row['espn_quote_status'] = 'captured_prelock' if row['espn_quote'] else 'no_matching_prelock_price'
                if policy_version in DURABLE_POLICIES:
                    if raw.get('score_quote'):
                        quote = json.loads(raw['score_quote'])
                        row['espn_quote'] = espn_spreads.match(row, [quote], allow_close=False).get('espn_quote')
                    q = row['espn_quote']
                    if (not q or cutoff-generated > dt.timedelta(minutes=MAX_FORECAST_AGE_MINUTES)
                            or not dt.timedelta(0) <= generated-utc(q['captured_utc']) <= dt.timedelta(minutes=5)):
                        continue
                    if manifest.get('fit'):
                        fit = manifest['fit']
                        columns = set(fit['names']) | set(m.PRODUCT_CONTEXT_NAMES) | {'home_moneyline', 'away_moneyline'}
                        inputs = {c: float(raw[c]) if raw.get(c) and math.isfinite(float(raw[c])) else None for c in columns}
                        row['scoring_audit'] = dict(fit=fit, inputs=inputs,
                            prepared_bundle_sha256=manifest['prepared_bundle_sha256'])
                    elif manifest['revision'] in ('boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24'):
                        continue
                row['candidate_sha256'] = digest(row)
                added.append(row)
                seen.add(candidate_id)
    append(data / CANDIDATES, added)
    candidates.extend(added)
    grouped = {}
    for row in durable_candidates(data, candidates) if finalize else []:
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
        if row['policy_version'] in DURABLE_POLICIES:
            receipt = next(r for r in read(data / RECEIPTS) if r['candidate_sha256'] == row['candidate_sha256'])
            lock.update(durable_commit=receipt['commit'], durable_utc=receipt['committed_utc'])
        if now >= utc(row['kickoff_utc']):
            lock.update(recovered_after_kickoff=True, finalization_policy_version=RECOVERY_POLICY)
        frozen.append(lock)
    append(data / LOCKS, frozen)
    validate_store(data)
    write_capture_status(data, now)
    return {'candidates': len(added), 'locks': len(frozen)}


def write_capture_status(data='data', now=None):
    """Explain unsaved decisions without creating or changing an archived pick."""
    import nfl_model as m
    import availability_collect as ac
    from schedule_gate import kickoff

    data = Path(data)
    now = utc(now or dt.datetime.now(dt.timezone.utc))
    latest = data / 'latest'
    if not (latest / 'manifest.json').exists() or not (latest / 'board.csv').exists():
        return
    manifest = json.loads((latest / 'manifest.json').read_text())
    generated = utc(manifest['generated_utc'])
    # The watcher keeps its candidates and locks in its own runtime stores.
    stores = [data] + runtime_stores(data)
    records = {key(r): r for store in stores for r in read(store / LOCKS)}
    locked = set(current_records(records, manifest['revision']))
    candidates = {key(r) for store in stores
                  for r in durable_candidates(store, read(store / CANDIDATES))}
    games = []
    with (latest / 'board.csv').open(newline='') as src:
        for raw in csv.DictReader(src):
            ko = kickoff(raw)
            if ko is None or now > ko + dt.timedelta(hours=FINALIZATION_GRACE_HOURS):
                continue
            identity = (manifest['revision'], raw['game_id'])
            cutoff = deadline(ko)
            issues = []
            if identity in locked:
                state = 'locked'
            elif identity in candidates:
                state = 'candidate saved; awaiting finalization'
            else:
                state = 'missed cutoff' if now >= cutoff else 'awaiting candidate'
                if raw.get('ready') != 'True':issues.append('model history not ready')
                if not generated <= now <= cutoff:issues.append('current board cannot be captured before the cutoff')
                if manifest['revision'] in ('boxscore-composite-v1.20','boxscore-composite-v1.21','boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24'):
                    if raw.get('availability_policy') != m.AVAILABILITY_POLICY:
                        issues.append('forecast availability evidence missing')
                    else:
                        for side in ('home','away'):
                            try:
                                e = json.loads(raw[side+'_availability_evidence'])
                                issues.extend(raw[side]+': '+str(b) for b in e.get('blockers',[]))
                                if not e.get('report_complete'):issues.append(raw[side]+': final report incomplete')
                                if manifest['revision'] in ('boxscore-composite-v1.21','boxscore-composite-v1.22','boxscore-composite-v1.23','boxscore-composite-v1.24'):
                                    issues.extend(raw[side]+': '+b for b in ac.readiness_issues(e.get('collection',{}),cutoff,True))
                            except (KeyError,ValueError,TypeError):
                                issues.append(raw[side]+': forecast availability evidence invalid')
                        if m.availability_snapshot(raw,ko,generated) is None:
                            issues.append('forecast availability validation failed')
                if not issues:issues.append('candidate rejected; check market line and fitted map')
            games.append(dict(game_id=raw['game_id'],state=state,lock_at_utc=cutoff.isoformat(),issues=issues))
    payload=dict(updated_utc=now.isoformat(),revision=manifest['revision'],forecast_utc=generated.isoformat(),games=games)
    path=data/'ats_capture_status.json'
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(payload,sort_keys=True,indent=2)+'\n');temporary.replace(path)


def display_records(data='data'):
    """New timed locks plus legacy archive decisions for pre-adoption deadlines."""
    data = Path(data)
    validate_store(data)
    out = {key(r): r for r in read(data / LOCKS)}
    for runtime in runtime_stores(data):
        validate_store(runtime)
        for row in read(runtime / LOCKS):
            if key(row) in out and out[key(row)] != row:
                raise ValueError('Conflicting immutable ATS selections')
            out[key(row)] = row
    for row in read(data / 'ats_forward_shadow.jsonl'):
        if key(row) in out or deadline(row['kickoff_utc']) >= ADOPTED_UTC:
            continue
        out[key(row)] = dict(row, model_wp=NormalDist().cdf(row['raw_spread'] / 12.37),
                             lock_at_utc=row['archived_utc'], legacy_lock=True)
    return out


RSS_RETIRED_UTC = utc('2026-11-09T19:30:00+00:00')
QB_REPAIRS_UTC = utc('2026-11-14T00:00:00+00:00')


def current_records(records, revision):
    """Keep earlier saved decisions authoritative across production revisions.

    Reporting aliases only: original rows, revisions, timestamps and journals
    are unchanged. No future v1.21 decision can substitute for a v1.22 lock.
    """
    out = {k: r for k, r in records.items() if k[0] == revision}
    if revision == 'boxscore-composite-v1.23':
        for (_, game), row in current_records(records, 'boxscore-composite-v1.22').items():
            if utc(row['lock_at_utc']) < QB_REPAIRS_UTC:
                out.setdefault((revision, game), row)
    if revision in ('boxscore-composite-v1.22','boxscore-composite-v1.23'):
        for (rev, game), row in records.items():
            if rev == 'boxscore-composite-v1.21' and utc(row['lock_at_utc']) < RSS_RETIRED_UTC:
                out.setdefault((revision, game), row)
    return out


def report(data='data'):
    info = validate_store(data)
    stores = runtime_stores(data)
    for runtime in stores:
        extra = validate_store(runtime)
        info = {k: info[k]+extra[k] for k in info}
    lines = ['ATS capture: latest saved forecast at or before kickoff minus 60 minutes.',
             f'Watcher policy: {WATCHER_POLICY}; legacy policies retain their original rows.',
             'A zero edge takes the market favorite; a pick\'em line with a zero mapped spread skips. '
             'Rows saved under the v1 policy keep their bytes and validate as skips; grading backfills '
             'them as favorite bets, labelled separately.',
             'An independent watcher refreshes prepared weekly inputs; cron is a backup wakeup only. '
             'New locks require a forecast within 10 minutes of T-60, a captured quote within 5 minutes '
             'of that forecast, complete official availability and confirmed pre-cutoff repository persistence.',
             'Both generated and observed timestamps must be at or before the cutoff. No post-cutoff input is eligible.',
             f'An already-saved candidate may be finalized up to {FINALIZATION_GRACE_HOURS} hours after kickoff '
             f'under {RECOVERY_POLICY}; its actual finalization time and recovery flag are retained.',
             'Recovered saved forecasts are reported separately from pregame-finalized locks. '
             'Automatic recovery never reconstructs missing pre-cutoff candidates. Explicit owner-requested '
             'retro locks may use a Git snapshot committed by the cutoff; they join the same lock journal '
             'and pooled results, with source hashes, original blockers and actual creation times retained.',
             'The moneyline ledger and earlier ATS shadow archive retain their original timing and records.',
             f'Store validation: PASS; {info["candidates"]} saved candidates, {info["locks"]} finalized saved decisions.']
    for row in read(Path(data) / LOCKS) + [row for runtime in stores for row in read(runtime/LOCKS)]:
        lag = (utc(row['lock_at_utc']) - utc(row['generated_utc'])).total_seconds() / 60
        lines.append(f'{row["game_id"]}: {row["selected_side"] or "skip"}; cutoff {row["lock_at_utc"]}; '
                     f'forecast {row["generated_utc"]} ({lag:.1f} min before cutoff); finalized {row["finalized_utc"]}; '
                     f'{"owner-requested retro lock" if row.get("retro_locked") else "recovered saved forecast" if row.get("recovered_after_kickoff") else "pregame finalization"}')
    return '\n'.join(lines)
