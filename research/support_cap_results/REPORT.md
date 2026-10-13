# Context support cap backtest

Protocol: [CONTEXT_SUPPORT_CAP.md](../CONTEXT_SUPPORT_CAP.md), committed before this run. Production v1.16 and its ledger are unchanged.

**Verdict for the primary arm (cap_k5), by the pre-registered rule: not supported.** Pooled 2023–2025 log-loss gain over production -0.000440 [-0.004576, +0.003225]; 7 side flips worth -5.03u against production.

Basis: Exposed historical development: 2023-2025 held-out walk-forward, prior-week fits. Recipe design used this history; not forward evidence.

## 2023–2025 held-out (primary basis)

812 common flat 1u bets; 815 binary proper scores.

| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|
| production | 565-246-1 | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605605 | 0.208989 |
| cap_k5 | 563-248-1 | +24.02 | +2.96% ± 2.51 | -4.10% | 0.606046 | 0.209268 |
| cap_k1 | 565-246-1 | +29.06 | +3.58% ± 2.52 | -4.10% | 0.605642 | 0.209013 |
| cap_k10 | 564-247-1 | +26.93 | +3.32% ± 2.52 | -4.10% | 0.605996 | 0.209195 |
| market favorite | 555-256-1 | +0.18 | +0.02% ± 2.47 | -4.10% | 0.608072 | 0.210334 |

Paired with production; week-cluster bootstrap intervals at 98.33%. Positive values favor the cap.

| Arm | ROI delta, pp [CI] | LL gain [CI] | Brier gain | Side flips | Flip units vs production | Capped games | LL gain on capped games (total) |
|---|---:|---:|---:|---:|---:|---:|---:|
| cap_k5 | -0.62 [-2.46, +0.96] | -0.000440 [-0.004576, +0.003225] | -0.000279 | 7 | -5.03 | 19 | -0.2273 |
| cap_k1 | +0.00 [+0.00, +0.00] | -0.000036 [-0.000610, +0.000494] | -0.000025 | 0 | +0.00 | 3 | -0.0297 |
| cap_k10 | -0.26 [-2.48, +1.92] | -0.000391 [-0.005605, +0.004474] | -0.000206 | 11 | -2.12 | 40 | +0.3341 |

### By season

| Arm | Season | W-L-P | Units | ROI | Log loss |
|---|---:|---:|---:|---:|---:|
| production | 2023 | 184-86-0 | +8.44 | +3.12% | 0.630814 |
| production | 2024 | 198-73-0 | +24.47 | +9.03% | 0.583169 |
| production | 2025 | 183-87-1 | -3.85 | -1.42% | 0.602822 |
| cap_k5 | 2023 | 182-88-0 | +2.67 | +0.99% | 0.633043 |
| cap_k5 | 2024 | 197-74-0 | +22.90 | +8.45% | 0.581829 |
| cap_k5 | 2025 | 184-86-1 | -1.55 | -0.57% | 0.603255 |
| cap_k1 | 2023 | 184-86-0 | +8.44 | +3.12% | 0.631323 |
| cap_k1 | 2024 | 198-73-0 | +24.47 | +9.03% | 0.582770 |
| cap_k1 | 2025 | 183-87-1 | -3.85 | -1.42% | 0.602822 |
| cap_k10 | 2023 | 183-87-0 | +3.96 | +1.47% | 0.635920 |
| cap_k10 | 2024 | 197-74-0 | +23.42 | +8.64% | 0.580158 |
| cap_k10 | 2025 | 184-86-1 | -0.45 | -0.17% | 0.601897 |
| market favorite | 2023 | 184-86-0 | +4.12 | +1.53% | 0.627349 |
| market favorite | 2024 | 194-77-0 | +14.11 | +5.21% | 0.587489 |
| market favorite | 2025 | 177-93-1 | -18.05 | -6.66% | 0.609383 |

## Post-hoc diagnostics

Added after the primary result; descriptive only and not part of the decision rule.

- cap_k5: 7 side flips worth -5.03u; flips on capped games: 2023_16_BAL_SF (-3.75u); the rest moved only through refitted coefficients (-1.28u).
- cap_k1: 0 side flips worth +0.00u; flips on capped games: none (+0.00u); the rest moved only through refitted coefficients (+0.00u).
- cap_k10: 11 side flips worth -2.12u; flips on capped games: 2023_15_NYJ_MIA, 2023_16_BAL_SF, 2025_12_BUF_HOU (+0.64u); the rest moved only through refitted coefficients (-2.76u).

Median refitted slope over all evaluation weeks, in log-odds per unit of hinge input. Winsorizing shrinks a hinge's training SD, and the ridge penalty applies to SD-standardized coefficients, so the raw slope is penalized less. With cap_k5 the median slope is steeper than production's for pass_1sd_pn, pass_1sd_np, pass_1sd_nn and flatter for pass_1sd_pp; a capped input can keep much of its contribution.

