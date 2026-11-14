# Points per possession for/allowed: isolated two-term study

Owner requested "points per possession for/allowed" after the simpler punt-rate
idea. Written before deriving/fitting this arm. The earlier scoring-finishing
bundle already included points per drive; this tests those rates alone, without
red-zone, fourth-down, pressure, punt-rate or team-identity regressors.

Two pooled additions: offensive points per qualifying possession and opponent
offensive points allowed per opponent qualifying possession. Construct each team's
past profile, then take home-minus-away differences. Do not combine with the
other requested research arms after seeing their results.

Use exactly the punt study's possession definition, now also retaining successful
PAT/two-point plays for point accounting. Qualifying possessions contain a
non-kneel/non-spike scrimmage snap, field-goal attempt or punt attempt. Exclude
clock-killing-only possessions, deleted/no-play, and two-point plays as separate
qualifying possessions. Offensive TD=6, made FG=3, made PAT=1, successful try=2.
Only TDs credited to the possessing offense, not defensive/return TDs, count.
PAT-only nonoffensive-scoring possessions are not counted. Safeties scored by the
defense are not offensive points. Defensive allowed is the opponent's identical
offensive count, not all scoreboard points conceded by a team. Thus special-team
and defensive scores cannot masquerade as offensive drive efficiency.

Source: the same frozen 2018-2026 nflverse PBP files. Mirror numerator and
denominator exactly across opponents. Audit scoring totals against the source
ledger, qualifying-possession totals against the punt study, coverage and hashes.

Profiles: trailing five seasons, half-life8 games, offseason retention .5, four
league pseudo-games. Primary lag two week indices, fixed one-week sensitivity.
Annual fit 2023 -> 2024; 2023-24 -> 2025; 2023-25 -> 2026 diagnostic. Shared
margin-residual regression uses training-only scaling, ridge10, equal game weights,
unpenalized intercept. No grid, interaction, coefficient/current-season refit or
ROI selection. Same frozen mapped base, intercept-only control, market/fair/home
benchmarks and earlier-season Gaussian conditional cover probabilities.

Report MAE/RMSE, cover LL/Brier/reliability, W-L-P, cover rate and -110 flat-1u
returns/ROI/SE. Primary cohort 544 games in 2024-25; 137 2026 games diagnostic.
10000 paired whole-week resamples within season, seed20261113. Nominal intervals
do not correct the many previously examined feature families. Historical revisions
and unavailable first-publication times prevent a native forward-evidence claim.

This metric is not opponent-adjusted, field-position-adjusted or game-state-adjusted;
short fields can raise offensive points per possession without stronger offense.
The market and existing first-down/passing/INT terms may already encode its signal.
Production fits/maps/locks/journals/notebook/site remain unchanged.
