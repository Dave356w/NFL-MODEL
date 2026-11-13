# Fixed −2-point backup-team adjustment: 2026 results

The result depends on the backup definition. On the **137 completed published 2026 picks**, subtracting two points from teams whose projected QB was **below QB1 on the dated pregame chart** changes **75–56–6 to 74–57–6**, losing **1.91 units** at a common −110. The broader established-incumbent **replacement-starter proxy** changes the record to **78–53–6**, gaining **5.73 units**. Neither paired week-cluster interval establishes a gain, and the two definitions must remain separate.

The fixed amount was requested by the owner after the earlier 2026 residuals and historical experiments were known. This is a counterfactual diagnostic, not a new forward test. No production penalty, saved forecast, handicap, pick or journal is changed.

## Exact adjustment and grading

The primary test subtracts **2 points directly from the final mapped team-margin projection**:

```text
adjusted home margin
  = original final home margin − 2 × home backup flag + 2 × away backup flag
```

A home backup lowers the home projection; an away backup raises it. When both teams have backups the relative margin adjustment cancels. The original median map is neither refitted nor reapplied after the overlay, so a one-sided adjustment is exactly two points. The saved market handicap remains unchanged.

The adjusted ATS side is the side favored against that handicap. A zero edge takes the market favorite; a pick’em line with zero edge skips. Pushes occur when actual home margin equals the market line. Primary returns risk 1u per bet at a common **assumed −110** for both original and adjusted selections. ROI includes pushes, cover rate excludes them, and the −110 break-even cover rate is 52.4%.

This common-price basis isolates the change in selections. It differs from the website’s current +11.97u price-aware total, which combines pre-lock, estimated closing and assumed prices. A separate matched-side-price comparison appears below.

## Pregame classifications and coverage

* **Dated-chart backup:** projected QB below QB1 on the latest chart at least 24 hours before kickoff, no older than seven days. For saved forecasts, the chart must also predate the exact saved forecast. It misses backups promoted to QB1 and is not a complete backup census.
* **Replacement proxy:** projected QB differs from the incumbent with the most strictly earlier starts this season, with at least two incumbent starts and continued QB membership on the latest earlier roster. Ties in prior starts use the most recent start. This includes benchings and returning starters, and can stop identifying a long-running backup once he becomes incumbent.

These flags use the projected QB. Actual first QB-position passers from play-by-play are used only for correctness diagnostics and strictly earlier incumbent histories; stale schedule QB fields are not accepted as actual-starter evidence. Questionable blends and unknown classifications remain unresolved. An unresolved game receives **no overlay** in the full-pool result; it is also excluded from the separately reported known-classification and backup-involved subsets.

The published pool contains **137 completed games**: 121 historical replays, 14 owner-authorized recovered saved-board decisions and two native locks. There is one pending row in the source snapshot; it is excluded. Both teams can be classified in **132 games**, leaving five unchanged. The chart definition flags 18 team-games in 18 games. The replacement proxy flags 26 team-games in 24 games; two games have replacements on both sides and therefore zero net margin change.

For historical replay rows, QB projections come from the frozen replay availability inputs. Saved decisions use their exact saved lineup evidence rather than a reconstructed current lineup. The initial reproduction exactly matches the published **75–56–6** record.

## Full published 2026 results

| Arm | Games | W–L–P | Cover rate | Units | ROI ± SE |
|---|---:|---|---:|---:|---:|
| Original published selections | 137 | 75–56–6 | 57.3% | +12.18u | +8.9% ± 7.9 pp |
| −2, dated-chart backups | 137 | 74–57–6 | 56.5% | +10.27u | +7.5% ± 7.9 pp |
| −2, replacement proxy | 137 | 78–53–6 | 59.5% | +17.91u | +13.1% ± 7.9 pp |
| Same-game market favorite | 137 | 67–64–6 | 51.1% | −3.09u | −2.3% ± 8.0 pp |
| Same-game home side | 137 | 56–75–6 | 42.7% | −24.09u | −17.6% ± 7.9 pp |

For chart backups, seven picks change: **four wins become losses and three losses become wins**. Net gain is **−1.91u**, or **−1.39 percentage points of ROI**; the 95% season-week cluster interval for the per-game return difference is **−8.62 to +5.66 pp**.

