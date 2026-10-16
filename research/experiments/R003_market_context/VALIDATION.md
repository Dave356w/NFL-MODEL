# MC1 / MC2 execution and validation

- **20 fixed candidate settings across two separately specified iterations**,
  plus global empirical controls and earlier-season selected policies.
- MC1: 10 kernel/neighbor/translated candidates. MC2: 10 direct-only refinement
  candidates, specified after MC1 results and labeled exploratory.
- Main score sample: 816 games, 2023–25, 272 per season. Moneyline common sample:
  812 bets. Other periods are separate: 1,567 earlier games and 79 diagnostic games.
- **629 repository tests passed, 1 expected failure**, 71.42 seconds. The 11 new
  tests cover source-only pairs, context weights, backoff/ESS, stable neighbor
  ties, prior-week filtering, future/own-label invariance, earlier-season
  selection, exact CRPS, infinite endpoint losses, translated negative-atom
  handling, coherence, quoted settlement, CLI and protected outputs.
- Notebook already in sync; **43 data files passed validation**; diff check passed.
- Both independent reruns exactly match prediction bytes, annual selections,
  metrics, contrasts, returns, reliability, reference/provenance, stability and
  reports. See each batch's `deterministic_reproduction.json`.
- Functional quote evaluation on four separated historical games exactly matches
  saved probabilities, including integer-line pushes. Synthetic −110 quotes are
  used only for functional verification, never historical spread ROI.
- **192 original experiment/data files remain hash-identical**. RF1's prediction
  hash also matches its prior provenance. Original production and ledger untouched.
- No live quote, prospective forecast, new outcome, deployment or wagering.

## Complete outcomes, including unfavorable findings

MC1 selected the market-relative variant with pseudo-games 80 in every target
season using strictly earlier OOF seasons. Main combined CRPS improves 0.023585
versus R003 but the interval includes deterioration. The positive-bound gate
fails. Main moneyline return is −1.71u, ROI −0.21% ±2.47 pp SE, favorite +0.18u,
negative-hold null −4.10%. This does not establish profitable forecasting.

MC2 selected the direct kernel with spread bandwidth 2, total bandwidth 3 and
zero global backoff in every target season. It improves MC1 direct matching
by 0.049928 CRPS points, descriptive interval [0.019475,0.082855]. It remains
worse than R003 by 0.037226, loss-increase interval [0.004292,0.069043], and
fails practical, positive-bound, annual-consistency and event-score gates.
Moneyline return is −4.21u, ROI −0.52% ±2.48 pp, same favorite/null controls.

The MC2 direct model retains actual football score pairs and gives useful
descriptive key-number shape: predicted three-point margin frequency 14.64%
versus 14.22% observed; seven-point 7.83% versus 8.33%. The translated benchmark
substantially understates those key margins and overstates ties. Translations
also create a small unsupported-score mass; it is reported, not silently masked.
These pooled comparisons are post-experiment diagnostics, not separate formal
discoveries. See `exploratory_diagnostics.json` and the high-level review.

Neither batch is promoted. The direct model is a transparent research
implementation of the owner's empirical idea; the translated benchmark is
explicitly a different assumption. Captured executable spread/total odds are
needed to assess whether their distribution-shape differences matter financially.

The reviewed source and parameters were not changed to force a failed gate to
pass. All 20 settings, unsuccessful arms, losses and first-iteration findings
remain available. No independent historical confirmation is claimed.
