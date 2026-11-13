# Prior-season backup and replacement QB margin residual fit

The primary fit does **not establish a need for an additional backup penalty**. On 2021–2025 replays, the estimated replacement-team adjustment is **−0.70 points**, with a 95% week-cluster bootstrap interval of **−2.03 to +0.73**. The same-game market-line fit is **−1.09 points** [−2.44, +0.32]. Both effects remain unresolved. No production penalty is changed.

This measures the residual after the existing QB adjustment and all other model terms. It is not the full value of a backup relative to an incumbent, and it is not a causal estimate of quarterback quality.

## Outcome, cohorts and evidence

The residual is **actual team margin minus projected team margin**, oriented toward the replacement QB's team. Negative means that team performed worse than projected. It is measured in points, not net yards per dropback. A QB can exceed his passing-efficiency projection while his team falls short of its margin projection.

The longer-history cohort identifies a projected replacement for an established incumbent: the incumbent has at least two strictly earlier starts that season, has the most prior starts (latest start breaks ties), and remains at QB on the latest earlier roster. The projected QB must differ from him. This proxy includes benchings, excludes offseason changes, and can stop identifying a long-running backup once he becomes the incumbent. Missing roster coverage, ambiguous names and Questionable blends remain unresolved.

The separate 2025 cohort identifies a projected QB **below QB1 on the latest eligible dated depth chart**, at least 24 hours before kickoff and no more than seven days old. This is not a complete backup census: a promoted backup already listed QB1 is outside it. Usable timestamped charts begin in 2025, so this cohort has no earlier chart-based training seasons.

The base forecasts are frozen historical **v1.22 ten-term replays**, not live locks and not historical reruns of the v1.23 repair. Their weekly model coefficients used earlier games, but these seasons informed model development. The residual study is exposed development research, not new untouched confirmation. **2026 contributes no training or test outcomes here.**

Actual QB labels use the earliest positively identified QB-position passer in actual play order, using the game-week roster to exclude gadget passers. Schedule QB IDs are retained only for discrepancy auditing: they can retain stale projections and cannot serve as independent actual-starter evidence. This outcome label is used to audit starter correctness and to form strictly earlier incumbent histories, never as a feature for that same game. The label cannot identify a QB who started but exited before recording any dropback.

Coverage is **1,257 of 1,359 games** in 2021–2025; 102 games have unresolved pregame classifications. There are **402 replacement team-games** in the eligible primary fit. The 2025 chart cohort covers 256 games and 33 projected below-QB1 team-games.

## Fitted point adjustments

At the game level, avoiding duplicate outcomes when both teams have replacements:

```text
actual home margin − projected home margin
  = intercept + beta × (home replacement flag − away replacement flag)
```

A negative beta would support an additional replacement-team downgrade. The fitted intercept separately captures overall home-margin bias. The primary 2021–2025 raw-model fit has a +0.98-point intercept.

| Cohort and years | Games | Replacement team-games | Projection | Beta, points | 95% interval |
|---|---:|---:|---|---:|---:|
| Replacement proxy, 2021–2025 | 1,257 | 402 | Raw model | −0.70 | [−2.03, +0.73] |
| Same rows | 1,257 | 402 | Market line | −1.09 | [−2.44, +0.32] |
| Both projected starters matched actual, 2021–2025 | 1,114 | 296 | Raw model | −0.60 | [−2.22, +1.09] |
| Same matched-starter rows | 1,114 | 296 | Market line | −0.92 | [−2.57, +0.80] |
| Replacement proxy, mapped-eligible 2023–2025 | 759 | 253 | Raw model | −1.42 | [−3.04, +0.26] |
| Same mapped-eligible rows | 759 | 253 | Weekly mapped model | −1.76 | [−3.35, −0.13] |
| Same mapped-eligible rows | 759 | 253 | Market line | −1.82 | [−3.42, −0.17] |
| Projected below QB1 on dated chart, 2025 | 256 | 33 | Raw model | +2.96 | [−1.60, +7.81] |
| Same chart rows | 256 | 33 | Weekly mapped model | +3.13 | [−1.58, +8.11] |
| Same chart rows | 256 | 33 | Market line | +2.33 | [−2.24, +7.17] |

The mapped-model coefficient alone has a negative interval on its in-sample 2023–2025 cohort. The market coefficient is almost identical on those same games. That result does not demonstrate a model-specific missing backup downgrade. The raw-model and matched-starter estimates remain uncertain; the smaller strict-chart cohort points in the other direction and also remains uncertain.

Mapped margins are unavailable for 2021–2022 because the weekly median map requires two earlier seasons. Raw and market estimates on the matching 2023–2025 rows are shown to avoid comparing different eras as though they were the same sample.

## Observed team-margin residuals when the replacement QB was selected correctly

These are unadjusted team-oriented means, distinct from the regression beta. Each row requires that replacement team's projected QB to match its actual QB; the opponent need not also match.

