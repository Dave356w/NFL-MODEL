# Market-only forecasts and rolling residuals

Exposed development; market quote capture times unknown. Stage one contains no box-score features.

812 common flat 1u bets; 815 binary win scores.

| Win model | Units | ROI ± SE | Null ROI | LL | Brier |
|---|---:|---:|---:|---:|---:|
| production_matched | +27.19 | +3.35% ± 2.55 | -4.10% | 0.607431 | 0.209769 |
| forecast_additive | +44.50 | +5.48% ± 2.54 | -4.10% | 0.606827 | 0.209571 |
| margin_total | +35.31 | +4.35% ± 2.53 | -4.10% | 0.607230 | 0.209748 |
| pass_total | +46.32 | +5.70% ± 2.54 | -4.10% | 0.606426 | 0.209456 |
| pass_market_total | +39.44 | +4.86% ± 2.54 | -4.10% | 0.606498 | 0.209458 |
| selected | +31.93 | +3.93% ± 2.54 | -4.10% | 0.608215 | 0.210125 |
| production_full | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605605 | 0.208989 |
| direct_margin_selected | +4.08 | +0.50% ± 2.47 | -4.10% | 0.607748 | 0.210309 |
| direct_margin_relationships | +4.08 | +0.50% ± 2.47 | -4.10% | 0.607748 | 0.210309 |
| market | +0.18 | +0.02% ± 2.47 | -4.10% | 0.608072 | 0.210334 |

## Paired win comparisons

| Arm | Comparator | ROI gain [CI], pp | LL gain [CI] |
|---|---|---:|---:|
| forecast_additive | production_matched | +2.13 [-0.43, +5.05] | +0.000604 [-0.001899, +0.002973] |
| forecast_additive | production_full | +1.90 [-0.60, +4.70] | -0.001222 [-0.008128, +0.004289] |
| margin_total | production_matched | +1.00 [-1.20, +3.26] | +0.000201 [-0.001911, +0.002233] |
| margin_total | production_full | +0.77 [-1.35, +3.11] | -0.001624 [-0.008388, +0.003573] |
| pass_total | production_matched | +2.36 [-0.25, +5.25] | +0.001005 [-0.002545, +0.004566] |
| pass_total | production_full | +2.13 [-0.27, +4.89] | -0.000821 [-0.006759, +0.004479] |
| pass_market_total | production_matched | +1.51 [-1.02, +4.20] | +0.000933 [-0.002512, +0.004652] |
| pass_market_total | production_full | +1.28 [-0.88, +3.71] | -0.000892 [-0.006195, +0.003947] |
| selected | production_full | +0.35 [-1.17, +1.94] | -0.002610 [-0.008197, +0.001845] |
| pass_total | pass_market_total | +0.85 [+0.00, +1.91] | +0.000072 [-0.000723, +0.000875] |
| margin_total | forecast_additive | -1.13 [-2.71, +0.31] | -0.000402 [-0.001295, +0.000451] |
| pass_total | forecast_additive | +0.22 [+0.00, +0.68] | +0.000402 [-0.001305, +0.002067] |

Fixed candidate/production comparisons use 98.75% intervals; selection/interaction/source contrasts 95%.

## Target distributions

| Target | Arm | N | NLL ↓ | CRPS ↓ | RMSE | Event LL ↓ | Market event LL ↓ |
|---|---|---:|---:|---:|---:|---:|---:|
| margin | market_centered | 816 | 3.957840 | 7.0859 | 12.653 | 0.693147 | 0.693588 |
| margin | market_relationships | 816 | 3.956549 | 7.0808 | 12.638 | 0.693529 | 0.693588 |
| margin | resid_h4_k4 | 816 | 3.956951 | 7.0834 | 12.643 | 0.693861 | 0.693588 |
| margin | resid_h4_k12 | 816 | 3.956958 | 7.0835 | 12.643 | 0.693878 | 0.693588 |
| margin | resid_h16_k4 | 816 | 3.956893 | 7.0828 | 12.643 | 0.693524 | 0.693588 |
| margin | resid_h16_k12 | 816 | 3.956941 | 7.0832 | 12.643 | 0.693539 | 0.693588 |
| margin | selected | 816 | 3.956549 | 7.0808 | 12.638 | 0.693529 | 0.693588 |
| total | market_centered | 816 | 3.981466 | 7.2414 | 12.959 | 0.693147 | 0.693319 |
| total | market_relationships | 816 | 3.978169 | 7.2221 | 12.916 | 0.690099 | 0.693319 |
| total | resid_h4_k4 | 816 | 3.978942 | 7.2271 | 12.926 | 0.690623 | 0.693319 |
| total | resid_h4_k12 | 816 | 3.978977 | 7.2273 | 12.926 | 0.690664 | 0.693319 |
| total | resid_h16_k4 | 816 | 3.979418 | 7.2309 | 12.932 | 0.690949 | 0.693319 |
| total | resid_h16_k12 | 816 | 3.979446 | 7.2310 | 12.933 | 0.690965 | 0.693319 |
| total | selected | 816 | 3.979189 | 7.2297 | 12.929 | 0.690784 | 0.693319 |

