# R001 - Tie mass calibration

**Recommendation: retain for research.** Historical hypothesis supported.
No independent validation or production qualification. Quote timestamps are unknown.

## Hypothesis, baseline and candidate

See PROTOCOL.md for the specification committed before execution. The primary
comparator is empirical market-only A; smooth A is a secondary transportability
check. Jeffreys Beta(0.5,0.5) tie frequency uses complete eligible games in the
current and five earlier seasons, strictly before each forecast week. The
diagonal and off-diagonal cells are each scaled to the new stratum probability;
their conditional shapes are unchanged. No hyperparameter search, validation
selection, test tuning, or ROI selection occurred. This is mass calibration,
not an overtime scoring model. Baseline coefficients and covariances are frozen
to R000; reconstruction is asserted against its forecasts to 1e-10.

## Sources, cutoffs and samples

Frozen committed schedule/total files from base e93b936, SHA-256 recorded in
R000. Scores include overtime. Integer scores 0-80; no outcome reaches 80.
Fit/covariance history uses the original prior-week procedure. Tie estimation
uses prior eligible realized ties only; no current-week updates. Logical week
cutoffs are proven; actual market timestamps and their pregame availability
cannot be proven from these files. This is a conditional-on-input historical
simulation. No new data, quote edits or outcome repairs.

Training begins in 2013; means start prequential fitting in 2015, scored forecasts
in 2017. 2017-22 has 1,567 exposed development games per arm; 2023-25 has 816
historical evaluation games (272 per season; 815 decisive outcomes); 2026 W1-5
has 79 separate diagnostic games. All four arms contain 2,462 games. No unseen
validation/test split exists; earlier weeks of an evaluation season can enter
later weekly fits. Four original information sets remain unchanged in R000.

## Primary comparison

Baseline-minus-candidate joint NLL = **0.018589 nats/game**,
paired week-bootstrap 95% interval **[0.013490147344642805, 0.02128705540142611]**.
Seven-contrast sensitivity interval: [0.010955703338697713, 0.02140081413139194].
10,000 whole-week resamples, within season, seed 20261016. One new primary
contrast; smooth and every secondary metric are descriptive. The seven-contrast
interval only adds this contrast to the original six; neither interval erases
earlier unrecorded selection or the fact this hypothesis was inspired by the
reported outcomes. Bootstrap conditions on the forecast path and does not
refit histories; overlap across training windows and rare ties limit inference.

## Historical evaluation scores

| arm | n | joint_nll | team_nll | margin_nll | total_nll | team_crps | margin_crps | total_crps | win_ll | win_brier | outcome_nll | p_tie |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| empirical__A_market | 816 | 7.125372 | 3.573907 | 3.927294 | 3.969632 | 5.111178 | 7.112852 | 7.240770 | 0.611353 | 0.211745 | 0.640421 | 0.024958 |
| empirical__R001_tie_hurdle | 816 | 7.106782 | 3.573044 | 3.908705 | 3.968048 | 5.109106 | 7.112072 | 7.241027 | 0.611353 | 0.211745 | 0.621831 | 0.004195 |
| smooth__A_market | 816 | 7.234615 | 3.615071 | 3.966518 | 3.978443 | 5.106060 | 7.101851 | 7.239583 | 0.609876 | 0.211209 | 0.642645 | 0.028734 |
| smooth__R001_tie_hurdle | 816 | 7.212326 | 3.614637 | 3.944230 | 3.976542 | 5.104056 | 7.103851 | 7.239685 | 0.609876 | 0.211209 | 0.620356 | 0.004195 |

Team NLL/CRPS are home/away averages; full individual marginals, conditional
nonpush spread/total scores, unconditional H/T/A scores, tie scores and counts
are in metrics.csv. Multiclass Brier is the sum of all three squared errors.
Winner LL/Brier condition on a decisive result; they remain unchanged by design.

## Season stability

| sample | arm | n | joint_nll | team_crps | margin_crps | total_crps | p_tie |
| --- | --- | --- | --- | --- | --- | --- | --- |
| season_2023 | empirical__A_market | 272 | 7.176552 | 5.179074 | 7.309620 | 7.284726 | 0.025666 |
| season_2023 | empirical__R001_tie_hurdle | 272 | 7.155780 | 5.177203 | 7.308198 | 7.284942 | 0.005222 |
| season_2023 | smooth__A_market | 272 | 7.285870 | 5.181237 | 7.305340 | 7.290655 | 0.029321 |
| season_2023 | smooth__R001_tie_hurdle | 272 | 7.261337 | 5.179470 | 7.306146 | 7.290744 | 0.005222 |
| season_2024 | empirical__A_market | 272 | 7.082301 | 5.030930 | 7.102053 | 6.968117 | 0.024884 |
| season_2024 | empirical__R001_tie_hurdle | 272 | 7.060892 | 5.027494 | 7.098375 | 6.968065 | 0.003787 |
| season_2024 | smooth__A_market | 272 | 7.197353 | 5.018843 | 7.082717 | 6.964195 | 0.028766 |
| season_2024 | smooth__R001_tie_hurdle | 272 | 7.171953 | 5.015046 | 7.080966 | 6.963936 | 0.003787 |
| season_2025 | empirical__A_market | 272 | 7.117262 | 5.123531 | 6.926882 | 7.469468 | 0.024323 |
| season_2025 | empirical__R001_tie_hurdle | 272 | 7.103676 | 5.122621 | 6.929643 | 7.470074 | 0.003574 |
| season_2025 | smooth__A_market | 272 | 7.220620 | 5.118099 | 6.917497 | 7.463901 | 0.028114 |
| season_2025 | smooth__R001_tie_hurdle | 272 | 7.203687 | 5.117653 | 6.924442 | 7.464374 | 0.003574 |

