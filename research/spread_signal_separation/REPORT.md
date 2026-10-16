# Market signal, historical-distribution information and ATS price

**The spread is informative; the current R003 plain transformation does not
establish incremental information or an ATS edge.** These are three different
questions, evaluated separately below with explicit market-only benchmarks.

Main sample: **816 games, 2023–25**, with 815 decisive winner outcomes and
797 decisive ATS outcomes. Separate 2019–22 and 2026 diagnostics are retained.
All history is exposed retrospective development, not native forward evidence.
Every new market-only fit uses strictly earlier weeks and the same six-season,
two-season-half-life window; no model or ROI threshold is selected here.

## Market-only financial benchmarks

Flat 1u moneyline on the more likely winner, same 812 eligible priced games:

| Forecast inputs | Units | ROI ± SE |
|---|---:|---:|
| Spread only, prior-trained logistic | −1.713 | −0.21% ±2.47 pp |
| Spread + total, prior-trained logistic | +2.720 | +0.33% ±2.47 pp |
| No-vig moneyline / market favorite | +0.180 | +0.02% ±2.47 pp |
| R003 plain | −4.210 | −0.52% ±2.48 pp |
| AC1 calibrated coherent distribution | −1.713 | −0.21% ±2.47 pp |

The common same-row favorite baseline is +0.180u and the moneyline
market-correct null is approximately −4.10% ROI. Every listed main ROI interval
includes zero. The spread-only benchmark's interval is [−5.09%,+4.75%]; the
spread+total interval is [−4.57%,+5.32%]. Positive point returns do not establish
an edge. Moneyline returns and ATS returns below price different events.

## 1. How well does spread predict margins and outright winners?

For margin, use the quoted signed spread directly as a point forecast of
home-minus-away, rather than turn a winner probability into a spread prediction.

| Margin forecast | MAE ↓ | RMSE ↓ |
|---|---:|---:|
| Zero margin | 11.205 | 14.500 |
| Earlier historical mean home margin | 11.098 | 14.351 |
| **Market spread** | **9.744** | 12.653 |
| Earlier linear margin-on-spread calibration | 9.770 | **12.648** |
| R003 plain mean | 9.835 | 12.754 |
| AC1 calibrated distribution mean | 9.776 | 12.656 |

Spread improves absolute error over the spread-free historical baseline by
**1.353 points/game**, 95% paired week interval **[1.055,1.659]**; 99%
sensitivity [0.954,1.757]. This is substantial predictive information.
Correlation with actual margin is **0.477**, and the raw-spread point forecast
explains approximately **22.0%** of observed margin variance in this cohort.
Large remaining game-level errors do not imply no signal.

For outright winner probabilities, the market-only benchmarks use logistic
models with only spread or spread/total as pregame inputs, fitted on earlier
outcomes. Training on past outcomes is not using current outcomes as features.

| Winner forecast | Log loss ↓ | Brier ↓ | Pick accuracy |
|---|---:|---:|---:|
| Earlier historical home-win rate | 0.690352 | 0.248602 | 54.23% |
| Fair home-win 0.5 reference | 0.693147 | 0.250000 | 54.23%* |
| **Market spread only** | **0.607050** | **0.210002** | 68.22% |
| Market spread + total | 0.607232 | 0.210027 | 68.59% |
| Market no-vig moneylines | 0.608072 | 0.210334 | 68.22% |
| R003 plain | 0.612332 | 0.212262 | 68.10% |
| AC1 coherent distribution | 0.608176 | 0.210394 | 68.34% |

*Exact 0.5 uses home solely for reporting pick accuracy; it is not a betting
signal. Proper scores, not this arbitrary tie-break, judge the forecast.

Spread-only winner log-loss gain over the historical home-rate baseline is
**0.083303**, 95% interval **[0.061115,0.105187]**; the 99% sensitivity
interval also stays positive. The market spread clearly contains winner signal.
Adding total does not resolve an improvement over spread-only here.

The market is not perfectly calibrated in every exposed period. Descriptive
main-period margin-on-spread slope is 1.166, week-cluster interval [1.021,1.311],
versus 0.976 [0.863,1.089] in 2019–22. This regression uses evaluation outcomes
for diagnosis, not forecasting. A fair cover line also need not equal a mean
margin; this descriptive deviation is not itself an executable ATS rule.

## 2. Does the historical distribution add information beyond spread?

For **this plain implementation**, no incremental improvement is demonstrated.

- Its mean margin adds **0.091 points of absolute error** versus spread alone.
  Gain = −0.0910, ordinary 95% interval [−0.1642,−0.0202]; the five-comparison
  sensitivity spans zero. AC1's difference from the spread point forecast is
  smaller and unresolved.
- Its winner log loss is **0.005282 worse** than spread-only, ordinary 95%
  gain interval [−0.010141,−0.000388]. The wider sensitivity interval includes
  zero. There is no added winner accuracy to promote from this comparison.
