# Test 37: input trends in the model's wrong picks, by total context

Protocol: [RESIDUAL_TRENDS.md](../RESIDUAL_TRENDS.md), pushed (`72549f5`) before any residual was computed. Production v1.18, its v1.16 shadow and the ledger are unchanged.

**Result.** 4 of 120 discovery cells reached |z| >= 2.0. On 2023-25, 0 confirmed (one-sided z >= 2.24), 4 kept the discovery direction without confirming, 0 reversed. H8 carries 4 forward.

Bases: discovery 1559 binary games (2017-22 reconstructions, prior-week fits (exposed history; hypothesis generation only)); confirmation 815 (2023-25 held-out reproduction (exposed development data; trends chosen on 2017-22 only)).

Residual r = y - p with p production v1.18. z > 0: where the input (home minus away) is high, the home team won more often than the model said, so the model under-weights the input in that context. Effect per SD is the log-odds per SD of the input the data would add (one Newton step). z is cluster-robust by week.

## Candidates (selected on 2017-22, tested on 2023-25)

| Context | Input | n D | z D | effect/SD D | n C | z C (discovery direction) | effect/SD C | Verdict | z 2026 | z D / z C under v1.16 |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| all games | `departure` | 1559 | -2.94 | -0.163 | 815 | +0.69 | -0.056 | direction holds | -1.05 | -3.92 / -1.11 |
| total 41.5-47 | `departure` | 765 | -2.79 | -0.247 | 425 | +0.16 | -0.018 | direction holds | +0.06 | -3.64 / -0.31 |
| total >= 47.5 | `d__for__rates_core__interception_pct` | 539 | -2.58 | -0.231 | 203 | +0.16 | -0.022 | direction holds | +1.04 | -2.00 / +0.01 |
| total <= 41 | `departure` | 255 | -2.10 | -0.199 | 187 | +1.25 | -0.237 | direction holds | +0.47 | -2.77 / -1.58 |

Forward set (H8): total <= 41 x `departure`, all games x `departure`, total 41.5-47 x `departure`, total >= 47.5 x `d__for__rates_core__interception_pct`.

## Wrong picks by third of the input, signed toward the model's side

Cut points are the 2017-22 terciles of the signed input in that context. "Wins - expected" is the model side's wins minus the wins its own probabilities expected; negative means more wrong picks than the model said.

**all games x `departure`** (z D -2.94, z C +0.69; cuts -0.0291, 0.0326)

| Third | Bets D | Wins - exp D | Units D (favorite) | Bets C | Wins - exp C | Units C (favorite) |
|---|---:|---:|---:|---:|---:|---:|
| low | 522 | +37.6 | +13.80 (+13.80) | 262 | +13.0 | -3.50 (-3.50) |
| middle | 521 | -12.1 | -32.52 (-32.52) | 288 | +11.6 | +9.65 (+9.65) |
| high | 516 | -11.0 | -5.49 (-40.49) | 262 | +11.5 | +22.91 (-5.97) |

**total 41.5-47 x `departure`** (z D -2.79, z C +0.16; cuts -0.0393, 0.0296)

| Third | Bets D | Wins - exp D | Units D (favorite) | Bets C | Wins - exp C | Units C (favorite) |
|---|---:|---:|---:|---:|---:|---:|
| low | 257 | +22.9 | +10.48 (+10.48) | 134 | +9.1 | +2.14 (+2.14) |
| middle | 255 | -7.3 | -19.68 (-19.68) | 144 | +15.0 | +17.36 (+17.36) |
| high | 255 | -9.6 | -10.69 (-25.94) | 146 | +5.4 | +10.83 (-8.63) |

**total >= 47.5 x `d__for__rates_core__interception_pct`** (z D -2.58, z C +0.16; cuts -0.55, 0.11)

| Third | Bets D | Wins - exp D | Units D (favorite) | Bets C | Wins - exp C | Units C (favorite) |
|---|---:|---:|---:|---:|---:|---:|
| low | 179 | +13.3 | +17.21 (+12.54) | 40 | +0.5 | -0.07 (-4.45) |
| middle | 179 | -0.2 | -1.91 (-13.10) | 97 | +10.2 | +14.41 (+8.74) |
| high | 178 | +2.3 | -0.73 (-9.28) | 65 | +5.2 | +7.12 (+0.67) |

**total <= 41 x `departure`** (z D -2.10, z C +1.25; cuts -0.0376, 0.0335)

| Third | Bets D | Wins - exp D | Units D (favorite) | Bets C | Wins - exp C | Units C (favorite) |
|---|---:|---:|---:|---:|---:|---:|
| low | 86 | +6.7 | +2.47 (+2.47) | 62 | -2.6 | -9.74 (-9.74) |
| middle | 85 | -6.7 | -12.40 (-12.40) | 61 | -4.7 | -8.89 (-8.89) |
| high | 85 | -6.9 | -8.97 (-4.30) | 63 | -1.9 | -4.10 (+2.98) |

