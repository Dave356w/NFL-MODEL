# R002 - Explicit overtime-inspired transitions

**Recommendation: retain for research.** Narrow historical hypothesis
supported; independent validation absent.

## Research question and specifications

Replace R001's uniform decisive redistribution of excess raw tie mass with equal-weight +2/+3/+6 terminal score transitions. Prior-week tie rate and conditional winner probability stay equal to R001. No OT frequencies are estimated.

Primary comparator: empirical R001_tie_hurdle; smooth is secondary. See PROTOCOL.md
and registration_record.json for the design committed before either new run.
No hyperparameter search, training-grid selection or ROI-based selection.
No candidate was revised after viewing its historical results.

## Inputs, cutoff and periods

Exactly the R000 frozen schedule/total input and coefficient/history files from
NFL-MODEL base e93b936. No outcomes, lines, quotes or production data changed.
Original means/covariances/empirical neighbors use strictly earlier weeks.
Tie estimation uses a prior-week, six-season unweighted Jeffreys Beta(.5,.5)
rate; the support mask has no fitted parameters. Training begins 2013, original
mean-error prequential fitting begins 2015, evaluated forecasts begin 2017.
2017-22: 1,567 exposed supplementary games per arm; 2023-25: 816 historical
comparison games, 272 per season, 815 decisive winner scores; 2026 W1-5: 79
separate diagnostic games. Every arm has 2,462 predictions. All seasons are
already exposed; no independent validation/test or selection split exists.
The existing prior-week training procedure may fit on earlier weeks within an
evaluation season. Market capture timestamps are unknown: actual pregame
availability cannot be verified. This is conditional-on-input development.

## Primary paired comparison and multiplicity

Joint-NLL gain = **0.007087740 nats/game**, baseline 7.106782444,
candidate 7.099694704, n=816.
95% interval: [0.003590019874130441, 0.010804016967508105].
Two-new-contrast adjusted 97.5% interval: **[0.003099460964283191, 0.0113909289533918]**.
Nine-contrast sensitivity interval: [0.0022275230707010842, 0.0124363465291133].
10,000 paired whole-week resamples within season, seed 20261016; game-weighted
means with the resampled game denominator. Primary advancement requires >=.005
nats/game and an adjusted positive lower bound. Secondary scores, raw-A versus
R002 and smooth results are descriptive. The nine-comparison sensitivity only
covers the enumerated family; no interval eliminates prior research exposure.
The bootstrap holds forecasts fixed, not refitting overlapping training windows.

## Joint, marginal and event predictive scores

| arm | n | joint_nll | home_nll | away_nll | margin_nll | total_nll | home_crps | away_crps | margin_crps | total_crps | win_ll | win_brier | outcome_nll | p_tie |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| empirical__A_market | 816 | 7.125372 | 3.600210 | 3.547603 | 3.927294 | 3.969632 | 5.193831 | 5.028526 | 7.112852 | 7.240770 | 0.611353 | 0.211745 | 0.640421 | 0.024958 |
| empirical__R001_tie_hurdle | 816 | 7.106782 | 3.599412 | 3.546677 | 3.908705 | 3.968048 | 5.191622 | 5.026589 | 7.112072 | 7.241027 | 0.611353 | 0.211745 | 0.621831 | 0.004195 |
| empirical__R002_ot_transitions | 816 | 7.099695 | 3.600191 | 3.547675 | 3.901939 | 3.968380 | 5.192934 | 5.028763 | 7.111436 | 7.241554 | 0.611353 | 0.211745 | 0.621831 | 0.004195 |
| smooth__A_market | 816 | 7.234615 | 3.640070 | 3.590072 | 3.966518 | 3.978443 | 5.187756 | 5.024364 | 7.101851 | 7.239583 | 0.609876 | 0.211209 | 0.642645 | 0.028734 |
| smooth__R001_tie_hurdle | 816 | 7.212326 | 3.639741 | 3.589533 | 3.944230 | 3.976542 | 5.185690 | 5.022423 | 7.103851 | 7.239685 | 0.609876 | 0.211209 | 0.620356 | 0.004195 |
| smooth__R002_ot_transitions | 816 | 7.199869 | 3.639988 | 3.590119 | 3.932972 | 3.976799 | 5.186826 | 5.024836 | 7.100609 | 7.240630 | 0.609876 | 0.211209 | 0.620356 | 0.004195 |

Team NLL/CRPS are also reported as home/away averages. Natural-log losses;
multiclass H/T/A Brier sums three squared errors. Binary winner scores condition
on a decisive outcome; spread/total binary scores condition on a nonpush.
metrics.csv includes all metrics and valid counts, including tie LL/Brier and
derived team-location threshold diagnostics. Those locations are not traded
team-total quotes. candidate_vs_baseline.csv includes paired CIs for every
metric, coverage and width. Positive loss gain favors the candidate; coverage
and width differences are not themselves model rankings.

