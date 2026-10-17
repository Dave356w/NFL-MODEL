# Win-probability calibration theory: test results

October 17, 2026. Research only. No production changes.

## Finding and concrete ideas

**Empirical win-frequency calibration does not currently establish a better WP
forecast than continuous v1.18.** The literal median of binary win/loss labels
is 0 or 1 (or sometimes 0.5), so the statistically meaningful analogue is a
calibrated win frequency, not a median probability.

1. **Do not replace WP with a stepped win-rate lookup based on this test.**
   v1.18 plus seven win-rate bands worsens both primary log loss and Brier loss,
   and also worsens the separate 2026 diagnostic.
2. **A monotone probability calibrator is a research comparison only.**
   Its primary log loss is essentially unchanged/slightly worse. It improves
   the 78-game 2026 slice but remains behind the market there. No challenger
   passes the specified adjusted primary comparison against both v1.18 and market.
3. **Keep probability calibration and median margin estimation distinct.**
   Outcomes of a binary event estimate WP through their frequency. A margin
   median estimates a different target. Better median-margin classifications
   do not imply that discretizing WP improves the underlying probabilities.

## Design and sample

Tested two calibration methods on each of v1.16 and v1.18: four challengers.
Each forecast season's calibrator uses strictly earlier seasons only. 2021–22
provide 540 decisive warm-up games; 2023, 2024, 2025, and 2026 calibration fits
use 540, 812, 1084, and 1355 earlier decisive games respectively.

The source contains 1438 games and five tied finals. Ties are excluded from
the binary W/L target. Primary evaluation is **2023–25: 815 decisive games**
(54 season-week blocks). Separate diagnostic is **2026 Weeks 1–5: 78 decisive
games** (five week blocks). The one tie in each evaluation cohort explains
the difference from the margin study's 816 and 79 games.

Current v1.18 is observed directly. v1.16 is recovered by analytically reversing
the fixed lambda=0.2 favorite-confidence penalty. Recovered probabilities match
all 1433 decisive retrospective reference rows, with maximum absolute difference
9.15e-11. Reference native snapshots
have different quote vintages and are excluded from this reconstruction check.

Seven-band method: fixed confidence cuts at 55%, 60%, 65%, 70%, 75%, and 80%,
Jeffreys-smoothed success frequencies (wins+0.5)/(games+1), returned to home
orientation. An exactly 50% forecast remains 50%. Rates below 50%, if learned,
are allowed. No cuts or smoothing parameters were optimized on scored outcomes.

Monotone method: symmetric isotonic regression of forecast probability on binary
outcome. Mirrored orientations each have weight 0.5 per original game, preserving
the original independent game count. Fixed bounds [.005,.995] prevent endpoint
log-loss singularities. Out-of-training-range values use the nearest endpoint.
This curve is monotone and interpolates between fitted thresholds; it is not
necessarily completely smooth or strictly increasing.

## Moneyline goal metric: same decisive-game cohorts

These probability calibrators were fitted on win frequencies/proper scores, never ROI.
Tied finals are excluded here to match the probability-test cohorts. Market pick'ems are
excluded from both sides of the common-row favorite comparison. Historical prices have
no independent quote timestamp. These are replay diagnostics, not a new profitability claim.

| Method | 2023–25 units | ROI ± 1 SE | 2026 W1–5 units | ROI ± 1 SE |
|---|---:|---:|---:|---:|
| Current v1.18 | +28.87 | +3.54% ± 2.53 pp | -4.85 | -6.22% ± 8.46 pp |
| v1.18 + win-rate bands | +28.87 | +3.54% ± 2.53 pp | -4.85 | -6.22% ± 8.46 pp |
| v1.18 + monotone calibration | +28.87 | +3.54% ± 2.53 pp | -4.85 | -6.22% ± 8.46 pp |
| Unadjusted v1.16 | +28.87 | +3.54% ± 2.53 pp | -4.85 | -6.22% ± 8.46 pp |
| v1.16 + win-rate bands | -5.55 | -0.68% ± 2.61 pp | -4.85 | -6.22% ± 8.46 pp |
| v1.16 + monotone calibration | +28.87 | +3.54% ± 2.53 pp | -4.85 | -6.22% ± 8.46 pp |

