# Fixed first-start fade: prior-season test

**The fixed first-start fade is not supported for adoption.** Its fitted first-start amplitude is **−1.04 points**, with a 95% week-cluster bootstrap interval of **−2.98 to +0.92**. In previous-season walk-forward testing, it slightly worsens squared point error relative to both the independently fitted intercept-only control and the blanket replacement correction; neither difference is resolved statistically. **No production penalty is changed.**

This tests one prespecified shape: a two-start half-life. It does not establish that another shape would fail, and it does not justify selecting another half-life from these results.

## Definition and evidence

The outcome is actual home margin minus the existing raw model projection. The fitted regressor is home exposure minus away exposure, with one row per game, including games with replacements on both sides only once. A negative coefficient would mean an extra downgrade to the projected replacement's team beyond the existing model QB and team-profile terms.

Exposure is the established-incumbent replacement flag multiplied by `2^(-(projected stint-start number − 1)/2)`:

| Projected start in the current team stint | Exposure |
|---|---:|
| First | 1.000 |
| Second | 0.707 |
| Third | 0.500 |
| Fifth | 0.250 |

The projected start number counts consecutive actual starts by that projected QB in strictly earlier games for the same team and season. A bye does not break the sequence; a different QB starting or a season boundary resets it. A veteran returning after another QB starts begins a new stint. This measures **team-stint continuity, not career starts or NFL inexperience**. The replacement flag can disappear once the player becomes the team's established incumbent, so the exposure is not a complete learning curve for all backup appearances.

The underlying replacement definition, actual-label repair and coverage follow [the original residual protocol](../QB_BACKUP_RESIDUALS.md) and [residual report](../qb_backup_residual_results/REPORT.md). The sample contains **1,257 eligible games from 2021–2025**, with **402 projected replacement team-games**. It excludes 102 of the 1,359 base replay games with unresolved pregame classifications. Actual labels come from the first positively identified QB-position passer in actual play order; schedule IDs can retain stale projections and are not treated as actual-starter evidence.

These are frozen v1.22 historical replays. The seasons informed model development, and the earlier blanket-replacement results were already known before this separate candidate was specified. The comparisons are exposed development research, not new untouched confirmation. No 2026 outcome is used to fit or score this candidate.

## Pooled fit and previous-season estimates

The all-year regression has a **+0.97-point intercept** and a **−1.04-point fade amplitude** [−2.98, +0.92]. The amplitude's interval crosses zero. It is an additional residual correction at full exposure, not the total value of a backup relative to the incumbent.

Each test-year correction is fitted using only earlier seasons:

| Test year | Training years | Training games | First-start fade amplitude | Blanket replacement coefficient |
|---|---|---:|---:|---:|
| 2023 | 2021–2022 | 498 | +0.96 | +0.49 |
| 2024 | 2021–2023 | 748 | +0.82 | +0.49 |
| 2025 | 2021–2024 | 1,001 | −0.94 | −0.65 |

Earlier training would have produced a first-start **increase**, not a downgrade, for the first two test seasons. The negative all-year estimate is not a stable effect recovered by successive prior-season fits.

## Walk-forward prediction comparison

The test contains **759 eligible games in 2023–2025**, including the same **224 replacement-involved games** for every arm. The intercept-only control independently fits its training mean residual. The blanket term and fade term each fit their own intercept and coefficient on the same training rows. No coefficient or decay rate is chosen using ATS results.

Positive MSE gain means the candidate lowers squared point error:

| Evaluation cohort | Fade gain versus intercept only, points² | 95% interval | Fade gain versus blanket term, points² | 95% interval |
|---|---:|---:|---:|---:|
| All 759 games | −0.35 | [−1.02, +0.29] | −0.10 | [−0.39, +0.22] |
| 224 replacement-involved games | −1.19 | [−3.34, +1.06] | −0.33 | [−1.29, +0.73] |

The point estimates favor the controls, and all intervals cross zero. The prespecified requirement of a positive incremental gain interval is not met.

| Arm | All-game MSE | All-game MAE, points | All-game Brier | Replacement-game MSE |
|---|---:|---:|---:|---:|
| Original raw model | 158.71 | 9.718 | 0.20877 | 158.58 |
| Intercept only | **157.83** | 9.741 | 0.20964 | **156.40** |
| Blanket replacement term | 158.08 | 9.752 | 0.20989 | 157.26 |
| Fixed first-start fade | 158.18 | 9.754 | 0.20981 | 157.59 |
| Market line | 159.82 | 9.767 | 0.21008 | 158.90 |

