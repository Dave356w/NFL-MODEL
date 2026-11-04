# Test 51 protocol: per-team market-implied points in the fit

Research only. Production v1.19, its v1.16 shadow lock, frozen recipes, the median map and the forward
ledger are unchanged. Owner request 2026-11-04 ("test adding per team market implied values into fit";
owner chose both arms). This protocol and its frozen input are committed and pushed before any arm is
built or scored.

## Question

Does v1.19 forecast better when each team's market-implied points enter the fit, either (A) for this
game or (B) as the team's decayed record of beating or missing its implied points in earlier games?

## Definitions

Implied points per team from the closing spread and total (nflverse sign: `spread_line` > 0 means the
home team is favored; `result` = home − away):

* home implied = (total_line + spread_line) / 2; away implied = (total_line − spread_line) / 2.

v1.19 already fixes the no-vig moneyline log-odds as an offset with weight 1. Arm A's free coefficients
therefore measure what the spread and total add beyond the moneyline: the home-minus-away part of the
two terms is the spread (its disagreement with the moneyline is research H9's subject), and the sum is
the total.

## Arms (fixed here)

Both arms are v1.19 (`PRODUCT_RECIPE`: v1.18 recipe on the ten `CORE_TERMS`, h8 profiles, h16 pass
contexts, ridge 0.1, market offset, favorite penalty λ 0.2 applied after the fit) with two added terms.
The added terms are fitted with the context ridge 0.1 and scaled by the fit's weighted RMS like every
other term (no centering). A missing value is 0, as for every production input. Weekly refits use
earlier rows only.

| Arm | Added terms |
|---|---|
| P | none (v1.19) |
| A this game's implied points | `mkt_home_implied` = home implied − 22.5; `mkt_away_implied` = away implied − 22.5 |
| B history vs implied points | `d__mkt_off_resid`, `d__mkt_def_resid` (home minus away) |

Arm B, per team and game, from the team's earlier regular-season games only (strictly earlier
(season, week); at most the three prior seasons, as production):

* offense residual o = points scored − own implied points; defense residual d = points allowed −
  opponent's implied points;
* pregame value = Σ w·x / (Σ w + 4), w = 2^(−games ago / 8) × 0.5^(seasons back). This is production's
  decayed point margin rule (h8, offseason halving, four pseudo-games at a prior of 0 = "on market").
  A positive o means the team has scored more than the market expected; a positive d means it has
  allowed more.

The 22.5 reference in A is half of v1.17's fixed 45-point total reference; it is fixed here, not fitted.

## Input

`research/market_implied_inputs/schedule_scores.csv`: nflverse `games.csv`, regular season 2011–2025,
fetched 2026-11-04 (sha256 in `provenance.json`). Home, away, result and spread are identical to both
frozen feature packs on every shared game. Totals are closing lines, the same basis as the historical
moneyline offset. Arm B's history begins 2011 so 2014 forecasts have three prior seasons.

## Bases, never pooled

2015–16, 2017–22 and 2023–25, from the Test 38/50 packs (`out_of_sample_results/frozen_features_2013_2020.csv.gz`
for 2014–20, `shrinkage_results/frozen_training_features.csv.gz` for 2021–25). P must reproduce v1.19's
published forecasts (`data/latest/retro_ledger.csv` `model_wp`, 2021–25) and Test 50's S3 forecasts
(2014–20) to 1e-9, and production's `fixed_band_spread` for 2023–25 with the 2021+ map history.

## Exposure, disclosed in advance

All three bases have been seen. Relevant earlier looks: Test 12 (market as an input: the features add
nothing to the close), v1.17's total interactions (2023–25), the totals study's per-team residuals against
implied points (addendum C, totals only, 2017–25), Test 46 / H9 (spread vs moneyline disagreement,
2006–2026, forward registration running), and Test 50, which chose v1.19's terms on 2019–25. No arm here
has been scored on win outcomes. A clean test is forward.

## Primary: log loss

Per basis, `LL(arm) − LL(P)` per binary game (×1000), mean with a week-clustered SE. Negative means the
arm is more accurate. Two arms, so the bar is |z| ≥ 2.24 (Bonferroni 97.5%).

* **Stop:** worse than P at z ≥ +2.24 on any basis.
* **Better:** nominally better on all three bases and z ≤ −2.24 on at least one.
* **Forward candidate:** not reliably worse on any basis and nominally better on at least two of three.
* **Unresolved:** otherwise.

Reported alongside: each added coefficient in the last fit of each basis (scaled units), and the
correlation of each added term with the market log-odds and with P's departure from the market.

## Secondary: ATS (reported, not optimized)

As Test 50: flat 1u at −110 against the market spread, same rows for every arm, each arm's model spread
`12.37·Φ⁻¹(p)` mapped with its own prior-season median map (`fixed_bands.fit`), zero edge takes the
favorite, a pick'em skips. Per basis: W-L-P, skips, units, ROI ± SE (pushes in the denominator), cover rate
excluding pushes, n, break-even 52.4%, same-row always-favorite and always-home baselines, the raw spread
view, side flips against P and units on those flips. 2023–25 also shows production's 2021+ map history.
Moneyline flat units are reported last (legacy).

## What a result means

Diagnostic only. Either arm changes `config_signature()` and would need a new `REVISION`; forward use
would also need a lock-time total captured with each snapshot (today `totals.py` captures totals
separately and the forward snapshot does not record one). A "better" or "forward candidate" arm would next
run as a reporting-only shadow on native locks, reviewed by the owner at 100 decided locks on log loss and
ATS units against v1.19 on the same games.

Run: `python research/market_implied.py`.
