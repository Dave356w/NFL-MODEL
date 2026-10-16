# R003 iterations by probability and spread-value bands

Compared **69 saved fixed/earlier-season-selected models** on identical games:
816 in 2023–25, separate 1,055-game 2019–22 development and 79-game 2026
diagnostic cohorts. No models are refitted, no bands optimized and no rule
adopted. All historical data are exposed. Prices are uniformly **assumed −110
on both sides**, not independently archived historical offers.

Use the [interactive comparison](comparison.html) to switch models, periods,
bands and measures. Full [band metrics](band_metrics.csv),
[probability/spread cross-tab](probability_spread_cross.csv),
[overall results](overall.json), [paired comparisons](paired_comparisons.json)
and [model catalog](model_catalog.json) accompany this report.

## Overall iteration comparison, 2023–25

The same policy is replayed for every model: at most one 1u-risk ATS bet when
conditional cover probability exceeds 52.38095%, otherwise pass. Win profit
is 10/11u; pushes refund the stake. This compares probability iterations with
one common EV rule. AC1's separate Stable rule is not substituted into this
table. Different models select different subsets, so their raw ROIs are not
matched-subset treatment effects. Paired calendar-return comparisons count
passes as zero and are saved separately.

| Iteration | Cover log loss ↓ | Bets | Units | ROI ± SE |
|---|---:|---:|---:|---:|
| MC1 selected direct kernel | 0.705191 | 611 | −36.727 | −6.01% ±3.82 pp |
| MC1 selected all, includes translated scores | 0.694792 | 294 | −20.545 | −6.99% ±5.48 pp |
| MC2 plain observed-score model | 0.700040 | 560 | −32.545 | −5.81% ±3.99 pp |
| SC1 selected schedule context | 0.700025 | 561 | −33.545 | −5.98% ±3.99 pp |
| PT1 selected pooled travel | 0.701200 | 551 | −27.364 | −4.97% ±4.03 pp |
| AC1 selected calibration | 0.693345 | 0 | 0 | Undefined |
| Fair 50/50 reference | 0.693147 | 0 | 0 | Undefined |

MC2's selected-all path and fixed plain coincide on the main cohort; all their
earlier-period differences remain in the full catalog. Calibrated forecasts
reduce unsupported departures but do not establish an edge beyond fair 0.5.

For historical completeness, the **different original support-mask model**
returns **+5.909u on 321 bets**, ROI **+1.84% ±5.24 pp**, 95% week interval
**[−8.08%,+12.44%]**, cover LL 0.693888. Same-row spread favorites return
−22.727u and the push-adjusted fair ATS null is −4.40%. Its RF1 extension
returns −8.636u on 369 bets, ROI −2.34% ±4.90 pp. These legacy constructions
are distinct from the owner's plain observed-score market-context model.
The original's favorable point estimate is not an established edge or a reason
to replace the current model based on this retrospective ranking.

For plain, same-row spread favorites return −0.091u and the fair ATS null is
−4.45%. For SC1 these are +0.818u/−4.45%, and for PT1 +5.091u/−4.45%.
Every main-period headline active-policy ROI interval includes zero. No-bet
ROI remains undefined.

## Probability bands: units and number of bets

Own-model bands contain different games as probabilities change. Forecast
probabilities and realized rates below exclude actual pushes; units include
refunded pushes. Upper band endpoints are included.

| Predicted cover probability | Plain units (bets) | SC1 units (bets) | PT1 units (bets) |
|---|---:|---:|---:|
| 50–52.38% | Pass (256 games) | Pass (255 games) | Pass (265 games) |
| >52.38–55% | −34.091 (228) | −35.091 (229) | −14.455 (217) |
| >55–60% | +5.818 (279) | +5.818 (279) | −9.364 (276) |
| >60–65% | −5.545 (39) | −5.545 (39) | −4.818 (44) |
| >65% | +1.273 (14) | +1.273 (14) | +1.273 (14) |

Plain's weakest band predicts **53.65%** and realizes **44.44%** (100–125–3),
losing −14.95% ROI. Its 55–60% band predicts 57.00% and realizes 53.51%,
returning +2.09% ROI ±5.63 pp SE. The 60–65% band predicts 61.76% but realizes
44.74%. Higher reported confidence does not show a reliable monotonic increase
in success. The >65% group has only 14 bets and a very wide cover-rate interval.
AC1 selected places all 816 forecasts below the price threshold.

