"""Read-only, independent checks of the production model and its median ATS map.

Each exported ledger is checked against the map policy it declares: the weekly decayed map
(map policy v2, owner decision 2026-11-04) or, for an export without the column, the annual
prior-season map.
For v1.24, the final 2026-onward margin also includes the independently
recomputed replacement-starter adjustment after that map.

No snapshots, recipes, probabilities, or grading policies are changed. The report
is regenerated from current data by build_site and stays in the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtri

import fixed_bands
import nfl_model as m
import ats_locks
from schedule_gate import kickoff as scheduled_kickoff

CUTS = [3., 7., 10.]
EPS = 1e-10
REPLACEMENT_REVISION = 'boxscore-composite-v1.24'
REPLACEMENT_POLICY = 'replacement-team-margin-minus2-2026-11-13-v1'


def median_rule(history, year):
    """Recompute from raw signed outcomes, independently of fixed_bands.fit."""
    tr = history[history.season < year].copy()
    tr = tr[np.isfinite(tr[['model_spread', 'result']]).all(axis=1)
            & tr.model_spread.ne(0)]
    if tr.season.nunique() < 2 or len(tr) < 300:
        return None
    band = np.searchsorted(CUTS, tr.model_spread.abs(), side='right')
    counts = [int((band == k).sum()) for k in range(4)]
    if min(counts) < 30:
        return None
    signed = np.sign(tr.model_spread.to_numpy()) * tr.result.to_numpy()
    return dict(season=int(year), training_max_season=int(tr.season.max()),
                training_games=len(tr), training_band_counts=counts,
                cuts=list(CUTS), magnitudes=[float(np.median(signed[band == k])) for k in range(4)])


def weekly_rule(history, year, week):
    """Map policy v2, recomputed independently of fixed_bands.fit_weekly: every game before
    (year, week), weight 0.5 ** (age in 19-slot seasons), weighted median per band."""
    s_, w_ = history.season.to_numpy(float), history.week.to_numpy(float)
    keep = ((s_ < year) | ((s_ == year) & (w_ < week))) & np.isfinite(history.model_spread.to_numpy(float)) \
        & np.isfinite(history.result.to_numpy(float)) & (history.model_spread.to_numpy(float) != 0)
    tr = history.loc[keep]
    if tr.loc[tr.season < year].season.nunique() < 2 or len(tr) < 300:
        return None
    band = np.searchsorted(CUTS, tr.model_spread.abs(), side='right')
    counts = [int((band == k).sum()) for k in range(4)]
    if min(counts) < 30:
        return None
    signed = np.sign(tr.model_spread.to_numpy()) * tr.result.to_numpy()
    weight = 0.5 ** (((year - tr.season.to_numpy()) * 19 + (week - tr.week.to_numpy())) / 19)
    mags = []
    for k in range(4):
        v, w = signed[band == k], weight[band == k]
        order = np.argsort(v, kind='stable'); v, w = v[order], w[order]
        below = np.cumsum(w) - w  # weight strictly before each sorted value
        half = w.sum() / 2
        i = int(np.argmax(below + w >= half * (1 - 1e-12)))
        exact = abs(below[i] + w[i] - half) <= 1e-12 * w.sum()
        mags.append(float((v[i] + v[i + 1]) / 2) if exact and i + 1 < len(v) else float(v[i]))
    last = tr.loc[tr.season == tr.season.max()]
    return dict(season=int(year), week=int(week), training_max_season=int(tr.season.max()),
                training_max_week=int(last.week.max()), training_games=len(tr), training_band_counts=counts,
                cuts=list(CUTS), magnitudes=mags)


def independent_grades(predicted, lines, margins, favorite_on_tie=True):
    """A matching line takes the market favorite (2026-10-19 rule) unless the
    line is a pick'em or the legacy skip rule is requested."""
    predicted, lines, margins = [np.asarray(v, float) for v in (predicted, lines, margins)]
    out = np.full(len(predicted), '', dtype='<U1')
    valid = np.isfinite(predicted) & np.isfinite(lines)
    tie = valid & (abs(predicted-lines) <= EPS)
    direction = np.where(tie, lines if favorite_on_tie else 0., predicted-lines)
    skipped = valid & (direction == 0)
    out[skipped] = 'S'
    played = valid & ~skipped & np.isfinite(margins)
    pushed = played & (abs(margins-lines) <= EPS)
    out[pushed] = 'P'
    decided = played & ~pushed
    out[decided] = np.where(direction[decided]*(margins[decided]-lines[decided]) > 0, 'W', 'L')
    return out


