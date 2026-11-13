# Simple punts per possession: fixed research protocol

Owner narrowed the next special-teams/field-position idea to "simply punts per
possession". This separate arm tests that simpler signal, not a kicking or
field-position composite. Written before deriving punt features or fitting them.

Two added pooled terms, no interaction or team fixed effects:

- Offensive punt rate: own punt attempts / own qualifying possessions.
- Defensive forced-punt rate: opponent punt attempts / opponent qualifying possessions.

Possession definition: nflverse regular-season `(game_id, posteam, fixed_drive)`,
with `drive` fallback only for a missing fixed drive. Count a possession once if
it contains at least one non-kneel/non-spike scrimmage snap, field-goal attempt,
or punt attempt. Exclude deleted/no-play and two-point plays. Exclude possessions
consisting only of kneels/spikes. Include turnover, failed-fourth-down and scoring
possessions; blocked punts still count as punt attempts. Fake punts recorded as
passes/rushes are not punt attempts. Numerator is literal punt attempts, not only
possessions ending with a punt, so a recovered punt followed by another punt in
the same possession can produce more than one attempt. Audit that frequency.

Source: the existing frozen 2018-2026 nflverse PBP snapshots, same hashes as the
pressure study. Audit offense/defense mirroring, both teams per game, missing
drive IDs, and source-game coverage. No target/future game enters its features.

Team profiles: trailing five seasons, eight-game half-life, .5 offseason
retention, four league-average pseudo-games in the count ratios. Primary source
lag two week indices; fixed one-week sensitivity. Report home-minus-away
offensive and defensive rate differences. No expectation/context fit or grid.

Use the same frozen mapped base forecasts and shared residual-margin evaluator:
train 2023 -> evaluate 2024; train 2023-24 -> evaluate 2025; train 2023-25 ->
separate 2026 diagnostic. Equal game weights, training-only standardization,
ridge10 on both additions, unpenalized intercept, coefficients frozen annually.
Compare original margin, intercept-only control, punt overlay, market margin,
market plus punts, always-home and fair-cover baselines on identical rows.

Metrics: margin MAE/RMSE, conditional-on-no-push cover log loss and Brier,
five-bin reliability, ATS W-L-P/cover rate and flat 1u -110 returns/ROI/SE.
Cover probabilities use the same prior-fit discretized-Gaussian construction.
Primary cohort 544 games in 2024-25; 137-game 2026 snapshot is diagnostic only.
Paired whole-week bootstrap within season, 10000 draws, seed20261113; nominal
intervals do not correct the repository's earlier research or multiple families.

Interpretation: this measures stalled drives/forced punts. It does not measure
punt distance, return value, kicking accuracy or turnover-created field position.
Turnovers and failed fourth downs can lower punt rate without improving an
offense. The existing market/first-down/INT features may already capture its
useful signal. No live model, map, lock, journal, notebook or site modification.
Revised historical PBP lacks verified first-publication timestamps; source lags
are assumptions, not proof of originally available pregame data.
