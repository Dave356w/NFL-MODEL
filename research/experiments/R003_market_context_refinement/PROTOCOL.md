# R003-MC2: exploratory direct empirical localization refinement

Frozen locally before MC2 scoring, after MC1 results were inspected. All history
is exposed. MC1's failed advancement decision remains intact; this is a new
exploratory iteration, not an independent retest or a repaired MC1 result.

MC1's direct global-backoff models underperformed R003 while translated models
performed better. This tests whether removing strong unconditional backoff
improves the user's original direct observed-outcome approach. No translated
outcome is a candidate. No new label, feature, Gaussian or possible-score mask.

Use MC1's frozen input, prior-week six-season window, two-season time decay,
score/settlement definitions, primary CRPS, annual selection and reporting.
Ten fixed candidates: direct kernels (spread,total) bandwidths (1,2), (2,3),
(4,6), each with pseudo-games 0 or 5; nearest 100 and 250 games, each with
pseudo-games 0 or 5. Kernel weights are stable exponentials, nearest ties use
game ID order. Pseudo-games 0 means entirely context-qualified weights; 5 adds
only a weak global empirical backoff. All raw score pairs remain observations.
No wider/narrower setting is added after evaluating this batch.

Select all-family and within-family settings each target season using only
strictly earlier OOF seasons beginning 2015, min two seasons. Select by mean
0.5*(margin CRPS+total CRPS), never ROI. Primary development comparison is the
annually selected direct policy versus unchanged R003 on identical 2023–25
games. Report MC1's earlier results separately rather than replacing them.
2017–22 is separate development context; 2026 is diagnostic.

10,000 season-stratified paired week resamples, seed 20261016; descriptive 95%
and 99.5% ten-arm sensitivity intervals, not full cross-iteration adjustment.
No independent confirmation claim. Keep MC1 forecasting gates: mean primary
gain >=.02, lower 95% bound >0, positive gain each main season, better than
global direct history, and no winner/cover/total LL degradation >.002 versus
R003, plus integrity. Exact wrong endpoint losses remain infinite, never floored
or omitted. Such errors fail the affected event-score gate; publish them even
if primary CRPS is favorable. No net profitability claim from forecast gates.

Freeze and retain this hash before scoring. Test prior-week sources, prior-year
selection, source-only atoms, probability normalization, CRPS, uncertainty, and
settlement. Independently repeat numerical outputs. Preserve MC1/RF1/original
experiments, user changes and production data. No production, deployment, live
capture, real spread-price or wagering activity.