Lower is better. Brier scores convert each continuous raw margin through the fixed 12.37-point normal mapping; they are not derived from the ATS weekly median-map margins. Tied finals are omitted from winner Brier scores. ATS pushes occur when actual margin equals the market handicap.

## Descriptive residuals by projected start number

These are **team-margin residuals**, oriented toward the projected replacement's team: actual margin minus projected margin. Negative means that team underperformed. They are not QB net-yards/dropback residuals.

The primary deployable fit uses pregame projected flags regardless of who eventually starts. The first table therefore includes projected replacements who did not actually start; a projected first start is not necessarily an actual first start.

| Projected stint-start number | Replacement team-games | Raw-model residual, points | Market residual, points |
|---|---:|---:|---:|
| 1 | 109 | −0.24 | −0.74 |
| 2 | 139 | −1.72 | −2.10 |
| 3 | 70 | +0.48 | +0.27 |
| 4 | 37 | −1.85 | −1.84 |
| 5 | 25 | +2.28 | +2.20 |
| 6 | 15 | +0.99 | +1.10 |
| 7 | 5 | +4.06 | +4.10 |
| 8 | 2 | −10.16 | −10.00 |

For the subset whose projected replacement actually started:

| Projected stint-start number | Correctly selected replacement team-games | Raw-model residual, points | Market residual, points |
|---|---:|---:|---:|
| 1 | 87 | −0.15 | −0.63 |
| 2 | 103 | −1.98 | −2.17 |
| 3 | 55 | +0.34 | +0.13 |

This correctness-conditioned subset is diagnostic, not a separately selected deployment fit. It does not show the largest shortfall at the first start, and the model and market residuals are similar. Later groups are small and do not trace a monotonic adaptation pattern. Do not tune the half-life or move a split point to fit these observed group means.

## Same-game ATS results

All arms use the same historical market handicap and flat **1u at assumed −110**. ROI includes pushes; uncertainty shown is one standard error. The reference break-even cover rate at −110 is 52.4%. These continuous-margin research selections are not native T−60 production picks.

| Arm | All 759 games, W–L–P | Units | ROI ± SE | Replacement-involved 224 games, W–L–P | Units | ROI ± SE |
|---|---|---:|---:|---|---:|---:|
| Original raw model | 369–376–14 | −40.55u | −5.3% ± 3.4 pp | 104–113–7 | −18.45u | −8.2% ± 6.3 pp |
| Intercept only | 392–353–14 | +3.36u | +0.4% ± 3.4 pp | 124–93–7 | +19.73u | +8.8% ± 6.2 pp |
| Blanket replacement term | 390–355–14 | −0.45u | −0.1% ± 3.4 pp | 122–95–7 | +15.91u | +7.1% ± 6.2 pp |
| Fixed first-start fade | 387–358–14 | −6.18u | −0.8% ± 3.4 pp | 120–97–7 | +12.09u | +5.4% ± 6.3 pp |
| Always market favorite | 386–359–14 | −8.09u | −1.1% ± 3.4 pp | 111–106–7 | −5.09u | −2.3% ± 6.3 pp |
| Always home | 376–369–14 | −27.18u | −3.6% ± 3.4 pp | 117–100–7 | +6.36u | +2.8% ± 6.3 pp |

The fade's descriptive ATS improvement over the original model does not establish a first-start effect: the independently fitted intercept-only arm performs better. The primary paired MSE comparisons also do not support the fade.

## Decision and reproduction

**Keep this candidate out of production.** The negative pooled amplitude remains uncertain, prior-season estimates change sign, and the fade does not improve on its controls in the walk-forward test. The hypothesis is unresolved; these results do not prove that early replacement starts have no extra risk.

Intervals use a 4,000-replicate season-week cluster bootstrap, seed 20261113. The half-life is fixed at two starts; no other decay rates were tried in this experiment. Play-calling, rushing, turnovers and field position are not separately attributed by this test.

Run from the repository root:

```bash
python research/qb_first_start_fade.py
```

The [protocol](../QB_FIRST_START_FADE.md), [full results](results.json), [input games with exposures](input_games.csv), [walk-forward forecasts](walk_forward.csv) and [team residuals](team_residuals.csv) record the candidate and its comparisons. Source hashes and frozen baseline inputs are linked from the [original residual report](../qb_backup_residual_results/REPORT.md). No production data, saved picks or penalty setting is rewritten.
