# Test 43: team profiles from the last 2, 3 or 4 games instead of long decay

Protocol: [FORM_WINDOWS.md](../FORM_WINDOWS.md), pushed (`d06f8e5`) before any windowed profile was built or scored. Production v1.18 and the ledger are unchanged. Development evidence only.

## Rebuild fidelity

Production's half-life-8 profiles recomputed from the rebuilt box scores, against the frozen packs:

- 2013-20 pack: 2048 games; max abs difference 3.55e-15; 100.0% of games identical to 1e-9; by season 2013 100%, 2014 100%, 2015 100%, 2016 100%, 2017 100%, 2018 100%, 2019 100%, 2020 100%.
- 2019-26 pack: 2143 games; max abs difference 1.68e+01; 54.4% of games identical to 1e-9; by season 2019 0%, 2020 0%, 2021 0%, 2022 100%, 2023 100%, 2024 100%, 2025 100%, 2026 29%.

The 2019-26 pack, like the published 2021-25 history it reproduces exactly, starts its history in 2019, so its 2019-21 profiles lack the 2016-18 games that the three-season window reaches; the rebuild carries them, as the 2013-20 pack does. 2022-25 are identical. 2026 differs through upstream revisions of the current season (diagnostic only).

Rebuilt production (rebuilt profiles, packs' availability and pass contexts) against the published v1.18 forecasts:

- 2015-16: max |dp| 9.83e-11, mean 1.39e-12, same side 100.0%.
- 2017-22: max |dp| 1.55e-02, mean 8.67e-04, same side 99.6%.
- 2023-25: max |dp| 1.14e-02, mean 1.06e-03, same side 99.8%.
- 2026 wk1-5 (diagnostic): max |dp| 2.14e-03, mean 4.69e-04, same side 100.0%.

Every arm, the comparator included, is scored on the rebuilt features (one data version).

## Verdicts (log-loss gain over rebuilt production decides)

- **window_2**: not better than production
- **window_3**: not better than production
- **window_4**: not better than production
- **selected (descriptive)**: not better than production

Nested selection chose, by season: 2017 window_4, 2018 window_4, 2019 window_4, 2020 production, 2021 production, 2022 production, 2023 production, 2024 production, 2025 production.

## Log-loss gain over rebuilt production (x1000 per game; [98.33% interval])

| Arm | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 (diag.) |
|---|---:|---:|---:|---:|
| window_2 | -0.75 [-7.04, +5.55] | -1.48 [-4.31, +1.35] | -0.57 [-5.19, +4.04] | -0.32 |
| window_3 | -1.12 [-5.97, +3.72] | -1.47 [-4.15, +1.21] | +0.20 [-4.05, +4.45] | -10.02 |
| window_4 | +4.36 [-1.26, +9.98] | -2.27 [-4.76, +0.21] | -1.34 [-4.97, +2.30] | +1.90 |
| selected | - | -1.82 [-3.45, -0.19] | +0.00 [+0.00, +0.00] | - |

## Log-loss gain over the market (x1000 per game ± SE)

| Model | 2015-16 | 2017-22 | 2023-25 | 2026 wk1-5 |
|---|---:|---:|---:|---:|
| rebuilt production | +0.05 ± 3.42 | -2.58 ± 1.71 | +1.63 ± 3.09 | -16.42 ± 15.07 |
| window_2 | -0.70 ± 3.43 | -4.06 ± 1.90 | +1.06 ± 3.11 | -16.74 ± 18.29 |
| window_3 | -1.08 ± 3.79 | -4.05 ± 1.80 | +1.83 ± 3.10 | -26.44 ± 9.51 |
| window_4 | +4.41 ± 4.08 | -4.86 ± 1.88 | +0.29 ± 3.26 | -14.51 ± 14.43 |
| selected | - | -4.41 ± 1.82 | +1.63 ± 3.09 | - |

## Flat 1u ROI (goal metric; reported, not used for the verdict)

| Model | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| rebuilt production | -3.46% ± 3.38 (-17.5u) | -1.73% ± 1.82 (-26.9u) | +3.63% ± 2.53 (+29.5u) |
| window_2 | -1.67% ± 3.39; +9.1u vs prod, 32 flips | -2.89% ± 1.82; -18.1u vs prod, 65 flips | +1.09% ± 2.54; -20.6u vs prod, 38 flips |
| window_3 | -2.35% ± 3.40; +5.6u vs prod, 26 flips | -2.96% ± 1.83; -19.2u vs prod, 69 flips | +2.54% ± 2.53; -8.9u vs prod, 36 flips |
| window_4 | +0.33% ± 3.40; +19.2u vs prod, 24 flips | -4.40% ± 1.83; -40.4u vs prod, 70 flips | +0.88% ± 2.53; -22.3u vs prod, 29 flips |
| selected | - | -3.05% ± 1.82; -20.6u vs prod, 31 flips | +3.63% ± 2.53; +0.0u vs prod, 0 flips |

Same-row market favorite and market-correct null: 2015-16 favorite -26.0u, null -2.40%; 2017-22 favorite -59.2u, null -2.61%; 2023-25 favorite +0.2u, null -4.10%.

## By total band (log-loss gain x1000; units vs rebuilt production)

| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |
|---|---|---:|---:|---:|
| window_2 | 2015-16 | -9.20 (+0.3u) | +4.07 (+4.7u) | -6.95 (+4.1u) |
| window_2 | 2017-22 | -0.84 (+2.4u) | -1.33 (-16.4u) | -1.98 (-4.1u) |
| window_2 | 2023-25 | -5.00 (-7.3u) | +1.73 (-7.8u) | -1.33 (-5.5u) |
| window_3 | 2015-16 | -9.88 (+0.4u) | +1.47 (-0.5u) | -2.66 (+5.7u) |
| window_3 | 2017-22 | -0.91 (+6.2u) | -1.12 (-13.4u) | -2.23 (-12.0u) |
| window_3 | 2023-25 | -0.28 (-0.0u) | +1.01 (-9.8u) | -1.06 (+0.9u) |
| window_4 | 2015-16 | +1.61 (+2.4u) | +6.53 (+12.7u) | +1.12 (+4.1u) |
| window_4 | 2017-22 | -2.19 (-3.5u) | -1.85 (-19.6u) | -2.92 (-17.3u) |
| window_4 | 2023-25 | -2.08 (-2.2u) | -2.24 (-14.4u) | +1.22 (-5.7u) |

## Limits

Exposed history; Test 8 swept half-lives on an older model. Upstream play-by-play revisions can make rebuilt profiles differ slightly from the frozen packs, so all arms use the rebuilt data. A "better" verdict would justify only a forward shadow test. Tables: `arms.csv`, `vs_market.csv`, `predictions.csv.gz`.

Run: `python research/form_windows.py --boxes PBP_DIR GAMES_CSV` (raw files), then `python research/form_windows.py`.