def replacement_predictions(history, mapped, saved, revision):
    """Audit the saved post-map policy without calling the production overlay.

    Earlier revisions and seasons retain their original map. Current exports
    must retain enough evidence to verify the binary flags, their pregame
    provenance, the original map and exactly one final two-point adjustment.
    Unresolved classifications are valid evidence, but never authorize a penalty.
    """
    predicted = np.asarray(mapped, float).copy()
    active = history.season.ge(2026).to_numpy() if revision == REPLACEMENT_REVISION else np.zeros(len(history), bool)
    if not active.any():
        return predicted
    if saved is None:
        raise ValueError('v1.24 historical export is missing replacement evidence')

    def number(row, name):
        value = row[name]
        if pd.isna(value) or str(value).strip() == '':
            return np.nan
        value = float(value)
        if not np.isfinite(value):
            raise ValueError(f'invalid {name}')
        return value

    def identity(row, name):
        value = row[name]
        return '' if pd.isna(value) else str(value).strip()

    for i in np.flatnonzero(active):
        row = saved.iloc[i]
        if row['qb_replacement_policy'] != REPLACEMENT_POLICY:
            raise ValueError('unknown or missing replacement margin policy')
        flags = []
        for side in ('home', 'away'):
            field = side + '_'
            flag = number(row, field + 'qb_replacement')
            status = identity(row, field + 'qb_replacement_status')
            if row[field + 'qb_replacement_policy'] != REPLACEMENT_POLICY:
                raise ValueError('replacement team policy missing')
            if np.isnan(flag):
                if not status or status in ('replacement starter', 'incumbent starter', 'no established incumbent',
                                             'incumbent no longer rostered at quarterback'):
                    raise ValueError('unresolved replacement flag has inconsistent status')
            else:
                if flag not in (0., 1.):
                    raise ValueError('replacement flags must be binary or unresolved')
                projected = identity(row, field + 'qb_projected_id')
                incumbent = identity(row, field + 'qb_incumbent_id')
                starts = number(row, field + 'qb_incumbent_starts')
                if not projected or not np.isfinite(starts) or starts < 0 or starts != int(starts):
                    raise ValueError('resolved replacement flag lacks quarterback evidence')
                if status == 'no established incumbent':
                    if flag != 0. or starts >= 2 or incumbent:
                        raise ValueError('no-incumbent classification is inconsistent')
                elif status in ('replacement starter', 'incumbent starter', 'incumbent no longer rostered at quarterback'):
                    if not incumbent or starts < 2:
                        raise ValueError('replacement classification lacks an established incumbent')
                    if ((status == 'replacement starter') != (flag == 1.)
                            or status == 'replacement starter' and projected == incumbent
                            or status == 'incumbent starter' and projected != incumbent):
                        raise ValueError('replacement flag disagrees with quarterback identities')
                    week = float(history.iloc[i].week)
                    last = number(row, field + 'qb_incumbent_last_week')
                    reference = number(row, field + 'qb_replacement_reference_week')
                    if not (0 < last < week and 0 < reference < week):
                        raise ValueError('replacement incumbent evidence is not strictly before the game')
                else:
                    raise ValueError('resolved replacement flag has unknown status')
            flags.append(flag)
        known = all(np.isfinite(flags))
        adjustment = -2. * flags[0] + 2. * flags[1] if known else 0.
        if not np.isclose(number(row, 'qb_replacement_base_margin'), predicted[i], atol=EPS, rtol=0, equal_nan=True):
            raise ValueError('replacement base does not match the independent median map')
        if not np.isclose(number(row, 'qb_replacement_margin_adjustment'), adjustment, atol=EPS, rtol=0):
            raise ValueError('replacement adjustment is not exactly two points per replacement')
        applied = known and np.isfinite(predicted[i])
        if str(row['qb_replacement_applied']).lower() != str(applied).lower():
            raise ValueError('replacement application marker disagrees with classification')
        status = 'classified' if known else 'unresolved; original margin retained'
        if row['qb_replacement_overlay_status'] != status:
            raise ValueError('replacement overlay status disagrees with classification')
        predicted[i] += adjustment
    return predicted


