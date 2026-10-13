# Margin-likelihood v1.16: 2017–2020 out of sample

Protocol: `research/MARGIN_LIKELIHOOD.md` (committed before this run). Held-out reconstruction; 2017–2020 were scored once before for v1.16, so this is not forward evidence.

**Verdict: falsified.** Log-loss gain over v1.16 +0.000895 [-0.005609, +0.007677]; change in units vs the favorite -13.39u.

1017 flat 1u bets; 1019 binary games. v1.16 reproduction max error 1.11e-16.

| Arm | W-L-P | Units | ROI ± SE | Null | Units vs favorite | Underdog picks | Their units | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| production | 691-322-4 | -0.42 | -0.04% ± 2.23 | -2.55% | +18.76 | 49 | +9.46 | 0.605604 | 0.208494 |
| margin_likelihood | 686-327-4 | -13.81 | -1.36% ± 2.21 | -2.55% | +5.37 | 38 | +1.96 | 0.604709 | 0.208185 |
| market | 685-328-4 | -19.18 | -1.89% ± 2.20 | -2.55% | +0.00 | 0 | +0.00 | 0.600368 | 0.206481 |

Challenger log-loss gain vs market: -0.004341 [-0.010811, +0.001936].

## By season

| Season | LL gain vs v1.16 | Units vs favorite change | Challenger ROI | v1.16 ROI |
|---|---:|---:|---:|---:|
| 2017 | +0.003828 | -3.16 | +7.51% | +8.76% |
| 2018 | -0.001330 | -3.67 | -3.57% | -2.13% |
| 2019 | +0.004500 | -4.29 | -9.09% | -7.40% |
| 2020 | -0.003428 | -2.27 | -0.26% | +0.63% |

## Fitted shape (strictly earlier seasons)

| Season | σ | w(0) | w(3) | w(7) | w(10) |
|---|---:|---:|---:|---:|---:|
| 2017 | 13.03 | 0.16 | 2.42 | 1.74 | 1.14 |
| 2018 | 13.05 | 0.13 | 2.55 | 1.66 | 1.18 |
| 2019 | 13.08 | 0.11 | 2.66 | 1.72 | 1.12 |
| 2020 | 13.09 | 0.10 | 2.57 | 1.84 | 1.14 |
