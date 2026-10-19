"""Read-only checks of stored model exports and immutable ATS evidence.

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

CUTS = [3., 7., 10.]
EPS = 1e-10
CONTINUOUS_REVISION = 'boxscore-composite-v1.19'


def exported_identity(latest):
    """Use the export's identity, even before the first build of a new revision.

    Data committed before v1.19 has a median map. Changing the imported model
    must not reinterpret or relabel those existing files as a new forecast.
    """
    path = Path(latest)/'manifest.json'
    manifest = json.loads(path.read_text()) if path.exists() else {}
    revision = manifest.get('revision', 'boxscore-composite-v1.18')
    continuous = (manifest.get('recipe', {}).get('architecture') == 'market_spread_total'
                  or revision == CONTINUOUS_REVISION)
    return revision, 'continuous' if continuous else 'median'


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
    try:
        inventory = ats_locks.validate_store(data)
        timed = ats_locks.read(data / ats_locks.LOCKS)
        capture = dict(policy=ats_locks.POLICY_VERSION, candidates=inventory['candidates'],
                       timed_locks=inventory['locks'],
                       original_selections=sum(bool(r.get('selected_side')) for r in timed),
                       original_skips=sum(not r.get('selected_side') for r in timed),
                       backfilled_skips=sum(ats_locks.backfilled(r) for r in timed))
        capture['by_revision_policy'] = [dict(revision=revision, policy=policy,
            timed_locks=sum(r.get('revision')==revision and r.get('policy_version')==policy for r in timed))
            for revision, policy in sorted({(r.get('revision', ''),r.get('policy_version', '')) for r in timed})]
        capture['current_revision'] = m.REVISION
        capture['current_revision_locks'] = sum(r.get('revision')==m.REVISION for r in timed)
        checks['primary_ats_store_integrity'] = True
    except (ValueError, KeyError, TypeError, OverflowError, OSError) as exc:
        capture = dict(policy=ats_locks.POLICY_VERSION, error=str(exc))
        checks['primary_ats_store_integrity'] = False
    history_path = latest/'retro_ledger.csv'
    historical_revision, export_mode = exported_identity(latest)
    if not history_path.exists():
        return dict(checks=checks, rules=[], historical=[], native={}, ats_archive={}, ats_capture=capture,
                    historical_revision=historical_revision, export_mode=export_mode,
                    status='No historical inputs yet' if all(checks.values()) else 'FAIL')
    d = pd.read_csv(history_path)
    checks['unique_historical_games'] = not d.game_id.duplicated().any()
    ml_grades,ml_units=independent_moneyline(d)
    if 'bet_result' in d:
        checks['historical_moneyline_outcomes']=bool(np.array_equal(d.bet_result.fillna('').to_numpy(),ml_grades))
        checks['historical_moneyline_returns']=bool(np.allclose(d.units,ml_units,atol=1e-10,equal_nan=True))
    d['model_spread'] = 12.37*ndtri(np.clip(d.model_wp.to_numpy(), .005, .995))
    predicted = np.full(len(d), np.nan); rules = []
    if export_mode == 'continuous':
        predicted[:] = d.model_spread.to_numpy()
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
    grades = independent_grades(predicted, d.spread_line, d.result)
    exported = latest/'fixed_band_ledger.csv'
    if exported.exists():
        saved = pd.read_csv(exported).set_index('game_id').reindex(d.game_id)
        checks['exported_'+export_mode+'_predictions'] = bool(np.allclose(saved.fixed_band_spread, predicted, equal_nan=True))
        # Each export is checked against the selection rule it declares; an export
        # written before the 2026-10-19 rule has no column and used the zero-edge skip.
        declared = saved.get('selection_version', pd.Series(dtype=object)).dropna().unique().tolist()
        export_rule = declared[0] if declared else 'zero-edge skip (before 2026-10-19)'
        checks['exported_selection_rule_known'] = (len(declared) <= 1 and
            (bool(declared) or export_mode != 'continuous') and
            export_rule in (fixed_bands.SELECTION_VERSION, 'zero-edge skip (before 2026-10-19)'))
        expected = grades if declared or export_mode == 'continuous' else independent_grades(predicted, d.spread_line, d.result, False)
        checks['exported_ats_grades'] = bool(np.array_equal(saved.fixed_band_ats_result.fillna('').to_numpy(), expected))
    production_grades, _ = fixed_bands.grade(d, predicted)
    checks['production_grading_matches_independent'] = bool(np.array_equal(grades, production_grades))
    saved_rules=latest/'fixed_band_rules.json'
    if saved_rules.exists():
        raw_rules=json.loads(saved_rules.read_text())
        if export_mode == 'continuous':
            checks['continuous_export_has_no_median_maps'] = raw_rules == []
        else:
            required={'season','training_max_season','training_games','training_band_counts','cuts','magnitudes'}
            schema=isinstance(raw_rules,list) and all(isinstance(r,dict) and required.issubset(r) for r in raw_rules)
            checks['exported_rule_schema']=schema
            stored={r['season']:r for r in raw_rules if isinstance(r,dict) and 'season' in r} if isinstance(raw_rules,list) else {}
            checks['exported_prior_season_maps']=all(r['season'] in stored and
                all(stored[r['season']].get(k)==v for k,v in r.items()) for r in rules)
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
    native = {}; snapshots = []; raw_path = data/'forward_predictions.jsonl'
    if raw_path.exists():
        snapshots = [json.loads(line) for line in raw_path.read_text().splitlines() if line.strip()]
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
            complete = set(g.loc[g.status.isin(['graded','tie']),['revision','game_id']].itertuples(index=False,name=None))
        archive = dict(policy=fixed_bands.POLICY_VERSION,snapshots=len(rows),completed=sum((r['revision'],r['game_id']) in complete for r in rows))
        archive['pending'] = archive['snapshots']-archive['completed']
        archive['original_selections'] = sum(bool(r.get('selected_side')) for r in rows)
        archive['original_skips'] = len(rows)-archive['original_selections']
        archive['backfilled_skips'] = sum(ats_locks.backfilled(r) for r in rows)
    return dict(checks=checks,rules=rules,historical=historical,native=native,ats_archive=archive,ats_capture=capture,
                historical_revision=historical_revision, export_mode=export_mode,
                export_selection=export_rule if exported.exists() else None,
                status='PASS' if all(checks.values()) else 'FAIL')


def report(data='data'):
    audit = inspect(data)
    mode = audit['export_mode']
    policy = 'continuous spread ATS' if mode == 'continuous' else 'fixed-band median ATS'
    lines = [f"Production sanity check: stored {audit['historical_revision']} and {policy}",f"Status: {audit['status']}",
             f'Active model revision: {m.REVISION}; stored historical exports retain their own revision.',
             'Basis: historical replay, legacy moneyline snapshots, earlier ATS archives and timed ATS locks remain separate.',
             ('ATS: continuous margin = 12.37 * inverse-normal(win probability); no median map.' if mode == 'continuous' else
              'ATS: signed pick-margin medians, including losses and tied finals; strictly earlier seasons only.'),
             'Grading: forecast-minus-market chooses side; equality within 1e-10 takes the market favorite '
             '(a pick\'em line skips) before push grading.',
             'Returns: 1u risk at assumed -110, wins +1/1.1, losses -1, pushes 0; skips excluded from ROI stakes.',
             'Source prices have no independent quote timestamp; historical ATS returns are proxy reconstructions.', '']
    for name, ok in audit['checks'].items():lines.append(f"  {'PASS' if ok else 'FAIL'} {name}")
    if audit.get('export_selection'):
        lines.append(f"  Exported ATS selection rule: {audit['export_selection']}")
    if mode == 'median':
        lines += ['', 'Prior-season maps (training excludes the forecast season):']
        for r in audit['rules']:
            lines.append(f"  {r['season']}: {r['magnitudes']}; prior n={r['training_games']}, band counts={r['training_band_counts']}, through {r['training_max_season']}")
    lines += ['', f'Historical replay: {policy} versus moneyline on identical game opportunities:']
    for r in audit['historical']:
        ml = r['moneyline']; baseline = r['favorite']
        se=f" +/- {100*r['roi_se']:.2f}pp (1 SE)" if r['roi_se'] is not None else ''
        roi_text=f"{100*r['roi']:+.2f}%" if r['roi'] is not None else 'unavailable'
        lines.append(f"  {r['season']}: ATS {r['wins']}-{r['losses']}-{r['pushes']}, {r['skips']} skips, "
                     f"{r['selected']}/{r['opportunities']} selected, {r['units']:+.2f}u, ROI {roi_text}{se}")
        lines.append(f"    ML {ml['wins']}-{ml['losses']}-{ml['pushes']}, {ml['units']:+.2f}u, ROI {100*ml['roi']:+.2f}% "
                     f"+/- {100*ml['roi_se']:.2f}pp (1 SE); market-correct null {100*ml['null_roi']:+.2f}%")
        if baseline:
            common=r['common_moneyline']
            lines.append(f"    Common-row ML/favorite control n={baseline['bets']} (excludes market pick'ems for both): "
                         f"model {common['units']:+.2f}u, ROI {100*common['roi']:+.2f}%; "
                         f"favorite {baseline['units']:+.2f}u, ROI {100*baseline['roi']:+.2f}%")
        lines.append(f"    Binary proper scores n={r['scored_games']}: log loss {r['log_loss']:.6f}, "
                     f"market {r['market_log_loss']:.6f}; Brier {r['brier']:.6f}; tied finals excluded from binary scoring.")
    lines += ['',f"Original {m.REVISION} snapshots and secondary moneyline grades: {json.dumps(audit['native'],sort_keys=True)}",
              f"Earlier median ATS archive (development history): {json.dumps(audit['ats_archive'],sort_keys=True)}",
              f"Primary 60-minute ATS capture (all revisions, with separate inventory): {json.dumps(audit['ats_capture'],sort_keys=True)}",
              'Only timed ATS locks provide native forward ATS evidence. Original skips are decisions, not recorded bets; '
              'retrospectively backfilled favorite bets are excluded from forward evidence.',
              'Older revisions keep their original continuous-spread diagnostics and median archives; no new model identity is attached to them.',
              'Never backfill native ATS locks for games that finished before adoption.',
              'Retrospectively updated forecasts are historical reconstructions and remain separate from original recorded decisions.',
              'Historical exports end at the last week present in retro_ledger.csv, not necessarily the newest completed board game.',
              'Historical development and selection are exposed; an unresolved comparison is not forward evidence of superiority.', '']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',default='data');a=p.parse_args()
    print(report(a.data));raise SystemExit(0 if inspect(a.data)['status'] != 'FAIL' else 1)


if __name__ == '__main__':main()