## Flat 1u ROI by context (goal metric; v1.18 and v1.16 make the same bets)

| Basis | Context | W-L-P | Units | ROI ± SE | Null | Same-row favorite |
|---|---|---:|---:|---:|---:|---:|
| discovery | all games | 1041-511-7 | -24.22 | -1.55% ± 1.82 | -2.61% | -59.21u (-3.80%) |
| discovery | total <= 41 | 158-96-2 | -18.91 | -7.39% ± 4.65 | -2.57% | -14.23u (-5.56%) |
| discovery | total 41.5-47 | 514-248-5 | -19.88 | -2.59% ± 2.55 | -2.64% | -35.14u (-4.58%) |
| discovery | total >= 47.5 | 369-167-0 | +14.57 | +2.72% ± 3.12 | -2.59% | -9.84u (-1.84%) |
| confirmation | all games | 565-246-1 | +29.06 | +3.58% ± 2.52 | -4.10% | +0.18u (+0.02%) |
| confirmation | total <= 41 | 111-75-0 | -22.73 | -12.22% ± 5.47 | -4.09% | -15.65u (-8.41%) |
| confirmation | total 41.5-47 | 307-117-0 | +30.32 | +7.15% ± 3.39 | -4.10% | +10.87u (+2.56%) |
| confirmation | total >= 47.5 | 147-54-1 | +21.46 | +10.62% ± 5.08 | -4.10% | +4.96u (+2.45%) |
| diagnostic | all games | 40-25-0 | -5.20 | -8.00% ± 9.37 | -4.10% | -4.05u (-6.23%) |
| diagnostic | total <= 41 | 9-2-0 | +2.48 | +22.59% ± 19.66 | -4.10% | +0.50u (+4.58%) |
| diagnostic | total 41.5-47 | 18-14-0 | -4.79 | -14.98% ± 13.87 | -4.12% | -1.29u (-4.02%) |
| diagnostic | total >= 47.5 | 13-9-0 | -2.89 | -13.13% ± 16.09 | -4.08% | -3.27u (-14.85%) |

## Strongest cells on each basis (v1.18), for context

*discovery*: all games x `departure` -2.94; total 41.5-47 x `departure` -2.79; total >= 47.5 x `d__for__rates_core__interception_pct` -2.58; total <= 41 x `departure` -2.10; total 41.5-47 x `market_logit` +1.93; total 41.5-47 x `d__avail__DL_out_cs` -1.89; total >= 47.5 x `d__for__rates_core__first_down_rate` +1.66; total >= 47.5 x `d__avail__OL_out_cs` +1.63

*confirmation*: total >= 47.5 x `pass_1sd_pn` -2.34; total 41.5-47 x `d__avail__qb_delta` +2.18; total >= 47.5 x `pass_product` +1.80; total >= 47.5 x `d__allowed__rates_core__penalty_yards_per_game` -1.77; total >= 47.5 x `d__allowed__rates_core__plays_per_game` -1.77; total >= 47.5 x `market_logit` +1.70; total >= 47.5 x `d__max_deficit` -1.66; all games x `pass_1sd_pn` -1.59

Cells at |z| >= 2: discovery 4, confirmation 2 of 120 (about 6 expected with no effect, fewer independent).

## H7 on history (source figures; the forward test is in PREREGISTRATION.md)

| Basis | Model | b high (n) | b low (n) | Delta ± SE |
|---|---|---:|---:|---:|
| discovery | v1.16 | +0.71 ± 0.38 (539) | -0.22 ± 0.51 (255) | +0.93 ± 0.63 |
| discovery | v1.18 | +1.49 ± 0.66 (539) | -0.05 ± 0.67 (255) | +1.53 ± 0.94 |
| confirmation | v1.16 | +0.99 ± 0.48 (203) | -0.07 ± 0.55 (187) | +1.07 ± 0.73 |
| confirmation | v1.18 | +1.44 ± 0.68 (203) | -0.17 ± 0.78 (187) | +1.60 ± 1.03 |
| 2017-20 only | v1.16 | +0.73 ± 0.49 (369) | -0.30 ± 0.69 (162) | +1.04 ± 0.85 |

## Reproduction and limits

2021-22 refit vs `retro_ledger.csv` (v1.18): max error 6.9e-16. Published totals matched: 2017-20 1017 bets -0.42u; 2023-25 812 bets +29.06u.
All bases are exposed history; the total bands were chosen after aggregate slices were seen. 120 cells per basis, correlated and nested, so some discovery cells pass by luck; confirmation is one-sided and Bonferroni over the candidates. A confirmed trend changes nothing by itself; acting on it is a new REVISION and the owner's decision. Full grids for both models and all bases: `scan.csv`.

Run: `python research/residual_trends.py`; forward: `--forward`.
