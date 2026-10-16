# Joint market and residual scoring distributions

Design fixed 2026-10-16 before this experiment's forecasts were generated.
This is exposed historical development, not a prospective preregistration.
Base repository: e93b936b9de03bab8e97a6b7ae71fb6d3a224fa7.

## Data and timing

Use only committed `research/form_windows_inputs/schedule.csv` joined one-to-one
to `research/residual_trends_inputs/schedule_totals.csv`. Regular season only.
Keep completed games with both scores, total and spread; moneyline availability
does not restrict distribution training. NFLverse spread is positive for a home
favorite. Derived team locations are (total + spread)/2 and (total - spread)/2.
These locations are not assumed to equal expected scores or traded team totals.
Freeze a compact input copy and source hashes. Do not fetch revised outcomes.

All features, feature scales, means, covariance models and empirical neighbors
for a forecast use only strictly earlier season/weeks. Update histories after
the entire week. No within-week feedback. Fit weekly over at most six seasons,
including the current one, with half-life two seasons for training observations.
Generate prequential mean errors from 2015 onward; report the main comparison
on 2023-25 (816 scheduled completed regular-season games), earlier 2017-22 as
supplemental development context, and 2026 W1-5 as a separate diagnostic.

## Fixed information sets

A: current spread and total. Mean residual regressors are spread/10,
(total-45)/10, their product, squared spread/10 and squared centered total/10.
B: A plus four team histories: home scored, home allowed, away scored, away
allowed residual EWMAs. A scored residual is score minus derived team location;
an allowed residual is opponent score minus opponent location. This is an
invertible representation of each team's total-residual and scoring-residual
histories, so the redundant total-residual features are exported but not refit.
C_abs: exactly B's mean, with lagged absolute residual histories added to the
covariance regression. C_sq: B's mean with squared residual histories instead.
EWMA span=4, alpha=.4, recursion starts at zero, older games are retained,
and all histories receive .5 offseason retention. No half-life/span selection.

Mean corrections: pooled weekly multi-output ridge of home/away market-relative
score residuals, target/10, weighted training-only standardization, unpenalized
intercept, fixed normalized L2=.1. No team fixed effects or box scores.
Covariance: ridge .1 of previous prequential mean-error cross-products/100 on
current market regressors, plus the designated absolute/squared histories for C.
Use prior in-sample errors only if fewer than 100 prequential errors exist;
this warm-up ends before the reported 2017-26 samples. Variances clipped to
[16,400] points squared and correlation to [-.6,.6] to ensure stable PSD fits.
All clipping events and support/fit cutoffs are exported.

## Two coherent distribution families, eight variants

Smooth: bivariate Gaussian weights evaluated at score-cell centers on integer
home and away support 0..80, then normalized. This is a discrete Gaussian
lattice approximation, not exact bivariate rectangle integration. The score
support implies consistent total/MOV support and parity and nonnegative scores;
rare football-impossible score pairs are not specifically removed.
Empirical: .85 smooth + .15 kernel-weighted histogram of prior actual score
pairs, with half a pseudo-game of smooth smoothing. Same support. Neighbor
Gaussian bandwidths are 6 spread points, 7 total points; B/C use designated
residual coordinates standardized on training games with bandwidth 1.5 SD.
C's empirical neighborhoods add the same absolute/squared residual histories
used in their covariance fits. Time weights as above. This tests a fixed
empirical mixture, not every possible discrete scoring model.
All settings are fixed; no best-result tuning or ROI optimization.

## Outputs and decisions

For every scored game and arm save home/away win and tie probabilities,
conditional non-tie win probability, score means, quantiles, and all home,
away, total and MOV marginal PMFs. Save cover/lose/push and over/under/push at
that game's market thresholds. Export several illustrative complete joint PMFs.
Evaluate exact joint-score NLL (primary), exact marginal NLLs, discrete CRPS,
50/80/90% interval coverage and width, binary winner and non-push cover/total
log loss/Brier, and calibration. Compare win probabilities to proportional
no-vig two-sided moneylines on identical non-tie rows. No actual team-total
price evaluation is possible from these inputs.

Report flat 1u moneyline units/ROI +/- SE at the model's favored side, a
market-favorite baseline, an always-underdog control and the market-correct
negative-hold null. Ties push. Market pick'ems and missing or invalid prices
are excluded identically across arms. Never use ROI to tune or select.

Six primary contrasts: each of B/C_abs/C_sq minus A within each shape family.
Use positive gain = baseline loss minus candidate loss. Paired season-stratified
whole-week block bootstrap, seed 20261016, 10,000 draws; nominal 95% and
Bonferroni 99.1667% intervals (six contrasts) for primary joint NLL. Other
metrics and C-vs-B contrasts have descriptive 95% intervals. Annual results
and all fixed arms must be shown; best historical rank is not qualification.
Intervals condition on these designs and do not cover prior research selection.

Historical lines have no independent quote timestamps. This is not a live
executable-price test. Scores include overtime. A smooth lattice can overstate
tie probability or miss football score concentrations; empirical mixtures may
overfit sparse cells. Support 0..80 is truncated, although every input outcome
is interior. No production recipe, ledger, data/ or site changes are authorized
by this experiment. A future test requires separate timestamped capture.
