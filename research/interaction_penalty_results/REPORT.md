# Joint interaction-penalty test

Registered before computation: 3b1d797685e11bb2fb898801cf00b9876a989bd6.
Exposed 2023-2025 historical development; not native challenger evidence.
All coefficients refitted jointly before each week. Lower scores are better.

## Earlier-season selections

| Evaluation season | Selection through | Interaction penalty |
|---|---:|---:|
| 2023 | 2022 | 3 |
| 2024 | 2023 | 0.3 |
| 2025 | 2024 | 0.3 |
| 2026 | 2025 | 0.3 |

## Probability scores

| Season | Arm | N | Log loss | Brier | LL minus production | Brier minus production |
|---|---|---:|---:|---:|---:|---:|
| 2023 | production | 272 | 0.630622 | 0.220167 | +0.000000 | +0.000000 |
| 2023 | ridge_0.3 | 272 | 0.630005 | 0.219754 | -0.000616 | -0.000413 |
| 2023 | ridge_1 | 272 | 0.631016 | 0.220265 | +0.000394 | +0.000098 |
| 2023 | ridge_3 | 272 | 0.631975 | 0.220691 | +0.001353 | +0.000524 |
| 2023 | no_interactions | 272 | 0.632579 | 0.220954 | +0.001957 | +0.000787 |
| 2023 | selected_stronger | 272 | 0.631975 | 0.220691 | +0.001353 | +0.000524 |
| 2023 | market | 272 | 0.627349 | 0.218710 | -0.003273 | -0.001458 |
| 2024 | production | 272 | 0.585169 | 0.199123 | +0.000000 | +0.000000 |
| 2024 | ridge_0.3 | 272 | 0.585617 | 0.199329 | +0.000447 | +0.000206 |
| 2024 | ridge_1 | 272 | 0.586298 | 0.199624 | +0.001128 | +0.000501 |
| 2024 | ridge_3 | 272 | 0.586440 | 0.199677 | +0.001270 | +0.000554 |
| 2024 | no_interactions | 272 | 0.586366 | 0.199648 | +0.001197 | +0.000525 |
| 2024 | selected_stronger | 272 | 0.585617 | 0.199329 | +0.000447 | +0.000206 |
| 2024 | market | 272 | 0.587489 | 0.200162 | +0.002320 | +0.001039 |
| 2025 | production | 271 | 0.603441 | 0.209128 | +0.000000 | +0.000000 |
| 2025 | ridge_0.3 | 271 | 0.604889 | 0.209841 | +0.001448 | +0.000713 |
| 2025 | ridge_1 | 271 | 0.606169 | 0.210498 | +0.002728 | +0.001370 |
| 2025 | ridge_3 | 271 | 0.606709 | 0.210783 | +0.003268 | +0.001655 |
| 2025 | no_interactions | 271 | 0.607013 | 0.210943 | +0.003572 | +0.001815 |
| 2025 | selected_stronger | 271 | 0.604889 | 0.209841 | +0.001448 | +0.000713 |
| 2025 | market | 271 | 0.609383 | 0.212139 | +0.005942 | +0.003011 |
| all | production | 815 | 0.606414 | 0.209473 | +0.000000 | +0.000000 |
| all | ridge_0.3 | 815 | 0.606839 | 0.209641 | +0.000425 | +0.000168 |
| all | ridge_1 | 815 | 0.607829 | 0.210128 | +0.001415 | +0.000655 |
| all | ridge_3 | 815 | 0.608377 | 0.210383 | +0.001962 | +0.000910 |
| all | no_interactions | 815 | 0.608655 | 0.210514 | +0.002240 | +0.001041 |
| all | selected_stronger | 815 | 0.607497 | 0.209954 | +0.001082 | +0.000481 |
| all | market | 815 | 0.608072 | 0.210334 | +0.001658 | +0.000862 |

## Primary paired comparisons

95% whole-week bootstrap, stratified within season. Negative differences favor selected_stronger.

