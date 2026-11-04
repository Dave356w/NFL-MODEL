# Test 52 protocol: implied points as fitted features, with no moneyline offset

Research only. Production v1.19, its v1.16 shadow lock, frozen recipes, the median map and the forward
ledger are unchanged. Owner request 2026-11-04, after Test 51: "can we test implied points as feature
without the moneyline as its starting point?" This protocol is committed and pushed before any arm is
built or scored. It reuses Test 51's frozen input (`market_implied_inputs/schedule_scores.csv`) and
definitions (home implied = (total + spread)/2, away implied = (total − spread)/2, each minus 22.5).

## Question

If the market enters the fit only through each team's implied points, with fitted weights, instead of
as the no-vig moneyline fixed at weight 1, does the model forecast as well as or better than v1.19?

## Arms (fixed here)

Each arm is fitted like v1.19 (h8 profiles, h16 pass contexts, ridge 0.1 on profile terms with site at
0.01, ridge 0.1 on context and added terms, scaling by weighted RMS without centering, weekly refits on
earlier rows only, two-season label decay) with two differences: **no moneyline offset** (the linear
predictor starts at 0), and **no favorite penalty** (the penalty shrinks toward the moneyline, so it
would bring it back). Training and forecast rows are v1.19's own: rows with a no-vig moneyline and pass
contexts, so every arm is scored on identical games. The moneyline only defines which rows are eligible.

| Arm | Fitted terms | Market input |
|---|---|---|
| P | v1.19's ten core terms | moneyline offset, weight 1, favorite penalty 0.2 |
| C core + implied, no offset | ten core terms + `mkt_home_implied`, `mkt_away_implied` | implied points only, fitted weights |
| C0 implied only, no offset | `site`, `mkt_home_implied`, `mkt_away_implied` | implied points only, fitted weights |

C0 is the control: how well the spread and total alone price games when the fit chooses their weights.
The difference between C and C0 is what v1.19's box-score terms add on top of implied points.

The no-offset fit is a research copy of `fit_composite`. Before any arm is scored, the copy run with the
offset and penalty switched back on must reproduce P to 1e-9.

## Bases, never pooled

2015–16, 2017–22 and 2023–25, as in Test 51 (same packs). P must reproduce v1.19's published 2021–25
forecasts to 1e-9.

## Exposure, disclosed in advance

All bases were seen before, and Test 51 has just scored implied points with the offset on the same games.
Test 12 found that a free market weight on the moneyline was no better than the offset (−0.0002 ± 0.0011
log loss on 2023–25). Spreads and totals are closing lines, like the historical moneyline.

## Primary: log loss

Per basis, `LL(arm) − LL(P)` per binary game (×1000), mean with a week-clustered SE; negative means the
arm is more accurate. Two arms, bar |z| ≥ 2.24 (Bonferroni 97.5%). Verdicts as Test 51:

* **Stop:** worse than P at z ≥ +2.24 on any basis.
* **Better:** nominally better on all three bases and z ≤ −2.24 on at least one.
* **Forward candidate:** not reliably worse on any basis and nominally better on at least two of three.
* **Unresolved:** otherwise.

Also reported per basis: each arm and P against the no-vig moneyline alone (same rows, ×1000, SE), and the
fitted implied-point coefficients in the last fit of each basis.

## Secondary: ATS (reported, not optimized)

As Tests 50–51: flat 1u at −110 against the market spread, the same rows for every arm, each arm's own
prior-season median map on `12.37·Φ⁻¹(p)`, zero edge takes the favorite, a pick'em skips. W-L-P, skips,
units, ROI ± SE (pushes in the denominator), cover rate, break-even 52.4%, always-favorite and always-home
baselines, raw spread view, flips against P. Moneyline flat units last (legacy).

## What a result means

Diagnostic only. Removing the offset changes the architecture and `config_signature()`, so adopting
it would need a new `REVISION`. It would also need a lock-time total with every snapshot. A "better" or
"forward candidate" arm would next run as a reporting-only shadow, reviewed by the owner at 100 decided
locks against v1.19 on the same games.

Run: `python research/implied_no_offset.py`.
