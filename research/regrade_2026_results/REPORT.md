# 2026 regrade with the current model (boxscore-composite-v1.24)

Snapshot: `data/latest` generated 2026-11-16T16:07:06.175073+00:00, config signature `642b5f2feb99…`. Graded games: 149 (weeks 1–10); pending games are excluded.

**Basis.** Current-season walk-forward replay of the unchanged production recipe: each week's forecast uses only earlier games, the weekly decayed median map is fitted before that week, and the −2 replacement-QB adjustment is applied after mapping. This is a reconstruction (evidence basis 3 in CLAUDE.md: diagnostic), not native forward evidence. The replay line is the replay ledger's market line, which can differ from a saved lock's T-60 line. The owner switched the public pages to this regrade on 2026-11-16; v1.24's own saved locks stay the bet at their lock line and price, so the public row differs slightly. "Public decision" columns below are the superseded 2026-11-15 lock-continuity record.

## Headline

| Arm | W-L-P | Skips | n | Units | ROI ± SE | Cover |
|---|---|---|---|---|---|---|
| boxscore-composite-v1.24 replay, priced | 86-57-6 | 0 | 149 | +20.97 | +14.1% ± 7.5 | 60.1% |
| boxscore-composite-v1.24 replay, flat −110 | 86-57-6 | 0 | 149 | +21.18 | +14.2% ± 7.5 | 60.1% |
| Public pages from 2026-11-16 (own v1.24 locks at lock price, else replay) | 86-57-6 | 0 | 149 | +21.12 | +14.2% ± 7.5 | 60.1% |
| Superseded lock-continuity record, same games | 80-63-6 | 0 | 149 | +9.10 | +6.1% ± 7.6 | 55.9% |

Break-even cover at −110: 52.4%. ROI ± 1 SE; pushes stay in the denominator.
Replay pricing: 30 ESPN quotes captured by T-60, 99 closing estimates at the exact handicap, 20 assumed −110 (no ESPN price at that handicap).

## Same-row baselines, all graded games

| Arm | W-L-P | Skips | n | Units | ROI ± SE | Cover |
|---|---|---|---|---|---|---|
| Median map (production) (flat −110) | 86-57-6 | 0 | 149 | +21.18 | +14.2% ± 7.5 | 60.1% |
| Raw model spread (flat −110) | 80-63-6 | 0 | 149 | +9.73 | +6.5% ± 7.6 | 55.9% |
| Line-only map (flat −110) | 75-68-6 | 0 | 149 | +0.18 | +0.1% ± 7.7 | 52.4% |
| Always favorite (flat −110) | 75-68-6 | 0 | 149 | +0.18 | +0.1% ± 7.7 | 52.4% |
| Always home (flat −110) | 59-84-6 | 0 | 149 | -30.36 | -20.4% ± 7.6 | 41.3% |

- Median map minus line-only map: sides differ on 35 of 149; +21.00u, per game +0.141 ± 0.075 (1 SE).
- Median map minus raw model spread: sides differ on 65 of 149; +11.45u, per game +0.077 ± 0.103 (1 SE).
- Median map minus always favorite: sides differ on 49 of 149; +21.00u, per game +0.141 ± 0.089 (1 SE).

## Agreement with the superseded lock-continuity record

Same side on 139 of 149 games. Where the replay and the public decision differ, the public decision is a saved lock (different revision, line or inputs) or a replay under the same recipe with a different line.

| Public basis | Games | Same side | Replay W-L-P, units | Public W-L-P, units |
|---|---|---|---|---|
| 60-minute lock | 34 | 26 | 24-10-0, +12.02 | 18-16-0, +0.19 |
| Historical replay | 92 | 92 | 49-37-6, +7.41 | 49-37-6, +7.41 |
| Owner-requested retro lock | 21 | 19 | 12-9-0, +1.69 | 12-9-0, +1.66 |
| Recovered saved forecast | 2 | 2 | 1-1-0, -0.15 | 1-1-0, -0.15 |