| Season | LL difference [95% interval] | Brier difference [95% interval] |
|---|---:|---:|
| 2023 | +0.001353 [-0.006861, +0.011151] | +0.000524 [-0.003303, +0.004896] |
| 2024 | +0.000447 [-0.001972, +0.002553] | +0.000206 [-0.000911, +0.001164] |
| 2025 | +0.001448 [-0.000372, +0.003316] | +0.000713 [-0.000128, +0.001574] |
| all | +0.001082 [-0.001805, +0.004458] | +0.000481 [-0.000856, +0.001995] |

## Registered gate

- every_season_both_better: FAIL
- both_paired_intervals_below_zero: FAIL
- not_worse_than_market: PASS

Historical gate failed. Keep production unchanged; no native launch from this test.

The primary selected rule and the no-interaction control have worse point estimates on both scores in every evaluation year. The primary paired intervals cross zero, so the size and direction of the population effect remain unresolved. This test does not qualify either stronger shrinkage or removing the interaction block; it does not prove the current interactions are universally reliable.

## ATS replay (secondary)

Same production prior-season mapping for every arm; flat 1u at assumed -110. Not lock-time execution returns.

| Season | Arm | W-L-P | Skips | Units | ROI |
|---|---|---:|---:|---:|---:|
| 2023 | production | 136-122-14 | 0 | +1.64 | +0.60% |
| 2023 | ridge_0.3 | 134-124-14 | 0 | -2.18 | -0.80% |
| 2023 | ridge_1 | 132-126-14 | 0 | -6.00 | -2.21% |
| 2023 | ridge_3 | 132-126-14 | 0 | -6.00 | -2.21% |
| 2023 | no_interactions | 131-127-14 | 0 | -7.91 | -2.91% |
| 2023 | selected_stronger | 132-126-14 | 0 | -6.00 | -2.21% |
| 2023 | market | 135-123-14 | 0 | -0.27 | -0.10% |
| 2024 | production | 142-126-4 | 0 | +3.09 | +1.14% |
| 2024 | ridge_0.3 | 141-127-4 | 0 | +1.18 | +0.43% |
| 2024 | ridge_1 | 141-127-4 | 0 | +1.18 | +0.43% |
| 2024 | ridge_3 | 141-127-4 | 0 | +1.18 | +0.43% |
| 2024 | no_interactions | 141-127-4 | 0 | +1.18 | +0.43% |
| 2024 | selected_stronger | 141-127-4 | 0 | +1.18 | +0.43% |
| 2024 | market | 136-132-4 | 0 | -8.36 | -3.07% |
| 2025 | production | 152-119-1 | 0 | +19.18 | +7.05% |
| 2025 | ridge_0.3 | 150-121-1 | 0 | +15.36 | +5.65% |
| 2025 | ridge_1 | 151-120-1 | 0 | +17.27 | +6.35% |
| 2025 | ridge_3 | 150-121-1 | 0 | +15.36 | +5.65% |
| 2025 | no_interactions | 150-121-1 | 0 | +15.36 | +5.65% |
| 2025 | selected_stronger | 150-121-1 | 0 | +15.36 | +5.65% |
| 2025 | market | 143-128-1 | 0 | +2.00 | +0.74% |

## Native evidence and integrity

{
  "saved_ats_locks": 16,
  "pregame_finalized_locks": 15,
  "recovered_locks": 1,
  "locks_with_exact_saved_first_snapshot_inputs": 0,
  "frozen_pack_latest_labeled_season": 2026,
  "frozen_pack_latest_labeled_week": 5,
  "native_challenger_predictions": 0,
  "native_challenger_graded": 0,
  "note": "Existing locks are production evidence only. No challenger existed at their cutoffs; no backfill or first-snapshot substitution."
}

Raw production reproduction max error: 1.03e-10.
Production source/data unchanged: True.

Native challenger sample is zero. Prior ATS outcomes cannot retrospectively validate a new challenger.
All historical results condition on exposed design choices. Fixed-arm intervals are descriptive, not alternate adoption gates.
Full coefficients, scaling, cutoffs, source hashes, predictions and selection scores accompany this report.
