# Test 60 protocol: does the model's band add anything beyond the line's own band? (2016–22)

Research only. Production v1.22, the weekly decayed median map, the lock policies and every journal are unchanged.
Owner request 2026-11-11: "run tests 1 and 2 on 2016–22" after the review of the median-band theory. This protocol is
committed and pushed before the line-only arm is scored on any season before 2023.

## Questions

1. **Replication (descriptive).** How does the production map (weekly refit, one-season half-life, policy v2) do
   against the spread on 2016–22?
2. **Primary.** On the same games, does the model's spread through the map beat the market line through the *same*
   map? The two arms differ only where the model's band (or side) differs from the line's, so the difference is what
   the model contributes beyond the line's own position in its band.

## Arms (fixed here)

All arms use the v1.19 forecast p (v1.22 keeps the same ten-term fit), x = 12.37·Φ⁻¹(p), the market spread L, flat
1u at −110 and production's pick rule (`fixed_bands.pick`: zero edge takes the market favorite; a pick'em with zero
edge skips). A skip returns 0 in paired differences.

| Arm | Prediction compared with L |
|---|---|
| D model | x through the weekly decayed map (`fixed_bands.fit_weekly` for that game's season and week) |
| D line-only | L through the same weekly rule |
| A model | x through the annual map (`fixed_bands.fit`) |
| A line-only | L through the same annual rule |
| R raw | x |

Baselines on the same rows: always favorite, always home.

## Bases, never pooled

* **Test (primary): 2016–22.** v1.19 replayed with weekly refits on earlier rows (Test 51's harness,
  `market_implied.forecasts`, which reproduces the published v1.19 forecasts). Maps are fitted on this replay's
  earlier games from 2014 with production's minimums (two complete earlier seasons, 300 games, 30 per band), so
  2016 is the first mapped season. Rows: finite spread, result, model spread and both maps.
* **Discovery (descriptive): 2023–26** from `data/latest/fixed_band_ledger.csv` with the weekly rules in
  `data/latest/fixed_band_rules.json`. Check: D model minus D line-only must reproduce the ledger report's
  +55.36u on 139 differing games of 952.

## Exposure, disclosed in advance

* v1.19's ten terms were chosen on 2019–25 (Test 50), so forecasts on 2019–22 are not clean.
* Test 59 already scored the weekly decayed map on 2017–22: 785-740-41, −26.4u, −1.7% ± 2.4 (n 1,566), against
  the annual map's −110.4u and always-favorite's −157.0u. **Question 1 is therefore largely answered already** and
  is reported here as a replication with 2016 added, not as a new finding.
* Test 54 scored the annual map on 2016–22: 880-896-46, −96.0u.
* 2023–26 is fully known: map +88.64u, line-only +33.27u, difference +55.36u on 139 differing games.
* No line-only result has been computed for any season before 2023. Closing lines; capture time unknown.

## Primary: D model − D line-only on 2016–22

Per game, units(D model) − units(D line-only). Sum, with SE = sd of the per-game differences × √n.

* **Supported:** the sum is positive and z ≥ 2. The model's band adds value beyond the line's on this basis.
* **Contradicted:** the sum is negative and z ≤ −2.
* **Unresolved:** otherwise. A crossing interval does not show the arms are equal.

## Reported, not gating

For each basis and season, every arm and baseline: W-L-P, skips, units, ROI ± SE (pushes in the denominator), cover
rate excluding pushes, n, break-even 52.4%. Paired contrasts with the count of differing sides and the record on
them: D model − D line-only (primary), A model − A line-only, D model − R raw, D model − A model. Replication check
of Test 59's D and A records on 2017–22 (any row-eligibility difference is stated, not tuned away).

## What a result means

Diagnostic only; nothing here changes production. The replay is exposed through v1.19's term selection, and any
change to the map or selection rule is a new policy version and the owner's decision.

* If the primary is unresolved or contradicted, the 2023–26 difference of +55.4u on 139 games stands as an
  unreplicated discovery-period result, and the native comparison at 100 decided locks (map, raw and line-only on
  the same rows, already reported) remains the deciding evidence.
* If it is supported, that is replication on exposed development data, not forward confirmation.

Run: `python research/map_vs_line.py`.
