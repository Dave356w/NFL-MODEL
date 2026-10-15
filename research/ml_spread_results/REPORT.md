# Test 46: moneyline vs spread disagreement on 2006–2012

Protocol [`ML_SPREAD_2006_12.md`](../ML_SPREAD_2006_12.md), committed and pushed (`f6d90a8`) before
any 2006–2012 disagreement was compared with an outcome. H9 (the forward version) was registered in
the same commit. Market prices only; no model. Run once: `python research/ml_spread_2006_12.py`.

**Registered verdict: consistent sign, unresolved.** Not replicated at 2 SE; not falsified.

## Primary: home win ~ 1 + logit(q) + dis (free slopes), season-week clusters

`dis = logit(q) − logit(Φ(spread/12.37))`. Positive means the moneyline is more bullish on the home
team than the spread.

| Sample | n | b on dis (per log-odds unit) | per SD (0.0991) | z |
|---|---:|---:|---:|---:|
| **2006–2012 (unseen for this question)** | 1,657 | **−1.12 ± 0.64** | −0.111 | −1.76 |
| 2006–2009 | 890 | −1.51 ± 0.85 | −0.150 | −1.79 |
| 2010–2012 | 767 | −0.50 ± 0.97 | −0.049 | −0.51 |
| 2013–2026 (discovery: the lead was found here) | 3,472 | −0.88 ± 0.45 | −0.088 | −1.95 |
| Pooled 2006–2026 | 5,129 | −0.98 ± 0.37, 95% [−1.71, −0.26] | −0.098 | −2.68 |

* **The sign replicates on the one block that was never used for this question.** There are two
  independent blocks, not six or eight eras:
  * 2013–2026 is the discovery data. Its four era fits (−0.86, −0.67, −0.94, −0.97; model-based
    SEs about 0.8–1.4) and Test 42's three era estimates all come from those same seasons.
  * 2006–2012 is the one held-out estimate.

  `ml_spread_discovery_eras.py` reproduces the 2013–2026 numbers the protocol cites
  (`discovery_eras.json`).
* **The pooled interval excludes zero, but it is not independent confirmation.** It includes
  2013–2026, where the lead was found. The registered decision uses 2006–2012 alone: b = −1.12
  against a −2 SE bar of −1.27. `lead_closed` is false.
* **The size is about what the protocol assumed.** It assumed −0.85; at 2006–2012's SE of 0.64,
  replication had about 25% power.
* **The logit(q) slope is above 1:** 1.09 ± 0.09. The moneyline's favorites won slightly more than
  q in 2006–2012, the reason the offset form is secondary.

**Secondary, offset form** (`logit(q) + a + b'·dis`): b' = −0.70 ± 0.49 (z −1.44).

## Secondary: the rule

1u at the moneyline on the side the spread favors more, when |dis| ≥ T = 0.11133. T was fixed in
advance as the 2013–2026 75th percentile.

| Sample | Bets | W-L-P | Units | ROI ± SE | Null | Same-row favorite |
|---|---:|---|---:|---:|---:|---:|
| 2006–2012 | 584 | 193-390-1 | +36.1 | +6.2% ± 7.2 | −2.1% | −42.9u |
| 2006–2009 | 338 | 121-217-0 | +63.3 | +18.7% ± 10.2 | −1.8% | −39.6u |
| 2010–2012 | 246 | 72-173-1 | −27.2 | −11.1% ± 9.9 | −2.4% | −3.3u |

* **Verdict: ROI above its null, unresolved** (+8.3 points over the null, about 1.1 SE).
* **The rule swings by era**, the same instability seen on 2013–2026 across thresholds.
* **91% of its bets are underdogs.** It mostly fades favorites whose moneyline is richer than the
  spread implies.
* **It saw 35% of games, not the planned 25%.** Disagreement is wider in 2006–2012 (SD 0.115,
  75th percentile 0.130) than in 2013–2026 (0.099, 0.111), so the fixed T admits more games.

## Coverage

| Season | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Priced, decided games / 256 | 209 | 255 | 185 | 242 | 256 | 256 | 256 |

Missing prices fall mostly in early weeks of 2006 and 2008.

## Reading

The lead survives its one unseen historical test with the same sign and a similar size, but it does
not clear the registered 2 SE bar. Nothing here makes dis a model input. H9 is now the test that
decides it, on lock-time prices from 2026 week 6. It needs about 1,650 forward games to approach
2 SE at this effect size, roughly six seasons. The rule's ROI is too era-dependent to act on.
