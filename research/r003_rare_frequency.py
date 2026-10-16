"""R003-RF1: a separately versioned, prior-week rare-score frequency correction.

Run from the checkout: python research/r003_rare_frequency.py
No network, production imports, original experiment writes, or ROI selection.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq

import distribution_ablations as d
import joint_market_residuals as j
import joint_market_residuals_report as report
import tie_hurdle as t
import tie_hurdle_report as summaries

OUT = j.ROOT / 'research/experiments/R003_rare_frequency'
BASELINE = 'empirical__R003_score_support'
ARM = 'empirical__R003_rare_frequency'
RARE = (1, 2, 4, 5)
RIDGE, MAX_THETA, MIN_GAMES = .01, 8., 256


def rare_counts(cap):
    scores = np.isin(np.arange(cap + 1), RARE).astype(int)
    return scores[:, None] + scores[None, :]


def sufficient(joint):
    p = d.check_joint(joint)
    return np.bincount(rare_counts(len(p) - 1).ravel(), weights=p.ravel(), minlength=3)


def transform(joint, theta):
    p = d.check_joint(joint)
    if isinstance(theta, bool) or not np.isfinite(theta) or not 0 <= theta <= MAX_THETA:
        raise ValueError('theta must be finite and within the registered bounds')
    q = p * np.exp(-float(theta) * rare_counts(len(p) - 1))
    q /= q.sum()
    d.check_joint(q)
    return q


def objective(theta, masses, observed, weights):
    """Loss difference from R003; derivative is observed minus tilted rare count."""
    k = np.arange(3)
    tilted = masses * np.exp(-theta * k)
    z = tilted.sum(axis=1)
    loss = weights @ (theta * observed + np.log(z)) + .5 * RIDGE * theta**2
    gradient = weights @ (observed - (tilted @ k) / z) + RIDGE * theta
    return float(loss), float(gradient)


def fit_penalty(archive, year, week):
    """Select earlier weeks before inspecting labels; never accept future training."""
    train = archive[j.before(archive, year, week) & (archive.season >= year - 5)].copy()
    audit = dict(season=int(year), week=int(week), training_games=len(train),
                 ridge=RIDGE, max_theta=MAX_THETA, warmup=len(train) < MIN_GAMES)
    if train.empty:
        return 0., dict(audit, theta=0., boundary='warmup', training_max_season=None,
                       training_max_week=None)
    if train.game_id.duplicated().any():
        raise ValueError('Duplicate calibration game IDs')
    mass = train[['mass0', 'mass1', 'mass2']].to_numpy(float)
    obs = train.rare_count.to_numpy(float)
    if (not np.isfinite(mass).all() or (mass < 0).any()
            or not np.allclose(mass.sum(axis=1), 1, atol=1e-12, rtol=0)
            or not np.isin(obs, [0, 1, 2]).all()):
        raise ValueError('Invalid calibration sufficient statistics')
    weights = j.time_weights(train, year); weights /= weights.sum()
    last = train.sort_values(['season', 'week']).iloc[-1]
    if len(train) < MIN_GAMES:
        theta, boundary = 0., 'warmup'
    elif objective(0., mass, obs, weights)[1] >= 0:
        theta, boundary = 0., 'lower'
    elif objective(MAX_THETA, mass, obs, weights)[1] <= 0:
        theta, boundary = MAX_THETA, 'upper'
    else:
        theta = brentq(lambda x: objective(x, mass, obs, weights)[1], 0., MAX_THETA,
                       xtol=1e-12)
        boundary = 'interior'
    audit.update(theta=float(theta), boundary=boundary,
                 training_max_season=int(last.season), training_max_week=int(last.week),
                 effective_training_games=float(1 / (weights @ weights)),
                 observed_rare_team_count=float(weights @ obs),
                 baseline_rare_team_count=float(weights @ (mass @ np.arange(3))),
                 penalized_loss_change=objective(theta, mass, obs, weights)[0])
    return float(theta), audit


def reconstruct_week(complete, fits, year, week, test):
    train = complete[j.before(complete, year, week) & (complete.season >= year - 5)]
    if train.empty:
        raise ValueError('No earlier baseline training games')
    weight = j.time_weights(train, year)
    means = test[['implied_home', 'implied_away']].to_numpy() + 10 * j.ridge_predict(
        fits[year, week, 'mean'], test[list(j.BASE)])
    covs, _ = j.stable_covariance(100 * j.ridge_predict(
        fits[year, week, 'covariance'], test[list(j.BASE)]))
    for i, (_, row) in enumerate(test.iterrows()):
        raw, _ = j.empirical_joint(j.smooth_joint(means[i], covs[i]), train, row, weight, ())
        yield row, d.condition_support(raw, d.football_support())[0]


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def verify_exports(frame, audits, path):
    """Re-read persisted marginals and prove event probabilities and row alignment."""
    with np.load(path, allow_pickle=False) as pack:
        ids = pack['game_ids'].tolist()
        if len(set(ids)) != len(ids):
            raise AssertionError('Duplicate PMF IDs')
        for arm, g in frame.groupby('arm'):
            if set(g.game_id) != set(ids):
                raise AssertionError('PMF prediction populations differ')
            g = g.set_index('game_id').loc[ids]
            for target in ['home', 'away', 'margin', 'total']:
                p = pack[arm + '__' + target]
                if (p.shape[0] != len(ids) or not np.isfinite(p).all() or (p < 0).any()
                        or not np.allclose(p.sum(axis=1), 1, atol=2e-6, rtol=0)):
                    raise AssertionError('Invalid saved marginal')
            p = pack[arm + '__margin']; support = pack['margin_support']
            checks = [(p[:, support > 0].sum(axis=1), g.p_home),
                      (p[:, support == 0].sum(axis=1), g.p_tie),
                      ((p * (support[None, :] > g.spread_line.to_numpy()[:, None])).sum(axis=1), g.cover_win),
                      ((p * (support[None, :] == g.spread_line.to_numpy()[:, None])).sum(axis=1), g.cover_push)]
            for actual, expected in checks:
                if not np.allclose(actual, expected, atol=2e-6, rtol=0):
                    raise AssertionError('Saved marginal and event probabilities disagree')
    if any((r.training_max_season, r.training_max_week) >= (r.season, r.week)
           for r in audits.itertuples()):
        raise AssertionError('Saved calibration fit includes future data')
    return dict(pmf_normalization=True, event_probability_agreement=True,
                row_alignment=True, calibration_cutoffs=True)


def run(out=OUT):
    out = Path(out).resolve()
    root = (j.ROOT / 'research/experiments').resolve()
    if not out.is_relative_to(root) or out == root:
        raise ValueError('Output must be a separate research experiment directory')
    if out in [(root / x).resolve() for x in d.EXPERIMENTS.values()] + [d.BASE.resolve(), d.R001.resolve()]:
        raise ValueError('Original experiment outputs are protected')
    protocol = out / 'PROTOCOL.md'; registration = out / 'registration_record.json'
    registered = json.loads(registration.read_text())
    if j.sha256(protocol) != registered['protocol_sha256']:
        raise ValueError('Registered protocol hash changed')
    frozen = pd.read_csv(d.BASE / 'features.csv.gz')
    complete = frozen[np.isfinite(frozen[['home_score', 'away_score', 'spread_line', 'total_line']]).all(axis=1)]
    if complete.game_id.duplicated().any():
        raise ValueError('Duplicate input game IDs')
    if not (np.equal(complete.home_score, np.floor(complete.home_score)).all()
            and np.equal(complete.away_score, np.floor(complete.away_score)).all()
            and complete[['home_score', 'away_score']].ge(0).all().all()
            and complete[['home_score', 'away_score']].le(j.CAP).all().all()):
        raise ValueError('Invalid observed scores')
    fits = t.load_fit_index(d.BASE / 'coefficient_audit.jsonl')
    original_path = j.ROOT / 'research/experiments/R003_score_support/predictions.csv.gz'
    original = pd.read_csv(original_path).query('arm == @BASELINE').set_index('game_id')
    calibration, records, audits, ids = [], [], [], []
    payload = {arm + '__' + target: [] for arm in (BASELINE, ARM)
               for target in ('home', 'away', 'margin', 'total')}
    max_error = 0.; examples = {}; mask = d.football_support()
    integrity = dict(normalized_joint=True, identical_support=True, coherent_means=True,
                     positive_realized_probability=True, prior_week_calibration=True)
    for (year, week), test in complete[complete.season >= 2015].groupby(['season', 'week'], sort=True):
        theta, audit = (0., None)
        if year >= 2017:
            theta, audit = fit_penalty(pd.DataFrame(calibration), int(year), int(week))
            if audit['warmup'] or (audit['training_max_season'], audit['training_max_week']) >= (year, week):
                raise ValueError('Evaluation warm-up or calibration timing violation')
            audits.append(audit)
        updates = []
        for row, baseline in reconstruct_week(complete, fits, year, week, test):
            hs, aws = int(row.home_score), int(row.away_score)
            if not mask[hs, aws] or baseline[hs, aws] <= 0:
                raise ValueError('Unsupported observed score: ' + row.game_id)
            mass = sufficient(baseline)
            updates.append(dict(game_id=row.game_id, season=int(year), week=int(week),
                                mass0=mass[0], mass1=mass[1], mass2=mass[2],
                                rare_count=int(hs in RARE) + int(aws in RARE)))
            if year < 2017:
                continue
            ids.append(row.game_id)
            candidate = transform(baseline, theta)
            if not np.array_equal(baseline > 0, candidate > 0):
                raise AssertionError('Legal numerical support changed')
            if candidate[hs, aws] <= 0:
                raise ValueError('Zero realized candidate probability')
            metadata = {k: row[k] for k in ['game_id', 'season', 'week', 'gameday', 'home_team',
                       'away_team', 'home_score', 'away_score', 'spread_line', 'total_line',
                       'home_moneyline', 'away_moneyline', 'q']}
            for arm, p in [(BASELINE, baseline), (ARM, candidate)]:
                metrics, marginals = j.summarize_joint(p, row)
                if not np.isclose(metrics['total_mean'], metrics['home_mean'] + metrics['away_mean'], atol=1e-10):
                    raise AssertionError('Incoherent means')
                if arm == BASELINE:
                    old = original.loc[row.game_id]
                    err = max(abs(metrics[k] - old[k]) for k in
                              ['joint_nll', 'p_home', 'p_tie', 'margin_crps', 'total_crps'])
                    max_error = max(max_error, err)
                    if err > 1e-10:
                        raise AssertionError('R003 baseline reconstruction failed')
                records.append(dict(arm=arm, **metadata, **metrics, **t.extra_scores(p, row),
                                    theta=theta, rare_either_probability=float(p[rare_counts(j.CAP) > 0].sum())))
                for target, values in marginals.items():
                    payload[arm + '__' + target].append(values.astype(np.float32))
                if row.game_id == '2026_05_SF_SEA':
                    examples[row.game_id + '__' + arm] = p.astype(np.float32)
        calibration.extend(updates)  # Whole-week update, after every prediction in that week.
    f = j.add_binary_and_bet_scores(pd.DataFrame(records))
    if f.duplicated(['arm', 'game_id']).any() or any(len(g) != 816 for _, g in f[f.season.between(2023, 2025)].groupby('arm')):
        raise AssertionError('Forecast population mismatch')
    pd.DataFrame(calibration).to_csv(out / 'calibration_archive.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    pd.DataFrame(audits).to_csv(out / 'fit_audit.csv', index=False)
    io = d.write_predictions(f, out / 'predictions.csv.gz')
    np.savez_compressed(out / 'marginal_probabilities.npz', game_ids=np.array(ids),
                        score_support=j.SCORE_SUPPORT, margin_support=j.MOV_SUPPORT,
                        total_support=j.TOTAL_SUPPORT, **{k: np.asarray(v) for k, v in payload.items()})
    np.savez_compressed(out / 'example_joint_probabilities.npz', **examples)
    integrity.update(verify_exports(f, pd.DataFrame(audits), out / 'marginal_probabilities.npz'))
    inputs = [d.BASE / x for x in ['features.csv.gz', 'coefficient_audit.jsonl']] + [original_path]
    sources = [Path(__file__), j.ROOT / 'research/distribution_ablations.py',
               j.ROOT / 'research/joint_market_residuals.py', j.ROOT / 'research/tie_hurdle.py',
               j.ROOT / 'research/joint_market_residuals_report.py', j.ROOT / 'research/tie_hurdle_report.py']
    dump(out / 'provenance.json', dict(experiment='R003-RF1', registration=registered,
         source_hashes={str(p.relative_to(j.ROOT)): j.sha256(p) for p in sources},
         input_hashes={str(p.relative_to(j.ROOT)): j.sha256(p) for p in inputs},
         baseline_max_error=max_error, integrity=integrity, io=io,
         numpy=np.__version__, pandas=pd.__version__, historical_quote_timestamps='unknown',
         independent_validation=False, production_changed=False))
    write_report(f, pd.DataFrame(audits), out)
    print((out / 'REPORT.md').read_text())
    return f


def write_report(f, audits, out):
    metrics = summaries.LOSSES + summaries.INTERVALS
    groups = [('2023-25', f.season.between(2023, 2025)), ('2017-22', f.season.between(2017, 2022)),
              ('2026 diagnostic', f.season.eq(2026))]
    groups += [(str(y), f.season.eq(y)) for y in sorted(f.season.unique())]
    rows, contrasts, roi = [], [], []
    for basis, mask in groups:
        sub = f[mask]
        for arm, g in sub.groupby('arm'):
            rows.append(dict(basis=basis, arm=arm, games=len(g),
                             **{m: float(g[m].mean()) for m in metrics},
                             rare_either_probability=float(g.rare_either_probability.mean()),
                             tie_probability=float(g.p_tie.mean())))
        b = sub[sub.arm.eq(BASELINE)].set_index('game_id').sort_index()
        c = sub[sub.arm.eq(ARM)].set_index('game_id').sort_index()
        if not b.index.equals(c.index):
            raise AssertionError('Unpaired results')
        delta = b[metrics].to_numpy() - c[metrics].to_numpy()
        boot = report.week_bootstrap(delta, b.season, b.week)
        for i, m in enumerate(metrics):
            contrasts.append(dict(basis=basis, metric=m, n=int(np.isfinite(delta[:, i]).sum()),
                                  baseline=float(b[m].mean()), candidate=float(c[m].mean()),
                                  gain=float(np.nanmean(delta[:, i])), ci95=report.interval(boot[:, i]),
                                  ci995=report.interval(boot[:, i], .995)))
        if basis in ['2023-25', '2017-22', '2026 diagnostic']:
            roi.extend(report.roi_rows(sub, basis))
    pd.DataFrame(rows).to_csv(out / 'metrics.csv', index=False)
    dump(out / 'contrasts.json', contrasts); dump(out / 'moneyline.json', roi)
    dump(out / 'reliability.json', summaries.reliability(f[f.season.between(2023, 2025)]))
    pit = []
    for basis, mask in groups[:3]:
        for arm, g in f[mask].groupby('arm'):
            for target in ['home', 'away', 'margin', 'total']:
                pit.append(dict(basis=basis, arm=arm, target=target, counts=np.histogram(
                    g[target + '_pit_mid'], bins=np.linspace(0, 1, 11))[0].tolist()))
    dump(out / 'pit.json', pit)
    primary = next(x for x in contrasts if x['basis'] == '2023-25' and x['metric'] == 'joint_nll')
    changes = {x['metric']: x for x in contrasts if x['basis'] == '2023-25'}
    main = f[f.season.between(2023, 2025)]
    b = main[main.arm.eq(BASELINE)].set_index('game_id'); c = main[main.arm.eq(ARM)].set_index('game_id').loc[b.index]
    gains = b.joint_nll - c.joint_nll
    annual = gains.groupby(b.season).mean()
    weekly = pd.DataFrame(dict(s=b.season, w=b.week, gain=gains)).groupby(['s', 'w']).gain.agg(['sum', 'count'])
    dump(out / 'stability.json', dict(annual_gain={str(k): float(v) for k, v in annual.items()},
         leave_one_season_out={str(y): float(gains[b.season != y].mean()) for y in annual.index},
         leave_one_week_out_range=[float(x) for x in [((gains.sum() - weekly['sum']) / (len(gains) - weekly['count'])).min(),
                                                      ((gains.sum() - weekly['sum']) / (len(gains) - weekly['count'])).max()]],
         largest_absolute_contributions={k: float(gains.loc[k]) for k in gains.abs().nlargest(10).index}))
    gates = dict(practical_gain=primary['gain'] >= .005, positive_interval=primary['ci95'][0] > 0,
                 all_primary_seasons_positive=bool((annual > 0).all()),
                 secondary_scores=all(changes[m]['gain'] >= -.01 for m in
                     ['team_nll', 'margin_nll', 'total_nll', 'team_crps', 'margin_crps', 'total_crps']),
                 winner_scores=all(changes[m]['gain'] >= -.001 for m in ['win_ll', 'win_brier']),
                 integrity=True)
    decision = dict(experiment='R003-RF1', gates=gates,
                    recommendation='retain for research' if all(gates.values()) else 'fails advancement gate',
                    independent_validation=False, production_promotion=False)
    dump(out / 'decision.json', decision)
    score_lines = ['| Metric | Original R003 | RF1 | Gain | 95% interval |', '|---|---:|---:|---:|---|']
    for m in ['joint_nll', 'team_nll', 'margin_nll', 'total_nll', 'team_crps', 'margin_crps', 'total_crps',
              'win_ll', 'win_brier', 'cover_ll', 'cover_brier', 'over_ll', 'tie_ll']:
        x = changes[m]
        score_lines.append(f"| {m} | {x['baseline']:.6f} | {x['candidate']:.6f} | {x['gain']:+.6f} | [{x['ci95'][0]:+.6f}, {x['ci95'][1]:+.6f}] |")
    rlines = ['| Basis | Arm | Bets | W–L–P | Units | ROI ± SE | Favorite units | Null ROI |', '|---|---|---:|---|---:|---:|---:|---:|']
    for x in roi:
        if x['arm'].startswith('control_'):
            continue
        fav = next(z['units'] for z in roi if z['basis'] == x['basis'] and z['arm'] == 'control_favorite')
        rlines.append(f"| {x['basis']} | {x['arm']} | {x['bets']} | {x['wins']}–{x['losses']}–{x['pushes']} | {x['units']:+.3f} | {100*x['roi']:+.2f}% ± {100*x['roi_se']:.2f} pp | {fav:+.3f} | {100*x['market_null']:.2f}% |")
    text = f"""# R003-RF1 — rare-score frequency results

