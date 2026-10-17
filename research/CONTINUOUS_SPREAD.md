# Continuous v1.18 model spread experiment

Specified 2026-10-17 before computing challenger forecasts. The historical
v1.18 recipe and comparison data have already been exposed. This is development,
not a new untouched holdout or native forward experiment.

Keep v1.18 moneylines, fixed-band production mapping and every existing ledger
unchanged. Estimate a separate continuous **mean home-minus-away margin**.
The fixed-band ATS decision value is a benchmark, not an expected margin.

## Fixed candidates

All use strictly earlier seasons, at least two seasons and 300 complete games.
Let L be market home-margin spread, R = 12.37 Phi^-1(v1.18 probability),
Q = 12.37 Phi^-1(no-vig market moneyline probability); probabilities clip to
[.005,.995] as in production. Target is actual margin minus L.

* `gap_anchor`: L + beta (R-L). Reproduce the existing single-slope signal
  calibration as a continuous point forecast, without a discrete PMF.
* `signal_anchor`: L + beta (R-Q). Remove the market-moneyline-to-spread
  conversion discrepancy from the correction before training.
* `split_signal_anchor`: same as signal_anchor, with distinct slopes for
  reinforcing the market favorite and the remaining signal. v1.18 already
  treats those two regimes differently in its moneyline penalty.

Each slope minimizes prior-season squared residual error with fixed ridge
200 in point units, clipped to [0,1]. Split features have disjoint support,
so their separate solutions are the constrained joint ridge solution. No
intercept, parameter grid, annual ROI selector, key-number snap, or current-year
outcome enters a fit. Missing model/market inputs cannot produce a forecast.

## Evaluation and decision

Primary: 2023-25 on identical available rows. 2026 through last completed saved
week is separate diagnostic. Include final ties. Benchmarks: raw v1.18 spread,
market spread and the existing year-specific fixed bands. Report MSE/RMSE,
MAE and bias. Mean squared error is the primary proper point-forecast score;
MAE is secondary and targets a median, not a mean.

Report paired season-stratified whole-week bootstrap score gains (10,000 draws,
seed 20261017), 95% descriptive and 98.333% three-candidate sensitivity bounds.
These condition on fitted paths and do not correct all previous research.
A candidate is worth a fresh forward comparison only if its primary MSE gain
beats both raw and market with positive 98.333% lower bounds. A historical
nomination does not authorize production replacement. If none passes, explicitly
retain the existing production behavior and report that no improvement is proven.

ATS diagnostics use exact model-line equality as skip, integer actual-line
equality as push, flat 1u risk at assumed -110. Show all opportunities, W-L-P,
skips, coverage, units and ROI; prices/timestamps are unverified. This mean-based
ATS sign diagnostic is not a cover-probability or EV forecast. No betting result
selects a candidate. Current board forecasts are counterfactual research output,
never backfilled into the append-only forward ledger.