Current v1.18 has 815 primary decisive selections, market-correct null ROI -4.10%. On the 811 common priced rows, model ROI is +3.58% versus favorite ROI +0.02%.
The 2026 comparison has 78 decisive selections: model ROI -6.22% versus same-row favorite -4.75%, null -4.10%.

v1.18 bands and monotone calibration change probabilities but none of the model choices in these cohorts, so their moneyline returns are identical. The v1.16 band lookup reverses some low-confidence selections and worsens primary returns.

## Primary results: 2023–25

Lower log loss and Brier loss are better. Confidence-bin expected calibration
error (ECE) is descriptive and depends on grouping.

| Method | Log loss | Brier loss | Confidence-bin ECE |
|---|---:|---:|---:|
| No-vig market | 0.608072 | 0.210334 | 5.27 pp |
| Unadjusted v1.16 | 0.605605 | 0.208989 | 5.33 pp |
| Current v1.18 | 0.606414 | 0.209473 | 6.32 pp |
| v1.16 + win-rate bands | 0.614241 | 0.212286 | 5.82 pp |
| v1.16 + monotone calibration | 0.609966 | 0.210394 | 4.84 pp |
| v1.18 + win-rate bands | 0.608429 | 0.210050 | 5.55 pp |
| v1.18 + monotone calibration | 0.606860 | 0.209887 | 5.93 pp |

Both new methods have worse primary proper-score point estimates than their
own parent model. v1.18 monotone calibration improves its confidence-bin ECE
from 6.32 to 5.93 percentage points, while slightly worsening log loss and Brier
loss. A better-looking reliability grouping does not establish improved total
forecast quality.

## Separate 2026 diagnostic

| Method | Log loss | Brier loss | Confidence-bin ECE |
|---|---:|---:|---:|
| No-vig market | 0.650754 | 0.228903 | 6.04 pp |
| Unadjusted v1.16 | 0.698291 | 0.245934 | 12.74 pp |
| Current v1.18 | 0.672035 | 0.238503 | 8.14 pp |
| v1.16 + win-rate bands | 0.679085 | 0.240450 | 7.80 pp |
| v1.16 + monotone calibration | 0.715567 | 0.240759 | 5.18 pp |
| v1.18 + win-rate bands | 0.675428 | 0.239409 | 6.31 pp |
| v1.18 + monotone calibration | 0.661412 | 0.233792 | 5.17 pp |

v1.18 monotone calibration improves log loss by +0.010623 per decisive game
and Brier loss by +0.004711 relative to current v1.18. The descriptive paired
95% log-loss gain interval is [+0.000407, +0.020395]; the wider sensitivity
interval is [-0.002156, +0.024157]. This is only five week blocks on already
examined data, not independent prospective confirmation. Its log loss still
trails the market's 0.650754.

## Annual stability: log loss

| Year | Games | Current v1.18 | v1.18 + bands | v1.18 + monotone |
|---|---:|---:|---:|---:|
| 2023 | 272 | 0.630622 | 0.637194 | 0.640341 |
| 2024 | 272 | 0.585169 | 0.583736 | 0.582417 |
| 2025 | 271 | 0.603441 | 0.604343 | 0.597789 |
| 2026 | 78 | 0.672035 | 0.675428 | 0.661412 |

Monotone v1.18 calibration hurts 2023 and helps 2024, 2025 and the small 2026
slice. Later calibrators have more training data, but these results do not
establish that sample size is the cause or justify discarding 2023.

## Paired primary uncertainty

Positive gain means the challenger reduces log loss. Whole weeks are resampled
within seasons, 10,000 draws, seed 20261017. Intervals condition on the fitted
calibration paths. The 99.375% bounds are an eight-primary-comparison Bonferroni
sensitivity check, not an adjustment for all previous research or input-vintage
uncertainty. No candidate has positive adjusted lower bounds against both
current v1.18 and market.

