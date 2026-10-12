# Earlier-season calibration and close-game stability

Exposed historical development; each evaluation season calibrated/selected using earlier-season OOF forecasts only. Formula design followed exposed history, so these are not untouched forward tests.

815 binary games, 294 with market confidence <60%. Production reproduction error 1.11e-16.

## Historical return context

| Arm | N | Units | ROI ± SE | Market-correct null |
|---|---:|---:|---:|---:|
| market | 811 | +0.18 | +0.02% ± 2.47 | -4.10% |
| production | 811 | +29.06 | +3.58% ± 2.53 | -4.10% |
| global_calibration | 811 | +10.74 | +1.32% ± 2.47 | -4.10% |
| close_only_calibration | 811 | +16.35 | +2.02% ± 2.51 | -4.10% |
| selected_scale | 811 | +0.18 | +0.02% ± 2.47 | -4.10% |

## Paired probability comparisons

Positive gain means the arm improves over production. Intervals use season/week clusters. Simultaneous intervals correct three all-game challenger comparisons; close slices remain descriptive.

| Slice | Arm | N | LL ↓ | LL gain [95% CI] | Brier ↓ |
|---|---|---:|---:|---|---:|
| all | market | 815 | 0.608072 | -0.002467 [-0.010503, +0.005517] | 0.210334 |
| all | production | 815 | 0.605605 | +0.000000 [+0.000000, +0.000000] | 0.208989 |
| all | global_calibration | 815 | 0.604970 | +0.000636 [-0.004467, +0.005688] | 0.208884 |
| all | close_only_calibration | 815 | 0.607325 | -0.001719 [-0.005503, +0.001410] | 0.209793 |
| all | selected_scale | 815 | 0.608072 | -0.002467 [-0.010503, +0.005517] | 0.210334 |
| market confidence <60% | market | 294 | 0.671079 | -0.009377 [-0.023324, +0.004793] | 0.239045 |
| market confidence <60% | production | 294 | 0.661702 | +0.000000 [+0.000000, +0.000000] | 0.234533 |
| market confidence <60% | global_calibration | 294 | 0.665065 | -0.003362 [-0.012362, +0.005635] | 0.236073 |
| market confidence <60% | close_only_calibration | 294 | 0.666468 | -0.004766 [-0.014846, +0.004004] | 0.236762 |
| market confidence <60% | selected_scale | 294 | 0.671079 | -0.009377 [-0.023324, +0.004793] | 0.239045 |

## Close-matchup annual replication

| Season | N | Market LL | Production LL | Production gain [95% CI] |
|---|---:|---:|---:|---|
| 2023 | 109 | 0.669613 | 0.667494 | +0.002119 [-0.021902, +0.026715] |
| 2024 | 95 | 0.669954 | 0.659399 | +0.010555 [-0.012655, +0.032352] |
| 2025 | 90 | 0.674044 | 0.657118 | +0.016925 [-0.010053, +0.041628] |

## Earlier-season fit choices

- 2023 global_calibration: intercept -0.0114, correction scale 0.2125; 540 games through 2022.
- 2023 close_only_calibration: intercept -0.1661, correction scale 0.1017; 165 games through 2022.
- 2023 selected correction scale 0.0; source through 2022.
- 2024 global_calibration: intercept +0.0216, correction scale 0.4071; 812 games through 2023.
- 2024 close_only_calibration: intercept -0.0025, correction scale 0.5408; 274 games through 2023.
- 2024 selected correction scale 0.0; source through 2023.
- 2025 global_calibration: intercept +0.0132, correction scale 0.5884; 1084 games through 2024.
- 2025 close_only_calibration: intercept +0.0001, correction scale 0.7856; 369 games through 2024.
- 2025 selected correction scale 0.0; source through 2024.

## Close-band contribution sensitivity

| Removed largest absolute contributions | N | Production LL gain [95% CI] |
|---|---:|---|
| close games, drop 0 largest absolute contributions | 294 | +0.009377 [-0.004793, +0.023324] |
| close games, drop 1 largest absolute contributions | 293 | +0.010997 [-0.003167, +0.024882] |
| close games, drop 5 largest absolute contributions | 289 | +0.011327 [-0.001455, +0.023962] |
| close games, drop 10 largest absolute contributions | 284 | +0.010314 [-0.001709, +0.021911] |

Trimming conditions on outcomes and is only a fragility diagnostic. Inspect annual consistency before interpreting the pooled close-band average.

Recalibration holds market prices fixed and adjusts only the model correction and intercept. The fixed ridge/scale grid are research choices; earlier-season fitting prevents calibration leakage but cannot remove historical design selection. No production, price source, native snapshots or deployment changes.
