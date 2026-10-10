# Passing profile robustness results

Basis: exposed historical development; not native forward evidence.

812 common flat 1u bets; 815 binary scores.

| Arm | Units | ROI ± SE | Market-null ROI | LL | Brier |
|---|---:|---:|---:|---:|---:|
| production | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605605 | 0.208989 |
| profile_4 | +25.34 | +3.12% ± 2.53 | -4.10% | 0.605271 | 0.208849 |
| profile_12 | +29.19 | +3.60% ± 2.53 | -4.10% | 0.605358 | 0.208937 |
| bounded_2 | +31.92 | +3.93% ± 2.53 | -4.10% | 0.605829 | 0.209167 |
| combined_4_2 | +24.62 | +3.03% ± 2.51 | -4.10% | 0.605700 | 0.209118 |
| selected | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605610 | 0.209011 |
| market | +0.18 | +0.02% ± 2.47 | -4.10% | 0.608072 | 0.210334 |

| Arm | ROI change [CI], pp | LL gain [CI] | Side flips |
|---|---:|---:|---:|
| profile_4 | -0.46 [-1.39, +0.00] | +0.000335 [-0.000931, +0.001724] | 2 |
| profile_12 | +0.02 [-1.18, +1.24] | +0.000247 [-0.001953, +0.002597] | 4 |
| bounded_2 | +0.35 [-0.58, +1.57] | -0.000223 [-0.002875, +0.002253] | 4 |
| combined_4_2 | -0.55 [-2.44, +1.19] | -0.000095 [-0.003388, +0.002674] | 6 |
| selected | +0.00 [+0.00, +0.00] | -0.000005 [-0.000236, +0.000226] | 0 |

Annual results, diagnostic slices, prior-season selections, cutoff audits and support counts accompany this report in results.json and CSVs. Fixed comparisons use 98.75% intervals; selected uses 95%. Intervals omit design-selection uncertainty.

Reproduction errors: features 2.63e-14; historical predictions 1.94e-10; archived forecasts 3.33e-16.

## Archived SF at SEA

| Arm | SEA probability |
|---|---:|
| production | 93.90% |
| profile_4 | 92.04% |
| profile_12 | 89.67% |
| bounded_2 | 91.86% |
| combined_4_2 | 91.20% |
| market | 59.34% |

## Annual results

| Arm | Season | Units | ROI | LL |
|---|---:|---:|---:|---:|
| production | 2023 | +8.44 | +3.12% | 0.630814 |
| production | 2024 | +24.47 | +9.03% | 0.583169 |
| production | 2025 | -3.85 | -1.42% | 0.602822 |
| profile_4 | 2023 | +4.72 | +1.75% | 0.631011 |
| profile_4 | 2024 | +24.47 | +9.03% | 0.581955 |
| profile_4 | 2025 | -3.85 | -1.42% | 0.602837 |
| profile_12 | 2023 | +4.72 | +1.75% | 0.631810 |
| profile_12 | 2024 | +26.02 | +9.60% | 0.581304 |
| profile_12 | 2025 | -1.55 | -0.57% | 0.602951 |
| bounded_2 | 2023 | +8.44 | +3.12% | 0.633993 |
| bounded_2 | 2024 | +25.04 | +9.24% | 0.581883 |
| bounded_2 | 2025 | -1.55 | -0.57% | 0.601594 |
| combined_4_2 | 2023 | +0.97 | +0.36% | 0.633848 |
| combined_4_2 | 2024 | +22.90 | +8.45% | 0.581706 |
| combined_4_2 | 2025 | +0.75 | +0.28% | 0.601530 |
| selected | 2023 | +8.44 | +3.12% | 0.630814 |
| selected | 2024 | +24.47 | +9.03% | 0.583169 |
| selected | 2025 | -3.85 | -1.42% | 0.602837 |
| market | 2023 | +4.12 | +1.53% | 0.627349 |
| market | 2024 | +14.11 | +5.21% | 0.587489 |
| market | 2025 | -18.05 | -6.66% | 0.609383 |

## Diagnostic slices

| Arm | Slice | Binary games | LL | Units |
|---|---|---:|---:|---:|
| production | production >=90% | 15 | 0.083459 | +1.37 |
| production | production profile >2 SD | 123 | 0.565984 | +1.99 |
| profile_4 | production >=90% | 15 | 0.083810 | +1.37 |
| profile_4 | production profile >2 SD | 123 | 0.564038 | +1.99 |
| profile_12 | production >=90% | 15 | 0.084877 | +1.37 |
| profile_12 | production profile >2 SD | 123 | 0.564126 | +3.54 |
| bounded_2 | production >=90% | 15 | 0.083691 | +1.37 |
| bounded_2 | production profile >2 SD | 123 | 0.570277 | +1.99 |
| combined_4_2 | production >=90% | 15 | 0.083534 | +1.37 |
| combined_4_2 | production profile >2 SD | 123 | 0.569268 | -1.76 |
| selected | production >=90% | 15 | 0.083463 | +1.37 |
| selected | production profile >2 SD | 123 | 0.565454 | +1.99 |
| market | production >=90% | 15 | 0.127253 | +1.37 |
| market | production profile >2 SD | 123 | 0.559070 | -1.92 |

## Prior-season log-loss selection

- 2023: production
- 2024: production
- 2025: profile_4
