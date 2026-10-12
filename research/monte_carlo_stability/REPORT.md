# NFL Monte Carlo simulation results

**Finding:** the simulations add useful outcome ranges and sensitivity measurements, but no challenger establishes improved predictive accuracy. Keep production unchanged.

Exposed historical development, 2023–2025; unknown historical quote capture times. No production changes or native forward claims.

816 common priced games; 812 common historical flat-unit observations; 815 binary win scores.

| Arm | Units | Historical ROI ± SE | Market-null ROI | Log loss ↓ | Brier ↓ |
|---|---:|---:|---:|---:|---:|
| market | +0.18 | +0.02% ± 2.47 | -4.10% | 0.608072 | 0.210334 |
| production | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605605 | 0.208989 |
| empirical | +4.08 | +0.50% ± 2.47 | -4.10% | 0.608860 | 0.210629 |
| price_calibrated | +0.18 | +0.02% ± 2.47 | -4.10% | 0.608072 | 0.210334 |
| model_adjusted | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605605 | 0.208989 |
| feature_bootstrap | +20.06 | +2.47% ± 2.53 | -4.10% | 0.605908 | 0.209218 |
| coefficient_bootstrap | +21.28 | +2.62% ± 2.53 | -4.10% | 0.605584 | 0.209017 |
| combined | +17.54 | +2.16% ± 2.53 | -4.10% | 0.605676 | 0.209135 |

## Paired probability comparisons

Positive gain means lower challenger loss. Family intervals correct for 12 comparisons. They do not account for earlier design exploration.

| Challenger | Comparator | LL gain | 95% interval | Family interval |
|---|---|---:|---|---|
| empirical | market | -0.000788 | [-0.0076627713734434295, 0.005503788590012106] | [-0.010605573666482493, 0.00844446245527256] |
| empirical | production | -0.003255 | [-0.014106457395760524, 0.007086250739603034] | [-0.020204946485826162, 0.011364274032446454] |
| price_calibrated | market | +0.000000 | [0.0, 0.0] | [0.0, 0.0] |
| price_calibrated | production | -0.002467 | [-0.010502790218456307, 0.005517161511940085] | [-0.014085988664186344, 0.0090221372296245] |
| model_adjusted | market | +0.002467 | [-0.005517161511940086, 0.010502790218456301] | [-0.0090221372296245, 0.014085988664186347] |
| model_adjusted | production | +0.000000 | [0.0, 0.0] | [0.0, 0.0] |
| feature_bootstrap | market | +0.002165 | [-0.005686944798694289, 0.009972757885574586] | [-0.009385822530824728, 0.013322026381356766] |
| feature_bootstrap | production | -0.000302 | [-0.0031078387535155238, 0.0025475795860646936] | [-0.004301082244017107, 0.0041515002237534826] |
| coefficient_bootstrap | market | +0.002488 | [-0.005417893612606615, 0.010279339174607547] | [-0.008518439322179534, 0.013971034319406942] |
| coefficient_bootstrap | production | +0.000021 | [-0.0008347137740704609, 0.0008582364187452756] | [-0.0012408967316808804, 0.0012384905139777732] |
| combined | market | +0.002396 | [-0.00517829894809554, 0.010024346681353484] | [-0.008618047472683613, 0.013479800596325114] |
| combined | production | -0.000071 | [-0.0028567046800163608, 0.002705952197801594] | [-0.004139045846545531, 0.004166424920387528] |

## Uncertainty in estimated probabilities

Ranges below describe conditional bootstrap sensitivity; they are separate from outcome prediction intervals and Monte Carlo numerical error. Market empirical ranges hold fitted target centers fixed.

| Arm | Average probability SD, pp | Average 5–95% width, pp | Ranges crossing 50% |
|---|---:|---:|---:|
| empirical | 1.46 | 4.77 | 21 |
| feature_bootstrap | 4.61 | 13.81 | 194 |
| coefficient_bootstrap | 4.13 | 13.25 | 187 |
| combined | 7.12 | 22.02 | 330 |

## Outcome distributions

Tail = absolute margin ≥21 or total ≥60. Intervals are central prediction intervals; discrete boundaries can overcover.

| Arm | Target | CRPS ↓ | 50% coverage | 80% coverage | 90% coverage | 90% width |
|---|---|---:|---:|---:|---:|---:|
| empirical | margin | 7.078 | 51.7% | 79.5% | 90.3% | 42.8 |
| empirical | total | 7.223 | 53.8% | 81.1% | 90.6% | 43.2 |
| gaussian_market | margin | 7.081 | 54.4% | 78.8% | 88.7% | 41.9 |
| gaussian_market | total | 7.222 | 53.2% | 82.1% | 90.6% | 42.8 |
| model_adjusted | margin | 7.046 | 52.5% | 80.8% | 90.4% | 42.9 |
| model_adjusted | total | 7.219 | 54.3% | 81.4% | 90.6% | 43.5 |
| price_calibrated | margin | 7.071 | 53.9% | 80.6% | 90.7% | 43.5 |
| price_calibrated | total | 7.219 | 54.2% | 81.2% | 90.6% | 43.5 |

## Paired distribution comparisons

Against prior-week Gaussian market relationship forecast. Positive CRPS gain means improvement.

