# Offensive allowed and defensive forced pressure, additive: earlier-season margin study

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
| 2024-25 | model_additive_pressure | 544 | 308-231-5 | +49.00 | +9.01% ± 4.04 pp | 9.6125 | 12.4841 | 0.686936 | 0.246861 |
| 2024-25 | market_original | 544 | 274-265-5 | -15.91 | -2.92% ± 4.08 pp | 9.6664 | 12.4393 | 0.693147 | 0.250000 |
| 2024-25 | market_control | 544 | 272-267-5 | -19.73 | -3.63% ± 4.08 pp | 9.6921 | 12.4387 | 0.693989 | 0.250420 |
| 2024-25 | market_additive_pressure | 544 | 293-246-5 | +20.36 | +3.74% ± 4.06 pp | 9.6585 | 12.4596 | 0.688443 | 0.247682 |
| 2024-25 | always_home | 544 | 272-267-5 | -19.73 | -3.63% ± 4.08 pp | — | — | 0.693147 | 0.250000 |
| 2024-25 | fair_cover | 544 | 274-265-5 | -15.91 | -2.92% ± 4.08 pp | 9.6664 | 12.4393 | 0.693147 | 0.250000 |
| 2026 | model_original | 137 | 75-56-6 | +12.18 | +8.89% ± 7.92 pp | 9.3650 | 11.9050 | 0.692460 | 0.249164 |
| 2026 | model_control | 137 | 67-64-6 | -3.09 | -2.26% ± 8.00 pp | 9.5289 | 12.0526 | 0.701907 | 0.254006 |
| 2026 | model_additive_pressure | 137 | 69-62-6 | +0.73 | +0.53% ± 7.99 pp | 9.4976 | 11.9797 | 0.698307 | 0.252247 |
| 2026 | market_original | 137 | 67-64-6 | -3.09 | -2.26% ± 8.00 pp | 9.4307 | 11.9784 | 0.693147 | 0.250000 |
| 2026 | market_control | 137 | 56-75-6 | -24.09 | -17.58% ± 7.93 pp | 9.5552 | 12.0877 | 0.700133 | 0.253491 |
| 2026 | market_additive_pressure | 137 | 58-73-6 | -20.27 | -14.80% ± 7.96 pp | 9.5441 | 12.0195 | 0.697045 | 0.251937 |
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
| 2024 | model_additive_pressure | 9.4096 | 0.671424 | 155-113-4 |
| 2025 | model_original | 9.7831 | 0.698970 | 151-120-1 |
| 2025 | model_control | 9.8131 | 0.699819 | 140-131-1 |
| 2025 | model_additive_pressure | 9.8154 | 0.702276 | 153-118-1 |
| 2026 | model_original | 9.3650 | 0.692460 | 75-56-6 |
| 2026 | model_control | 9.5289 | 0.701907 | 67-64-6 |
| 2026 | model_additive_pressure | 9.4976 | 0.698307 | 69-62-6 |

## Increment over the intercept-only control

Positive gain favors the new statistics. Paired whole-week bootstrap within season, 10,000 draws.
These are nominal 95% intervals, not corrected for the multiple feature families or prior research selection.

| Cohort | Offset | MAE gain [95%] | Cover LL gain [95%] |
|---|---|---|---|
| 2024-25 | model_additive_pressure_minus_control | +0.0270 [-0.0680, +0.1245] | +0.003860 [-0.003435, +0.011264] |
| 2024-25 | market_additive_pressure_minus_control | +0.0337 [-0.0643, +0.1351] | +0.005545 [-0.001682, +0.012952] |
| 2026 | model_additive_pressure_minus_control | +0.0314 [-0.1684, +0.2105] | +0.003600 [-0.007668, +0.013985] |
| 2026 | market_additive_pressure_minus_control | +0.0111 [-0.2005, +0.2078] | +0.003088 [-0.009353, +0.014421] |

## Fixed one-week-lag sensitivity

| Cohort | Arm | MAE | Cover LL | ATS W-L-P |
|---|---|---:|---:|---|
| 2024-25 | model_additive_pressure | 9.6203 | 0.687096 | 304-235-5 |
| 2026 | model_additive_pressure | 9.4974 | 0.698252 | 65-66-6 |

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

Offensive pressure allowed and defensive pressure forced have separate additive coefficients; no matchup interaction is fitted.
This follow-up was selected after the original pressure and offensive-only diagnostics; it is not independent confirmation.

## Reproduce

```sh
python research/additive_pressure.py
```

This uses committed frozen aggregate inputs. See the protocol for raw reconstruction and source definitions.

## Requested LAC/PHI diagnostic

Positive change favors the named team. Feature-only excludes shared intercept recalibration.
All teams are saved in team_summary_2026.csv; this slice did not select the fit.

| Team | n | Feature-only change | Full change | Original MAE | Control MAE | Adjusted MAE | Pick flips vs original/control |
|---|---:|---:|---:|---:|---:|---:|---|
| LAC | 8 | -1.342 | -1.342 | 10.250 | 10.494 | 9.503 | 3/4 |
| PHI | 9 | +0.324 | +0.432 | 7.778 | 8.103 | 8.366 | 2/4 |

This additive follow-up was requested after the full-pressure and offensive-only arms. It is selected historical development, not fresh confirmation.

## Direct incremental value of defensive pressure

Positive gain favors adding defensive pressure to offensive pressure.
Same earlier-season fits and same paired games; no interaction.

| Cohort | Offset | MAE gain [95%] | Cover LL gain [95%] |
|---|---|---|---|
| 2024-25 | model | -0.0363 [-0.0729, +0.0026] | +0.000362 [-0.002602, +0.003423] |
| 2024-25 | market | -0.0117 [-0.0488, +0.0259] | +0.001456 [-0.002068, +0.005133] |
| 2026 | model | -0.0032 [-0.0147, +0.0087] | -0.000069 [-0.000735, +0.000638] |
| 2026 | market | -0.0096 [-0.0431, +0.0286] | -0.000251 [-0.002457, +0.002175] |
