# Test 33: explosive-play rates added to v1.16

Basis: Walk-forward development (fixed recipe); not forward evidence. v1.16 reproduction error 1e-10.

## held-out 2023-25

812 common priced flat 1u bets; 815 binary games.

| Arm | W-L-P | Units | ROI ± SE | Market-correct null | LL | LL with v1.18 penalty | Brier |
|---|---|---:|---:|---:|---:|---:|---:|
| production | 565-246-1 | +29.06 | +3.6% ± 2.5 | -4.1% | 0.60561 | 0.60641 | 0.20899 |
| explosive | 562-249-1 | +22.37 | +2.8% ± 2.5 | -4.1% | 0.60657 | 0.60724 | 0.20939 |
| market favorite (same rows) | 555-256-1 | +0.18 | +0.0% ± 2.5 | -4.1% | 0.60807 |  | 0.21033 |

explosive − production: LL gain -0.00096 ± 0.00079 (95% week-clustered [-0.00263, +0.00063]); with the v1.18 penalty -0.00083 [-0.00201, +0.00033]; ROI -0.82 pts ± 0.76 [-2.32, +0.62]; sides flipped 9.

## walk-forward 2021-22

542 common priced flat 1u bets; 540 binary games.

| Arm | W-L-P | Units | ROI ± SE | Market-correct null | LL | LL with v1.18 penalty | Brier |
|---|---|---:|---:|---:|---:|---:|---:|
| production | 350-189-3 | -23.80 | -4.4% ± 3.1 | -2.7% | 0.62735 | 0.62033 | 0.21881 |
| explosive | 350-189-3 | -22.40 | -4.1% ± 3.2 | -2.7% | 0.62732 | 0.62102 | 0.21896 |
| market favorite (same rows) | 345-194-3 | -40.03 | -7.4% ± 3.1 | -2.7% | 0.61508 |  | 0.21386 |

explosive − production: LL gain +0.00003 ± 0.00197 (95% week-clustered [-0.00325, +0.00332]); with the v1.18 penalty -0.00068 [-0.00314, +0.00184]; ROI +0.26 pts ± 1.27 [-2.30, +3.22]; sides flipped 10.

## 2026 so far (diagnostic)

65 common priced flat 1u bets; 65 binary games.

| Arm | W-L-P | Units | ROI ± SE | Market-correct null | LL | LL with v1.18 penalty | Brier |
|---|---|---:|---:|---:|---:|---:|---:|
| production | 40-25-0 | -5.20 | -8.0% ± 9.4 | -4.1% | 0.68467 | 0.68231 | 0.24385 |
| explosive | 40-25-0 | -5.20 | -8.0% ± 9.4 | -4.1% | 0.68721 | 0.68312 | 0.24513 |
| market favorite (same rows) | 41-24-0 | -4.05 | -6.2% ± 9.2 | -4.1% | 0.66627 |  | 0.23591 |

explosive − production: LL gain -0.00254 ± 0.00193 (95% week-clustered [-0.00759, +0.00408]); with the v1.18 penalty -0.00081 [-0.00500, +0.00405]; ROI +0.00 pts ± 0.00 [+0.00, +0.00]; sides flipped 0.

## Explosive coefficients (weekly refits 2021-26)

| Feature | Median | Share positive |
|---|---:|---:|
| d__for__explosive__explosive_pass_rate | -0.0448 | 31% |
| d__for__explosive__explosive_rush_rate | -0.0415 | 14% |
| d__allowed__explosive__explosive_pass_rate | +0.0018 | 57% |
| d__allowed__explosive__explosive_rush_rate | -0.0427 | 2% |

Correlation with the matching main feature (difference scale): for_pass_vs_net_pass_ypp +0.83, for_rush_vs_rush_ypa +0.82, allowed_pass_vs_net_pass_ypp +0.75, allowed_rush_vs_rush_ypa +0.77.
