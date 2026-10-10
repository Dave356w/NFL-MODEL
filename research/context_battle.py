"""Research context battle; protocol in CONTEXT_BATTLE.md."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import production_qualification as p
q, m, ROOT = p.q, p.m, p.ROOT
FAMILIES = ('hinge_0.5', 'hinge_1', 'hinge_1.5', 'hinge_2', 'multiscale',
            'one_extreme', 'market_context', 'early_context')
LEVEL = 1 - .05 / (2 * len(FAMILIES))


def context_features(desc, frame):
    """Pregame-only continuous, orientation-antisymmetric interactions."""
    d = desc[['ho', 'ad', 'ao', 'hd', 'product']].copy()
    extras = {}
    for t in (.5, 1., 1.5, 2.):
        cols = []
        for a, sa in [('p', 1), ('n', -1)]:
            for b, sb in [('p', 1), ('n', -1)]:
                col = f'h{t:g}_{a}{b}'
                d[col] = (np.maximum(sa*d.ho-t, 0)*np.maximum(sb*d.ad-t, 0)
                          - np.maximum(sa*d.ao-t, 0)*np.maximum(sb*d.hd-t, 0))
                cols.append(col)
        extras[f'hinge_{t:g}'] = ['product'] + cols
    extras['multiscale'] = ['product'] + sum([extras[f'hinge_{t:g}'][1:] for t in (.5, 1., 1.5)], [])
    def tail(x):
        return np.sign(x)*np.maximum(np.abs(x)-1, 0)
    d['one_extreme'] = .5*(tail(d.ho)*d.ad+d.ho*tail(d.ad)-tail(d.ao)*d.hd-d.ao*tail(d.hd))
    d['market_context'] = d['product'] * np.abs(2*frame.q-1)
    d['early_context'] = d['product'] * np.exp(-(frame.week-1)/4)
    for name in ('one_extreme', 'market_context', 'early_context'):
        extras[name] = ['product', name]
    return d, extras


def select(prior, family):
    prior = prior[prior['home won'].isin([0., 1.])]
    cols = [f'{family}__r{r:g}' for r in q.PENS]
    return min(cols, key=lambda c: (q.losses(prior['home won'], prior[c]).mean(), c))


def analyze(held, arms):
    bets = {a: m.flat_bets(held, a) for a in arms}
    common = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    proper = held['home won'].isin([0, 1]).to_numpy()
    groups = (held.season.astype(str)+'_'+held.week.astype(str)).to_numpy()
    losses = {a: q.losses(held['home won'], held[a]).to_numpy()[proper] for a in arms}
    rows, comparisons, seasons = [], [], []
    for a in arms:
        b = bets[a].loc[common]
        rows.append({'arm': a, **m.roi_summary(b), 'log_loss': float(losses[a].mean()),
                     'brier': float(((held[a]-held['home won'])**2).to_numpy()[proper].mean()),
                     'roi_interval_95': p.cluster_interval(b.units, groups[common], .95)})
        for baseline in ('fixed_market_product', 'production'):
            if a in (baseline, 'q'): continue
            du = (b.units - bets[baseline].loc[common].units).to_numpy()
            dl = losses[baseline] - losses[a]
            comparisons.append({'arm': a, 'baseline': baseline, 'roi_delta': float(du.mean()),
                'roi_delta_interval_simultaneous': p.cluster_interval(du, groups[common], LEVEL),
                'roi_delta_interval_95': p.cluster_interval(du, groups[common], .95),
                'll_gain': float(dl.mean()), 'll_gain_interval_simultaneous': p.cluster_interval(dl, groups[proper], LEVEL),
                'll_gain_interval_95': p.cluster_interval(dl, groups[proper], .95),
                'side_flips': int(((held[a]>.5)!=(held[baseline]>.5)).to_numpy()[common].sum())})
        for year in p.OUTER:
            mask = common & (held.season.to_numpy() == year)
            ps = proper & (held.season.to_numpy() == year)
            seasons.append({'arm': a, 'season': year, **m.roi_summary(bets[a].loc[mask]),
                            'log_loss': float(q.losses(held['home won'], held[a]).to_numpy()[ps].mean())})
    return rows, comparisons, seasons, common


def run(input_dir, cache_dir, output_dir):
    input_dir, cache_dir, output_dir = (x.resolve() for x in (input_dir, cache_dir, output_dir))
    for target in (input_dir, cache_dir, output_dir):
        if any(target.resolve() == ROOT/x or ROOT/x in target.resolve().parents for x in ('data', 'public')):
            raise ValueError('Research cannot write production outputs')
    # Reuse only the existing qualification runner's source/input-hash-matched grid.
    p.main(['--input-dir', str(input_dir), '--cache-dir', str(cache_dir),
            '--output-dir', str(cache_dir/'context_base_results')])
    s, boxes, av = q.prepare()
    frame = m.attach_moneylines(m.lagged_features(boxes, s, 8., av), s)
    frame['q'] = m.market_ml_wp(frame)
    f16 = m.lagged_features(boxes, s, 16., av)
    if frame.game_id.tolist() != f16.game_id.tolist(): raise ValueError('Profile alignment mismatch')
    desc = q.descriptors(f16)
    d, extras = context_features(desc, frame)
    f = pd.concat([frame, d], axis=1)
    eligible = f.ready & f['home won'].isin([0., 1.]) & np.isfinite(f.q) & np.isfinite(f['product'])
    base = pd.read_csv(cache_dir/'candidate_predictions.csv.gz')
    indexed = f.set_index('game_id', drop=False)
    out = base[p.BASE_COLS].copy()
    audit = []
    names = m.feature_names(q.BASE_FAMILY)
    for (year, week), test_rows in out.groupby(['season', 'week'], sort=True):
        test = indexed.loc[test_rows.game_id].copy()
        train = f[eligible & m.before(f, year, week)]
        for family in FAMILIES:
            for ridge in q.PENS:
                values, info = p.fit_predict(train, test, names, extras[family], .1, ridge, True)
                out.loc[test_rows.index, f'{family}__r{ridge:g}'] = values
                audit.append({'evaluation_season': int(year), 'evaluation_week': int(week),
                              'family': family, 'ridge': ridge, **info})
        if week == 1: print(f'Context fits {year}', flush=True)
    if not np.isfinite(out.iloc[:, len(p.BASE_COLS):]).all().all(): raise ValueError('Incomplete predictions')
    original, _ = p.select_outer(base, p.configurations())
    held = original[p.BASE_COLS+['production', 'fixed_market_product']].copy()
    matched = out.set_index('game_id').loc[held.game_id]
    selections = []
    for year in p.OUTER:
        mask = held.season == year
        prior = out[out.season < year]
        for family in FAMILIES:
            col = select(prior, family)
            held.loc[mask, family] = matched.loc[held.loc[mask, 'game_id'], col].to_numpy()
            held.loc[mask, family+'_fixed_r0.1'] = matched.loc[held.loc[mask, 'game_id'], family+'__r0.1'].to_numpy()
            selections.append({'evaluation_season': year, 'family': family, 'selected': col,
                               'selection_through_season': int(prior.season.max())})
    # Independently fit product alone and enforce exact fixed-model reproduction.
    fixed_key = next(k for k in base if k.startswith('fixed_market_product__'))
    for (year, week), test_rows in out.groupby(['season', 'week'], sort=True):
        tr = f[eligible & m.before(f, year, week)]
        te = indexed.loc[test_rows.game_id]
        values, _ = p.fit_predict(tr, te, names, ['product'], .1, .1, True)
        if not np.allclose(values, base.loc[test_rows.index, fixed_key], atol=1e-10, rtol=0):
            raise ValueError('Fixed comparator reproduction failed')
    committed = pd.read_csv(ROOT/'research/qualification_results/heldout_predictions.csv').set_index('game_id')
    for arm in ('production', 'fixed_market_product'):
        if not np.allclose(held[arm], committed.loc[held.game_id, arm], atol=1e-10, rtol=0):
            raise ValueError('Committed comparator reproduction failed')
    references = pd.read_csv(input_dir/'reference_audit.csv')
    if not ((references.max_reference_season < references.season) |
            ((references.max_reference_season == references.season) &
             (references.max_reference_week < references.week))).all():
        raise ValueError('Normalization timing audit failed')
    for col in ('ho', 'ad', 'ao', 'hd'):
        held[col] = indexed.loc[held.game_id, col].to_numpy()
    held['q'] = original.q
    arms = ['production', 'fixed_market_product', 'q'] + list(FAMILIES) + [a+'_fixed_r0.1' for a in FAMILIES]
    rows, comparisons, seasons, common = analyze(held, arms)
    winner = max([r for r in rows if r['arm'] in (*FAMILIES, 'fixed_market_product')],
                 key=lambda r: (r['roi'], -r['log_loss']))['arm']
    nomination = {'arm': winner, 'status': 'exposed_historical_ROI_leader_for_forward_comparison',
        'main_family': q.BASE_FAMILY, 'main_half_life': 8., 'main_ridge': .1,
        'pass_half_life': 16., 'market_logit_coefficient': 1.,
        'interaction_ridge': .1 if winner == 'fixed_market_product' else float(select(out, winner).split('__r')[1]),
        'extras': ['product'] if winner == 'fixed_market_product' else extras[winner],
        'selection_through_season': 2025, 'production_deployed': False}
    timing = pd.DataFrame(audit)
    ok = ((timing.training_max_season < timing.evaluation_season) |
          ((timing.training_max_season == timing.evaluation_season) & (timing.training_max_week < timing.evaluation_week)))
    if not ok.all() or any(x['selection_through_season'] >= x['evaluation_season'] for x in selections):
        raise ValueError('Timing audit failed')
    counts = []
    zd = desc.loc[f.game_id.isin(held.game_id)]
    for t in (.5, 1., 1.5, 2.):
        counts.append({'threshold_sd': t, 'home_both_extreme': int(((abs(zd.ho)>t)&(abs(zd.ad)>t)).sum()),
                       'away_both_extreme': int(((abs(zd.ao)>t)&(abs(zd.hd)>t)).sum())})
    result = {'basis': 'exposed historical development; weekly chronological 2023–2025',
        'proper_games': int(held['home won'].isin([0,1]).sum()), 'bets': int(common.sum()),
        'primary_confidence_level': LEVEL, 'results': rows, 'comparisons': comparisons,
        'by_season': seasons, 'context_support': counts, 'selections': selections, 'nomination': nomination,
        'fits_audited': len(audit), 'all_fits_prior_week': True, 'fixed_comparator_reproduced': True, 'committed_comparators_reproduced': True,
        'all_normalization_references_prior_week': True,
        'excluded_games': held.loc[~common, ['game_id','q']].to_dict('records')}
    output_dir.mkdir(parents=True, exist_ok=True)
    held.to_csv(output_dir/'heldout_predictions.csv', index=False)
    flips = []
    base_bets = m.flat_bets(held, 'fixed_market_product')
    for arm in FAMILIES:
        mask = common & ((held[arm]>.5)!=(held.fixed_market_product>.5)).to_numpy()
        changed = held.loc[mask, p.BASE_COLS+['ho','ad','ao','hd','fixed_market_product',arm]].copy()
        changed = changed.rename(columns={arm: 'context_probability'})
        changed['arm'] = arm
        changed['incremental_units'] = (m.flat_bets(held, arm).units-base_bets.units).loc[mask]
        flips.append(changed)
    pd.concat(flips, ignore_index=True).to_csv(output_dir/'changed_sides.csv', index=False)
    out.to_csv(cache_dir/'context_candidate_predictions.csv.gz', index=False)
    timing.to_csv(cache_dir/'context_fit_audit.csv.gz', index=False)
    for name, value in [('results.json', result), ('nominated_candidate.json', nomination)]:
        (output_dir/name).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    paths = [Path(__file__), ROOT/'research/CONTEXT_BATTLE.md', ROOT/'research/production_qualification.py',
             ROOT/'research/qualified_interactions.py', ROOT/'nfl_model.py', input_dir/'schedule.csv',
             input_dir/'boxes.csv', input_dir/'availability.pkl', cache_dir/'candidate_predictions.csv.gz']
    (output_dir/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)) if x.is_relative_to(ROOT) else str(x): p.sha(x) for x in paths}, indent=2)+'\n')
    write_report(result, output_dir)
    print(json.dumps(nomination, indent=2), flush=True)


def write_report(result, out):
    pct = lambda x: f'{100*x:+.2f}%'
    ci = lambda x: f'[{100*x[0]:+.2f}, {100*x[1]:+.2f}]'
    lines = ['# Additional context battle', '',
        f"Historical ROI leader: **{result['nomination']['arm']}**. No deployment performed.", '',
        f"Exposed 2023–2025 development: {result['bets']} common flat 1u bets, {result['proper_games']} binary proper scores. Ties push; market pickems and any exact model abstentions excluded.", '',
        'Excluded games: '+', '.join(x['game_id'] for x in result['excluded_games'])+'. Four are market pickems; 2024_17_GB_MIN is an exact model abstention. Baseline ROI therefore differs from the previous 812-bet report.', '',
        '## Primary comparison', '', '| Arm | W–L–P | Units | ROI ± SE | Market-null ROI | Log loss |',
        '|---|---:|---:|---:|---:|---:|']
    for r in result['results']:
        if '_fixed_r' in r['arm']: continue
        lines.append(f"| {r['arm']} | {r['wins']}–{r['losses']}–{r['pushes']} | {r['units']:+.2f} | {pct(r['roi'])} ± {100*r['roi_se']:.2f} | {pct(r['null_roi'])} | {r['log_loss']:.6f} |")
    lines += ['', '## Paired primary comparisons', '',
        f"Intervals are {100*LEVEL:.4f}% week-cluster bootstrap (8,000 draws), adjusted for eight context families × two comparators. ROI bounds are percentage points; positive LL gain is better.", '',
        '| Context | Comparator | ROI difference [interval] | LL gain [interval] | Side flips |', '|---|---|---|---|---:|']
    for c in result['comparisons']:
        if c['arm'] not in FAMILIES: continue
        lo, hi = c['ll_gain_interval_simultaneous']
        lines.append(f"| {c['arm']} | {c['baseline']} | {pct(c['roi_delta'])} {ci(c['roi_delta_interval_simultaneous'])} | {c['ll_gain']:+.6f} [{lo:+.6f}, {hi:+.6f}] | {c['side_flips']} |")
    lines += ['', '## Season results', '', '| Arm | Season | Units | ROI | Log loss |', '|---|---:|---:|---:|---:|']
    for r in result['by_season']:
        if '_fixed_r' in r['arm']: continue
        lines.append(f"| {r['arm']} | {r['season']} | {r['units']:+.2f} | {pct(r['roi'])} | {r['log_loss']:.6f} |")
    lines += ['', '## Fixed 0.1 interaction penalty sensitivity', '',
        'These supplemental arms hold the interaction penalty identical to fixed_market_product. They separate feature changes from earlier-season penalty selection; they are not extra confirmatory winners.', '',
        '| Arm | Units | ROI | Log loss |', '|---|---:|---:|---:|']
    for r in result['results']:
        if '_fixed_r' in r['arm']:
            lines.append(f"| {r['arm']} | {r['units']:+.2f} | {pct(r['roi'])} | {r['log_loss']:.6f} |")
    lines += ['', '## Context support', '', '| Threshold | Home both extreme | Away both extreme |', '|---:|---:|---:|']
    for r in result['context_support']:
        lines.append(f"| {r['threshold_sd']} | {r['home_both_extreme']} | {r['away_both_extreme']} |")
    lines += ['', '## Forward candidate', '', '```json', json.dumps(result['nomination'], indent=2), '```', '',
        'Coefficients refit weekly using earlier weeks only. This ROI ranking is a development nomination, not confirmed superiority: the histories were already used for feature design. Bootstrap intervals condition on the prediction process and do not capture all research selection uncertainty. Historical quotes have no independent capture timestamps; prospective input and grading prices must be captured before kickoff.', '',
        'Reproduce: `python research/context_battle.py`. Default inputs are the qualification cache; use `--input-dir research/qualified_output` for the earlier local cache. Full grids and fit audits remain in .nfl_cache; compact predictions, results, protocol and hashes are committed. Production and its ledger remain unchanged.', '']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input-dir', type=Path, default=ROOT/'.nfl_cache/production_qualification_inputs')
    ap.add_argument('--cache-dir', type=Path, default=ROOT/'.nfl_cache/production_qualification')
    ap.add_argument('--output-dir', type=Path, default=ROOT/'research/context_results')
    args = ap.parse_args()
    run(args.input_dir, args.cache_dir, args.output_dir)
