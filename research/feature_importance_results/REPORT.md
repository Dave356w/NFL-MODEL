# Test 38: feature importance, interactions and correlation structure

Protocol: [FEATURE_IMPORTANCE.md](../FEATURE_IMPORTANCE.md), pushed (`0d850c6`) before parts B-D were computed; part A was computed first and is post hoc. Diagnostic only; production v1.18 and the ledger are unchanged.

Bases (never pooled): 2015-16 510, 2017-22 1559, 2023-25 815 binary games; native week 5 13 (part A only). Production reproduces the published forecasts: 2017-20 1.1e-16, 2021-22 2.3e-13, 2023-25 1.1e-16; native snapshots 0.0e+00.

Units: log loss per game x1000. Positive = the input makes the forecast more accurate. z is week-clustered.

## B. Drop-column importance (refit without the input)

Importance = log loss without the input minus with it. "Units" = production minus the arm on the same bets.

| Arm | 2015-16 | 2017-22 | 2023-25 | Same sign | Units (15-16 / 17-22 / 23-25) | Side flips |
|---|---:|---:|---:|---|---|---:|
| off 1st-down rate | -0.13 (-0.9) | +0.49 (+2.6) | +0.02 (+0.1) |  | -2.2 / +18.8 / +14.0 | 25 |
| def penalty yds | -0.17 (-0.6) | +0.01 (+0.0) | +0.88 (+2.2) |  | -0.5 / +21.2 / +6.1 | 30 |
| def 1st-down rate | +0.58 (+0.9) | -0.15 (-0.8) | +0.42 (+1.2) |  | -9.3 / +16.5 / +8.7 | 25 |
| WRTE out | -0.12 (-0.1) | +0.05 (+0.1) | +0.26 (+1.1) |  | -3.4 / +11.7 / +2.5 | 32 |
| off fumbles | +1.00 (+1.0) | -0.21 (-0.6) | +0.36 (+0.7) |  | +4.1 / +17.5 / +8.6 | 35 |
| off INT % | +0.02 (+0.1) | -0.06 (-0.2) | +0.08 (+0.3) |  | +1.9 / +5.0 / +4.2 | 26 |
| pass_product | -0.15 (-1.5) | -0.06 (-0.3) | +0.99 (+1.9) |  | -0.0 / +9.7 / +0.3 | 15 |
| RB out | +0.82 (+0.9) | -0.34 (-0.9) | -0.03 (-0.1) |  | +6.4 / +2.8 / +5.4 | 39 |
| def fumbles | +0.21 (+0.7) | -0.30 (-1.7) | +0.30 (+0.9) |  | -10.9 / +4.2 / +5.3 | 19 |
| group: pass tail hinges | -0.12 (-0.1) | -0.47 (-0.5) | +1.03 (+0.6) |  | -1.8 / +11.3 / +9.7 | 35 |
| LB out | +0.02 (+0.0) | -0.26 (-1.0) | +0.29 (+0.8) |  | -8.1 / +2.4 / +2.1 | 19 |
| pass_1sd_np | +0.43 (+0.7) | -0.29 (-0.3) | -0.07 (-0.6) |  | -5.3 / +7.4 / +0.1 | 16 |
| group: unit absences | +0.24 (+0.1) | -0.40 (-0.4) | +0.01 (+0.0) |  | +6.1 / +25.6 / +9.2 | 68 |
| group: defense box rates | -0.23 (-0.2) | -1.07 (-1.7) | +1.92 (+1.5) |  | -8.8 / +4.8 / +23.0 | 76 |
| def plays | +0.30 (+0.7) | -0.22 (-0.8) | -0.06 (-0.5) |  | +1.0 / -1.8 / +4.2 | 30 |
| def rush yds/att | -0.30 (-1.2) | -0.18 (-0.6) | +0.60 (+1.2) |  | -3.6 / +7.3 / +12.6 | 27 |
| pass_1sd_pn | -0.36 (-1.5) | -0.02 (-0.1) | +1.40 (+0.8) |  | +0.0 / +7.6 / +4.9 | 17 |
| group: offense box rates | -0.19 (-0.1) | -0.82 (-1.4) | +0.26 (+0.3) |  | -3.6 / +19.2 / +10.1 | 77 |
| def pass yds/play | -0.27 (-0.6) | +0.02 (+0.2) | -0.38 (-0.8) |  | -2.6 / +1.8 / +1.3 | 16 |
| pass_1sd_pp | -0.12 (-0.4) | -0.05 (-0.4) | -0.23 (-0.5) | yes | -2.2 / +7.8 / +3.7 | 7 |
| off plays | -0.07 (-0.2) | -0.31 (-1.2) | +0.01 (+0.1) |  | -13.5 / -0.2 / +3.2 | 20 |
| off pass yds/play | -0.00 (-0.0) | -0.16 (-0.6) | -0.14 (-1.0) | yes | -1.3 / +14.5 / -4.0 | 20 |
| def INT % | -0.26 (-1.5) | -0.21 (-1.3) | +0.63 (+1.2) |  | -4.4 / +10.0 / +4.8 | 25 |
| off penalty yds | -0.13 (-0.1) | -0.21 (-1.4) | -0.03 (-0.1) | yes | -3.8 / +8.4 / +3.8 | 24 |
| max_deficit | -0.13 (-1.0) | -0.02 (-0.1) | -0.17 (-0.8) | yes | -8.1 / +6.2 / +1.7 | 10 |
| max_lead | +0.14 (+0.3) | -0.17 (-1.3) | -0.12 (-1.1) |  | -6.7 / +1.8 / +0.0 | 10 |
| DB out | -0.61 (-1.0) | +0.33 (+0.6) | -0.46 (-1.7) |  | -1.0 / +9.2 / +10.3 | 33 |
| DL out | -0.35 (-1.3) | -0.15 (-0.7) | -0.05 (-0.2) | yes | -3.8 / +8.5 / +2.0 | 20 |
| off rush yds/att | -0.29 (-0.3) | -0.40 (-2.1) | +0.02 (+0.2) |  | +2.6 / +10.9 / +6.4 | 17 |
| qb_delta | -0.66 (-1.4) | -0.15 (-0.4) | -0.26 (-0.6) | yes | -4.6 / -6.2 / +1.0 | 31 |
| group: lead/deficit peaks | -0.07 (-0.1) | -0.21 (-1.1) | -0.37 (-1.3) | yes | -6.7 / +6.0 / +0.0 | 10 |
| OL out | -0.67 (-1.2) | -0.18 (-0.6) | -0.13 (-1.0) | yes | -6.4 / +15.8 / +7.6 | 28 |
| pass_1sd_nn | -0.02 (-0.5) | -0.14 (-1.2) | -0.18 (-1.2) | yes | -2.0 / +5.6 / +1.3 | 13 |
| site (supplementary) | -0.47 (-0.7) | -0.52 (-1.2) | -0.54 (-1.3) | yes | -1.4 / +11.8 / +4.3 | 46 |

