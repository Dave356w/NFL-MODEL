# Favorite-penalty forward verdict: operating characteristics

`python research/forward_monitoring.py`. 200,000 simulated paths per cell, in chunks of 20,000 from
seed 20261015; the Monte Carlo SE is about 0.05 points. The first decisive verdict stands.

**Method.**
* Each path resamples whole historical weeks of the penalty's per-game log-loss gain: 158 weeks of
  2017–20 and 2021–25, about 15 games a week, recentred to the true gain.
* The paths keep the gain's skew (2.8) and excess kurtosis (16). The largest historical game is
  2024 ARI@SF at +0.73.
* At each January checkpoint the verdict uses the week-cluster SE of the sampled weeks, as
  `grade_ledger.fp_verdict` does.
* The checkpoints are about 206, 478, 750, 1,022 and 1,294 graded native v1.16 games, over 14, 32,
  50, 68 and 86 weeks.

Three methods:
* **Every week resampled.** Outcome-free with respect to the forward ledger.
* **Given the 13 week-5 rows.** The first week is fixed to the graded native week-5 rows (sum
  +1.90), which are in the registered sample and were seen before the addenda. That week lies beyond
  all 158 historical weeks (largest +1.49).
* **Gaussian, known SE.** The method of the first 2026-10-15 addendum: Brownian paths with SD
  0.084, which is 0.070 inflated by the 2017–20 design effect of 1.42.

## Every week resampled (first look → all five)

| Rule | False falsification (+0.0023) | False support (0) | Falsifies a true 0 | Supports a true +0.004 |
|---|---:|---:|---:|---:|
| As first written | 33.2% → 46.8% | 2.2% → 5.5% | 51.4% → 76.9% | 11.5% → 51.7% |
| Three-way, z 2.24 (addendum above) | 3.0% → 6.4% | 1.2% → 3.1% | 7.3% → 24.9% | 7.1% → 46.2% |
| **Three-way, t(G − 1) (adopted)** | 1.9% → 5.1% | 0.6% → 2.2% | 4.9% → 22.2% | 4.2% → 43.3% |

* **Gaussian paths with a known SE understate false falsification.** They put z 2.24 at
  1.1% → 3.2%.
* **The gain is right-skewed, and the estimate moves with its SE** (correlation about 0.4). When no
  large gain has arrived, the estimate is low and the estimated SE small, which is where false
  falsification happens.
* **The t critical value widens the bounds most at the first look.** It is 2.53 at 14 weeks and
  2.28 at 86, so it costs little power later.

## Given the 13 week-5 rows (the ledger's actual position)

| Rule | False falsification (+0.0023) | False support (0) | Falsifies a true 0 | Supports a true +0.004 |
|---|---:|---:|---:|---:|
| As first written | 0.7% → 7.2% | 1.7% → 8.9% | 2.5% → 33.5% | 9.0% → 68.5% |
| Three-way, z 2.24 (addendum above) | 0.0% → 0.0% | 0.5% → 3.7% | 0.0% → 0.9% | 3.3% → 53.4% |
| **Three-way, t(G − 1) (adopted)** | 0.0% → 0.0% | 0.1% → 2.9% | 0.0% → 0.8% | 1.0% → 50.3% |

* **Falsification is out of reach through 2031.** By January 2031, a true 0 is falsified 0.8% of
  the time and a true −0.002 is falsified 7.3%.
* **The verdict can support the penalty or stay unresolved.** False support at 0 is 2.9%; support
  at +0.004 is 50% by 2031.

Full tables: `operating_characteristics.csv` (all three methods, true gains −0.002 to +0.004) and
`tables.md`. The adopted rule is recorded in the second `FAVORITE_PENALTY.md` addendum of 2026-10-15.
