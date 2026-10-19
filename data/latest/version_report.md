# Production restoration and all competing-model results

Current production: **boxscore-composite-v1.18**, the v1.16 recipe with the favorite-confidence penalty (lambda 0.2); v1.16 continues as a shadow lock for its pre-registered tests.
Configuration: `73636f306d54de2c12a0d8ba394f0aecae9d58d2cd9aa415a87c4b22bca58a20`. Owner decision 2026-10-13.
Original forecasts and frozen recipes remain unchanged. This report grades existing predictions; it does not retune or select a candidate.

## Native forward results

Each experiment contains one original pregame forecast per game. Different revisions can overlap and have different lock quotes; do not pool them. Ties push; binary scores exclude ties. Pending games remain ungraded.

| Original revision | N | W-L-P | Units | ROI ± SE | Favorite units | Null ROI | LL ↓ | Market LL ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| boxscore-composite-v1.12 | 1 | 0-1-0 | -1.00 | -100.00% ± — | -1.00 | -4.03% | 1.034360 | 1.402440 |
| boxscore-composite-v1.13 | 1 | 0-1-0 | -1.00 | -100.00% ± — | -1.00 | -4.00% | 1.002170 | 1.402440 |
| boxscore-composite-v1.14 | 1 | 0-1-0 | -1.00 | -100.00% ± — | -1.00 | -4.08% | 0.965520 | 1.508470 |
| boxscore-composite-v1.16 | 28 | 15-10-1 | -2.55 | -9.81% ± 14.69 | -0.68 | -4.10% | 0.754322 | 0.666189 |
| boxscore-composite-v1.17 | 14 | 8-5-1 | -1.34 | -9.56% ± 19.32 | +0.40 | -4.08% | 0.765942 | 0.574300 |
| boxscore-composite-v1.18 | 14 | 6-6-0 | -2.93 | -24.38% ± 23.27 | -1.06 | -4.12% | 0.742673 | 0.760980 |

## Frozen archived-input counterfactuals

These forecasts use the archived v1.16 input cohort and original moneylines. Total/cover/over schedule quote capture times are unknown. They are reconstructed research forecasts, not executable native locks. No missing games are backfilled. Outcomes are taken from the current graded ledger.

| Study and arm | N | W-L-P | Units | ROI ± SE | Favorite units | Null ROI | LL ↓ | Market LL ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| market_offset: with_market | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.738627 | 0.540710 |
| market_offset: without_market | 13 | 6-6-1 | -3.59 | -27.62% ± 19.80 | +1.37 | -4.07% | 0.803355 | 0.540710 |
| market_offset: market_only | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.540710 | 0.540710 |
| shrinkage: production | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.738627 | 0.540710 |
| shrinkage: product_only | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.617611 | 0.540710 |
| shrinkage: active_10 | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.728070 | 0.540710 |
| shrinkage: active_30 | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.711994 | 0.540710 |
| shrinkage: active_100 | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.680775 | 0.540710 |
| shrinkage: information_30 | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.659836 | 0.540710 |
| profile_robustness: production | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.738627 | 0.540710 |
| profile_robustness: profile_4 | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.715757 | 0.540710 |
| profile_robustness: profile_12 | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.693564 | 0.540710 |
| profile_robustness: bounded_2 | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.713827 | 0.540710 |
| profile_robustness: combined_4_2 | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.706598 | 0.540710 |
| profile_robustness: market | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.540710 | 0.540710 |
| margin_total: production_matched | 13 | 10-2-1 | +3.42 | +26.35% ± 17.22 | +1.37 | -4.07% | 0.745556 | 0.540710 |
| margin_total: forecast_additive | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.727586 | 0.540710 |
| margin_total: margin_total | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.728437 | 0.540710 |
| margin_total: pass_total | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.722123 | 0.540710 |
| margin_total: pass_market_total | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.723230 | 0.540710 |
| margin_total: production_full | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.738627 | 0.540710 |
| margin_total: direct_margin_corrected | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.722482 | 0.540710 |
| market_residual: production_matched | 13 | 10-2-1 | +3.42 | +26.35% ± 17.22 | +1.37 | -4.07% | 0.745556 | 0.540710 |
| market_residual: forecast_additive | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.739854 | 0.540710 |
| market_residual: margin_total | 13 | 10-2-1 | +3.42 | +26.35% ± 17.22 | +1.37 | -4.07% | 0.737952 | 0.540710 |
| market_residual: pass_total | 13 | 10-2-1 | +3.42 | +26.35% ± 17.22 | +1.37 | -4.07% | 0.736200 | 0.540710 |
| market_residual: pass_market_total | 13 | 10-2-1 | +3.42 | +26.35% ± 17.22 | +1.37 | -4.07% | 0.737256 | 0.540710 |
| market_residual: production_full | 13 | 9-3-1 | +1.37 | +10.58% ± 18.40 | +1.37 | -4.07% | 0.738627 | 0.540710 |