Of the 10 disagreements: 2 have a different market line (saved T-60 line vs replay line), 4 carry a replay QB adjustment, and 10 were saved by an earlier revision. These games: 2026_07_LA_LV (replay W, public L), 2026_07_DAL_PHI (replay W, public L), 2026_08_ARI_DAL (replay W, public L), 2026_08_CLE_PIT (replay W, public L), 2026_08_TEN_CIN (replay W, public L), 2026_08_NE_MIA (replay L, public W), 2026_08_PHI_WAS (replay W, public L), 2026_09_DAL_IND (replay L, public W), 2026_09_BUF_MIN (replay W, public L), 2026_10_WAS_NYG (replay W, public L).

**Hindsight warning.** v1.19–v1.24 (including the replacement-QB rule adopted 2026-11-13 after an audit of saved picks) were designed after weeks 7–9 were observed. The replay's advantage on games where it disagrees with saved locks is therefore in-sample and is not evidence that the current model would have beaten those locks forward.

## By week (replay, priced)

| Week | W-L-P | Units | Same side as public |
|---|---|---|---|
| 1 | 10-5-1 | +4.17 | 16/16 |
| 2 | 10-6-0 | +2.84 | 16/16 |
| 3 | 6-8-2 | -2.44 | 16/16 |
| 4 | 7-7-2 | -0.83 | 16/16 |
| 5 | 8-6-1 | +1.37 | 15/15 |
| 6 | 9-5-0 | +3.15 | 14/14 |
| 7 | 10-4-0 | +5.31 | 12/14 |
| 8 | 8-6-0 | +1.24 | 9/14 |
| 9 | 8-7-0 | +0.09 | 13/15 |
| 10 | 10-3-0 | +6.07 | 12/13 |

## Native 60-minute locks against same-game baselines

Forward evidence basis 1: pregame-finalized locks of every revision (lock continuity), graded on the saved lock line. Owner-requested retro and recovered locks are excluded here.

| Arm | W-L-P | Skips | n | Units | ROI ± SE | Cover |
|---|---|---|---|---|---|---|
| Saved native locks, priced | 18-16-0 | 0 | 34 | +0.19 | +0.6% ± 16.5 | 52.9% |
| Median map (production) (flat −110) | 18-16-0 | 0 | 34 | +0.36 | +1.1% ± 16.6 | 52.9% |
| Raw model spread (flat −110) | 18-16-0 | 0 | 34 | +0.36 | +1.1% ± 16.6 | 52.9% |
| Line-only map (flat −110) | 15-19-0 | 0 | 34 | -5.36 | -15.8% ± 16.5 | 44.1% |
| Always favorite (flat −110) | 21-13-0 | 0 | 34 | +6.09 | +17.9% ± 16.1 | 61.8% |
| Always home (flat −110) | 15-19-0 | 0 | 34 | -5.36 | -15.8% ± 16.5 | 44.1% |

- Median map minus line-only map: sides differ on 9 of 34; +5.73u, per game +0.168 ± 0.168 (1 SE).
- Median map minus raw model spread: sides differ on 18 of 34; +0.00u, per game +0.000 ± 0.242 (1 SE).
- Median map minus always favorite: sides differ on 13 of 34; -5.73u, per game -0.168 ± 0.203 (1 SE).

Native locks by saving revision: v1.18 27, v1.21 1, v1.22 1, v1.24 5. n = 34 decided of the 100 needed for the map-versus-raw review.

## Limits

- Replay rows have no saved pregame timestamp; most are priced at the closing price for the exact handicap or an assumed −110. They are not lock-time returns.
- The recipe was selected on earlier seasons; 2026 is walk-forward but the model design was exposed to it. Per-band and per-week records are descriptive.
- Intervals crossing zero leave the effect unresolved; they do not show it is zero.