**Decision: {decision['recommendation']}.** Exposed historical development;
no independent validation, production promotion, live quote capture or wagering.
One prior-week fitted penalty on legal rare team scores {{1,2,4,5}}. Original
R003 and all original results are preserved; this is a separately versioned extension.

## Flat 1u moneyline results

{chr(10).join(rlines)}

These use identical eligible games per basis; ties push, market pick'ems are
excluded identically. ROI was not used to select or fit. Paired return intervals,
market-favorite and underdog controls are in moneyline.json. Historical prices
have unknown capture timestamps. Actual spread/total prices are unavailable,
so no historical ATS/total ROI is claimed.

## Predictive scores: 816 games, 2023–25

{chr(10).join(score_lines)}

Positive gain means R003 loss minus RF1 loss. Joint NLL is the single new primary
contrast: gain {primary['gain']:+.6f}; ten-contrast sensitivity 99.5% interval
{primary['ci995']}. Bootstrap: 10,000 paired whole-week draws within season,
seed 20261016, conditional on forecast paths without refitting. All periods were
already exposed, including the diagnostic that motivated this candidate; neither
interval accounts for the full adaptive research process. Secondary intervals
are descriptive and are not separate discovery claims.

Annual primary gains: {dict((int(k), round(float(v), 6)) for k, v in annual.items())}.
Complete annual and separate-period metrics, coverage/width, reliability, PIT,
influence and leave-one-week/season sensitivity accompany this report.

