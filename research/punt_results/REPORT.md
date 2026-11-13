# Punts per possession and defensive forced-punt rate: earlier-season margin study

**Decision: retain for research; no production adoption supported.**

Basis: exposed historical reconstruction, not native forward evidence. Coefficients are pooled across all teams,
fitted on 2023 for 2024, 2023-24 for 2025, and 2023-25 for the separate 2026 diagnostic.
Primary source lag is two week indices; one-week sensitivity was fixed in advance. No ROI-selected settings.

All ATS returns below risk 1u at assumed -110; these differ from the public page's mixed-price returns.
Cover probability is a research discretized-Gaussian margin approximation, conditioned on no push,
not an existing saved production probability. Its scale is fitted on prior-season training residuals.

The intercept-only control separates adding the new statistics from merely recalibrating the base margin.
The original model retains its original mapped margin without this intercept adjustment.

## Primary and current-season comparisons

| Cohort | Arm | n | ATS W-L-P | Units | ROI ± SE | MAE | RMSE | Cover LL | Brier |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| 2024-25 | model_original | 544 | 316-223-5 | +64.27 | +11.81% ± 4.02 pp | 9.5956 | 12.4524 | 0.690362 | 0.248477 |
| 2024-25 | model_control | 544 | 286-253-5 | +7.00 | +1.29% ± 4.07 pp | 9.6394 | 12.4362 | 0.690796 | 0.248749 |
| 2024-25 | model_punts | 544 | 297-242-5 | +28.00 | +5.15% ± 4.06 pp | 9.6471 | 12.4601 | 0.691070 | 0.248805 |
| 2024-25 | market_original | 544 | 274-265-5 | -15.91 | -2.92% ± 4.08 pp | 9.6664 | 12.4393 | 0.693147 | 0.250000 |
| 2024-25 | market_control | 544 | 272-267-5 | -19.73 | -3.63% ± 4.08 pp | 9.6921 | 12.4387 | 0.693989 | 0.250420 |
| 2024-25 | market_punts | 544 | 278-261-5 | -8.27 | -1.52% ± 4.08 pp | 9.6632 | 12.4360 | 0.692809 | 0.249837 |
| 2024-25 | always_home | 544 | 272-267-5 | -19.73 | -3.63% ± 4.08 pp | — | — | 0.693147 | 0.250000 |
| 2024-25 | fair_cover | 544 | 274-265-5 | -15.91 | -2.92% ± 4.08 pp | 9.6664 | 12.4393 | 0.693147 | 0.250000 |
| 2026 | model_original | 137 | 75-56-6 | +12.18 | +8.89% ± 7.92 pp | 9.3650 | 11.9050 | 0.692460 | 0.249164 |
| 2026 | model_control | 137 | 67-64-6 | -3.09 | -2.26% ± 8.00 pp | 9.5289 | 12.0526 | 0.701907 | 0.254006 |
| 2026 | model_punts | 137 | 66-65-6 | -5.00 | -3.65% ± 8.00 pp | 9.5605 | 12.0339 | 0.702493 | 0.254338 |
| 2026 | market_original | 137 | 67-64-6 | -3.09 | -2.26% ± 8.00 pp | 9.4307 | 11.9784 | 0.693147 | 0.250000 |
| 2026 | market_control | 137 | 56-75-6 | -24.09 | -17.58% ± 7.93 pp | 9.5552 | 12.0877 | 0.700133 | 0.253491 |
| 2026 | market_punts | 137 | 59-72-6 | -18.36 | -13.40% ± 7.97 pp | 9.5740 | 12.0704 | 0.700726 | 0.253778 |
| 2026 | always_home | 137 | 56-75-6 | -24.09 | -17.58% ± 7.93 pp | — | — | 0.693147 | 0.250000 |
| 2026 | fair_cover | 137 | 67-64-6 | -3.09 | -2.26% ± 8.00 pp | 9.4307 | 11.9784 | 0.693147 | 0.250000 |

Market_original is the same-row always-favorite action baseline. Always-home has no margin forecast.
Fair_cover is a .5 probability benchmark; its displayed action uses the same favorite-on-zero-edge convention.
Cover rates exclude pushes; ROI includes pushes; skip counts and cover rates are in metrics.csv.

## Annual original/control/challenger

| Season | Arm | MAE | Cover LL | ATS W-L-P |
|---|---|---:|---:|---|
| 2024 | model_original | 9.4081 | 0.681657 | 165-103-4 |
| 2024 | model_control | 9.4657 | 0.681672 | 146-122-4 |
| 2024 | model_punts | 9.4027 | 0.679002 | 152-116-4 |
| 2025 | model_original | 9.7831 | 0.698970 | 151-120-1 |
| 2025 | model_control | 9.8131 | 0.699819 | 140-131-1 |
| 2025 | model_punts | 9.8914 | 0.703004 | 145-126-1 |
| 2026 | model_original | 9.3650 | 0.692460 | 75-56-6 |
| 2026 | model_control | 9.5289 | 0.701907 | 67-64-6 |
| 2026 | model_punts | 9.5605 | 0.702493 | 66-65-6 |

## Increment over the intercept-only control

Positive gain favors the new statistics. Paired whole-week bootstrap within season, 10,000 draws.
These are nominal 95% intervals, not corrected for the multiple feature families or prior research selection.

| Cohort | Offset | MAE gain [95%] | Cover LL gain [95%] |
|---|---|---|---|
| 2024-25 | model_punts_minus_control | -0.0076 [-0.0915, +0.0733] | -0.000274 [-0.005701, +0.004937] |
| 2024-25 | market_punts_minus_control | +0.0290 [-0.0515, +0.1076] | +0.001180 [-0.004063, +0.006334] |
| 2026 | model_punts_minus_control | -0.0316 [-0.1336, +0.0484] | -0.000586 [-0.007738, +0.005292] |
| 2026 | market_punts_minus_control | -0.0187 [-0.1432, +0.0903] | -0.000593 [-0.009206, +0.007024] |

## Fixed one-week-lag sensitivity

| Cohort | Arm | MAE | Cover LL | ATS W-L-P |
|---|---|---:|---:|---|
| 2024-25 | model_punts | 9.6342 | 0.690405 | 290-249-5 |
| 2026 | model_punts | 9.5809 | 0.703195 | 64-67-6 |

## Audit and limits

- Frozen forecasts and input hashes are in ../pressure_inputs; feature-source coverage is in the corresponding input directory.
- All source statistics precede the prediction by the declared lag; fit labels are from earlier seasons only.
- Historical source files were revised after games. Asset modification time is not original row publication time.
  The lag is a conservative assumption, not proof of point-in-time availability. Latest PBP has week-10 2026 data
  while PFR pressure ends in week 9; missing pressure is excluded, never treated as zero.
- PBP-defined opportunities and rounded PFR pressure percentages mostly agree; convention mismatches are counted in pressure_inputs/coverage.json.
- Reliability by five fixed probability bins is in reliability.csv. Pick accuracy is not calibration.
- Only two full evaluation seasons and a partially completed current season are available under the comparable mapped base.
- No production fit, notebook, lock, journal, public page or betting policy is modified.

This is a two-feature drive-stall study: offensive punts per possession and defensive punts forced per opponent possession.
It does not measure punt quality, return value, kicking accuracy or starting field position.
Turnovers and failed fourth downs can lower offensive punt rate without improving the offense.

## Reproduce

```sh
python research/punts_per_possession.py
```

This uses committed frozen aggregate inputs. See the protocol for raw reconstruction and source definitions.