For the replacement proxy, eleven picks change: **four wins become losses and seven losses become wins**. Net gain is **+5.73u**, or **+4.18 pp of ROI**; the corresponding 95% interval is **−7.34 to +14.27 pp**. Both intervals cross zero. The results do not justify selecting a backup definition or penalty using this 2026 performance.

### Backup-involved games only

| Definition | Games | Original W–L–P | Adjusted W–L–P | Original units | Adjusted units | Same-game favorite W–L–P | Same-game home W–L–P |
|---|---:|---|---|---:|---:|---|---|
| Dated-chart backup | 18 | 9–8–1 | 8–9–1 | +0.18u | −1.73u | 11–6–1 | 5–12–1 |
| Replacement proxy | 24 | 11–12–1 | 14–9–1 | −2.00u | +3.73u | 12–11–1 | 7–16–1 |

Adjusted ROI is **−9.6% ± 22.5 pp** on the 18 chart games and **+15.5% ± 19.0 pp** on the 24 replacement games. The correct-starter-only backup subsets have the same records here: all flagged projected starters in these eligible subsets match their actual first QB-position passer.

### Changed picks

All rows retain the original handicap. `W→L` means the original selection won while the adjusted selection lost; `L→W` is the reverse.

| Game | Chart-backup overlay | Replacement-proxy overlay |
|---|---|---|
| Week 2 MIN @ CHI | MIN → CHI, W→L | — |
| Week 2 SEA @ ARI | SEA → ARI, W→L | — |
| Week 3 ATL @ GB | — | ATL → GB, W→L |
| Week 3 SEA @ WAS | WAS → SEA, W→L | WAS → SEA, W→L |
| Week 3 TEN @ NYG | — | NYG → TEN, W→L |
| Week 4 IND @ WAS | IND → WAS, L→W | IND → WAS, L→W |
| Week 4 NYJ @ CHI | CHI → NYJ, W→L | CHI → NYJ, W→L |
| Week 5 NYG @ WAS | — | WAS → NYG, L→W |
| Week 6 BAL @ CLE | BAL → CLE, L→W | BAL → CLE, L→W |
| Week 7 DAL @ PHI | — | PHI → DAL, L→W |
| Week 8 PHI @ WAS | — | PHI → WAS, L→W |
| Week 9 BUF @ MIN | MIN → BUF, L→W | MIN → BUF, L→W |
| Week 10 WAS @ NYG | — | NYG → WAS, L→W |

The seven chart flips and eleven replacement flips overlap; they are alternative definitions, not additive adjustments. Full handicaps, margins, QB names, flags and before/after grades are retained in [flips.csv](flips.csv).

## Margin error and raw-projection sensitivity

The primary adjustment improves some bet thresholds without improving full-season squared margin error:

| Projection, all 137 games | MAE, points | MSE, points² |
|---|---:|---:|
| Original final mapped margin | 9.365 | 141.730 |
| Final mapped margin −2 for chart backups | 9.365 | 141.876 |
| Final mapped margin −2 for replacement proxy | 9.365 | 142.839 |
| Same-game market line | 9.431 | 143.482 |

The mean home-oriented residual changes from −1.32 points to −1.26 under the chart rule and −1.23 under the replacement rule; the market residual is −1.67. These home-oriented means are not backup-team-oriented residuals and can cancel across sides.

As a separate sensitivity, apply the same −2 overlay to the **continuous raw model margin** and choose a side directly from that adjusted raw margin, without a median map. The raw baseline is **70–61–6**. Chart backups leave it at **70–61–6**; the replacement proxy changes it to **69–62–6**. Raw-model MSE changes from 142.403 to 142.416 and 143.692 respectively. This is not a raw-adjustment-then-remapping experiment and should not be interpreted as one.

The replacement proxy’s apparent gain is therefore specific to moving the final mapped ATS selection thresholds in this exposed sample. It does not show a general improvement in team-margin forecasts.

### Backup-team-oriented residuals

To address the original full-team question, orient each residual toward the projected backup's team: **actual team margin minus its projected margin**. Negative means the backup team underperformed. These means differ from the home-oriented means above; their team-row counts can exceed game counts when both sides have replacements.

