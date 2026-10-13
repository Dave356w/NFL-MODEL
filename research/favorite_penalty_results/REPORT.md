# Favorite-confidence penalty for v1.16: results

Protocol `research/FAVORITE_PENALTY.md`; lambda 0.2. Implementation check: **passed**. Forward verdict: **no verdict (13 of 100 native games)**.

| Basis | n | Changed | LL v1.16 | LL penalized | LL market | Gain vs v1.16 | 95% interval | Bets identical | Units |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|
| 2017-20 out of sample (exposed) | 1019 | 616 | 0.60560 | 0.60163 | 0.60037 | +0.00397 ± 0.00271 | [-0.00111, +0.00943] | True | +3.34 |
| 2021-25 rebuilt (exposed; lambda chosen here) | 1355 | 720 | 0.61427 | 0.61196 | 0.61086 | +0.00231 ± 0.00171 | [-0.00099, +0.00566] | True | +4.08 |
| 2026 weeks 1-5 walk-forward (unseen) | 78 | 34 | 0.69829 | 0.67203 | 0.65075 | +0.02626 ± 0.02538 | [-0.00127, +0.08027] | True | -4.85 |
| native v1.16 ledger (unseen) | 13 | 5 | 0.76589 | 0.61936 | 0.57140 | +0.14653 | one week: none | True | +0.37 |

Gain is v1.16 log loss minus penalized log loss (positive = penalty better), with week-cluster SE and bootstrap interval. Units are flat 1u on the model side over games with a winner (ties excluded), identical for both arms by construction.