## All committed historical tests

Exposed 2023–2025 chronological development. Compare arms within each study; cohorts differ (811 versus 812 bets), warm-up training histories differ, and the label production in the older qualification/context studies describes the pre-v1.16 model. Repeated control rows are not independent evidence.

| Study and arm | N | W-L-P | Units | ROI ± SE | Favorite units | Null ROI | LL ↓ | Market LL ↓ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| qualification: production | 812 | 547-264-1 | +16.30 | +2.01% ± 2.65 | +0.18 | -4.10% | 0.631630 | 0.608072 |
| qualification: market_additive | 812 | 555-256-1 | +0.18 | +0.02% ± 2.47 | +0.18 | -4.10% | 0.608005 | 0.608072 |
| qualification: market_product | 812 | 554-257-1 | -1.11 | -0.14% ± 2.47 | +0.18 | -4.10% | 0.606162 | 0.608072 |
| qualification: market_qualified | 812 | 556-255-1 | +3.73 | +0.46% ± 2.48 | +0.18 | -4.10% | 0.607887 | 0.608072 |
| qualification: market_extreme | 812 | 558-253-1 | +6.88 | +0.85% ± 2.47 | +0.18 | -4.10% | 0.607723 | 0.608072 |
| qualification: fixed_market_product | 812 | 562-249-1 | +19.32 | +2.38% ± 2.49 | +0.18 | -4.10% | 0.607584 | 0.608072 |
| qualification: q | 812 | 555-256-1 | +0.18 | +0.02% ± 2.47 | +0.18 | -4.10% | 0.608072 | 0.608072 |
| context: production | 811 | 546-264-1 | +15.38 | +1.90% ± 2.65 | +1.18 | -4.10% | 0.631630 | 0.608072 |
| context: fixed_market_product | 811 | 562-248-1 | +20.32 | +2.51% ± 2.49 | +1.18 | -4.10% | 0.607584 | 0.608072 |
| context: q | 811 | 555-255-1 | +1.18 | +0.15% ± 2.47 | +1.18 | -4.10% | 0.608072 | 0.608072 |
| context: hinge_0.5 | 811 | 563-247-1 | +23.43 | +2.89% ± 2.50 | +1.18 | -4.10% | 0.607527 | 0.608072 |
| context: hinge_1 | 811 | 565-245-1 | +27.24 | +3.36% ± 2.50 | +1.18 | -4.10% | 0.608663 | 0.608072 |
| context: hinge_1.5 | 811 | 561-249-1 | +22.45 | +2.77% ± 2.53 | +1.18 | -4.10% | 0.606111 | 0.608072 |
| context: hinge_2 | 811 | 563-247-1 | +23.02 | +2.84% ± 2.50 | +1.18 | -4.10% | 0.607533 | 0.608072 |
| context: multiscale | 811 | 564-246-1 | +24.88 | +3.07% ± 2.50 | +1.18 | -4.10% | 0.607778 | 0.608072 |
| context: one_extreme | 811 | 564-246-1 | +24.41 | +3.01% ± 2.50 | +1.18 | -4.10% | 0.608473 | 0.608072 |
| context: market_context | 811 | 564-246-1 | +24.41 | +3.01% ± 2.50 | +1.18 | -4.10% | 0.608570 | 0.608072 |
| context: early_context | 811 | 564-246-1 | +24.41 | +3.01% ± 2.50 | +1.18 | -4.10% | 0.609078 | 0.608072 |
| context: hinge_0.5_fixed_r0.1 | 811 | 559-251-1 | +17.74 | +2.19% ± 2.52 | +1.18 | -4.10% | 0.606478 | 0.608072 |
| context: hinge_1_fixed_r0.1 | 811 | 565-245-1 | +30.06 | +3.71% ± 2.52 | +1.18 | -4.10% | 0.605605 | 0.608072 |
| context: hinge_1.5_fixed_r0.1 | 811 | 565-245-1 | +28.73 | +3.54% ± 2.52 | +1.18 | -4.10% | 0.605986 | 0.608072 |
| context: hinge_2_fixed_r0.1 | 811 | 563-247-1 | +23.02 | +2.84% ± 2.50 | +1.18 | -4.10% | 0.607533 | 0.608072 |
| context: multiscale_fixed_r0.1 | 811 | 560-250-1 | +22.34 | +2.75% ± 2.54 | +1.18 | -4.10% | 0.605923 | 0.608072 |
| context: one_extreme_fixed_r0.1 | 811 | 558-252-1 | +14.51 | +1.79% ± 2.51 | +1.18 | -4.10% | 0.607517 | 0.608072 |
| context: market_context_fixed_r0.1 | 811 | 565-245-1 | +26.54 | +3.27% ± 2.50 | +1.18 | -4.10% | 0.607805 | 0.608072 |
| context: early_context_fixed_r0.1 | 811 | 561-249-1 | +18.66 | +2.30% ± 2.50 | +1.18 | -4.10% | 0.608259 | 0.608072 |
| market_offset: with_market | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 0.605605 | 0.608072 |
| market_offset: without_market | 812 | 544-267-1 | +19.01 | +2.34% ± 2.72 | +0.18 | -4.10% | 0.625832 | 0.608072 |
| market_offset: market_only | 812 | 555-256-1 | +0.18 | +0.02% ± 2.47 | +0.18 | -4.10% | 0.608072 | 0.608072 |
| shrinkage: production | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 0.605605 | 0.608072 |
| shrinkage: product_only | 812 | 562-249-1 | +19.32 | +2.38% ± 2.49 | +0.18 | -4.10% | 0.607584 | 0.608072 |
| shrinkage: market | 812 | 555-256-1 | +0.18 | +0.02% ± 2.47 | +0.18 | -4.10% | 0.608072 | 0.608072 |
| shrinkage: active_10 | 812 | 563-248-1 | +25.50 | +3.14% ± 2.53 | +0.18 | -4.10% | 0.605505 | 0.608072 |
| shrinkage: active_30 | 812 | 563-248-1 | +25.50 | +3.14% ± 2.53 | +0.18 | -4.10% | 0.605549 | 0.608072 |
| shrinkage: active_100 | 812 | 563-248-1 | +23.93 | +2.95% ± 2.52 | +0.18 | -4.10% | 0.606001 | 0.608072 |
| shrinkage: information_30 | 812 | 561-250-1 | +17.76 | +2.19% ± 2.50 | +0.18 | -4.10% | 0.606599 | 0.608072 |
| shrinkage: selected | 812 | 564-247-1 | +24.48 | +3.01% ± 2.50 | +0.18 | -4.10% | 0.606627 | 0.608072 |
| profile_robustness: production | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 0.605605 | 0.608072 |
| profile_robustness: profile_4 | 812 | 563-248-1 | +25.34 | +3.12% ± 2.53 | +0.18 | -4.10% | 0.605271 | 0.608072 |
| profile_robustness: profile_12 | 812 | 565-246-1 | +29.19 | +3.60% ± 2.53 | +0.18 | -4.10% | 0.605358 | 0.608072 |
| profile_robustness: bounded_2 | 812 | 566-245-1 | +31.92 | +3.93% ± 2.53 | +0.18 | -4.10% | 0.605829 | 0.608072 |
| profile_robustness: combined_4_2 | 812 | 563-248-1 | +24.62 | +3.03% ± 2.51 | +0.18 | -4.10% | 0.605700 | 0.608072 |
| profile_robustness: selected | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 0.605610 | 0.608072 |
| profile_robustness: market | 812 | 555-256-1 | +0.18 | +0.02% ± 2.47 | +0.18 | -4.10% | 0.608072 | 0.608072 |
| margin_total: production_matched | 812 | 562-249-1 | +27.19 | +3.35% ± 2.55 | +0.18 | -4.10% | 0.607431 | 0.608072 |
| margin_total: forecast_additive | 812 | 560-251-1 | +19.99 | +2.46% ± 2.53 | +0.18 | -4.10% | 0.605717 | 0.608072 |
| margin_total: margin_total | 812 | 561-250-1 | +21.83 | +2.69% ± 2.53 | +0.18 | -4.10% | 0.605814 | 0.608072 |
| margin_total: pass_total | 812 | 565-246-1 | +29.76 | +3.67% ± 2.53 | +0.18 | -4.10% | 0.605569 | 0.608072 |
| margin_total: pass_market_total | 812 | 564-247-1 | +28.10 | +3.46% ± 2.53 | +0.18 | -4.10% | 0.604746 | 0.608072 |
| margin_total: selected | 812 | 565-246-1 | +29.98 | +3.69% ± 2.53 | +0.18 | -4.10% | 0.606025 | 0.608072 |
| margin_total: production_full | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 0.605605 | 0.608072 |
| margin_total: direct_margin_corrected | 812 | 554-257-1 | +4.83 | +0.59% ± 2.50 | +0.18 | -4.10% | 0.608977 | 0.608072 |
| margin_total: direct_margin_standalone | 812 | 542-269-1 | +17.72 | +2.18% ± 2.73 | +0.18 | -4.10% | 0.628899 | 0.608072 |
| margin_total: market | 812 | 555-256-1 | +0.18 | +0.02% ± 2.47 | +0.18 | -4.10% | 0.608072 | 0.608072 |
| market_residual: production_matched | 812 | 562-249-1 | +27.19 | +3.35% ± 2.55 | +0.18 | -4.10% | 0.607431 | 0.608072 |
| market_residual: forecast_additive | 812 | 571-240-1 | +44.50 | +5.48% ± 2.54 | +0.18 | -4.10% | 0.606827 | 0.608072 |
| market_residual: margin_total | 812 | 567-244-1 | +35.31 | +4.35% ± 2.53 | +0.18 | -4.10% | 0.607230 | 0.608072 |
| market_residual: pass_total | 812 | 572-239-1 | +46.32 | +5.70% ± 2.54 | +0.18 | -4.10% | 0.606426 | 0.608072 |
| market_residual: pass_market_total | 812 | 569-242-1 | +39.44 | +4.86% ± 2.54 | +0.18 | -4.10% | 0.606498 | 0.608072 |
| market_residual: selected | 812 | 565-246-1 | +31.93 | +3.93% ± 2.54 | +0.18 | -4.10% | 0.608215 | 0.608072 |
| market_residual: production_full | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 0.605605 | 0.608072 |
| market_residual: direct_margin_selected | 812 | 557-254-1 | +4.08 | +0.50% ± 2.47 | +0.18 | -4.10% | 0.607748 | 0.608072 |
| market_residual: direct_margin_relationships | 812 | 557-254-1 | +4.08 | +0.50% ± 2.47 | +0.18 | -4.10% | 0.607748 | 0.608072 |
| market_residual: market | 812 | 555-256-1 | +0.18 | +0.02% ± 2.47 | +0.18 | -4.10% | 0.608072 | 0.608072 |

