# Test 39: candidate model updates from Tests 36-38

Protocol: [MODEL_UPDATES.md](../MODEL_UPDATES.md), pushed (`a35d3e7`) before any candidate was scored. Production v1.18 and the ledger are unchanged. **Development evidence only**: every historical basis informed the candidates; the clean test of any of them is forward.

Production reproduces the published forecasts: 2017-20 1.1e-16, 2021-22 2.3e-13, 2023-25 1.1e-16; the native week-5 replay reproduces the archived snapshots to 1e-9 or better.

## Verdicts (primary candidates; log-loss gain over production decides)

- **ridge_0.3**: unresolved
- **ridge_1.0**: unresolved
- **shrink_0.5**: unresolved
- **prune_lobo**: unresolved

Rule: supported if the gain is positive on all three bases and its 98.75% interval excludes zero on at least one; not supported if the gain is <= 0 on two or more; otherwise unresolved.

## Log-loss gain over production (x1000 per game, all games; [98.75% interval])

| Arm | 2015-16 | 2017-22 | 2023-25 | 2014 (sens.) | 2026 wk1-5 (diag.) | native wk5 (replay) |
|---|---:|---:|---:|---:|---:|---:|
| ridge_0.3 | +0.66 [-3.07, +4.38] | +1.81 [+0.04, +3.59] | -0.19 [-3.18, +2.80] | +8.42 | +9.01 | +20.53 |
| ridge_1.0 | +0.50 [-6.03, +7.03] | +2.66 [-0.51, +5.82] | -1.03 [-6.47, +4.40] | +13.35 | +14.13 | +36.42 |
| shrink_0.5 | +0.84 [-3.50, +5.19] | +2.03 [-0.11, +4.18] | +0.15 [-3.63, +3.93] | +9.79 | +9.99 | +24.78 |
| prune_lobo | +0.75 [-2.78, +4.28] | +0.98 [-1.30, +3.26] | -2.15 [-8.32, +4.02] | +7.39 | +2.47 | +2.74 |
| prune_8 (descriptive) | +1.90 [-1.50, +5.31] | +1.00 [-0.70, +2.70] | +1.20 [-0.56, +2.97] | +6.52 | +3.62 | +2.72 |
| no_site (descriptive) | +0.47 [-1.16, +2.10] | +0.52 [-0.53, +1.56] | +0.54 [-0.47, +1.56] | -0.14 | -1.19 | -0.20 |
| half_life_4 (descriptive) | -0.04 [-1.21, +1.13] | +0.65 [-0.23, +1.54] | +0.26 [-1.12, +1.65] | -0.52 | +0.14 | +1.35 |

## Flat 1u ROI (goal metric; reported, not used for the verdict)

Arm ROI ± SE, units versus production on the same bets, and side flips (units on flipped games).

| Arm | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| production | -3.46% ± 3.38 (-17.5u) | -1.55% ± 1.82 (-24.2u) | +3.58% ± 2.52 (+29.1u) |
| ridge_0.3 | -2.72% ± 3.33; +3.7u vs prod; 14 flips (+3.7u) | -2.59% ± 1.81; -16.1u vs prod; 31 flips (-16.1u) | +1.77% ± 2.50; -14.7u vs prod; 17 flips (-14.7u) |
| ridge_1.0 | -5.80% ± 3.30; -11.9u vs prod; 27 flips (-11.9u) | -4.07% ± 1.79; -39.3u vs prod; 65 flips (-39.3u) | +1.53% ± 2.47; -16.6u vs prod; 30 flips (-16.6u) |
| shrink_0.5 | -2.78% ± 3.33; +3.4u vs prod; 16 flips (+3.4u) | -2.62% ± 1.80; -16.6u vs prod; 42 flips (-16.6u) | +1.61% ± 2.49; -16.0u vs prod; 23 flips (-16.0u) |
| prune_lobo | -3.05% ± 3.36; +2.0u vs prod; 18 flips (+2.0u) | -2.16% ± 1.82; -9.5u vs prod; 50 flips (-9.5u) | +0.96% ± 2.49; -21.3u vs prod; 32 flips (-21.3u) |
| prune_8 | -1.75% ± 3.37; +8.7u vs prod; 19 flips (+8.7u) | -2.29% ± 1.82; -11.5u vs prod; 35 flips (-11.5u) | +3.36% ± 2.51; -1.8u vs prod; 12 flips (-1.8u) |
| no_site | -3.19% ± 3.38; +1.4u vs prod; 11 flips (+1.4u) | -2.31% ± 1.82; -11.8u vs prod; 29 flips (-11.8u) | +3.05% ± 2.52; -4.3u vs prod; 6 flips (-4.3u) |
| half_life_4 | -3.31% ± 3.37; +0.7u vs prod; 9 flips (+0.7u) | -1.96% ± 1.82; -6.3u vs prod; 19 flips (-6.3u) | +3.27% ± 2.52; -1.8u vs prod; 10 flips (-1.8u) |

