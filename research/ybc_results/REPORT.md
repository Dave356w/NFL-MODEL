# Test 44: yards before contact and tackles for loss, offense and defense

Protocol: [YARDS_BEFORE_CONTACT.md](../YARDS_BEFORE_CONTACT.md), pushed (`fac1eee`) before any profile was built or scored; tackles-for-loss addendum pushed (`1c0464d`) before any profile was built or scored. Production v1.18 and the ledger are unchanged. Development evidence only.

Production reproduces its published forecasts (max abs error): 2017-20 2.2e-16, 2021-22 2.3e-13, 2023-25 2.2e-16, 2021-22 basis 2.3e-13.

**Inputs** (home minus away, production's half-life-8 weighting with four league pseudo-games): yards before contact per carry, offense (`d_ybc_off`) and allowed (`d_ybc_def`); yards after contact per carry (`d_yac_off`, `d_yac_def`), PFR charting via nflverse from 2018; share of designed runs tackled for a loss, offense (`d_tfl_off`, higher is worse) and forced by the defense (`d_tfl_def`), nflverse play-by-play from 2013.

Coverage of evaluation games: ybc 2021-22 100%, 2023-25 100%, 2026 wk1-5 (diagnostic) 100%; tfl 2015-16 100%, 2017-22 100%, 2023-25 100%, 2026 wk1-5 (diagnostic) 100%.

## Verdicts (log-loss gain over production decides; K = 4)

- **plus_ybc** (2021-22, 2023-25): not better than production
- **plus_ybc_yac** (2021-22, 2023-25): not better than production
- **swap_rush** (2021-22, 2023-25): not better than production
- **plus_tfl** (2015-16, 2017-22, 2023-25): not better than production

Rule: better if the gain is positive on every basis and its 98.75% interval excludes zero on at least one; not better if <= 0 on at least half the bases (one of two; two of three); otherwise unresolved.

## Yards before / after contact: log-loss gain over production (x1000 per game; [98.75% interval])

| Arm | 2021-22 | 2023-25 | 2026 wk1-5 (diag.) |
|---|---:|---:|---:|
| plus_ybc | -0.29 [-3.05, +2.47] | +0.05 [-1.16, +1.27] | -4.19 |
| plus_ybc_yac | +0.01 [-4.28, +4.30] | -0.33 [-2.27, +1.61] | -4.33 |
| swap_rush | +0.14 [-4.12, +4.40] | -0.40 [-2.37, +1.58] | -3.69 |

Log-loss gain over the market (x1000 per game ± SE):

| Model | 2021-22 | 2023-25 | 2026 wk1-5 |
|---|---:|---:|---:|
| production | -5.25 ± 3.08 | +1.66 ± 3.02 | -16.04 ± 15.01 |
| plus_ybc | -5.54 ± 3.18 | +1.71 ± 2.98 | -20.23 ± 16.54 |
| plus_ybc_yac | -5.24 ± 3.28 | +1.33 ± 2.95 | -20.37 ± 17.67 |
| swap_rush | -5.11 ± 3.22 | +1.26 ± 2.93 | -19.73 ± 17.49 |

Flat 1u ROI at the moneyline (goal metric; reported, not used for the verdict):

| Model | 2021-22 | 2023-25 |
|---|---:|---:|
| production | -4.39% ± 3.15 (-23.8u, n=542) | +3.58% ± 2.52 (+29.1u, n=812) |
| plus_ybc | -5.98% ± 3.13; -8.6u vs prod, 10 flips | +3.02% ± 2.52; -4.6u vs prod, 6 flips |
| plus_ybc_yac | -4.72% ± 3.15; -1.8u vs prod, 15 flips | +2.98% ± 2.53; -4.9u vs prod, 11 flips |
| swap_rush | -5.18% ± 3.14; -4.3u vs prod, 14 flips | +2.90% ± 2.53; -5.5u vs prod, 11 flips |

Same-row market favorite and market-correct null: 2021-22 favorite -40.0u, null -2.72%; 2023-25 favorite +0.2u, null -4.10%.

By total band (log-loss gain x1000; units vs production):

| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |
|---|---|---:|---:|---:|
| plus_ybc | 2021-22 | -3.38 (-2.0u) | +2.54 (-0.3u) | -3.20 (-6.2u) |
| plus_ybc | 2023-25 | +1.65 (+0.0u) | +0.48 (-4.7u) | -2.32 (+0.1u) |
| plus_ybc_yac | 2021-22 | -4.66 (-2.0u) | +2.78 (+4.5u) | -1.95 (-4.3u) |
| plus_ybc_yac | 2023-25 | +2.09 (+2.7u) | -0.30 (-4.0u) | -2.61 (-3.5u) |
| swap_rush | 2021-22 | -4.53 (-2.0u) | +3.14 (+2.1u) | -2.20 (-4.3u) |
| swap_rush | 2023-25 | +2.17 (+4.8u) | -0.44 (-6.7u) | -2.68 (-3.5u) |

## Tackles for loss: log-loss gain over production (x1000 per game; [98.75% interval])

| Arm | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 (diag.) |
|---|---:|---:|---:|---:|
| plus_tfl | -0.81 [-3.14, +1.52] | -0.74 [-1.34, -0.13] | -0.22 [-1.70, +1.25] | +0.53 |

Log-loss gain over the market (x1000 per game ± SE):

| Model | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 |
|---|---:|---:|---:|---:|
| production | +0.05 ± 3.42 | -2.64 ± 1.70 | +1.66 ± 3.02 | -16.04 ± 15.01 |
| plus_tfl | -0.76 ± 3.85 | -3.38 ± 1.70 | +1.44 ± 3.10 | -15.51 ± 14.97 |

Flat 1u ROI at the moneyline (goal metric; reported, not used for the verdict):

| Model | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| production | -3.46% ± 3.38 (-17.5u, n=507) | -1.55% ± 1.82 (-24.2u, n=1559) | +3.58% ± 2.52 (+29.1u, n=812) |
| plus_tfl | -2.96% ± 3.39; +2.5u vs prod, 7 flips | -1.99% ± 1.82; -6.9u vs prod, 12 flips | +3.42% ± 2.53; -1.3u vs prod, 9 flips |

Same-row market favorite and market-correct null: 2015-16 favorite -26.0u, null -2.40%; 2017-22 favorite -59.2u, null -2.61%; 2023-25 favorite +0.2u, null -4.10%.

By total band (log-loss gain x1000; units vs production):

| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |
|---|---|---:|---:|---:|
| plus_tfl | 2015-16 | +3.00 (+2.5u) | -1.22 (-0.0u) | -1.62 (+0.0u) |
| plus_tfl | 2017-22 | -0.48 (-2.3u) | -0.72 (-3.1u) | -0.89 (-1.5u) |
| plus_tfl | 2023-25 | +0.28 (+2.2u) | -1.37 (-5.4u) | +1.71 (+1.9u) |

## What the fits learn (mean fitted coefficient per SD; share of weekly fits positive)

**plus_ybc_yac**

| Input | 2021-22 | 2023-25 |
|---|---:|---:|
| d_ybc_off | -0.002 (47%) | +0.036 (98%) |
| d_ybc_def | -0.110 (0%) | -0.055 (0%) |
| d_yac_off | +0.040 (94%) | -0.044 (0%) |
| d_yac_def | +0.063 (100%) | +0.015 (67%) |
| off rush_yards_per_attempt | +0.026 (100%) | +0.004 (69%) |
| def rush_yards_per_attempt | -0.023 (0%) | -0.026 (0%) |

**plus_tfl**

| Input | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| d_tfl_off | -0.034 (15%) | -0.014 (26%) | -0.022 (26%) |
| d_tfl_def | -0.046 (0%) | +0.014 (71%) | +0.026 (89%) |
| off rush_yards_per_attempt | -0.066 (0%) | -0.008 (38%) | +0.002 (57%) |
| def rush_yards_per_attempt | -0.023 (32%) | -0.012 (40%) | -0.040 (0%) |

Correlations (2021-25 games, `correlations_2021_25.csv`): d_ybc_off vs off rush_yards_per_attempt +0.79; d_ybc_def vs def rush_yards_per_attempt +0.78; d_yac_off vs off rush_yards_per_attempt +0.55; d_yac_def vs def rush_yards_per_attempt +0.55. Tackles for loss, 2015-25: d_tfl_off vs off rush_yards_per_attempt -0.24; d_tfl_def vs def rush_yards_per_attempt -0.34; with yards before contact (2021-25): d_tfl_off vs d_ybc_off -0.18; d_tfl_def vs d_ybc_def -0.34.

## Limits

Yards before contact can only be scored on 2021-25 (data from 2018; fits need two seasons of rows): two bases and less power than Tests 40-43. PFR charting is a human judgement of the contact point. Tackles for loss are scored on 2015-25, all exposed history. A "better" verdict would justify only a forward shadow test. Tables: `arms.csv`, `vs_market.csv`, `profiles.csv.gz`, `predictions.csv.gz`, `correlations_2021_25.csv`.

Run: `python research/yards_before_contact.py --build DIR --pbp PBP_DIR` (raw files), then `python research/yards_before_contact.py`.
