# Variance-aware shrinkage and chronological ablation

Fixed protocol `410bbd2bb30fbc9fb3db19f90e98fead9a5be9a8` pushed before execution. Exposed historical development; not native forward evidence.

## Flat 1u returns and proper scores

| Basis | Arm | Bets | Units | ROI ± SE | Favorite units | Market null | LL | Market LL | Brier |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015-16 | production | 507 | -17.52 | -3.46% ± 3.38 | -26.01 | -2.40% | 0.640437 | 0.640486 | 0.224936 |
| 2015-16 | reliability | 507 | -9.07 | -1.79% ± 3.36 | -26.01 | -2.40% | 0.641820 | 0.640486 | 0.225640 |
| 2015-16 | chronological_prune | 507 | -14.54 | -2.87% ± 3.37 | -26.01 | -2.40% | 0.639862 | 0.640486 | 0.224712 |
| 2017-22 | production | 1559 | -24.22 | -1.55% ± 1.82 | -59.21 | -2.61% | 0.608107 | 0.605463 | 0.210072 |
| 2017-22 | reliability | 1559 | -34.90 | -2.24% ± 1.82 | -59.21 | -2.61% | 0.607130 | 0.605463 | 0.209616 |
| 2017-22 | chronological_prune | 1559 | -31.39 | -2.01% ± 1.81 | -59.21 | -2.61% | 0.608789 | 0.605463 | 0.210377 |
| 2023-25 | production | 812 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 0.606414 | 0.608072 | 0.209473 |
| 2023-25 | reliability | 812 | +8.90 | +1.10% ± 2.52 | +0.18 | -4.10% | 0.607245 | 0.608072 | 0.209831 |
| 2023-25 | chronological_prune | 812 | +19.45 | +2.39% ± 2.52 | +0.18 | -4.10% | 0.607474 | 0.608072 | 0.209965 |

## Primary paired changes versus production

97.5% normal week-cluster intervals, two primary comparisons per basis. Positive gain favors the challenger.

| Basis | Arm | LL gain ×1000 [interval] | ROI gain pp [interval] | Units gain | Side flips |
|---|---|---:|---:|---:|---:|
| 2015-16 | reliability | -1.382 [-4.192, +1.427] | +1.67 [-2.10, +5.43] | +8.45 | 17 |
| 2015-16 | chronological_prune | +0.575 [-0.966, +2.116] | +0.59 [-2.12, +3.30] | +2.98 | 8 |
| 2017-22 | reliability | +0.977 [-0.301, +2.256] | -0.68 [-2.14, +0.77] | -10.68 | 31 |
| 2017-22 | chronological_prune | -0.682 [-2.479, +1.114] | -0.46 [-2.08, +1.16] | -7.17 | 32 |
| 2023-25 | reliability | -0.830 [-2.943, +1.282] | -2.48 [-5.17, +0.20] | -20.16 | 18 |
| 2023-25 | chronological_prune | -1.059 [-3.062, +0.943] | -1.18 [-3.40, +1.04] | -9.61 | 16 |

## Feature sampling variability and shrinkage

Whole prior games are resampled together. Estimates hold the league prior fixed and are conditional on observed opponents/personnel. They do not isolate coaching or distinguish all genuine form changes from sampling noise. Raw variances have different units and must not be ranked across different statistics.

| Feature | Median reliability 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| off plays | 0.566 | 0.520 | 0.463 |
| off pass yds/play | 0.612 | 0.636 | 0.677 |
| off rush yds/att | 0.554 | 0.531 | 0.575 |
| off 1st-down rate | 0.740 | 0.702 | 0.728 |
| off fumbles | 0.112 | 0.151 | 0.073 |
| off INT % | 0.361 | 0.422 | 0.228 |
| off penalty yds | 0.406 | 0.338 | 0.343 |
| def plays | 0.537 | 0.388 | 0.322 |
| def pass yds/play | 0.503 | 0.536 | 0.427 |
| def rush yds/att | 0.470 | 0.388 | 0.374 |
| def 1st-down rate | 0.469 | 0.578 | 0.519 |
| def fumbles | 0.186 | 0.169 | 0.106 |
| def INT % | 0.285 | 0.309 | 0.337 |
| def penalty yds | 0.338 | 0.273 | 0.184 |
| max_lead | 0.511 | 0.527 | 0.591 |
| max_deficit | 0.449 | 0.461 | 0.481 |

Availability, QB, site and pass interactions are not assigned fabricated bootstrap measurement variances. Their grouped refit ablations are included below. Coefficient trajectories are in fit_audit.csv.gz; temporal coefficient movement includes actual model adaptation, not just uncertainty.

## Fixed group-drop diagnostics

Each cell: LL gain ×1000 on removing/refitting the group [99.375% interval]; units change. These exposed diagnostic arms do not choose the pruning challenger on evaluation results.

