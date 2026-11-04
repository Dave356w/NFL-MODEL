# Test 58: market-centered ATS cover probability at actual spread prices

Protocol: [SPREAD_PRICE_PROBABILITY.md](../SPREAD_PRICE_PROBABILITY.md), committed (`d91b78a`) before any arm was scored. Diagnostic only.

Reproduction: v1.19 retro_ledger 2021-25 2.4e-15, Test 50 S3 2014-20 (6-digit CSV) 5.0e-07, fixed_band_spread 2023-25 0.0e+00, map vs fixed_bands 2016-22 0.0e+00, map vs fixed_bands 2023-26 0.0e+00.

Verdicts (bar |z| >= 2.24): A raw disagreement: unresolved, B mapped disagreement: unresolved.

## Cover log loss gain over the no-vig spread price (x1000, positive = arm better)

| Basis | Period | Arm | n | Gain | z |
|---|---|---|---:|---:|---:|
| 2016-22 | 2016-2022 | A raw disagreement | 1776 | -1.04 ± 0.62 | -1.66 |
| 2016-22 | 2016-2022 | B mapped disagreement | 1278 | -0.64 ± 0.67 | -0.95 |
| 2016-22 | 2016 | A raw disagreement | 251 | -5.29 ± 3.79 | -1.40 |
| 2016-22 | 2016 | B mapped disagreement | 0 | +nan ± nan | +nan |
| 2016-22 | 2017 | A raw disagreement | 247 | -0.59 ± 1.33 | -0.45 |
| 2016-22 | 2017 | B mapped disagreement | 0 | +nan ± nan | +nan |
| 2016-22 | 2018 | A raw disagreement | 247 | -1.13 ± 1.33 | -0.85 |
| 2016-22 | 2018 | B mapped disagreement | 247 | -1.41 ± 3.14 | -0.45 |
| 2016-22 | 2019 | A raw disagreement | 246 | +0.07 ± 0.08 | +0.83 |
| 2016-22 | 2019 | B mapped disagreement | 246 | -1.58 ± 1.34 | -1.18 |
| 2016-22 | 2020 | A raw disagreement | 256 | -0.19 ± 0.35 | -0.56 |
| 2016-22 | 2020 | B mapped disagreement | 256 | -0.02 ± 0.05 | -0.39 |
| 2016-22 | 2021 | A raw disagreement | 268 | -0.21 ± 0.49 | -0.42 |
| 2016-22 | 2021 | B mapped disagreement | 268 | +0.08 ± 0.15 | +0.54 |
| 2016-22 | 2022 | A raw disagreement | 261 | +0.01 ± 0.01 | +0.53 |
| 2016-22 | 2022 | B mapped disagreement | 261 | -0.36 ± 0.29 | -1.26 |
| 2023-26 | 2023-2026 | A raw disagreement | 912 | -0.00 ± 0.48 | -0.01 |
| 2023-26 | 2023-2026 | B mapped disagreement | 386 | +0.71 ± 1.69 | +0.42 |
| 2023-26 | 2023 | A raw disagreement | 258 | -0.03 ± 0.25 | -0.12 |
| 2023-26 | 2023 | B mapped disagreement | 0 | +nan ± nan | +nan |
| 2023-26 | 2024 | A raw disagreement | 268 | +0.01 ± 0.02 | +0.75 |
| 2023-26 | 2024 | B mapped disagreement | 0 | +nan ± nan | +nan |
| 2023-26 | 2025 | A raw disagreement | 271 | +1.35 ± 0.53 | +2.57 |
| 2023-26 | 2025 | B mapped disagreement | 271 | +0.29 ± 2.06 | +0.14 |
| 2023-26 | 2026 | A raw disagreement | 115 | -3.16 ± 3.29 | -0.96 |
| 2023-26 | 2026 | B mapped disagreement | 115 | +1.70 ± 2.89 | +0.59 |

## Fitted β (log-odds per 10 points of disagreement)

