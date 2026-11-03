# Test 49 stage 1: outlier-robust team profiles, stat-level screen

Protocol: [ROBUST_PROFILES.md](../ROBUST_PROFILES.md), pushed (`0271988`) before any arm was built or scored. Production v1.18 and the ledger are unchanged. No win/loss outcomes, prices or ROI are used. Development evidence on already-exposed seasons.

## Fidelity

- P reproduces production's half-life-8 profiles (`form_windows.profiles`, tested against `nfl_model.lagged_features`) on 3486 games, max abs difference 0.0e+00.
- Arm C's comparator (P on the uncapped re-aggregation of the same play-by-play) differs from frozen P by at most 0.0e+00.

Scored team-games: 6844 (all seasons, including warm-up 2013–14). Interval level 98.33% for the primary statistic; team-season cluster bootstrap, 2000 draws, seed 20261103.

## Primary statistic: mean % change in recalibrated MSE vs production (negative = better)

| Arm | Features | 2015-16 | 2017-22 | 2023-25 | 2015-25 | 2026 wk1-5 (diagnostic) | Pooled 98.33% interval | Verdict |
|---|---:|---:|---:|---:|---:|---:|---|---|
| A weighted median | 12 | +0.337 | +0.699 | +0.448 | +0.565 | +0.690 | [+0.407, +0.730] | stop |
| B winsorized mean | 16 | −0.014 | −0.002 | +0.008 | −0.001 | +0.031 | [−0.021, +0.019] | unresolved |
| C per-play cap | 4 | +0.017 | −0.071 | +0.264 | +0.036 | +1.102 | [−0.158, +0.240] | stop |

Raw (unrecalibrated) MSE, secondary:

| Arm | 2015-16 | 2017-22 | 2023-25 | 2015-25 | 2026 wk1-5 (diagnostic) |
|---|---:|---:|---:|---:|---:|
| A weighted median | +3.240 | +3.093 | +2.854 | +3.057 | +3.250 |
| B winsorized mean | −0.146 | −0.069 | −0.075 | −0.085 | −0.071 |
| C per-play cap | +33.615 | +31.848 | +28.253 | +31.082 | +29.652 |

By week bucket, 2015–25 pooled (descriptive):

| Arm | wk1-4 | wk5-9 | wk10-18 |
|---|---:|---:|---:|
| A weighted median | +0.579 | +0.430 | +0.630 |
| B winsorized mean | +0.020 | −0.023 | +0.000 |
| C per-play cap | −0.025 | −0.149 | +0.167 |

## Per feature: % change in recalibrated MSE (2015–25 pooled, 95% interval; descriptive)

| Feature | A weighted median | B winsorized mean | C per-play cap |
|---|---|---|---|
| for:plays_per_game | +0.60 [+0.20, +1.00] | +0.02 [−0.05, +0.09] | – |
| for:net_pass_yards_per_pass_play | +1.16 [+0.60, +1.72] | +0.12 [+0.02, +0.22] | −0.13 [−0.48, +0.21] |
| for:rush_yards_per_attempt | +0.38 [−0.00, +0.77] | −0.09 [−0.17, −0.00] | +0.44 [+0.00, +0.89] |
| for:first_down_rate | +1.44 [+0.78, +2.08] | +0.10 [−0.00, +0.21] | – |
| for:fumbles_lost_per_game | – | +0.00 [−0.02, +0.02] | – |
| for:interception_pct | – | −0.04 [−0.08, +0.01] | – |
| for:penalty_yards_per_game | +0.41 [+0.13, +0.71] | −0.08 [−0.15, −0.03] | – |
| allowed:plays_per_game | −0.01 [−0.33, +0.31] | −0.05 [−0.10, −0.01] | – |
| allowed:net_pass_yards_per_pass_play | +0.27 [−0.10, +0.66] | +0.09 [+0.03, +0.15] | +0.08 [−0.14, +0.30] |
| allowed:rush_yards_per_attempt | +0.31 [−0.02, +0.65] | −0.03 [−0.09, +0.03] | −0.24 [−0.57, +0.09] |
| allowed:first_down_rate | +0.61 [+0.18, +1.03] | −0.03 [−0.10, +0.06] | – |
| allowed:fumbles_lost_per_game | – | +0.01 [−0.01, +0.04] | – |
| allowed:interception_pct | – | +0.02 [−0.01, +0.04] | – |
| allowed:penalty_yards_per_game | +0.14 [−0.05, +0.35] | −0.08 [−0.12, −0.03] | – |
| max_lead | +0.78 [+0.32, +1.25] | +0.04 [−0.05, +0.13] | – |
| max_deficit | +0.68 [+0.25, +1.14] | −0.02 [−0.10, +0.06] | – |

Arm B clip activity: share of history team-games outside the 2.5–97.5% thresholds (final week of each 2015–25 season, averaged): plays_per_game 4.4%, net_pass_yards_per_pass_play 5.0%, rush_yards_per_attempt 5.0%, first_down_rate 5.0%, fumbles_lost_per_game 1.5%, interception_pct 2.4%, penalty_yards_per_game 4.5%, max_lead 2.4%, max_deficit 2.4%.

