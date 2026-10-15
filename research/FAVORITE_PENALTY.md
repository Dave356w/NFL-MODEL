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

## Addendum 2026-10-15 (second): corrected error rates, t(G − 1) bounds (before any verdict point)

**What was wrong.** Review after the addendum above was merged found that its error rates came from
Gaussian paths with a known SE. The per-game gain is right-skewed (skew 2.8, excess kurtosis 16).
The ledger estimates a week-cluster SE from only about 14 weeks at the first look. Together these
make false falsification more likely than the Gaussian paths show.

**Corrected simulation** (`research/forward_monitoring.py`, 200,000 paths; Monte Carlo SE about
0.05 points):
* Each path resamples whole historical weeks of the per-game gain: 158 weeks of 2017–20 and
  2021–25, recentred to the true gain.
* At each look the SE is the week-cluster SE of the sampled weeks, as the ledger computes it.
* The looks are about 206, 478, 750, 1,022 and 1,294 graded games over 14, 32, 50, 68 and 86 weeks.

On that basis, z = 2.24 falsifies a true +0.0023 3.0% → 6.4% of the time over the five looks, not
the 1.1% → 3.2% reported above.

**Change.** The bounds use t, the two-sided 97.5% t critical value with G − 1 degrees of freedom,
in place of 2.24. G is the number of season-weeks, so t is 2.53 at 14 weeks and 2.28 at 86.
- **Supported**: gain − t·SE > 0.
- **Falsified**: gain + t·SE < +0.002.
- Everything else in the addendum above is unchanged: no verdict below 200 graded games, January
  checkpoints only, first native v1.16 snapshot per game.

**A January checkpoint** is the first report after the regular season's week 18 is fully graded,
with no pending v1.16 row left for that season. Before that, including early-January builds while
weeks 17–18 are still pending, `grade_ledger.py` labels the line an interim reading, not a verdict.
The line also prints the week-cluster SE and the number of weeks.

Simulated over the five looks (first look → all five), every week resampled:

| Rule | False falsification (+0.0023) | False support (0) | Falsifies a true 0 | Supports a true +0.004 |
|---|---:|---:|---:|---:|
| As first written | 33.2% → 46.8% | 2.2% → 5.5% | 51.4% → 76.9% | 11.5% → 51.7% |
| Three-way, z 2.24 (addendum above) | 3.0% → 6.4% | 1.2% → 3.1% | 7.3% → 24.9% | 7.1% → 46.2% |
| **Three-way, t(G − 1) (adopted)** | 1.9% → 5.1% | 0.6% → 2.2% | 4.9% → 22.2% | 4.2% → 43.3% |

With t(G − 1), false falsification is about 5% and false support about 2%.

**Given the 13 week-5 rows already in the sample.** The registered sample includes the 13 graded
native week-5 rows. The protocol above registered them before they were scored. Their gain sums to
+1.90 (mean +0.147):
* That week lies beyond all 158 historical weeks; the largest of those sums to +1.49.
* SF@SEA alone (+1.59) is more than twice the largest historical game (+0.73, 2024 ARI@SF).

With that week fixed as the first week of every path:

| Rule | False falsification (+0.0023) | False support (0) | Falsifies a true 0 | Supports a true +0.004 |
|---|---:|---:|---:|---:|
| As first written | 0.7% → 7.2% | 1.7% → 8.9% | 2.5% → 33.5% | 9.0% → 68.5% |
| Three-way, z 2.24 (addendum above) | 0.0% → 0.0% | 0.5% → 3.7% | 0.0% → 0.9% | 3.3% → 53.4% |
| **Three-way, t(G − 1) (adopted)** | 0.0% → 0.0% | 0.1% → 2.9% | 0.0% → 0.8% | 1.0% → 50.3% |

* **Falsification is out of reach through 2031.** By January 2031, a penalty with no gain is
  falsified 0.8% of the time, and one that costs 0.002 a game is falsified 7.3%.
* False support at 0 is 2.9%. Support at +0.004 is 50%.
* Until about 2031, then, the forward verdict can only support the penalty or stay unresolved.
  "Unresolved" is not evidence for it.
* The week-5 rows stay in the sample. They were registered before they were scored, and removing
  them now would be a change informed by their outcome.

**Disclosure.**
* The change was chosen from the simulation alone, before any verdict point.
* It uses no forward outcome beyond the 13 week-5 rows disclosed above.
* It makes both an early support and an early falsification harder.
* All three methods (every week resampled, given week 5, and Gaussian) are kept in
  `research/forward_monitoring_results/`.
