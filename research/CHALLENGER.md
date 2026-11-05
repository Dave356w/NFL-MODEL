# Test 60 protocol: a challenger to production on every scorecard measure

Research only. Production (v1.21: the v1.19 ten-term fit, the 0.2 favorite penalty, map policy v2 and ATS lock
policy v3), the frozen recipes, the forward ledger and the ATS locks are unchanged. Owner challenge 2026-11-05:
"build a competitive model that surpasses current production model on all measures". This protocol is committed
and pushed before any arm is scored on outcomes.

## Disclosed before the run

* Every historical basis below is exposed. v1.19's terms were chosen on 2019–25 (Test 50), the 0.2 penalty on
  2021–25, and map policy v2 after Test 59 scored 2016–26. Test 39 found that halving v1.18's departure from the
  market gained log loss on 2015–16, 2017–22 and 2023–25 (no interval excluded zero) and gave up moneyline units.
  That result suggested the challenger. The results are development evidence, not confirmation.
* Seen today without outcomes: production's departure from the no-vig moneyline, logit p − logit q, has SD
  0.09–0.25 per season (2014–25). The Fisher information it gives about its own weight is about 0.4–3.6 per season.
  One season of outcomes can therefore only pin a departure weight to about ±0.5–1.5.
* The harness reproduces production. P equals v1.19's published 2021–25 forecasts (`retro_ledger.csv`, 2.4e-15).
  Production's v2 weekly map rebuilt from the ledger equals `fixed_band_spread` on 2023–26 (0.0). Inverting the
  0.2 penalty on published 2021–25 `model_wp` recovers the unpenalized fit (2.4e-15). That inversion supplies
  2026 weeks 1–8, which the frozen feature packs do not cover.

## Arms (fixed here)

All arms share production's market inputs, rows and ATS machinery. Only the win probability p differs. Spread =
`nfl_model.implied_spread(p)` (12.37 × Φ⁻¹(p)). The arm's map is map policy v2 (`fixed_bands.fit_weekly`) fitted on
the arm's own spreads. Pick = `fixed_bands.pick` (zero edge takes the market favorite; a pick'em with zero mapped
spread skips).

| Arm | Win probability |
|---|---|
| **P production** | v1.19 weekly fit with the 0.2 favorite penalty (`retro_ledger.csv` and its research replay) |
| **C challenger: departure-calibrated v1.19** | logit p_C = logit q + α · (logit p_P − logit q), with α refit before every week |
| M market only (benchmark, not a candidate) | p = q, the proportional no-vig closing moneyline |

**C's weight α.** α is the posterior mode of a one-parameter logistic regression with offset logit q and regressor
g = logit p_P − logit q, prior α ~ N(1, 0.5²), clipped to [0, 2]. α = 1 is production exactly, so C nests P and
moves away from it only as earlier outcomes support. Training rows are every earlier labeled, priced game in the
harness, unweighted: 2014 onward, plus 2026 weeks before the forecast week. A game in week w of season Y uses only
rows with (season, week) < (Y, w). Ties are excluded. C keeps production's penalty, because g is production's
penalized departure. With no earlier rows (2014 week 1), C = P.

## Bases, never pooled

* **Win probability:** 2015–16, 2017–22, 2023–25 (v1.19 replay; 2014 is warm-up only) and **2026 weeks 1–8**
  (production's published v1.19 replay, 121 games, seen before this test).
* **ATS and spreads:** **2016–22** (map history from 2014, as Tests 54–59) and **2023–26** (map history from 2021,
  production's window, reproducing the published `fixed_band_spread` for P).

## Scorecard: every measure, every basis

Each cell is C minus P on the same rows, with a week-clustered SE unless stated. M is reported beside them.

| # | Measure | Bases | Better means |
|---|---|---|---|
| 1 | Log loss (primary) | 4 WP bases | lower |
| 2 | Brier score | 4 WP bases | lower |
| 3 | Calibration error: 10 equal-width bins of home-win p, Σ (n_b/N) · \|ȳ_b − p̄_b\|; SE from 2,000 week-cluster bootstrap resamples, seed 20261105 | 4 WP bases | lower |
| 4 | Moneyline flat 1u units (legacy, model's side at the closing moneyline, `nfl_model.flat_bets`) | 4 WP bases | higher |
| 5 | ATS units, flat 1u at −110 | 2 ATS bases | higher |
| 6 | ATS units at each game's actual spread price (−110 where none, counted) | 2 ATS bases | higher |
| 7 | ATS cover rate excluding pushes | 2 ATS bases | higher |
| 8 | Mapped spread absolute error vs the final margin | 2 ATS bases | lower |
| 9 | Raw model spread absolute error vs the final margin | 2 ATS bases | lower |

That gives 26 cells. ATS rows are the same games for every arm: graded, with a market spread and a finite mapped
spread for all three arms. Every ATS row also reports W-L-P, skips, ROI ± SE (pushes in the denominator), n, the
52.4% break-even, flips against P and the same-row always-favorite and always-home baselines. Moneyline rows report
the market-correct null and the same-row market favorite.

## Verdicts

* **Challenge (owner's wording): C surpasses P on all measures** only if C is better in point estimate in all 26
  cells. An exact tie in a cell is not a win. Cell counts of better, worse and tied are reported.
* **Reliably better on a cell:** z ≥ 1.96 in C's favour. **Reliably worse:** z ≥ 1.96 against C. These are
  per-cell, uncorrected, and descriptive.
* **Primary verdict (log loss, K = 1, bar 1.96):** *stop* if C is reliably worse on any WP basis; *better* if C is
  lower on all four WP bases and reliably lower on at least one; *forward candidate* if lower on at least three of
  the four; *unresolved* otherwise.

Also reported: α by season and week, and per-season log loss for C, P and M.

## What a result means

Diagnostic only. Adopting C changes production's probabilities, so it would be a new `REVISION`. C's α depends only
on earlier outcomes and on q and p_P. Every forward snapshot saves both (`market_no_vig_wp`, `model_wp`), so C
can run as a reporting-only shadow on native games without new capture. ROI is reported, not optimized. No result here justifies choosing a model on ATS units.

Run: `python research/challenger.py`.