| Arm | Target | CRPS gain | 95% interval | Family interval |
|---|---|---:|---|---|
| empirical | margin | +0.0033 | [-0.02258607540783028, 0.027908888064662428] | [-0.030650690546698747, 0.03613993098097483] |
| price_calibrated | margin | +0.0096 | [-0.014253402062617115, 0.03279471643650798] | [-0.023266482718053073, 0.04009624223303367] |
| model_adjusted | margin | +0.0344 | [-0.03232784104513882, 0.10050772523023617] | [-0.05366436085664, 0.1209910788828127] |
| empirical | total | -0.0004 | [-0.03977073042015389, 0.03635558512915476] | [-0.0535612512216982, 0.05062519323028075] |
| price_calibrated | total | +0.0029 | [-0.023126651733724808, 0.029810017713084728] | [-0.0317353936815592, 0.040156605168327544] |
| model_adjusted | total | +0.0032 | [-0.023155125511494047, 0.030259060355086957] | [-0.03151863195416477, 0.04089025597665131] |

## Spread/total probability scores

Pushes excluded from conditional binary scores.

| Arm | Target | Non-push games | Event log loss ↓ | Event Brier ↓ |
|---|---|---:|---:|---:|
| empirical | margin | 797 | 0.696264 | 0.251540 |
| empirical | total | 811 | 0.692300 | 0.249572 |
| gaussian_market | margin | 797 | 0.693529 | 0.250186 |
| gaussian_market | total | 811 | 0.690099 | 0.248478 |
| model_adjusted | margin | 797 | 0.692855 | 0.249862 |
| model_adjusted | total | 811 | 0.693319 | 0.250086 |
| price_calibrated | margin | 797 | 0.693588 | 0.250220 |
| price_calibrated | total | 811 | 0.693319 | 0.250086 |

## By season

| Arm | Year | Units | Historical ROI | Log loss ↓ |
|---|---:|---:|---:|---:|
| market | 2023 | +4.12 | +1.53% | 0.627349 |
| market | 2024 | +14.11 | +5.21% | 0.587489 |
| market | 2025 | -18.05 | -6.66% | 0.609383 |
| production | 2023 | +8.44 | +3.12% | 0.630814 |
| production | 2024 | +24.47 | +9.03% | 0.583169 |
| production | 2025 | -3.85 | -1.42% | 0.602822 |
| empirical | 2023 | +6.07 | +2.25% | 0.624256 |
| empirical | 2024 | +14.11 | +5.21% | 0.584893 |
| empirical | 2025 | -16.09 | -5.94% | 0.617464 |
| price_calibrated | 2023 | +4.12 | +1.53% | 0.627349 |
| price_calibrated | 2024 | +14.11 | +5.21% | 0.587489 |
| price_calibrated | 2025 | -18.05 | -6.66% | 0.609383 |
| model_adjusted | 2023 | +8.44 | +3.12% | 0.630814 |
| model_adjusted | 2024 | +24.47 | +9.03% | 0.583169 |
| model_adjusted | 2025 | -3.85 | -1.42% | 0.602822 |
| feature_bootstrap | 2023 | +3.09 | +1.15% | 0.631483 |
| feature_bootstrap | 2024 | +22.65 | +8.36% | 0.583508 |
| feature_bootstrap | 2025 | -5.68 | -2.10% | 0.602721 |
| coefficient_bootstrap | 2023 | +4.86 | +1.80% | 0.630905 |
| coefficient_bootstrap | 2024 | +24.47 | +9.03% | 0.582492 |
| coefficient_bootstrap | 2025 | -8.05 | -2.97% | 0.603347 |
| combined | 2023 | +3.07 | +1.14% | 0.631425 |
| combined | 2024 | +22.15 | +8.17% | 0.582839 |
| combined | 2025 | -7.68 | -2.84% | 0.602755 |

## Numerical and source checks

- Exact production reproduction: maximum probability error 1.03e-10.
- Draws: 512 feature / 128 coefficient / 8192 outcomes, seed 20261013.
- Outcome draw mean absolute probability error: 0.402 percentage points. Exact weighted probabilities score the candidates.
- Minimum effective residual sample size: 275.1.
- Missing target-price exclusions: 0 of 816 eligible win games.
- Price-calibrated simulations reproduce the supplied moneyline by construction; model-adjusted simulations reproduce production by construction. Neither provides an independent new win signal.
- Model-adjusted scores constrain win and total probabilities; spread probabilities are allowed to change with the win signal.
- Availability and normalization reference uncertainty are held fixed. Feature bootstrap ranges are conditional sensitivity intervals, not validated confidence intervals.
- Whole games preserve within-game relationships; Bayesian multipliers measure profile estimation uncertainty, not future-game randomness. Historical regime shifts are not explicitly modelled.
- Integer score projection preserves parity and nonnegative scores, but is not a drive simulation and does not guarantee exact football key-number mass.
- Unknown quote timing and reconstructed upstream boxes limit historical interpretation. Recentered profile deviations preserve archived baseline inputs.
- Input hashes, full covariance matrices, per-feature SDs, annual summaries, calibration bins and source cutoffs are provided alongside this report.
- No historical winner is automatically adopted. A new forward experiment is required before making a production change.