| Season | Correct replacement team-games | Raw-model residual | Mapped-model residual | Market residual |
|---|---:|---:|---:|---:|
| 2021 | 44 | −1.70 | Unavailable | −2.17 |
| 2022 | 62 | +2.83 | Unavailable | +2.77 |
| 2023 | 70 | −0.00 | −0.30 | +0.00 |
| 2024 | 53 | −3.30 | −3.47 | −3.31 |
| 2025 | 89 | −0.81 | −0.94 | −1.34 |
| 2025 dated-chart cohort | 31 | +2.04 | +2.16 | +1.37 |

Replacement teams show negative residuals in some seasons, especially 2024, but the market shows much the same pattern. There is no stable historical six-point shortfall specific to this model.

## Previous-season walk-forward test

For 2023, 2024 and 2025, train the residual coefficients only on 2021 through the preceding season. Score three model arms: the original raw projection, intercept plus replacement correction, and an **independently fitted intercept-only correction**. The control's intercept is its own training mean residual, not the intercept borrowed from the joint regression. Nothing is fitted to ATS ROI.

| Test season | Training seasons | Prior-season fitted replacement beta | Test games | Replacement-involved games | MSE gain versus original | Incremental MSE gain versus intercept only |
|---|---|---:|---:|---:|---:|---:|
| 2023 | 2021–2022 | +0.49 | 250 | 80 | +2.12 | +0.06 |
| 2024 | 2021–2023 | +0.49 | 253 | 63 | −1.23 | −1.02 |
| 2025 | 2021–2024 | −0.65 | 256 | 81 | +1.00 | +0.19 |

Positive MSE gain means lower squared point error. The learned coefficient changes sign: earlier training did not consistently favor a downgrade.

Across **759 eligible test games**, intercept plus replacement correction improves MSE by **0.63 points²** versus the original [−1.25, +2.53], but worsens it by **0.26 points²** versus intercept only; incremental gain **−0.26** [−0.75, +0.24]. On the **224 replacement-involved games**, the incremental gain is **−0.86 points²** [−2.48, +0.80]. Neither interval establishes a predictive benefit from the replacement term.

| Arm, all 759 test games | MSE | MAE, points | Winner Brier score |
|---|---:|---:|---:|
| Original raw model | 158.71 | 9.72 | 0.20877 |
| Intercept + replacement | 158.08 | 9.75 | 0.20989 |
| Intercept only | **157.83** | 9.74 | 0.20964 |
| Market line | 159.82 | 9.77 | 0.21008 |

Lower is better. Winner probabilities here use each raw margin through the fixed 12.37-point normal mapping; they are not probabilities derived from the ATS median-map margins. Tied finals are excluded from Brier scoring. ATS pushes occur when the actual margin equals the market handicap.

### Same-game ATS results

Every priced comparison below uses the same historical market handicap and a common **flat 1u, assumed −110** basis. ROI includes pushes; uncertainty shown is one standard error, not a 95% interval. The −110 cover-rate break-even reference is 52.4%. These are continuous-margin research selections, not reconstructed native T−60 picks or evidence for production adoption.

| Arm | All 759 games, W–L–P | Units | ROI ± SE | Replacement-involved 224 games, W–L–P | Units | ROI ± SE |
|---|---|---:|---:|---|---:|---:|
| Original raw model | 369–376–14 | −40.55u | −5.3% ± 3.4 pp | 104–113–7 | −18.45u | −8.2% ± 6.3 pp |
| Intercept + replacement | 390–355–14 | −0.45u | −0.1% ± 3.4 pp | 122–95–7 | +15.91u | +7.1% ± 6.2 pp |
| Intercept only | 392–353–14 | +3.36u | +0.4% ± 3.4 pp | 124–93–7 | +19.73u | +8.8% ± 6.2 pp |
| Always market favorite | 386–359–14 | −8.09u | −1.1% ± 3.4 pp | 111–106–7 | −5.09u | −2.3% ± 6.3 pp |
| Always home | 376–369–14 | −27.18u | −3.6% ± 3.4 pp | 117–100–7 | +6.36u | +2.8% ± 6.3 pp |

The ATS improvement from the combined correction is also present, and slightly larger, in the intercept-only control. It cannot be attributed to a successful backup downgrade. Point-error comparisons and their paired intervals govern this residual experiment; ATS returns are descriptive.

## Decision and reproduction

**Leave the additional backup penalty unchanged.** The primary negative coefficient is unresolved, its historical sign is unstable, the strict chart cohort does not show a negative effect, and the previous-season test does not improve upon the independently fitted intercept-only control. This does not prove that backups need no adjustment; the existing model already has a QB term, and finer distinctions may matter.

Confidence intervals are 95% percentile bootstraps clustered by season-week, seed 20261113, 4,000 replicates. They describe these exposed historical cohorts and conditional walk-forward forecasts. There are only five primary seasons and one usable chart season; the chart and replacement definitions should not be pooled or treated as interchangeable.

Run from the repository root:

```bash
python research/qb_backup_residuals.py
```

The frozen [input games](../qb_backup_residual_inputs/games.csv), [source hashes](../qb_backup_residual_inputs/provenance.json), [full results](results.json), [team residuals](team_residuals.csv) and [walk-forward forecasts](walk_forward.csv) make the analysis reviewable. `--prepare-inputs` regenerates the input snapshot from the source files named in the provenance file; ordinary reproduction reads the frozen snapshot. The fit does not write production data, saved picks or penalty settings.
