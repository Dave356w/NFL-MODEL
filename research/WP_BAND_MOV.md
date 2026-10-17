# Model W% band -> average signed MOV test

Written locally 2026-10-17 UTC before this test's forecasts. Historical outcomes,
prior spread tests, and pooled 2021–25 band means have already been examined.
This is exposed development, not an untouched or externally registered test.
Production and original forecast ledgers remain unchanged.

## Fixed definitions

Train each target season on strictly earlier seasons in the frozen 1,438-row
v1.18 forecast pack from the continuous-spread test. Require at least two seasons
and 300 directed complete games; every band must have at least one observation.
Use model pick confidence c=max(p,1-p), and signed pick margin
m=sign(p-.5)*(home score-away score). Include losses as negative and ties as zero.
Exact p=.5 has no directed pick: exclude it from training and forecast zero.

Three fixed arms, with no grid or ROI selection:

1. `wp_mean` (primary requested method): arithmetic mean m in production's existing
   confidence bands 50–55%, 55–60%, 60–65%, 65–70%, 70–75%, 75–80%, 80%+.
   Forecast sign(p-.5)*that band's prior mean; do not round to an integer.
2. `wp_monotone_mean`: same seven means, weighted least-squares isotonic regression
   with training band counts as weights. This only pools adjacent reversals.
   Do not clamp negative means or force confidence to imply a positive mean.
3. `four_band_mean` (definition check): average signed MOV using the exact
   confidence cutpoints equivalent to current raw-spread magnitudes 3/7/10
   under sigma=12.37, rather than selecting magnitudes by ATS W-L. This retains
   the installed four groups but changes their fitting objective to means.

No smoothing bandwidth, market-offset slope, key-number snap, or current-season
outcome enters a fit. Missing or empty bins must fail explicitly, not be filled
from the scored season. Keep exact probabilities 0/1 valid in endpoint bins.

## Evaluation

Use identical rows and baselines to the earlier test: 816 primary 2023–25 games,
79 diagnostic 2026 W1–5 games; final ties included. Compare raw v1.18, market,
and installed ATS-optimized fixed bands. Report MSE/RMSE, MAE and bias, annual
results, per-game forecasts, prior-band counts and signed means.

Positive paired score gain means lower candidate error. Resample whole weeks
within season, 10,000 draws, seed 20261017; show 95% intervals and 98.333%
three-candidate sensitivity bounds. Nominate for a fresh forward test only if
primary MSE improvement has positive sensitivity lower bounds against both raw
and market. This is not a rule for automatic production replacement.

Report ATS W-L-P, all opportunities, skips/coverage, units/ROI at assumed -110,
and paired week intervals for units per opportunity. Mean margins are not cover
probabilities; these are descriptive sign decisions. Actual historical ATS quote
timestamps/prices are unverified. No ROI chooses a mapping. Freeze inputs and
retain every candidate even if it fails. No production writes or native ledger
backfills are permitted by this test.

## User-requested median extension

Added after the mean-only results were computed, at the user's request to compare
median MOV statistically. The exposed mean results are known; no median forecasts
have yet been scored. Add `wp_median` and `four_band_median` with the same seven
and four fixed groups, using each prior group's arithmetic sample median of
signed pick margin (average the two central observations for even n). No rounding,
threshold search or market input in training. Retain every original mean arm.

Mean estimates target squared error; medians target absolute error. Compare both
MSE and MAE on the same games, including direct median-minus-matched-mean pairs.
Median nomination uses MAE against raw and market, while mean nomination retains
MSE. Report 95% intervals plus 99% five-candidate sensitivity bounds. ATS returns
are descriptive, not a fitting target; a conditional median at its own line is
not a full cover-probability forecast at the quoted market line. Include losses
and tied finals identically in all fits. This extension is adaptive development,
not a new untouched experiment or evidence of prospective profitability.

After seeing the median results, add a descriptive ±0.01-point perturbation of
signed pick-band forecasts for the integer-valued median arms and installed fixed
bands. It diagnoses exact model-market equality skips; it does not select a new
rule or replace the unchanged median result with a favorable perturbation.
