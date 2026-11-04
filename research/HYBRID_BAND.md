# Test 54 protocol: raw spread inside the 3–7 band, median map elsewhere (historical)

Research only. Production v1.19, the median map, the lock policy and the forward ledger are unchanged. Owner
request 2026-11-04 after the band breakdown of map vs raw spread: "test the 3–7 weakness ... register 'raw
spread inside 3–7, map elsewhere' historically." This protocol is committed and pushed before the hybrid is
scored on any season.

## Hypothesis and where it came from

On the v1.19 replay with production's map, the map trailed the raw spread only where |raw spread| is in [3, 7):
2023–26 −26.7u ± 24.0 (map 162-170-12, raw 176-156-12), 2025–26 −7.6u ± 11.5. The rule was found on 2023–26,
so those seasons are discovery and cannot test it.

## Arms (fixed here)

All arms use v1.19's forecast p and model spread x = 12.37·Φ⁻¹(p), the market spread L, flat 1u at −110, and
production's pick rule (zero edge takes the market favorite; a pick'em with zero edge skips).

| Arm | Prediction compared with L |
|---|---|
| M map | median-mapped spread (production) |
| R raw | x |
| H hybrid | x when 3 ≤ \|x\| < 7, otherwise the mapped spread |

The band edges are the map's own cuts (`np.digitize(|x|, [3, 7, 10]) == 1`). H differs from M only inside the band.

## Bases, never pooled

* **Test (primary): 2016–22.** v1.19 replayed with weekly refits on earlier rows (Test 51's harness, which reproduces
  the published v1.19 forecasts to 2.4e-15). Each season's map is fitted on this replay's earlier seasons from 2014
  (`fixed_bands.fit`: two seasons and 300 games minimum), so 2016 is the first mapped season.
* **Discovery (descriptive): 2023–26** with production's map from `data/latest/fixed_band_ledger.csv`.

## Exposure, disclosed in advance

v1.19's ten terms were chosen on 2019–25 (Test 50), so the forecasts on 2019–22 are not clean. Tests 50–51 already
reported map vs raw over all bands on 2017–22 (raw ahead of the map in total), but no band-level ATS for these
seasons has been computed. Closing lines; capture time unknown.

## Primary: H − M on 2016–22

Per bet, units(H) − units(M) on the same games (nonzero only inside the band where the sides differ). Sum and mean
with an SE from the per-game differences.

* **Supported:** the sum is positive and z ≥ 2.
* **Contradicted:** the sum is negative and z ≤ −2.
* **Unresolved:** otherwise. A crossing interval does not show the rules are equal.

## Reported, not gating

For each basis and season: W-L-P, skips, units, ROI ± SE (pushes in the denominator), cover rate, n and break-even
52.4% for M, R and H, with the same-row always-favorite and always-home baselines; the band-only records (in band
and outside it); flips H vs M with units on them; and the zero-edge count inside the band. Per-band records are
descriptive, not cover probabilities.

## What a result means

Diagnostic only. Even "supported" would not change production: the 2016–22 replay is exposed through v1.19's term
selection, and changing the ATS selection rule is a new policy version and the owner's decision. The clean next
step would be a reporting-only H arm on native locks, reviewed with the map-vs-raw question at 100 decided locks.

Run: `python research/hybrid_band.py`.