## Annual stability and influences

| sample | arm | n | joint_nll | team_crps | margin_crps | total_crps | win_ll | p_tie |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| season_2023 | empirical__A_market | 272 | 7.176552 | 5.179074 | 7.309620 | 7.284726 | 0.625384 | 0.025666 |
| season_2023 | empirical__R001_tie_hurdle | 272 | 7.155780 | 5.177203 | 7.308198 | 7.284942 | 0.625384 | 0.005222 |
| season_2023 | empirical__R002_ot_transitions | 272 | 7.150063 | 5.179780 | 7.308450 | 7.288230 | 0.625384 | 0.005222 |
| season_2023 | smooth__A_market | 272 | 7.285870 | 5.181237 | 7.305340 | 7.290655 | 0.625165 | 0.029321 |
| season_2023 | smooth__R001_tie_hurdle | 272 | 7.261337 | 5.179470 | 7.306146 | 7.290744 | 0.625165 | 0.005222 |
| season_2023 | smooth__R002_ot_transitions | 272 | 7.251432 | 5.181950 | 7.304318 | 7.294259 | 0.625165 | 0.005222 |
| season_2024 | empirical__A_market | 272 | 7.082301 | 5.030930 | 7.102053 | 6.968117 | 0.596566 | 0.024884 |
| season_2024 | empirical__R001_tie_hurdle | 272 | 7.060892 | 5.027494 | 7.098375 | 6.968065 | 0.596566 | 0.003787 |
| season_2024 | empirical__R002_ot_transitions | 272 | 7.049049 | 5.029515 | 7.098330 | 6.966446 | 0.596566 | 0.003787 |
| season_2024 | smooth__A_market | 272 | 7.197353 | 5.018843 | 7.082717 | 6.964195 | 0.593188 | 0.028766 |
| season_2024 | smooth__R001_tie_hurdle | 272 | 7.171953 | 5.015046 | 7.080966 | 6.963936 | 0.593188 | 0.003787 |
| season_2024 | smooth__R002_ot_transitions | 272 | 7.152509 | 5.017381 | 7.078567 | 6.962579 | 0.593188 | 0.003787 |
| season_2025 | empirical__A_market | 272 | 7.117262 | 5.123531 | 6.926882 | 7.469468 | 0.612114 | 0.024323 |
| season_2025 | empirical__R001_tie_hurdle | 272 | 7.103676 | 5.122621 | 6.929643 | 7.470074 | 0.612114 | 0.003574 |
| season_2025 | empirical__R002_ot_transitions | 272 | 7.099972 | 5.123250 | 6.927528 | 7.469986 | 0.612114 | 0.003574 |
| season_2025 | smooth__A_market | 272 | 7.220620 | 5.118099 | 6.917497 | 7.463901 | 0.611281 | 0.028114 |
| season_2025 | smooth__R001_tie_hurdle | 272 | 7.203687 | 5.117653 | 6.924442 | 7.464374 | 0.611281 | 0.003574 |
| season_2025 | smooth__R002_ot_transitions | 272 | 7.195666 | 5.118162 | 6.918943 | 7.465052 | 0.611281 | 0.003574 |

Primary stability: `{"annual_gain": {"2023": 0.005717191259771718, "2024": 0.011842722179074797, "2025": 0.0037033064879524215}, "comparator": "R001_tie_hurdle", "leave_one_season_out_gain": {"2023": 0.007773014333513608, "2024": 0.00471024887386207, "2025": 0.008779956719423257}, "leave_one_week_out_gain_range": [0.006407176985948388, 0.007657900726574543], "positive_game_fraction": 0.2647058823529412, "shape": "empirical", "top_ten_absolute_contribution_fraction": 0.08243869790210977}`.
Other shapes/comparators, leave-week/season estimates and largest observations
are retained in stability.json and influential_games.json. The frozen data contain only final scores, so this is an overtime-inspired mass-transport diagnostic, not a fitted regulation-to-OT simulator. The underlying raw PMF already includes overtime. The fixed terminal kernel omits many valid multi-score endings and has deliberately unestimated weights. Cap-boundary mass is explicitly retained in the R001 decisive shape and logged; near-cap representable increments are renormalized.

## Coverage and calibration