| Arm, season | β |
|---|---:|
| A raw disagreement 2016 | -1.306 |
| A raw disagreement 2017 | -0.492 |
| A raw disagreement 2018 | -0.293 |
| A raw disagreement 2019 | +0.027 |
| A raw disagreement 2020 | +0.176 |
| A raw disagreement 2021 | +0.107 |
| A raw disagreement 2022 | +0.004 |
| B mapped disagreement 2016 | — |
| B mapped disagreement 2017 | — |
| B mapped disagreement 2018 | +0.420 |
| B mapped disagreement 2019 | +0.223 |
| B mapped disagreement 2020 | +0.011 |
| B mapped disagreement 2021 | -0.028 |
| B mapped disagreement 2022 | -0.083 |
| A raw disagreement 2023 | -0.051 |
| A raw disagreement 2024 | +0.005 |
| A raw disagreement 2025 | +0.152 |
| A raw disagreement 2026 | +0.552 |
| B mapped disagreement 2023 | — |
| B mapped disagreement 2024 | — |
| B mapped disagreement 2025 | +0.387 |
| B mapped disagreement 2026 | +0.346 |

## ATS at actual prices

| Basis | Period | Rule | W-L-P | Bets | Units | ROI ± SE | Cover | Market null ROI |
|---|---|---|---|---:|---:|---:|---:|---:|
| 2016-22 | 2016-2022 | A raw disagreement | 114-132-3 | 249 | -21.9 | -8.8% ± 6.2 | 46.3% | -2.4% |
| 2016-22 | 2016-2022 | B mapped disagreement | 70-82-4 | 156 | -16.9 | -10.8% ± 7.6 | 46.1% | -2.5% |
| 2016-22 | 2016-2022 | production picks | 880-896-46 | 1822 | -65.5 | -3.6% ± 2.3 | 49.5% | -2.4% |
| 2016-22 | 2016-2022 | always favorite | 843-929-46 | 1818 | -119.5 | -6.6% ± 2.3 | 47.6% | -2.4% |
| 2016-22 | 2016-2022 | always home | 862-914-46 | 1822 | -94.8 | -5.2% ± 2.3 | 48.5% | -2.4% |
| 2016-22 | 2016 | A raw disagreement | 77-85-3 | 165 | -11.2 | -6.8% ± 7.6 | 47.5% | -2.4% |
| 2016-22 | 2016 | B mapped disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2016-22 | 2016 | production picks | 139-112-5 | 256 | +19.9 | +7.8% ± 6.0 | 55.4% | -2.4% |
| 2016-22 | 2016 | always favorite | 128-122-5 | 255 | +0.5 | +0.2% ± 6.1 | 51.2% | -2.4% |
| 2016-22 | 2016 | always home | 123-128-5 | 256 | -11.0 | -4.3% ± 6.1 | 49.0% | -2.4% |
| 2016-22 | 2017 | A raw disagreement | 30-34-0 | 64 | -4.7 | -7.3% ± 12.4 | 46.9% | -2.4% |
| 2016-22 | 2017 | B mapped disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2016-22 | 2017 | production picks | 131-116-8 | 255 | +7.2 | +2.8% ± 6.0 | 53.0% | -2.4% |
| 2016-22 | 2017 | always favorite | 131-113-8 | 252 | +12.5 | +5.0% ± 6.1 | 53.7% | -2.4% |
| 2016-22 | 2017 | always home | 129-118-8 | 255 | +5.0 | +2.0% ± 6.0 | 52.2% | -2.4% |
| 2016-22 | 2018 | A raw disagreement | 7-12-0 | 19 | -5.0 | -26.3% ± 22.8 | 36.8% | -2.5% |
| 2016-22 | 2018 | B mapped disagreement | 47-53-1 | 101 | -9.6 | -9.5% ± 9.6 | 47.0% | -2.6% |
| 2016-22 | 2018 | production picks | 114-133-9 | 256 | -25.3 | -9.9% ± 6.0 | 46.2% | -2.6% |
| 2016-22 | 2018 | always favorite | 114-133-9 | 256 | -23.2 | -9.0% ± 6.0 | 46.2% | -2.6% |
| 2016-22 | 2018 | always home | 119-128-9 | 256 | -14.8 | -5.8% ± 6.0 | 48.2% | -2.6% |
| 2016-22 | 2019 | A raw disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2016-22 | 2019 | B mapped disagreement | 23-29-3 | 55 | -7.3 | -13.3% ± 12.8 | 44.2% | -2.4% |
| 2016-22 | 2019 | production picks | 115-131-10 | 256 | -22.0 | -8.6% ± 6.0 | 46.7% | -2.4% |
| 2016-22 | 2019 | always favorite | 113-133-10 | 256 | -24.1 | -9.4% ± 6.0 | 45.9% | -2.4% |
| 2016-22 | 2019 | always home | 106-140-10 | 256 | -39.3 | -15.4% ± 5.9 | 43.1% | -2.4% |
| 2016-22 | 2020 | A raw disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2016-22 | 2020 | B mapped disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2016-22 | 2020 | production picks | 125-131-0 | 256 | -12.3 | -4.8% ± 6.1 | 48.8% | -2.4% |
| 2016-22 | 2020 | always favorite | 114-142-0 | 256 | -32.1 | -12.6% ± 6.1 | 44.5% | -2.4% |
| 2016-22 | 2020 | always home | 127-129-0 | 256 | -8.3 | -3.3% ± 6.1 | 49.6% | -2.4% |
| 2016-22 | 2021 | A raw disagreement | 0-1-0 | 1 | -1.0 | -100.0% ± nan | 0.0% | -2.3% |
| 2016-22 | 2021 | B mapped disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2016-22 | 2021 | production picks | 124-144-4 | 272 | -27.1 | -10.0% ± 5.8 | 46.3% | -2.6% |
| 2016-22 | 2021 | always favorite | 125-143-4 | 272 | -22.6 | -8.3% ± 5.9 | 46.6% | -2.6% |
| 2016-22 | 2021 | always home | 129-139-4 | 272 | -16.6 | -6.1% ± 5.9 | 48.1% | -2.6% |
| 2016-22 | 2022 | A raw disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2016-22 | 2022 | B mapped disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2016-22 | 2022 | production picks | 132-129-10 | 271 | -5.8 | -2.1% ± 5.8 | 50.6% | -2.4% |
| 2016-22 | 2022 | always favorite | 118-143-10 | 271 | -30.5 | -11.3% ± 5.8 | 45.2% | -2.4% |
| 2016-22 | 2022 | always home | 129-132-10 | 271 | -9.8 | -3.6% ± 5.8 | 49.4% | -2.4% |
| 2023-26 | 2023-2026 | A raw disagreement | 8-9-0 | 17 | -2.0 | -11.8% ± 23.4 | 47.1% | -4.5% |
| 2023-26 | 2023-2026 | B mapped disagreement | 27-25-0 | 52 | -0.8 | -1.6% ± 13.3 | 51.9% | -4.5% |
| 2023-26 | 2023-2026 | production picks | 493-419-25 | 937 | +28.6 | +3.1% ± 3.1 | 54.1% | -4.5% |
| 2023-26 | 2023-2026 | always favorite | 467-445-25 | 937 | -21.7 | -2.3% ± 3.1 | 51.2% | -4.5% |
| 2023-26 | 2023-2026 | always home | 452-460-25 | 937 | -48.3 | -5.2% ± 3.1 | 49.6% | -4.5% |
| 2023-26 | 2023 | A raw disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2023-26 | 2023 | B mapped disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2023-26 | 2023 | production picks | 133-125-14 | 272 | -3.9 | -1.4% ± 5.7 | 51.6% | -4.5% |
| 2023-26 | 2023 | always favorite | 137-121-14 | 272 | +3.0 | +1.1% ± 5.6 | 53.1% | -4.5% |
| 2023-26 | 2023 | always home | 128-130-14 | 272 | -13.5 | -4.9% ± 5.7 | 49.6% | -4.5% |
| 2023-26 | 2024 | A raw disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2023-26 | 2024 | B mapped disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2023-26 | 2024 | production picks | 143-125-4 | 272 | +5.3 | +2.0% ± 5.8 | 53.4% | -4.5% |
| 2023-26 | 2024 | always favorite | 143-125-4 | 272 | +4.7 | +1.7% ± 5.7 | 53.4% | -4.5% |
| 2023-26 | 2024 | always home | 137-131-4 | 272 | -5.6 | -2.1% ± 5.8 | 51.1% | -4.5% |
| 2023-26 | 2025 | A raw disagreement | 0-0-0 | 0 | +0.0 | +nan% ± nan | nan% | +nan% |
| 2023-26 | 2025 | B mapped disagreement | 17-19-0 | 36 | -3.8 | -10.6% ± 16.0 | 47.2% | -4.5% |
| 2023-26 | 2025 | production picks | 151-120-1 | 272 | +16.3 | +6.0% ± 5.7 | 55.7% | -4.5% |
| 2023-26 | 2025 | always favorite | 131-140-1 | 272 | -21.3 | -7.8% ± 5.8 | 48.3% | -4.5% |
| 2023-26 | 2025 | always home | 135-136-1 | 272 | -13.7 | -5.0% ± 5.8 | 49.8% | -4.5% |
| 2023-26 | 2026 | A raw disagreement | 8-9-0 | 17 | -2.0 | -11.8% ± 23.4 | 47.1% | -4.5% |
| 2023-26 | 2026 | B mapped disagreement | 10-6-0 | 16 | +3.0 | +18.6% ± 23.7 | 62.5% | -4.5% |
| 2023-26 | 2026 | production picks | 66-49-6 | 121 | +10.9 | +9.0% ± 8.4 | 57.4% | -4.5% |
| 2023-26 | 2026 | always favorite | 56-59-6 | 121 | -8.2 | -6.8% ± 8.5 | 48.7% | -4.5% |
| 2023-26 | 2026 | always home | 52-63-6 | 121 | -15.6 | -12.9% ± 8.5 | 45.2% | -4.5% |