def replacement_export_basis(history, mapped, saved, records, native_games=()):
    """Use immutable v1.24 decisions ahead of replay, with their own map/line.

    Calibration keeps replay WP and team annotations even when a saved lock
    supplies its ATS decision. Only the frozen lock's replacement evidence can
    audit that decision. Games without a lock cannot acquire a replay after
    adoption, and a native forecast also blocks historical fallback.
    """
    base = np.asarray(mapped, float).copy()
    lines = history.spread_line.to_numpy(float).copy()
    evidence = saved.astype(object).copy() if saved is not None else None
    unavailable = np.zeros(len(history), bool)
    cutoff = pd.Timestamp('2026-11-14T00:00:00Z')
    for i, row in enumerate(history.to_dict('records')):
        if int(row['season']) != 2026:
            continue
        lock = records.get((REPLACEMENT_REVISION, row['game_id']))
        if lock is not None:
            if any(str(lock[name]) != str(row[name]) for name in ('game_id', 'home', 'away')) or any(
                    int(lock[name]) != int(row[name]) for name in ('season', 'week')):
                raise ValueError('frozen ATS lock identity differs from historical game')
            rule = lock['fixed_rule']
            raw = 12.37 * ndtri(np.clip(float(lock['model_wp']), .005, .995))
            base[i] = np.sign(raw) * rule['magnitudes'][np.searchsorted(rule['cuts'], abs(raw), side='right')]
            lines[i] = float(lock['market_spread'])
            if evidence is None:
                raise ValueError('v1.24 native ATS export is missing')
            for name in ('qb_replacement_base_margin', 'qb_replacement_margin_adjustment'):
                if not np.isclose(float(saved.iloc[i][name]), float(lock[name]), atol=EPS, rtol=0):
                    raise ValueError('exported replacement metadata differs from its frozen lock')
            if saved.iloc[i]['qb_replacement_policy'] != lock['qb_replacement_policy']:
                raise ValueError('exported replacement policy differs from its frozen lock')
            marker = lock.get('qb_replacement_applied')
            exported_marker = saved.iloc[i]['qb_replacement_applied']
            if not (pd.isna(marker) and pd.isna(exported_marker)) and str(marker).lower() != str(exported_marker).lower():
                raise ValueError('exported replacement application marker differs from its frozen lock')
            if not np.isclose(float(saved.iloc[i].fixed_band_spread), float(lock['fixed_band_spread']), atol=EPS, rtol=0):
                raise ValueError('exported ATS margin differs from its frozen lock')
            for name, value in lock.items():
                if name.startswith(('home_qb_', 'away_qb_')) or name in (
                        'qb_replacement_base_margin', 'qb_replacement_margin_adjustment', 'qb_replacement_policy'):
                    if name not in evidence:
                        evidence[name] = pd.Series(index=evidence.index, dtype=object)
                    evidence.iloc[i, evidence.columns.get_loc(name)] = np.nan if value is None else value
            known = all(lock.get(side + '_qb_replacement') in (0., 1.) for side in ('home', 'away'))
            evidence.iloc[i, evidence.columns.get_loc('qb_replacement_applied')] = known and np.isfinite(base[i])
            evidence.iloc[i, evidence.columns.get_loc('qb_replacement_overlay_status')] = (
                'classified' if known else 'unresolved; original margin retained')
        else:
            # A date-only historical row authorizes replay only when *every*
            # possible kickoff's deadline on that Eastern date predates adoption.
            kickoff = pd.to_datetime(row.get('kickoff_utc'), utc=True, errors='coerce')
            if pd.isna(kickoff):
                kickoff = scheduled_kickoff(row)
            if pd.notna(kickoff):
                before = kickoff - pd.Timedelta(hours=1) < cutoff
            else:
                day = pd.to_datetime(row.get('gameday'), format='%Y-%m-%d', errors='coerce')
                before = pd.notna(day) and ((day.normalize() + pd.Timedelta(days=1)).tz_localize(
                    'America/New_York') - pd.Timedelta(hours=1) <= cutoff)
            if row['game_id'] in native_games or not before:
                unavailable[i] = True
                lines[i] = np.nan
    if saved is not None and not np.allclose(saved.spread_line, lines, atol=EPS, rtol=0, equal_nan=True):
        raise ValueError('exported ATS line differs from its replay or frozen lock')
    predicted = replacement_predictions(history, base, evidence, REPLACEMENT_REVISION)
    predicted[unavailable] = np.nan
    return predicted, lines


