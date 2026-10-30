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

## Results (run 2026-10-30, after the protocol commit)

Full output: `research/totals_pace_results/RESULTS.txt`. Walk-forward predictions:
`predictions.csv.gz`. Intervals are 95% week-cluster bootstrap.

**Grid.** (h, K, L) = (16, 8, 64), with 2009–2016 T0 RMSE 13.338. All 12 cells fell
between 13.34 and 13.39.

**Outcomes, 2017–2025, stage M (n 1803).**

| | RMSE |
|---|---|
| Schedule line | 13.254 |
| T1 | 13.630 |
| T0 | 13.726 |
| P0 | 13.732 |

Stage E (n 580) is the same: line 13.25, T1 13.68. The context terms do help against
outcomes. In the 2025 fit, dome added +2.8 points, retractable roof +1.9 and division
−1.4. None of that closes the gap to the line.

**Against the market, 2017–2025.**

| Arm, stage | Squared error vs line | w on (T − line) | Over/under LL gain vs no-vig | Model side, \|P − q\| ≥ .05: ROI (null) |
|---|---|---|---|---|
| T1, M | +10.11 [+6.62, +13.89] | −0.013 [−0.189, +0.160] | −0.0201 [−0.0278, −0.0120] | −2.1% [−7.0, +3.3] (null −3.3%), n 1042 |
| T0, M | +12.72 [+9.19, +16.41] | −0.131 [−0.302, +0.030] | −0.0206 [−0.0288, −0.0118] | −3.1% [−8.7, +2.3] (null −3.3%), n 1058 |
| T1, E | +11.39 [+4.73, +18.19] | −0.138 [−0.475, +0.209] | −0.0206 [−0.0334, −0.0087] | −5.2% [−13.7, +3.2] (null −3.2%), n 322 |

For squared error, a positive number means the model is worse than the line.

By season (T1, stage M), the over/under LL gain was negative in all nine seasons. Its
interval excluded zero in 2020–2022. w was never resolved above zero. All-game ROI was below
its null in 8 of 9 seasons.

**Verdict under the registered criteria: no demonstrated totals signal at these quotes.**
The model fails all three conditions:

- its RMSE is worse than the line,
- its LL gain is resolved negative, and
- its weight on (T − line) is about 0.

Given the posted total, the model's departures carry no information about the outcome. A
standalone pace × efficiency model does not reproduce the bookmaker total. This agrees with
the ridge total in `MARGIN_TOTAL_MODELS.md`.

**Limitations.**

- The schedule quotes have no capture time and are probably near the close. The NBA analogue
  found its only signal at the open and none at the close, so this test cannot rule out an
  open-price signal.
- No weather forecast is used.
- Historical design exposure means the intervals are not untouched confirmation.

**Next.** Do not register a forward O/U test on this model. The native over/under prices now
captured in `data/h5_totals.jsonl` are taken at the first lock, earlier than these quotes.
They allow a later check at that timing if the owner wants one. Re-run this script at that
point, with the predictions joined to the captured prices. A market-anchored residual model
(line + small corrections such as dome or wind forecast) is the remaining candidate. It
would be falsified by w ≤ 0 or an LL gain interval at or below zero, as here.

## Addendum A: shrinkage toward the market-context median (protocol committed 2026-10-30, before its run)

This is the owner's follow-up question: can the model work if its total is shrunk toward the
historical median final total for its posted O/U? The 2017–2025 verdict above stands
whatever this addendum finds.

- **Median by line band, m(line).** Posted totals are put in 2-point bands: < 36, [36, 38),
  [38, 40), … [52, 54), ≥ 54. For evaluation season Y, m(line) = line + the median of
  (final − line) in that band over all priced games from 2006 to Y − 1. Only earlier seasons
  are used.
- **S1, shrunk total.** T_s = m + w·(T − m). T is the walk-forward T1 (secondary: T0), with
  the same fits as above. w is the no-intercept least-squares slope of (final − m) on
  (T − m) over the out-of-sample predictions from 2009 to Y − 1, clipped to [0, 1].
  σ_s is the residual sd of (final − T_s) on those same seasons, computed separately for
  stage E and stage M. P(over) = 1 − Φ((line − T_s)/σ_s).
- **M1, median alone.** Bet the sign of (m − line) and skip games where it is zero. This
  rule has no probability, so it gets an ROI only.
- **Evaluation.** The same criteria and output as the main protocol, for stage M and stage
  E, 2017–2025. The 2026 season to date is shown separately as a current-season diagnostic
  that cannot count toward a verdict. The pass criteria are unchanged: RMSE no worse than
  the line, an LL gain whose 95% interval excludes zero, and a weight on (T_s − line)
  above 0.

Run: `python research/totals_median.py` → `research/totals_pace_results/MEDIAN_SHRINK.txt`.

### Addendum A results (run 2026-10-30, after its protocol commit)

Full output: `research/totals_pace_results/MEDIAN_SHRINK.txt`. Intervals are 95% week-cluster
bootstrap.

