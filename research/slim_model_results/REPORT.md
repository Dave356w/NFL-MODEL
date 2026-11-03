# Test 50: slim models from the fit analysis

Protocol: [SLIM_MODEL.md](../SLIM_MODEL.md), committed (`4b11376`) before any arm was scored. Diagnostic only; production v1.18 and the ledger are unchanged. All bases were exposed before the arms were chosen.

Reproduction of published forecasts by P: 2017-20 1.1e-16, 2021-22 2.3e-13, 2023-25 1.1e-16, fixed_band_spread 2023-25 0.0e+00.

## Log loss (arm minus v1.18, x1000; negative = slim arm better; bar |z| >= 2.39)

| Arm | Terms | 2015-16 | 2017-22 | 2023-25 | Verdict |
|---|---:|---:|---:|---:|---|
| S1 trim | 22 | +0.48 ± 1.72 (z +0.3, n 510) | -0.78 ± 0.83 (z -0.9, n 1559) | -1.11 ± 0.86 (z -1.3, n 815) | forward candidate |
| S2 trim + one INT term | 21 | +0.11 ± 1.73 (z +0.1, n 510) | -0.63 ± 0.91 (z -0.7, n 1559) | -1.30 ± 0.82 (z -1.6, n 815) | forward candidate |
| S3 core | 10 | +1.22 ± 3.39 (z +0.4, n 510) | -2.68 ± 1.15 (z -2.3, n 1559) | -1.40 ± 1.38 (z -1.0, n 815) | unresolved |

v1.18 log loss per game: 2015-16 0.64044, 2017-22 0.60811, 2023-25 0.60641. S3 verdict counts 2015-16 only (protocol).

## ATS, flat 1u at -110 (same rows for every arm; each arm uses its own prior-season median map)

Break-even cover rate 52.4%. ROI SE has pushes in the denominator. Flips and flip units are against v1.18 in the same view.

