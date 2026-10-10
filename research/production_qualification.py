"""Chronological market comparison and production qualification (research only).

Protocol: research/PRODUCTION_QUALIFICATION.md. Never writes data/ or public/.
"""
import argparse
import hashlib
import importlib.metadata
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit

import qualified_interactions as q

m = q.m
ROOT = Path(__file__).resolve().parents[1]
ARMS = ('production', 'market_additive', 'market_product', 'market_qualified',
        'market_extreme', 'fixed_market_product')
EXTRAS = {'production': [], 'market_additive': [], 'market_product': ['product'],
          'market_qualified': ['q_pp', 'q_pn', 'q_np', 'q_nn'],
          'market_extreme': ['product', 'e_pp', 'e_pn', 'e_np', 'e_nn'],
          'fixed_market_product': ['product']}
OUTER = (2023, 2024, 2025)
LEVEL = 1 - .05 / len(ARMS)
SEED = 20261010


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configurations():
    out = {}
    for arm in ARMS:
        recipes = ([{'family': q.BASE_FAMILY, 'half_life': 8., 'ridge': .1}]
                   if arm == 'fixed_market_product' else m.candidates())
        for recipe in recipes:
            pens = ([.1] if arm == 'fixed_market_product' or not EXTRAS[arm] else q.PENS)
            for pen in pens:
                key = f'{arm}__{m.recipe_key(recipe)}__i{pen:g}'
                out[key] = {'arm': arm, **recipe, 'interaction_ridge': pen}
    return out


def fit_predict(train, test, names, extra, ridge, interaction_ridge, offset):
    """Production math, with independent interaction ridge and optional market offset."""
    year, week = int(test.season.iloc[0]), int(test.week.iloc[0])
    if not m.before(train, year, week).all():
        raise ValueError('Training includes current or future week')
    if len(train) < m.MIN_TRAIN_GAMES:
        raise ValueError('Insufficient eligible training rows')
    X = train[names + extra].to_numpy(float)
    T = test[names + extra].to_numpy(float)
    X = np.where(np.isfinite(X), X, 0.); T = np.where(np.isfinite(T), T, 0.)
    age = ((year - train.season.to_numpy()) * 19 + week - train.week.to_numpy()) / (19 * m.FIT_HALF_LIFE_SEASONS)
    w = np.exp2(-age); w /= w.sum()
    mu = w @ X
    scale = np.sqrt(w @ ((X - mu) ** 2)); scale[scale < 1e-8] = 1.; scale[0] = 1.
    X /= scale; T /= scale
    penalty = np.r_[np.full(len(names), ridge), np.full(len(extra), interaction_ridge)]
    penalty[0] *= .1
    base = logit(np.clip(train.q.to_numpy(), 1e-5, 1-1e-5)) if offset else np.zeros(len(train))
    target_base = logit(np.clip(test.q.to_numpy(), 1e-5, 1-1e-5)) if offset else np.zeros(len(test))
    y = train['home won'].to_numpy(float)

    def objective(beta):
        eta = base + X @ beta
        return (np.sum(w * (np.logaddexp(0, eta) - y * eta)) + .5 * np.sum(penalty * beta**2),
                X.T @ (w * (expit(eta) - y)) + penalty * beta)

    beta = m.checked_optimize(objective, len(penalty))
    return expit(target_base + T @ beta), {'training_games': len(train),
        'training_max_season': int(train.season.max()),
        'training_max_week': int(train.loc[train.season == train.season.max(), 'week'].max())}


def select_key(prior, configs, arm):
    """Only earlier seasons may be supplied by the caller; no ROI selection."""
    prior = prior[prior['home won'].isin([0., 1.])]
    keys = [k for k, c in configs.items() if c['arm'] == arm]
    if arm == 'production':
        frame = prior[['season', 'home won']].copy()
        for k in keys:
            frame['p__' + m.recipe_key(configs[k])] = prior[k]
        recipe, _ = m.select_recipe(frame)
        return next(k for k in keys if m.recipe_key(configs[k]) == m.recipe_key(recipe))
    y = prior['home won'].to_numpy()
    return min(keys, key=lambda k: (q.losses(y, prior[k].to_numpy()).mean(), k))


def select_outer(pred, configs):
    pieces, selections = [], []
    for year in OUTER:
        prior = pred[pred.season < year]
        if prior.season.nunique() < 2:
            raise ValueError('Need two prior validation seasons')
        part = pred[pred.season == year][BASE_COLS].copy()
        for arm in ARMS:
            key = select_key(prior, configs, arm)
            part[arm] = pred.loc[part.index, key]
            selections.append({'evaluation_season': year, 'arm': arm, 'key': key,
                               'recipe': configs[key], 'selection_through_season': int(prior.season.max()),
                               'validation_games': len(prior)})
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True), selections


