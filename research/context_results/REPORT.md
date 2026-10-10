# Additional context battle

Historical ROI leader: **hinge_1**. No deployment performed.

Exposed 2023–2025 development: 811 common flat 1u bets, 815 binary proper scores. Ties push; market pickems and any exact model abstentions excluded.

Excluded games: 2023_02_IND_HOU, 2023_03_LAC_MIN, 2024_11_CIN_LAC, 2024_17_GB_MIN, 2025_10_PHI_GB. Four are market pickems; 2024_17_GB_MIN is an exact model abstention. Baseline ROI therefore differs from the previous 812-bet report.

## Primary comparison

| Arm | W–L–P | Units | ROI ± SE | Market-null ROI | Log loss |
|---|---:|---:|---:|---:|---:|
| production | 546–264–1 | +15.38 | +1.90% ± 2.65 | -4.10% | 0.631630 |
| fixed_market_product | 562–248–1 | +20.32 | +2.51% ± 2.49 | -4.10% | 0.607584 |
| q | 555–255–1 | +1.18 | +0.15% ± 2.47 | -4.10% | 0.608072 |
| hinge_0.5 | 563–247–1 | +23.43 | +2.89% ± 2.50 | -4.10% | 0.607527 |
| hinge_1 | 565–245–1 | +27.24 | +3.36% ± 2.50 | -4.10% | 0.608663 |
| hinge_1.5 | 561–249–1 | +22.45 | +2.77% ± 2.53 | -4.10% | 0.606111 |
| hinge_2 | 563–247–1 | +23.02 | +2.84% ± 2.50 | -4.10% | 0.607533 |
| multiscale | 564–246–1 | +24.88 | +3.07% ± 2.50 | -4.10% | 0.607778 |
| one_extreme | 564–246–1 | +24.41 | +3.01% ± 2.50 | -4.10% | 0.608473 |
| market_context | 564–246–1 | +24.41 | +3.01% ± 2.50 | -4.10% | 0.608570 |
| early_context | 564–246–1 | +24.41 | +3.01% ± 2.50 | -4.10% | 0.609078 |

## Paired primary comparisons

Intervals are 99.6875% week-cluster bootstrap (8,000 draws), adjusted for eight context families × two comparators. ROI bounds are percentage points; positive LL gain is better.

| Context | Comparator | ROI difference [interval] | LL gain [interval] | Side flips |
|---|---|---|---|---:|
| hinge_0.5 | fixed_market_product | +0.38% [-2.27, +2.96] | +0.000057 [-0.003323, +0.003511] | 11 |
| hinge_0.5 | production | +0.99% [-4.78, +6.45] | +0.024103 [+0.009395, +0.039868] | 97 |
| hinge_1 | fixed_market_product | +0.85% [-1.38, +3.24] | -0.001080 [-0.006071, +0.003009] | 9 |
| hinge_1 | production | +1.46% [-4.12, +6.99] | +0.022966 [+0.007805, +0.039810] | 97 |
| hinge_1.5 | fixed_market_product | +0.26% [-1.83, +2.44] | +0.001473 [-0.002315, +0.007245] | 9 |
| hinge_1.5 | production | +0.87% [-5.17, +6.75] | +0.025519 [+0.009474, +0.041424] | 101 |
| hinge_2 | fixed_market_product | +0.33% [+0.00, +1.66] | +0.000050 [-0.000298, +0.000362] | 1 |
| hinge_2 | production | +0.94% [-5.41, +6.99] | +0.024096 [+0.009411, +0.039521] | 101 |
| multiscale | fixed_market_product | +0.56% [-1.50, +2.77] | -0.000194 [-0.002855, +0.002714] | 8 |
| multiscale | production | +1.17% [-4.32, +6.56] | +0.023852 [+0.008991, +0.039954] | 96 |
| one_extreme | fixed_market_product | +0.50% [-1.68, +2.74] | -0.000890 [-0.003233, +0.001509] | 8 |
| one_extreme | production | +1.11% [-4.38, +6.33] | +0.023156 [+0.008943, +0.038438] | 94 |
| market_context | fixed_market_product | +0.50% [-1.68, +2.74] | -0.000986 [-0.003436, +0.001520] | 8 |
| market_context | production | +1.11% [-4.38, +6.33] | +0.023060 [+0.008842, +0.038482] | 94 |
| early_context | fixed_market_product | +0.50% [-1.68, +2.74] | -0.001494 [-0.004716, +0.001806] | 8 |
| early_context | production | +1.11% [-4.38, +6.33] | +0.022552 [+0.008180, +0.038621] | 94 |

## Season results