| Basis | Arm | View | W-L-P | Skips | Units | ROI ± SE | Cover | Flips | Units on flips (arm − P) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2015-16 | P | median map | 130-121-5 | 0 | -2.8 | -1.1% ± 5.9 | 51.8% |  |  |
| 2015-16 | P | raw spread | 115-136-5 | 0 | -31.5 | -12.3% ± 5.9 | 45.8% |  |  |
| 2015-16 | always favorite | baseline | 128-122-5 | 1 | -5.6 | -2.2% ± 5.9 | 51.2% |  |  |
| 2015-16 | always home | baseline | 123-128-5 | 0 | -16.2 | -6.3% ± 5.9 | 49.0% |  |  |
| 2015-16 | S1 trim | median map | 127-124-5 | 0 | -8.5 | -3.3% ± 5.9 | 50.6% | 43 | -5.7 |
| 2015-16 | S1 trim | raw spread | 112-139-5 | 0 | -37.2 | -14.5% ± 5.9 | 44.6% | 21 | -5.7 |
| 2015-16 | S2 trim + one INT term | median map | 129-122-5 | 0 | -4.7 | -1.8% ± 5.9 | 51.4% | 65 | -1.9 |
| 2015-16 | S2 trim + one INT term | raw spread | 111-140-5 | 0 | -39.1 | -15.3% ± 5.9 | 44.2% | 22 | -7.6 |
| 2015-16 | S3 core | median map | 139-112-5 | 0 | +14.4 | +5.6% ± 5.9 | 55.4% | 35 | +17.2 |
| 2015-16 | S3 core | raw spread | 123-128-5 | 0 | -16.2 | -6.3% ± 5.9 | 49.0% | 52 | +15.3 |
| 2017-22 | P | median map | 762-763-41 | 0 | -70.3 | -4.5% ± 2.4 | 50.0% |  |  |
| 2017-22 | P | raw spread | 747-778-41 | 0 | -98.9 | -6.3% ± 2.4 | 49.0% |  |  |
| 2017-22 | always favorite | baseline | 715-807-41 | 3 | -157.0 | -10.0% ± 2.4 | 47.0% |  |  |
| 2017-22 | always home | baseline | 739-786-41 | 0 | -114.2 | -7.3% ± 2.4 | 48.5% |  |  |
| 2017-22 | S1 trim | median map | 761-764-41 | 0 | -72.2 | -4.6% ± 2.4 | 49.9% | 210 | -1.9 |
| 2017-22 | S1 trim | raw spread | 761-764-41 | 0 | -72.2 | -4.6% ± 2.4 | 49.9% | 155 | +26.7 |
| 2017-22 | S2 trim + one INT term | median map | 775-750-41 | 0 | -45.5 | -2.9% ± 2.4 | 50.8% | 269 | +24.8 |
| 2017-22 | S2 trim + one INT term | raw spread | 768-757-41 | 0 | -58.8 | -3.8% ± 2.4 | 50.4% | 171 | +40.1 |
| 2017-22 | S3 core | median map | 741-784-41 | 0 | -110.4 | -7.0% ± 2.4 | 48.6% | 336 | -40.1 |
| 2017-22 | S3 core | raw spread | 766-759-41 | 0 | -62.6 | -4.0% ± 2.4 | 50.2% | 278 | +36.3 |
| 2023-25 | P | median map | 419-378-19 | 0 | +2.9 | +0.4% ± 3.3 | 52.6% |  |  |
| 2023-25 | P | raw spread | 409-388-19 | 0 | -16.2 | -2.0% ± 3.3 | 51.3% |  |  |
| 2023-25 | always favorite | baseline | 411-386-19 | 0 | -12.4 | -1.5% ± 3.3 | 51.6% |  |  |
| 2023-25 | always home | baseline | 400-397-19 | 0 | -33.4 | -4.1% ± 3.3 | 50.2% |  |  |
| 2023-25 | S1 trim | median map | 429-368-19 | 0 | +22.0 | +2.7% ± 3.3 | 53.8% | 193 | +19.1 |
| 2023-25 | S1 trim | raw spread | 409-388-19 | 0 | -16.2 | -2.0% ± 3.3 | 51.3% | 74 | -0.0 |
| 2023-25 | S2 trim + one INT term | median map | 432-365-19 | 0 | +27.7 | +3.4% ± 3.3 | 54.2% | 195 | +24.8 |
| 2023-25 | S2 trim + one INT term | raw spread | 410-387-19 | 0 | -14.3 | -1.7% ± 3.3 | 51.4% | 74 | +1.9 |
| 2023-25 | S3 core | median map | 422-375-19 | 0 | +8.6 | +1.1% ± 3.3 | 52.9% | 157 | +5.7 |
| 2023-25 | S3 core | raw spread | 396-401-19 | 0 | -41.0 | -5.0% ± 3.3 | 49.7% | 102 | -24.8 |
| 2023-25 | P | median map, 2021+ history (supplementary) | 430-367-19 | 0 | +23.9 | +2.9% ± 3.3 | 54.0% |  |  |
| 2023-25 | S1 trim | median map, 2021+ history (supplementary) | 418-379-19 | 0 | +1.0 | +0.1% ± 3.3 | 52.4% | 148 | -22.9 |
| 2023-25 | S2 trim + one INT term | median map, 2021+ history (supplementary) | 425-372-19 | 0 | +14.4 | +1.8% ± 3.3 | 53.3% | 110 | -9.5 |
| 2023-25 | S3 core | median map, 2021+ history (supplementary) | 427-370-19 | 0 | +18.2 | +2.2% ± 3.3 | 53.6% | 158 | -5.7 |

## Moneyline flat units (legacy, same bets)

| Basis | Arm | Bets | v1.18 | Arm |
|---|---|---:|---:|---:|
| 2015-16 | S1 trim | 512 | -16.7 | -20.0 |
| 2015-16 | S2 trim + one INT term | 512 | -16.7 | -16.1 |
| 2015-16 | S3 core | 512 | -16.7 | -18.1 |
| 2017-22 | S1 trim | 1566 | -21.5 | -41.6 |
| 2017-22 | S2 trim + one INT term | 1566 | -21.5 | -47.9 |
| 2017-22 | S3 core | 1566 | -21.5 | -45.6 |
| 2023-25 | S1 trim | 816 | +28.9 | +16.1 |
| 2023-25 | S2 trim + one INT term | 816 | +28.9 | +18.7 |
| 2023-25 | S3 core | 816 | +28.9 | +19.1 |
