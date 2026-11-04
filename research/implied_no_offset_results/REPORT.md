# Test 52: implied points as fitted features, no moneyline offset

Protocol: [IMPLIED_NO_OFFSET.md](../IMPLIED_NO_OFFSET.md), committed (`5e912a4`) before any arm was scored. Diagnostic only; production v1.19 and the ledger are unchanged.

Reproduction: v1.19 retro_ledger 2021-25 2.4e-15, Test 50 S3 2014-20 (6-digit CSV) 5.0e-07, fixed_band_spread 2023-25 0.0e+00, research fit copy vs P (offset on) 2.2e-16.

## Log loss (arm minus v1.19, x1000; negative = arm better; bar |z| >= 2.24)

| Arm | 2015-16 | 2017-22 | 2023-25 | Verdict |
|---|---:|---:|---:|---|
| C core + implied, no offset | +4.08 ± 3.77 (z +1.1, n 510) | +6.89 ± 2.15 (z +3.2, n 1559) | +3.28 ± 2.55 (z +1.3, n 815) | stop |
| C0 implied only, no offset | +0.83 ± 3.79 (z +0.2, n 510) | +7.14 ± 2.87 (z +2.5, n 1559) | +10.07 ± 3.80 (z +2.6, n 815) | stop |

## Against the no-vig moneyline alone (model minus market, x1000; negative = beats the market)

| Model | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| P | +1.17 ± 1.67 | -0.04 ± 1.24 | -3.06 ± 2.23 |
| C core + implied, no offset | +5.25 ± 4.56 | +6.85 ± 2.75 | +0.22 ± 3.48 |
| C0 implied only, no offset | +2.00 ± 3.88 | +7.10 ± 2.60 | +7.01 ± 3.32 |

Market log loss per game: 2015-16 0.64049, 2017-22 0.60546, 2023-25 0.60807.

## Implied-point coefficients in the last fit of each basis (log-odds per point)

| Basis | Arm | Home implied | Away implied | Site (scaled) |
|---|---|---:|---:|---:|
| 2015-16 | C core + implied, no offset | +0.0717 | -0.1032 | +0.087 |
| 2015-16 | C0 implied only, no offset | +0.0850 | -0.1165 | +0.048 |
| 2017-22 | C core + implied, no offset | +0.0730 | -0.0824 | +0.040 |
| 2017-22 | C0 implied only, no offset | +0.0961 | -0.1032 | -0.003 |
| 2023-25 | C core + implied, no offset | +0.0826 | -0.0928 | +0.025 |
| 2023-25 | C0 implied only, no offset | +0.1039 | -0.1122 | -0.013 |

## ATS, flat 1u at -110 (same rows for every arm; each arm uses its own prior-season median map)

Break-even cover rate 52.4%. ROI SE has pushes in the denominator. Flips and flip units are against v1.19 in the same view.

