# R003 - Independent football-score support

**Recommendation: reject advancement of this fixed candidate.** Narrow historical hypothesis
fails the locked advancement rule; independent validation absent.

## Research question and specifications

Condition raw market-only PMFs on an additive joint scoring reachability mask. Safety/field-goal/TD/try generators include rare one-point safety points awarded to the opponent after a touchdown. No R001/R002 transform is combined with this candidate.

Primary comparator: empirical A_market; smooth is secondary. See PROTOCOL.md
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

Joint-NLL gain = **0.000286158 nats/game**, baseline 7.125371554,
candidate 7.125085396, n=816.
95% interval: [0.0002566189534217582, 0.0003194377444592511].
Two-new-contrast adjusted 97.5% interval: **[0.00025288570420257847, 0.0003247148043872129]**.
Nine-contrast sensitivity interval: [0.0002462591028399939, 0.00033836391770058637].
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
| empirical__R003_score_support | 816 | 7.125085 | 3.600085 | 3.547414 | 3.927311 | 3.970556 | 5.194011 | 5.028581 | 7.112870 | 7.240943 | 0.611359 | 0.211747 | 0.640421 | 0.024952 |
| smooth__A_market | 816 | 7.234615 | 3.640070 | 3.590072 | 3.966518 | 3.978443 | 5.187756 | 5.024364 | 7.101851 | 7.239583 | 0.609876 | 0.211209 | 0.642645 | 0.028734 |
| smooth__R003_score_support | 816 | 7.234278 | 3.639941 | 3.589873 | 3.966563 | 3.979384 | 5.187926 | 5.024390 | 7.101913 | 7.239680 | 0.609888 | 0.211213 | 0.642652 | 0.028729 |

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
| season_2023 | empirical__R003_score_support | 272 | 7.176150 | 5.179449 | 7.309762 | 7.285398 | 0.625401 | 0.025658 |
| season_2023 | smooth__A_market | 272 | 7.285870 | 5.181237 | 7.305340 | 7.290655 | 0.625165 | 0.029321 |
| season_2023 | smooth__R003_score_support | 272 | 7.285398 | 5.181599 | 7.305581 | 7.291237 | 0.625197 | 0.029314 |
| season_2024 | empirical__A_market | 272 | 7.082301 | 5.030930 | 7.102053 | 6.968117 | 0.596566 | 0.024884 |
| season_2024 | empirical__R003_score_support | 272 | 7.082041 | 5.030919 | 7.101957 | 6.967970 | 0.596565 | 0.024880 |
| season_2024 | smooth__A_market | 272 | 7.197353 | 5.018843 | 7.082717 | 6.964195 | 0.593188 | 0.028766 |
| season_2024 | smooth__R003_score_support | 272 | 7.197047 | 5.018797 | 7.082623 | 6.963941 | 0.593189 | 0.028762 |
| season_2025 | empirical__A_market | 272 | 7.117262 | 5.123531 | 6.926882 | 7.469468 | 0.612114 | 0.024323 |
| season_2025 | empirical__R003_score_support | 272 | 7.117065 | 5.123520 | 6.926892 | 7.469462 | 0.612115 | 0.024319 |
| season_2025 | smooth__A_market | 272 | 7.220620 | 5.118099 | 6.917497 | 7.463901 | 0.611281 | 0.028114 |
| season_2025 | smooth__R003_score_support | 272 | 7.220389 | 5.118078 | 6.917533 | 7.463863 | 0.611283 | 0.028111 |

Primary stability: `{"annual_gain": {"2023": 0.00040183612167548195, "2024": 0.00026002343820252143, "2025": 0.00019661504751978677}, "comparator": "A_market", "leave_one_season_out_gain": {"2023": 0.0002283192428611541, "2024": 0.0002992255845976344, "2025": 0.00033092977993900166}, "leave_one_week_out_gain_range": [0.0002740625936642849, 0.0002893971071596035], "positive_game_fraction": 1.0, "shape": "empirical", "top_ten_absolute_contribution_fraction": 0.10881357692123088}`.
Other shapes/comparators, leave-week/season estimates and largest observations
are retained in stability.json and influential_games.json. The support mask comes from a fixed scoring abstraction, not observed score frequency. It keeps valid rare (6,1)/(1,6) outcomes. Conditioning cannot claim a comprehensive possession/clock or administrative-rule model. Any unsupported realized observation would abort the run, with no NLL floor or row deletion. Exact-score improvement on supported outcomes is algebraically -log(1-removed_mass); a tiny positive effect is therefore not evidence of learned scoring patterns.

## Coverage and calibration

| arm | margin_coverage90 | margin_width90 | total_coverage90 | total_width90 | home_coverage90 | home_width90 | away_coverage90 | away_width90 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| empirical__A_market | 0.890931 | 41.410539 | 0.905637 | 42.090686 | 0.909314 | 30.102941 | 0.904412 | 29.178922 |
| empirical__R003_score_support | 0.890931 | 41.412990 | 0.905637 | 42.072304 | 0.909314 | 30.090686 | 0.904412 | 29.154412 |
| smooth__A_market | 0.888480 | 40.631127 | 0.903186 | 41.645833 | 0.904412 | 29.715686 | 0.898284 | 28.650735 |
| smooth__R003_score_support | 0.888480 | 40.638480 | 0.903186 | 41.612745 | 0.904412 | 29.698529 | 0.898284 | 28.633578 |

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
| empirical__R003_score_support | 812 | -0.905519 | -0.001115 | 0.024716 | -0.040995 |
| smooth__A_market | 812 | -4.552976 | -0.005607 | 0.024735 | -0.040995 |
| smooth__R003_score_support | 812 | -4.552976 | -0.005607 | 0.024735 | -0.040995 |
| control_favorite | 812 | 0.180119 | 0.000222 | 0.024663 | -0.040995 |
| control_underdog | 812 | -89.820146 | -0.110616 | 0.049336 | -0.040995 |

Flat 1u on the more probable decisive winner, tie pushes, four market pick'ems
excluded identically: 812 primary bets. Favorite/underdog same-row controls,
paired ROI intervals and negative-hold null are in moneyline_diagnostics.json.
No-vig moneyline proper-score comparisons are in a separate JSON. ROI is never
used for candidate selection. Missing timestamp verification prevents execution
claims. Actual spread/total/team-total prices are absent; their ROI is unavailable.

## Reproducibility and failure record

20 integrity checks pass: normalized/coherent PMFs, aligned identical
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

Locked decision gates: `{"adjusted_interval_positive": true, "all_seasons_positive": true, "integrity": true, "practical_gain": false, "secondary_tolerances": true}`.
Secondary tolerance violations: [].
No native prospective samples have been collected. No production promotion.

## Commands and next unresolved question

```bash
OPENBLAS_NUM_THREADS=1 python research/distribution_ablations.py R003
OPENBLAS_NUM_THREADS=1 python research/distribution_ablation_report.py R003
OPENBLAS_NUM_THREADS=1 python -m pytest tests -q
```

Rule provenance: research/RULE_SOURCES.json, official NFL Rule 11 (scoring/try)
and Rule 16 (current overtime context), read 2026-10-16. The reachability mask
and kernel are mathematical modeling choices, not tables of NFL probabilities.

Next unresolved hypothesis: test one preregistered football-score frequency model, with adequate rare-event/tail support and fresh independent evaluation; do not tune this mask using the observed gain.
