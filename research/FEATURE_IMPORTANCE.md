# Test 38 protocol: feature importance, interactions and correlation structure (diagnostic)

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner request 2026-10-14. Parts B–D below are committed and pushed before any of them is
computed. Part A was computed and seen first and is disclosed as post hoc.

## Question

Which of the model's inputs earn their place in its accuracy, within total contexts? Do pairs of
inputs interact in ways the additive model misses? How are the inputs, their contributions and
their per-game errors correlated?

## Exposure, disclosed in advance

* **Part A was computed before this protocol.** It is the per-game attribution in the session
  that led to it. Seen: every feature's contribution-removal effect by context on 2015–16, 2017–22,
  2023–25 and the native week-5 games, the culprit and helper tallies, and the worst misses. Small
  same-sign drags appeared for largest deficit (mid totals), the home-field adjustment (all, mid and
  low totals), OL absences (low totals) and the QB projection. The pass tail hinges caused the
  largest single-game misses and hits, with a net near zero.
* Contribution-removal effects correlate with drop-column importance (part B), so part B is not blind.
* All three historical bases have been scored many times (Tests 32–37).
* The total bands are Test 37's, chosen after aggregate slices were seen.

## Bases, never pooled

2015–16 (510 binary games), 2017–22 (1,559) and 2023–25 (815). Each uses v1.16 refit before every
week from earlier rows only, from the frozen packs (`out_of_sample_results/frozen_features_2013_2020.csv.gz`
for 2015–20 and `shrinkage_results/frozen_training_features.csv.gz` for 2021–25), then the v1.18
favorite penalty. Production must reproduce the published forecasts to 1e-9 (2017–20
`predictions.csv`, 2021–22 `retro_ledger.csv`, 2023–25 `historical_reproduction.csv`). The native
week-5 games appear in part A only. Contexts are all games and Test 37's total bands. Binary
results only; ties push in ROI.

## A. Per-game attribution (post hoc, descriptive)

For game i and input j with fitted contribution c_ij (log-odds), the effect is
`LL(production without c_ij) − LL(production)`: positive means j made that forecast more accurate.
Report it by input, group and context; the culprit and helper tallies; the worst games with their
culprits; and the full per-game table.

## B. Drop-column importance (refit)

**Arms.** Production, plus one arm per input (28) and one per multi-input group (offense box rates,
defense box rates, unit absences, lead/deficit peaks, pass tail hinges): 33 arms. An arm zeroes its
column(s) in every row and refits the production recipe before every evaluation week. Zeroed
columns get no weight, so this equals refitting without them; every other setting is unchanged.
v1.18's penalty is applied after.

**Importance** = `LL(arm) − LL(production)` per game, as a mean with a week-clustered SE. Positive
means the input improves accuracy. Also reported: the flat 1u ROI difference (arm minus
production, on the same bets), side flips and the units on flipped games.

**Reading, per basis and context:** helps (z ≥ 2), hurts (z ≤ −2), unresolved otherwise; and
whether the sign agrees on all three bases. 33 arms × 4 contexts × 3 bases = 396 cells, so about
18 reach |z| ≥ 2 by chance.

## C. Interaction scan (Test 37 design)

**Interactions.** All 378 pairs of the 28 inputs, plus each input × the market log-odds: 406, in 4
contexts = 1,624 cells per basis. Within a context the interaction is
`(x_j − mean x_j)·(x_k − mean x_k)`, scored with Test 37's week-clustered score test against
production v1.18's residual `y − p`.

**Discovery 2017–22:** cells with |z| ≥ 3.0, ranked by |z|, at most K = 10 (about four pass by chance).
**Confirmation 2023–25 and replication 2015–16**, each one-sided in the discovery direction:
confirmed (or replicated) at z* ≥ Φ⁻¹(1 − 0.05/K), direction holds at 0 < z* below that, reversed
at z* ≤ 0. Nothing is registered forward. An interaction that clears both bars would be a
candidate for the owner to consider, and adding one would be a new `REVISION`.

## D. Correlation structure (descriptive)

1. The input correlation matrix per basis: pairs with |r| ≥ 0.5 on all three bases, and each
   input's variance inflation factor.
2. Correlations across games between group contributions (do groups offset each other?) and
   between group accuracy effects from part A (do they fail together?), per basis.

## What a result means

Diagnostic only. Removing, reweighting or adding a term changes `config_signature()` and needs a
new `REVISION`; that is the owner's decision. The historical bases are all exposed, so a clean test
of any change is forward.

Run: `python research/feature_importance.py`.
