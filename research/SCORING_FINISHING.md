# Scoring opportunities and finishing: separate fixed research arm

Added at the owner's request while the pressure experiment was being completed.
Written before calculating scoring-feature associations or fitting this arm.
Do not combine it with pressure or tune it using either arm's results.

Use the same frozen base forecasts, annual earlier-season fits, two-week source
lag (one-week sensitivity), Gaussian cover-probability construction, fair/market/
home controls, metrics and week-cluster uncertainty as PRESSURE_MARGIN.md.
The current production win classifier, map, locks and site are not modified.

Aggregate nflverse PBP into regular-season offensive drives. A qualifying drive
has at least one non-kneel/non-spike scrimmage snap or a field-goal attempt.
Include touchdowns scored by the offense, made field goals, and its extra-point/
two-point conversions; exclude defensive/return TDs. Count each drive once.
Keep short/late drives unless they consist only of clock-killing kneels/spikes.

Four rate families, each for offense and opponent-allowed defense (eight terms):
1. Offensive points per qualifying drive.
2. Red-zone TD conversion minus earlier-season league expectation. A trip is a
   qualifying drive with a snap/FG from the opponent's 20 or closer, including
   fourth downs. Estimate TD expectation from prior seasons by entry-yardline
   bins 1-5/6-10/11-20, entry down and yards-to-go bins 1/2/3-4/5-7/8+.
3. Fourth-down go rate minus earlier-season league expectation, conditional on
   field-position bins 0-20/21-40/41-60/61-80/81-100, yards-to-go bins above,
   whether trailing and whether Q4 with <=300 seconds and margin <=8.
4. Fourth-down execution minus expected conversion in those same contexts,
   evaluated only on actual attempts. Do not interpret attempt selection as random.

Expectation tables: earlier seasons only, shrink cell rates toward the earlier
league rate with 20 pseudo-opportunities. 2018 supplies expectation reference;
scoring-feature source games start in 2019. No source game's own outcome enters
its expected rate. Context bins and smoothing are fixed, not selected on results.

Team profiles: trailing five seasons, half-life eight team games, .5 offseason
retention, four league-average pseudo-games in count/rate ratios, source games
at least two week indices earlier. Missing denominator is shrunk to league prior,
not treated as a zero conversion rate. Fit the eight home-minus-away differences
jointly in a residual-margin regression with an unpenalized intercept and ridge10
on standardized features. Coefficients fit pooled across all teams, frozen annually.

Decision measure limitation: go rate above contextual expectation measures
aggressiveness, NOT optimal decision quality. A true go/punt/FG win-probability
regret requires validated counterfactual action values and is not fabricated here.
PBP timestamps/revisions do not establish original availability. Historical
reconstruction only; no native forward evidence or automatic promotion.

Report all eight coefficients, not favorable team slices. Primary comparisons
are 2024-25 pooled; separate 2026 diagnostic. Intervals are nominal, unadjusted
for both requested feature families or the repository's prior research history.
