# R003-AC1: ATS calibration and stable selection

**no established ATS edge.** Exposed historical development at assumed −110, not forward confirmation.

## Return results, 816 games 2023–25

| Policy | Bets | W–L–P | Units | ROI ± SE | Same-row favorite units | Null |
|---|---:|---|---:|---:|---:|---:|
| context_r100_EV | 99 | 41–55–3 | -17.727 | -17.91% ±9.40 pp | +5.182 | -4.41% |
| context_r100_Stable | 62 | 27–32–3 | -7.455 | -12.02% ±11.88 pp | +2.091 | -4.33% |
| context_r10_EV | 235 | 115–113–7 | -8.455 | -3.60% ±6.15 pp | -25.636 | -4.41% |
| context_r10_Stable | 164 | 81–80–3 | -6.364 | -3.88% ±7.41 pp | -2.545 | -4.46% |
| fair_EV | 0 | 0–0–0 | +0.000 | undefined (no bets) | +0.000 | — |
| fair_Stable | 0 | 0–0–0 | +0.000 | undefined (no bets) | +0.000 | — |
| platt_r100_EV | 0 | 0–0–0 | +0.000 | undefined (no bets) | +0.000 | — |
| platt_r100_Stable | 0 | 0–0–0 | +0.000 | undefined (no bets) | +0.000 | — |
| platt_r10_EV | 18 | 7–9–2 | -2.636 | -14.65% ±21.69 pp | +1.182 | -4.04% |
| platt_r10_Stable | 1 | 0–1–0 | -1.000 | -100.00% ±nan pp | +0.909 | -4.55% |
| raw_EV | 560 | 270–278–12 | -32.545 | -5.81% ±3.99 pp | -0.091 | -4.45% |
| raw_Stable | 531 | 255–266–10 | -34.182 | -6.44% ±4.11 pp | +0.182 | -4.46% |
| selected_EV | 0 | 0–0–0 | +0.000 | undefined (no bets) | +0.000 | — |
| selected_Stable | 0 | 0–0–0 | +0.000 | undefined (no bets) | +0.000 | — |
| temperature_r100_EV | 0 | 0–0–0 | +0.000 | undefined (no bets) | +0.000 | — |
| temperature_r100_Stable | 0 | 0–0–0 | +0.000 | undefined (no bets) | +0.000 | — |
| temperature_r10_EV | 4 | 1–3–0 | -2.091 | -52.27% ±47.73 pp | +1.727 | -4.55% |
| temperature_r10_Stable | 0 | 0–0–0 | +0.000 | undefined (no bets) | +0.000 | — |

## All-game conditional cover proper scores

| Model | Cover LL ↓ | Brier ↓ | Mean absolute edge |
|---|---:|---:|---:|
| context_r10 | 0.695196 | 0.251018 | 0.017814 |
| context_r100 | 0.694555 | 0.250702 | 0.012034 |
| fair | 0.693147 | 0.250000 | 0.000000 |
| platt_r10 | 0.694014 | 0.250433 | 0.007790 |
| platt_r100 | 0.693784 | 0.250319 | 0.007239 |
| raw | 0.700040 | 0.253348 | 0.046568 |
| selected | 0.693345 | 0.250099 | 0.003580 |
| temperature_r10 | 0.693441 | 0.250147 | 0.003835 |
| temperature_r100 | 0.693199 | 0.250026 | 0.000831 |

Annual choices: [(2019, 'fair'), (2020, 'platt_r100'), (2021, 'platt_r100'), (2022, 'platt_r100'), (2023, 'platt_r100'), (2024, 'fair'), (2025, 'fair'), (2026, 'fair')].
Gates: {'sample_size': False, 'positive_ROI_interval': False, 'positive_adjusted_ROI_interval': False, 'annual_positive': False, 'proper_score_vs_fair': False, 'proper_score_vs_raw': True, 'integrity': True}.

Primary policy is selected_Stable; EV is a fixed secondary rule, never chosen from historical ROI. All fixed variants, including unfavorable/no-bet arms, are retained. Betting fewer games or matching the market is not an established edge.

Calibration fits only earlier OOF binary outcomes, excluding pushes. Six settings: temperature/Platt/context × ridge 10/100. Model selection uses earlier OOF cover log loss; fair 0.5 and raw are explicit choices. Stable requires raw ESS >=50 and positive EV on the same side after removing the latest available training season.

Historical paired-score atoms and raw push mass are retained by within-cover-group reweighting. No synthetic scores, score translation, ROI tuning, fees, live quotes, production updates or ledger changes. See distribution_metrics.csv for coherent score-distribution side effects.

All history was exposed, including the failures that motivated this family. Intervals use 10,000 paired whole-week draws within season, seed 20261016, conditional on fitted forecasts. Sensitivity uses 14 fixed non-fair policies; it does not correct all adaptive research. Pass-only ROI is undefined, not zero-risk edge evidence.

Prices are assumed uniformly -110 per the user; historical quote timing/availability is unaudited. An established/executable edge requires new independently retained predictions and real contemporaneous offers.

Full per-game probabilities, decisions, annual selections, weekly coefficients/cutoffs, protocol, hashes, proper-score comparisons, returns and independent repeat checks accompany this report.

Reproduce: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/ats_calibration.py`
