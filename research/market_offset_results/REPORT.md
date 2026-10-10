# Market starting point ablation

Only difference: the market-logit offset is removed and all coefficients are refitted. Same features, scaling, training rows and penalties.

Basis: Exposed historical development; fixed recipe, weekly prior-game refits. Not native forward evidence.

812 common flat 1u bets; 815 binary proper scores.

| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|
| with_market | 565-246-1 | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605605 | 0.208989 |
| without_market | 544-267-1 | +19.01 | +2.34% ± 2.72 | -4.10% | 0.625832 | 0.217275 |
| market_only | 555-256-1 | +0.18 | +0.02% ± 2.47 | -4.10% | 0.608072 | 0.210334 |

## Paired differences

Positive values favor retaining the market offset. Intervals are 95% week-cluster bootstrap.

| Comparator | ROI gain [CI], pp | LL gain [CI] | Brier gain [CI] | Side flips |
|---|---:|---:|---:|---:|
| without_market | +1.24 [-3.45, +5.79] | +0.020226 [+0.010003, +0.030187] | +0.008286 [+0.004107, +0.012385] | 106 |
| market_only | +3.56 [+0.46, +6.65] | +0.002467 [-0.005517, +0.010503] | +0.001346 [-0.002259, +0.004877] | 42 |

## Annual results

| Arm | Season | Units | ROI | Log loss |
|---|---:|---:|---:|---:|
| with_market | 2023 | +8.44 | +3.12% | 0.630814 |
| with_market | 2024 | +24.47 | +9.03% | 0.583169 |
| with_market | 2025 | -3.85 | -1.42% | 0.602822 |
| without_market | 2023 | -15.96 | -5.91% | 0.652173 |
| without_market | 2024 | +34.49 | +12.73% | 0.608618 |
| without_market | 2025 | +0.48 | +0.18% | 0.616670 |
| market_only | 2023 | +4.12 | +1.53% | 0.627349 |
| market_only | 2024 | +14.11 | +5.21% | 0.587489 |
| market_only | 2025 | -18.05 | -6.66% | 0.609383 |

## Archived SF at SEA counterfactual

Seattle/home probabilities; earlier-week refits at archived inputs, not new snapshots.

- with_market: 93.90%
- without_market: 93.69%
- market_only: 59.34%

## Checks and interpretation

Historical maximum production reproduction error: 1.03e-10.
Archived current maximum reproduction error: 3.33e-16.
All 108 fits used strictly earlier weeks. Excluded bets: 2023_02_IND_HOU, 2023_03_LAC_MIN, 2024_11_CIN_LAC, 2025_10_PHI_GB.
The ablation removes the direct market starting point, not all information correlated with prices. No new intercept or retuned penalties were added.
The effect is conditional on the existing frozen recipe. Model design used these seasons; bootstrap intervals omit that selection uncertainty.
Production and forward snapshots are unchanged. Run: `python research/market_offset_ablation.py`.
