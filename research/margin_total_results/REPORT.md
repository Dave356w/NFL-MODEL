# Direct margin/total and production interaction results

Exposed historical development, not native forward qualification. Schedule quotes have no known lock timestamps. Gaussian approximation and market-centered benchmarks; true market event probabilities use both no-vig prices.

Stack: 812 common flat 1u bets; 815 binary scores.

| Win model | Units | ROI ± SE | Market-null | LL | Brier |
|---|---:|---:|---:|---:|---:|
| production_matched | +27.19 | +3.35% ± 2.55 | -4.10% | 0.607431 | 0.209769 |
| forecast_additive | +19.99 | +2.46% ± 2.53 | -4.10% | 0.605717 | 0.209152 |
| margin_total | +21.83 | +2.69% ± 2.53 | -4.10% | 0.605814 | 0.209169 |
| pass_total | +29.76 | +3.67% ± 2.53 | -4.10% | 0.605569 | 0.209114 |
| pass_market_total | +28.10 | +3.46% ± 2.53 | -4.10% | 0.604746 | 0.208815 |
| selected | +29.98 | +3.69% ± 2.53 | -4.10% | 0.606025 | 0.209271 |
| production_full | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605605 | 0.208989 |
| direct_margin_corrected | +4.83 | +0.59% ± 2.50 | -4.10% | 0.608977 | 0.210120 |
| direct_margin_standalone | +17.72 | +2.18% ± 2.73 | -4.10% | 0.628899 | 0.217986 |
| market | +0.18 | +0.02% ± 2.47 | -4.10% | 0.608072 | 0.210334 |

Positive paired gains favor the new arm over matched-cohort production. Fixed contrasts use 98.333% intervals; selected/full-history diagnostics 95%.

| Arm | ROI delta [CI], pp | LL gain [CI] | Side flips |
|---|---:|---:|---:|
| forecast_additive | -0.89 [-3.45, +1.71] | +0.001714 [-0.000975, +0.004765] | 14 |
| margin_total | -0.66 [-3.26, +2.02] | +0.001617 [-0.001062, +0.004507] | 17 |
| pass_total | +0.32 [-2.97, +3.79] | +0.001862 [-0.001891, +0.005650] | 23 |
| selected | +0.34 [-2.36, +3.10] | +0.001406 [-0.001420, +0.004289] | 21 |
| production_full | +0.23 [-1.43, +1.74] | +0.001826 [-0.002185, +0.007230] | 11 |

## Interaction benefit and full-history production comparisons

| Arm | Comparator | ROI delta [CI], pp | LL gain [CI] |
|---|---|---:|---:|
| margin_total | forecast_additive | +0.23 [-0.81, +1.25] | -0.000097 [-0.000872, +0.000612] |
| pass_total | forecast_additive | +1.20 [-0.26, +2.95] | +0.000148 [-0.001721, +0.001856] |
| forecast_additive | production_full | -1.12 [-3.23, +1.14] | -0.000112 [-0.007270, +0.005271] |
| margin_total | production_full | -0.89 [-3.14, +1.45] | -0.000209 [-0.007442, +0.005044] |
| pass_total | production_full | +0.09 [-2.46, +2.94] | +0.000036 [-0.006482, +0.005572] |
| pass_total | pass_market_total | +0.21 [-0.76, +1.25] | -0.000823 [-0.002229, +0.000535] |

Interactions vs additive use 97.5% intervals (two contrasts); comparisons vs full production use 98.333% (three). The supplementary pass_market_total contrast uses a descriptive 95% interval. Direct-margin win probabilities condition on a non-tie.

## Distribution forecasts

| Target | Arm | N | NLL ↓ | CRPS ↓ | MAE | RMSE | 90% coverage |
|---|---|---:|---:|---:|---:|---:|---:|
| margin | market_centered | 816 | 3.957840 | 7.0859 | 9.744 | 12.653 | 88.8% |
| margin | corrected | 816 | 3.959389 | 7.1117 | 9.795 | 12.675 | 89.2% |
| margin | standalone | 816 | 3.987619 | 7.3045 | 10.041 | 13.036 | 89.2% |
| total | market_centered | 816 | 3.981466 | 7.2414 | 10.121 | 12.959 | 90.6% |
| total | corrected | 816 | 3.988114 | 7.3053 | 10.235 | 13.043 | 90.0% |
| total | standalone | 816 | 4.009772 | 7.4541 | 10.410 | 13.330 | 90.1% |

| Target | Arm | NLL gain vs market-centered [CI] | CRPS gain [CI] |
|---|---|---:|---:|
| margin | corrected | -0.001549 [-0.013790, +0.011041] | -0.0258 [-0.1140, +0.0636] |
| margin | standalone | -0.029779 [-0.051357, -0.008248] | -0.2186 [-0.3780, -0.0592] |
| total | corrected | -0.006647 [-0.021090, +0.007084] | -0.0639 [-0.1688, +0.0397] |
| total | standalone | -0.028306 [-0.047973, -0.008524] | -0.2127 [-0.3551, -0.0631] |

