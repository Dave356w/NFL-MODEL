# Test 60: a departure-calibrated challenger to production

Protocol: [CHALLENGER.md](../CHALLENGER.md), committed and pushed (`842f1ec`) before any arm was scored. Diagnostic only; production and the ledger are unchanged. Every basis was exposed earlier (see protocol).

Reproduction: P vs published v1.19 model_wp 2021-25 2.4e-15, penalty inversion vs unpenalized fit 2021-25 2.4e-15, 2026 re-penalized vs published model_wp 1.1e-16, spread price file: line/result mismatches 0, spread price file: games without prices 0, P map vs published fixed_band_spread 2023-26 0.0e+00.

**Challenge (better than production in all 26 cells): not met.** C is better in 11, worse in 15 and tied in 0; reliably better (z ≥ 1.96) in 0, reliably worse in 0. Primary verdict (log loss): **forward candidate**.

## Scorecard: arm minus production (± 1 SE; z in the arm's favour)

| Measure | Basis | C challenger − P | | M market only − P |
|---|---|---|---|---|
| log loss (×1000) | 2015-16 | -0.54 ± 0.70 (z +0.8) | better | -1.17 ± 1.67 (z +0.7) |
| Brier (×1000) | 2015-16 | -0.19 ± 0.33 (z +0.6) | better | -0.39 ± 0.76 (z +0.5) |
| calibration error (points) | 2015-16 | -0.45 ± 0.78 (z +0.6) | better | -0.80 ± 1.21 (z +0.7) |
| moneyline units (u) | 2015-16 | -4.7 ± 4.8 (z -1.0) | worse | -7.0 ± 6.5 (z -1.1) |
| log loss (×1000) | 2017-22 | -0.23 ± 0.58 (z +0.4) | better | +0.04 ± 1.24 (z -0.0) |
| Brier (×1000) | 2017-22 | -0.06 ± 0.27 (z +0.2) | better | +0.11 ± 0.57 (z -0.2) |
| calibration error (points) | 2017-22 | +0.30 ± 0.47 (z -0.6) | worse | +0.49 ± 0.63 (z -0.8) |
| moneyline units (u) | 2017-22 | -10.4 ± 12.0 (z -0.9) | worse | -10.8 ± 15.3 (z -0.7) |
| log loss (×1000) | 2023-25 | +0.66 ± 1.05 (z -0.6) | worse | +3.06 ± 2.23 (z -1.4) |
| Brier (×1000) | 2023-25 | +0.31 ± 0.50 (z -0.6) | worse | +1.50 ± 1.05 (z -1.4) |
| calibration error (points) | 2023-25 | -0.06 ± 0.59 (z +0.1) | better | -1.19 ± 0.99 (z +1.2) |
| moneyline units (u) | 2023-25 | -1.7 ± 7.7 (z -0.2) | worse | -17.1 ± 11.5 (z -1.5) |
| log loss (×1000) | 2026 wk1-8 | -1.62 ± 3.06 (z +0.5) | better | -2.65 ± 9.36 (z +0.3) |
| Brier (×1000) | 2026 wk1-8 | -0.63 ± 1.36 (z +0.5) | better | -1.21 ± 4.38 (z +0.3) |
| calibration error (points) | 2026 wk1-8 | +0.68 ± 1.92 (z -0.4) | worse | -2.34 ± 2.59 (z +0.9) |
| moneyline units (u) | 2026 wk1-8 | +1.6 ± 1.5 (z +1.1) | better | -2.9 ± 5.5 (z -0.5) |
| ATS units at -110 (u) | 2016-22 | -22.9 ± 26.5 (z -0.9) | worse | -40.1 ± 37.3 (z -1.1) |
| ATS units at actual prices (u) | 2016-22 | -25.8 ± 27.0 (z -1.0) | worse | -45.1 ± 38.0 (z -1.2) |
| ATS cover rate (points) | 2016-22 | -0.68 ± 0.78 (z -0.9) | worse | -1.18 ± 1.10 (z -1.1) |
| mapped spread abs error (points) | 2016-22 | -0.003 ± 0.028 (z +0.1) | better | -0.022 ± 0.038 (z +0.6) |
| raw spread abs error (points) | 2016-22 | -0.008 ± 0.009 (z +0.9) | better | -0.002 ± 0.017 (z +0.1) |
| ATS units at -110 (u) | 2023-26 | -19.1 ± 15.3 (z -1.2) | worse | -57.3 ± 26.1 (z -2.2) |
| ATS units at actual prices (u) | 2023-26 | -19.7 ± 15.2 (z -1.3) | worse | -56.4 ± 26.1 (z -2.2) |
| ATS cover rate (points) | 2023-26 | -1.10 ± 0.88 (z -1.2) | worse | -3.29 ± 1.50 (z -2.2) |
| mapped spread abs error (points) | 2023-26 | +0.003 ± 0.035 (z -0.1) | worse | +0.100 ± 0.054 (z -1.9) |
| raw spread abs error (points) | 2023-26 | +0.023 ± 0.017 (z -1.4) | worse | +0.067 ± 0.037 (z -1.8) |

