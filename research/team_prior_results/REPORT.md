# Test 45: per-team, coach and QB shrinkage targets vs the league prior

Design and disclosure: [TEAM_PRIOR.md](../TEAM_PRIOR.md). **Not pre-registered.** The data are exposed
2015–2025 development history, and the market prices are nflverse closing moneylines. Rebuild with
`python research/team_prior_study/run.py`.

**Verdict: no.** No team, coach, QB or continuity target predicts a team's own stats better than the
league prior. None adds anything reliable beyond the closing moneyline. Neither continuity-conditioned
retention arm helps. Keep the league prior; no `REVISION`.

## Team identity is real, and it is mostly coach and QB

Year-to-year correlation of a team's season rate, 320 team-season pairs, 2015–2025. This is descriptive.
The QB split uses the realized primary starter, so it is not a pregame gate.

| Offensive stat | All | Same coach and QB | Both changed |
|---|---:|---:|---:|
| Net pass yards per dropback | 0.44 | 0.46 (n=163) | −0.06 (n=32) |
| First-down rate | 0.47 | 0.51 | −0.10 |
| Plays per game | 0.26 | 0.25 | 0.10 |
| Largest lead | 0.38 | 0.38 | −0.09 |

Fumbles lost (offense and defense) and defensive penalty yards show no detectable persistent team
signal: season-level reliability is −0.14, 0.12 and 0.00. Full tables: `persistence_table.csv`,
`persistence_reliability.csv`.

## Stat level: predicting the team's statistic in the next game

5,278 team-games, 2016–2025; 2,000-draw team-season cluster bootstrap. Each cell is the % change in MSE
vs the league target (negative = better). The metrics are the 16 v1.18 box-score and peak profiles.

* **Raw.** Every alternative target is worse than the league target: +0.3% to +1.4% for team_window,
  team_prior and coach, and +0.2% to +0.6% for continuity. Most were better in 0–2 of 10 seasons. No
  shrinkage at all (`none`) is worse by +1.3% to +3.5%. Shrinking toward the league earns its place.
* **Recalibrated walk-forward on earlier seasons only.** This is what the regression effectively does.
  Every difference stays within about ±0.6% with no consistent sign. Team_prior on offensive
  first-down rate is worse, +0.58% [+0.04, +1.13].
* **Where the premise applies.** On games with the same coach and QB, the continuity target is still
  worse in the raw form: allowed pass +1.01% [+0.51, +1.53], offensive pass +0.79% [+0.15, +1.46].
  Early-season gains are small and confined to a few stats: penalty yards and largest deficit in
  weeks 1–4, −0.3% to −0.6%.

Tables: `stat_pred_pooled_{raw,recal}.csv` and `stat_pred_{raw,recal}_{subset}.csv`.

## Market level: a simplified market-offset model, 2017–2025

The model is the logit of the no-vig closing moneyline plus site plus 16 profile differences, refit
weekly. It reproduces `nfl_model.fit_composite` to 1e-16. It omits availability, the QB projection, pass
contexts and the favorite penalty, so it is **not production**. On matched rows it trails full v1.16 by
about 40u (−11.1u vs +28.6u on 1,829 bets).

Goal metric, flat 1u moneyline ROI on the model's side. All 2017–25, 2,371 bets. Market-correct null
−3.12%; same-row favorite −59.03u (−2.49%).

| Target | Units | ROI ± SE | Units vs league | ROI diff vs league [95%] | Flips (W-L) |
|---|---:|---:|---:|---|---|
| league (simplified) | −36.05 | −1.52% ± 1.46 | | | |
| team_window | −17.12 | −0.72% ± 1.46 | +18.94 | +0.80 [−0.04, +1.73] | 26 (18-8) |
| team_prior | −25.37 | −1.07% ± 1.46 | +10.68 | +0.45 [−0.48, +1.41] | 34 (20-14) |
| continuity | −35.18 | −1.48% ± 1.46 | +0.87 | +0.04 [−0.80, +0.85] | 27 (14-13) |
| coach | −30.67 | −1.29% ± 1.46 | +5.38 | +0.23 [−0.62, +1.14] | 31 (17-14) |
| qb_offense | −37.99 | −1.60% ± 1.46 | −1.94 | −0.08 [−0.75, +0.56] | 15 (7-8) |
| none | −32.27 | −1.36% ± 1.46 | +3.78 | +0.16 [−0.34, +0.70] | 10 (6-4) |

