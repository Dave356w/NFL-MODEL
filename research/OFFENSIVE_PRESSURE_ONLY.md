# Offensive pressure allowed only

Owner requested this ablation after inspecting LAC/PHI changes from the full
pressure arm. It is a post-hoc, owner-selected follow-up, not preregistered or
an independent confirmation. Written before fitting this one-feature arm.

One pooled extra regressor: home offensive pressure allowed minus away offensive
pressure allowed, in units of .05. No defensive pressure, matchup interaction,
other new statistics, team dummies or team-selected coefficients enter the fit.

Reuse frozen PFR pressure counts and PBP opportunities, but profiles require
only offensive `times_pressured` and `opportunities`; defensive columns are not
read. Same trailing five seasons, half-life8 games, .5 offseason retention,
four league pseudo-games. Two-week source lag primary; one-week sensitivity.
Historical original publication timing remains unverified.

Use identical frozen base forecasts and annual training cutoffs: 2023 -> 2024,
2023-24 -> 2025, 2023-25 -> separate 2026 diagnostic. Margin-residual regression
fits an unpenalized intercept and ridge10 on the one training-standardized
pressure coefficient, equal game weights. Compare the same intercept-only
control to isolate the feature from shared recalibration. Also retain original,
market, market-plus-pressure, fair-cover and always-home comparisons.

Primary: 544 future games in 2024-25; 2026 snapshot 137 games diagnostic.
MAE/RMSE, conditional no-push Gaussian cover LL/Brier/reliability, ATS W-L-P,
cover rate and flat 1u -110 returns/ROI/SE. Same 10000 paired whole-week bootstrap
within season, seed20261113. Nominal intervals do not account for selection of
this follow-up after seeing the full-pressure or other feature-arm results.

Save all-team 2026 diagnostics, then describe LAC/PHI as requested: feature-only
and full-overlay margin changes, original/control/adjusted margin errors, ATS
pick changes and per-game forecasts. These small team slices do not select the
coefficient, decay, penalty or a production decision. No live changes.