| arm | margin_coverage90 | margin_width90 | total_coverage90 | total_width90 | home_coverage90 | home_width90 | away_coverage90 | away_width90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| empirical__A_market | 0.890931 | 41.410539 | 0.905637 | 42.090686 | 0.909314 | 30.102941 | 0.904412 | 29.178922 |
| empirical__R001_tie_hurdle | 0.892157 | 41.694853 | 0.905637 | 42.085784 | 0.911765 | 30.225490 | 0.905637 | 29.302696 |
| empirical__R002_ot_transitions | 0.890931 | 41.410539 | 0.905637 | 42.132353 | 0.909314 | 30.113971 | 0.905637 | 29.203431 |
| smooth__A_market | 0.888480 | 40.631127 | 0.903186 | 41.645833 | 0.904412 | 29.715686 | 0.898284 | 28.650735 |
| smooth__R001_tie_hurdle | 0.888480 | 40.905637 | 0.903186 | 41.615196 | 0.906863 | 29.870098 | 0.899510 | 28.785539 |
| smooth__R002_ot_transitions | 0.888480 | 40.629902 | 0.904412 | 41.680147 | 0.904412 | 29.731618 | 0.898284 | 28.681373 |

50/80/90% coverage/width and paired differences are in metrics/paired outputs.
Integer equal-tail intervals include endpoint mass. Reliability bins include
counts, predicted/observed frequencies and Wilson binomial intervals for winner,
no-vig moneyline, H/T/A, spread, total and derived team-location thresholds.
Midpoint PIT deciles are descriptive for discrete distributions, not an exact
uniformity test. Only one tie in the primary sample: rare-event calibration
cannot be established. No post-result calibration map is fitted.

## Independent hypothetical moneyline diagnostics

| arm | bets | units | roi | roi_se | market_null |
| --- | --- | --- | --- | --- | --- |
| empirical__A_market | 812 | -0.905519 | -0.001115 | 0.024716 | -0.040995 |
| empirical__R001_tie_hurdle | 812 | -0.905519 | -0.001115 | 0.024716 | -0.040995 |
| empirical__R002_ot_transitions | 812 | -0.905519 | -0.001115 | 0.024716 | -0.040995 |
| smooth__A_market | 812 | -4.552976 | -0.005607 | 0.024735 | -0.040995 |
| smooth__R001_tie_hurdle | 812 | -4.552976 | -0.005607 | 0.024735 | -0.040995 |
| smooth__R002_ot_transitions | 812 | -4.552976 | -0.005607 | 0.024735 | -0.040995 |
| control_favorite | 812 | 0.180119 | 0.000222 | 0.024663 | -0.040995 |
| control_underdog | 812 | -89.820146 | -0.110616 | 0.049336 | -0.040995 |

Flat 1u on the more probable decisive winner, tie pushes, four market pick'ems
excluded identically: 812 primary bets. Favorite/underdog same-row controls,
paired ROI intervals and negative-hold null are in moneyline_diagnostics.json.
No-vig moneyline proper-score comparisons are in a separate JSON. ROI is never
used for candidate selection. Missing timestamp verification prevents execution
claims. Actual spread/total/team-total prices are absent; their ROI is unavailable.

## Reproducibility and failure record

22 integrity checks pass: normalized/coherent PMFs, aligned identical
game sets, strict prior-week cutoffs, positive realized probability and unchanged
protocol hash; experiment-specific invariants are in verification.json.
Full joint nonnegativity/normalization is asserted for every transformed game.
Baselines reconstructed to max error 2.13e-14.
Source/input/protocol hashes are archived. Tests and independent rerun records
are attached separately; a report is not a claim the full production suite ran.
R003's initial compressed predictions lacked a valid end-of-stream marker, so
its first report and repeat check failed before usable metrics were accepted.
The corrupt output and logs remain under R003/failures/initial_write/. The
root cause was not established. An engineering-only serialization revision now
builds and verifies the full gzip stream, fsyncs and atomically publishes it,
then validates the published bytes. The repaired R003 and its independent
repeat pass; R002 canonical prediction CSV is unchanged after that revision.
This is not a revised candidate, parameter search or independent second test.
No production files, deployed pages or betting ledgers are present in this
isolated workspace. Failures and every negative metric remain in this directory.

Locked decision gates: `{"adjusted_interval_positive": true, "all_seasons_positive": true, "integrity": true, "practical_gain": true, "secondary_tolerances": true}`.
Secondary tolerance violations: [].
No native prospective samples have been collected. No production promotion.

## Commands and next unresolved question

```bash
OPENBLAS_NUM_THREADS=1 python research/distribution_ablations.py R002
OPENBLAS_NUM_THREADS=1 python research/distribution_ablation_report.py R002
OPENBLAS_NUM_THREADS=1 python -m pytest tests -q
```

Rule provenance: research/RULE_SOURCES.json, official NFL Rule 11 (scoring/try)
and Rule 16 (current overtime context), read 2026-10-16. The reachability mask
and kernel are mathematical modeling choices, not tables of NFL probabilities.

Next unresolved hypothesis: execute the separately registered R003 ablation; a genuine mechanistic OT model additionally requires regulation/possession labels and a fresh evaluation cohort.
