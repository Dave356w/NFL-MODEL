# Test 41: iterations of the Test 40 ratings model

Protocol: [KALMAN_ITERATIONS.md](../KALMAN_ITERATIONS.md), pushed (`cc9642a`) before any iteration was built or scored. Production v1.18 and the ledger are unchanged. Development evidence only.

Production reproduces its published forecasts: 2017-20 1.1e-16, 2021-22 6.9e-16, 2023-25 1.1e-16.

**Tuning (2013-14 only):** eff_all: q x1, rho 0.8, P0 x0.5; margin: q x0.25, rho 0.8, P0 x0.5; ats: q x0.25, rho 0.8, P0 x0.5; pass/rush EPA and success-rate settings as in Test 40.

## Verdicts (log-loss gain over production decides)

- **k2_margin**: not better than production
- **k3_ats**: not better than production
- **k4_combined**: not better than production
- **k5_ridge1**: not better than production
- **k6_compact**: not better than production
- **selected**: not better than production
- **kalman_epa (Test 40, reference)**: not better than production

Nested selection chose, by season: 2017 production, 2018 k6_compact, 2019 k5_ridge1, 2020 k2_margin, 2021 k5_ridge1, 2022 k2_margin, 2023 k5_ridge1, 2024 k5_ridge1, 2025 k5_ridge1.

Rule: better if the gain is positive on every basis scored and its 99.17% interval excludes zero on at least one; not better if <= 0 on at least half; otherwise unresolved.

## Log-loss gain over production (x1000 per game; [99.17% interval])

| Arm | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 (diag.) |
|---|---:|---:|---:|---:|
| kalman_epa | -0.93 [-9.92, +8.06] | +2.65 [-1.76, +7.07] | -2.74 [-9.69, +4.22] | +13.58 |
| k2_margin | -0.07 [-9.36, +9.22] | +2.64 [-1.84, +7.11] | -2.78 [-9.76, +4.20] | +13.62 |
| k3_ats | -0.69 [-9.86, +8.49] | +2.51 [-2.04, +7.06] | -2.98 [-9.96, +3.99] | +13.54 |
| k4_combined | -0.50 [-9.47, +8.48] | +2.54 [-1.87, +6.94] | -2.86 [-10.04, +4.31] | +14.02 |
| k5_ridge1 | -0.19 [-9.12, +8.75] | +2.89 [-1.54, +7.31] | -2.11 [-9.68, +5.46] | +15.28 |
| k6_compact | -0.00 [-9.28, +9.27] | +2.55 [-2.02, +7.12] | -3.10 [-10.26, +4.06] | +14.00 |
| selected | - | +2.20 [-2.07, +6.46] | -2.11 [-9.68, +5.46] | - |

## Log-loss gain over the market (x1000 per game ± SE)

| Model | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 |
|---|---:|---:|---:|---:|
| production | +0.05 ± 3.42 | -2.64 ± 1.70 | +1.66 ± 3.02 | -16.04 ± 15.01 |
| kalman_epa | -0.88 ± 1.11 | +0.01 ± 0.76 | -1.08 ± 0.82 | -2.46 ± 0.79 |
| k2_margin | -0.02 ± 1.33 | -0.01 ± 0.77 | -1.12 ± 0.81 | -2.42 ± 0.82 |
| k3_ats | -0.64 ± 1.41 | -0.14 ± 0.79 | -1.33 ± 0.98 | -2.50 ± 0.67 |
| k4_combined | -0.45 ± 1.10 | -0.11 ± 0.69 | -1.21 ± 0.66 | -2.02 ± 0.89 |
| k5_ridge1 | -0.14 ± 0.57 | +0.24 ± 0.42 | -0.45 ± 0.37 | -0.76 ± 0.87 |
| k6_compact | +0.04 ± 1.48 | -0.09 ± 0.75 | -1.44 ± 0.83 | -2.04 ± 0.83 |
| selected | - | -0.45 ± 0.78 | -0.45 ± 0.37 | - |

## Flat 1u ROI (goal metric; reported, not used for the verdict)

| Model | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| production | -3.46% ± 3.38 (-17.5u) | -1.55% ± 1.82 (-24.2u) | +3.58% ± 2.52 (+29.1u) |
| kalman_epa | -5.46% ± 3.30; -10.1u vs prod, 36 flips | -4.37% ± 1.79; -43.9u vs prod, 74 flips | -0.42% ± 2.47; -32.4u vs prod, 38 flips |
| k2_margin | -5.76% ± 3.31; -11.7u vs prod, 39 flips | -3.99% ± 1.79; -38.0u vs prod, 75 flips | -0.18% ± 2.47; -30.5u vs prod, 37 flips |
| k3_ats | -4.59% ± 3.31; -5.8u vs prod, 42 flips | -4.07% ± 1.80; -39.3u vs prod, 72 flips | -0.87% ± 2.47; -36.1u vs prod, 38 flips |
| k4_combined | -5.04% ± 3.30; -8.0u vs prod, 39 flips | -4.67% ± 1.79; -48.7u vs prod, 80 flips | -0.41% ± 2.47; -32.4u vs prod, 40 flips |
| k5_ridge1 | -4.35% ± 3.30; -4.5u vs prod, 35 flips | -4.14% ± 1.79; -40.4u vs prod, 83 flips | -0.44% ± 2.47; -32.6u vs prod, 38 flips |
| k6_compact | -5.00% ± 3.31; -7.8u vs prod, 41 flips | -4.28% ± 1.79; -42.5u vs prod, 79 flips | -1.35% ± 2.47; -40.0u vs prod, 42 flips |
| selected | - | -3.94% ± 1.80; -37.2u vs prod, 69 flips | -0.44% ± 2.47; -32.6u vs prod, 38 flips |

