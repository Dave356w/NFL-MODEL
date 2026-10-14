# Test 39 protocol: candidate model updates from Tests 36–38

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner request 2026-10-14 ("test updates to the model based on the analysis"). Committed
and pushed before any candidate below is scored.

## Motivation, and why this is development evidence only

Tests 36–38 point one way. The model's departures from the market run large (Test 37). No input
earns its place once the model is refit without it, and every input with a consistent sign is
one the model scores slightly better without (Test 38). Slower decay of old training games was
Test 36's only lead. That suggests **more shrinkage toward the market** or **fewer inputs**.

Every historical season available (2014–2025) informed those findings, so no historical result here
is a clean test. The candidates are fixed in advance and few, and the pruning candidate chooses its
inputs without the basis it is scored on. A clean test is forward: a shadow lock of any supported
candidate, which would be an owner decision.

## Arms, fixed

All arms are production v1.16 refit before every evaluation week from earlier rows only, with
v1.18's favorite penalty applied last. Each arm changes one thing.

**Primary candidates (K = 4):**
1. `ridge_0.3`: main and context ridge 0.1 → 0.3 (the site penalty stays at 0.1 × main).
2. `ridge_1.0`: both ridges 1.0.
3. `shrink_0.5`: after the fit, halve the departure from the market,
   `logit p = logit q + 0.5·(logit p16 − logit q)`. This can un-flip underdog picks.
4. `prune_lobo`: for evaluation basis B, drop (zero and refit without) every input, the home-field
   term included, whose Test 38 drop-column importance (all games,
   `feature_importance_results/importance.csv`) was negative on **both** of the other two bases.
   Selection never sees B.

**Descriptive only, not judged:** `prune_8` (the 8 inputs negative on all three bases in Test 38)
and `no_site` (drop the home-field adjustment). Both were chosen on the bases they are scored on,
so any gain is partly by construction. `half_life_4` (Test 36's lead: fit half-life 2 → 4 seasons)
is shown for reference.

## Bases, never pooled

2015–16 (510 binary games), 2017–22 (1,559) and 2023–25 (815), built exactly as in Test 38 and
reproducing the published forecasts to 1e-9. Sensitivity: 2014 (trained on 190 games). Diagnostic:
2026 weeks 1–5 from the frozen Test 36 pack. Counterfactual: the 14 native week-5 v1.16 snapshots,
replayed at their archived inputs and moneylines with each arm refit on earlier pack rows; production
reproduces them to 2.2e-16. Replays are not new forward evidence.

## Metrics

* **Primary (decides): log-loss gain over production** (positive = arm better), per basis, with a
  week-clustered SE and a 98.75% interval (Bonferroni over K = 4).
* **Goal metric (reported):** flat 1u ROI on the arm's side (W-L-P, units, ROI ± SE, market-correct
  null, same-row favorite), the paired units difference versus production, side flips and units on
  flipped games. Brier. Results by total band.
* ROI is reported, not optimized. Choosing an arm on ROI would be the owner's decision and a new
  `REVISION`.

## Decision rule, per primary candidate

* **Supported for a forward shadow test**: the log-loss gain is positive on all three bases, and
  its 98.75% interval excludes zero on at least one.
* **Not supported**: the gain is ≤ 0 on two or more bases.
* Otherwise **unresolved**.

"Supported" changes nothing by itself. Production stays v1.18 until the owner decides; any change
is a new `REVISION` and `OUTPUT_NAME`. The recommended next step for a supported candidate is a
forward shadow lock, pre-registered before its first snapshot.

Run: `python research/model_updates.py`.
