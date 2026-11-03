# Test 49 protocol: outlier-robust team profiles (weighted median, winsorized mean, per-play yardage cap)

Research only. Production v1.18, its v1.16 shadow lock, frozen recipes, `data/` and the forward ledger
are unchanged. Owner request 2026-11-03 ("testing windowed medians per feature to limit outliers from
biasing means"). This protocol is committed and pushed before any arm is built or scored.

## Question

Production describes each team by decayed ratios of sums: half-life 8 team games, halved at each
season boundary, three prior seasons plus the current one, shrunk toward the league by four
pseudo-games. Would an estimator that limits outlier games or plays describe teams better?

**Prior evidence (exposed development):** the garbage-time filter (Test 4), the ±2 SD pass-context clamp
(passing robustness), short flat windows (Test 43) and extra pseudo-games (Test 36) did not beat
production. A descriptive tail check of 2013–25 per-game values (skew, excess kurtosis, share of
8-game medians equal to zero; no forecasts) was run before this protocol was written. It found mild
tails (excess kurtosis 0.1 to 2.1) and degenerate medians for fumbles lost (54% of 8-game medians are
0) and interception % (31%). That check is why arm A excludes those two features.

"Windowed" means production's window and decay. Test 43 showed short flat windows are noisier.

## Inputs

* Box scores and schedule: `research/form_windows_inputs/` (Test 43, SHA-256s in its `provenance.json`).
* Arm C only: nflverse play-by-play 2013–2026. The 2013–25 files are re-downloaded and must be
  hash-identical to the Test 40/43 provenance. The 2026 file is in-season and will differ; the 2026
  diagnostic uses only games already in the frozen box scores.

## Profiles

For every team-game from 2013 through 2026 week 5, each arm builds a pregame profile from strictly
earlier games (`nfl_model.before`), seasons ≥ season − 3. Weights are production's: `2^(−age/8)` with
age in team games, × 0.5 per season boundary. There are 16 profiles: 7 rates × 2 roles (offense
`for`, defense `allowed`) and the 2 score peaks. The rates are plays/game, net yards per dropback,
rush yards per attempt, first downs per 100 plays, fumbles lost per game, interception % and
penalty yards per game. Sack % is excluded, as in production.

| Arm | Location estimator | Applied to |
|---|---|---|
| **P** production (comparator) | `nfl_model.metric_profile`: decayed ratio of sums + 4 league pseudo-games (league means from the same history); peaks `Σw·x/(Σw+4)` | all 16 |
| **A** weighted median | Weighted median of per-game values, weight = decay × the game's denominator (1 for per-game stats). Lower weighted median (smallest value whose cumulative weight reaches half; at exactly half, the midpoint with the next value). Then the same shrinkage share as P: `(1−λ)·median + λ·league`, `λ = 4·p̄_den/(Σw·den + 4·p̄_den)`; peaks shrink toward 0 with `λ = 4/(Σw+4)` | 12: plays, yds/dropback, rush yds/att, first-down rate, penalty yds (both roles), max lead, max deficit. Fumbles and INT % stay P |
| **B** winsorized mean | Each earlier game's per-game value clipped to the 2.5th and 97.5th percentiles (numpy linear) of all team-games in the same history (unweighted, positive denominator, same thresholds for both roles); clipped numerator = clipped value × denominator; then P's ratio of sums and P's league prior | all 16 |
| **C** per-play cap | Pass plays (attempts and sacks) capped at 20 yards, rushes at 10 (Test 33's explosive thresholds), box scores re-aggregated with `nfl_model.aggregate_boxscores`, then P's estimator | 4: yds/dropback and rush yds/att, both roles |

Features an arm does not apply keep P's value. Fidelity checks run before any score: P must reproduce
`form_windows.profiles(half_life=8)` (itself tested against `nfl_model.lagged_features`). The uncapped
re-aggregation must reproduce the frozen box scores. Arm C is compared with P computed from the
uncapped rebuild of the same download, which is the frozen P wherever that check passes.

## Stage 1: stat-level screen (no win/loss outcomes, prices or ROI)

* **Target:** the realized statistic in that game: the team's own for `for` profiles and peaks, the
  opponent's for `allowed`. It is always uncapped, including for arm C.
* **Rows:** team-games whose team has at least `MIN_TEAM_HISTORY` (4) earlier games in the window and
  a positive target denominator. Rows are common to all arms.
* **Scores:** denominator-weighted MSE (weight = pass plays, rush attempts, plays or pass attempts in
  that game; 1 for per-game stats and peaks). **Primary:** after a walk-forward weighted least-squares
  recalibration `y ~ a + b·profile`, fitted per arm and feature on seasons 2014 to s − 1 and applied to
  season s (2013 is warm-up). Raw MSE is secondary.
* **Bases** (Test 43's, never pooled for decisions): 2015–16, 2017–22, 2023–25. 2026 weeks 1–5 is a
  diagnostic. The pooled 2015–25 statistic is used only for the interval rule below.
* **Primary statistic per arm:** the equal-weight mean, over the arm's applied features, of the
  percentage change in recalibrated MSE versus P (negative = better).
* **Uncertainty:** team-season cluster bootstrap, 2,000 draws, seed 20261103, one shared draw matrix
  for every comparison. 98.33% percentile intervals for the three primary statistics (K = 3); 95% for
  per-feature results, which are descriptive.
* **Descriptive:** per feature, per basis, and by week bucket (1–4, 5–9, 10–18).

**Decision rule (fixed):**

* **Advance to stage 2:** the primary statistic is below zero on all three bases and its pooled
  2015–25 98.33% interval lies entirely below zero.
* **Stop:** the primary statistic is ≥ 0 on two or more bases.
* Otherwise **unresolved**: reported, and stage 2 runs only if the owner asks.

A stat-level gain is necessary but not sufficient. Test 45 found stat-level and market-level results
can disagree.

## Stage 2: market-level test (only for arms that advance)

As Test 43: an advancing arm replaces only its applied main-profile differences in rebuilt production.
Availability, the half-life-16 pass contexts, home field, the market offset, the weekly fit, ridge 0.1
and the v1.18 penalty are production's. The bases are the same, with 2026 as a diagnostic.

* **Primary:** log-loss gain over rebuilt production, week-clustered, Bonferroni over the advancing
  arms. Test 43's rule: **better** (worth a forward shadow) if the gain is > 0 on all three bases and
  its interval excludes zero on at least one; **not better** if the gain is ≤ 0 on two or more bases;
  otherwise **unresolved**.
* **ATS, reported and never optimized:** mapped model spread (`fixed_bands`, median signed MOV fitted
  to prior-season margins) against the schedule spread, flat 1u at −110. Lead with W-L-P, skips,
  units, ROI ± SE (pushes in the denominator), cover rate excluding pushes, n, break-even 52.4%, and
  the same-row always-favorite and always-home baselines. Moneyline flat 1u is reported as legacy.
* Stage-2 implementation details are committed before any stage-2 score exists.

## Outputs and limits

Script `research/robust_profiles.py`; tests `tests/test_robust_profiles.py`; capped-yardage inputs
and provenance `research/robust_profiles_inputs/`; results `research/robust_profiles_results/`
(REPORT.md). This is development evidence on seasons already exposed by earlier tests. It is not
forward evidence, and the intervals omit design-selection uncertainty. Adoption would change
`config_signature()`, so it would need a new `REVISION` and `OUTPUT_NAME` and the owner's decision.

Run: `python research/robust_profiles.py --capped PBP_DIR` (build arm C's capped yardage; raw files
needed), then `python research/robust_profiles.py` (fidelity checks and stage 1; no network).
