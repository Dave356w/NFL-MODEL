# Context shrinkage backtest

Basis: Exposed historical development; prior-week fits, 2023-2025. Recipe design used this history; not forward evidence.

812 common flat 1u bets; 815 binary proper scores.

| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|
| production | 565-246-1 | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605605 | 0.208989 |
| product_only | 562-249-1 | +19.32 | +2.38% ± 2.49 | -4.10% | 0.607584 | 0.209859 |
| market | 555-256-1 | +0.18 | +0.02% ± 2.47 | -4.10% | 0.608072 | 0.210334 |
| active_10 | 563-248-1 | +25.50 | +3.14% ± 2.53 | -4.10% | 0.605505 | 0.208956 |
| active_30 | 563-248-1 | +25.50 | +3.14% ± 2.53 | -4.10% | 0.605549 | 0.208970 |
| active_100 | 563-248-1 | +23.93 | +2.95% ± 2.52 | -4.10% | 0.606001 | 0.209166 |
| information_30 | 561-250-1 | +17.76 | +2.19% ± 2.50 | -4.10% | 0.606599 | 0.209438 |
| selected | 564-247-1 | +24.48 | +3.01% ± 2.50 | -4.10% | 0.606627 | 0.209373 |

Paired prior-week-cluster bootstrap; four fixed candidate comparisons use 98.75% intervals. Positive LL gain favors shrinkage.

| Arm | ROI delta vs production [CI], pp | LL gain [CI] | Side flips |
|---|---:|---:|---:|
| active_10 | -0.44 [-1.34, +0.00] | +0.000101 [-0.000683, +0.001136] | 2 |
| active_30 | -0.44 [-1.34, +0.00] | +0.000056 [-0.001695, +0.002209] | 2 |
| active_100 | -0.63 [-2.42, +1.06] | -0.000396 [-0.003742, +0.003217] | 8 |
| information_30 | -1.39 [-3.47, +0.54] | -0.000994 [-0.005455, +0.003531] | 12 |
| selected | -0.56 [-1.68, +0.42] | -0.001022 [-0.003673, +0.001360] | 7 |

## Annual selection

- 2023: information_30; selection through 2022.
- 2024: active_10; selection through 2023.
- 2025: active_30; selection through 2024.

## Annual results

| Arm | Season | Units | ROI | Log loss |
|---|---:|---:|---:|---:|
| production | 2023 | +8.44 | +3.12% | 0.630814 |
| production | 2024 | +24.47 | +9.03% | 0.583169 |
| production | 2025 | -3.85 | -1.42% | 0.602822 |
| product_only | 2023 | +3.86 | +1.43% | 0.636443 |
| product_only | 2024 | +19.21 | +7.09% | 0.581645 |
| product_only | 2025 | -3.75 | -1.38% | 0.604652 |
| market | 2023 | +4.12 | +1.53% | 0.627349 |
| market | 2024 | +14.11 | +5.21% | 0.587489 |
| market | 2025 | -18.05 | -6.66% | 0.609383 |
| active_10 | 2023 | +4.89 | +1.81% | 0.631099 |
| active_10 | 2024 | +24.47 | +9.03% | 0.582514 |
| active_10 | 2025 | -3.85 | -1.42% | 0.602891 |
| active_30 | 2023 | +4.89 | +1.81% | 0.631665 |
| active_30 | 2024 | +24.47 | +9.03% | 0.581959 |
| active_30 | 2025 | -3.85 | -1.42% | 0.603014 |
| active_100 | 2023 | +6.01 | +2.23% | 0.633079 |
| active_100 | 2024 | +19.47 | +7.18% | 0.581567 |
| active_100 | 2025 | -1.55 | -0.57% | 0.603348 |
| information_30 | 2023 | +3.86 | +1.43% | 0.634338 |
| information_30 | 2024 | +17.65 | +6.51% | 0.581496 |
| information_30 | 2025 | -3.75 | -1.38% | 0.603954 |
| selected | 2023 | +3.86 | +1.43% | 0.634338 |
| selected | 2024 | +24.47 | +9.03% | 0.582514 |
| selected | 2025 | -3.85 | -1.42% | 0.603014 |

## Diagnostic slices

| Arm | Slice | Binary games | Log loss | Brier |
|---|---|---:|---:|---:|
| production | any hinge active | 121 | 0.601799 | 0.206399 |
| production | PN active | 31 | 0.589829 | 0.203295 |
| production | production >=90% | 15 | 0.083459 | 0.006678 |
| product_only | any hinge active | 121 | 0.612989 | 0.211566 |
| product_only | PN active | 31 | 0.670735 | 0.237476 |
| product_only | production >=90% | 15 | 0.090815 | 0.007918 |
| market | any hinge active | 121 | 0.604729 | 0.208731 |
| market | PN active | 31 | 0.668729 | 0.237932 |
| market | production >=90% | 15 | 0.127253 | 0.014932 |
| active_10 | any hinge active | 121 | 0.600785 | 0.206061 |
| active_10 | PN active | 31 | 0.594573 | 0.204454 |
| active_10 | production >=90% | 15 | 0.084558 | 0.006836 |
| active_30 | any hinge active | 121 | 0.600650 | 0.206011 |
| active_30 | PN active | 31 | 0.603024 | 0.207227 |
| active_30 | production >=90% | 15 | 0.085971 | 0.007059 |
| active_100 | any hinge active | 121 | 0.603041 | 0.207117 |
| active_100 | PN active | 31 | 0.622826 | 0.215602 |
| active_100 | production >=90% | 15 | 0.088083 | 0.007420 |
| information_30 | any hinge active | 121 | 0.606661 | 0.208810 |
| information_30 | PN active | 31 | 0.642568 | 0.224630 |
| information_30 | production >=90% | 15 | 0.089330 | 0.007639 |
| selected | any hinge active | 121 | 0.607562 | 0.208622 |
| selected | PN active | 31 | 0.628836 | 0.218383 |
| selected | production >=90% | 15 | 0.087760 | 0.007408 |

## Current SF at SEA counterfactual

Probabilities are Seattle/home; joint prior-week refits at archived inputs. Not new forward snapshots.

- archived_probability: 93.90%
- production: 93.90%
- product_only: 74.96%
- active_10: 93.11%
- active_30: 91.68%
- active_100: 88.04%
- information_30: 84.69%

## Reproduction and limits

Historical max probability error vs committed production: 1.03e-10.
Current max probability error vs archived production: 3.3306690738754696e-16.
Production >=90% slice: 15 wins from 15 games; small exposed sample, not confirmation of calibrated tail probabilities.
Full timing/support audit and input/source hashes accompany this report. Historical input revisions can affect reproduction.
Shrinking coefficients does not bound an extreme current input or independently validate 94% confidence. Intervals omit model-design selection uncertainty.
Production and its ledger were not modified. Run: `python research/context_shrinkage.py`.