Same-row market favorite and market-correct null: 2015-16 favorite -26.0u, null -2.40%; 2017-22 favorite -59.2u, null -2.61%; 2023-25 favorite +0.2u, null -4.10%.

## By total band (log-loss gain over production x1000; units vs production)

| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |
|---|---|---:|---:|---:|
| k2_margin | 2015-16 | +0.14 (+5.4u) | +2.17 (-5.8u) | -4.72 (-11.3u) |
| k2_margin | 2017-22 | +2.11 (+1.1u) | +5.48 (-11.5u) | -1.16 (-27.6u) |
| k2_margin | 2023-25 | +5.39 (+7.1u) | -3.19 (-25.1u) | -9.44 (-12.5u) |
| k3_ats | 2015-16 | +0.15 (+3.6u) | +2.12 (+2.0u) | -6.78 (-11.3u) |
| k3_ats | 2017-22 | +1.44 (-2.9u) | +5.41 (-10.7u) | -1.11 (-25.7u) |
| k3_ats | 2023-25 | +6.46 (+7.1u) | -3.73 (-28.7u) | -10.11 (-14.5u) |
| k4_combined | 2015-16 | -1.66 (+3.6u) | +2.23 (-2.3u) | -5.57 (-9.3u) |
| k4_combined | 2017-22 | +2.25 (-2.8u) | +6.19 (-14.1u) | -2.51 (-31.8u) |
| k4_combined | 2023-25 | +4.45 (+9.1u) | -3.21 (-25.1u) | -8.89 (-16.4u) |
| k5_ridge1 | 2015-16 | -2.38 (+5.4u) | +2.78 (-4.5u) | -5.30 (-5.5u) |
| k5_ridge1 | 2017-22 | +3.67 (-1.0u) | +6.13 (-9.2u) | -2.08 (-30.1u) |
| k5_ridge1 | 2023-25 | +5.74 (+7.1u) | -2.43 (-21.3u) | -8.67 (-18.4u) |
| k6_compact | 2015-16 | +1.39 (+5.4u) | +2.54 (-2.0u) | -5.80 (-11.3u) |
| k6_compact | 2017-22 | +1.79 (+1.2u) | +6.12 (-15.9u) | -2.16 (-27.9u) |
| k6_compact | 2023-25 | +5.99 (+7.1u) | -3.57 (-28.7u) | -10.48 (-18.4u) |
| selected | 2017-22 | -1.78 (-5.9u) | +6.96 (+0.5u) | -2.69 (-31.9u) |
| selected | 2023-25 | +5.74 (+7.1u) | -2.43 (-21.3u) | -8.67 (-18.4u) |

## Mean fitted coefficient per SD (weekly fits)

| Arm | Basis | Coefficients |
|---|---|---|
| kalman_epa | 2015-16 | site -0.038, pass_edge +0.056, rush_edge +0.008, qb_delta -0.029 |
| kalman_epa | 2017-22 | site -0.046, pass_edge +0.004, rush_edge +0.021, qb_delta +0.032 |
| kalman_epa | 2023-25 | site -0.036, pass_edge -0.040, rush_edge +0.031, qb_delta +0.051 |
| k2_margin | 2015-16 | site -0.035, pass_edge +0.005, rush_edge -0.011, qb_delta -0.025, margin_edge +0.095 |
| k2_margin | 2017-22 | site -0.045, pass_edge -0.020, rush_edge +0.009, qb_delta +0.034, margin_edge +0.048 |
| k2_margin | 2023-25 | site -0.036, pass_edge -0.045, rush_edge +0.028, qb_delta +0.051, margin_edge +0.010 |
| k3_ats | 2015-16 | site -0.037, pass_edge +0.017, rush_edge -0.004, qb_delta -0.026, ats_edge +0.081 |
| k3_ats | 2017-22 | site -0.046, pass_edge +0.005, rush_edge +0.022, qb_delta +0.032, ats_edge -0.004 |
| k3_ats | 2023-25 | site -0.036, pass_edge -0.019, rush_edge +0.043, qb_delta +0.051, ats_edge -0.050 |
| k4_combined | 2015-16 | site -0.038, eff_edge +0.063, qb_delta -0.028 |
| k4_combined | 2017-22 | site -0.046, eff_edge +0.020, qb_delta +0.033 |
| k4_combined | 2023-25 | site -0.035, eff_edge -0.009, qb_delta +0.051 |
| k5_ridge1 | 2015-16 | site -0.029, pass_edge +0.014, rush_edge +0.003, qb_delta -0.008 |
| k5_ridge1 | 2017-22 | site -0.034, pass_edge +0.002, rush_edge +0.005, qb_delta +0.008 |
| k5_ridge1 | 2023-25 | site -0.026, pass_edge -0.008, rush_edge +0.006, qb_delta +0.013 |
| k6_compact | 2015-16 | site -0.034, eff_edge -0.006, margin_edge +0.068, ats_edge +0.056, qb_delta -0.024 |
| k6_compact | 2017-22 | site -0.046, eff_edge -0.000, margin_edge +0.053, ats_edge -0.022, qb_delta +0.034 |
| k6_compact | 2023-25 | site -0.036, eff_edge +0.007, margin_edge +0.023, ats_edge -0.059, qb_delta +0.052 |

## Limits

Exposed history; six arms and a selection arm on the same bases (Bonferroni over 6). The ATS rating uses closing spreads of past games only. EPA comes from nflverse's expected-points model (Test 7 caveat). A "better" verdict would justify only a forward shadow test. Tables: `arms.csv`, `vs_market.csv`, `edges.csv.gz`, `predictions.csv.gz`.

Run: `python research/kalman_iterations.py`.