- **The fitted weight on the model is near zero.** For T1, w was 0.13 (fit for 2017), 0.03
  (2021 and 2025) and 0 (2026). For T0 it was 0.16 in 2017 and 0 from 2021. Out of sample,
  the earlier seasons put almost all the weight on the market median, so T_s ≈ m(line).
- **S1 with T1, stage M, 2017–2025 (n 1803).**

  | | Value |
  |---|---|
  | RMSE: line, shrunk model | 13.254, 13.309 |
  | Squared error vs line | +1.46 [+0.25, +2.68] (worse) |
  | Over/under LL gain vs no-vig | −0.0027 [−0.0056, +0.0001] |
  | w on (T_s − line) | −0.23 [−0.84, +0.39] |
  | Model side, all games: ROI (null) | −5.2% (−3.3%) |
  | Model side, \|P − q\| ≥ .05: ROI | −4.9%, n 187 |

  Shrinkage cut the LL loss from −0.020 to −0.003 only by discarding the model. Stage E is
  the same: LL gain −0.0026 [−0.0066, +0.0019]. T0 is the same.
- **M1, median sign alone, stage M.** 766–783–16, ROI −4.2% [−9.0, +0.7] against a −3.3%
  null. Stage E: 240–259–2, ROI −6.9%.
- **2026 to date, diagnostic only.** w = 0, so S1 = M1. Stage M: 13–23 on M1, LL gain
  −0.0085. Stage E: 22–28, LL gain −0.0075.

**Verdict: fails Addendum A's criteria, as it failed the main protocol.** The shrunk model
remains worse than the line in RMSE, has no positive LL gain and no positive weight on
(T_s − line). The market-context median adds nothing to the posted total: the medians of
(final − line) by band are −1.5 to +1.5 points and change sign between eras.

## Addendum B: median bands with residual adjustments (protocol committed 2026-10-30, before its run)

This is the owner's follow-up question: start from the band median, then add a fitted
residual correction. It builds on the drift finding: the market tracks the scoring level
faster than the model does.

- **Medians, rebuilt season by season.** For any game in season s, m = line + the median of
  (final − line) in the game's band over priced games from 2006 to s − 1. Training rows
  therefore never use their own season's medians.
  - **Absolute bands (A):** Addendum A's 2-point bands of the line.
  - **Era-relative bands (R):** 2-point bands of (line − league), with edges −8, −6, … +8
    and open tails. League is the to-date level from the main protocol (2 × league points per
    team over completed weeks this season, with last season counted as 64 team-games).
- **Residual model.** Regress (final − m) on:
  - (T1 − m), the pace model's departure from the median;
  - (league − line), the drift gap;
  - dome, retractable roof, short weeks, byes, division game, 3-game form and phase, as in
    the main protocol.

  Ordinary least squares with an intercept, fitted for evaluation season Y on 2009 to Y − 1.
  T1 is the walk-forward prediction. T_r = m + fitted residual. σ is the residual sd on the
  training rows, computed separately for stages E and M. P(over) = 1 − Φ((line − T_r)/σ).
- **Arms.**
  - **BA:** absolute bands + residual.
  - **BR:** era-relative bands + residual.
  - **MR:** era-relative median sign alone (ROI only).
- **Evaluation and criteria.** Unchanged: stages M and E, 2017–2025, with 2026 to date as a
  diagnostic only. Pass requires RMSE no worse than the line, an LL gain whose 95% interval
  excludes zero, and a weight above 0 on (T_r − line).

Run: `python research/totals_residual.py` → `research/totals_pace_results/MEDIAN_RESIDUAL.txt`.

### Addendum B results (run 2026-10-30, after its protocol commit)

Full output: `research/totals_pace_results/MEDIAN_RESIDUAL.txt`. Intervals are 95%
week-cluster bootstrap. Stage M is 2017–2025, n 1803; the line's RMSE there is 13.254.

| Arm, stage | RMSE | Squared error vs line | LL gain vs no-vig | w on (T_r − line) | Model side, all: ROI (null −3.3%) |
|---|---|---|---|---|---|
| BA, M | 13.297 | +1.15 [−0.31, +2.57] | −0.0058 [−0.0091, −0.0025] | +0.11 [−0.37, +0.62] | −5.4% |
| BR, M | 13.310 | +1.48 [+0.11, +2.88] | −0.0052 [−0.0085, −0.0017] | −0.00 [−0.49, +0.50] | −5.1% |
| BA, E | 13.325 | +1.68 [−0.98, +4.48] | −0.0004 [−0.0067, +0.0055] | −0.01 | +3.5% [−4.4, +11.4] |
| BR, E | 13.289 | +0.71 [−1.79, +3.17] | +0.0009 [−0.0049, +0.0066] | +0.30 [−0.43, +1.02] | +1.6% [−4.8, +7.8] |

- **MR (era-relative median sign).** Stage M: 637–636–15, ROI −3.2% [−8.5, +2.0], against a
  −3.3% null. Stage E: 204–213–2, ROI −5.2%.
