# Fixed-variant retest under the every-season market rule

Protocol frozen 2026-10-19 before computing the new results. The owner has
held v1.19 and requested a retest of variants. This is research only: no
production model, public page, native archive or workflow is changed.

## Cohort and fitting

Use the retained full-source 2019–2026 feature pack from the v1.19 rebuild.
The evaluation cohort is all 1,451 completed eligible games in 2021–2026:
2021–25 are separate complete seasons and 2026 is a separate partial-season
diagnostic through 92 completed games. Exclude the pending game. Keep tied
finals in ATS returns; exclude them only from binary winner proper scores.
Use the identical game IDs, labels and quotes for every candidate and control.

Before every week fit only strictly earlier weeks, with the existing h8 main
and h16 passing profiles, outcome half-life 38 weeks, normalized weights and
training-only SD scaling without centering. Missing main matchup inputs are
neutral zero. All inputs retain their current definitions; no new travel,
location or opponent-adjustment feature is introduced by this retest.

## Fixed candidate family

Use the same 29 individual inputs, three prespecified additive pairs and full
29-input correction as the earlier feature-modulation experiment. The pairs
are allowed net passing plus QB delta; passing product plus DB absences; and
allowed first-down rate plus opponent penalty-yard history. These are the
original proxy definitions, not clean causal measurements.

For each correction fit two anchors: the paired no-vig moneyline probability,
and the earlier-trained spread/total logistic baseline on `[1, spread/7,
(total−44)/7, product]`. Its ridge is `0.01 / ESS`; correction penalties are
0.1, except site 0.01. Hold the fitted anchor fixed while estimating the
correction. Apply gamma **0.05, 0.10, 0.25, 0.50 or 1.00** in logit space.
The first two shrinkages are new, explicitly exploratory fixed arms. There
are 330 feature generators, two gamma-zero market controls and a separate
v1.18 incumbent comparator. Do not change this grid after seeing results.

Each forecast generator has three ATS conversions: raw inverse-normal margin,
its own prior-season median map, and the incumbent's prior-season median map.
Keep the 2021 calibration-history floor and existing support rules. A median
path lacking earlier support in 2021–22 is **incomplete for the six-season
rule**, even if it passes all available 2023–26 seasons. Do not silently remove
those years or extend its history to obtain a passing result.

No candidate or gamma may change between evaluation seasons. Refitting the
same fixed regression on earlier weeks is allowed; selecting a different
feature or shrinkage after inspecting each target season is not this rule.

## Separate observed-result gates

Report component gates and failed seasons, not just a pooled ranking:

1. **Probability gate:** lower mean winner log loss **and** Brier score than
   **both** no-vig moneyline and spread/total-only baselines in every declared
   season. Also report own-anchor-only and individual-metric comparisons so
   the interpretation of “market” is visible.
2. **ATS gate:** positive ROI after assumed −110 pricing, and higher ROI than
   the same-anchor/same-map market-only policy and the market-favorite control
   in every declared season. Always-home is a diagnostic control, not an
   additional market model. Show cover rate, W–L–P, skips, selected/eligible
   games, units, ROI and uncertainty. Pushes remain in stakes; skips do not.
3. **Joint gate:** full six-season coverage and both gates above. A passing
   subset, a profitable pool or beating a negative-return control cannot
   override a failing season. Preserve all failures in the output.

Equality tolerances are 1e−12 for proper-score gains and 1e−10 for ROI gains.
Identical records cannot count as strictly better because of floating-point
cancellation. Also report a separate common 2023–26 window across all paths
to compare median policies on identical available seasons; it does not replace
the six-season gate.

Map-derived margins do not define calibrated cover probabilities. The ATS
comparison concerns decisions and price-aware returns; winner proper scores
concern a different target. The offered point spread itself becomes a
favorite selection under the existing zero-edge rule, not a cover-probability
forecast. Zero edge within 1e-10 takes the market favorite; pick'em zero edge
skips.

## Uncertainty and release status

These gates first screen observed results. An observed pass does not establish
reliability. Use paired whole-week bootstrap uncertainty within seasons, shared
resamples across variants, and simultaneous intervals accounting for the fixed
family and seasons. Keep 2026's small number of clusters explicit. Intervals
condition on the retained forecasts and omit training/refit uncertainty and
the earlier adaptive research; do not call them fresh validation.

Do not select a production winner from the worst-season rank or tune the grid
until it passes. If no candidate passes, report that. If any passes observed
gates, retain it as a research candidate pending uncertainty assessment and
fresh validation with actual pregame prices. The production hold remains in
place throughout this retest.
