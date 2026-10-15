# Test 46 protocol: moneyline vs spread disagreement on 2006–2012

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner request 2026-10-15 ("build and test items"). **Committed and pushed before any
2006–2012 disagreement has been compared with an outcome.** The forward version is registered as H9
in `PREREGISTRATION.md` in the same commit.

## Question

When the no-vig moneyline and the spread-implied probability disagree, does the outcome lean toward
the spread's view? This is a market-only question. It needs no model.

## Exposure, disclosed in advance

**Where the lead comes from.** Test 42 (`DISJOINT_FEATURES.md`) found the disagreement coefficient
negative in every era (−0.061, −0.035, −0.050 per SD) and called it "the one lead worth a forward
look". On 2026-10-14 the author of this protocol re-estimated it on 2013–2026 schedule prices. The
coefficient was negative in four eras: −0.86, −0.67, −0.94 and −0.97 per unit of log-odds
disagreement, each about 1 SE. A one-sided betting rule's ROI swung with the threshold (−1.0% at
0.10, +11.6% at 0.15). Those numbers motivate this test; they are not evidence for it.

**Earlier uses of 2006–2012.** These seasons have been used only for other market questions:
* the de-vig method selection (Test 35, 2006–16 log loss);
* the source slice of H5 (low-total underdogs, 2006–2025);
* the H3 ladder margins (2006–2024);
* Tests 18–19's schedule and situation factors (2010–2025).

None of these computed the disagreement against outcomes. Before this commit, the only 2006–2012
quantities computed from these games were outcome-free: the moneyline overround by era and the
disagreement's correlation with logit q.

**Allocation of the 2006–2012 block** (also recorded in `PREREGISTRATION.md`).
* Test 46 is the block's market-only consumer and runs first, once.
* A later reduced-model test on 2008–2012 remains possible. It would disclose that Test 46 had looked
  at these seasons' market residuals, not at any model feature.
* No other consumer is named.

## Data

The nflverse `games.csv` (`nflverse/nfldata`, downloaded 2026-10-14, SHA-256 recorded). The test
freezes the regular-season games of 2006–2012 that have both moneylines, a spread and a result into
`research/ml_spread_inputs/` with provenance.

Ties (result 0) are excluded from the binary fits and push in ROI. Priced coverage is incomplete in
2006–2008; the report states it.

## Definitions (fixed)

* **q**: the proportional no-vig moneyline probability of the home team (`nfl_model.market_ml_wp`).
* **Spread probability**: `q_s = Φ(spread_line / 12.37)`. This uses the schedule's sign convention
  (positive = home favored) and production's `MARKET_SIGMA`.
* **Disagreement**: `dis = logit(q) − logit(q_s)`, with both probabilities clipped to [1e-4, 1 − 1e-4].
  Positive means the moneyline is more bullish on the home team than the spread.
* **Scale**: SD(dis) on 2013–2026 = 0.09912, computed outcome-free on 3,513 games, is used to
  report per-SD effects.

## Primary estimand

A logistic regression of the home win on an intercept, logit(q) and dis, with **free slopes**: the
same specification as Test 42 and the 2013–2026 re-estimates. It uses cluster-robust (season-week)
standard errors. The primary coefficient is `b`, on dis, per unit of log-odds disagreement.

**Decision for 2006–2012:**
* **Replicated**: b ≤ −2 SE.
* **Falsified for 2006–2012**: b ≥ 0. The lead is then **closed** if, in addition, the pooled
  2006–2026 estimate (the same specification on 2006–2026, with season-week clusters) has a 95%
  interval that includes 0.
* Otherwise **consistent sign, unresolved**.

**Power, stated now.** The 2013–2026 era fits had SE ≈ 0.85 per about 1,020 games, so the
2006–2012 SE is about 0.67 at about 1,650 games. If b = −0.85 per unit (about −0.08 per SD), then:
* z ≈ −1.3;
* replication at 2 SE has about 23% power;
* a negative point estimate has about 90% probability, so b ≥ 0 is a meaningful falsifier with
  roughly a 10% false-falsification risk.

## Secondary (reported, not decisive)

1. **Offset form**: `logit P(home) = logit(q) + a + b'·dis`. Outcome-free, dis correlates +0.56
   with logit(q) on 2006–2012. Under a fixed offset, b' would also absorb any favorite-longshot
   miscalibration of the moneyline, so this form is secondary.
2. **Rule**: 1u at the moneyline on the side the spread favors more than the moneyline does (away
   if dis > 0, home if dis < 0) when |dis| ≥ **T = 0.11133**. T is the 75th percentile of |dis|
   over 2013–2026, computed outcome-free on 3,513 games and fixed by that percentile rule, not by
   ROI. Reported with W-L-P, units, ROI ± SE, the market-correct null and the same-row market
   favorite. The rule **fails** if ROI ≤ its null.
3. **Eras**: 2006–2009 and 2010–2012 separately; the per-season priced share.

## Reading

A replication would make the H9 forward test worth watching. It would not make the lead a model
input. Using dis in production (as an input, a blended anchor or a bet filter) would need its own
pre-registered forward evidence, the owner's decision and a new `REVISION`.

Run: `python research/ml_spread_2006_12.py`. Results: `research/ml_spread_results/`.
