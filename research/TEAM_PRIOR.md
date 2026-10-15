# Test 45: per-team, coach and QB shrinkage targets instead of the league prior

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner question 2026-10-14: "Would a per team average instead of league where used help
isolate personnel and coaching tendencies?"

**Not pre-registered.** This note was written after the analysis ran (2026-10-14/15, in a Claude Code
session). The arms below were fixed before any outcome was scored. The two retention arms were added
after the first seven had been scored. Every season used, 2015–2025, is exposed development history.
Read everything here as exploratory: no result can nominate a candidate on its own.

## Where production uses the league

Production's box-score profiles (`metric_profile`) add **four league-average pseudo-games** to each
team's decayed history. Margin and lead/deficit peaks shrink toward 0. For a team with full history,
the pseudo-games hold this share of the half-life-8 profile weight:

| Week | 1 | 5 | 10 | 17 |
|---|---:|---:|---:|---:|
| League pseudo-games (h8 main) | 43% | 36% | 31% | 28% |
| League pseudo-games (h16 pass) | 33% | 28% | 24% | 20% |
| Team's prior seasons (h8) | 57% | 33% | 19% | 9% |

The other league-wide settings, reviewed in the code audit, are: the QB backup prior
(150 dropbacks), the pass-context center/SD, one set of coefficients, one home-field term,
`STATUS_WEIGHT`, the unit weights and `OFFSEASON_RETENTION` = 0.5.

## Arms

The first eight variants change **only the target of the four pseudo-games**. Weights, window and
everything else stay production's. Everything uses strictly earlier games only.

* `league`: production. It reproduces `nfl_model.lagged_features` bit for bit on 2013–2026.
* `league_level`: rates as production; peaks and margin shrink toward the league window mean
  instead of 0. This is the level reference for the team-type arms.
* `team_window`: the team's own undecayed mean over the same window (the literal "per-team
  average instead of league").
* `team_prior`: the team's own mean over prior seasons only.
* `continuity`: `team_prior` only when this game's head coach equals the coach of the team's last
  game of the prior season **and** the starter of the team's most recent earlier game was the
  prior-season primary starter; otherwise `league_level`.
* `coach`: the head coach's own earlier games in the window, on any team (at least 8 games).
* `qb_offense`: for offensive passing, interception and first-down rates, the games started by the
  most recent earlier game's starter, on any team (at least 8 starts).
* `none`: no pseudo-games.

Two further arms change **season-boundary retention** instead of the target. They use league
pseudo-games:

* `retention_cont_75_25`: 0.75 per boundary where coach and QB continued, 0.25 where either changed.
* `retention_cont_50_25`: production's 0.5 where they continued, 0.25 where either changed.

Two flat controls, `retention_flat_75` and `retention_flat_25`, use the same retention at every
boundary. They separate the effect of *continuity* from the effect of the *retention level*.

Coach and QB identities come from the nflverse games file, frozen in `team_prior_inputs/`. A game's
own head coach is public pregame. A game's own starter is never used.

## Evaluation

1. **Stat level (uses no win/loss outcomes).** Out-of-sample error of each pregame profile for the
   team's statistic in that game, 2016–2025 (5,278 team-games). Two forms are reported: raw, and
   after walk-forward linear recalibration fitted on earlier seasons only. Each is reported pooled,
   by week bucket and by coach/QB continuity, with 2,000-draw team-season cluster bootstrap
   intervals. Year-to-year persistence by continuity is reported descriptively.
2. **Market level.** A simplified production-style model per variant:
   * offset logit of the no-vig closing moneyline;
   * site plus the 16 non-availability box-score and peak differences;
   * ridge 0.1, training-row decay with a 2-season half-life, refit before every week.

   It is validated against `nfl_model.fit_composite`. It omits the availability, QB-projection and
   pass-context terms and the favorite penalty, so it is **not** production. Reported for 2017–2025
   by era: flat 1u moneyline ROI on the model's side (units, ROI ± SE, market-correct null,
   same-row favorite), units vs the simplified league arm, and log-loss gain with 95% week-cluster
   bootstrap intervals. Bonferroni: 7 arms (target study) and 9 (with retention). An
   incremental-delta arm adds the 16 variant-minus-league inputs to the league model.

Prices are the nflverse closing moneylines, not ledger lock prices.

## Reading rule

* A variant **helps isolate tendencies** only if it predicts the team's own statistics better than
  the league target, and in the games where its premise applies (for example, continuity rows).
* It **helps the goal metric** only if the market-level ROI and log-loss intervals exclude zero in
  its favor on more than one era.

Intervals that cross zero are unresolved. Adoption of anything would be an owner decision, a new
`REVISION` and a pre-registered forward test.

Run: `python research/team_prior_study/run.py`. Results: `team_prior_results/REPORT.md`.
