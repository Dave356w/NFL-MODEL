# Pooled travel adjustment: R003-PT1

**No qualified improvement. Keep the plain empirical model.** Four fixed pooled
travel variants were tested after SC1's positive but unresolved travel estimate.
All four slightly worsen the primary distribution score on 2023–25. These are
exposed historical development results, not a fresh confirmation sample.

## Moneyline results

On the same 812 eligible 2023–25 bets:

| Policy | Units | ROI ± SE |
|---|---:|---:|
| Plain empirical | −4.210 | −0.52% ±2.48 pp |
| Earlier-season-selected pooled travel | −6.057 | −0.75% ±2.48 pp |
| Same-row favorite | +0.180 | +0.02% ±2.47 pp |

The selected model changes one pick; the resulting loss of 1.847 units is not
robust evidence about a betting strategy. The proportional market-correct null
is approximately −4.10%. No ROI is used for fitting or selection. No historical
spread/total ROI is claimed without actual offered prices.

## How the model shares evidence

A single regularized multinomial classifier estimates travel direction from
spread, total and residual score shape using all usable earlier games in the
six-season window. It learns linear or quadratic associations shared across
market contexts, rather than requiring an exact match of travel/rest/slot keys.
At prediction time, it evaluates each historical score atom using the target's
market lines, then uses a capped Bayes density ratio to reweight the plain
distribution. All atoms remain actual historical paired scores; no scores are
translated, simulated or enumerated. No target outcome is consumed.

Four fixed settings combine linear/quadratic score-shape terms and ridge
strength 20/100. Density ratios are capped at 0.5–2 before normalization. Class
support below 20 or unknown travel gives exactly plain; otherwise the pooled
tilt is mixed with plain using support/(support+100). Ridge, capping and mixing
are separate fixed protections. Zero outcome-shape coefficients give exactly
plain, even with nonzero market coefficients.

Pooling increases mean effective support to **142 eastward / 144 westward**
games, compared with SC1's roughly 26 median market-relevant matches. The
support definitions differ: pooling borrows strength by assuming the association
generalizes across markets. All 799 known-travel main-sample games receive an
adjustment; 17 unknown/neutral games fall back. Long-direction mean context
weights are approximately 59%, with additional coefficient regularization.

## Distribution results, 816 games 2023–25

Primary CRPS averages margin and total CRPS; lower is better.

| Arm | Primary CRPS | Gain vs plain |
|---|---:|---:|
| Plain | 7.214133 | — |
| Linear, ridge 20 | 7.217057 | −0.002924 |
| Linear, ridge 100 | 7.215555 | −0.001422 |
| Quadratic, ridge 20 | 7.216857 | −0.002723 |
| Quadratic, ridge 100 | 7.215451 | −0.001318 |

Annual selection uses winner log loss from strictly earlier OOF seasons, with
plain included and winning ties. It chooses quadratic/ridge 20 for 2023–25.
Its primary gain is **−0.002723**, 95% paired week interval
**[−0.008766,+0.003291]**; four-challenger sensitivity also spans zero. This
does not establish a harmful effect, but it fails the improvement gates.

Winner log loss improves only **0.000181**, interval [−0.001060,+0.001393].
Margin/total CRPS worsen by 0.002314/0.003133 and cover log loss worsens by
0.001161. All three primary seasons have negative mean distribution gains.
Earlier 2017–22 moneyline returns also slightly worsen (−65.44u vs −64.54u);
2026 diagnostic bets remain unchanged.

Compared with the previous fixed SC1 travel arm, the selected pooled model's
distribution gain is **−0.009791**, interval [−0.019861,+0.000293]. Against
SC1's earlier-season-selected policy it is −0.003798,
interval [−0.009857,+0.002182]. Those are descriptive comparisons; the previous
travel arm's favorable historical rank remains insufficient for adoption.

## What this changes about the hypothesis

Pooling fixes much of the matching-sample shortage, but that alone does not
create predictive information beyond market prices. Under this design, the
learned common travel relationship does not improve the full distribution.
The slight winner-score gain does not transfer to margin/total accuracy.

These timezone labels describe team home bases, not actual itinerary, sleep,
acclimation or venue-local preparation. Geography, team quality and market
selection may confound the association. The experiment does not rule out all
travel effects or every possible pooled estimator. It does reject advancing
this fixed family. Do not lower regularization or add interactions after viewing
these results and call the resulting sample independent.

No production/default/ledger change follows. Any further travel hypothesis
requires a separately fixed design and stronger feature or forward evidence.

## Validation and reproduction

**654 passed, 1 xfailed**, including 10 new behavior tests. All 788 weekly fits
converge with prior-week cutoffs. Plain reproduction error is at most 3.55e-15;
184 fallback rows exactly equal plain on checked probabilities and CRPS. A
separate full run reproduces all 15 checked artifacts byte for byte. Original
192 protected experiment/data files remain unchanged.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/pooled_travel_empirical.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/review_pooled_travel.py
```

The [full report](experiments/R003_pooled_travel/REPORT.md),
[frozen protocol](experiments/R003_pooled_travel/PROTOCOL.md), per-game predictions,
coefficient audits, source hashes, selections, category support, comparisons and
validation records are retained in `experiments/R003_pooled_travel/`.