def independent_moneyline(frame):
    """American-price arithmetic and W/L/push settlement from source columns."""
    p=frame.model_wp.to_numpy(float);y=frame['home won'].to_numpy(float)
    home=p>.5
    price=np.where(home,frame.home_moneyline,frame.away_moneyline).astype(float)
    valid=np.isfinite(p)&~np.isclose(p,.5)&np.isfinite(price)&(abs(price)>=100)&np.isin(y,[0.,.5,1.])
    grades=np.full(len(frame),'',dtype='<U1');units=np.full(len(frame),np.nan)
    push=valid&(y==.5);win=valid&~push&((y==1)==home);lose=valid&~push&~win
    grades[push]='P';grades[win]='W';grades[lose]='L'
    payout=np.divide(100.,-price,out=np.zeros_like(price),where=price<0)
    payout=np.where(price>0,price/100.,payout)
    units[push]=0.;units[win]=payout[win];units[lose]=-1.
    return grades,units


def record(grades):
    w, l, p, s = [int((grades == x).sum()) for x in 'WLPS']
    units = w/1.1-l
    returns=np.array([1/1.1]*w+[-1.]*l+[0.]*p)
    return dict(opportunities=w+l+p+s, selected=w+l+p, wins=w, losses=l,
                pushes=p, skips=s, units=units, roi=units/(w+l+p) if w+l+p else None,
                roi_se=float(returns.std(ddof=1)/np.sqrt(len(returns))) if len(returns)>1 else None)