- AC1's winner loss is close to spread-only, with unresolved gain −0.001127,
  interval [−0.004105,+0.001869]. Repairing overconfidence does not establish
  new information beyond the market inputs.

For ATS probabilities, compare conditional home-cover forecasts at the quoted
line on the **same 797 non-push games**:

| Cover forecast | Log loss ↓ | Brier ↓ |
|---|---:|---:|
| **Market-neutral 50/50** | **0.693147** | **0.250000** |
| R003 plain | 0.700040 | 0.253348 |
| AC1 selected calibration | 0.693345 | 0.250099 |
| Original legacy support-mask model | 0.693888 | 0.250347 |

Equal −110 offers imply a 50/50 no-vig ATS reference. That is a market-neutral
benchmark, not a claim every game's true probability is exactly 0.5. Actual
home cover frequency is 50.19% in the main cohort. Winner probabilities from
the spread-only classifier are never substituted for ATS cover probabilities.

Raw's ATS log-loss gain versus fair is −0.006893, ordinary interval
[−0.013490,−0.000137], with wider sensitivity crossing zero. AC1 removes much
of that error, but has no resolved advantage over fair: gain −0.000198,
interval [−0.001017,+0.000620]. This is evidence about the tested mapping,
not proof that all historical distributions or future features lack value.

## 3. Does any directional advantage survive −110?

Keep the **original −110-selected games fixed** when removing the price cost;
do not reselect at even-money odds. This isolates directional results from
payout reduction without searching a new strategy.

| ATS policy | W–L–P | Even-money units | −110 payout reduction | Net units |
|---|---|---:|---:|---:|
| Plain | 270–278–12 | −8.000 | −24.545 | **−32.545** |
| AC1 selected | No bets | 0 | 0 | 0; ROI undefined |
| Market-neutral 50/50 EV rule | No bets | 0 | 0 | 0; ROI undefined |
| Original legacy support mask | 166–145–10 | +21.000 | −15.091 | +5.909 |

For 1u risk, a −110 winner earns 10/11u. Therefore:

`net units = (wins − losses) − wins/11`

Plain's selected bets already have **negative directional returns at even
money**. Its 49.27% decisive cover rate falls below both even-money 50% and
−110 break-even 52.38095%. Price then removes another 24.545 units.

Its −110 result is **−5.81% ROI ±3.99 pp SE**, 95% interval
[−12.78%,+0.89%], on 560 bets. Same-row spread favorites return −0.091u;
the fair ATS null, adjusted for observed pushes, is −4.45%. Losing here does
not establish performance below that negative-hold null with high certainty.

The legacy construction has positive historical point returns, **+1.84% ±5.24
pp SE**, but its interval [−8.08%,+12.44%] is wide. Same-row spread favorites
return −22.727u; its fair ATS null is −4.40%. It is a different model, and
neither its returns nor its proper scores establish an edge. No historical ROI
winner is adopted. AC1's all-pass result supplies no positive-profit evidence.

## Conclusion and next test

The market spread successfully summarizes meaningful matchup information.
The current R003 plain score-distribution construction has not added reliable
information beyond it, and its apparent ATS edges do not survive even before
price. Calibration recovers market-like forecasts and appropriate abstention.

A new candidate should demonstrate incremental proper-score information over
**spread-only, spread+total and moneyline market baselines**, then establish
price-aware results on genuinely fresh retained forecasts and actual quotes.
The next useful hypothesis is a separately specified pregame team/QB matchup
signal available at forecast time. These findings do not justify additional
ROI-based threshold tuning on the same historical bands.

## Reproduction and limits

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/spread_signal_separation.py`.
Per-game forecasts, 129 prior-week fit windows, signed-spread bands, paired
comparisons and exact price decompositions accompany this report. Main point
forecasts share 816 games; winner proper scores exclude one game tie; ATS
proper scores exclude 19 pushes. Moneyline returns exclude quote pick'ems and
include refunded game ties, yielding 812 bets.

New market-only fitting uses one fixed specification per baseline; predictive
parameters never use current-week outcomes. Descriptive OLS is clearly separate.
Intervals use 10,000 paired whole-week draws within season, seed20261016,
conditional on fitted paths; five-comparison 99% sensitivity is not correction
for all earlier adaptive research. AC1 coherent margin/winner forecasts are
available for main years only; absent older forecasts are not filled with raw.

Both −110 sides are a user-specified retrospective scenario, not verified
historical offered prices. Moneyline/spread capture times and schedule revisions
remain unaudited. All history is exposed, and no forward edge is established.
**684 passed, 1 xfailed**; nine data artifacts reproduce exactly in a separate
process. Input/protected-file hashes remain unchanged. No production, original
forecast, betting rule or native forward-ledger row is changed.
