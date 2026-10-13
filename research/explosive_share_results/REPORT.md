# Test 34: explosive share of offensive yardage, 2017–2020

Protocol: [EXPLOSIVE_SHARE.md](../EXPLOSIVE_SHARE.md), pushed before any number existed. Basis: One-time 2017-2020 out-of-sample reconstruction (exposure disclosed in EXPLOSIVE_SHARE.md); not forward evidence.
v1.16 reproduction error 2.2e-16. **Verdict: unresolved.**

1017 common priced flat 1u bets; 1019 binary games.

| Arm | W-L-P | Units | ROI ± SE | Market-correct null | LL | Brier |
|---|---|---:|---:|---:|---:|---:|
| production | 691-322-4 | -0.42 | -0.0% ± 2.2 | -2.6% | 0.60560 | 0.20849 |
| explosive_share | 689-324-4 | -3.66 | -0.4% ± 2.2 | -2.6% | 0.60551 | 0.20858 |
| market favorite (same rows) | 685-328-4 | -19.18 | -1.9% ± 2.2 | -2.6% | 0.60037 | 0.20648 |

explosive_share − production: LL gain +0.00009 ± 0.00086 (95% week-clustered [-0.00142, +0.00163]); ROI -0.32 pts ± 0.78 [-1.71, +1.05]; sides flipped 16.

Coefficient: median -0.0697, negative in 100% of 68 weekly fits. Correlation with the offense net-yards-per-pass-play difference +0.34; league explosive share of net yards 42.5%.

| Season | Bets | v1.16 units | + share units | Favorite units | LL gain |
|---|---:|---:|---:|---:|---:|
| 2017 | 253 | +22.17 | +18.44 | +14.05 | -0.00068 |
| 2018 | 254 | -5.41 | -9.49 | -8.11 | +0.00016 |
| 2019 | 254 | -18.78 | -14.35 | -19.78 | +0.00078 |
| 2020 | 256 | +1.61 | +1.75 | -5.35 | +0.00010 |
