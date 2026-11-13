# Saved-pick QB audit and logic repairs

Completed 2026 saved ATS decisions, weeks 6–10. This is a diagnostic of saved forecasts, not the pooled public replay record. No saved prediction or selection was rewritten.

## Result

Across 45 saved picks (90 team projections), 89 single-QB projections match the first actual QB-position passer and one is a Questionable blend. There are no confirmed wrong-starter selections in this saved sample. This does not prove selection is always correct outside this sample.

The earlier Dallas–Philadelphia “McKee vs Hurts” mismatch was a stale schedule QB field, not a model selection error: the actual play-by-play contains McKee’s 37 dropbacks. Schedule QB fields are not accepted as actual-starter evidence.

## Logic repairs

* A confirmed starter retains his full QB efficiency estimate despite a lingering Questionable injury tag. Unconfirmed Questionable projections still blend. Medical exclusions still block an ineligible starter.
* Historical starter labels follow the earliest actual QB-position passer, using passer play order and game-week roster positions. Gadget passers are excluded; unknown/conflicting positions or order stay unresolved. A starter who exits after an early dropback remains ahead of his replacement. A QB who leaves before any dropback cannot be identified from this measure.
* v1.23 has a new experiment/output/signature. Previous signatures and saved decisions remain intact. The v1.16 shadow receives its original first-dropback labels and its own training features. No backup prior, shrinkage or penalty was increased.

## Backup team-margin residuals

Residual = actual team margin minus projected team margin, flipped for an away backup. Negative means the backup’s team underperformed. Raw is the saved normal-mapped model projection; mapped is the locked weekly/annual ATS projection. These are distinct from passing-efficiency errors.

The strict descriptive cohort is a correctly selected QB listed below QB1 on the latest dated pregame chart (at least 24 hours before kickoff, available by the saved forecast, no older than seven days). It excludes promoted backups now listed QB1 and is not a census of all backups.

| Game / backup | Raw model residual | Locked mapped residual | Market residual |
|---|---:|---:|---:|
| 2026_07_CIN_BAL / T.Huntley | -19.45 | -19.00 | -19.00 |
| 2026_09_JAX_BAL / Joe Fagnano | -11.80 | -10.00 | -13.00 |
| 2026_09_CLE_NO / Shedeur Sanders | +2.47 | +4.00 | +2.00 |
| 2026_09_ARI_SEA / Drew Lock | +4.94 | +8.00 | +5.50 |
| 2026_09_BUF_MIN / C.Wentz | -14.65 | -14.00 | -13.50 |
| Mean, n=5 | -7.70 | -6.20 | -7.60 |

The raw residual averages −7.70 points, versus −7.60 for the same-game market. The five-game t interval for the raw mean is approximately −21.11 to +5.71 points; cases span only two weeks, so this is illustrative and not robust clustered inference. Negative team residuals do not identify QB talent as their cause.

These QBs’ realized passing efficiency averaged +0.42 net yards/dropback above their pregame estimates (two at least one yard worse, two at least one yard better, one closer). This is a different measurement from team-margin residual.

## ATS and margin comparison

All returns below risk 1u at a common −110 on the saved handicap. This isolates selections; it does not reproduce the public report’s mix of actual/estimated prices. Favorite and home controls use exactly the same games. Saved candidate/lock evidence is separate from owner-authorized recovered saved-board evidence. A late finalization of an already saved candidate remains in the former group.

| Evidence basis | n | Model W–L–P | Favorite W–L–P | Home W–L–P | Model ROI ± SE | Favorite ROI ± SE | Raw home-margin residual | Market home-margin residual |
|---|---:|---|---|---|---:|---:|---:|---:|
| native saved lock | 31 | 14-17-0 | 17-14-0 | 14-17-0 | -13.8% ± 17.3 pp | +4.7% ± 17.3 pp | -0.56 | -0.52 |
| recovered saved board | 14 | 8-6-0 | 10-4-0 | 3-11-0 | +9.1% ± 26.2 pp | +36.4% ± 23.9 pp | -5.11 | -4.93 |

The saved candidate/lock group’s mapped margin MAE is 10.29 points versus 9.90 for the market; recovered boards are 8.50 versus 8.86. The same-board market probability is available for 29 of 31 candidate/lock games: matched Brier is 0.2136 model versus 0.2022 market. For all 14 recovered boards it is 0.1336 versus 0.1270. These are diagnostic results across revisions, not fresh confirmation of one fixed model.

## Valuation slices

A large realized QB efficiency error means at least 1 net yard/dropback of absolute error with at least 15 actual starter dropbacks. It is an outcome-conditioned descriptive slice, not a pregame prediction that a QB will be poorly valued. Ordinary single-game variation makes this threshold common.

| Basis / correct-starter slice | n | Model W–L–P | Favorite W–L–P |
|---|---:|---|---|
| native saved lock / correct; large realized quality error | 25 | 13-12-0 | 13-12-0 |
| native saved lock / correct; quality unmeasurable | 1 | 1-0-0 | 1-0-0 |
| native saved lock / correct; smaller realized quality error | 4 | 0-4-0 | 3-1-0 |
| recovered saved board / correct; large realized quality error | 13 | 7-6-0 | 9-4-0 |
| recovered saved board / correct; smaller realized quality error | 1 | 1-0-0 | 1-0-0 |

## Sources and reproducibility

`games.csv` retains every saved handicap, selected side and margin error. `team_qbs.csv` retains saved/actual IDs, play-order label source, schedule discrepancy, chart rank, efficiency errors and team-oriented residuals. Historical boards match saved revision, forecast timestamp, raw projection and handicap, and their Git commit precedes the lock cutoff. Missing evidence is never filled with reconstructed current lineups. All 45 games have saved lineup evidence.

Actual QB outcomes come from nflverse play-by-play for 2021–2026 plus game-week roster positions, not schedule QB fields. The small derived passer-order extract and original download URLs/hashes are frozen in `research/qb_saved_pick_audit_inputs/`. Forecast journals, roster/depth inputs and historical board evidence are hashed in `provenance.json`.

```sh
python research/qb_saved_pick_audit.py --output-dir research/qb_saved_pick_audit_results
```

The prior-season residual fit is reported separately in `research/qb_backup_residual_results/REPORT.md`. It supplies a broader historical check of the negative recent team residuals; no blanket backup penalty is adopted.
