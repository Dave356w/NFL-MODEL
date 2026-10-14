# Test 42 protocol: a model built only from features production does not use

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner request 2026-10-14 ("try model features not shared by production version").
Committed and pushed before any feature below has been built or scored.

## Question

Production uses the no-vig moneyline, 23 box-score averages, availability (QB and unit absences),
the pass-matchup contexts and home field. Does information production never sees add anything,
either on its own or on top of production? A feature set disjoint from production's gives
departures from the market that are not production's departures restated, so this tests
independent information directly.

## Features (none used by production; all known before kickoff)

* **Ratings** (Tests 40–41: same frozen observations, same filters and 2013–14 tuning):
  `pass_edge`, `rush_edge` (EPA), `margin_edge` (point margin), `ats_edge` (margin beyond the
  closing spread).
* **Schedule:** `rest_diff` = home rest days minus away rest days, clipped to ±7.
* **Market structure:**
  * `ml_spread_gap` = logit(q) − logit(Φ(spread_line / 12.37)). Positive means the moneyline is more
    bullish on the home team than the spread (12.37 is `MARKET_SIGMA`).
  * `total_x_market` = (total − 45)/10 × logit(q), which lets high-total games sit nearer to or
    further from 50/50 than the moneyline says.
  * `div_x_market` = division game × logit(q), the same for division games.

**Sources.** `div_game` and the rest days come from the nflverse schedule, frozen once in
`disjoint_features_inputs/schedule_context.csv` (the same download as Test 37, with the SHA-256
checked). The spread comes from the frozen packs; the total from Test 37's frozen totals. As with
q, history uses the last recorded lines. A missing line gives the feature 0, production's
missing-input convention.

**Excluded:** production's inputs, home field included, and weather. Recorded game-time weather
is an actual, not a pregame forecast.

## Arms, fixed

All are refit before every week on strictly earlier rows of the same packs and row sets as
production, with production's fit, decay and ridge 0.1, and the v1.18 penalty applied last.

**Primary (K = 3):**
1. **`disjoint`**: market offset + the 8 features above.
2. **`production_plus_disjoint`**: production's 29 inputs and the 8 features in one joint fit
   (penalty 0.1 throughout, site 0.01).
3. **`blend`**: the equal-weight average of production's and `disjoint`'s departures from the
   market, then the penalty. Nothing is fit.

**Descriptive:** `disjoint_ratings` (the 4 ratings only) and `disjoint_context` (rest plus the 3
market-structure features), to show which family carries anything.

## Bases, metrics, decision rule

Bases are never pooled: 2015–16, 2017–22 and 2023–25, with production reproducing its published
forecasts. 2026 weeks 1–5 is a diagnostic. The metrics are Test 40's: the log-loss gain over
production (week-clustered, 98.33% interval), gain over the market, flat 1u ROI (null, same-row
favorite, units vs production, side flips) and results by total band. Also reported: the
game-by-game correlation of the `disjoint` and production departures, and the mean fitted
coefficients.

* **Better than production, worth a forward shadow test:** gain > 0 on all three bases, with the
  interval excluding zero on at least one.
* **Not better:** gain ≤ 0 on two or more bases.
* Otherwise **unresolved**.

Development evidence only. Tests 20 (rest), 40 and 41 (ratings) have looked at some of these
families before, and the market-structure features are new. Adoption would be a new `REVISION`
and the owner's decision.

Run: `python research/disjoint_features.py`.
