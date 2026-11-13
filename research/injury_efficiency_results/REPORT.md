# Injury -> team efficiency -> frozen model -> ATS median

Implemented as an aggregate positional prototype, not a direct margin penalty. No live forecast, lock, journal, or production fit changes.

## Scope

Stage one learns average positional-absence effects from **2,348 team-games in 2020–2025**. Fresh exposure is current medical snap-weighted burden minus the burden in the games represented by the prior rolling profile. It controls for venue and opponent prior efficiencies; all training predates 2026.

The five propagated inputs are offensive first-down rate/INT percentage, defensive first-down rate/INT percentage, and opponent penalty yards. Own and opponent OL/WRTE/RB/DL/LB/DB changes have separate coefficients.

This estimates average historical replacement effects, not named starter/replacement talent. QB, passing-product contexts and net passing remain at their saved values. It therefore tests a real but partial efficiency pathway, not every injury mechanism.

## Saved-report 2026 replay

Both teams' latest reports must be complete before T60. Twelve eligible games; same saved handicap and -110 price for both arms. Saved core win probabilities reproduce within 1e-9 before any intervention. Frozen win coefficients, market offset, favorite penalty and earlier-week median rules are preserved.

| Arm | W-L-P | Units | Margin MAE |
|---|---|---:|---:|
| baseline | 5-7-0 | -2.45 | 7.917 |
| adjusted | 6-6-0 | -0.55 | 7.500 |

Two mapped medians change; only one ATS side changes. All profit difference comes from that one KC pick.

| Game | Raw margin before -> after | Median before -> after |
|---|---|---|
| 2026_09_NYG_PHI | -3.0194 -> -2.9568 | -5 -> -3 |
| 2026_09_NYJ_KC | 9.9050 -> 10.0414 | 6 -> 13 |

KC crosses the raw 10-point band boundary, producing a 6 -> 13 mapped-median jump from only 0.136 points of raw movement. This quantization sensitivity makes the apparent gain fragile. Philadelphia becomes more optimistic and its margin error worsens; LAC's mapped median is unchanged.

## Held-out efficiency errors

| Efficiency | Prior-profile MAE | Injury-adjusted MAE |
|---|---:|---:|
| def_fd | 5.8977 | 5.8435 |
| def_int | 2.5560 | 2.5498 |
| def_penalty | 20.9685 | 21.2397 |
| off_fd | 6.0187 | 5.9828 |
| off_int | 2.7839 | 2.7663 |

## Validation and limits

- Full suite: 1199 passed, 1 expected failure, 123 subtests passed. Four new checks cover zero fresh-exposure identity, exclusion of stage intercept/context corrections, physical rate bounds, planted effects and probability propagation.
- Saved model probabilities reproduce on every replay game. Stage training cutoff is 2025; saved win-model cutoffs and median rules precede each target week.
- A repeat reproduces the evaluated predictions. Notebook already in sync; 308 existing data files validate.
- Outcomes enter stage-one training only for 2020–25; 2026 actual efficiencies are used only to score diagnostics. Prior 2026 games may enter lagged profiles.
- Historical snap/report source-publication timing is unverified; this is report-backed reconstruction, not native execution evidence.
- The twelve-game sample spans only two weeks, and is too small for a promotion claim. No parameters or thresholds were selected on returns.
- Potential market double-counting, omitted individual replacement quality, game-state/opponent confounding and unmodified passing contexts remain limitations.

Reproduce with `python research/injury_efficiency.py`. Frozen 2026 box aggregates, stage coefficients/scales, training values/cutoffs, efficiency changes and per-game predictions are saved here.

The median map remains fitted on original, unadjusted historical forecasts.
Candidate-specific remapping from earlier injury-adjusted out-of-fold forecasts
has not been tested; this is a controlled input intervention using the frozen map.
