# Pressure allowed/generated and matchup: earlier-season margin study

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
| 2024-25 | model_pressure | 544 | 309-230-5 | +50.91 | +9.36% ± 4.03 pp | 9.6279 | 12.4933 | 0.687540 | 0.247159 |
| 2024-25 | market_original | 544 | 274-265-5 | -15.91 | -2.92% ± 4.08 pp | 9.6664 | 12.4393 | 0.693147 | 0.250000 |
| 2024-25 | market_control | 544 | 272-267-5 | -19.73 | -3.63% ± 4.08 pp | 9.6921 | 12.4387 | 0.693989 | 0.250420 |
| 2024-25 | market_pressure | 544 | 298-241-5 | +29.91 | +5.50% ± 4.05 pp | 9.6467 | 12.4535 | 0.688127 | 0.247517 |
| 2024-25 | always_home | 544 | 272-267-5 | -19.73 | -3.63% ± 4.08 pp | — | — | 0.693147 | 0.250000 |
| 2024-25 | fair_cover | 544 | 274-265-5 | -15.91 | -2.92% ± 4.08 pp | 9.6664 | 12.4393 | 0.693147 | 0.250000 |
| 2026 | model_original | 137 | 75-56-6 | +12.18 | +8.89% ± 7.92 pp | 9.3650 | 11.9050 | 0.692460 | 0.249164 |
| 2026 | model_control | 137 | 67-64-6 | -3.09 | -2.26% ± 8.00 pp | 9.5289 | 12.0526 | 0.701907 | 0.254006 |
| 2026 | model_pressure | 137 | 60-71-6 | -16.45 | -12.01% ± 7.98 pp | 9.5503 | 12.0197 | 0.702774 | 0.254448 |
| 2026 | market_original | 137 | 67-64-6 | -3.09 | -2.26% ± 8.00 pp | 9.4307 | 11.9784 | 0.693147 | 0.250000 |
| 2026 | market_control | 137 | 56-75-6 | -24.09 | -17.58% ± 7.93 pp | 9.5552 | 12.0877 | 0.700133 | 0.253491 |
| 2026 | market_pressure | 137 | 56-75-6 | -24.09 | -17.58% ± 7.93 pp | 9.6029 | 12.0551 | 0.702187 | 0.254493 |
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
| 2024 | model_pressure | 9.4538 | 0.673423 | 156-112-4 |
| 2025 | model_original | 9.7831 | 0.698970 | 151-120-1 |
| 2025 | model_control | 9.8131 | 0.699819 | 140-131-1 |
| 2025 | model_pressure | 9.8020 | 0.701500 | 153-118-1 |
| 2026 | model_original | 9.3650 | 0.692460 | 75-56-6 |
| 2026 | model_control | 9.5289 | 0.701907 | 67-64-6 |
| 2026 | model_pressure | 9.5503 | 0.702774 | 60-71-6 |

## Increment over the intercept-only control

Positive gain favors the new statistics. Paired whole-week bootstrap within season, 10,000 draws.
These are nominal 95% intervals, not corrected for both feature families or prior research selection.

| Cohort | Offset | MAE gain [95%] | Cover LL gain [95%] |
|---|---|---|---|
| 2024-25 | model_pressure_minus_control | +0.0116 [-0.0798, +0.1035] | +0.003256 [-0.003987, +0.010575] |
| 2024-25 | market_pressure_minus_control | +0.0454 [-0.0502, +0.1433] | +0.005861 [-0.001469, +0.013370] |
| 2026 | model_pressure_minus_control | -0.0213 [-0.1618, +0.1251] | -0.000867 [-0.009744, +0.008155] |
| 2026 | market_pressure_minus_control | -0.0477 [-0.2008, +0.1216] | -0.002054 [-0.012582, +0.009443] |

## Fixed one-week-lag sensitivity

| Cohort | Arm | MAE | Cover LL | ATS W-L-P |
|---|---|---:|---:|---|
| 2024-25 | model_pressure | 9.6654 | 0.689334 | 298-241-5 |
| 2026 | model_pressure | 9.5206 | 0.700034 | 66-65-6 |

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

The three pressure coefficients and standardization values are in fits.json. The matchup coefficient changes sign
between annual fits; its contribution is not independently established by this joint three-term experiment.

## Reproduce

```sh
python research/pressure_margin.py
```

This uses committed frozen aggregate inputs. See the protocol for raw reconstruction and source definitions.
