# Test 40 protocol: a separate model built on dynamic play-efficiency ratings, against production

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner request 2026-10-14 ("explore a separate novel model using features of your choice
based on available data and compare vs production"). Committed and pushed before any rating,
feature or forecast below has been computed. Only one play-by-play file (2013) had been downloaded,
to check its columns.

## Idea

Production describes each team with 23 exponentially decayed box-score averages (raw, not
opponent-adjusted at h8) plus availability terms, on top of the no-vig market. Tests 37–39 found
that none of those inputs measurably earns its place, and that fewer inputs or more shrinkage looks
slightly better.

This model replaces the box-score block with a few **dynamic, opponent-adjusted ratings**. A
Kalman filter tracks four latent strengths per team: pass offense, pass defense, rush offense and
rush defense, in efficiency per play. Each game is an observation of offense plus opposing defense,
weighted by its number of plays. Ratings drift week to week, regress toward the league between
seasons, and carry their own uncertainty. That differs from production in three ways: it adjusts
for opponents, separates pass from rush on both sides of the ball, and weights by information. The
model keeps production's market offset, fit and QB availability term, so the comparison isolates
the ratings.

## Data, frozen

nflverse play-by-play, regular seasons 2013–2026 (2026 through the latest published week),
downloaded once. Team-game observations are aggregated and committed to
`kalman_ratings_inputs/team_games.csv` with source URLs and SHA-256s. The raw files are not
committed. A play counts if it is a pass (dropbacks, sacks and scrambles included) or a rush, not
deleted, not a two-point attempt, and has a non-null result.

* **EPA per play**, nflverse's expected-points model. Caveat, as in Test 7: that model was fit on
  earlier seasons, which may overlap 2015–19, a mild form of lookahead.
* **Rule-based success rate**, with no model involved: a play succeeds if it gains at least 40% of
  the yards to go on 1st down, 60% on 2nd, 100% on 3rd or 4th, or scores a touchdown.

## Ratings (no lookahead)

* For each metric (EPA or success) and each play type (pass or rush), every team has an offensive
  and a defensive state.
* Observation: an offense's mean per play in a game, minus the league mean and the home effect
  (both estimated from strictly earlier games), equals its offensive state plus the opponent's
  defensive state, with variance σ²/n.
* σ² is the per-play variance from 2013–14 plays.
* Between consecutive weeks the variance grows by q. At a season boundary each state is multiplied
  by ρ and its variance by ρ², then grows by P₀(1 − ρ²).
* Initial state: 0 with variance P₀ in 2013 week 1.
* Ratings for week w are snapshotted before any week-w game is filtered.

**Hyperparameters** (q, ρ, P₀; one set per metric) maximize the one-step-ahead Gaussian predictive
likelihood of the observations, not of game results, on 2013–14 only. The grid:
q ∈ {0.25, 0.5, 1, 2, 4} × 10⁻³·σ²/30, ρ ∈ {0.4, 0.6, 0.8}, P₀ ∈ {0.5, 1, 2} × the 2013–14
variance of team-season means. 2013–14 are never evaluation seasons.

## Model

Matchup edges, home minus away:
* `pass_edge = (off_pass_H + def_pass_A) − (off_pass_A + def_pass_H)`
* `rush_edge` the same for rush.

`logit p = logit q + β·[pass_edge, rush_edge, qb_delta, site]`. Fit exactly as production's
`fit_composite`: refit before every week on strictly earlier rows of the same pack and row set,
two-season decay, standardized inputs, ridge 0.1 (site 0.01), v1.18's favorite penalty applied
last. `qb_delta` and `site` are production's own pregame columns.

## Arms, fixed

1. **`kalman_epa`** (primary): the model above with EPA ratings.
2. **`kalman_sr`** (primary): the same with success-rate ratings (no EP model, so no lookahead).
3. **`blend`** (primary): equal-weight average of production's and `kalman_epa`'s departures from
   the market, `logit q + ½·D_prod + ½·D_kalman`, then the penalty. Nothing is fit.
4. **`kalman_epa_standalone`** (context, not judged): the same inputs with an intercept and no
   market offset, to show how the ratings fare without the market.

## Bases, never pooled

2015–16, 2017–22 and 2023–25, on the same games, packs and training rows as Tests 38–39, with
production reproducing its published forecasts. 2026 weeks 1–5 is a diagnostic.

## Metrics and decision rule

* **Primary (decides): log-loss gain over production per basis**, week-clustered, 98.33% interval
  (Bonferroni over 3 primary arms).
* Also reported: log-loss gain over the market; flat 1u ROI (W-L-P, units, ROI ± SE,
  market-correct null, same-row favorite); units vs production and side flips; Brier; results by
  total band.
* **Better than production, worth a forward shadow test**: gain > 0 on all three bases, with the
  interval excluding zero on at least one.
* **Not better**: gain ≤ 0 on two or more bases.
* Otherwise **unresolved**.

Everything here is development evidence. A forward test would be an owner decision, and adoption
would be a new `REVISION`.

Run: `python research/kalman_ratings.py --build` (download and freeze; needs network), then
`python research/kalman_ratings.py`.