## Cover/over probabilities at market lines

Pushes excluded from both arms. These compare actual no-vig prices, not a reconstructed 50% baseline. 98.75% intervals.

| Target | Arm | Nonpush N | Pushes | Event LL ↓ | Market LL ↓ | LL gain [CI] |
|---|---|---:|---:|---:|---:|---:|
| margin | market_centered | 797 | 19 | 0.693147 | 0.693588 | +0.000440 [-0.001770, +0.002678] |
| margin | corrected | 797 | 19 | 0.694871 | 0.693588 | -0.001284 [-0.011647, +0.009033] |
| margin | standalone | 797 | 19 | 0.708241 | 0.693588 | -0.014653 [-0.035288, +0.004813] |
| total | market_centered | 811 | 5 | 0.693147 | 0.693319 | +0.000172 [-0.000977, +0.001390] |
| total | corrected | 811 | 5 | 0.699999 | 0.693319 | -0.006679 [-0.019570, +0.006673] |
| total | standalone | 811 | 5 | 0.709251 | 0.693319 | -0.015932 [-0.033247, +0.002161] |

## Annual win results

| Arm | Season | Units | ROI | LL |
|---|---:|---:|---:|---:|
| production_matched | 2023 | +1.80 | +0.67% | 0.637521 |
| production_matched | 2024 | +24.24 | +8.95% | 0.583400 |
| production_matched | 2025 | +1.15 | +0.42% | 0.601349 |
| forecast_additive | 2023 | +6.92 | +2.56% | 0.634959 |
| forecast_additive | 2024 | +21.26 | +7.85% | 0.580216 |
| forecast_additive | 2025 | -8.19 | -3.02% | 0.601962 |
| margin_total | 2023 | +6.92 | +2.56% | 0.634649 |
| margin_total | 2024 | +23.16 | +8.54% | 0.580150 |
| margin_total | 2025 | -8.25 | -3.04% | 0.602632 |
| pass_total | 2023 | +6.71 | +2.48% | 0.633593 |
| pass_total | 2024 | +28.81 | +10.63% | 0.579223 |
| pass_total | 2025 | -5.75 | -2.12% | 0.603884 |
| pass_market_total | 2023 | +5.13 | +1.90% | 0.631052 |
| pass_market_total | 2024 | +28.95 | +10.68% | 0.578839 |
| pass_market_total | 2025 | -5.99 | -2.21% | 0.604345 |
| selected | 2023 | +6.92 | +2.56% | 0.634959 |
| selected | 2024 | +28.81 | +10.63% | 0.579223 |
| selected | 2025 | -5.75 | -2.12% | 0.603884 |
| production_full | 2023 | +8.44 | +3.12% | 0.630814 |
| production_full | 2024 | +24.47 | +9.03% | 0.583169 |
| production_full | 2025 | -3.85 | -1.42% | 0.602822 |
| direct_margin_corrected | 2023 | +3.91 | +1.45% | 0.626118 |
| direct_margin_corrected | 2024 | +13.98 | +5.16% | 0.599178 |
| direct_margin_corrected | 2025 | -13.06 | -4.82% | 0.601608 |
| direct_margin_standalone | 2023 | -10.04 | -3.72% | 0.652390 |
| direct_margin_standalone | 2024 | +30.89 | +11.40% | 0.620771 |
| direct_margin_standalone | 2025 | -3.13 | -1.16% | 0.613480 |
| market | 2023 | +4.12 | +1.53% | 0.627349 |
| market | 2024 | +14.11 | +5.21% | 0.587489 |
| market | 2025 | -18.05 | -6.66% | 0.609383 |

## Prior-season stack selection

- 2023: forecast_additive (selection through 2022)
- 2024: pass_total (selection through 2023)
- 2025: pass_total (selection through 2024)

Full-history production reproduction error: 1.03e-10.
All stage-one features, coefficient fits, variance calibration and stage-two coefficient fits precede evaluation weeks. Stage-two warm-up removes early training games; production_full discloses its impact. These intervals omit model-design selection uncertainty.


## Archived SF at SEA counterfactual

Schedule total quote is not a known lock quote. Seattle/home margin is positive.
- margin_line: 3.000
- total_line: 45.500
- margin__corrected__mean: 16.735
- margin__corrected__sd: 12.592
- total__corrected__mean: 47.077
- total__corrected__sd: 13.246
- production_matched: 94.20% Seattle
- forecast_additive: 93.27% Seattle
- margin_total: 93.37% Seattle
- pass_total: 93.20% Seattle
- pass_market_total: 93.23% Seattle
- production_full: 93.90% Seattle
- direct_margin_corrected: 91.33% Seattle