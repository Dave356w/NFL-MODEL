# Test 51: per-team market-implied points in the v1.19 fit

Protocol: [MARKET_IMPLIED.md](../MARKET_IMPLIED.md), committed (`2e8c50c`) before any arm was scored. Diagnostic only; production v1.19 and the ledger are unchanged. All bases were exposed earlier (see protocol).

Reproduction by P: v1.19 retro_ledger 2021-25 2.4e-15, Test 50 S3 2014-20 (6-digit CSV) 5.0e-07, fixed_band_spread 2023-25 0.0e+00.

## Log loss (arm minus v1.19, x1000; negative = arm better; bar |z| >= 2.24)

| Arm | 2015-16 | 2017-22 | 2023-25 | Verdict |
|---|---:|---:|---:|---|
| A this game's implied points | -0.32 ± 0.90 (z -0.4, n 510) | +0.26 ± 0.46 (z +0.6, n 1559) | -0.60 ± 0.58 (z -1.0, n 815) | forward candidate |
| B history vs implied points | +0.29 ± 1.14 (z +0.3, n 510) | -0.22 ± 0.45 (z -0.5, n 1559) | +0.62 ± 0.72 (z +0.9, n 815) | unresolved |

v1.19 log loss per game: 2015-16 0.64165, 2017-22 0.60542, 2023-25 0.60501.

## Added coefficients in the last fit of each basis (per weighted-RMS unit, log-odds)

| Basis | Arm | Fit | Coefficients |
|---|---|---|---|
| 2015-16 | A this game's implied points | 2016 wk 17 | mkt_home_implied -0.047, mkt_away_implied -0.064 |
| 2015-16 | B history vs implied points | 2016 wk 17 | d__mkt_off_resid -0.026, d__mkt_def_resid -0.057 |
| 2017-22 | A this game's implied points | 2022 wk 18 | mkt_home_implied -0.014, mkt_away_implied -0.023 |
| 2017-22 | B history vs implied points | 2022 wk 18 | d__mkt_off_resid -0.047, d__mkt_def_resid +0.112 |
| 2023-25 | A this game's implied points | 2025 wk 18 | mkt_home_implied +0.018, mkt_away_implied -0.052 |
| 2023-25 | B history vs implied points | 2025 wk 18 | d__mkt_off_resid -0.030, d__mkt_def_resid -0.026 |

## Added terms: spread and overlap with the market

| Basis | Term | Mean | SD | Corr with market log-odds | Corr with v1.19 departure |
|---|---|---:|---:|---:|---:|
| 2015-16 | mkt_home_implied | +1.25 | 3.16 | +0.83 | -0.23 |
| 2015-16 | mkt_away_implied | -0.91 | 3.07 | -0.81 | +0.20 |
| 2015-16 | d__mkt_off_resid | -0.08 | 2.29 | +0.51 | -0.00 |
| 2015-16 | d__mkt_def_resid | +0.01 | 2.14 | -0.49 | +0.11 |
| 2017-22 | mkt_home_implied | +1.23 | 3.86 | +0.81 | -0.07 |
| 2017-22 | mkt_away_implied | -0.51 | 3.93 | -0.82 | +0.12 |
| 2017-22 | d__mkt_off_resid | +0.01 | 2.25 | +0.48 | +0.01 |
| 2017-22 | d__mkt_def_resid | -0.01 | 2.06 | -0.37 | +0.13 |
| 2023-25 | mkt_home_implied | +0.30 | 3.66 | +0.81 | -0.09 |
| 2023-25 | mkt_away_implied | -1.25 | 3.59 | -0.80 | +0.12 |
| 2023-25 | d__mkt_off_resid | -0.01 | 2.25 | +0.48 | +0.04 |
| 2023-25 | d__mkt_def_resid | -0.04 | 2.13 | -0.41 | +0.12 |

## ATS, flat 1u at -110 (same rows for every arm; each arm uses its own prior-season median map)

Break-even cover rate 52.4%. ROI SE has pushes in the denominator. Flips and flip units are against v1.19 in the same view.

