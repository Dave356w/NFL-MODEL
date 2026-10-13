# Availability weighting candidates

Protocol: [AVAILABILITY_WEIGHTS.md](../AVAILABILITY_WEIGHTS.md), committed before any candidate forecast. Production v1.16 and its ledger are unchanged. Historical development, not forward evidence.

**A, Questionable by practice: unresolved.** Pooled log-loss gain over v1.16 +0.000310 [-0.000260, +0.000871] (97.5%), 1834 games; 12 side flips worth -11.35u against v1.16.

**B, split units: falsified.** Pooled log-loss gain over v1.16 -0.000032 [-0.002166, +0.001973] (97.5%), 1834 games; 31 side flips worth -23.63u against v1.16.

## 2017-2020

Rebuilt production columns reproduce the frozen columns exactly (0 of 2048 rows differ; max 1.11e-16). Control against the committed v1.16 forecasts: max difference 1.11e-16.

1017 flat 1u bets where the market has a favorite (same rows for every arm and the favorite); 1019 binary games for log loss.

| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Same-row favorite | Log loss |
|---|---:|---:|---:|---:|---:|---:|
| control | 691-322-4 | -0.42 | -0.04% ± 2.23 | -2.55% | -19.18u (-1.89%) | 0.605604 |
| A_practice | 686-327-4 | -9.92 | -0.98% ± 2.23 | -2.55% | -19.18u (-1.89%) | 0.605160 |
| B_split | 687-326-4 | -8.19 | -0.80% ± 2.23 | -2.55% | -19.18u (-1.89%) | 0.605654 |

| Candidate vs v1.16 | Log-loss gain [97.5%] | Units vs v1.16 | Side flips |
|---|---:|---:|---:|
| A, Questionable by practice | +0.000443 [-0.000442, +0.001313] | -9.50 | 9 |
| B, split units | -0.000051 [-0.001830, +0.001784] | -7.77 | 14 |

## 2023-2025

Rebuilt production columns reproduce the frozen columns exactly (0 of 1871 rows differ; max 1.11e-16). Control against the committed v1.16 forecasts: max difference 1.11e-16.

812 flat 1u bets where the market has a favorite (same rows for every arm and the favorite); 815 binary games for log loss.

| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Same-row favorite | Log loss |
|---|---:|---:|---:|---:|---:|---:|
| control | 565-246-1 | +29.06 | +3.58% ± 2.52 | -4.10% | +0.18u (+0.02%) | 0.605605 |
| A_practice | 564-247-1 | +27.21 | +3.35% ± 2.53 | -4.10% | +0.18u (+0.02%) | 0.605461 |
| B_split | 556-255-1 | +13.19 | +1.62% ± 2.54 | -4.10% | +0.18u (+0.02%) | 0.605614 |

| Candidate vs v1.16 | Log-loss gain [97.5%] | Units vs v1.16 | Side flips |
|---|---:|---:|---:|
| A, Questionable by practice | +0.000144 [-0.000493, +0.000811] | -1.85 | 3 |
| B, split units | -0.000008 [-0.003986, +0.003681] | -15.86 | 17 |

Week-cluster bootstrap intervals; positive gains favor the candidate. Log loss decides; ROI is reported, not optimized. Supported needs a positive gain on both bases and a pooled interval above zero; a pooled gain at or below zero falsifies.

Run: `python research/availability_weights.py --prepare` (downloads), then `python research/availability_weights.py`.