BASE_COLS = ['game_id', 'season', 'week', 'home', 'away', 'home won', 'result',
             'spread_line', 'home_moneyline', 'away_moneyline', 'q']


def generate(features, desc, cache):
    configs = configurations()
    first = features[4.]
    common = (first.ready & first['home won'].isin([0., .5, 1.]) & np.isfinite(first.q)
              & np.isfinite(desc['product']) & first.season.between(2021, 2025))
    pred = first.loc[common, BASE_COLS].copy()
    values = pd.DataFrame(np.nan, index=pred.index, columns=list(configs))
    audit = []
    for h in m.TEAM_HALF_LIVES:
        f = pd.concat([features[h], desc], axis=1)
        eligible = f.ready & f['home won'].isin([0., 1.]) & np.isfinite(f['product'])
        for (year, week), test in f.loc[common].groupby(['season', 'week'], sort=True):
            before = m.before(f, year, week)
            all_train = f[eligible & before]
            priced_train = all_train[np.isfinite(all_train.q)]
            for key, cfg in configs.items():
                if cfg['half_life'] != h: continue
                offset = cfg['arm'] != 'production'
                train = priced_train if offset else all_train
                p, info = fit_predict(train, test, m.feature_names(cfg['family']), EXTRAS[cfg['arm']],
                                      cfg['ridge'], cfg['interaction_ridge'], offset)
                values.loc[test.index, key] = p
                audit.append({'evaluation_season': int(year), 'evaluation_week': int(week), 'candidate': key, **info})
            if week == 1: print(f'h{h:g}: fit {year}; {len(test)} test games', flush=True)
    if not np.isfinite(values).all().all(): raise ValueError('Incomplete candidate predictions')
    pred = pd.concat([pred, values], axis=1).reset_index(drop=True)
    pred.to_csv(cache / 'candidate_predictions.csv.gz', index=False)
    pd.DataFrame(audit).to_csv(cache / 'fit_audit.csv.gz', index=False)
    return pred, configs


def cluster_interval(values, groups, level=LEVEL, reps=8000):
    v = np.asarray(values, float); groups = np.asarray(groups)
    if not np.isfinite(v).all(): raise ValueError('Missing primary comparison values')
    a = pd.DataFrame({'v': v, 'g': groups}).groupby('g').v.agg(['sum', 'count'])
    if len(a) < 2: raise ValueError('Need at least two week clusters')
    idx = np.random.default_rng(SEED).integers(0, len(a), (reps, len(a)))
    draws = a['sum'].to_numpy()[idx].sum(1) / a['count'].to_numpy()[idx].sum(1)
    tail = (1-level)/2
    return np.quantile(draws, [tail, 1-tail]).tolist()


def gate(intervals):
    bounds = np.asarray(intervals, float)
    if bounds.shape != (3, 2) or not np.isfinite(bounds).all():
        raise ValueError('Qualification requires three finite confidence intervals')
    if np.all(bounds[:, 0] > 0): return 'pass'
    if np.any(bounds[:, 1] < 0): return 'adverse'
    return 'unresolved'


def common_bets(held):
    bets = {arm: m.flat_bets(held, arm) for arm in (*ARMS, 'q')}
    common = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    return bets, common


def summarize(held):
    bets, common = common_bets(held)
    y = held['home won'].to_numpy()
    groups = (held.season.astype(str) + '_' + held.week.astype(str)).to_numpy()
    market_loss = q.losses(y, held.q.to_numpy())
    proper = held['home won'].isin([0., 1.]).to_numpy()
    rows, seasons = [], []
    for arm in (*ARMS, 'q'):
        b = bets[arm].loc[common]; summary = m.roi_summary(b)
        realized = b.units.to_numpy(); null_excess = (b.units - b.null_ev).to_numpy()
        diff = (b.units - bets['q'].loc[common].units).to_numpy()
        primary = [cluster_interval(v, groups[common]) for v in (realized, diff, null_excess)]
        ll = q.losses(y, held[arm].to_numpy())
        rows.append({'arm': arm, **summary, 'roi_interval': primary[0],
            'roi_difference_vs_favorite': float(diff.mean()), 'favorite_difference_interval': primary[1],
            'excess_over_null': float(null_excess.mean()), 'null_excess_interval': primary[2],
            'log_loss': float(ll[proper].mean()), 'brier': float(np.mean((held[arm].to_numpy()[proper]-y[proper])**2)),
            'log_loss_gain_vs_market': float((market_loss-ll)[proper].mean()),
            'log_loss_gain_interval_95': cluster_interval((market_loss-ll)[proper], groups[proper], .95),
            'backtest_gate': 'control' if arm == 'q' else gate(primary)})
        for season in OUTER:
            mask = common & (held.season.to_numpy() == season)
            s = m.roi_summary(bets[arm].loc[mask])
            season_proper = proper & (held.season.to_numpy() == season)
            seasons.append({'arm': arm, 'season': season, **s,
                            'log_loss': float(ll[season_proper].mean())})
    return rows, seasons, {'proper_score_games': int(proper.sum()), 'ties_predicted': int((~proper).sum()), 'primary_bet_games': int(common.sum()),
        'excluded_from_primary': held.loc[~common, ['game_id', 'q']].to_dict('records')}