| Evidence / definition | Backup team-starts | Before −2 overlay | After overlay | Same-game market residual |
|---|---:|---:|---:|---:|
| Full published pool, dated-chart backup | 18 | −0.72 | +1.28 | −1.17 |
| Full published pool, replacement proxy | 26 | +0.62 | +2.31 | +0.81 |
| Archived saved decisions, dated-chart backup | 5 | −6.20 | −4.20 | −7.60 |

The broader full-season sample does not reproduce the large negative mean seen in the five archived chart-backup starts. In the full pool, the chart overlay moves the mean through zero; the replacement proxy was already positive and becomes more positive. Its ATS gain therefore does not demonstrate better calibration of the average backup-team margin. For the replacement proxy, two games have replacements on both sides: four team rows receive zero net relative-margin shift, which explains why the mean rises by less than two points. Individual oriented residuals are retained in [team_residuals.csv](team_residuals.csv).

## Matched-side-price sensitivity

Only rows where **both the original and adjusted selection have an available matched side price** enter this comparison. A flipped pick uses the newly selected side’s price at the same handicap, never the price originally attached to the other team. Missing prices are excluded symmetrically; no assumed −110 is added in this sensitivity.

| Published paired price cohort | Games | Original W–L–P | Adjusted W–L–P | Original units | Adjusted units |
|---|---:|---|---|---:|---:|
| Chart-backup overlay | 116 | 65–47–4 | 64–48–4 | +11.88u | +10.07u |
| Replacement-proxy overlay | 116 | 65–47–4 | 67–45–4 | +11.88u | +15.81u |

These prices include historical closing estimates as well as pre-lock captures. They are not uniformly lock-time prices.

## Separate archived saved-decision check

The earlier saved-pick audit contains **45 archived decisions** across model revisions, including 29 old v1.18 decisions whose public display was later replaced by the owner-authorized replay. This is not an extra 45 games to add to the published 137, and its original selections can differ from the published pool.

| Archived 45-game arm | Original W–L–P | Adjusted W–L–P | Original units | Adjusted units | Flips |
|---|---|---|---:|---:|---:|
| Chart-backup overlay | 22–23–0 | 23–22–0 | −3.00u | −1.09u | 1 |
| Replacement-proxy overlay | 22–23–0 | 26–19–0 | −3.00u | +4.64u | 4 |

The chart rule changes only BUF–MIN: MIN +3.5 loses; BUF −3.5 wins after the home projection changes from −3 to −5. Five chart-backup games go from 2–3 to 3–2. Ten replacement-involved archive games go from 4–6 to 8–2; two of those games have replacements on both sides and no net margin adjustment. One unresolved archived lineup is left unchanged.

The archive’s same-game favorite is 27–18 (+6.55u) and home side is 17–28 (−12.55u), at common −110. Source-specific saved candidate/lock versus recovered-board rows remain separate in [results.json](results.json); the archived aggregate is not homogeneous native forward evidence. Its few changed bets and small number of weeks cannot override the broader full-season and prior-season evidence.

## Reproduction and limits

The overlay is fixed at two points; no amount, threshold, chart definition or lineup subset was tuned to maximize 2026 results. The full-season pool includes reconstructed historical replays, and the owner requested this check after seeing 2026 outcomes. Treat the result as exposed current-season research. Existing prior-season tests did not establish a benefit from a blanket replacement term or a first-start fading term.

Uncertainty for paired return differences uses the existing 4,000-replicate season-week bootstrap, seed 20261113. ROI uncertainty in record tables is one standard error. Small archive cohorts contain few clusters, so their bootstrap intervals should not be treated as reliable independent confirmation.

```bash
python research/qb_minus2_2026.py
```

The ordinary run reads frozen [input games](../qb_minus2_2026_inputs/games.csv) and [QB classifications](../qb_minus2_2026_inputs/team_qbs.csv). `--prepare-inputs` rebuilds them from the sources and hashes in [provenance.json](../qb_minus2_2026_inputs/provenance.json). [per_game.csv](per_game.csv), [flips.csv](flips.csv) and [results.json](results.json) retain all comparisons. No production data or saved selection is rewritten.
