# SB1: soft neighboring-band empirical distributions

**development gate failed; do not promote.** Production, live forecasts and original archives are unchanged.

Exposed retrospective development. Each scored season uses strictly earlier-season PMFs and anchors. No smoothing parameter, threshold or ROI-selected variant was searched.

## Forecast scores: 2023-25

| Forecast | Conditional cover log loss | Brier | Margin CRPS | Median MAE |
| --- | ---: | ---: | ---: | ---: |
| hard empirical bands | 0.697254 | 0.251801 | 7.101045 | 9.765319 |
| soft empirical bands | 0.694593 | 0.250537 | 7.075315 | 9.717525 |
| Actual paired-price market (conditional only) | 0.693588 | 0.250220 | Unidentified | Unidentified |

All-game cohort 816; decisive 797; exact paired-price cohort 816. Pushes are excluded identically from conditional cover scoring. Paired-subset soft/hard scores are retained in results.json.

## Primary paired gains

Positive favors soft. The two intervals are 97.5% each (Bonferroni familywise 95%).

- soft_vs_hard_cover: gain +0.002661; interval [-0.002104811905360655, 0.007281434118656068]; n=797.
- soft_vs_market_cover: gain -0.001005; interval [-0.011545092102423857, 0.009597117970355633]; n=797.

## ATS returns

Uniform -110 is hypothetical. Paired prices require both exact-handicap side prices. Historical schedule capture times are unknown, and 2026 ESPN closes are retrospective estimates; neither scenario certifies execution at lock.

| Period | Prices | Policy | Bets / passes | W-L-P | Units | ROI +/- SE | Same-selected favorite units |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: |
| 2023-25 | assumed110 | soft_ev | 509 / 307 | 260-239-10 | -2.636 | -0.52% +/- 4.19 pp | -2.636 |
| 2023-25 | assumed110 | hard_ev | 574 / 242 | 293-263-18 | +3.364 | +0.59% +/- 3.92 pp | +11.000 |
| 2023-25 | assumed110 | median | 816 / 0 | 430-367-19 | +23.909 | +2.93% +/- 3.29 pp | -12.364 |
| 2023-25 | assumed110 | raw | 816 / 0 | 409-388-19 | -16.182 | -1.98% +/- 3.30 pp | -12.364 |
| 2023-25 | assumed110 | favorite | 816 / 0 | 411-386-19 | -12.364 | -1.52% +/- 3.30 pp | -12.364 |
| 2023-25 | assumed110 | home | 816 / 0 | 400-397-19 | -33.364 | -4.09% +/- 3.30 pp | -12.364 |
| 2023-25 | paired | soft_ev | 495 / 321 | 256-229-10 | +4.387 | +0.89% +/- 4.25 pp | -2.262 |
| 2023-25 | paired | hard_ev | 550 / 266 | 283-252-15 | +6.894 | +1.25% +/- 4.03 pp | -11.015 |
| 2023-25 | paired | median | 816 / 0 | 430-367-19 | +23.039 | +2.82% +/- 3.29 pp | -13.555 |
| 2023-25 | paired | raw | 816 / 0 | 409-388-19 | -17.763 | -2.18% +/- 3.30 pp | -13.555 |
| 2023-25 | paired | favorite | 816 / 0 | 411-386-19 | -13.555 | -1.66% +/- 3.30 pp | -13.555 |
| 2023-25 | paired | home | 816 / 0 | 400-397-19 | -32.743 | -4.01% +/- 3.31 pp | -13.555 |
| 2026 diagnostic | assumed110 | soft_ev | 58 / 48 | 30-26-2 | +1.273 | +2.19% +/- 12.39 pp | -8.273 |
| 2026 diagnostic | assumed110 | hard_ev | 59 / 47 | 29-27-3 | -0.636 | -1.08% +/- 12.20 pp | -0.636 |
| 2026 diagnostic | assumed110 | median | 106 / 0 | 58-42-6 | +10.727 | +10.12% +/- 8.93 pp | -10.273 |
| 2026 diagnostic | assumed110 | raw | 106 / 0 | 47-53-6 | -10.273 | -9.69% +/- 9.03 pp | -10.273 |
| 2026 diagnostic | assumed110 | favorite | 106 / 0 | 47-53-6 | -10.273 | -9.69% +/- 9.03 pp | -10.273 |
| 2026 diagnostic | assumed110 | home | 106 / 0 | 42-58-6 | -19.818 | -18.70% +/- 8.94 pp | -10.273 |
| 2026 diagnostic | paired | soft_ev | 47 / 39 | 23-22-2 | -0.646 | -1.37% +/- 13.92 pp | -10.291 |
| 2026 diagnostic | paired | hard_ev | 50 / 36 | 26-22-2 | +1.806 | +3.61% +/- 13.37 pp | -5.845 |
| 2026 diagnostic | paired | median | 86 / 0 | 49-33-4 | +11.380 | +13.23% +/- 9.91 pp | -7.503 |
| 2026 diagnostic | paired | raw | 86 / 0 | 40-42-4 | -5.667 | -6.59% +/- 10.11 pp | -7.503 |
| 2026 diagnostic | paired | favorite | 86 / 0 | 39-43-4 | -7.503 | -8.72% +/- 10.11 pp | -7.503 |
| 2026 diagnostic | paired | home | 86 / 0 | 33-49-4 | -18.867 | -21.94% +/- 9.95 pp | -7.503 |

## Annual paired-price results

| Season | Soft cover LL | Market cover LL | Soft EV bets | Soft EV ROI |
| --- | ---: | ---: | ---: | ---: |
| 2023 | 0.703247 | 0.693148 | 176 | -7.97% |
| 2024 | 0.698115 | 0.695292 | 151 | +0.15% |
| 2025 | 0.682871 | 0.692321 | 168 | +10.82% |
| 2026 diagnostic | 0.701201 | 0.694080 | 47 | -1.37% |

Main paired-price soft EV ROI 95% interval: [-0.07549225867229273, 0.09369931387017492]. Mean predicted conditional cover on its decisive selections: 55.76%; realized: 52.78%. Expected units: +32.053; realized units: +4.387.

Complete yearly tables, bootstrap ROI intervals, expected returns, calibration bins, zero-probability events and same-selected median/raw/favorite/home controls are in results.json and calibration.csv.

## Interpretation and limitations

- This tests one fixed interpolation of the empirical band distributions, with a matched hard-PMF control.
- Empirical key-number masses and tails are preserved; the mixture can have median jumps even when its cover probabilities are continuous.
- The endpoint PMFs are clamped outside their prior median anchors. The separate raw-sign orientation boundary at zero is not solved.
- Small bands can have zero mass on an event later observed. Forecasts are unchanged; score clipping and zero-event counts are explicit.
- Bootstrap intervals resample complete weeks within season; they omit recipe/design-selection uncertainty and refitting uncertainty.
- All historical data and the 2026 diagnostic are exposed. No result is independent forward validation or a production adoption decision.

Reproduce: `python -m research.soft_band_distributions`
