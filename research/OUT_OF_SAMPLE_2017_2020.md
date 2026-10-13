# Out-of-sample 2017–2020 protocol

Research only; production v1.16, frozen recipes and the forward ledger are
unchanged. Written and pushed before any v1.16 or challenger forecast for
2017–2020 exists. Owner decision 2026-10-13: spend these seasons once on the
two questions below.

## Exposure, disclosed in advance

These seasons are the least-used the repository has, not untouched.

* **Test 32** (unmerged branch `claude/relaxed-meitner-8dxoq4`, commit 1e55189)
  scored 2017–20 once with a v1.12-era model that had no market offset. On
  1,013 bets it returned +1.2% ± 2.4 against −1.9% for the favorite (−2.6%
  null) and had 0.0221 worse log loss than the market. The author of this
  protocol knows that result.
* **Test 24** used 2019–22 once for the pass-matchup correlation.
* **2019–20 were production's warm-up training seasons.** No v1.16 forecast
  was ever scored on them.
* **The challenger's 60% threshold comes from exposed 2021–25 diagnostics:**
  75 of v1.16's 79 underdog picks came in games whose favorite was under 60%.
* **Before writing this, only input coverage was checked:** moneyline,
  snap-count, injury and roster availability for 2013–2020. No outcome-based
  number for 2013–2020 was computed.

## Data and pipeline

* Load regular seasons 2013–2020 with the production loaders and build the
  v1.16 inputs exactly as the committed v1.16 pack does:
  * h8 main profiles with availability;
  * h16 pass profiles;
  * `pass_contexts`;
  * schedule moneylines;
  * no-vig q.
* **History seasons, 2013–2016:** training only.
* **Scored seasons, 2017–2020:** regular-season games that are ready, priced
  on both moneylines, and have finite pass contexts. Ties push in ROI and are
  excluded from binary scores.
* **Freeze the feature pack** in the results directory, so CI can replay
  without network access.
* **Pipeline check:** rebuild 2019–2020 from those seasons alone and compare
  with the committed v1.16 pack (`research/shrinkage_results`). Report the
  largest input difference. Upstream data can have been revised since that
  pack was built.

## Arms

All arms refit coefficients before every scored week using strictly earlier
weeks.

1. **`production`: exact v1.16.** `fit_composite` with `LEGACY_PRODUCT_RECIPE`
   on all eligible earlier games.
2. **`close_fit`: the challenger.**
   * Identical features, market offset, penalties, standardization and decay.
   * Trains only on earlier eligible games where max(q, 1 − q) < 0.60.
   * Forecasts only such games; elsewhere it forecasts q, so it backs the
     market favorite.
3. **`v116_close_only`: descriptive decomposition, outside the decision
   rules.** v1.16 probabilities in close games, q elsewhere.
4. **Baselines on the same rows:** the market favorite and the market-correct
   null.

## Questions and decision rules, fixed in advance

All intervals are week-cluster bootstrap with 8,000 draws and the
qualification seed. They are 97.5% intervals: Bonferroni across the two
questions.

**Q1: does v1.16's edge exist out of sample?**

* **Primary statistic A:** paired units per bet, v1.16 minus the market
  favorite, on common bets. Market pick'ems and exact model abstentions are
  excluded.
  * **Supported** if A's lower bound is above 0.
  * **Contradicted** if A's upper bound is below 0.
  * **Unresolved** otherwise.
* **Secondary statistic B:** log-loss gain over the no-vig market, reported
  with its interval.

**Q2: does the close-game challenger beat v1.16?**

* **Statistic C:** paired units per bet, challenger minus v1.16, all common
  bets.
* **Statistic D:** log-loss gain over v1.16 on close games.
* **Verdicts:**
  * **Not supported** if C ≤ 0 or D ≤ 0.
  * **Favored, unresolved** if both are positive and either interval
    includes 0.
  * **Supported** if both lower bounds are above 0.
* Only "favored" or "supported" makes the challenger eligible for a forward
  shadow next to frozen v1.16. This test changes nothing in production.

## Also reported, descriptive

* Per arm: W-L-P, units, ROI ± SE, market-correct null, same-row favorite,
  log loss, Brier.
* Results by season, and the 2017–18 subset (the least exposed).
* Underdog picks by favorite band.
* Calibration intercept and slope.
* The value of v1.16's market departures (multiplier on the offset), by
  season.
* Training cutoffs and input hashes.

## Limits

* This is one use of four seasons, about 1,000 bets. If v1.16's historical
  edge were real, Q1 would have about a 60% chance of resolving it.
* An unresolved verdict means the seasons cannot decide. It does not mean the
  edge is zero.
* Adoption of anything would be an owner decision and a new `REVISION`.
