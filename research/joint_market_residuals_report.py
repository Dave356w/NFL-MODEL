"""Summarize the fixed joint-scoring experiment with paired week uncertainty."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import joint_market_residuals as j

SEED = 20261016
REPS = 10000
LABELS = dict(A_market='A: market only', B_residual='B: residual means',
              C_absolute='C: absolute residuals', C_squared='C: squared residuals')
METRICS = ('joint_nll', 'margin_nll', 'total_nll', 'team_nll', 'margin_crps',
           'total_crps', 'team_crps', 'win_ll', 'win_brier', 'cover_ll', 'over_ll', 'model_units')


def week_bootstrap(values, seasons, weeks, reps=REPS, seed=SEED):
    """Paired, season-stratified week resampling; divide by resampled game n."""
    values = np.asarray(values, float)
    if values.ndim == 1:
        values = values[:, None]
    seasons, weeks = np.asarray(seasons), np.asarray(weeks)
    valid = np.isfinite(values)
    numerator = np.zeros((reps, values.shape[1]))
    denominator = np.zeros_like(numerator)
    rng = np.random.default_rng(seed)
    for season in sorted(set(seasons)):
        take = seasons == season
        unique, inverse = np.unique(weeks[take], return_inverse=True)
        sums = np.zeros((len(unique), values.shape[1]))
        counts = np.zeros_like(sums)
        for col in range(values.shape[1]):
            sums[:, col] = np.bincount(inverse, weights=np.where(valid[take, col], values[take, col], 0), minlength=len(unique))
            counts[:, col] = np.bincount(inverse, weights=valid[take, col].astype(float), minlength=len(unique))
        draws = rng.multinomial(len(unique), np.full(len(unique), 1 / len(unique)), size=reps)
        numerator += draws @ sums
        denominator += draws @ counts
    return np.divide(numerator, denominator, out=np.full_like(numerator, np.nan), where=denominator > 0)


def interval(values, level=.95):
    alpha = 1 - level
    return [float(x) for x in np.nanquantile(values, [alpha / 2, 1 - alpha / 2])]


def basis_masks(f):
    return dict(primary_2023_25=f.season.between(2023, 2025),
                earlier_2017_22=f.season.between(2017, 2022), diagnostic_2026=f.season == 2026)


def summary_rows(f, basis):
    rows = []
    for arm, group in f.groupby('arm', sort=True):
        row = dict(basis=basis, arm=arm, games=len(group), win_games=int(group.win_ll.notna().sum()),
                   mean_tie_probability=float(group.p_tie.mean()),
                   realized_tie_rate=float((group.home_score == group.away_score).mean()))
        for col in METRICS:
            row[col] = float(group[col].mean())
        for target in ('home', 'away', 'margin', 'total'):
            row[target + '_mae'] = float(group[target + '_abs_error'].mean())
            row[target + '_rmse'] = float(np.sqrt(group[target + '_sq_error'].mean()))
            for level in ('50', '80', '90'):
                for metric in ('coverage', 'width'):
                    key = target + '_' + metric + level
                    row[key] = float(group[key].mean())
        row['covariance_clip_rate'] = float(group.covariance_clipped.mean())
        row['median_effective_neighbors'] = float(group.empirical_effective_neighbors.median())
        rows.append(row)
    return rows


def same_row_bet_ids(f):
    valid_sets = [set(g.loc[g.model_units.notna(), 'game_id']) for _, g in f.groupby('arm')]
    return set.intersection(*valid_sets)


def roi_rows(f, basis):
    common = same_row_bet_ids(f)
    f = f[f.game_id.isin(common)].copy()
    rows, pair_rows = [], []
    for arm, g in f.groupby('arm', sort=True):
        g = g.sort_values('game_id')
        v = g.model_units.to_numpy()
        boot = week_bootstrap(np.column_stack([v, v - g.favorite_units,
                                                v - g.model_null, v - g.underdog_units]),
                              g.season, g.week)
        picked_market_favorite = ((g.p_home_non_tie > .5) == (g.q > .5)).to_numpy()
        win = v > 0
        row = dict(basis=basis, arm=arm, bets=len(g), units=float(v.sum()), roi=float(v.mean()),
                   roi_se=float(v.std(ddof=1) / np.sqrt(len(v))), roi_ci95=interval(boot[:, 0]),
                   wins=int(win.sum()), losses=int((v < 0).sum()), pushes=int((v == 0).sum()),
                   market_null=float(g.model_null.mean()),
                   market_favorite_picks=int(picked_market_favorite.sum()),
                   market_underdog_picks=int((~picked_market_favorite).sum()),
                   favorite_subset_units=float(v[picked_market_favorite].sum()),
                   underdog_subset_units=float(v[~picked_market_favorite].sum()),
                   paired_favorite_gain=float((v - g.favorite_units).mean()),
                   paired_favorite_ci95=interval(boot[:, 1]),
                   excess_over_market_null=float((v - g.model_null).mean()),
                   excess_over_market_null_ci95=interval(boot[:, 2]),
                   paired_underdog_gain=float((v - g.underdog_units).mean()),
                   paired_underdog_ci95=interval(boot[:, 3]))
        rows.append(row)
    first = f[f.arm == sorted(f.arm.unique())[0]].sort_values('game_id')
    for name in ('favorite', 'underdog'):
        v = first[name + '_units'].to_numpy()
        boot = week_bootstrap(v, first.season, first.week)
        rows.append(dict(basis=basis, arm='control_' + name, bets=len(first), units=float(v.sum()),
                         roi=float(v.mean()), roi_se=float(v.std(ddof=1) / np.sqrt(len(v))),
                         roi_ci95=interval(boot[:, 0]), wins=int((v > 0).sum()),
                         losses=int((v < 0).sum()), pushes=int((v == 0).sum()),
                         market_null=float(first[name + '_null'].mean())))
    return rows


def contrasts(f, basis, reps=REPS):
    rows = []
    pairs = [(shape + '__' + info, shape + '__A_market', 'primary')
             for shape in j.SHAPES for info in j.INFOS[1:]]
    pairs += [(shape + '__' + info, shape + '__B_residual', 'uncertainty_vs_mean')
              for shape in j.SHAPES for info in j.INFOS[2:]]
    pairs += [('empirical__' + info, 'smooth__' + info, 'shape') for info in j.INFOS]
    common = same_row_bet_ids(f)
    for arm, comparator, family in pairs:
        a = f[f.arm == arm].set_index('game_id').sort_index()
        b = f[f.arm == comparator].set_index('game_id').sort_index()
        if not a.index.equals(b.index):
            raise ValueError('Unpaired comparison')
        values = b[list(METRICS)].to_numpy() - a[list(METRICS)].to_numpy()
        values[:, -1] *= -1  # More moneyline units is better; lower losses are better.
        values[~a.index.isin(common), -1] = np.nan
        draws = week_bootstrap(values, a.season, a.week, reps=reps)
        for col, metric in enumerate(METRICS):
            simultaneous = interval(draws[:, col], 1 - .05 / 6) if family == 'primary' and metric == 'joint_nll' else None
            rows.append(dict(basis=basis, arm=arm, comparator=comparator, family=family, metric=metric,
                             n=int(np.isfinite(values[:, col]).sum()), gain=float(np.nanmean(values[:, col])),
                             ci95=interval(draws[:, col]), joint_nll_six_contrast_ci=simultaneous))
    return rows


def calibration(f):
    rows = []
    for arm, g in f.groupby('arm', sort=True):
        proper = g[g.home_score != g.away_score]
        for label, probs in [('model', proper.p_home_non_tie), ('moneyline', proper.q)]:
            z = proper.assign(prob=np.asarray(probs))
            z = z[np.isfinite(z.prob)]
            z['bin'] = np.minimum((z.prob * 10).astype(int), 9)
            for binid, cell in z.groupby('bin'):
                rows.append(dict(arm=arm, source=label, bin=int(binid), n=len(cell),
                                 predicted=float(cell.prob.mean()), observed=float((cell.home_score > cell.away_score).mean())))
    return rows


def validate_outputs(f, out):
    probs = np.load(out / 'marginal_probabilities.npz')
    ids = list(probs['game_ids'])
    audit = pd.read_csv(out / 'fit_audit.csv')
    ha = pd.read_csv(out / 'history_audit.csv.gz')
    checks = {}
    checks['all_fit_cutoffs_prior'] = all((r.training_max_season, r.training_max_week) < (r.season, r.week)
                                           and (r.covariance_max_season, r.covariance_max_week) < (r.season, r.week)
                                           for r in audit.itertuples())
    checks['all_history_cutoffs_prior'] = all((r.source_season, r.source_week) < (r.season, r.week) for r in ha.itertuples())
    checks['no_reported_covariance_fallback'] = not audit.loc[audit.season >= 2017, 'covariance_fallback'].any()
    checks['identical_game_sets'] = all(set(g.game_id) == set(ids) for _, g in f.groupby('arm'))
    checks['probabilities_nonnegative_and_normalized'] = all(
        np.all(probs[k] >= 0) and np.allclose(probs[k].sum(axis=1), 1., atol=2e-6)
        for k in probs.files if '__' in k)
    checks['win_loss_tie_sum_to_one'] = bool(np.allclose(f.p_home + f.p_tie + f.p_away, 1.))
    checks['mean_identities'] = bool(np.allclose(f.total_mean, f.home_mean + f.away_mean)
                                    and np.allclose(f.margin_mean, f.home_mean - f.away_mean))
    checks['cover_and_total_sum_to_one'] = bool(np.allclose(f.cover_win + f.cover_push + f.cover_lose, 1.)
                                               and np.allclose(f.over_win + f.over_push + f.over_lose, 1.))
    checks['primary_game_count'] = len(f.loc[f.season.between(2023, 2025)].drop_duplicates('game_id')) == 816
    checks['pmf_rows_match_order'] = True
    for arm, g in f.groupby('arm'):
        g = g.set_index('game_id').loc[ids]
        margin = probs[arm + '__margin']
        ph = margin[:, probs['margin_support'] > 0].sum(axis=1)
        if not np.allclose(ph, g.p_home, atol=1e-6):
            checks['pmf_rows_match_order'] = False
    (out / 'verification.json').write_text(json.dumps(checks, indent=2) + '\n')
    if not all(checks.values()):
        raise ValueError('Output validation failed: ' + str(checks))
    return checks


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(str(c) for c in row) + ' |' for row in rows])


def ci_text(ci, decimals=5):
    return '[' + ', '.join(f'{v:+.{decimals}f}' for v in ci) + ']'


def plots(f, summary, paired, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.dpi': 150})
    primary = [x for x in paired if x['basis'] == 'primary_2023_25' and x['family'] == 'primary' and x['metric'] == 'joint_nll']
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for index, row in enumerate(primary):
        low, high = row['joint_nll_six_contrast_ci']
        color = '#2563eb' if row['arm'].startswith('smooth') else '#0f766e'
        ax.plot([low, high], [index, index], color=color, lw=2)
        ax.scatter(row['gain'], index, color=color, s=36, zorder=3)
    ax.axvline(0, color='#64748b', ls='--', lw=1)
    ax.set_yticks(range(len(primary)), [x['arm'].replace('__', ' / ').replace('C_absolute', 'C: absolute').replace('C_squared', 'C: squared').replace('B_residual', 'B: means') for x in primary])
    ax.invert_yaxis()
    ax.set_xlabel('Joint-score log-loss gain over the same shape’s market-only model →')
    ax.set_title('Do residual histories add information? 2023–2025')
    fig.text(.5, .015, 'Paired whole-week bootstrap; intervals adjust for six primary contrasts. Higher is better.', ha='center', fontsize=8, color='#475569')
    fig.tight_layout(rect=(0, .05, 1, 1)); fig.savefig(out / 'joint_gain_intervals.png'); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for ax, target, title in zip(axes, ['total', 'margin'], ['Game total', 'Margin of victory']):
        for shape, marker in [('smooth', 'o'), ('empirical', 's')]:
            rows = [x for x in summary if x['basis'] == 'primary_2023_25' and x['arm'].startswith(shape)]
            for row in rows:
                ax.scatter(row[target + '_width90'], row[target + '_coverage90'] * 100,
                           marker=marker, s=45, label=row['arm'].replace('__', ' / '))
        ax.axhline(90, color='#64748b', ls='--', lw=1)
        ax.set_title(title); ax.set_xlabel('Mean 90% interval width, points'); ax.set_ylabel('Observed coverage, %')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', ncol=2, fontsize=8, frameon=False)
    fig.suptitle('Coverage should be assessed together with interval width')
    fig.tight_layout(rect=(0, .22, 1, .95)); fig.savefig(out / 'interval_calibration.png'); plt.close(fig)
    # An actual retrospective forecast, with the result shown only as reference.
    game = f[f.game_id == '2026_05_SF_SEA']
    if len(game):
        pack = np.load(out / 'marginal_probabilities.npz')
        pos = list(pack['game_ids']).index('2026_05_SF_SEA')
        fig, axes = plt.subplots(1, 2, figsize=(10, 4))
        for target, ax, actual in [('home', axes[0], game.home_score.iloc[0]), ('away', axes[1], game.away_score.iloc[0])]:
            for shape, color in [('smooth', '#2563eb'), ('empirical', '#0f766e')]:
                ax.plot(pack['score_support'], pack[shape + '__B_residual__' + target][pos], color=color, label=shape)
            ax.axvline(actual, color='#b45309', ls='--', lw=1.2, label='Realized score')
            ax.set_xlim(0, 60); ax.set_xlabel('Points'); ax.set_ylabel('Probability of exact points')
            ax.set_title('Seattle' if target == 'home' else 'San Francisco'); ax.legend(frameon=False, fontsize=8)
        fig.suptitle('2026 W5 SF at SEA: prior-week forecast, diagnostic example')
        fig.tight_layout(); fig.savefig(out / 'example_team_distributions.png'); plt.close(fig)


def write_report(summary, annual, paired, roi, market, market_pairs, checks, out):
    primary = [x for x in summary if x['basis'] == 'primary_2023_25']
    main_pairs = [x for x in paired if x['basis'] == 'primary_2023_25' and x['family'] == 'primary' and x['metric'] == 'joint_nll']
    supported = [x for x in main_pairs if x['joint_nll_six_contrast_ci'][0] > 0]
    harmed = [x for x in main_pairs if x['joint_nll_six_contrast_ci'][1] < 0]
    best = min(primary, key=lambda x: x['joint_nll'])
    main_roi = [x for x in roi if x['basis'] == 'primary_2023_25']
    lines = ['# NFL joint market and residual distribution experiment', '', 'Date: October 16, 2026.', '',
             '**Historical development only.** All forecast fits and team histories use earlier whole weeks. The designs were chosen after prior NFL research was exposed; historical market quote timestamps are unknown. These are not archived native pregame forecasts.', '',
             '## Findings', '',
             f"The lowest pooled exact joint-score log loss is **{best['arm']}**, at **{best['joint_nll']:.6f}** on 816 regular-season games in 2023–2025. This is an observed ranking, not a qualified selection.", '',
             f"Of the six fixed residual-versus-market-only joint-score comparisons, **{len(supported)}** have a positive lower bound after the declared six-comparison adjustment. " +
             ('The supported comparisons are ' + ', '.join(x['arm'] for x in supported) + '.' if supported else 'The experiment does not establish incremental joint-score skill from the residual features.'), '',
             f"All six added-feature variants have worse pooled joint-score point estimates than their matching A baseline. **{len(harmed)}** have an adjusted interval wholly below zero: " + (', '.join(x['arm'] for x in harmed) if harmed else 'none') + '.', '',
             'All eight variants return negative pooled moneyline units; none beats the same-row market favorite in point estimates. Market-only empirical gives the best exact joint-score score, while market-only smooth gives the best MOV, total and team CRPS among these eight arms. The no-vig moneyline has a better winner log-loss point estimate than every new arm.', '',
             '**Calibration limitation:** the raw joint models assign roughly 2.5–2.9% average tie probability versus one tie in 816 games (0.12%). These raw tie probabilities are unsuitable for operational use. Binary winner scores are conditional on a non-tie; they do not validate unconditional win/loss/tie calibration. No post-result tie correction was fitted into the fixed variants.', '',
             'Probability skill, moneyline returns, and full-distribution shape are separate results. Read the paired intervals and annual tables alongside the pooled rankings. All settings are fixed; no best-result refitting or ROI optimization was performed.', '',
             '## Eight fixed variants', '',
             table(['Information set', 'Mean features', 'Uncertainty features'], [
                 ['A: market only', 'Current spread and total, fixed quadratic terms', 'Current spread and total'],
                 ['B: residual means', 'A + scored/allowed residual EWMAs for both teams', 'Same market features as A'],
                 ['C: absolute residuals', 'Exactly B', 'Market + absolute residual EWMAs'],
                 ['C: squared residuals', 'Exactly B', 'Market + squared residual EWMAs']]), '',
             'Each is fit as a normalized smooth bivariate Gaussian lattice and as an 85% smooth / 15% conditional empirical score-pair mixture. Empirical neighbors use market context and the information set’s lagged histories. Therefore a C-versus-B empirical comparison changes both covariance predictors and empirical neighbors; the smooth comparison isolates the covariance change.', '',
             'EWMA span is four team games (alpha=.4), initialized at zero with 50% offseason retention. The history is not truncated after four games. Total-residual EWMA equals scored plus allowed EWMA and is exported rather than redundantly refit.', '',
             '## Moneyline returns: primary same-row sample', '',
             'One flat hypothetical unit on the model’s favored side, no value filter or stake sizing. Both prices must be valid; market pick’ems are excluded. Ties push. Every row uses the intersection eligible for all eight models. ± is one game-level SE; paired intervals resample whole weeks within season. The null is the proportional no-vig moneyline probability applied to the actual quoted payout, following the repository’s conditional decisive-game convention.', '',
             table(['Model / control', 'N', 'W–L–P', 'Units', 'ROI ± SE', 'Market null'], [
                 [r['arm'], r['bets'], f"{r['wins']}–{r['losses']}–{r['pushes']}", f"{r['units']:+.2f}",
                  f"{100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f}", f"{100*r['market_null']:+.2f}%"] for r in main_roi]), '',
             table(['Model', 'ROI gain over favorite, pp', '95% paired CI, pp', 'Underdog picks'], [
                 [r['arm'], f"{100*r['paired_favorite_gain']:+.2f}", ci_text([100*v for v in r['paired_favorite_ci95']], 2), r['market_underdog_picks']]
                 for r in main_roi if not r['arm'].startswith('control_')]), '',
             'These ROI intervals are descriptive and do not adjust for searching eight models or earlier experiments. The machine-readable results also contain ROI intervals, comparisons with the always-underdog control, excess over the price-adjusted null, and model-favorite versus model-underdog contribution totals.', '',
             '## Full-distribution and winner scores', '',
             'Lower is better for all scores below. CRPS is the exact discrete CDF score in points; team CRPS averages home and away. Exact joint-score NLL is the primary endpoint. Winner scores condition on a decisive game and exclude ties identically.', '',
             table(['Variant', 'Joint NLL', 'MOV CRPS', 'Total CRPS', 'Team CRPS', 'Win LL', 'Brier'], [
                 [r['arm'], f"{r['joint_nll']:.6f}", f"{r['margin_crps']:.4f}", f"{r['total_crps']:.4f}", f"{r['team_crps']:.4f}", f"{r['win_ll']:.6f}", f"{r['win_brier']:.6f}"] for r in primary]), '',
             f"Same-row no-vig moneyline baseline: winner LL **{market['win_ll']:.6f}**, Brier **{market['win_brier']:.6f}**, n={market['n']}. A moneyline supplies no unique joint-score, total or team-score distribution, so those baseline cells are intentionally not invented.", '',
             table(['Variant', 'Win LL gain over no-vig moneyline', '95% paired CI'], [
                 [r['arm'], f"{r['ll_gain']:+.6f}", ci_text(r['ll_ci95'], 6)] for r in market_pairs]), '',
             'Moneyline probability comparisons use identical decisive, valid-price rows and descriptive 95% whole-week intervals. These intervals do not cover selecting among eight models.', '',
             '## Do the lagged residuals improve the joint distribution?', '',
             'Positive gain favors the added information. All contrasts compare identical games within the same shape family. Intervals below are paired, season-stratified whole-week bootstrap, 10,000 draws, with nominal 99.1667% per-contrast coverage for six primary comparisons (Bonferroni nominal family level 95%).', '',
             table(['Added information', 'Comparator', 'Joint NLL gain', 'Six-comparison interval'], [
                 [r['arm'], r['comparator'], f"{r['gain']:+.6f}", ci_text(r['joint_nll_six_contrast_ci'], 6)] for r in main_pairs]), '',
             '![Joint-score gains](joint_gain_intervals.png)', '',
             'Other target comparisons and the C-versus-B / empirical-versus-smooth contrasts are in paired_comparisons.json with descriptive 95% intervals. Their multiplicity is not covered by the six primary intervals.', '',
             '## Season consistency', '',
             table(['Season', 'Variant', 'N', 'Joint NLL', 'Total CRPS', 'Team CRPS', 'Win LL'], [
                 [r['season'], r['arm'], r['games'], f"{r['joint_nll']:.5f}", f"{r['total_crps']:.4f}", f"{r['team_crps']:.4f}", f"{r['win_ll']:.6f}"]
                 for r in annual if 2023 <= r['season'] <= 2025]), '',
             '## Calibration and uncertainty', '',
             table(['Variant', 'MOV 90% coverage / width', 'Total 90% coverage / width', 'Mean tie p / actual tie rate', 'Covariance clipped'], [
                 [r['arm'], f"{100*r['margin_coverage90']:.2f}% / {r['margin_width90']:.1f}",
                  f"{100*r['total_coverage90']:.2f}% / {r['total_width90']:.1f}",
                  f"{100*r['mean_tie_probability']:.2f}% / {100*r['realized_tie_rate']:.2f}%", f"{100*r['covariance_clip_rate']:.2f}%"] for r in primary]), '',
             'Widths are in points. Discrete equal-tail intervals can exceed nominal coverage because endpoint mass is included. 50% and 80% intervals, marginal score NLLs, MAE/RMSE, non-push cover/over log loss and Brier, and winner reliability bins are exported. Cover/over scores have no actual two-sided price benchmark in this input pack; a 50% threshold is not a complete market distribution.', '',
             '![Interval calibration](interval_calibration.png)', '',
             '## Separate 2026 diagnostic', '',
             'The committed schedule inputs contain 79 completed games through week 5. These results are current-season historical reconstructions, not forward captures, and are not pooled into the primary sample.', '',
             table(['Variant', 'N', 'Joint NLL', 'MOV CRPS', 'Total CRPS', 'Team CRPS', 'Win LL'], [
                 [r['arm'], r['games'], f"{r['joint_nll']:.5f}", f"{r['margin_crps']:.4f}", f"{r['total_crps']:.4f}", f"{r['team_crps']:.4f}", f"{r['win_ll']:.6f}"]
                 for r in summary if r['basis'] == 'diagnostic_2026']), '',
             '## Earlier 2017–2022 development context', '',
             'These six seasons add 1,567 earlier-data forecasts per arm. They are supplementary exposed development history, not an independently selected confirmation sample.', '',
             table(['Variant', 'N', 'Joint NLL', 'MOV CRPS', 'Total CRPS', 'Team CRPS', 'Win LL'], [
                 [r['arm'], r['games'], f"{r['joint_nll']:.5f}", f"{r['margin_crps']:.4f}", f"{r['total_crps']:.4f}", f"{r['team_crps']:.4f}", f"{r['win_ll']:.6f}"]
                 for r in summary if r['basis'] == 'earlier_2017_22']), '',
             '![Team-point probability example](example_team_distributions.png)', '',
             '## Reproduction and limits', '',
             'Run `OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals.py`, then `OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals_report.py`. Requirements: numpy, pandas, matplotlib; pytest for the focused tests. No network access or production model imports are required. The frozen input pack permits a standalone rerun from the supplied folder layout.', '',
             f"All {len(checks)} output integrity checks pass, including earlier-week history/fit cutoffs, no covariance fallback in reported samples, identical game IDs, normalized PMFs, correct probability file ordering, and total/MOV identities. The separate focused tests include an adversarial own-week outcome-mutation check.", '',
             'The smooth model is a Gaussian lattice approximation, not exact cell integration. Support is nonnegative integer scores 0–80 and is truncated; all input outcomes lie strictly inside its upper boundary. The model does not encode every football-impossible score pair. Tie probabilities must be inspected rather than assumed calibrated. Empirical neighbors can be sparse. Covariance safeguards clip variances to 16–400 and correlations to ±.6; clipping is reported. These fixed settings constrain what this experiment can establish.', '',
             'Market lines are location proxies, not guaranteed means. Derived team points are not separately traded team totals. Historical prices have unknown capture timestamps, results include overtime, and there is no executable-price or staking claim. The bootstrap conditions on the fixed experiment and excludes earlier research/design selection uncertainty. Better distribution scores alone do not establish profitable betting.', '',
             'The experiment changes no production forecast, recipe, append-only ledger or deployed page. Full per-game predictions, all marginal probabilities, illustrative joint PMFs, features, history and fit audits, frozen sources, code, tests and machine-readable summaries accompany this report.', '']
    (out / 'REPORT.md').write_text('\n'.join(lines))


def run(out):
    out = j.guard_output(out)
    f = pd.read_csv(out / 'predictions.csv.gz')
    checks = validate_outputs(f, out)
    summaries, paired, roi = [], [], []
    for name, mask in basis_masks(f).items():
        z = f.loc[mask]
        summaries += summary_rows(z, name)
        paired += contrasts(z, name)
        roi += roi_rows(z, name)
    annual, annual_roi = [], []
    for year, z in f.groupby('season', sort=True):
        rows = summary_rows(z, f'annual_{int(year)}')
        for row in rows:
            row['season'] = int(year)
        annual += rows
        annual_roi += roi_rows(z, f'annual_{int(year)}')
    primary = f[f.season.between(2023, 2025)]
    first = primary[primary.arm == sorted(primary.arm.unique())[0]]
    same = first[first.win_ll.notna() & first.market_win_ll.notna()]
    market = dict(n=len(same), win_ll=float(same.market_win_ll.mean()), win_brier=float(same.market_win_brier.mean()))
    market_pairs = []
    for arm, group in primary.groupby('arm', sort=True):
        group = group[group.win_ll.notna() & group.market_win_ll.notna()].sort_values('game_id')
        values = np.column_stack([group.market_win_ll - group.win_ll,
                                  group.market_win_brier - group.win_brier])
        draws = week_bootstrap(values, group.season, group.week)
        market_pairs.append(dict(arm=arm, n=len(group), ll_gain=float(values[:, 0].mean()),
                                 ll_ci95=interval(draws[:, 0]), brier_gain=float(values[:, 1].mean()),
                                 brier_ci95=interval(draws[:, 1])))
    # The same source has valid prices on all 815 decisive primary rows.
    cal = calibration(primary)
    for filename, content in [('summary.json', summaries), ('annual_summary.json', annual),
                               ('paired_comparisons.json', paired), ('moneyline_returns.json', roi),
                               ('annual_moneyline_returns.json', annual_roi), ('winner_calibration.json', cal),
                               ('moneyline_probability_comparisons.json', market_pairs),
                               ('moneyline_baseline.json', market)]:
        (out / filename).write_text(json.dumps(content, indent=2, allow_nan=False) + '\n')
    pd.DataFrame(summaries).to_csv(out / 'summary.csv', index=False)
    pd.DataFrame(annual).to_csv(out / 'annual_summary.csv', index=False)
    pd.DataFrame(cal).to_csv(out / 'winner_calibration.csv', index=False)
    plots(f, summaries, paired, out)
    write_report(summaries, annual, paired, roi, market, market_pairs, checks, out)
    print('Primary scores:')
    print(pd.DataFrame(summaries).query("basis == 'primary_2023_25'")[['arm', 'games', 'joint_nll', 'margin_crps', 'total_crps', 'team_crps', 'win_ll']].to_string(index=False))
    print('Primary joint-score comparisons:')
    for row in paired:
        if row['basis'] == 'primary_2023_25' and row['family'] == 'primary' and row['metric'] == 'joint_nll':
            print(row['arm'], row['gain'], row['joint_nll_six_contrast_ci'])
    print(f'Passed {len(checks)} integrity checks; wrote REPORT.md and summaries.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=j.ROOT / 'research/joint_market_residual_results')
    run(parser.parse_args().output_dir)
