# Test 58 protocol: market-centered ATS cover probability at actual spread prices

Research only. Production v1.19, the median map, lock policy v2 and the forward ledger are unchanged. Owner request
2026-11-04: instead of the median map, start from the market line and its price and turn that into a cover
probability, using actual spread prices. This protocol and its frozen input are committed and pushed before any arm
is scored.

## Question

Does v1.19's disagreement with the market spread improve the market's own no-vig cover probability, measured by
cover log loss? ROI at the actual prices is reported, not optimized.

## Input

`research/spread_price_inputs/spread_odds.csv`: nflverse `games.csv` (fetched 2026-11-04), regular season 2014–2026,
completed games with valid prices on both sides (|odds| ≥ 100): game_id, season, week, spread_line, result,
home_spread_odds, away_spread_odds. Prices are the source's quotes at the listed line (closing basis, capture time
unknown), the same basis as the spread line and moneyline used elsewhere.

## Definitions

Home covers if result > L, away if result < L, push if equal (L = home spread, positive when the home team is
favored). Spread prices settle on decided games only, so the proportional de-vig of the two prices (as production's
moneyline) is the market's no-vig home cover probability given no push: q.

## Arms (fixed here)

Forecast p of a home cover given no push:

| Arm | Forecast |
|---|---|
| M market | q |
| A raw disagreement | logit p = logit q + β·(x − L)/10, x = v1.19's raw model spread (12.37·Φ⁻¹(p_win)) |
| B mapped disagreement | logit p = logit q + β·(m − L)/10, m = production's median-mapped spread |

β is one coefficient per season, fitted by maximum likelihood on decided games of strictly earlier seasons (no
intercept, offset logit q, no ridge). Fits use the basis's own history: the v1.19 replay from 2014 for 2016–22 and
production's ledger from 2021 for 2023–26 (at least two earlier seasons). Arm B needs a map, so it starts where the map
does.

## Bases, never pooled

* **2016–22:** v1.19 replay (Test 51's harness, which reproduces the published v1.19 forecasts), maps from 2014.
* **2023–26:** production's v1.19 ledger and exported map.

## Exposure, disclosed in advance

v1.19's terms were chosen on 2019–25. ATS results for these seasons were reported in Tests 54–57 and Test 48 (v1.18).
Actual spread prices have not been used in any earlier test. The primary metric is a proper score, not ROI.

## Primary: cover log loss gain over M

Per basis, LL(M) − LL(arm) per decided game (×1000), mean with a week-clustered SE. Two arms, bar |z| ≥ 2.24.

* **Supported:** positive with z ≥ 2.24 on one basis and positive on the other, with every fitted β > 0.
* **Contradicted:** negative with z ≤ −2.24 on either basis.
* **Unresolved:** otherwise.

## Reported, not gating

* Fitted β by season; the share of games where |p − q| exceeds the price's break-even margin.
* Calibration: predicted vs realized home cover rate by decile of p − q.
* **ROI at actual prices.** Each arm bets the side with positive expected value at its own price
  (EV = p·payout − (1 − p) for home, likewise for away; skip if neither is positive). Wins pay the actual price, losses
  −1, pushes 0. Reported with W-L-P, bets, units, ROI ± SE, the market-correct null on the same bets, and production's
  ATS picks, always favorite and always home graded at the same actual prices.

## What a result means

Diagnostic only. A supported arm would be a candidate cover-probability forecast. Using it to choose ATS bets would be
a new ATS policy version and the owner's decision, and it would need a lock-time spread price saved with each lock.

Run: `python research/spread_price_probability.py`.