def inspect(data='data'):
    data = Path(data); latest = data/'latest'
    checks = {}
    # Primary ATS capture is independent of historical exports. A standalone
    # sanity check must reject corrupt timed-lock evidence even on an otherwise
    # empty data directory; validation never rewrites either append-only store.
    timed = []; records = {}
    try:
        inventory = ats_locks.validate_store(data)
        timed = ats_locks.read(data / ats_locks.LOCKS)
        for runtime in ats_locks.runtime_stores(data):
            extra = ats_locks.validate_store(runtime)
            inventory = {k: inventory[k]+extra[k] for k in inventory}
            timed += ats_locks.read(runtime/ats_locks.LOCKS)
        for row in timed:
            key = ats_locks.key(row)
            if key in records and records[key] != row:
                raise ValueError('Conflicting immutable ATS selections')
            records[key] = row
        capture = dict(policy=ats_locks.POLICY_VERSION, candidates=inventory['candidates'],
                       timed_locks=sum(not r.get('recovered_after_kickoff') for r in timed),
                       recovered_saved_forecasts=sum(bool(r.get('recovered_after_kickoff')) for r in timed),
                       original_selections=sum(bool(r.get('selected_side')) for r in timed),
                       original_skips=sum(not r.get('selected_side') for r in timed),
                       backfilled_skips=sum(ats_locks.backfilled(r) for r in timed))
        checks['primary_ats_store_integrity'] = True
    except (ValueError, KeyError, TypeError, OverflowError, OSError) as exc:
        capture = dict(policy=ats_locks.POLICY_VERSION, error=str(exc))
        checks['primary_ats_store_integrity'] = False
    history_path = latest/'retro_ledger.csv'
    if not history_path.exists():
        return dict(checks=checks, rules=[], historical=[], native={}, ats_archive={}, ats_capture=capture,
                    status='No historical inputs yet' if all(checks.values()) else 'FAIL')
    d = pd.read_csv(history_path)
    checks['unique_historical_games'] = not d.game_id.duplicated().any()
    ml_grades,ml_units=independent_moneyline(d)
    if 'bet_result' in d:
        checks['historical_moneyline_outcomes']=bool(np.array_equal(d.bet_result.fillna('').to_numpy(),ml_grades))
        checks['historical_moneyline_returns']=bool(np.allclose(d.units,ml_units,atol=1e-10,equal_nan=True))
    d['model_spread'] = 12.37*ndtri(np.clip(d.model_wp.to_numpy(), .005, .995))
    exported = latest/'fixed_band_ledger.csv'
    saved = pd.read_csv(exported).set_index('game_id').reindex(d.game_id) if exported.exists() else None
    declared_map = (saved.get('map_policy_version', pd.Series(dtype=object)).dropna().unique().tolist()
                    if saved is not None else [fixed_bands.MAP_POLICY_VERSION])
    weekly = declared_map == [fixed_bands.MAP_POLICY_VERSION]
    checks['exported_map_policy_known'] = len(declared_map) <= 1 and (weekly or not declared_map)
    predicted = np.full(len(d), np.nan); rules = []
    if weekly:
        for year in sorted(d.season.unique()):
            ok = True; season_rules = []
            for week in sorted(d.loc[d.season.eq(year), 'week'].unique()):
                rule = weekly_rule(d, int(year), int(week))
                production = fixed_bands.fit_weekly(d, int(year), int(week))
                if (rule is None) != (production is None):
                    ok = False; continue
                if rule is None:
                    continue
                season_rules.append(rule)
                ok &= (production['magnitudes'] == rule['magnitudes']
                       and production['training_band_counts'] == rule['training_band_counts']
                       and fixed_bands.trained_before(production, int(year), int(week)))
                mask = (d.season.eq(year) & d.week.eq(week)).to_numpy(); x = d.loc[mask, 'model_spread'].to_numpy()
                predicted[mask] = np.sign(x)*np.array(rule['magnitudes'])[np.searchsorted(CUTS, abs(x), side='right')]
            if season_rules:
                rules += season_rules
                checks[f'{int(year)}_prior_only_weekly_medians'] = bool(ok)
    else:
        for year in sorted(d.season.unique()):
            rule = median_rule(d, year)
            if rule is None:
                continue
            rules.append(rule)
            mask = d.season.eq(year).to_numpy(); x = d.loc[mask, 'model_spread'].to_numpy()
            predicted[mask] = np.sign(x)*np.array(rule['magnitudes'])[np.searchsorted(CUTS, abs(x), side='right')]
            production = fixed_bands.fit(d, year)
            checks[f'{int(year)}_prior_only_medians'] = bool(production and
                production['magnitudes'] == rule['magnitudes'] and
                production['training_band_counts'] == rule['training_band_counts'] and
                production['training_max_season'] < year)
    manifest_path = latest/'manifest.json'
    revision = json.loads(manifest_path.read_text()).get('revision') if manifest_path.exists() else None
    replacement_error = None
    ats_history = d.copy()
    raw_path = data/'forward_predictions.jsonl'
    snapshots = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()] if raw_path.exists() else []
    if revision == REPLACEMENT_REVISION:
        try:
            native_games = {r['game_id'] for r in snapshots if r['revision'] == revision}
            predicted, lines = replacement_export_basis(d, predicted, saved, records, native_games)
            ats_history['spread_line'] = lines
            checks['exported_replacement_margin_evidence'] = True
        except (ValueError, KeyError, TypeError, OverflowError) as exc:
            replacement_error = str(exc)
            checks['exported_replacement_margin_evidence'] = False
    grades = independent_grades(predicted, ats_history.spread_line, d.result)
    if saved is not None:
        checks['exported_median_predictions'] = bool(np.allclose(saved.fixed_band_spread, predicted, equal_nan=True))
        # Each export is checked against the selection rule it declares; an export
        # written before the 2026-10-19 rule has no column and used the zero-edge skip.
        declared = saved.get('selection_version', pd.Series(dtype=object)).dropna().unique().tolist()
        export_rule = declared[0] if declared else 'zero-edge skip (before 2026-10-19)'
        checks['exported_selection_rule_known'] = (len(declared) <= 1 and
            export_rule in (fixed_bands.SELECTION_VERSION, 'zero-edge skip (before 2026-10-19)'))
        expected = grades if declared else independent_grades(predicted, ats_history.spread_line, d.result, False)
        checks['exported_ats_grades'] = bool(np.array_equal(saved.fixed_band_ats_result.fillna('').to_numpy(), expected))
    production_grades, _ = fixed_bands.grade(ats_history, predicted)
    checks['production_grading_matches_independent'] = bool(np.array_equal(grades, production_grades))
    saved_rules=latest/'fixed_band_rules.json'
    if saved_rules.exists():
        raw_rules=json.loads(saved_rules.read_text())
        required={'season','training_max_season','training_games','training_band_counts','cuts','magnitudes'}
        if weekly: required |= {'week','training_max_week'}
        schema=isinstance(raw_rules,list) and all(isinstance(r,dict) and required.issubset(r) for r in raw_rules)
        checks['exported_rule_schema']=schema
        rkey=(lambda r:(r['season'],r['week'])) if weekly else (lambda r:r['season'])
        stored={rkey(r):r for r in raw_rules if isinstance(r,dict) and required.issubset(r)} if schema else {}
        checks['exported_prior_season_maps']=schema and all(rkey(r) in stored and
            all(stored[rkey(r)].get(k)==v for k,v in r.items()) for r in rules)
    historical = []
    eligible = np.isin(grades, list('WLPS'))
    for label, mask in [('All', eligible)] + [(str(int(y)), eligible & d.season.eq(y).to_numpy()) for y in sorted(d.season.unique())]:
        if not mask.any():
            continue
        item = dict(season=label, **record(grades[mask]))
        item['last_week'] = int(d.loc[mask, 'week'].max()) if label != 'All' else None
        ml_bets = m.flat_bets(d.loc[mask], 'model_wp')
        ml = m.roi_summary(ml_bets)
        fav = None; common_ml = None
        if 'market_ml_wp' in d:
            fav_bets = m.flat_bets(d.loc[mask], 'market_ml_wp')
            common = ml_bets.units.notna() & fav_bets.units.notna()
            fav = m.roi_summary(fav_bets[common]); common_ml=m.roi_summary(ml_bets[common])
        item['moneyline'] = {k: ml[k] for k in ['bets','wins','losses','pushes','units','roi','roi_se','null_roi']}
        item['favorite'] = {k: fav[k] for k in ['bets','wins','losses','pushes','units','roi']} if fav else None
        item['common_moneyline'] = {k: common_ml[k] for k in ['bets','wins','losses','pushes','units','roi']} if common_ml else None
        g = d.loc[mask & d['home won'].isin([0., 1.]).to_numpy()]
        y = g['home won'].to_numpy(); p = np.clip(g.model_wp.to_numpy(),1e-12,1-1e-12)
        q = np.clip(g.market_wp.to_numpy(),1e-12,1-1e-12)
        item['scored_games'] = len(g)
        item['log_loss'] = float(-(y*np.log(p)+(1-y)*np.log1p(-p)).mean())
        item['market_log_loss'] = float(-(y*np.log(q)+(1-y)*np.log1p(-q)).mean())
        item['brier'] = float(((p-y)**2).mean())
        historical.append(item)
    native = {}
    if raw_path.exists():
        snaps = [r for r in snapshots if r['revision'] == m.REVISION]
        checks['unique_production_snapshot_keys'] = len({(r['experiment'],r['game_id']) for r in snaps}) == len(snaps)
        checks['production_snapshots_before_kickoff'] = all(pd.Timestamp(r['generated_utc']) < pd.Timestamp(r['kickoff_utc']) for r in snaps)
        native['snapshots'] = len(snaps)
    graded_path = data/'forward_ledger.csv'
    if graded_path.exists():
        from grade_ledger import summary
        g = pd.read_csv(graded_path)
        n = g[g.revision == m.REVISION]
        native_grades,native_units=independent_moneyline(n)
        checks['native_moneyline_outcomes']=bool(np.array_equal(n.bet_result.fillna('').to_numpy(),native_grades))
        checks['native_moneyline_returns']=bool(np.allclose(n.units,native_units,atol=1e-5,equal_nan=True))
        sm = summary(n)
        native.update({k:sm[k] for k in ['snapshots','graded','pending','ties']})
        native['moneyline'] = {k:sm['roi'][k] for k in ['bets','wins','losses','pushes','units','roi']}
    archive = {}; path = data/'ats_forward_shadow.jsonl'
    if path.exists():
        rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
        rows = [r for r in rows if r.get('policy_version') == fixed_bands.POLICY_VERSION]
        lookup = {(r['revision'],r['game_id']):r for r in snapshots}
        valid = [];mapped=[]
        for r in rows:
            source = lookup.get((r['revision'],r['game_id']))
            encoded = json.dumps(source,sort_keys=True,separators=(',',':')).encode() if source else b''
            valid.append(source is not None and hashlib.sha256(encoded).hexdigest() == r['source_snapshot_sha256'])
            if source:
                x=12.37*ndtri(np.clip(float(source['model_wp']),.005,.995))
                rule=r['fixed_rule'];value=np.sign(x)*rule['magnitudes'][np.searchsorted(rule['cuts'],abs(x),side='right')]
                mapped.append(abs(value-r['fixed_band_spread'])<=EPS and source['spread_line']==r['market_spread'])
        checks['median_archive_source_hashes'] = all(valid)
        checks['median_archive_matches_frozen_rule_and_line'] = len(mapped)==len(rows) and all(mapped)
        checks['median_archive_before_kickoff'] = all(pd.Timestamp(r['archived_utc']) < pd.Timestamp(r['kickoff_utc']) for r in rows)
        checks['median_archive_unique_games'] = len({r['game_id'] for r in rows}) == len(rows)
        checks['median_archive_prior_season_fit'] = all(r['fixed_rule']['training_max_season'] < r['season'] for r in rows)
        complete = set()
        if graded_path.exists():
            complete = set(g.loc[g.revision.eq(m.REVISION) & g.status.isin(['graded','tie']),'game_id'])
        archive = dict(policy=fixed_bands.POLICY_VERSION,snapshots=len(rows),completed=sum(r['game_id'] in complete for r in rows))
        archive['pending'] = archive['snapshots']-archive['completed']
        archive['original_selections'] = sum(bool(r.get('selected_side')) for r in rows)
        archive['original_skips'] = len(rows)-archive['original_selections']
        archive['backfilled_skips'] = sum(ats_locks.backfilled(r) for r in rows)
    return dict(checks=checks,rules=rules,weekly=weekly,historical=historical,native=native,ats_archive=archive,ats_capture=capture,
                export_selection=export_rule if exported.exists() else None, replacement_error=replacement_error,
                status='PASS' if all(checks.values()) else 'FAIL')


