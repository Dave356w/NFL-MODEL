# Test 40: a separate model on dynamic play-efficiency ratings, against production

Protocol: [KALMAN_RATINGS.md](../KALMAN_RATINGS.md), pushed (`0562c5e`) before any rating, feature or forecast was computed. Production v1.18 and the ledger are unchanged. Development evidence only.

Production reproduces its published forecasts: 2017-20 1.1e-16, 2021-22 6.9e-16, 2023-25 1.1e-16.

**Model.** `logit p = logit q + b*[pass_edge, rush_edge, qb_delta, site]`, where the edges come from a full-covariance Kalman filter over every team's pass/rush offense and defense (per-play efficiency, opponent-adjusted, drifting weekly, regressed between seasons). Fit, decay, ridge and the favorite penalty are production's.

**Tuning (2013-14 observation likelihood only):** EPA: q x2, rho 0.6, P0 x0.5; SR: q x2, rho 0.8, P0 x0.5.

## Verdicts (log-loss gain over production decides)

- **kalman_epa**: not better than production
- **kalman_sr**: not better than production
- **blend**: unresolved

Rule: better if the gain is positive on all three bases and its 98.33% interval excludes zero on at least one; not better if <= 0 on two or more; otherwise unresolved.

## Log-loss gain over production (x1000 per game; [98.33% interval])

| Arm | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 (diag.) |
|---|---:|---:|---:|---:|
| kalman_epa | -0.93 [-9.09, +7.23] | +2.65 [-1.36, +6.66] | -2.74 [-9.05, +3.57] | +13.58 |
| kalman_sr | -1.44 [-9.67, +6.78] | +2.68 [-1.51, +6.87] | -2.15 [-8.90, +4.60] | +13.63 |
| blend | +0.03 [-4.62, +4.68] | +1.80 [-0.29, +3.88] | -0.72 [-3.91, +2.48] | +8.99 |
| kalman_epa_standalone | -10.87 [-35.14, +13.39] | -29.19 [-42.56, -15.83] | -31.10 [-46.51, -15.70] | +18.05 |

## Log-loss gain over the market (x1000 per game ± SE)

| Model | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 |
|---|---:|---:|---:|---:|
| production | +0.05 ± 3.42 | -2.64 ± 1.70 | +1.66 ± 3.02 | -16.04 ± 15.01 |
| kalman_epa | -0.88 ± 1.11 | +0.01 ± 0.76 | -1.08 ± 0.82 | -2.46 ± 0.79 |
| kalman_sr | -1.40 ± 1.04 | +0.03 ± 0.79 | -0.49 ± 0.86 | -2.41 ± 0.75 |
| blend | +0.07 ± 1.65 | -0.85 ± 0.99 | +0.94 ± 1.82 | -7.05 ± 6.53 |
| kalman_epa_standalone | -10.82 ± 9.75 | -31.84 ± 5.31 | -29.44 ± 6.00 | +2.01 ± 20.99 |

## Flat 1u ROI (goal metric; reported, not used for the verdict)

| Model | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| production | -3.46% ± 3.38 (-17.5u) | -1.55% ± 1.82 (-24.2u) | +3.58% ± 2.52 (+29.1u) |
| kalman_epa | -5.46% ± 3.30; -10.1u vs prod, 36 flips | -4.37% ± 1.79; -43.9u vs prod, 74 flips | -0.42% ± 2.47; -32.4u vs prod, 38 flips |
| kalman_sr | -5.83% ± 3.30; -12.0u vs prod, 35 flips | -3.75% ± 1.79; -34.2u vs prod, 77 flips | -0.78% ± 2.47; -35.4u vs prod, 46 flips |
| blend | -3.89% ± 3.33; -2.2u vs prod, 17 flips | -3.00% ± 1.80; -22.5u vs prod, 36 flips | +1.25% ± 2.50; -18.9u vs prod, 21 flips |
| kalman_epa_standalone | -6.73% ± 3.52; -16.6u vs prod, 87 flips | -2.04% ± 1.98; -7.6u vs prod, 250 flips | -3.88% ± 2.66; -60.5u vs prod, 136 flips |

Same-row market favorite and market-correct null: 2015-16 favorite -26.0u, null -2.40%; 2017-22 favorite -59.2u, null -2.61%; 2023-25 favorite +0.2u, null -4.10%.

## By total band (log-loss gain over production x1000; units vs production)

| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |
|---|---|---:|---:|---:|
| kalman_epa | 2015-16 | -2.16 (+3.6u) | +1.97 (-4.4u) | -6.31 (-9.3u) |
| kalman_epa | 2017-22 | +2.11 (-2.9u) | +5.57 (-15.4u) | -1.22 (-25.7u) |
| kalman_epa | 2023-25 | +5.39 (+7.1u) | -3.16 (-25.1u) | -9.35 (-14.5u) |
| kalman_sr | 2015-16 | -3.77 (+3.6u) | +0.98 (-8.2u) | -5.39 (-7.4u) |
| kalman_sr | 2017-22 | +2.21 (-0.9u) | +5.76 (-7.7u) | -1.47 (-25.6u) |
| kalman_sr | 2023-25 | +5.05 (+11.1u) | -3.09 (-30.1u) | -6.82 (-16.4u) |
| blend | 2015-16 | +0.20 (+1.9u) | +1.40 (-7.1u) | -2.86 (+3.0u) |
| blend | 2017-22 | +2.33 (-1.3u) | +2.91 (-14.3u) | -0.04 (-6.9u) |
| blend | 2023-25 | +3.51 (+3.5u) | -1.22 (-18.1u) | -3.56 (-4.4u) |

## What the ratings model learns

Mean fitted coefficient per SD of each input over the weekly fits (share of fits with a positive sign):

| Input | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| site | -0.038 (21%) | -0.046 (23%) | -0.036 (0%) |
| pass_edge | +0.056 (100%) | +0.004 (66%) | -0.040 (0%) |
| rush_edge | +0.008 (68%) | +0.021 (80%) | +0.031 (72%) |
| d__avail__qb_delta | -0.029 (9%) | +0.032 (66%) | +0.051 (100%) |

Correlation of production's and kalman_epa's departures from the market, game by game: 2015-16 +0.28, 2017-22 +0.48, 2023-25 +0.28, 2026 wk1-5 (diagnostic) +0.14.

## Limits

Exposed history: the bases have been scored in many earlier tests, though no ratings model had been. EPA comes from nflverse's expected-points model, fit on earlier seasons (Test 7 caveat); the success-rate arm has no such issue. A "better" verdict would justify only a forward shadow test; adoption is a new REVISION and the owner's decision. Tables: `arms.csv`, `vs_market.csv`, `edges.csv.gz`, `predictions.csv.gz`, `tuning_grid.json`.

Run: `python research/kalman_ratings.py --build` (network), then `python research/kalman_ratings.py`.