| Challenger | Comparator | Log-loss gain | 95% interval | 99.375% sensitivity interval |
|---|---|---:|---|---|
| v1.16 + win-rate bands | Current v1.18 | -0.007827 | [-0.014073, -0.001117] | [-0.016342, +0.001450] |
| v1.16 + win-rate bands | No-vig market | -0.006169 | [-0.015222, +0.003031] | [-0.018731, +0.007454] |
| v1.16 + monotone calibration | Current v1.18 | -0.003552 | [-0.009934, +0.002415] | [-0.012398, +0.004789] |
| v1.16 + monotone calibration | No-vig market | -0.001894 | [-0.010326, +0.006288] | [-0.013768, +0.009743] |
| v1.18 + win-rate bands | Current v1.18 | -0.002015 | [-0.006710, +0.002703] | [-0.008634, +0.004361] |
| v1.18 + win-rate bands | No-vig market | -0.000357 | [-0.007250, +0.006500] | [-0.010156, +0.009366] |
| v1.18 + monotone calibration | Current v1.18 | -0.000446 | [-0.004885, +0.004022] | [-0.006905, +0.005890] |
| v1.18 + monotone calibration | No-vig market | +0.001212 | [-0.005388, +0.007728] | [-0.007991, +0.010263] |

## What the empirical lookup learns for 2026

Fitted using 1355 decisive games through 2025:

| Parent confidence | Prior games | Empirical calibrated confidence |
|---|---:|---:|
| 50–55% | 252 | 57.91% |
| 55–60% | 259 | 60.96% |
| 60–65% | 224 | 65.56% |
| 65–70% | 189 | 66.58% |
| 70–75% | 161 | 75.62% |
| 75–80% | 134 | 72.96% |
| 80%+ | 136 | 87.96% |

The 70–75% group's fitted success frequency exceeds the 75–80% group's rate.
This shows the sampling irregularity that a direct lookup can transmit into
future forecasts. Isotonic calibration enforces order, but flexibility still
requires evaluation outside its training seasons.

## Validation and reproduction

- Independent archived v1.16 reconstruction check: 1433 matched decisive games.
- Label-invariance check: changing all outcomes in or after a forecast season
  leaves that season's probabilities unchanged, at all four year boundaries.
- Known-count bin fixture, neutral forecast, probability bounds, symmetry and
  isotonic monotonicity checks pass.
- Scores agree with independent scikit-learn log-loss/Brier implementations.
- Duplicate game records are rejected.
- Seven output artifacts reproduce byte for byte in a separate process.

From the repository root, run:

```bash
python -m research.wp_probability_calibration
python -m pytest tests/test_wp_probability_calibration.py -q
```

Dependencies and exact versions are recorded in `provenance.json`.
This directory includes frozen source inputs. The independently archived reference forecasts remain in `research/favorite_penalty_results/inputs.csv`. The research runner and tests retain the
fixed protocol, annual maps, per-game forecasts, calibration tables,
current-board counterfactuals and paired uncertainty estimates. Current-board
counterfactuals are research output, not archived forward forecasts.

## Limits

The base model recipe and favorite penalty were selected after historical
development; 2023–25 is already examined. Strict earlier-season calibration
prevents leakage at the calibration stage but does not undo that upstream
selection. These are reconstructed historical forecasts with uncertain source
quote vintages. No raw NFL features were rebuilt in this test. No new independent
holdout, prospective performance, ATS improvement or financial edge is claimed.
Do not select a new rule on a favorable annual slice or a grouped calibration
chart alone. The supplied decision applies only to the four specified challengers.

## Sources

- [Frozen historical ledger](https://github.com/Dave356w/NFL-MODEL/blob/690c0c6740f7a5a6c4ef3c2abe244cc0df0dca2d/data/latest/fixed_band_ledger.csv)
- [Favorite-confidence transformation and research history](https://github.com/Dave356w/NFL-MODEL/blob/690c0c6740f7a5a6c4ef3c2abe244cc0df0dca2d/research/FAVORITE_PENALTY.md)
- [Independent frozen v1.16 inputs](https://github.com/Dave356w/NFL-MODEL/blob/690c0c6740f7a5a6c4ef3c2abe244cc0df0dca2d/research/favorite_penalty_results/inputs.csv)
- [scikit-learn probability calibration documentation](https://scikit-learn.org/stable/modules/calibration.html)

Log loss and Brier loss measure overall probabilistic forecasting quality;
their values incorporate discrimination as well as calibration. ECE is
reported separately rather than treated as a proper score.

## Repository implementation

The weighted PAV calibrator is implemented with NumPy rather than adding a production dependency. Its per-game probabilities match the independently executed scikit-learn reference to numerical precision. `provenance.json` records source hashes and current runtime versions.
