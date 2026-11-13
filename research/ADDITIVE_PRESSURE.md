# Offensive allowed + defensive forced: two additive pressure features

Owner requested adding defensive pressure forced as an independent feature after
the offensive-only ablation. This follow-up has two separately learned additive
coefficients, no interaction. "Independent" means a separate regressor, not a
claim that the two measured rates are statistically independent.

Written before fitting this two-feature arm. Both the original three-term and
offensive-only arms were already inspected; this is selected exposed development,
not preregistration or independent confirmation. Do not select specifications on
the requested LAC/PHI slice or on returns.

Features: home-minus-away offensive pressure allowed, and home-minus-away defensive
pressure generated/forced (both per PBP pass/sack/scramble opportunity, scaled by
.05). Reuse the original pressure profiles and source hashes. Explicitly remove
the matchup column from the feature frame; fit only the two named additions.

Preserve half-life8, four league pseudo-games, .5 offseason retention, five-season
history, two-week source lag primary and one-week sensitivity. Same fixed mapped
base rows, 2023 -> 2024 / 2023-24 -> 2025 / 2023-25 -> 2026 annual fits, ridge10,
training-only standardization and unpenalized intercept. No grid, team coefficients,
current-season coefficient updates or live changes.

Compare with original model, intercept-only control, market/fair/home baselines,
and directly with the frozen offensive-only arm on identical rows. Primary cohort
544 games 2024-25; 137 current-season games diagnostic. Same MAE/RMSE, Gaussian
conditional-cover LL/Brier/reliability, W-L-P, -110 units/ROI/SE and 10000 paired
whole-week bootstrap within season, seed20261113. Report the direct comparison
against offensive-only separately; nominal intervals do not correct sequential
feature-family selection.

Save all-team 2026 diagnostics and show requested LAC/PHI without fitting on those
teams separately. Historical first-publication times remain unverified. No model,
map, lock, journal, notebook or public-site activation is included.
