# AV research: input audit

## Sources and coverage

nflreadpy 0.1.5; REG season 2013–2025 (snap counts start 2013).
Snap share mapped to GSIS ids: 99.98%; box-score yards with no snap row: 0.007%; rows with no unit (K/P/LS, not modelled): 21042.

| Season | Player-games | Players | Games |
|---|---:|---:|---:|
| 2013 | 22820 | 1927 | 256 |
| 2014 | 22879 | 1962 | 256 |
| 2015 | 22863 | 1971 | 256 |
| 2016 | 22902 | 1993 | 256 |
| 2017 | 22877 | 2008 | 256 |
| 2018 | 22895 | 2020 | 256 |
| 2019 | 22871 | 2025 | 256 |
| 2020 | 23778 | 2189 | 256 |
| 2021 | 25248 | 2296 | 272 |
| 2022 | 25162 | 2190 | 271 |
| 2023 | 25322 | 2142 | 272 |
| 2024 | 25373 | 2189 | 272 |
| 2025 | 25374 | 2187 | 272 |

## rAV against PFR career AV (validation only; never a feature)

Weighted career rAV (100% best season, 95% next, ...) against nflverse `draft_picks.w_av` for players drafted 2013–2021. Per game: both divided by career games (rAV: games with a snap; PFR: `games`), players with ≥ 16.

| Unit | Players | Pearson | Spearman | Mean rAV_w | Mean PFR w_av | Per-game players | Per-game Pearson | Per-game Spearman |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 2127 | 0.956 | 0.958 | 17.8 | 17.4 | 1642 | 0.891 | 0.904 |
| QB | 85 | 0.995 | 0.983 | 24.0 | 24.7 | 50 | 0.933 | 0.931 |
| OL | 346 | 0.971 | 0.989 | 24.2 | 22.1 | 276 | 0.806 | 0.820 |
| RB | 189 | 0.992 | 0.991 | 20.8 | 16.1 | 154 | 0.977 | 0.974 |
| WRTE | 385 | 0.997 | 0.993 | 11.9 | 14.5 | 314 | 0.986 | 0.980 |
| DL | 323 | 0.961 | 0.976 | 18.1 | 19.1 | 274 | 0.859 | 0.820 |
| LB | 329 | 0.971 | 0.982 | 21.0 | 18.1 | 245 | 0.863 | 0.875 |
| DB | 432 | 0.960 | 0.986 | 14.3 | 14.4 | 329 | 0.786 | 0.849 |

## Replacement levels and rookie draft priors (fitted on earlier seasons only)

Replacement = 25th percentile of player-season rAV per full game (≥ 4 full-game equivalents), the three seasons before. Rookie prior = a ln(pick) + b per unit, rookie seasons of earlier cohorts (WLS by full games).

| Season | QB rep | OL rep | RB rep | WRTE rep | DL rep | LB rep | DB rep | QB a / b (n) | OL a / b (n) | WRTE a / b (n) | DL a / b (n) | DB a / b (n) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2019 | 0.613 | 0.483 | 0.844 | 0.241 | 0.511 | 0.617 | 0.368 | -0.002 / 0.681 (28) | -0.010 / 0.600 (142) | -0.053 / 0.592 (175) | -0.032 / 0.693 (166) | -0.006 / 0.455 (184) |
| 2020 | 0.611 | 0.480 | 0.843 | 0.223 | 0.519 | 0.619 | 0.369 | -0.015 / 0.723 (35) | -0.010 / 0.598 (165) | -0.053 / 0.601 (205) | -0.029 / 0.693 (194) | -0.004 / 0.443 (217) |
| 2021 | 0.640 | 0.502 | 0.841 | 0.247 | 0.483 | 0.594 | 0.339 | -0.018 / 0.741 (41) | -0.006 / 0.592 (194) | -0.061 / 0.643 (239) | -0.032 / 0.696 (219) | +0.000 / 0.423 (255) |
| 2022 | 0.598 | 0.469 | 0.807 | 0.234 | 0.514 | 0.635 | 0.365 | -0.010 / 0.695 (47) | -0.003 / 0.575 (225) | -0.067 / 0.658 (274) | -0.031 / 0.703 (243) | -0.001 / 0.433 (292) |
| 2023 | 0.561 | 0.464 | 0.806 | 0.233 | 0.525 | 0.648 | 0.374 | -0.011 / 0.694 (54) | -0.002 / 0.567 (254) | -0.069 / 0.663 (311) | -0.030 / 0.703 (268) | -0.003 / 0.443 (333) |
| 2024 | 0.556 | 0.454 | 0.782 | 0.217 | 0.552 | 0.667 | 0.399 | -0.011 / 0.685 (61) | -0.002 / 0.563 (282) | -0.062 / 0.640 (352) | -0.031 / 0.712 (302) | -0.003 / 0.441 (364) |
| 2025 | 0.580 | 0.479 | 0.806 | 0.218 | 0.529 | 0.631 | 0.379 | -0.023 / 0.745 (67) | -0.002 / 0.566 (318) | -0.064 / 0.648 (388) | -0.031 / 0.706 (327) | -0.003 / 0.440 (396) |

## Participation layer (2019–2025 team-weeks)

Team-weeks: 3742; v1.15 projected QB matched to an id: 99.1% (else the QB unit uses the generic fill); membership skipped as a data gap: 15.
Player rows: 261071; Out 6729, Doubtful 1021, Questionable 9048; roster-out 14213; departed 18082.
Mean projected-share total per unit equals its slots by construction; mean |projected − full-health| share moved per team-week: 5.88 full-game equivalents.
Teams with ≥ 3 starters out (share ≥ .5, Out/Doubtful/roster-out): 23.0% of team-weeks; median roster continuity 0.608.

## Same-week reserve list: publication timing

Players newly on a game-week out list (weeks 2+, 2019–25): 6086; took an offensive or defensive snap in that game: 10 (0.16%). Weekly roster rows carry no publish time; this bounds how often a historical row reflects a post-kickoff move, not moves between the final injury report and kickoff.
