# Favorite-penalty forward verdict: operating characteristics

`python research/forward_monitoring.py`. Outcome-free with respect to the forward ledger.

**Method.** Each of 20,000 simulated paths resamples whole historical weeks of the penalty's per-game
log-loss gain: 158 weeks of 2017–20 and 2021–25, about 15 games a week, recentred to the true gain.
The paths keep the gain's skew (2.8) and excess kurtosis (16). At each January checkpoint the
verdict uses the week-cluster SE of the sampled weeks, as `grade_ledger.fp_verdict` does. The
checkpoints are about 206, 478, 750, 1,022 and 1,294 graded native v1.16 games, over 14, 32, 50, 68
and 86 weeks. The first decisive verdict stands.

For comparison, "Gaussian, known SE" is the method of the addendum's first draft: Brownian paths
with SD 0.084, which is 0.070 inflated by the 2017–20 design effect of 1.42.

## The adopted rule, and why its critical value is t(G − 1)

Each cell runs from the first look to all five looks.

| Rule (week-block bootstrap) | False falsification (+0.0023) | False support (0) | Falsifies a true 0 | Supports a true +0.004 |
|---|---:|---:|---:|---:|
| As written | 33% → 47% | 2.3% → 5.6% | 52% → 76% | 12% → 51% |
| Three-way, z 2.24 (first draft) | 2.9% → 6.1% | 1.2% → 3.1% | 7% → 25% | 7% → 46% |
| **Three-way, t(G − 1) 97.5% (adopted)** | **1.8% → 4.8%** | **0.7% → 2.3%** | 5% → 22% | 5% → 43% |

* **Gaussian paths with a known SE understate false falsification.** They put z 2.24 at 1.1% → 3.2%.
* **The gain is right-skewed.** A few large gains (SF@SEA in week 5 is one) lift the mean. Most
  paths therefore sit below the true gain with a small estimated SE, and that is where false
  falsification happens.
* **The t critical value widens the bounds most at the first look.** It is 2.53 at 14 weeks and
  2.28 at 86, so it costs little power later.

Full table: `operating_characteristics.csv`, with both methods and true gains −0.002 to +0.004.
The adopted rule is recorded in the second `FAVORITE_PENALTY.md` addendum of 2026-10-15.