| Arm | Season | Units | ROI | Log loss |
|---|---:|---:|---:|---:|
| production | 2023 | -0.24 | -0.09% | 0.656505 |
| production | 2024 | +33.13 | +12.27% | 0.605772 |
| production | 2025 | -17.51 | -6.46% | 0.632615 |
| fixed_market_product | 2023 | +3.86 | +1.43% | 0.636443 |
| fixed_market_product | 2024 | +20.21 | +7.48% | 0.581645 |
| fixed_market_product | 2025 | -3.75 | -1.38% | 0.604652 |
| q | 2023 | +4.12 | +1.53% | 0.627349 |
| q | 2024 | +15.11 | +5.60% | 0.587489 |
| q | 2025 | -18.05 | -6.66% | 0.609383 |
| hinge_0.5 | 2023 | +7.62 | +2.82% | 0.636550 |
| hinge_0.5 | 2024 | +24.66 | +9.14% | 0.581609 |
| hinge_0.5 | 2025 | -8.86 | -3.27% | 0.604410 |
| hinge_1 | 2023 | +7.62 | +2.82% | 0.636328 |
| hinge_1 | 2024 | +25.47 | +9.43% | 0.583169 |
| hinge_1 | 2025 | -5.85 | -2.16% | 0.606484 |
| hinge_1.5 | 2023 | +1.34 | +0.50% | 0.633353 |
| hinge_1.5 | 2024 | +24.66 | +9.14% | 0.581883 |
| hinge_1.5 | 2025 | -3.55 | -1.31% | 0.603086 |
| hinge_2 | 2023 | +3.86 | +1.43% | 0.636586 |
| hinge_2 | 2024 | +20.21 | +7.48% | 0.581388 |
| hinge_2 | 2025 | -1.05 | -0.39% | 0.604615 |
| multiscale | 2023 | +7.62 | +2.82% | 0.636073 |
| multiscale | 2024 | +23.11 | +8.56% | 0.581645 |
| multiscale | 2025 | -5.85 | -2.16% | 0.605608 |
| one_extreme | 2023 | +7.62 | +2.82% | 0.636602 |
| one_extreme | 2024 | +24.66 | +9.14% | 0.582164 |
| one_extreme | 2025 | -7.87 | -2.90% | 0.606647 |
| market_context | 2023 | +7.62 | +2.82% | 0.636645 |
| market_context | 2024 | +24.66 | +9.14% | 0.581987 |
| market_context | 2025 | -7.87 | -2.90% | 0.607072 |
| early_context | 2023 | +7.62 | +2.82% | 0.636676 |
| early_context | 2024 | +24.66 | +9.14% | 0.582402 |
| early_context | 2025 | -7.87 | -2.90% | 0.608152 |

## Fixed 0.1 interaction penalty sensitivity

These supplemental arms hold the interaction penalty identical to fixed_market_product. They separate feature changes from earlier-season penalty selection; they are not extra confirmatory winners.

| Arm | Units | ROI | Log loss |
|---|---:|---:|---:|
| hinge_0.5_fixed_r0.1 | +17.74 | +2.19% | 0.606478 |
| hinge_1_fixed_r0.1 | +30.06 | +3.71% | 0.605605 |
| hinge_1.5_fixed_r0.1 | +28.73 | +3.54% | 0.605986 |
| hinge_2_fixed_r0.1 | +23.02 | +2.84% | 0.607533 |
| multiscale_fixed_r0.1 | +22.34 | +2.75% | 0.605923 |
| one_extreme_fixed_r0.1 | +14.51 | +1.79% | 0.607517 |
| market_context_fixed_r0.1 | +26.54 | +3.27% | 0.607805 |
| early_context_fixed_r0.1 | +18.66 | +2.30% | 0.608259 |

## Context support

| Threshold | Home both extreme | Away both extreme |
|---:|---:|---:|
| 0.5 | 257 | 264 |
| 1.0 | 60 | 65 |
| 1.5 | 6 | 10 |
| 2.0 | 0 | 0 |

## Forward candidate

```json
{
  "arm": "hinge_1",
  "status": "exposed_historical_ROI_leader_for_forward_comparison",
  "main_family": "rates_core_avail_cs_peaks_nosacks",
  "main_half_life": 8.0,
  "main_ridge": 0.1,
  "pass_half_life": 16.0,
  "market_logit_coefficient": 1.0,
  "interaction_ridge": 0.1,
  "extras": [
    "product",
    "h1_pp",
    "h1_pn",
    "h1_np",
    "h1_nn"
  ],
  "selection_through_season": 2025,
  "production_deployed": false
}
```

Coefficients refit weekly using earlier weeks only. This ROI ranking is a development nomination, not confirmed superiority: the histories were already used for feature design. Bootstrap intervals condition on the prediction process and do not capture all research selection uncertainty. Historical quotes have no independent capture timestamps; prospective input and grading prices must be captured before kickoff.

Reproduce: `python research/context_battle.py`. Default inputs are the qualification cache; use `--input-dir research/qualified_output` for the earlier local cache. Full grids and fit audits remain in .nfl_cache; compact predictions, results, protocol and hashes are committed. Production and its ledger remain unchanged.