| Context | production | cap_k5 | cap_k1 | cap_k10 |
|---|---:|---:|---:|---:|
| pass_product | +0.048 | +0.036 | +0.048 | +0.029 |
| pass_1sd_pp | -1.133 | -0.932 | -1.133 | -0.026 |
| pass_1sd_pn | -1.080 | -1.745 | -1.080 | -3.222 |
| pass_1sd_np | -0.107 | -0.760 | -0.107 | -1.071 |
| pass_1sd_nn | +0.021 | +0.749 | +0.021 | +0.983 |

SF@SEA at its archived inputs, hinge contribution to the log-odds (Seattle probability): production +1.70 (93.9%); cap_k5 +1.08 (88.9%); cap_k1 +1.70 (93.9%); cap_k10 +1.08 (88.4%).

## 2026 diagnostic (not pooled)

65 common flat 1u bets; 65 binary proper scores.

| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Log loss | Brier |
|---|---:|---:|---:|---:|---:|---:|
| production | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.10% | 0.684668 | 0.243849 |
| cap_k5 | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.10% | 0.685035 | 0.244012 |
| cap_k1 | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.10% | 0.684668 | 0.243849 |
| cap_k10 | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.10% | 0.684988 | 0.243853 |
| market favorite | 41-24-0 | -4.05 | -6.23% ± 9.20 | -4.10% | 0.666270 | 0.235907 |

Paired with production; week-cluster bootstrap intervals at 98.33%. Positive values favor the cap.

| Arm | ROI delta, pp [CI] | LL gain [CI] | Brier gain | Side flips | Flip units vs production | Capped games | LL gain on capped games (total) |
|---|---:|---:|---:|---:|---:|---:|---:|
| cap_k5 | +0.00 [+0.00, +0.00] | -0.000368 [-0.007626, +0.005384] | -0.000164 | 0 | +0.00 | 1 | -0.1608 |
| cap_k1 | +0.00 [+0.00, +0.00] | +0.000000 [+0.000000, +0.000000] | +0.000000 | 0 | +0.00 | 0 | +0.0000 |
| cap_k10 | +0.00 [+0.00, +0.00] | -0.000321 [-0.001940, +0.003360] | -0.000004 | 0 | +0.00 | 6 | -0.1812 |

Basis: Current-season walk-forward diagnostic: 2026 games with outcomes in the frozen pack; not pooled.

## Native v1.16 snapshot replay (counterfactual)

Home-team probabilities at the archived inputs and moneylines, each arm refitted on earlier weeks. Not new forward snapshots; the native ledger is unchanged.

| Game | Market q | Archived | production | cap_k5 | cap_k1 | cap_k10 | Result | PN input |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| BAL@ATL | 61.6% | 71.0% | 71.0% | 70.9% | 71.0% | 70.6% | -7 | +0.000 |
| CHI@GB | 46.8% | 49.9% | 49.9% | 49.6% | 49.9% | 49.4% | +24 | +0.000 |
| CIN@MIA | 25.2% | 25.8% | 25.8% | 25.8% | 25.8% | 26.0% | -7 | +0.000 |
| CLE@NYJ | 55.1% | 54.4% | 54.4% | 54.3% | 54.4% | 53.9% | +5 | +0.000 |
| DEN@LAC | 36.9% | 41.3% | 41.3% | 41.3% | 41.3% | 41.1% | -6 | +0.000 |
| DET@ARI | 31.5% | 34.3% | 34.3% | 34.7% | 34.3% | 34.0% | -24 | +0.000 |
| HOU@TEN | 24.9% | 24.2% | 24.2% | 24.2% | 24.2% | 24.3% | -23 | +0.000 |
| IND@PIT | 57.2% | 54.0% | 54.0% | 54.0% | 54.0% | 54.1% | +12 | +0.000 |
| LV@NE | 63.1% | 61.1% | 61.1% | 61.2% | 61.1% | 61.4% | +28 | +0.000 |
| MIN@NO | 43.7% | 48.2% | 48.2% | 48.1% | 48.2% | 48.1% | -10 | +0.000 |
| NYG@WAS | 60.4% | 57.7% | 57.7% | 57.7% | 57.7% | 57.6% | +0 | +0.000 |
| PHI@JAX | 76.6% | 79.5% | 79.5% | 79.5% | 79.5% | 79.5% | +2 | +0.000 |
| SF@SEA | 59.3% | 93.9% | 93.9% | 88.9% | 93.9% | 88.4% | -3 | -1.623 |

Replay totals over 13 graded snapshots (0 pending): production +1.37u, LL 0.7386, 0 capped; cap_k5 +1.37u, LL 0.6895, 1 capped; cap_k1 +1.37u, LL 0.7386, 0 capped; cap_k10 +1.37u, LL 0.6845, 1 capped; market LL 0.5407; favorite +1.37u.

## Reproduction and limits

Production arm vs committed v1.16 history: max probability error 1.11e-16. Production arm vs archived v1.16 snapshots: max probability error 2.22e-16. All 236 weekly fits train strictly before their evaluation week; caps read only those training rows.
Caps change only the few games with large hinge values, so power is low and the historical comparison cannot settle whether the cap helps. Intervals omit model-design selection uncertainty. Exposed history; no forward confirmation. Adoption would be an owner decision and a new REVISION.

Run: `python research/context_support_cap.py`.