**Across the 28 single-input arms** (post-hoc summary, all games):

- 2015-16: the refit without the input scores better in 19 of 28 (mean importance -0.047); removing it costs production units in 5 of 28 (median -3.0u; 160 side flips).
- 2017-22: the refit without the input scores better in 23 of 28 (mean importance -0.119); removing it costs production units in 25 of 28 (median +7.7u; 331 side flips).
- 2023-25: the refit without the input scores better in 14 of 28 (mean importance +0.142); removing it costs production units in 26 of 28 (median +4.0u; 138 side flips).
- Same sign on all three bases: 8 of 28, all of them negative (8 negative, 0 positive): DL out, OL out, qb_delta, off pass yds/play, off penalty yds, max_deficit, pass_1sd_nn, pass_1sd_pp.
- Reading: no input reliably earns its place in log loss once the model is refit without it; the inputs with a consistent sign are ones the model scores slightly better without, which points to mild over-fitting (the same direction as Test 37's oversized departures). Removals cost units on 2017-25 but not on never-scored 2015-16. Design tuning cannot explain all of that: a post-hoc split shows the same on 2017-20 (22 of 28 arms), scored only after v1.16 was fixed. Era or chance remain open; each arm flips about 10 bets per basis, so units are noisy.

Cells at |z| >= 2 across arms, contexts and bases: 14 of 408 (about 19 expected by chance). The site arm is supplementary (not in the protocol's 28).

**Context cells at |z| >= 2:** off 1st-down rate, total 41.5-47, 2015-16: -0.45 (z -2.4); off 1st-down rate, total 41.5-47, 2017-22: +0.52 (z +2.1); off INT %, total 41.5-47, 2015-16: -0.56 (z -2.4); def plays, total 41.5-47, 2015-16: +0.86 (z +2.1); def 1st-down rate, total >= 47.5, 2023-25: +2.16 (z +2.4); def INT %, total 41.5-47, 2015-16: -0.43 (z -2.3); def penalty yds, total >= 47.5, 2023-25: +2.54 (z +2.8); DL out, total <= 41, 2015-16: -1.25 (z -2.1); pass_product, total >= 47.5, 2023-25: +2.28 (z +2.4); pass_1sd_pp, total <= 41, 2023-25: +0.30 (z +2.4); group: defense box rates, total >= 47.5, 2017-22: -1.91 (z -2.2)

## C. Interaction scan

1624 cells per basis (406 interactions x 4 contexts). |z| >= 3: 2015-16 0, 2017-22 1, 2023-25 0 (about 4 expected by chance on each). Bar for confirmation and replication: one-sided z >= 1.64.

| Context | Interaction | z 2017-22 | z 2023-25 (dir.) | Verdict | z 2015-16 (dir.) | Verdict |
|---|---|---:|---:|---|---:|---|
| total 41.5-47 | def rush yds/att x pass_product | +3.93 | -0.20 | reversed | -0.48 | reversed |

## A. Per-game attribution (post hoc)

Effect of removing each fitted contribution from each game (no refit), by group, all games:

| Group | 2015-16 | 2017-22 | 2023-25 | native wk5 | Culprit / helper share 2017-22 |
|---|---:|---:|---:|---:|---:|
| offense box rates | -0.68 (-0.4) | -0.73 (-1.1) | +1.06 (+1.1) | -8.42 | 23% / 24% |
| defense box rates | +0.76 (+0.6) | -0.62 (-0.9) | +1.35 (+0.9) | -4.30 | 21% / 21% |
| QB projection | -0.62 (-1.3) | -0.15 (-0.4) | -0.30 (-0.7) | -3.65 | 6% / 6% |
| unit absences | +0.23 (+0.1) | -0.25 (-0.3) | -0.01 (-0.0) | -4.75 | 24% / 29% |
| lead/deficit peaks | -0.10 (-0.1) | -0.33 (-1.2) | -0.86 (-1.8) | -0.53 | 1% / 1% |
| pass matchup product | -0.16 (-1.3) | -0.19 (-0.8) | +0.93 (+1.4) | +2.66 | 3% / 2% |
| pass tail hinges | +0.25 (+0.3) | -0.71 (-0.8) | +1.03 (+0.5) | -22.88 | 4% / 5% |
| home field | -0.47 (-0.7) | -0.46 (-1.1) | -0.51 (-1.2) | +0.14 | 18% / 12% |

Feature x context cells with the same sign on all three bases: 38 of 116 (about 29 expected). Most harmful and most helpful of those (combined z = sum/sqrt 3, for ranking only):

- max_deficit, total 41.5-47: z -2.26 / -1.66 / -1.26 (combined -2.99)
- site, total 41.5-47: z -1.01 / -1.56 / -1.66 (combined -2.44)
- max_deficit, all games: z -1.02 / -1.68 / -1.42 (combined -2.38)
- pass_1sd_nn, all games: z -0.27 / -1.88 / -1.50 (combined -2.10)
- DL out, total <= 41: z -1.60 / -1.67 / -0.11 (combined -1.95)
- site, total >= 47.5: z +0.51 / +1.57 / +1.11 (combined +1.84)
- def penalty yds, total >= 47.5: z +0.99 / +0.51 / +2.53 (combined +2.33)
- off INT %, total >= 47.5: z +2.23 / +2.01 / +0.94 (combined +2.99)

Worst games against the market, with the inputs that hurt most (contribution, effect x1000):

- 2023_15_NYJ_MIA (total 36.0): market 0.74, model 0.37, home won; -698 vs market. Hurt: pass_1sd_pn -1.63 (-700), off fumbles -0.08 (-51), max_deficit -0.08 (-47)
- 2024_01_NYJ_SF (total 43.0): market 0.62, model 0.35, home won; -579 vs market. Hurt: pass_1sd_pn -0.96 (-518), pass_product -0.16 (-99), max_deficit -0.08 (-51)
- 2024_18_NYG_PHI (total 36.5): market 0.58, model 0.44, home won; -275 vs market. Hurt: def pass yds/play -0.19 (-101), qb_delta -0.16 (-85), pass_product -0.11 (-62)
- 2021_04_DET_CHI (total 42.0): market 0.58, model 0.24, home won; -886 vs market. Hurt: pass_1sd_np -1.20 (-758), off 1st-down rate -0.15 (-110), qb_delta -0.12 (-91)
- 2018_01_ATL_PHI (total 44.5): market 0.50, model 0.29, home won; -548 vs market. Hurt: LB out -0.32 (-217), WRTE out -0.13 (-94), DB out -0.11 (-74)
- 2021_01_DEN_NYG (total 41.5): market 0.43, model 0.65, home lost; -488 vs market. Hurt: DB out +0.31 (-191), RB out +0.16 (-99), OL out +0.11 (-72)
- 2015_01_KC_HOU (total 41.0): market 0.50, model 0.67, home lost; -403 vs market. Hurt: DB out +0.21 (-136), OL out +0.17 (-108), WRTE out +0.16 (-103)
- 2015_13_HOU_BUF (total 42.0): market 0.57, model 0.40, home won; -370 vs market. Hurt: WRTE out -0.23 (-130), off penalty yds -0.16 (-93), off rush yds/att -0.15 (-89)
- 2016_17_OAK_DEN (total 40.0): market 0.53, model 0.37, home won; -356 vs market. Hurt: off fumbles -0.26 (-156), def 1st-down rate -0.12 (-74), qb_delta -0.10 (-64)

Native week 5 (locked v1.16 snapshots, v1.18 view):

- SF@SEA: market 0.59, model 0.70, away won, -305 vs market. Hurt: pass_1sd_pn +1.70 (-226), pass_product +0.39 (-53). Helped: def penalty yds -0.10 (+14), def 1st-down rate -0.09 (+13)
- MIN@NO: market 0.44, model 0.48, away won, -84 vs market. Hurt: def 1st-down rate +0.17 (-77), off fumbles +0.10 (-48). Helped: off INT % -0.13 (+63), def INT % -0.07 (+36)
- DEN@LAC: market 0.37, model 0.41, away won, -73 vs market. Hurt: off INT % +0.20 (-74), def INT % +0.08 (-34). Helped: def penalty yds -0.23 (+101), WRTE out -0.04 (+17)
- IND@PIT: market 0.57, model 0.54, home won, -57 vs market. Hurt: off INT % -0.12 (-52), off fumbles -0.05 (-25). Helped: def INT % +0.09 (+41), def fumbles +0.05 (+22)
- BAL@ATL: market 0.62, model 0.64, away won, -53 vs market. Hurt: qb_delta +0.26 (-33), off INT % +0.20 (-26). Helped: def 1st-down rate -0.05 (+6), off 1st-down rate -0.03 (+3)
- DET@ARI: market 0.31, model 0.34, away won, -42 vs market. Hurt: off INT % +0.20 (-46), pass_1sd_pp +0.16 (-44). Helped: pass_product -0.22 (+81), off 1st-down rate -0.08 (+27)
- LV@NE: market 0.63, model 0.61, home won, -32 vs market. Hurt: pass_product -0.07 (-27), off rush yds/att -0.06 (-21). Helped: off INT % +0.07 (+27), off 1st-down rate +0.05 (+21)
- BUF@LA: market 0.61, model 0.62, away won, -30 vs market. Hurt: pass_1sd_pn +0.21 (-26), pass_product +0.12 (-15). Helped: def 1st-down rate -0.11 (+13), off fumbles -0.06 (+7)
- CLE@NYJ: market 0.55, model 0.54, home won, -14 vs market. Hurt: off INT % -0.14 (-24), def INT % -0.11 (-21). Helped: pass_product +0.15 (+69), def 1st-down rate +0.07 (+35)
- CIN@MIA: market 0.25, model 0.26, away won, -8 vs market. Hurt: off plays +0.07 (-10), off INT % +0.06 (-9). Helped: off 1st-down rate -0.10 (+27), pass_product -0.06 (+15)
- HOU@TEN: market 0.25, model 0.25, away won, +2 vs market. Hurt: off INT % +0.11 (-6), off fumbles +0.05 (-3). Helped: off penalty yds -0.06 (+7), def penalty yds -0.05 (+6)
- PHI@JAX: market 0.77, model 0.77, home won, +8 vs market. Hurt: def penalty yds -0.10 (-5), off INT % -0.07 (-3). Helped: off 1st-down rate +0.12 (+6), def INT % +0.11 (+5)
- CHI@GB: market 0.47, model 0.50, home won, +64 vs market. Hurt: def INT % -0.06 (-29), def penalty yds -0.06 (-28). Helped: off plays +0.09 (+46), pass_product +0.07 (+35)

## D. Correlation structure

Input pairs with |r| >= 0.5 on all three bases: 4.

- max_lead vs max_deficit: -0.81 / -0.84 / -0.82
- off pass yds/play vs off 1st-down rate: +0.77 / +0.79 / +0.85
- def pass yds/play vs def 1st-down rate: +0.79 / +0.70 / +0.74
- off pass yds/play vs max_lead: +0.52 / +0.61 / +0.74

Highest variance inflation factors (collinearity): off 1st-down rate 5.2/5.5/7.3; max_deficit 5.2/5.0/5.2; max_lead 4.9/4.6/5.0; off pass yds/play 4.0/4.4/6.0; def 1st-down rate 5.6/4.1/4.3; def pass yds/play 4.8/3.3/3.6

Group contributions across games, mean r over bases. Most offsetting: pass matchup product vs pass tail hinges -0.10; offense box rates vs lead/deficit peaks -0.09; lead/deficit peaks vs pass matchup product -0.02; QB projection vs lead/deficit peaks -0.02.
Group accuracy effects across games (do they fail together?). Most aligned: defense box rates vs lead/deficit peaks +0.07; unit absences vs home field +0.07; defense box rates vs home field +0.07; pass tail hinges vs home field +0.05. Most opposed: offense box rates vs lead/deficit peaks -0.10; offense box rates vs pass tail hinges -0.04; QB projection vs pass tail hinges -0.03; QB projection vs unit absences -0.03.

## Limits

All bases are exposed history; part A was seen before the protocol; drop-column importance is correlated with part A. Multiplicity is large (396 importance cells, 1,624 interaction cells per basis). Nothing here changes the model; removing, reweighting or adding a term is a new REVISION and the owner's decision, and only forward data can test it cleanly. Full tables: `importance.csv`, `interactions.csv.gz`, `attribution_summary.csv`, `attribution_per_game.csv.gz`, `input_correlations.csv`, `vif.csv`.

Run: `python research/feature_importance.py`.