Empirical stability: `{"annual_gain": {"2023": 0.020771785657298498, "2024": 0.021409357527614067, "2025": 0.01358618642022301}, "decisive_game_gain_sum": 17.178292329215623, "leave_one_season_out_gain": {"2023": 0.01749777197391854, "2024": 0.017178986038760752, "2025": 0.02109057159245628}, "leave_one_week_out_gain_range": [0.018505554148040938, 0.02107288862804717], "positive_game_fraction": 0.9987745098039216, "shape": "empirical", "tie_game_gain_sum": -2.0095786766187462}`.
The exact joint NLL gain equals the tie-event Bernoulli gain: all improvement
comes from reweighting tie versus decisive mass, not better conditional exact
score prediction. Influential games and all leave-one-week/season checks are
archived. A single tie means unconditional tie calibration remains uncertain.
The observed tie-rate binomial 95% interval is [3.102624414707473e-05, 0.006808898096458874]; this interval is
descriptive under independent equal-rate trials, not a calibrated rare-event model.

## Coverage and calibration

| arm | margin_coverage90 | margin_width90 | total_coverage90 | total_width90 | home_coverage90 | home_width90 | away_coverage90 | away_width90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| empirical__A_market | 0.890931 | 41.410539 | 0.905637 | 42.090686 | 0.909314 | 30.102941 | 0.904412 | 29.178922 |
| empirical__R001_tie_hurdle | 0.892157 | 41.694853 | 0.905637 | 42.085784 | 0.911765 | 30.225490 | 0.905637 | 29.302696 |
| smooth__A_market | 0.888480 | 40.631127 | 0.903186 | 41.645833 | 0.904412 | 29.715686 | 0.898284 | 28.650735 |
| smooth__R001_tie_hurdle | 0.888480 | 40.905637 | 0.903186 | 41.615196 | 0.906863 | 29.870098 | 0.899510 | 28.785539 |

All 50/80/90% interval coverage and width values and paired differences are in
the machine-readable files. Equal-tail integer intervals include endpoint mass.
Reliability bins (winner, moneyline, unconditional H/T/A, spread, total and
derived team-location thresholds) include counts and Wilson binomial intervals.
Midpoint PIT deciles are descriptive for discrete distributions; they are not
randomized uniform PIT tests. No calibration map was fitted to evaluation labels.

## Independent betting diagnostics

| arm | bets | units | roi | roi_se | market_null |
| --- | --- | --- | --- | --- | --- |
| empirical__A_market | 812 | -0.905519 | -0.001115 | 0.024716 | -0.040995 |
| empirical__R001_tie_hurdle | 812 | -0.905519 | -0.001115 | 0.024716 | -0.040995 |
| smooth__A_market | 812 | -4.552976 | -0.005607 | 0.024735 | -0.040995 |
| smooth__R001_tie_hurdle | 812 | -4.552976 | -0.005607 | 0.024735 | -0.040995 |
| control_favorite | 812 | 0.180119 | 0.000222 | 0.024663 | -0.040995 |
| control_underdog | 812 | -89.820146 | -0.110616 | 0.049336 | -0.040995 |

Flat 1u on the most probable decisive winner, ties push; four pick'ems excluded
identically, n=812. Candidate side choices and settlements equal baseline by
construction. Favorite/underdog controls and paired intervals are archived.
Unknown quote timestamps invalidate executable-price or native-forward claims.
Spread/total and actual team-total prices are absent: their ROI is not estimated.
Derived team locations are only diagnostic thresholds, not traded team totals.
No-vig moneyline winner comparisons are included in R000 and unchanged by R001.

## Integrity, failures and limitations

14 output checks passed. Focused and capture-test logs are recorded in
research/VALIDATION.md after execution. No silent fallback is introduced.
Baseline covariance warm-up is inherited, logged, and absent in reported years.
Tie fit uses 1024-1599 prior games.
The constant within-week tie rate omits spread/total dependence and rule regimes;
the six-season window may mix overtime eras. Prior-week features are logical,
not proof the historical market inputs were available. The smooth lattice still
permits unusual football score pairs. Score cap and empirical sparsity remain.
This archive is not a full repository checkout; prior 517-test claims are not
reasserted as newly verified. No production files or external ledgers changed.

## Reproduce and next step

From the bundle root:

```bash
OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals.py --output-dir research/experiments/R000_reproduction
OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals_report.py --output-dir research/experiments/R000_reproduction
OPENBLAS_NUM_THREADS=1 python research/tie_hurdle.py
OPENBLAS_NUM_THREADS=1 python research/tie_hurdle_report.py
OPENBLAS_NUM_THREADS=1 python -m pytest tests -q
```

Highest-priority unresolved hypothesis: explicitly resolve tied score states
into plausible overtime final scores using a fixed transition model, preserving
joint coherence. Register it as R002 and obtain fresh evaluation. Do not optimize
transition rules on these results. Phase 2 residual experiments remain queued.
The forward capture implementation is offline infrastructure only; no genuine
provider quotes or prospective outcomes have been collected by this run.