| Basis | Arm | View | W-L-P | Skips | Units | ROI ± SE | Cover | Flips | Units on flips (arm − P) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2015-16 | P | median map | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% |  |  |
| 2015-16 | P | raw spread | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% |  |  |
| 2015-16 | always favorite | baseline | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% |  |  |
| 2015-16 | always home | baseline | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% |  |  |
| 2015-16 | C core + implied, no offset | median map | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | 0 | +0.0 |
| 2015-16 | C core + implied, no offset | raw spread | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | 0 | +0.0 |
| 2015-16 | C0 implied only, no offset | median map | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | 0 | +0.0 |
| 2015-16 | C0 implied only, no offset | raw spread | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | 0 | +0.0 |
| 2015-16 | P | raw spread, all rows (supplementary) | 233-266-13 | 0 | -54.2 | -10.6% ± 4.2 | 46.7% |  |  |
| 2015-16 | C core + implied, no offset | raw spread, all rows (supplementary) | 246-253-13 | 0 | -29.4 | -5.7% ± 4.2 | 49.3% | 227 | +24.8 |
| 2015-16 | C0 implied only, no offset | raw spread, all rows (supplementary) | 250-249-13 | 0 | -21.7 | -4.2% ± 4.2 | 50.1% | 278 | +32.5 |
| 2015-16 | always favorite | baseline, all rows (supplementary) | 242-256-13 | 1 | -36.0 | -7.0% ± 4.2 | 48.6% |  |  |
| 2015-16 | always home | baseline, all rows (supplementary) | 237-262-13 | 0 | -46.5 | -9.1% ± 4.2 | 47.5% |  |  |
| 2017-22 | P | median map | 610-668-33 | 0 | -113.5 | -8.7% ± 2.6 | 47.7% |  |  |
| 2017-22 | P | raw spread | 632-646-33 | 0 | -71.5 | -5.5% ± 2.6 | 49.5% |  |  |
| 2017-22 | always favorite | baseline | 584-694-33 | 0 | -163.1 | -12.4% ± 2.6 | 45.7% |  |  |
| 2017-22 | always home | baseline | 610-668-33 | 0 | -113.5 | -8.7% ± 2.6 | 47.7% |  |  |
| 2017-22 | C core + implied, no offset | median map | 647-631-33 | 0 | -42.8 | -3.3% ± 2.6 | 50.6% | 365 | +70.6 |
| 2017-22 | C core + implied, no offset | raw spread | 668-610-33 | 0 | -2.7 | -0.2% ± 2.6 | 52.3% | 483 | +68.7 |
| 2017-22 | C0 implied only, no offset | median map | 627-651-33 | 0 | -81.0 | -6.2% ± 2.6 | 49.1% | 506 | +32.5 |
| 2017-22 | C0 implied only, no offset | raw spread | 686-592-33 | 0 | +31.6 | +2.4% ± 2.6 | 53.7% | 623 | +103.1 |
| 2017-22 | P | raw spread, all rows (supplementary) | 766-759-41 | 0 | -62.6 | -4.0% ± 2.4 | 50.2% |  |  |
| 2017-22 | C core + implied, no offset | raw spread, all rows (supplementary) | 797-728-41 | 0 | -3.5 | -0.2% ± 2.4 | 52.3% | 590 | +59.2 |
| 2017-22 | C0 implied only, no offset | raw spread, all rows (supplementary) | 806-719-41 | 0 | +13.7 | +0.9% ± 2.4 | 52.9% | 754 | +76.4 |
| 2017-22 | always favorite | baseline, all rows (supplementary) | 715-807-41 | 3 | -157.0 | -10.0% ± 2.4 | 47.0% |  |  |
| 2017-22 | always home | baseline, all rows (supplementary) | 739-786-41 | 0 | -114.2 | -7.3% ± 2.4 | 48.5% |  |  |
| 2023-25 | P | median map | 422-375-19 | 0 | +8.6 | +1.1% ± 3.3 | 52.9% |  |  |
| 2023-25 | P | raw spread | 396-401-19 | 0 | -41.0 | -5.0% ± 3.3 | 49.7% |  |  |
| 2023-25 | always favorite | baseline | 411-386-19 | 0 | -12.4 | -1.5% ± 3.3 | 51.6% |  |  |
| 2023-25 | always home | baseline | 400-397-19 | 0 | -33.4 | -4.1% ± 3.3 | 50.2% |  |  |
| 2023-25 | C core + implied, no offset | median map | 436-361-19 | 0 | +35.4 | +4.3% ± 3.3 | 54.7% | 314 | +26.7 |
| 2023-25 | C core + implied, no offset | raw spread | 417-380-19 | 0 | -0.9 | -0.1% ± 3.3 | 52.3% | 317 | +40.1 |
| 2023-25 | C0 implied only, no offset | median map | 408-389-19 | 0 | -18.1 | -2.2% ± 3.3 | 51.2% | 368 | -26.7 |
| 2023-25 | C0 implied only, no offset | raw spread | 394-403-19 | 0 | -44.8 | -5.5% ± 3.3 | 49.4% | 468 | -3.8 |
| 2023-25 | P | raw spread, all rows (supplementary) | 396-401-19 | 0 | -41.0 | -5.0% ± 3.3 | 49.7% |  |  |
| 2023-25 | C core + implied, no offset | raw spread, all rows (supplementary) | 417-380-19 | 0 | -0.9 | -0.1% ± 3.3 | 52.3% | 317 | +40.1 |
| 2023-25 | C0 implied only, no offset | raw spread, all rows (supplementary) | 394-403-19 | 0 | -44.8 | -5.5% ± 3.3 | 49.4% | 468 | -3.8 |
| 2023-25 | always favorite | baseline, all rows (supplementary) | 411-386-19 | 0 | -12.4 | -1.5% ± 3.3 | 51.6% |  |  |
| 2023-25 | always home | baseline, all rows (supplementary) | 400-397-19 | 0 | -33.4 | -4.1% ± 3.3 | 50.2% |  |  |
| 2023-25 | P | median map, 2021+ history (supplementary) | 294-245-5 | 0 | +22.3 | +4.1% ± 4.1 | 54.5% |  |  |
| 2023-25 | C core + implied, no offset | median map, 2021+ history (supplementary) | 298-241-5 | 0 | +29.9 | +5.5% ± 4.1 | 55.3% | 171 | +7.6 |
| 2023-25 | C0 implied only, no offset | median map, 2021+ history (supplementary) | 276-263-5 | 0 | -12.1 | -2.2% ± 4.1 | 51.2% | 211 | -34.4 |

## Moneyline flat units (legacy, same bets)

| Basis | Arm | Bets | v1.19 | Arm |
|---|---|---:|---:|---:|
| 2015-16 | C core + implied, no offset | 512 | -18.1 | -23.5 |
| 2015-16 | C0 implied only, no offset | 512 | -18.1 | -24.8 |
| 2017-22 | C core + implied, no offset | 1566 | -45.6 | -16.3 |
| 2017-22 | C0 implied only, no offset | 1566 | -45.6 | -47.0 |
| 2023-25 | C core + implied, no offset | 816 | +19.1 | +24.7 |
| 2023-25 | C0 implied only, no offset | 816 | +19.1 | -1.7 |