| Basis | Arm | View | W-L-P | Skips | Units | ROI ± SE | Cover | Flips | Units on flips (arm − P) |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2015-16 | P | median map | 139-112-5 | 0 | +14.4 | +5.6% ± 5.9 | 55.4% |  |  |
| 2015-16 | P | raw spread | 123-128-5 | 0 | -16.2 | -6.3% ± 5.9 | 49.0% |  |  |
| 2015-16 | always favorite | baseline | 128-122-5 | 1 | -5.6 | -2.2% ± 5.9 | 51.2% |  |  |
| 2015-16 | always home | baseline | 123-128-5 | 0 | -16.2 | -6.3% ± 5.9 | 49.0% |  |  |
| 2015-16 | A this game's implied points | median map | 128-123-5 | 0 | -6.6 | -2.6% ± 5.9 | 51.0% | 65 | -21.0 |
| 2015-16 | A this game's implied points | raw spread | 137-114-5 | 0 | +10.5 | +4.1% ± 5.9 | 54.6% | 38 | +26.7 |
| 2015-16 | B history vs implied points | median map | 132-119-5 | 0 | +1.0 | +0.4% ± 5.9 | 52.6% | 12 | -13.4 |
| 2015-16 | B history vs implied points | raw spread | 132-119-5 | 0 | +1.0 | +0.4% ± 5.9 | 52.6% | 27 | +17.2 |
| 2017-22 | P | median map | 741-784-41 | 0 | -110.4 | -7.0% ± 2.4 | 48.6% |  |  |
| 2017-22 | P | raw spread | 766-759-41 | 0 | -62.6 | -4.0% ± 2.4 | 50.2% |  |  |
| 2017-22 | always favorite | baseline | 715-807-41 | 3 | -157.0 | -10.0% ± 2.4 | 47.0% |  |  |
| 2017-22 | always home | baseline | 739-786-41 | 0 | -114.2 | -7.3% ± 2.4 | 48.5% |  |  |
| 2017-22 | A this game's implied points | median map | 753-772-41 | 0 | -87.5 | -5.6% ± 2.4 | 49.4% | 180 | +22.9 |
| 2017-22 | A this game's implied points | raw spread | 759-766-41 | 0 | -76.0 | -4.9% ± 2.4 | 49.8% | 126 | -13.4 |
| 2017-22 | B history vs implied points | median map | 794-731-41 | 0 | -9.2 | -0.6% ± 2.4 | 52.1% | 238 | +101.2 |
| 2017-22 | B history vs implied points | raw spread | 777-748-41 | 0 | -41.6 | -2.7% ± 2.4 | 51.0% | 109 | +21.0 |
| 2023-25 | P | median map | 422-375-19 | 0 | +8.6 | +1.1% ± 3.3 | 52.9% |  |  |
| 2023-25 | P | raw spread | 396-401-19 | 0 | -41.0 | -5.0% ± 3.3 | 49.7% |  |  |
| 2023-25 | always favorite | baseline | 411-386-19 | 0 | -12.4 | -1.5% ± 3.3 | 51.6% |  |  |
| 2023-25 | always home | baseline | 400-397-19 | 0 | -33.4 | -4.1% ± 3.3 | 50.2% |  |  |
| 2023-25 | A this game's implied points | median map | 417-380-19 | 0 | -0.9 | -0.1% ± 3.3 | 52.3% | 133 | -9.5 |
| 2023-25 | A this game's implied points | raw spread | 412-385-19 | 0 | -10.5 | -1.3% ± 3.3 | 51.7% | 49 | +30.5 |
| 2023-25 | B history vs implied points | median map | 417-380-19 | 0 | -0.9 | -0.1% ± 3.3 | 52.3% | 85 | -9.5 |
| 2023-25 | B history vs implied points | raw spread | 408-389-19 | 0 | -18.1 | -2.2% ± 3.3 | 51.2% | 64 | +22.9 |
| 2023-25 | P | median map, 2021+ history (supplementary) | 427-370-19 | 0 | +18.2 | +2.2% ± 3.3 | 53.6% |  |  |
| 2023-25 | A this game's implied points | median map, 2021+ history (supplementary) | 421-376-19 | 0 | +6.7 | +0.8% ± 3.3 | 52.8% | 82 | -11.5 |
| 2023-25 | B history vs implied points | median map, 2021+ history (supplementary) | 418-379-19 | 0 | +1.0 | +0.1% ± 3.3 | 52.4% | 85 | -17.2 |

## Moneyline flat units (legacy, same bets)

| Basis | Arm | Bets | v1.19 | Arm |
|---|---|---:|---:|---:|
| 2015-16 | A this game's implied points | 512 | -18.1 | -25.0 |
| 2015-16 | B history vs implied points | 512 | -18.1 | -23.6 |
| 2017-22 | A this game's implied points | 1566 | -45.6 | -51.4 |
| 2017-22 | B history vs implied points | 1566 | -45.6 | -42.0 |
| 2023-25 | A this game's implied points | 816 | +19.1 | +12.5 |
| 2023-25 | B history vs implied points | 816 | +19.1 | +28.6 |