## Selected distribution improvement

| Target | Comparator | NLL gain [98.75% CI] | CRPS gain [CI] |
|---|---|---:|---:|
| margin | market_centered | +0.001291 [-0.002974, +0.005730] | +0.0051 [-0.0281, +0.0406] |
| margin | market_relationships | +0.000000 [+0.000000, +0.000000] | +0.0000 [+0.0000, +0.0000] |
| total | market_centered | +0.002277 [-0.004469, +0.008846] | +0.0116 [-0.0426, +0.0627] |
| total | market_relationships | -0.001021 [-0.002966, +0.000818] | -0.0076 [-0.0225, +0.0066] |

## Prior-season target selections

- 2023 margin: market_relationships (through 2022)
- 2023 total: resid_h16_k4 (through 2022)
- 2024 margin: market_relationships (through 2023)
- 2024 total: resid_h16_k4 (through 2023)
- 2025 margin: market_relationships (through 2024)
- 2025 total: market_relationships (through 2024)
- 2026 margin: market_relationships (through 2025)
- 2026 total: market_relationships (through 2025)

## Annual production comparisons

| Arm | Season | Units | ROI | LL |
|---|---:|---:|---:|---:|
| production_matched | 2023 | +1.80 | +0.67% | 0.637521 |
| production_matched | 2024 | +24.24 | +8.95% | 0.583400 |
| production_matched | 2025 | +1.15 | +0.42% | 0.601349 |
| forecast_additive | 2023 | +11.13 | +4.12% | 0.634346 |
| forecast_additive | 2024 | +32.58 | +12.02% | 0.583381 |
| forecast_additive | 2025 | +0.79 | +0.29% | 0.602740 |
| margin_total | 2023 | +8.83 | +3.27% | 0.635402 |
| margin_total | 2024 | +27.46 | +10.13% | 0.582988 |
| margin_total | 2025 | -0.99 | -0.36% | 0.603285 |
| pass_total | 2023 | +11.13 | +4.12% | 0.632331 |
| pass_total | 2024 | +34.40 | +12.69% | 0.582337 |
| pass_total | 2025 | +0.79 | +0.29% | 0.604603 |
| pass_market_total | 2023 | +9.32 | +3.45% | 0.632261 |
| pass_market_total | 2024 | +29.34 | +10.83% | 0.582508 |
| pass_market_total | 2025 | +0.79 | +0.29% | 0.604717 |
| selected | 2023 | +1.80 | +0.67% | 0.637521 |
| selected | 2024 | +29.34 | +10.83% | 0.582508 |
| selected | 2025 | +0.79 | +0.29% | 0.604603 |
| production_full | 2023 | +8.44 | +3.12% | 0.630814 |
| production_full | 2024 | +24.47 | +9.03% | 0.583169 |
| production_full | 2025 | -3.85 | -1.42% | 0.602822 |
| direct_margin_selected | 2023 | +6.07 | +2.25% | 0.622334 |
| direct_margin_selected | 2024 | +14.11 | +5.21% | 0.589986 |
| direct_margin_selected | 2025 | -16.09 | -5.94% | 0.610934 |
| direct_margin_relationships | 2023 | +6.07 | +2.25% | 0.622334 |
| direct_margin_relationships | 2024 | +14.11 | +5.21% | 0.589986 |
| direct_margin_relationships | 2025 | -16.09 | -5.94% | 0.610934 |
| market | 2023 | +4.12 | +1.53% | 0.627349 |
| market | 2024 | +14.11 | +5.21% | 0.587489 |
| market | 2025 | -18.05 | -6.66% | 0.609383 |

Production reproduction error 1.03e-10. All histories and nested fits precede evaluation weeks. Paired week-cluster bootstrap excludes design-selection uncertainty. Gaussian approximation and unknown quote timing limit interpretation. No native forward qualification or production change.


## Archived SF at SEA counterfactual

Schedule total/cover/over prices have unknown lock timing. Seattle/home margin is positive.
- margin_line: 3.000
- margin_mean: 3.229
- margin_sd: 12.504
- total_line: 45.500
- total_mean: 46.235
- total_sd: 13.092
- production_matched: 94.20% Seattle
- forecast_additive: 94.02% Seattle
- margin_total: 94.08% Seattle
- pass_total: 94.07% Seattle
- pass_market_total: 94.03% Seattle
- production_full: 93.90% Seattle
