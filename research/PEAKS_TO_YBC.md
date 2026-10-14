# Replace lead/deficit peaks with yards before contact

Owner request, 2026-10-14: test removal of both lead/deficit peaks and replacement with yards before contact. Research only; production v1.18, its shadow lock and native ledger remain unchanged.

## Fixed specification

Primary challenger `peaks_to_ybc`: production's 29 fitted inputs minus `d__max_lead` and `d__max_deficit`, plus `d_ybc_off` and `d_ybc_def` (29 terms). Retain rush yards per attempt, site, availability, pass product and all four pass tails. Comparators: production (29 terms), and `no_peaks` with neither peaks nor YBC (27 terms), which isolates YBC's incremental value after removal.

Reuse Test 44's raw frozen PFR/nflverse team-game carries and yards before contact. Offensive and defensive-allowed YBC/carry profiles use strictly earlier weeks, half-life 8 team games, 0.5 offseason retention, three-season history, and four league pseudo-games. Differences are home minus away. Recompute full-precision profiles, do not use the rounded exported profile file. Missing evaluation YBC is an error, not a neutral imputation.

Use the frozen Test 36 training pack. Refit before every evaluation week with exactly production's eligible training rows, weighted log loss, scales, ridge 0.1 (site 0.01), fixed no-vig moneyline offset and final v1.18 favorite penalty. All models use identical games and quotes. Require reproduction of archived production forecasts to 1e-9 and an independent fit_composite comparison before accepting the experiment.

## Evaluation fixed before running

Historical bases, separately: 2021-22 and 2023-25. YBC source begins in 2018; do not invent earlier-period results. Frozen 2026 weeks 1-5 are diagnostic only. Every period and previous YBC/ablation result is already exposed; the new joint replacement has not been scored. This is development evidence, not an untouched or native-forward test.

Lead with flat 1u units/ROI +/- per-game SE, same-row market-favorite return and market-correct null, and paired ROI differences/side flips. Also report log loss, Brier, and paired week-cluster uncertainty. Ties push in returns and are excluded from binary scoring; paired eligible directional bets use the repository's convention. Include annual and total-band slices as descriptive.

Two fixed contrasts: challenger minus production and challenger minus no_peaks. Use 97.5% two-sided normal week-cluster intervals (Bonferroni for two contrasts within a basis). No across-era or across-metric confirmation claim. A development nomination requires positive LL gains on both historical bases against each comparator, with a positive lower bound on at least one historical basis for each comparator. Otherwise no nomination; unresolved intervals do not establish equivalence. Never tune on ROI or automatically adopt.

## Reproducibility

Freeze the archived 2021-25 production reference probabilities and input manifest before scoring. Hash inputs and executed sources. Store per-game forecasts, common-sample coverage, yearly results and paired comparisons. Keep transient ledger-integrity checks separate from deterministic outputs. Add a standalone replay workflow covering model/research dependencies, tests and frozen inputs; compare regenerated deterministic outputs with committed results. Runtime timing and live ledger metadata are not deterministic research results.
