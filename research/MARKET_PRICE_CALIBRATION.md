# Test 53 protocol: price-dependent calibration of the no-vig moneyline (market only)

Research only. Production v1.19, its offset, the favorite penalty, the median map and the forward ledger
are unchanged. Owner question 2026-11-04: should the moneyline as v1.19's fixed starting point be capped by
realized market accuracy, given that "market accuracy depends on moneyline prices"? This protocol is
committed and pushed before any calibrated price is scored.

## Question

Stage 1 (this protocol): does a recalibration of the no-vig moneyline probability q that depends on the
price, fitted only on earlier seasons, forecast home wins better than q itself? Stage 2, a v1.19 refit with
the calibrated q as offset, is registered separately and only if stage 1 passes.

## Data

`research/devig_methods_results/schedule_pack.csv.gz` (Test 35's frozen nflverse pack, 2006–25 regular
season). Included games have valid prices for both sides and a decided result (ties out). q is production's
proportional de-vig. Favorite orientation: f = max(q, 1 − q), y_f = 1 if the market favorite won.

## Arms (fixed here)

Each arm is refit once per season on all earlier seasons from 2006 (expanding window), so no season sees
its own or later outcomes. The first scored season is 2009 (three earlier seasons).

| Arm | Map | Parameters |
|---|---|---|
| M0 raw | q | none (production) |
| M1 linear | logit p = a + b·logit(q), home-oriented | 2: home bias a, overall confidence b |
| M2 price bands | logit p_f = logit f + δ_k, favorite-oriented, k by f in [.50,.60), [.60,.70), [.70,.80), [.80,1] | 4 shifts, ridge 0.5·10·δ_k² each (about 50 games of "no shift") |
| M3 isotonic | p_f = isotonic increasing fit of y_f on f, clipped to [.5, .995] | step function |

M2 uses Test 35's four bands. M2 and M3 are symmetric: they act on the favorite and give the underdog
1 − p_f. M1 can change the favorite near q = 0.5 through its intercept; M2 and M3 cannot. The cap the owner
asked about is M1 with b < 1 or an M2 band with δ_k < 0.

## Selection and verdict

* **Selection (2009–16):** the arm with the lowest log loss per game; M0 if none is lower.
* **Held-out (2017–25), scored once:** the selected arm's log-loss gain over M0 per game, mean with a
  week-clustered SE and a 97.5% interval.
* **Pass:** gain > 0 with an interval that excludes zero → stage 2 can be registered.
* **Fail:** gain < 0 with an interval that excludes zero, or M0 selected → keep q.
* **Unresolved, keep q:** otherwise. A crossing interval does not show the arms are equal.

## Reported, not gating

* Every arm's held-out gain over M0 with interval, and by band.
* Per band on 2006–16 and 2017–25: n, mean f, favorite win rate ± SE, and the realized minus implied gap.
* Each arm's fitted parameters for 2017 and 2025 (M1 a, b; M2 δ_k; M3 knots).
* Season by season: the sign of the selected arm's gain.

No ROI or ATS gate. M2 and M3 never change the market favorite, so flat moneyline sides are unchanged. The
calibrated q matters only as an input to v1.19 (stage 2), where ATS would be reported.

## Exposure, disclosed in advance

Test 35 reported calibration slopes (1.006 on 2006–16, 1.080 ± 0.060 on 2017–25) and flat ROI by these same
four bands on both periods. The Calibration tab shows market WP calibration by band for 2023 onward. No
price-dependent map has been fitted or scored on outcomes before. Closing prices, capture time unknown.

## What a result means

A pass shows the closing moneyline is miscalibrated in a way earlier seasons can predict, and it would justify
stage 2: replace q with the calibrated q in the v1.19 offset and the favorite penalty. That changes
`config_signature()` and needs a new `REVISION`, which is the owner's decision. A fail or an unresolved result
leaves the fixed weight of 1 on q as is.

Run: `python research/market_price_calibration.py`.
