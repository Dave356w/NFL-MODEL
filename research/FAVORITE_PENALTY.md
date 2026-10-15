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

## Adoption (2026-10-13)

The owner made the penalty the production forecast as `boxscore-composite-v1.18`. The decision
rules above are unchanged. Native v1.16 rows continue through the v1.16 shadow lock (same
signature `9dad9b9a…`, same gate), so `fp_wp`/`fp_log_loss` on those rows still grade the forward
verdict. `research/favorite_penalty.py --freeze` read v1.16 forecasts from `retro_ledger.csv`; from
v1.18 that file holds penalized forecasts, so the frozen `inputs.csv` must not be refrozen from it.

## Outputs

* `nfl_model.favorite_penalized_wp` and `FAVORITE_PENALTY` (reporting only);
  a `model_wp_fp` column in `retro_ledger.csv`.
* `grade_ledger.py`: `fp_wp` / `fp_log_loss` columns in `forward_ledger.csv`
  and a v1.16 report line.
* `research/favorite_penalty.py` → `research/favorite_penalty_results/`.

## Addendum 2026-10-15: three-way verdict (owner request, before any verdict point)

Written after the 13 week-5 native v1.16 rows (gain +0.147, about 84% from SF@SEA) and the 78 graded
2026 weeks 1–5 rows had been seen. **It does not use their values.** The rule is chosen from
simulated operating characteristics alone (`research/forward_monitoring.py`), built from the
historical per-game spread of the gain:
* SD 0.070, inflated to 0.084 by the 2017–20 week-cluster design effect of 1.42;
* the January checkpoints: about 206, 478, 750, 1,022 and 1,294 graded native v1.16 games from
  2027 to 2031.

**Why the rule changes.** The rule above ("falsified if, at 200 or more games, the penalized log
loss is not lower") falsifies a penalty whose true gain is the adopted +0.0023 35% of the time at
the first January look, and 50% across five looks. At +0.004 the rate is still 25–33%.

**Replacement rule.** It is judged only at the January checkpoints, on the first native v1.16
snapshot per game, using the week-cluster SE of the per-game gain:
- **No verdict** below 200 graded games.
- **Supported**: gain − 2.24·SE > 0.
- **Falsified**: gain + 2.24·SE < +0.002, so the data exclude the gain the penalty was adopted for.
- Otherwise **unresolved**.

Simulated over the five looks (`research/forward_monitoring_results/`):

| Rule | False falsification (true gain +0.0023) | False support (true gain 0) | Falsifies a true 0 | Supports a true +0.004 |
|---|---:|---:|---:|---:|
| As written | 35% → 50% | 2.5% → 6.7% | 51% → 77% | 10% → 44% |
| Replacement | 1.1% → 3.2% | 1.3% → 4.1% | 3% → 15% | 6% → 38% |

The cost is power: the replacement is slower to reach a verdict either way, and "unresolved" is
the likely reading through 2028. That is the honest state of evidence at these effect sizes. The
penalty cannot change ROI either way, because it never changes a pick.
`grade_ledger.py` prints this verdict on the v1.16 penalty line.