| Group removed | 2015-16 | 2017-22 | 2023-25 |
|---|---:|---:|---:|
| offense_box_rates | +0.194 [-4.697, +5.086]; +5.53u | +0.820 [-0.779, +2.420]; -19.24u | -0.262 [-2.585, +2.061]; -11.99u |
| defense_box_rates | +0.231 [-2.462, +2.924]; +10.76u | +1.071 [-0.659, +2.801]; -4.80u | -1.915 [-5.491, +1.661]; -21.06u |
| qb_projection | +0.656 [-0.640, +1.952]; +4.62u | +0.153 [-1.021, +1.326]; +6.25u | +0.255 [-0.950, +1.461]; -0.98u |
| unit_absences | -0.242 [-7.106, +6.622]; -4.18u | +0.397 [-2.175, +2.970]; -23.63u | -0.008 [-1.849, +1.832]; -9.23u |
| lead_deficit_peaks | +0.071 [-1.355, +1.497]; +6.71u | +0.208 [-0.307, +0.724]; -6.05u | +0.366 [-0.409, +1.140]; +0.00u |
| pass_matchup_product | +0.153 [-0.121, +0.427]; +0.03u | +0.057 [-0.534, +0.648]; -9.73u | -0.992 [-2.389, +0.405]; -0.30u |
| pass_tail_hinges | +0.119 [-2.067, +2.306]; +1.76u | +0.467 [-1.864, +2.799]; -13.28u | -1.030 [-6.072, +4.012]; -9.74u |
| home_field | +0.472 [-1.309, +2.254]; +1.35u | +0.516 [-0.626, +1.658]; -11.78u | +0.542 [-0.567, +1.651]; -4.28u |

## Chronological pruning choices

At most one group removed, based on up to three earlier completed OOF seasons; a minimum of two is required. The earlier-season paired one-SE benefit gate precedes the within-one-SE simplicity choice.

| Evaluation season | Earlier seasons | Selected |
|---|---|---|
| 2015 | 2014 | production |
| 2016 | 2014,2015 | drop_defense_box_rates |
| 2017 | 2014,2015,2016 | drop_defense_box_rates |
| 2018 | 2015,2016,2017 | drop_pass_tail_hinges |
| 2019 | 2016,2017,2018 | drop_offense_box_rates |
| 2020 | 2017,2018,2019 | drop_home_field |
| 2021 | 2018,2019,2020 | drop_defense_box_rates |
| 2022 | 2019,2020,2021 | drop_defense_box_rates |
| 2023 | 2020,2021,2022 | drop_defense_box_rates |
| 2024 | 2021,2022,2023 | drop_defense_box_rates |
| 2025 | 2022,2023,2024 | drop_home_field |

## Forecast dispersion and calibration

Departure variance is variance of final model-minus-market log odds. Lower dispersion is not itself better forecasting. Calibration fits are descriptive and never adjust these predictions.

| Basis | Arm | Departure variance | Calibration intercept | Calibration slope |
|---|---|---:|---:|---:|
| 2015-16 | production | 0.02787 | +0.013 | 0.918 |
| 2015-16 | reliability | 0.02168 | +0.012 | 0.908 |
| 2015-16 | chronological_prune | 0.02434 | +0.010 | 0.921 |
| 2017-22 | production | 0.02309 | -0.010 | 1.063 |
| 2017-22 | reliability | 0.01968 | -0.012 | 1.067 |
| 2017-22 | chronological_prune | 0.01838 | -0.014 | 1.061 |
| 2023-25 | production | 0.03323 | -0.003 | 1.137 |
| 2023-25 | reliability | 0.02633 | -0.001 | 1.109 |
| 2023-25 | chronological_prune | 0.02880 | -0.007 | 1.121 |

## Decisions and limits

- **reliability**: No nomination; improvement unresolved.
- **chronological_prune**: No nomination; improvement unresolved.

Archived baseline maximum error 1.11e-10, independent fit maximum error 2.22e-16, reconstructed main-input maximum error 4.97e-14.

Only main raw h8 box/peak inputs receive reliability shrinkage. The existing four pseudo-games and fit standardization remain; constant per-feature scaling would cancel, so point-in-time factors vary across rows. 128 multiplier-bootstrap draws are a fixed approximation. Selection and source/design uncertainty are not fully reflected in score intervals. Historical quotes have unknown capture times. Return SE is per-game; paired intervals cluster by week. Ties push in returns and are omitted from binary scores. Market pick-ems follow existing paired directional conventions. No current-season or native-forward result is claimed. No production recipe, forecast, signature or native ledger changed.

Full tables include annual results, all group ablations, weekly coefficients/cutoffs, variance components and per-game forecasts. Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/variance_ablation.py`.