- **Residual coefficients (2026 fit, BR).**
  - The model's departure from the median gets −0.00 and the drift gap −0.06: both are
    worthless on top of the median.
  - Dome +1.2 and retractable roof +1.1 points; division −1.2.
  - These terms fit consistently: dome +0.8 to +1.6 and division −1.1 to −1.3 across the
    2017–2026 fits.
- **2026 to date, diagnostic only.** BR went 21–23 in stage M and 25–39 in stage E. MR went
  10–17 and 19–22.

**Verdict: fails Addendum B's criteria.**

- **Stage M:** both arms have a resolved negative LL gain and RMSE no better than the line.
- **Stage E:** both arms are about level with the market, with unresolved intervals and
  RMSE above the line. A positive ROI in an early-season slice is not evidence: 2026's
  stage E went 25–39 on BR.

The residual model's only consistent terms are roof and division effects of about one point
on top of the posted total. Any further test should isolate them: a registered rule on
those terms alone, falsified by an LL gain at or below zero. The median and the pace model
contribute nothing beyond the line.

## Addendum C: per-team market residuals from implied points (protocol committed 2026-10-30, before its run)

This is the owner's follow-up question: do teams persistently beat or miss the market's
implied points, and does that adjust the O/U line?

- **Implied points.** From the schedule line and spread (`spread_line`, positive means the
  home team is favoured): home = (total_line + spread_line)/2, away = (total_line −
  spread_line)/2. These quotes have the same unknown capture time as before.
- **Team residuals.** For each team-game:
  - offense residual o = points scored − the team's implied points;
  - defense residual d = points allowed − the opponent's implied points.

  Each team's pregame residual is a decayed mean over its earlier games this season
  (half-life h), shrunk toward 0 with weight K games: Σw·x / (K + Σw). Only weeks strictly
  before the game are used. Week 1 has no residual (0).
- **Signal.** R = o_home + d_away + o_away + d_home, in points versus the line.
- **Adjusted total.** T_c = line + k·R. k is the no-intercept least-squares slope of
  (final − line) on R, fitted on seasons 2009 to Y − 1 for evaluation season Y. k is
  unclipped, so a negative k (the market overreacting) is allowed and reported. σ is the
  residual sd of (final − T_c) on the training rows, computed separately for stages E and
  M. P(over) = 1 − Φ((line − T_c)/σ).
- **Grid.** (h, K) ∈ {4, 8, 16} × {2, 4, 8}, chosen on the lowest 2009–2016 walk-forward
  RMSE of T_c (with k fitted walk-forward inside that window, from 2008), then fixed. No
  grid choice uses 2017+ or any price.
- **Second arm, C2.** The same, but o and d carry over from last season, regressed 50%, as
  the starting value with weight K.
- **Evaluation and criteria.** Unchanged: stages M and E, 2017–2025, with 2026 to date as a
  diagnostic only. Pass requires RMSE no worse than the line, an LL gain whose 95% interval
  excludes zero, and a weight above 0 on (T_c − line). The weight test here is a test of k.

Run: `python research/totals_team_residual.py` → `research/totals_pace_results/TEAM_RESIDUAL.txt`.

### Addendum C results (run 2026-10-30, after its protocol commit)

Full output: `research/totals_pace_results/TEAM_RESIDUAL.txt`. Intervals are 95%
week-cluster bootstrap.

- **The selection window already shows nothing.** Every grid cell's 2009–2016 RMSE
  (13.162–13.165) was worse than the line's (13.156). The chosen cells were C1 (4, 2) and
  C2 (16, 8).
- **The fitted k is small and negative.**
  - C1: k = −0.01 (fit for 2017), then −0.03 to −0.04 for 2018–2026.
  - C2: from +0.07 to −0.05.
  - Teams that recently beat their implied points go slightly under next, so the market
    adjusts at least fully. With sd(R) = 4.9 points (C1), the adjustment k·R has an sd of
    only about 0.2 points. No game reached |P − q| ≥ 0.05.
- **C1, stage M, 2017–2025 (n 1803).**
  - RMSE 13.252 against the line's 13.254. Squared error −0.05 [−0.26, +0.15].
  - LL gain −0.0002 [−0.0012, +0.0008].
  - w on (T_c − line): +1.4 [−2.3, +5.3].
  - Model side, all games: ROI −3.2% against a −3.3% null.
- **C1, stage E.** LL gain +0.0015 [−0.0004, +0.0035]. Model side ROI +5.9% [−3.1, +14.9].
  Unresolved.
- **C2, stage M.** LL gain −0.0007 [−0.0016, +0.0003], ROI −3.8%. Stage E: +0.0012
  [−0.0006, +0.0031], ROI +4.0%. Unresolved.
- **2026 to date, diagnostic only.** C1 went 21–23 in stage M and 32–32 in stage E.

**Verdict: fails Addendum C's criteria.**

- No arm's LL gain interval excludes zero.
- Neither the weight nor k is resolved above zero.
- The adjusted line is the posted line to within about 0.2 points.

The market already prices each team's scoring relative to its implied points. If anything
it slightly over-adjusts (k < 0), and by far less than the hold. The early-season (stage E)
gains are unresolved and point the same way in both arms. A forward test of them would need
its own registration, not this hindsight slice.