def write_report(result, out):
    rows = result['results']; pct = lambda x: f'{100*x:+.2f}%'
    ci = lambda x: f'[{100*x[0]:+.2f}, {100*x[1]:+.2f}]'
    nominated = result['nomination']['arm']
    lines = ['# Production model qualification backtest', '',
        '**Production status: not qualified by native forward evidence.**', '',
        f"Backtest-passing families: {result['backtest_passing_arms'] or 'none'}. Forward-test nomination: **{nominated}**.", '',
        f"Basis: exposed historical development, 2023–2025; {result['sample']['proper_score_games']} proper-score games and {result['sample']['primary_bet_games']} common flat-1u bets.", '',
        '## Betting qualification', '',
        f"Primary intervals: {100*LEVEL:.4f}% week-cluster bootstrap, Bonferroni across six families; {8000:,} draws. Bounds below are percentage points.", '',
        '| Candidate | W–L–P | Units | ROI ± SE | Market-correct null | ROI interval | Difference vs favorite interval | Null-excess interval | Gate |',
        '|---|---:|---:|---:|---:|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['arm']} | {r['wins']}–{r['losses']}–{r['pushes']} | {r['units']:+.2f} | {pct(r['roi'])} ± {100*r['roi_se']:.2f} | {pct(r['null_roi'])} | {ci(r['roi_interval'])} | {ci(r['favorite_difference_interval'])} | {ci(r['null_excess_interval'])} | {r['backtest_gate']} |")
    lines += ['', 'The gate requires all three lower bounds above zero: net profitability, superiority to the market favorite on identical games, and performance beyond the selected-side market-correct null. A positive point estimate is insufficient.', '',
        '## Probability forecasts', '', '| Candidate | Log loss | Brier | LL gain vs market [95% CI] |', '|---|---:|---:|---|']
    for r in rows:
        lo, hi = r['log_loss_gain_interval_95']
        lines.append(f"| {r['arm']} | {r['log_loss']:.6f} | {r['brier']:.6f} | {r['log_loss_gain_vs_market']:+.6f} [{lo:+.6f}, {hi:+.6f}] |")
    lines += ['', '## Season consistency', '', '| Candidate | Season | Bets | ROI | Log loss |', '|---|---:|---:|---:|---:|']
    for r in result['by_season']:
        lines.append(f"| {r['arm']} | {r['season']} | {r['bets']} | {pct(r['roi'])} | {r['log_loss']:.6f} |")
    lines += ['', '## Selected forward specification', '', '```json', json.dumps(result['nomination'], indent=2), '```', '',
        'This nomination is selected using exposed development results, not confirmed evidence. Hyperparameters are frozen in nominated_candidate.json; coefficients may refit weekly under the recorded rule. No production recipe or ledger was changed and live capture is not activated.', '',
        '## Limits and reproduction', '',
        'Historical market quotes have no independent capture timestamp; this is a closing-price benchmark. A prospective test must capture both market input and grading price before kickoff. Feature design already used these evaluation seasons. Bootstrap intervals condition on the fitted selection process and do not capture all design uncertainty.', '',
        'Run `python research/production_qualification.py`. Full candidate grids, feature caches and fit timing audits are kept under .nfl_cache or the specified cache directory; compact per-game evaluation predictions, selections, input/source hashes and results are committed alongside this report. See research/PRODUCTION_QUALIFICATION.md for the fixed protocol.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=ROOT/'.nfl_cache/production_qualification_inputs')
    parser.add_argument('--cache-dir', type=Path, default=ROOT/'.nfl_cache/production_qualification')
    parser.add_argument('--output-dir', type=Path, default=ROOT/'research/qualification_results')
    parser.add_argument('--recompute', action='store_true')
    args = parser.parse_args(argv)
    for target in (args.input_dir, args.cache_dir, args.output_dir):
        resolved = target.resolve()
        if resolved == ROOT/'data' or ROOT/'data' in resolved.parents or resolved == ROOT/'public' or ROOT/'public' in resolved.parents:
            raise ValueError('Research output cannot target production data or public')
    for p in (args.input_dir, args.cache_dir, args.output_dir): p.mkdir(parents=True, exist_ok=True)
    q.OUT = args.input_dir; q.CACHE = args.input_dir/'cache'
    s, b, av = q.prepare()
    hashes = {str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p): sha(p) for p in
        [args.input_dir/'schedule.csv', args.input_dir/'boxes.csv', args.input_dir/'availability.pkl',
         Path(__file__), ROOT/'research/qualified_interactions.py', ROOT/'nfl_model.py',
         ROOT/'research/PRODUCTION_QUALIFICATION.md']}
    signature = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    cache_meta = args.cache_dir/'signature.json'
    reuse = not args.recompute and cache_meta.exists() and json.loads(cache_meta.read_text()) == signature
    if reuse and (args.cache_dir/'candidate_predictions.csv.gz').exists():
        print('Reusing hash-matched complete predictions', flush=True)
        pred = pd.read_csv(args.cache_dir/'candidate_predictions.csv.gz'); configs = configurations()
    else:
        print('Building production profiles and raw h16 pass contexts', flush=True)
        features = {}
        for h in m.TEAM_HALF_LIVES:
            f = m.attach_moneylines(m.lagged_features(b, s, h, av), s)
            f['q'] = m.market_ml_wp(f); features[h] = f
            print(f'Profiles h{h:g}: {len(f)} rows', flush=True)
        ids = features[4.].game_id.tolist()
        if any(f.game_id.tolist() != ids for f in features.values()): raise ValueError('Profile alignment mismatch')
        desc = q.descriptors(features[16.])
        pred, configs = generate(features, desc, args.cache_dir)
        cache_meta.write_text(json.dumps(signature))
    held, selections = select_outer(pred, configs)
    if held.game_id.duplicated().any(): raise ValueError('Duplicate evaluation games')
    timing = pd.read_csv(args.cache_dir/'fit_audit.csv.gz')
    references = pd.read_csv(args.input_dir/'reference_audit.csv')
    fit_ok = ((timing.training_max_season < timing.evaluation_season) |
              ((timing.training_max_season == timing.evaluation_season) &
               (timing.training_max_week < timing.evaluation_week)))
    reference_ok = ((references.max_reference_season < references.season) |
                    ((references.max_reference_season == references.season) &
                     (references.max_reference_week < references.week)))
    if not fit_ok.all() or not reference_ok.all(): raise ValueError('Timing audit failed')
    if any(s['selection_through_season'] >= s['evaluation_season'] for s in selections):
        raise ValueError('Selection includes evaluation season')
    rows, seasons, sample = summarize(held)
    passing = [r['arm'] for r in rows if r['backtest_gate'] == 'pass']
    pool = [r for r in rows if r['arm'] in passing] if passing else [r for r in rows if r['arm'].startswith(('market_', 'fixed_market_'))]
    nominated = min(pool, key=lambda r: (r['log_loss'], r['arm']))['arm']
    final_key = select_key(pred, configs, nominated)
    nomination = {'arm': nominated, 'key': final_key, 'recipe': configs[final_key],
                  'selection_through_season': 2025, 'status': 'backtest_pass_requires_forward' if nominated in passing else 'unqualified_forward_candidate',
                  'market_offset': nominated != 'production', 'market_quote_contract': 'first qualifying pregame snapshot; input and grading use same moneylines',
                  'pass_profile_half_life': 16., 'normalization': 'prior-week season center; trailing-four-season SD; orientations pooled',
                  'coefficient_refit': 'weekly, earlier weeks only, two-season fit decay',
                  'extras': EXTRAS[nominated]}
    result = {'basis': 'exposed chronological historical development; no native forward evidence',
              'production_qualified': False, 'backtest_passing_arms': passing, 'nomination': nomination,
              'results': rows, 'by_season': seasons, 'sample': sample,
              'primary_confidence_level': LEVEL, 'bootstrap_draws': 8000, 'seed': SEED,
              'candidate_configurations': len(configs), 'selections': selections}
    provenance = {'git_commit': subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
                  'source_and_input_sha256': hashes, 'cache_signature': signature,
                  'packages': {p: importlib.metadata.version(p) for p in ('numpy','pandas','scipy','nflreadpy','pyarrow')}}
    out = args.output_dir
    audit = {'fits_audited': len(timing), 'all_fits_strictly_prior_week': True,
             'normalization_reference_weeks': len(references), 'all_references_strictly_prior_week': True,
             'unique_evaluation_games': len(held), 'proper_score_games': sample['proper_score_games'],
             'primary_bets': sample['primary_bet_games'], 'candidate_configurations': len(configs)}
    held.to_csv(out/'heldout_predictions.csv', index=False)
    for name, data in [('results.json', result), ('selections.json', selections), ('provenance.json', provenance), ('nominated_candidate.json', nomination), ('audit_summary.json', audit)]:
        (out/name).write_text(json.dumps(data, indent=2, allow_nan=False)+'\n')
    write_report(result, out)
    print(json.dumps({'passing': passing, 'nomination': nomination, 'sample': sample}, indent=2), flush=True)


if __name__ == '__main__':
    main()