Signs: log loss, Brier, calibration error and absolute errors are arm − P (negative = arm better); units and cover rate are arm − P (positive = arm better).

## Win-probability levels

| Basis | Arm | n | Log loss | Brier | Calibration error |
|---|---|---:|---:|---:|---:|
| 2015-16 | P production | 510 | 0.64165 | 0.22564 | 3.75 pts |
| 2015-16 | C challenger | 510 | 0.64111 | 0.22546 | 3.30 pts |
| 2015-16 | M market only | 510 | 0.64049 | 0.22525 | 2.94 pts |
| 2017-22 | P production | 1559 | 0.60542 | 0.20893 | 3.12 pts |
| 2017-22 | C challenger | 1559 | 0.60520 | 0.20887 | 3.43 pts |
| 2017-22 | M market only | 1559 | 0.60546 | 0.20904 | 3.62 pts |
| 2023-25 | P production | 815 | 0.60501 | 0.20883 | 4.29 pts |
| 2023-25 | C challenger | 815 | 0.60568 | 0.20915 | 4.23 pts |
| 2023-25 | M market only | 815 | 0.60807 | 0.21033 | 3.11 pts |
| 2026 wk1-8 | P production | 120 | 0.65059 | 0.22823 | 7.60 pts |
| 2026 wk1-8 | C challenger | 120 | 0.64897 | 0.22760 | 8.29 pts |
| 2026 wk1-8 | M market only | 120 | 0.64794 | 0.22702 | 5.26 pts |

## Moneyline flat 1u (legacy basis, same bets)

| Basis | Arm | Bets | Units | ROI ± SE | Market-correct null | Same-row favorite | Picks against the market favorite |
|---|---|---:|---:|---:|---:|---:|---:|
| 2015-16 | P production | 507 | -19.0 | -3.7% ± 3.3 | -2.4% | -26.0u | 13 |
| 2015-16 | C challenger | 507 | -23.7 | -4.7% ± 3.3 | -2.4% | -26.0u | 7 |
| 2015-16 | M market only | 507 | -26.0 | -5.1% ± 3.3 | -2.4% | -26.0u | 0 |
| 2017-22 | P production | 1559 | -48.4 | -3.1% ± 1.8 | -2.6% | -59.2u | 63 |
| 2017-22 | C challenger | 1559 | -58.8 | -3.8% ± 1.8 | -2.6% | -59.2u | 27 |
| 2017-22 | M market only | 1559 | -59.2 | -3.8% ± 1.8 | -2.6% | -59.2u | 0 |
| 2023-25 | P production | 812 | +17.3 | +2.1% ± 2.5 | -4.1% | +0.2u | 37 |
| 2023-25 | C challenger | 812 | +15.7 | +1.9% ± 2.5 | -4.1% | +0.2u | 22 |
| 2023-25 | M market only | 812 | +0.2 | +0.0% ± 2.5 | -4.1% | +0.2u | 0 |
| 2026 wk1-8 | P production | 121 | -0.7 | -0.6% ± 6.7 | -4.1% | -3.6u | 9 |
| 2026 wk1-8 | C challenger | 121 | +0.9 | +0.7% ± 6.7 | -4.1% | -3.6u | 8 |
| 2026 wk1-8 | M market only | 121 | -3.6 | -3.0% ± 6.6 | -4.1% | -3.6u | 0 |

## ATS, flat 1u (same rows for every arm; each arm uses map policy v2 on its own spreads)

Break-even cover rate 52.4% at −110. ROI SE has pushes in the denominator.

