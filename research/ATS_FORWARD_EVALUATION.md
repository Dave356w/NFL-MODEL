# ATS fixed benchmark and native-forward audit (2026-10-16)

## Frozen comparisons

Production **boxscore-composite-v1.18**, moneyline decisions, and source snapshots remain unchanged. Preserve signed original spread, cutpoints `[3, 7, 10]`, integer band mappings, and exact zero-edge tolerance `1e-10`. The committed annual benchmark is:

| Target season | Prior-season map (<3 / 3–<7 / 7–<10 / 10+) |
|---|---|
| 2023 | 2 / 2 / 6 / 13 |
| 2024 | 2 / 4 / 6 / 13 |
| 2025 | 4 / 5 / 6 / 13 |
| 2026 | 4 / 5 / 7 / 13 |

The 2026 rule is trained through 2025. It does not refit based on 2026 results. Any new target season is fitted using prior seasons only. The coverage-constrained optimizer uses the same objective and tie-break as the existing benchmark. The defect fix applies when the unconstrained optimum violates the minimum 90% training selection rate but a feasible monotone runner-up exists. Historical mappings and returns must be compared against the committed artifacts before deployment.

The committed exposed-history baseline through 2026 Week 5 (2023–2026) is **895 eligible graded opportunities, 856 selections, 39 skips, 440 wins, 394 losses, 22 pushes, +6.00u**, ROI **+0.70%** per selection at *assumed* -110. 2026 Weeks 1–5: 79 opportunities, 73 selections, 6 skips, 39–31–3, +4.45u, +6.10% ROI. This is exposed historical development, **not independent validation**.

`fixed_bands.summary` reports **opportunities**, **selections**, **skips**, and **selection_rate**, alongside wins, losses, pushes, units and ROI. The same eligible population is used for both the raw and mapped spread. The skip decision is made **before** grading any push. Every graded eligible game is selected or skipped; unpriced games, missing mappings and unplayed games are outside this specific eligibility population and must never be folded into ROI as losses or wins.

## Native ATS snapshots

`research/ats_forward_shadow.py` continues to append immutable first-v1.18 pre-kickoff records to `data/ats_forward_shadow.jsonl`. No historical game is backfilled. The record keeps source snapshot hash and model revision; source forecast and kickoff times; archive time; original and mapped home-margin spreads; contemporaneously observed schedule spread; selected side; signed edge; exact-equality skip; a stable policy version and complete fitting rule; and the three-category ATS distributions.

The archived market spread has **no independently verified bookmaker quote timestamp**. The fixed -110 payout is a research proxy; it is not proof of an executable bet. The additional market-centered three-way probability control is saved *at lock time* to permit genuinely out-of-sample paired evaluation. Missing control values in older snapshots stay missing.

Scoring is on **all graded archived opportunities**, including model skips and outcomes that push. The mutually exclusive outcomes are home cover, away cover, push. Report multiclass log loss and multiclass Brier score against the saved market-centered control. ROI, W/L/P, selection rate and the full game denominator are secondary decision-policy diagnostics; no retrospective threshold search. Market accuracy and ATS probability quality are separate from moneyline profitability.

## Challenger and decision standard

The prior `research/ats_cover_probability.py` margin distribution and `research/experiments/R003_ats_calibration/` probability-calibration experiment already evaluate spread-side probabilities. **R003-AC1 did not establish an ATS edge**, and historical target prices were assumed rather than verified. No second model is promoted by this mechanics patch.

For a future *independent* direct-margin-residual challenger, register its features, training cutoffs, frozen score-distribution family, model-selection metric and locked decision rule **before** reading new game results. Residual target is `actual_home_margin - archived_market_home_margin`. Fit and select on only prior-week or earlier-season records. Compare new archived forecasts on exactly paired game opportunities, primarily by proper scores for cover/away/push with week-cluster uncertainty; only secondarily by a fixed -110 decision policy. Promote neither bands nor challenger on this already exposed history.