Same-row market favorite and market-correct null: 2015-16 favorite -26.0u, null -2.40%; 2017-22 favorite -59.2u, null -2.61%; 2023-25 favorite +0.2u, null -4.10%.

## By total band (log-loss gain x1000; units vs production)

| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |
|---|---|---:|---:|---:|
| ridge_0.3 | 2015-16 | +0.34 (+0.0u) | +2.06 (+0.7u) | -2.07 (+3.0u) |
| ridge_0.3 | 2017-22 | +2.28 (-1.3u) | +3.06 (-9.8u) | -0.18 (-5.0u) |
| ridge_0.3 | 2023-25 | +3.44 (+0.2u) | -0.67 (-12.4u) | -2.52 (-2.4u) |
| ridge_1.0 | 2015-16 | -0.20 (-0.3u) | +2.80 (-6.2u) | -3.91 (-5.4u) |
| ridge_1.0 | 2017-22 | +3.67 (+2.7u) | +5.06 (-16.1u) | -1.23 (-25.9u) |
| ridge_1.0 | 2023-25 | +5.09 (+9.0u) | -1.46 (-13.1u) | -5.79 (-12.5u) |
| shrink_0.5 | 2015-16 | +0.30 (-2.1u) | +2.51 (+6.8u) | -2.31 (-1.2u) |
| shrink_0.5 | 2017-22 | +3.41 (+6.0u) | +3.90 (-11.3u) | -1.27 (-11.4u) |
| shrink_0.5 | 2023-25 | +3.96 (+5.3u) | -0.07 (-12.4u) | -2.89 (-8.8u) |
| prune_lobo | 2015-16 | +1.39 (-2.1u) | +2.10 (+4.8u) | -2.28 (-0.7u) |
| prune_lobo | 2017-22 | +2.40 (+1.6u) | +2.66 (+3.1u) | -2.06 (-14.3u) |
| prune_lobo | 2023-25 | +7.02 (+5.9u) | -1.91 (-12.9u) | -11.10 (-14.3u) |

## Pruned inputs (prune_lobo)

- 2015-16: def plays, DL out, OL out, RB out, qb_delta, off pass yds/play, off penalty yds, max_deficit, max_lead, pass_1sd_nn, pass_1sd_np, pass_1sd_pp, site
- 2017-22: def pass yds/play, DB out, DL out, OL out, qb_delta, off pass yds/play, off penalty yds, max_deficit, pass_1sd_nn, pass_1sd_pp, site
- 2023-25: def INT %, def rush yds/att, DL out, OL out, qb_delta, off pass yds/play, off penalty yds, off plays, off rush yds/att, max_deficit, pass_1sd_nn, pass_1sd_pn, pass_1sd_pp, pass_product, site
- other bases: DL out, OL out, qb_delta, off pass yds/play, off penalty yds, max_deficit, pass_1sd_nn, pass_1sd_pp, site

## Limits

All historical bases informed these candidates (Tests 36-38), so even the leave-one-basis-out pruning is not a clean test. The decision rule uses log loss, as the protocol requires; ROI is reported. Supported means only "worth a forward shadow test"; any production change is a new REVISION and the owner's decision. Full tables: `arms.csv`, `predictions.csv.gz`.

Run: `python research/model_updates.py`.
