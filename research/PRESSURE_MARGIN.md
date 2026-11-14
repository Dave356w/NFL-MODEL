# Pressure margin overlay: fixed research protocol

Written before calculating pressure/outcome associations. Historical development;
base recipes and historical results have already been exposed. No production change.

Use current ten-term model's archived mapped margin predictions (2023-25) and
public saved 2026 predictions. Fit pooled across all teams, with coefficients frozen
for an entire evaluation season using previous seasons only: 2023 -> 2024,
2023-24 -> 2025, 2023-25 -> 2026 diagnostic. Do not select settings using ROI.

Pressure source: nflverse PFR weekly passing, aggregate times_pressured across
passers, then credit the same counts to the opposing defense. This avoids summing
individual defensive players' potentially overlapping pressure credits.
Denominator: nflverse PBP pass attempts + sacks + QB scrambles (union, no duplicate
sacks), excluding deleted/no-play and two-point plays. Retain only regular season.
Audit missing fields, duplicate IDs, team/opponent mappings, denominator coverage,
pressure counts vs opportunities, and reported PFR pressure percentages.

Primary features use source games at least two week indices earlier; one-week lag
is a prespecified sensitivity, not a verified publication cutoff. Do not treat file
updated_at as original row publication. Latest historical revised data do not
establish point-in-time availability; report that limit and no forward claim.

Team offense/defense rates: half-life 8 team games, offseason retention .5,
four league-average pseudo-games, trailing five seasons. League priors use only
eligible earlier source games. In units of .05 rate, define a_t = centered offensive
pressure allowed and d_t = centered defensive pressure generated. Three additions:
a_home-a_away, d_home-d_away,
a_home*d_away-a_away*d_home. All inputs are from prior source games only.

Fit Gaussian residual margin regression with an intercept and the three features,
training-column standardization, ridge 10 on standardized pressure coefficients,
unpenalized intercept, equal game weights. Fixed choices, no hyperparameter search.
Compare archived mapped model, intercept-only residual control, pressure overlay,
market margin, and pressure overlay on market. Control and overlay use the same
training/evaluation rows. Annual fits never consume current-season labels.

Metrics: ATS W-L-P, flat 1u units/ROI and SE at assumed -110; same-row favorite and
home controls; MAE, RMSE; conditional-on-no-push home-cover log loss and Brier,
five fixed probability-bin reliability. Actual matched side prices are additional
context only, not optimized. Cover probabilities come from a discretized Gaussian
margin with sigma estimated on each arm's prior-season training residuals;
condition on nonpush for integer handicaps. Compare with fair .5. Do not claim
calibration from pick accuracy. Always bet according to predicted margin vs line;
zero edge takes market favorite, except zero/zero pick'em skips.

Primary summary pools 2024-25. 2026 is a separate diagnostic. 10,000 paired
whole-week bootstrap resamples within season for MAE and cover-log-loss differences,
seed 20261113. Intervals condition on fitted paths, not full model/data uncertainty.
Sensitivity: one-week lag; leave production, locks, journals, site and notebook intact.

Meaningful checks: no target/future data in profiles or annual fits, offense/defense
symmetry, missing-source rejection, positive denominators, push treatment, analytic
normal cover probabilities, baseline reproduction and deterministic replay.
