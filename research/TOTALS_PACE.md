# Pace × efficiency totals (O/U) model

Protocol committed 2026-10-30, before any fit or result. This is research only: `nfl_model.py`,
the recipe, `data/forward_predictions.jsonl`, the ATS locks and the public pages are untouched.
The data are historical and already exposed. The model follows the NBA repository's totals
fit (`diagnostics/totals_model`) adapted to the NFL. It differs from the ridge total tested in
`MARGIN_TOTAL_MODELS.md`, which scored worse than the market total (over LL .7000 versus
.6933, unresolved).

## Data

- nflverse `nfldata/games.csv`, regular season 2006–2025: scores, `total_line`,
  `over_odds`/`under_odds`, `roof`, rest days, division flag. The quotes have no capture
  time. Treat them as an unknown pregame snapshot, probably near the close. There is no
  opening line, so open and close cannot be separated.
- nflverse `stats_team_week` (regular season): offensive plays per team-game = pass attempts
  + sacks taken + carries.
- Observed weather (`temp`, `wind`) is recorded on game day. It is not a pregame forecast,
  so it is excluded.

## Model

The unit is one team-game. Every input uses only weeks strictly before the game's week.

- **Team rates.** Each team gets decayed means (half-life h team-games) of: offensive plays,
  plays allowed, points per offensive play scored, and points per play allowed. The prior
  is last season's figure regressed 40% to that season's league mean, weighted as K
  team-games. A team's first season in the data uses the league mean.
- **League level to date.** League points per game in completed weeks this season, plus
  last season's league mean weighted as L games.
- **Naive total.** Expected plays for team X = X's offensive plays + the opponent's plays
  allowed − league plays. Expected points per play = X's rate + the opponent's rate allowed
  − league rate. N = Σ over both teams of expected plays × expected points per play.
- **Arms.**
  - **P0:** points only. Decayed points for and against with the same prior, and
    N_pts = PF_h + PA_a + PF_a + PA_h − 2·league points per team.
  - **T0:** pace × efficiency. total − league = a + b·(N − league) + phase.
  - **T1:** T0 plus pregame context: dome, retractable roof (either status; open/closed is
    decided on game day), short week (rest ≤ 4 days), off a bye (rest ≥ 10), division game,
    and a 3-game form term (last-3 points scored minus the decayed rate, both teams summed).
  - Phase = team-games played before the game, clipped to 0–8, linear.
- **Fit.** Least squares on completed earlier seasons only. Each evaluation season is
  refitted on all prior seasons from 2008 (2006–07 are warm-up).
- **Grid.** (h, K) ∈ {4, 8, 16} × {4, 8} and L ∈ {16, 64}. Choose the cell with the lowest
  T0 RMSE on 2008–2016 and fix it for every arm. Evaluate 2017–2025. No grid choice uses
  2017+ or any price.
- **Probability.** P(over) = 1 − Φ((line − T)/σ). σ is the residual sd of the earlier
  seasons, computed separately for stage E (either team has < 4 team-games this season) and
  stage M (both have ≥ 4).

## Evaluation (2017–2025, by season and pooled; stages E and M never pooled)

- **Against outcomes.** RMSE for P0, T0, T1 and the market line. Paired squared-error
  difference against the line, ±95% with week-cluster bootstrap.
- **Against the market.**
  - The weight w in (total − line) = w·(T − line), with a 95% interval.
  - P(over) log loss against the two-sided no-vig q, pushes excluded from both.
  - Flat 1u on the model's side, both for all games and for |P(over) − q| ≥ 0.05. Each is
    reported with ROI ± 95% and the no-vig null (the hold), pushes returning the stake.
- **Descriptive.** Rows by posted total (< 41, 41–44.5, 45–47.5, ≥ 48) and by model
  over / under. These are not filters.

## What would count, and what would not

The model earns a native forward test (a separate owner decision and amendment) only if T1
or T0 has, for 2017–2025 stage M:

- RMSE no worse than the line,
- an LL gain over the no-vig market whose 95% interval excludes zero, and
- w > 0 with a 95% interval excluding zero.

Otherwise the conclusion is no demonstrated totals signal at these quotes. Because the
quotes are probably near the close, a null here would not rule out a signal at the open.
That case is the reason for the price capture below.

## Native capture (from 2026-10-30)

`totals.py` now also writes the schedule's `over_odds`/`under_odds` into each new
`data/h5_totals.jsonl` record. The record is append-only and written once, at the build
that first locks the game. Earlier records are never backfilled. The capture is for a
future native over/under evaluation and is graded nowhere.

Run: `python research/totals_pace.py` → `research/totals_pace_results/RESULTS.txt`.
