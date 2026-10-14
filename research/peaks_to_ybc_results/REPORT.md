# Replace lead/deficit peaks with yards before contact

Protocol `e5538ef06d0e315adb7bffd51105db55cace41c5` pushed before this replacement was scored. All history already exposed; development evidence only.

29-term production vs 27-term no-peaks control vs 29-term replacement with offensive and defensive-allowed YBC/carry. Rush efficiency and every other production input remain in the replacement.

## Flat 1u returns and probability scores

| Basis | Arm | Bets | W-L-P | Units | ROI ± SE | Favorite units | Market-null ROI | Binary n | LL | Market LL | Brier |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021-22 | production | 542 | 350-189-3 | -23.80 | -4.39% ± 3.15 | -40.03 | -2.72% | 540 | 0.620331 | 0.615077 | 0.215988 |
| 2021-22 | no_peaks | 542 | 349-190-3 | -25.97 | -4.79% ± 3.14 | -40.03 | -2.72% | 540 | 0.620163 | 0.615077 | 0.215926 |
| 2021-22 | peaks_to_ybc | 542 | 348-191-3 | -28.09 | -5.18% ± 3.14 | -40.03 | -2.72% | 540 | 0.620516 | 0.615077 | 0.216140 |
| 2023-25 | production | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 815 | 0.606414 | 0.608072 | 0.209473 |
| 2023-25 | no_peaks | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 815 | 0.606048 | 0.608072 | 0.209316 |
| 2023-25 | peaks_to_ybc | 812 | 563-248-1 | +24.36 | +3.00% ± 2.52 | +0.18 | -4.10% | 815 | 0.606006 | 0.608072 | 0.209282 |
| 2026 wk1-5 (diagnostic) | production | 65 | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.05 | -4.10% | 65 | 0.682309 | 0.666270 | 0.243040 |
| 2026 wk1-5 (diagnostic) | no_peaks | 65 | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.05 | -4.10% | 65 | 0.681581 | 0.666270 | 0.242727 |
| 2026 wk1-5 (diagnostic) | peaks_to_ybc | 65 | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.05 | -4.10% | 65 | 0.685725 | 0.666270 | 0.244597 |

## Replacement minus each control

Positive gains favor replacement. Intervals: 97.5%, normal week-cluster, two contrasts within each basis. No across-era/metric confirmation claim; annual and total-band slices are descriptive.

| Basis | Control | LL gain ×1000 [interval] | Brier gain ×1000 | ROI gain pp [interval] | Units gain | Side flips |
|---|---|---:|---:|---:|---:|---:|
| 2021-22 | production | -0.185 [-3.046, +2.677] | -0.151 | -0.79 [-3.34, +1.76] | -4.29 | 10 |
| 2021-22 | no_peaks | -0.353 [-2.864, +2.159] | -0.214 | -0.39 [-2.80, +2.02] | -2.12 | 9 |
| 2023-25 | production | +0.408 [-0.960, +1.777] | +0.191 | -0.58 [-1.91, +0.75] | -4.70 | 6 |
| 2023-25 | no_peaks | +0.042 [-1.039, +1.124] | +0.035 | -0.58 [-1.91, +0.75] | -4.70 | 6 |
| 2026 wk1-5 (diagnostic) | production | -3.416 [-6.130, -0.702] | -1.558 | +0.00 [+0.00, +0.00] | +0.00 | 0 |
| 2026 wk1-5 (diagnostic) | no_peaks | -4.144 [-7.845, -0.443] | -1.871 | +0.00 [+0.00, +0.00] | +0.00 | 0 |

## Verdict and checks

No nomination: development support unresolved.

A nomination requires positive LL gains on both historical bases against each comparator, with a positive lower bound on at least one historical basis for each comparator. No automatic production adoption.

Reproduction maximum errors: 2021-22 independent: 1.11e-16, 2021-22 archived: 2.30e-13, 2023-25 independent: 2.22e-16, 2023-25 archived: 9.15e-11, 2026 wk1-5 (diagnostic) independent: 1.11e-16.

All evaluation and eligible training rows have finite YBC. Profiles use only earlier weeks. Per-game forecasts, full-precision profiles, weekly fit cutoff/coefficient audits, annual slices, contrasts by total band and source/input hashes accompany this report.

## Limits

PFR charting begins in 2018; no invented pre-2021 test. Charts are retrospective source snapshots with no independent publication timestamps. Historical moneylines are the frozen schedule quotes with unknown capture times. 2026 weeks 1-5 are reconstructed diagnostics, not native forward evidence. Repeated historical design is not accounted for by the intervals. Ties push in returns and are omitted from binary scores. Paired directional bets follow repository conventions, including excluding a market pick-em comparator. No recipe, production forecast or ledger was changed.

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/peaks_to_ybc.py`.
