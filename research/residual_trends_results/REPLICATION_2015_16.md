# Test 37 replication: the H8 trends and H7 on never-scored 2015-16

Protocol addendum in [RESIDUAL_TRENDS.md](../RESIDUAL_TRENDS.md), pushed (`816f35c`) before any 2013-16 forecast was compared with an outcome. Nothing was re-selected: the four trends are Test 37's forward set and H7 is as registered. A backward replication; it does not replace the forward test.

Basis: 2015-16 regular seasons, 510 binary games; v1.16 refit before every week from earlier rows of the frozen 2013-20 pack (training from 2013), v1.18 by the favorite penalty. The same refit reproduces the published 2017-20 forecasts to 1.1e-16. 2014 is a sensitivity basis (trained on 190 games of 2013) and decides nothing.

## Trends (z in the discovery direction; positive = the trend continues)

Replicated at z >= 2.24 (one-sided, Bonferroni over 4).

| Context x input | z 2017-22 | z 2023-25 | z 2015-16 | Effect/SD 2015-16 | Verdict | z 2014 (sensitivity) |
|---|---:|---:|---:|---:|---|---:|
| total <= 41 x `departure` | -2.10 | +1.25 | +0.00 | -0.001 | direction holds | +1.07 |
| all games x `departure` | -2.94 | +0.69 | +0.98 | -0.089 | direction holds | +1.72 |
| total 41.5-47 x `departure` | -2.79 | +0.16 | +1.37 | -0.161 | direction holds | +1.37 |
| total >= 47.5 x `d__for__rates_core__interception_pct` | -2.58 | +0.16 | +0.30 | -0.059 | direction holds | +1.28 |

## Wrong picks by third of the input signed toward the model's side (2017-22 cut points), 2015-16

| Context x input | Third | Bets | Wins - expected | Units (same-row favorite) |
|---|---|---:|---:|---:|
| total <= 41 x `departure` | low | 20 | -0.6 | -2.82 (-2.82) |
| total <= 41 x `departure` | middle | 12 | -0.4 | -0.90 (-0.90) |
| total <= 41 x `departure` | high | 29 | +0.8 | +1.76 (+5.20) |
| all games x `departure` | low | 177 | +4.1 | -11.07 (-11.07) |
| all games x `departure` | middle | 139 | -2.3 | -5.37 (-5.37) |
| all games x `departure` | high | 191 | -5.7 | -1.08 (-9.57) |
| total 41.5-47 x `departure` | low | 96 | +6.2 | -1.31 (-1.31) |
| total 41.5-47 x `departure` | middle | 84 | +0.7 | -0.02 (-0.02) |
| total 41.5-47 x `departure` | high | 120 | -6.6 | -6.08 (-10.56) |
| total >= 47.5 x `d__for__rates_core__interception_pct` | low | 50 | -1.3 | -2.23 (-3.05) |
| total >= 47.5 x `d__for__rates_core__interception_pct` | middle | 59 | +2.1 | +2.59 (-5.81) |
| total >= 47.5 x `d__for__rates_core__interception_pct` | high | 37 | -4.6 | -8.50 (-6.73) |

## H7: departure slope, high-total band minus low-total band

| Basis | Model | b high (n) | b low (n) | Delta ± SE | Verdict |
|---|---|---:|---:|---:|---|
| 2015-16 | v1.16 | +0.36 ± 0.57 (147) | +0.55 ± 0.93 (63) | -0.19 ± 1.09 | contradicted |
| 2015-16 | v1.18 | +1.69 ± 1.13 (147) | +0.69 ± 1.70 (63) | +1.00 ± 2.04 | secondary |
| 2014 (sensitivity) | v1.16 | -0.78 ± 0.80 (87) | -1.13 ± 1.01 (22) | +0.35 ± 1.29 | sensitivity only |
| 2014 (sensitivity) | v1.18 | -1.05 ± 1.19 (87) | -1.22 ± 1.91 (22) | +0.17 ± 2.26 | secondary |

History for comparison (v1.16): 2017-22 delta +0.93 ± 0.63; 2023-25 +1.07 ± 0.73.

## Flat 1u ROI by context (goal metric; v1.18 and v1.16 make the same bets)

| Basis | Context | W-L-P | Units | ROI ± SE | Null | Same-row favorite |
|---|---|---:|---:|---:|---:|---:|
| 2015-16 | all games | 320-185-2 | -17.52 | -3.46% ± 3.38 | -2.40% | -26.01u (-5.13%) |
| 2015-16 | total <= 41 | 38-23-0 | -1.97 | -3.23% ± 9.99 | -2.41% | +1.47u (+2.41%) |
| 2015-16 | total 41.5-47 | 192-107-1 | -7.42 | -2.47% ± 4.38 | -2.40% | -11.89u (-3.96%) |
| 2015-16 | total >= 47.5 | 90-55-1 | -8.14 | -5.57% ± 6.34 | -2.40% | -15.59u (-10.68%) |
| 2015-16 | log-loss gain vs market, all games (v1.18) | | | +0.00005 | | |
| 2014 (sensitivity) | all games | 164-89-1 | -10.40 | -4.09% ± 4.65 | -2.40% | -9.03u (-3.55%) |
| 2014 (sensitivity) | total <= 41 | 13-9-0 | -3.06 | -13.93% ± 16.38 | -2.39% | -3.78u (-17.18%) |
| 2014 (sensitivity) | total 41.5-47 | 99-47-1 | +2.75 | +1.87% ± 6.11 | -2.40% | -4.50u (-3.06%) |
| 2014 (sensitivity) | total >= 47.5 | 52-33-0 | -10.09 | -11.87% ± 7.96 | -2.40% | -0.75u (-0.89%) |
| 2014 (sensitivity) | log-loss gain vs market, all games (v1.18) | | | -0.01569 | | |

Limits: older seasons with different rules, play styles and pre-2017 data quality; 2015-16 is a third basis, never pooled with 2017-22 or 2023-25. Expected z if a trend were real at its discovery size was 1.0-1.7 (protocol), so "direction holds" is the likely best case and "reversed" counts against a trend.

Run: `python research/residual_trends.py --replicate`.
