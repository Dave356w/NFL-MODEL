# Context support cap protocol

Research only; production v1.16, frozen recipes and the forward ledger are
unchanged. Written and committed before any candidate backtest. Trigger: the
2026 week-5 SF@SEA snapshot (Seattle 93.9% against a 59.3% no-vig market), where
`pass_1sd_pn = -1.62` alone added +1.70 to the log-odds. That outcome and the
2023–2025 history were known when this was written. Before writing it, only
pregame feature values were examined: candidate cap levels and how many games
each would touch. No candidate was scored against outcomes.

## Rule

Keep production v1.16 exactly: raw h8 main profiles, raw h16 pass profiles,
no-vig moneyline logit offset with coefficient 1, shared pass product plus the
four signed 1 SD hinge contexts, main and context ridge 0.1, site penalty 0.01,
two-season fit decay, the same eligible training rows, and a joint refit of all
coefficients before every evaluation week using earlier weeks only.

Before each evaluation week, for each hinge context (`pass_1sd_pp`, `pn`, `np`,
`nn`) take the eligible earlier training rows that production's fit uses. The
cap is the K-th largest absolute value among those rows where the context is
non-zero. With fewer than K non-zero rows the cap is 0 and the hinge contributes
nothing. The context is then winsorized at ±cap in both the training rows and
the evaluation rows, and all coefficients are refitted. Caps read pregame
feature values only, never outcomes and never the evaluation week's rows. The
shared product and every other input are unchanged.

Fixed candidates, with no annual selection or other tuning:

* `cap_k5` (primary): every value a hinge can take is matched or exceeded by at
  least five training games.
* `cap_k1`: the observed training range. This guards only against
  extrapolation beyond the largest value ever trained on.
* `cap_k10`: a stricter support requirement.

## Evaluation

1. **Primary basis: 2023–2025** held-out walk-forward rows, the 816 games of
   `research/restore_v116_results/historical_reproduction.csv`. This is exposed
   development history, not forward evidence. The production arm must
   reproduce that file's probabilities within 1e-7.
2. **Diagnostic: 2026 games with outcomes in the frozen feature pack** (a
   current-season walk-forward). Reported separately and never pooled.
3. **Counterfactual replay: the 13 native v1.16 snapshots.** Each is replayed
   at its archived inputs and moneyline with every arm refitted on earlier
   weeks, and graded with the frozen results in `research/restore_v116_inputs`.
   The production arm must reproduce each archived probability within 1e-9.
   These replays are labelled counterfactual and are not new forward snapshots.

Inputs are the committed frozen pack
`research/shrinkage_results/frozen_training_features.csv.gz` and the frozen
snapshot and result copies above. No network access is needed.

Report, per arm:

* flat 1u moneyline ROI on the model's side (the goal metric): W-L-P, units,
  ROI ± SE, the market-correct null and the same-row market favorite;
* log loss and Brier;
* results by season;
* paired differences against production, with week-cluster bootstrap
  intervals (8,000 draws) at 98.33%, Bonferroni-adjusted over the three
  candidates within each metric;
* side flips and the units won or lost on flipped games;
* binding counts (evaluation games with any capped hinge) and the scores on
  those games.

Ties push in ROI and are excluded from proper scores.

## Decision rule, fixed in advance

`cap_k5` is **not supported** if either holds:

* its pooled 2023–2025 log-loss gain over production is ≤ 0;
* the bets where its side differs from production's lose units relative to
  production.

A positive gain whose interval includes zero is **unresolved**, not
established. Power is expected to be low, because the cap directly changes only
the few games with large hinge values (about 20 graded games over 2023–2026
for K=5). This test is development evidence on exposed history and cannot
provide forward confirmation. Adoption would be an owner decision and a new
`REVISION`.