## Calibration of arm A by decile of p − q

| Basis | Decile | n | Mean p − q | Mean p | Realized home cover |
|---|---:|---:|---:|---:|---:|
| 2016-22 | 0 | 178 | -1.81 pts | 0.485 | 0.567 |
| 2016-22 | 1 | 178 | -0.53 pts | 0.493 | 0.433 |
| 2016-22 | 2 | 177 | -0.27 pts | 0.496 | 0.497 |
| 2016-22 | 3 | 178 | -0.11 pts | 0.498 | 0.478 |
| 2016-22 | 4 | 177 | -0.02 pts | 0.498 | 0.475 |
| 2016-22 | 5 | 178 | -0.00 pts | 0.500 | 0.506 |
| 2016-22 | 6 | 177 | +0.03 pts | 0.500 | 0.435 |
| 2016-22 | 7 | 178 | +0.15 pts | 0.504 | 0.494 |
| 2016-22 | 8 | 177 | +0.56 pts | 0.507 | 0.525 |
| 2016-22 | 9 | 178 | +2.65 pts | 0.525 | 0.444 |
| 2023-26 | 0 | 92 | -1.44 pts | 0.482 | 0.424 |
| 2023-26 | 1 | 91 | -0.28 pts | 0.500 | 0.451 |
| 2023-26 | 2 | 91 | -0.08 pts | 0.501 | 0.495 |
| 2023-26 | 3 | 91 | -0.02 pts | 0.497 | 0.451 |
| 2023-26 | 4 | 91 | -0.01 pts | 0.497 | 0.538 |
| 2023-26 | 5 | 91 | +0.00 pts | 0.501 | 0.495 |
| 2023-26 | 6 | 91 | +0.02 pts | 0.502 | 0.593 |
| 2023-26 | 7 | 91 | +0.10 pts | 0.498 | 0.484 |
| 2023-26 | 8 | 91 | +0.28 pts | 0.504 | 0.505 |
| 2023-26 | 9 | 92 | +1.15 pts | 0.514 | 0.522 |