def report(data='data'):
    audit = inspect(data)
    lines = [f'Production sanity check: {m.REVISION} and the median ATS map',f"Status: {audit['status']}",
             'Basis: historical replay, legacy moneyline snapshots, earlier ATS archives and timed ATS locks remain separate.',
             ('ATS map policy v2: weekly weighted medians of signed pick margins (one-season half-life), '
              'including losses and tied finals; games before the forecast week only.' if audit.get('weekly', True) else
              'ATS: signed pick-margin medians, including losses and tied finals; strictly earlier seasons only.'),
             'Grading: forecast-minus-market chooses side; equality within 1e-10 takes the market favorite '
             '(a pick\'em line skips) before push grading.',
             'Returns: 1u risk at assumed -110, wins +1/1.1, losses -1, pushes 0; skips excluded from ROI stakes.',
             'Source prices have no independent quote timestamp; historical ATS returns are proxy reconstructions.', '']
    for name, ok in audit['checks'].items():lines.append(f"  {'PASS' if ok else 'FAIL'} {name}")
    if 'exported_replacement_margin_evidence' in audit['checks']:
        lines.append('  v1.24 final margin (2026 onward): median map - 2 × home replacement '
                     '+ 2 × away replacement; either unresolved flag retains the original map.')
    if audit.get('replacement_error'):
        lines.append(f"  Replacement margin evidence: {audit['replacement_error']}")
    if audit.get('export_selection'):
        lines.append(f"  Exported ATS selection rule: {audit['export_selection']}")
    if audit.get('weekly'):
        lines += ['', 'Weekly maps, last week of each season (training ends before the forecast week):']
        last = {}
        for r in audit['rules']: last[r['season']] = r
        for r in last.values():
            n = sum(x['season'] == r['season'] for x in audit['rules'])
            lines.append(f"  {r['season']} week {r['week']}: {r['magnitudes']}; prior n={r['training_games']}, "
                         f"band counts={r['training_band_counts']}, through {r['training_max_season']} week {r['training_max_week']}; "
                         f"{n} weekly rules this season")
    else:
        lines += ['', 'Prior-season maps (training excludes the forecast season):']
        for r in audit['rules']:
            lines.append(f"  {r['season']}: {r['magnitudes']}; prior n={r['training_games']}, band counts={r['training_band_counts']}, through {r['training_max_season']}")
    lines += ['', 'Historical replay: median ATS versus moneyline on identical game opportunities:']
    for r in audit['historical']:
        ml = r['moneyline']; baseline = r['favorite']
        se=f" +/- {100*r['roi_se']:.2f}pp (1 SE)" if r['roi_se'] is not None else ''
        lines.append(f"  {r['season']}: ATS {r['wins']}-{r['losses']}-{r['pushes']}, {r['skips']} skips, "
                     f"{r['selected']}/{r['opportunities']} selected, {r['units']:+.2f}u, ROI {100*r['roi']:+.2f}%{se}")
        lines.append(f"    ML {ml['wins']}-{ml['losses']}-{ml['pushes']}, {ml['units']:+.2f}u, ROI {100*ml['roi']:+.2f}% "
                     f"+/- {100*ml['roi_se']:.2f}pp (1 SE); market-correct null {100*ml['null_roi']:+.2f}%")
        if baseline:
            common=r['common_moneyline']
            lines.append(f"    Common-row ML/favorite control n={baseline['bets']} (excludes market pick'ems for both): "
                         f"model {common['units']:+.2f}u, ROI {100*common['roi']:+.2f}%; "
                         f"favorite {baseline['units']:+.2f}u, ROI {100*baseline['roi']:+.2f}%")
        lines.append(f"    Binary proper scores n={r['scored_games']}: log loss {r['log_loss']:.6f}, "
                     f"market {r['market_log_loss']:.6f}; Brier {r['brier']:.6f}; tied finals excluded from binary scoring.")
    lines += ['',f"Legacy native {m.REVISION} moneyline: {json.dumps(audit['native'],sort_keys=True)}",
              f"Earlier median ATS archive (development history): {json.dumps(audit['ats_archive'],sort_keys=True)}",
              f"Primary 60-minute ATS capture: {json.dumps(audit['ats_capture'],sort_keys=True)}",
              'Only timed ATS locks provide native forward ATS evidence. Original skips are decisions, not recorded bets; '
              'retrospectively backfilled favorite bets are excluded from forward evidence.',
              'Recovered saved forecasts retain pre-cutoff inputs but were finalized after kickoff; '
              'they are reported separately from pregame-finalized forward locks.',
              'The native ledger continuous-spread diagnostic is legacy conversion, not the median ATS policy.',
              'Never backfill median ATS locks for games that finished before adoption.',
              'The 2026 season overview can combine historical ML replay with recorded forecasts; recorded games take precedence once.',
              'Median ATS history currently ends at the last week present in retro_ledger.csv, not necessarily the newest completed board game.',
              'Historical development and selection are exposed; an unresolved comparison is not forward evidence of superiority.', '']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',default='data');a=p.parse_args()
    print(report(a.data));raise SystemExit(0 if inspect(a.data)['status'] != 'FAIL' else 1)


if __name__ == '__main__':main()