**Band migration matters.** PT1's own 55–60% group looks much worse than
plain's. But only 232 games overlap: 47 leave the band and 44 enter it. On
the original plain 279-game 55–60% cohort, PT1 makes the exact same bets and
returns the same +5.818u. It assigns 56.98% probability versus plain's 57.00%.
The own-band ROI difference therefore does not demonstrate worsening on those
same original games. `common_plain_probability_band` fixes both the games and
the calibration side for this comparison; returns still use each model's own
policy choices within that common cohort.

## Offered spread magnitude: units and bets

These cohorts have identical games across iterations, defined by the absolute
offered spread. Bet subsets within each cohort can still differ.

| Absolute spread | Plain units (bets) | SC1 units (bets) | PT1 units (bets) |
|---|---:|---:|---:|
| 0–3 points | −6.818 (219) | −6.818 (219) | −3.545 (210) |
| >3–7 points | −37.636 (224) | −38.636 (225) | −34.818 (225) |
| >7–10 points | +13.182 (68) | +13.182 (68) | +13.182 (68) |
| >10 points | −1.273 (49) | −1.273 (49) | −2.182 (48) |

The **>3–7-point bucket drives more than the entire net plain loss**; other
buckets offset it. All 224 plain bets in this offered-spread bucket are on
**underdogs receiving >3 through 7 points**, with a 95–124–5 record and
43.38% decisive cover rate. That is a directional selection tendency worth
monitoring, not proof that reversing or excluding this band is profitable.

The >7–10-point bucket looks favorable at +19.39% ROI, but has only 68 bets,
with ±11.20 pp SE. Its earlier-period result reverses, as shown below.
The interactive `handicap_band` view distinguishes favorites laying points
from underdogs receiving them rather than combining their signed offers.

## Projected point value is not cover probability

Define projected value as `(model mean margin − offered line)`, oriented toward
the model's probability-selected side. A negative number means the mean points
the other way; a skewed distribution can still give this side >50% cover chance.

| Plain projected value | Bets | Units | ROI |
|---|---:|---:|---:|
| <=0 points | 98 | −14.000 | −14.29% |
| >0–1 | 245 | −12.818 | −5.23% |
| >1–3 | 197 | −3.909 | −1.98% |
| >3–7 | 18 | −1.727 | −9.60% |
| >7 | 2 | −0.091 | −4.55% |

There is no dependable increasing return with projected point value. The
largest-value groups are particularly small. This is a diagnostic of the
mean and distribution, not a test of a newly optimized mean-gap betting rule.
AC1 mean margins are available for 2023–25 only; older projected-value views
explicitly show `Unavailable` rather than substitute raw means.

## Do favorable bands persist?

| Plain band | 2019–22 ROI (bets) | 2023–25 ROI (bets) |
|---|---:|---:|
| Cover probability >52.38–55% | +4.56% (287) | −14.95% (228) |
| Cover probability >55–60% | −5.03% (338) | +2.09% (279) |
| Offered spread >3–7 | +8.71% (289) | −16.80% (224) |
| Offered spread >7–10 | −9.41% (115) | +19.39% (68) |

These sign reversals weaken the case for a simple band filter. The positive
recent probability/spread pockets are hypotheses; these exposed slices do not
validate a threshold. The separate 2026 diagnostic is small and not fresh
confirmation. The legacy original also has a wide main ROI interval; its
positive main-period return does not resolve superiority.

The most useful conclusion is to retain the calibrated probability view and
track conditional calibration across these fixed bands on new games. The
existing results do not justify promoting a profitable-looking band or rolling
back to a historical ROI winner. New predictive signal requires its own fixed
specification and genuinely fresh evaluation.

## Definitions, uncertainty and reproduction

Calibration uses all decisive forecast games in each band, while bet returns
use only that model's positive-EV subset. Their sample sizes are both exported.
`common_plain_probability_band` uses plain's side for calibration; all other
axes use each model's higher-probability side (home breaks exact 0.5 ties only
for forecast summaries). No tie-break triggers a positive-EV bet.

Overall ROI/paired intervals use 10,000 whole-week draws within season, seed
20261016, conditional on existing forecasts. Band cover intervals are descriptive
Wilson intervals assuming independent binary results; ROI SE is per-bet sample
SE. They do not correct the many model/band comparisons or prior model design.
No-bet ROI and empty-band calibration are undefined, not zero-error estimates.

Reproduce with `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/compare_r003_bands.py`.
Independent rerun matches all eight generated artifacts byte for byte. All
69 models share the same outcomes/lines within each cohort, every axis exactly
partitions games/bets/units, and common-plain labels agree across models.
**678 passed, 1 xfailed**; interactive table filters also pass a DOM smoke
check. Original 192 protected files remain unchanged. No production, forecast,
threshold, bankroll policy or native forward-ledger row is modified.