## Selection-adjusted benchmark

Basis: Exposed 2023-2025 held-out walk-forward; fixed committed forecasts; not forward evidence.

Across 53 committed arms on the same 809 games, if the market were exactly right the best arm would beat the same-row favorite by a median +16.7u by luck alone (95th percentile +44.7u).
Observed best: market_residual:pass_total beats it by +46.1u (market-correct p 0.042; Reality Check p 0.037). v1.16 beats it by +30.6u (p 0.180 against the best-arm null; 0.007 unadjusted). v1.17 beats it by +46.1u (p 0.042).
Log loss: best arm margin_total:pass_market_total gains +0.0035 over the market (market-correct p 0.047; Reality Check p 0.697).
Forecasts are fixed and only committed arms are included. Many more configurations were tried, so the real selection adjustment is larger and these p-values are optimistic.

Source: `research/selection_benchmark_results/REPORT.md`.

## Interpretation

v1.17 has the highest tested historical return among the recent fixed challengers, but its paired advantage over v1.16 remains unresolved (98.75% ROI-difference interval −0.27 to +4.89 percentage points). v1.16 has better historical binary scores than v1.17. The extra passing-by-total interaction beats the additive market-target challenger on returns through one changed historical pick. Shrinkage and bounded variants do not establish replacement superiority.
Historical intervals condition on exposed model development and omit design-selection uncertainty. ROI ± SE is one standard error, not a confidence interval. Native results are small-sample descriptive evidence. Source reports retain paired week-cluster intervals and annual comparisons.
The restored production is not qualified as reliably profitable. Retrospective snapshot grades are reported separately from native outcomes, and repeated snapshots are never counted as independent games.
