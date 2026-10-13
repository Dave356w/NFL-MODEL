# Favorite-confidence penalty for v1.16 (reporting only, v1.16.2)

Committed before the implementation exists and before the 2026 or native-ledger
numbers below are computed. Owner request 2026-10-13: confirm, test and apply
the penalty to v1.16 retrospectively. Production v1.16's forecasts, snapshots,
bets, recipe, `REVISION` and `config_signature()` are unchanged. The penalized
probability is an additional, reporting-only column. Making it the live
forecast would be a new revision and a separate owner decision.

## The rule

With q the no-vig moneyline home probability and p the v1.16 home probability:

* **Bullish on the favorite:** q ≠ ½, p is on the market favorite's side, and p
  is further from ½ than q (logit p > logit q > 0, or logit p < logit q < 0).
* **Penalized probability:** on those games
  p′ = sigmoid(logit q + λ·(logit p − logit q)); everywhere else p′ = p.
* **λ = 0.2, fixed.**

Because p′ lies between q and p on the same side of ½ as both, every pick and
every flat bet is identical to v1.16's.

## Exposure, disclosed in advance

λ and the rule were found in conversation on 2026-10-13 using the committed
v1.16 predictions:

* λ = 0.2 minimized log loss on 2021–25 (grid 0 to 1, step 0.05).
* With λ = 0.2 fixed, 2017–20 out of sample improved by +0.0040 ± 0.0023
  (week-cluster SE). λ chosen on 2017–20 (0.0) improved 2021–25 by
  +0.0022 ± 0.0023.

So 2017–20 and 2021–25 are exposed: re-scoring them here checks the
implementation, not the idea. Not yet examined with the penalty:

* the 79 graded 2026 weeks 1–5 games in the rebuilt history (current-season
  walk-forward, basis 3);
* the graded native v1.16 forward-ledger snapshots (basis 1).

## Decision

* **Implementation check:** on 2017–20 out of sample and 2021–25 rebuilt, the
  log-loss gain over v1.16 must be positive and every bet identical; otherwise
  the implementation is wrong and is not merged.
* **Unseen evidence:** 2026 weeks 1–5 and native v1.16 rows are reported
  with gain ± SE and n. No verdict below 100 graded native games.
* **Forward falsification:** falsified if, at 200 or more graded native v1.16
  games (first snapshot per game), the penalized log loss is not lower than
  v1.16's. Supported if the 95% interval of the gain lies above zero at that
  point.

Log loss is secondary to the owner's goal metric. This rule cannot change ROI,
so ROI is reported only to confirm it is identical.

## Outputs

* `nfl_model.favorite_penalized_wp` and `FAVORITE_PENALTY` (reporting only);
  a `model_wp_fp` column in `retro_ledger.csv`.
* `grade_ledger.py`: `fp_wp` / `fp_log_loss` columns in `forward_ledger.csv`
  and a v1.16 report line.
* `research/favorite_penalty.py` → `research/favorite_penalty_results/`.