## Fit and integrity

One theta per week, normalized joint-NLL fit with ridge {RIDGE}, bounds [0,{MAX_THETA}],
current plus five prior seasons, two-season decay, min {MIN_GAMES} calibration games.
Calibration uses prior-week OOF distributions beginning 2015; whole-week updates
occur only after prediction. Evaluation begins 2017. No key-number, tie-hurdle,
OT correction, grid, or ROI filter was added. Rare legal scores retain positive
probability. All derived probabilities come from the same normalized joint PMF.

Theta range: {audits.theta.min():.6f}–{audits.theta.max():.6f}; upper-bound hits:
{int(audits.boundary.eq('upper').sum())}; lower-bound hits: {int(audits.boundary.eq('lower').sum())}.
Per-week cutoffs and sufficient statistics are saved. Provenance records baseline
reconstruction errors, source/input/protocol hashes, versions and serialization
integrity. Fixed decision gates: {gates}.

Reproduce: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/r003_rare_frequency.py`.
For an independent repeat, copy PROTOCOL.md and registration_record.json to a new
directory under research/experiments, then pass that path with --output-dir.
Generated marginal PMFs are ignored by Git; all archived R000–R003 outputs remain
unchanged. The original spread-EV CLI keeps its default original-R003 arm.
"""
    (out / 'REPORT.md').write_text(text)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, default=OUT)
    run(ap.parse_args().output_dir)
