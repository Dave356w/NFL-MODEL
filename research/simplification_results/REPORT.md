# Fixed model simplification results

Protocol committed before this run: `e4a7959ddacb3a0336e0ca282b8d1681dd3430f7`. All history was already exposed; development evidence only.

Production v1.18, its v1.16 shadow lock and native snapshots are unchanged.

Baseline reproduction maximum errors: 2017-20: 1.11e-16, 2021-22: 6.94e-16, 2023-25: 1.11e-16.

## Flat 1u returns (goal metric)

| Basis | Arm | Bets | W-L-P | Units | ROI ± SE | Favorite units | Market-null ROI | Binary n | LL | Market LL | Brier |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015-16 | production | 507 | 320-185-2 | -17.52 | -3.46% ± 3.38 | -26.01 | -2.40% | 510 | 0.640437 | 0.640486 | 0.224936 |
| 2015-16 | no_peaks | 507 | 323-182-2 | -10.82 | -2.13% ± 3.40 | -26.01 | -2.40% | 510 | 0.640366 | 0.640486 | 0.224907 |
| 2015-16 | no_peaks_site | 507 | 323-182-2 | -11.58 | -2.28% ± 3.39 | -26.01 | -2.40% | 510 | 0.640090 | 0.640486 | 0.224812 |
| 2015-16 | no_pass_tails | 507 | 321-184-2 | -15.76 | -3.11% ± 3.38 | -26.01 | -2.40% | 510 | 0.640318 | 0.640486 | 0.224880 |
| 2017-22 | production | 1559 | 1041-511-7 | -24.22 | -1.55% ± 1.82 | -59.21 | -2.61% | 1559 | 0.608107 | 0.605463 | 0.210072 |
| 2017-22 | no_peaks | 1559 | 1038-514-7 | -30.27 | -1.94% ± 1.82 | -59.21 | -2.61% | 1559 | 0.607899 | 0.605463 | 0.209983 |
| 2017-22 | no_peaks_site | 1559 | 1039-513-7 | -29.81 | -1.91% ± 1.82 | -59.21 | -2.61% | 1559 | 0.607387 | 0.605463 | 0.209808 |
| 2017-22 | no_pass_tails | 1559 | 1035-517-7 | -37.50 | -2.41% ± 1.82 | -59.21 | -2.61% | 1559 | 0.607640 | 0.605463 | 0.209886 |
| 2023-25 | production | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 815 | 0.606414 | 0.608072 | 0.209473 |
| 2023-25 | no_peaks | 812 | 565-246-1 | +29.06 | +3.58% ± 2.52 | +0.18 | -4.10% | 815 | 0.606048 | 0.608072 | 0.209316 |
| 2023-25 | no_peaks_site | 812 | 562-249-1 | +23.07 | +2.84% ± 2.52 | +0.18 | -4.10% | 815 | 0.605583 | 0.608072 | 0.209165 |
| 2023-25 | no_pass_tails | 812 | 562-249-1 | +19.32 | +2.38% ± 2.49 | +0.18 | -4.10% | 815 | 0.607445 | 0.608072 | 0.209917 |
| 2026 wk1-5 (diagnostic) | production | 65 | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.05 | -4.10% | 65 | 0.682309 | 0.666270 | 0.243040 |
| 2026 wk1-5 (diagnostic) | no_peaks | 65 | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.05 | -4.10% | 65 | 0.681581 | 0.666270 | 0.242727 |
| 2026 wk1-5 (diagnostic) | no_peaks_site | 65 | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.05 | -4.10% | 65 | 0.682856 | 0.666270 | 0.243318 |
| 2026 wk1-5 (diagnostic) | no_pass_tails | 65 | 39-26-0 | -7.25 | -11.15% ± 9.31 | -4.05 | -4.10% | 65 | 0.676080 | 0.666270 | 0.240367 |

## Paired comparisons with production

Intervals are 98.33%, normal week-cluster intervals, adjusted for three arms within a basis. Annual and total-band slices are descriptive. No across-basis multiplicity claim.

| Basis | Arm | LL gain ×1000 [interval] | Brier gain ×1000 | ROI gain pp [interval] | Units gain | Side flips |
|---|---|---:|---:|---:|---:|---:|
| 2015-16 | no_peaks | +0.071 [-1.177, +1.319] | +0.029 | +1.32 [-0.45, +3.10] | +6.71 | 5 |
| 2015-16 | no_peaks_site | +0.348 [-1.725, +2.420] | +0.124 | +1.17 [-1.60, +3.94] | +5.95 | 11 |
| 2015-16 | no_pass_tails | +0.119 [-1.795, +2.034] | +0.057 | +0.35 [-0.47, +1.17] | +1.76 | 1 |
| 2017-22 | no_peaks | +0.208 [-0.243, +0.659] | +0.089 | -0.39 [-1.05, +0.27] | -6.05 | 5 |
| 2017-22 | no_peaks_site | +0.720 [-0.355, +1.796] | +0.264 | -0.36 [-2.02, +1.30] | -5.59 | 30 |
| 2017-22 | no_pass_tails | +0.467 [-1.574, +2.509] | +0.186 | -0.85 [-2.18, +0.47] | -13.28 | 20 |
| 2023-25 | no_peaks | +0.366 [-0.312, +1.044] | +0.157 | +0.00 [+0.00, +0.00] | +0.00 | 0 |
| 2023-25 | no_peaks_site | +0.831 [-0.417, +2.080] | +0.308 | -0.74 [-2.13, +0.66] | -5.98 | 5 |
| 2023-25 | no_pass_tails | -1.030 [-5.445, +3.384] | -0.444 | -1.20 [-3.19, +0.79] | -9.74 | 13 |
| 2026 wk1-5 (diagnostic) | no_peaks | +0.728 [-0.674, +2.130] | +0.313 | +0.00 [+0.00, +0.00] | +0.00 | 0 |
| 2026 wk1-5 (diagnostic) | no_peaks_site | -0.546 [-2.502, +1.410] | -0.278 | +0.00 [+0.00, +0.00] | +0.00 | 0 |
| 2026 wk1-5 (diagnostic) | no_pass_tails | +6.229 [-21.815, +34.273] | +2.673 | -3.15 [-9.69, +3.39] | -2.05 | 1 |

## Development screen

- **no_peaks**: unresolved.
- **no_peaks_site**: unresolved.
- **no_pass_tails**: unresolved.

Worth a forward shadow test requires positive LL gain on all three historical bases and a positive lower interval bound on at least one. Nonpositive gain on two bases means not supported; otherwise unresolved. This does not establish return superiority or automatically nominate/adopt an arm.

## Limits and reproduction

Historical schedule quotes have unknown capture times. Repeated design on these periods is not accounted for by the intervals. The 2026 reconstruction is diagnostic, not native forward evidence. Ties push in returns and are omitted from binary scores. Return SE is per-game; paired ROI-gain intervals cluster by week. Forecast coverage is checked before comparison; directional returns use paired eligible games.

Per-game forecasts (17-digit precision), annual slices, total-band comparisons and source/input hashes are in `predictions.csv.gz`, `annual.csv`, `arms.csv`, and `provenance.json`.

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/simplification.py`.