Log-loss gain vs league ×10⁻³, All 2017–25 (n = 2,374), 95% week-cluster intervals:

| Target | Gain |
|---|---|
| team_window | +0.31 [−0.46, +1.10] |
| team_prior | +0.33 [−0.59, +1.29] |
| continuity | +0.01 [−0.80, +0.82] |
| coach | +0.06 [−0.74, +0.87] |
| qb_offense | −0.32 [−0.79, +0.15] |
| none | −0.01 [−0.31, +0.29] |

* **Every interval crosses zero.** Team_window's units come almost entirely from 2017–20: +17.13u on 13
  flips, 11-2. That is the best of more than 21 disjoint era-by-arm cells; its Bonferroni p is about 0.46.
  It is +0.32u on 2023–25.
* **The two best rows carry no identity information.** Team_window and team_prior only re-weight the
  team's own history.
* **Era signs flip.** Team_window and team_prior gain log loss on 2017–20 (+0.68, +0.87) and lose on
  2023–25 (−0.14, −0.25). Coach and continuity lose on 2023–25 (−0.83, −0.39).
* **Adding the variant-minus-league differences as 16 extra inputs** lowers log loss for every arm,
  including near-null ones, so it measures the cost of 16 free coefficients, not missing information.
  It is reported (`market_test_table_delta.csv`) but not used for the verdict.

## Continuity-conditioned season-boundary retention (two arms added post hoc)

This is the most direct way to let continuity matter: keep more of last season when coach and QB stayed
and less when either changed. The arms use league pseudo-games.

| Arm or control, All 2017–25 | Units vs league | ROI diff [95%] | LL gain ×10⁻³ [95%] |
|---|---:|---|---|
| cont_75_25 | +4.86 | +0.20 [−0.66, +1.06] | −0.06 [−0.70, +0.56] |
| cont_50_25 | +11.17 | +0.47 [−0.24, +1.17] | +0.16 [−0.37, +0.69] |
| flat_75 (control) | +3.74 | +0.16 [−0.57, +0.88] | −0.25 [−0.76, +0.28] |
| flat_25 (control) | +14.28 | +0.60 [−0.20, +1.46] | +0.46 [−0.31, +1.20] |

* **The control that ignores continuity does as well or better** (flat_25 +14.3u vs cont_50_25 +11.2u).
  Any movement comes from the retention *level*, not the continuity label.
* **At the stat level, conditioning hurts exactly where it should help.** On games after a change
  (n = 2,814), cont_75_25 and cont_50_25 are worse than league on 7 and 8 of 16 metrics and better on
  none. A uniform 0.75 is better than league on 10 of 16 overall, including after changes.
* **The direction conflicts.** Stats favor more retention (0.75); the market model leans toward less
  (0.25). Neither is resolved.

Tables: `retention_*`.

## Review

An independent reviewer read every script and checked for lookahead:
* the evaluated game's stats, QB and outcome;
* same-week or later data;
* in-sample recalibration.

It found none. The `tests/test_team_prior.py` perturbation test covers the builders. The reviewer
independently re-fitted the market model and recomputed the headline numbers.

**One bug was fixed before this commit.** The shared bet-row filter dropped one game,
2020_14_ATL_LAC, from every arm because a delta arm sat at p = 0.4999995. The filter now excludes delta
arms. This changed continuity from +2.72u to +0.87u and coach from +7.23u to +5.38u; no conclusion
moved. Coach data list the season-opening coach for 5 interim spans in 2024–25 (43 team-games).
Excluding them changes nothing.

**Power.** The minimum detectable effect is about 1.1×10⁻³ log loss or 1.3 ROI points. Only 1–1.5% of
games flip side.

## Reading

The intuition is right about where identity lives, but production already carries it. The team's own
history holds 57–72% of every profile, and last season alone holds about half at week 1. Coaching and QB
changes are frequent (47% of 2016–25 team-seasons open with a new head coach or week-1 starter) and
public. A team-keyed prior double-counts the team's past and carries it across those changes. A
coach-keyed or continuity-keyed prior predicts no better, and the market already prices the changes.

**Untested and low leverage:**
* a single-parameter mix toward a team prior;
* QB priors keyed to production's pregame `qb_expected` inside the full pipeline.

Either would need its own pre-registered held-out test.
