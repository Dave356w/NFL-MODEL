# Points per possession for and allowed: earlier-season margin study

**Decision: retain for research; no production adoption supported.**

Basis: exposed historical reconstruction, not native forward evidence. Coefficients are pooled across all teams,
fitted on 2023 for 2024, 2023-24 for 2025, and 2023-25 for the separate 2026 diagnostic.
Primary source lag is two week indices; one-week sensitivity was fixed in advance. No ROI-selected settings.

All ATS returns below risk 1u at assumed -110; these differ from the public page's mixed-price returns.
Cover probability is a research discretized-Gaussian margin approximation, conditioned on no push,
not an existing saved production probability. Its scale is fitted on prior-season training residuals.

**Methodological caution:** the production map targets a median margin, while this study fits squared-error
mean residuals. Its intercept shifts toward a mean, not a refitted median. Earlier-season residual medians
are zero even though their means are positive. These are mean-margin overlays, not clean tests of adding
features to the production ATS median. See ../ats_median_audit/REPORT.md before interpreting adoption.

The intercept-only control separates adding the new statistics from merely recalibrating the base margin.
The original model retains its original mapped margin without this intercept adjustment.

## Primary and current-season comparisons

| Cohort | Arm | n | ATS W-L-P | Units | ROI ± SE | MAE | RMSE | Cover LL | Brier |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| 2024-25 | model_original | 544 | 316-223-5 | +64.27 | +11.81% ± 4.02 pp | 9.5956 | 12.4524 | 0.690362 | 0.248477 |
| 2024-25 | model_control | 544 | 286-253-5 | +7.00 | +1.29% ± 4.07 pp | 9.6394 | 12.4362 | 0.690796 | 0.248749 |
| 2024-25 | model_ppp | 544 | 282-257-5 | -0.64 | -0.12% ± 4.07 pp | 9.6737 | 12.4625 | 0.694678 | 0.250592 |
| 2024-25 | market_original | 544 | 274-265-5 | -15.91 | -2.92% ± 4.08 pp | 9.6664 | 12.4393 | 0.693147 | 0.250000 |
| 2024-25 | market_control | 544 | 272-267-5 | -19.73 | -3.63% ± 4.08 pp | 9.6921 | 12.4387 | 0.693989 | 0.250420 |
| 2024-25 | market_ppp | 544 | 267-272-5 | -29.27 | -5.38% ± 4.08 pp | 9.7509 | 12.4750 | 0.697319 | 0.252080 |
| 2024-25 | always_home | 544 | 272-267-5 | -19.73 | -3.63% ± 4.08 pp | — | — | 0.693147 | 0.250000 |
| 2024-25 | fair_cover | 544 | 274-265-5 | -15.91 | -2.92% ± 4.08 pp | 9.6664 | 12.4393 | 0.693147 | 0.250000 |
| 2026 | model_original | 137 | 75-56-6 | +12.18 | +8.89% ± 7.92 pp | 9.3650 | 11.9050 | 0.692460 | 0.249164 |
| 2026 | model_control | 137 | 67-64-6 | -3.09 | -2.26% ± 8.00 pp | 9.5289 | 12.0526 | 0.701907 | 0.254006 |
| 2026 | model_ppp | 137 | 65-66-6 | -6.91 | -5.04% ± 8.00 pp | 9.5527 | 12.0434 | 0.704653 | 0.255391 |
| 2026 | market_original | 137 | 67-64-6 | -3.09 | -2.26% ± 8.00 pp | 9.4307 | 11.9784 | 0.693147 | 0.250000 |
| 2026 | market_control | 137 | 56-75-6 | -24.09 | -17.58% ± 7.93 pp | 9.5552 | 12.0877 | 0.700133 | 0.253491 |
| 2026 | market_ppp | 137 | 57-74-6 | -22.18 | -16.19% ± 7.94 pp | 9.5833 | 12.0731 | 0.702052 | 0.254440 |
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
| 2024 | model_ppp | 9.4423 | 0.682203 | 146-122-4 |
| 2025 | model_original | 9.7831 | 0.698970 | 151-120-1 |
| 2025 | model_control | 9.8131 | 0.699819 | 140-131-1 |
| 2025 | model_ppp | 9.9051 | 0.707015 | 136-135-1 |
| 2026 | model_original | 9.3650 | 0.692460 | 75-56-6 |
| 2026 | model_control | 9.5289 | 0.701907 | 67-64-6 |
| 2026 | model_ppp | 9.5527 | 0.704653 | 65-66-6 |

## Increment over the intercept-only control

Positive gain favors the new statistics. Paired whole-week bootstrap within season, 10,000 draws.
These are nominal 95% intervals, not corrected for the multiple feature families or prior research selection.

| Cohort | Offset | MAE gain [95%] | Cover LL gain [95%] |
|---|---|---|---|
| 2024-25 | model_ppp_minus_control | -0.0343 [-0.1161, +0.0535] | -0.003882 [-0.008993, +0.001837] |
| 2024-25 | market_ppp_minus_control | -0.0588 [-0.1284, +0.0182] | -0.003331 [-0.007804, +0.001606] |
| 2026 | model_ppp_minus_control | -0.0238 [-0.2208, +0.1736] | -0.002746 [-0.016064, +0.010141] |
| 2026 | market_ppp_minus_control | -0.0281 [-0.1911, +0.1341] | -0.001919 [-0.012930, +0.008627] |

## Fixed one-week-lag sensitivity

| Cohort | Arm | MAE | Cover LL | ATS W-L-P |
|---|---|---:|---:|---|
| 2024-25 | model_ppp | 9.6850 | 0.695309 | 283-256-5 |
| 2026 | model_ppp | 9.5586 | 0.705095 | 67-64-6 |

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

This isolates offensive points per possession and opponent offensive points allowed per opponent possession.
It excludes defensive/return touchdowns and is not adjusted for opponents, game state or starting field position.
It is separate from the earlier finishing bundle, which also fitted red-zone and fourth-down terms.

## Reproduce

```sh
python research/points_per_possession.py
```

This uses committed frozen aggregate inputs. See the protocol for raw reconstruction and source definitions.
