# Test 61 protocol: the median map with 2020–21 excluded from its training

Research only. Production v1.22, the weekly decayed median map, the lock policies and every journal are unchanged.
Owner request 2026-11-11 ("Covid affected seasons are noisy ... run it with 2020–21 excluded from training") after
Test 60, where all of the model-versus-line-only gain on 2016–22 came from 2020–21. This protocol is committed and
pushed before any map with those seasons excluded is fitted or scored.

## Question

The band numbers used for 2022–26 were fitted on trailing games that include 2020–21; with a one-season half-life
those seasons weigh heavily in 2022 and still count in 2023. Does the map's 2023–26 record depend on band numbers
learned from 2020–21?

## History and arms (fixed here)

One history of v1.19 forecasts: the Test 51 replay (`market_implied.forecasts`) for 2014–25 plus the production
ledger's 2026 rows. Check: on 2021–25 the replay's model spread must equal the ledger's.

Every map is the production weekly decayed map (`fixed_bands.fit_weekly`: cuts 3/7/10, one-season half-life, two
complete earlier seasons, 300 games, 30 per band). Only its training rows differ. Age is calendar age in every arm,
so an excluded season still counts as elapsed time.

| Arm | Map training rows | Input |
|---|---|---|
| X model | all earlier games from 2014 **except seasons 2020 and 2021** | model spread |
| X line-only | same rule | market line |
| F model | all earlier games from 2014 (control) | model spread |
| F line-only | same rule | market line |
| P model | production: the ledger's own earlier games from 2021 (`fixed_band_spread`), reference | model spread |
| R raw | none | model spread |

Baselines on the same rows: always favorite, always home. Flat 1u at −110, production's pick rule
(`fixed_bands.pick`); a skip returns 0 in paired differences. Only the map's training changes: the model's
coefficients were still fitted on 2020–21 games, as in production.

P differs from F by its history window (2021+ against 2014+), so P is a reference and X is compared with F.

## Bases, never pooled

* **2022** (replay; the first season after the excluded ones). P does not exist for 2022.
* **2023–26** (the period behind the production record).

Rows: finite spread, result, model spread and X and F maps.

## Exposure, disclosed in advance

Everything about 2022–26 under the production and annual maps is known (Tests 59–60, the ledger report: P +88.6u,
+9.3% ± 3.0 on 952). Test 60's post-hoc cut is known: without 2020–21 in the *scored* seasons, model minus line-only
on 2016–22 is −0.2u. No map with 2020–21 removed from training, and no long-history (2014+) weekly map on 2023–26,
has been fitted or scored. v1.19's terms were chosen on 2019–25. Closing lines; capture time unknown.

## Primary: X model − F model on 2023–26

Per game, units(X model) − units(F model). Sum, with SE = sd of the per-game differences × √n.

* **Covid training helped:** negative and z ≤ −2 (removing 2020–21 from training reliably costs units).
* **Covid training hurt:** positive and z ≥ 2.
* **Unresolved:** otherwise. A crossing interval does not show the maps are equal.

## Reported, not gating

For each basis and season, every arm and baseline: W-L-P, skips, units, ROI ± SE (pushes in the denominator), cover
rate excluding pushes, n, break-even 52.4%. Paired contrasts with the count of differing sides: X model − F model
(primary), X model − X line-only, F model − F line-only, X model − P model, F model − P model, X model − R raw. The
band numbers of X, F and P at week 1 of each season. Checks: P reproduces 532-395-25 on 2023–26.

## What a result means

Diagnostic only; nothing here changes production, and a different training window would be a new map policy and the
owner's decision.

* If X stays near F and P on 2023–26, the record does not rest on band numbers learned from 2020–21. That does not
  make it forward evidence.
* If X falls well below F, part of the 2023–26 record came from those seasons' band numbers, and the map's edge
  depends on a training window chosen after the fact.
* F − P shows how much the record depends on production's short history window, a separate exposure.

Run: `python research/map_covid_training.py`.