| Basis | Arm | W-L-P | Skips | Units −110 | ROI −110 ± SE | Units at price | ROI at price ± SE | Cover | Underdog share | Flips vs P | MAE mapped | MAE raw |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2016-22 | P production | 920-856-46 | 0 | -19.6 | -1.1% ± 2.2 | +13.3 | +0.7% ± 2.3 | 51.8% | 54% | 0 | 9.919 | 9.823 |
| 2016-22 | C challenger | 908-868-46 | 0 | -42.5 | -2.3% ± 2.2 | -12.5 | -0.7% ± 2.2 | 51.1% | 56% | 210 | 9.916 | 9.815 |
| 2016-22 | M market only | 899-877-46 | 0 | -59.7 | -3.3% ± 2.2 | -31.8 | -1.7% ± 2.2 | 50.6% | 55% | 356 | 9.897 | 9.822 |
| 2016-22 | always favorite | 843-929-46 | 4 | -162.6 | -8.9% ± 2.2 | -119.5 | -6.6% ± 2.3 | 47.6% | 0% | 988 |  |  |
| 2016-22 | always home | 862-914-46 | 0 | -130.4 | -7.2% ± 2.2 | -94.8 | -5.2% ± 2.3 | 48.5% | 38% | 998 |  |  |
| 2023-26 | P production | 524-388-25 | 0 | +88.4 | +9.4% ± 3.0 | +87.5 | +9.3% ± 3.0 | 57.5% | 37% | 0 | 9.685 | 9.701 |
| 2023-26 | C challenger | 514-398-25 | 0 | +69.3 | +7.4% ± 3.1 | +67.9 | +7.2% ± 3.1 | 56.4% | 37% | 68 | 9.688 | 9.724 |
| 2023-26 | M market only | 494-418-25 | 0 | +31.1 | +3.3% ± 3.1 | +31.2 | +3.3% ± 3.1 | 54.2% | 40% | 193 | 9.785 | 9.768 |
| 2023-26 | always favorite | 467-445-25 | 0 | -20.5 | -2.2% ± 3.1 | -21.7 | -2.3% ± 3.1 | 51.2% | 0% | 345 |  |  |
| 2023-26 | always home | 452-460-25 | 0 | -49.1 | -5.2% ± 3.1 | -48.3 | -5.2% ± 3.1 | 49.6% | 40% | 511 |  |  |

Prices assumed at −110: 2016-22 P production 0, 2023-26 P production 0.

## C's departure weight α (1 = production)

| Season | First week | Last week | Min | Max | SE at last week |
|---|---:|---:|---:|---:|---:|
| 2015 | 0.675 | 0.511 | 0.511 | 0.693 | 0.452 |
| 2016 | 0.545 | 0.613 | 0.526 | 0.613 | 0.424 |
| 2017 | 0.540 | 0.391 | 0.376 | 0.637 | 0.397 |
| 2018 | 0.405 | 0.567 | 0.383 | 0.636 | 0.358 |
| 2019 | 0.542 | 0.546 | 0.517 | 0.607 | 0.347 |
| 2020 | 0.568 | 0.529 | 0.522 | 0.572 | 0.342 |
| 2021 | 0.534 | 0.526 | 0.482 | 0.558 | 0.318 |
| 2022 | 0.524 | 0.512 | 0.474 | 0.552 | 0.306 |
| 2023 | 0.525 | 0.486 | 0.415 | 0.535 | 0.272 |
| 2024 | 0.487 | 0.582 | 0.450 | 0.615 | 0.264 |
| 2025 | 0.578 | 0.673 | 0.575 | 0.673 | 0.255 |
| 2026 | 0.677 | 0.660 | 0.641 | 0.729 | 0.246 |

## Log loss by season

| Season | n | P | C | M |
|---|---:|---:|---:|---:|
| 2015 | 256 | 0.65446 | 0.65351 | 0.65213 |
| 2016 | 254 | 0.62875 | 0.62862 | 0.62875 |
| 2017 | 255 | 0.58996 | 0.58813 | 0.58670 |
| 2018 | 254 | 0.60742 | 0.60895 | 0.61115 |
| 2019 | 255 | 0.61268 | 0.61299 | 0.61360 |
| 2020 | 255 | 0.59113 | 0.59060 | 0.59006 |
| 2021 | 271 | 0.62176 | 0.62118 | 0.62156 |
| 2022 | 269 | 0.60842 | 0.60818 | 0.60855 |
| 2023 | 272 | 0.62895 | 0.62718 | 0.62735 |
| 2024 | 272 | 0.58270 | 0.58462 | 0.58749 |
| 2025 | 271 | 0.60338 | 0.60523 | 0.60938 |
| 2026 | 120 | 0.65059 | 0.64897 | 0.64794 |
