# Test 42: a model built only from features production does not use

Protocol: [DISJOINT_FEATURES.md](../DISJOINT_FEATURES.md), pushed (`69b104c`) before any feature was built or scored. Production v1.18 and the ledger are unchanged. Development evidence only.

Production reproduces its published forecasts: 2017-20 1.1e-16, 2021-22 2.3e-13, 2023-25 1.1e-16.

**Disjoint features:** ratings `pass_edge`, `rush_edge`, `margin_edge`, `ats_edge`; schedule `rest_diff`; market structure `ml_spread_gap`, `total_x_market`, `div_x_market`. None is a production input.

## Verdicts (log-loss gain over production decides)

- **disjoint**: unresolved
- **production_plus_disjoint**: not better than production
- **blend**: unresolved

Rule: better if the gain is positive on all three bases and its 98.33% interval excludes zero on at least one; not better if <= 0 on two or more; otherwise unresolved.

## Log-loss gain over production (x1000 per game; [98.33% interval])

| Arm | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 (diag.) |
|---|---:|---:|---:|---:|
| disjoint | +0.82 [-8.24, +9.87] | +2.39 [-1.94, +6.73] | -3.25 [-10.53, +4.02] | +15.29 |
| production_plus_disjoint | -0.89 [-5.43, +3.65] | +0.15 [-1.09, +1.40] | -1.31 [-3.68, +1.05] | -0.69 |
| blend | +0.78 [-4.67, +6.24] | +2.04 [-0.24, +4.32] | -0.56 [-4.26, +3.14] | +8.97 |
| disjoint_ratings | +0.56 [-7.59, +8.71] | +2.58 [-1.62, +6.79] | -2.50 [-9.25, +4.25] | +15.35 |
| disjoint_context | -1.29 [-9.89, +7.31] | +2.38 [-1.90, +6.65] | -2.47 [-10.00, +5.07] | +16.16 |

## Log-loss gain over the market (x1000 per game ± SE)

| Model | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 |
|---|---:|---:|---:|---:|
| production | +0.05 ± 3.42 | -2.64 ± 1.70 | +1.66 ± 3.02 | -16.04 ± 15.01 |
| disjoint | +0.86 ± 2.16 | -0.25 ± 0.61 | -1.59 ± 1.28 | -0.75 ± 3.18 |
| production_plus_disjoint | -0.84 ± 3.22 | -2.49 ± 1.70 | +0.34 ± 3.03 | -16.73 ± 15.84 |
| blend | +0.83 ± 1.74 | -0.60 ± 0.88 | +1.10 ± 1.72 | -7.07 ± 7.97 |
| disjoint_ratings | +0.61 ± 1.11 | -0.06 ± 0.48 | -0.84 ± 0.79 | -0.69 ± 0.61 |
| disjoint_context | -1.25 ± 1.31 | -0.27 ± 0.39 | -0.81 ± 0.93 | +0.12 ± 2.78 |

## Flat 1u ROI (goal metric; reported, not used for the verdict)

| Model | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| production | -3.46% ± 3.38 (-17.5u) | -1.55% ± 1.82 (-24.2u) | +3.58% ± 2.52 (+29.1u) |
| disjoint | -4.70% ± 3.30; -6.3u vs prod, 38 flips | -3.99% ± 1.79; -38.0u vs prod, 88 flips | -0.43% ± 2.47; -32.5u vs prod, 40 flips |
| production_plus_disjoint | -3.47% ± 3.35; -0.1u vs prod, 15 flips | -1.48% ± 1.82; +1.2u vs prod, 26 flips | +2.29% ± 2.52; -10.4u vs prod, 11 flips |
| blend | -4.91% ± 3.31; -7.4u vs prod, 23 flips | -2.71% ± 1.80; -18.1u vs prod, 43 flips | +0.86% ± 2.49; -22.0u vs prod, 28 flips |
| disjoint_ratings | -5.07% ± 3.30; -8.2u vs prod, 39 flips | -4.00% ± 1.79; -38.1u vs prod, 88 flips | +0.06% ± 2.47; -28.6u vs prod, 44 flips |
| disjoint_context | -4.70% ± 3.30; -6.3u vs prod, 34 flips | -4.16% ± 1.79; -40.6u vs prod, 85 flips | -0.21% ± 2.47; -30.8u vs prod, 41 flips |

Same-row market favorite and market-correct null: 2015-16 favorite -26.0u, null -2.40%; 2017-22 favorite -59.2u, null -2.61%; 2023-25 favorite +0.2u, null -4.10%.

## By total band (log-loss gain over production x1000; units vs production)

| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |
|---|---|---:|---:|---:|
| disjoint | 2015-16 | +6.88 (+3.4u) | +2.72 (-0.3u) | -5.66 (-9.4u) |
| disjoint | 2017-22 | +3.04 (+2.9u) | +5.21 (-11.0u) | -1.91 (-29.9u) |
| disjoint | 2023-25 | +8.95 (+5.2u) | -5.28 (-21.2u) | -10.24 (-16.5u) |
| production_plus_disjoint | 2015-16 | +7.57 (+1.9u) | -1.22 (-7.0u) | -3.85 (+5.1u) |
| production_plus_disjoint | 2017-22 | -0.11 (+0.1u) | -0.54 (+7.2u) | +1.26 (-6.0u) |
| production_plus_disjoint | 2023-25 | +1.89 (+1.7u) | -2.44 (-12.1u) | -1.90 (-0.1u) |
| blend | 2015-16 | +4.56 (-0.3u) | +1.81 (-5.9u) | -2.94 (-1.2u) |
| blend | 2017-22 | +3.13 (+8.1u) | +3.46 (-10.7u) | -0.48 (-15.4u) |
| blend | 2023-25 | +5.70 (+5.3u) | -1.71 (-18.5u) | -3.91 (-8.9u) |

## What the disjoint features learn (mean fitted coefficient per SD over the weekly fits)

| Feature | 2015-16 disjoint | 2017-22 disjoint | 2023-25 disjoint | 2015-16 joint | 2017-22 joint | 2023-25 joint |
|---|---:|---:|---:|---:|---:|---:|
| pass_edge | +0.010 | -0.016 | -0.032 | +0.018 | -0.028 | -0.029 |
| rush_edge | -0.008 | +0.013 | +0.036 | +0.018 | +0.007 | +0.036 |
| margin_edge | +0.096 | +0.055 | +0.024 | +0.108 | +0.043 | +0.020 |
| ats_edge | +0.070 | -0.023 | -0.058 | +0.055 | -0.029 | -0.055 |
| rest_diff | -0.020 | -0.016 | +0.018 | -0.031 | -0.021 | +0.018 |
| ml_spread_gap | -0.061 | -0.035 | -0.050 | -0.049 | -0.036 | -0.052 |
| total_x_market | -0.054 | -0.001 | +0.036 | -0.037 | -0.004 | +0.031 |
| div_x_market | -0.061 | +0.031 | +0.046 | -0.052 | +0.028 | +0.033 |

Correlation of production's and the disjoint model's departures from the market, game by game: 2015-16 +0.15, 2017-22 +0.29, 2023-25 +0.07, 2026 wk1-5 (diagnostic) +0.09.

Feature coverage (share of evaluation games with a value; missing counts as 0): complete on every basis.

## Limits

Exposed history. Rest and the ratings were examined before (Tests 20, 40, 41); the market-structure features are new. History uses the last recorded lines for q, the spread and the total alike. A "better" verdict would justify only a forward shadow test. Tables: `arms.csv`, `vs_market.csv`, `predictions.csv.gz`.

Run: `python research/disjoint_features.py`.
