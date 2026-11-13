# ATS median and selection sanity check

**Arithmetic and chronological checks pass. The important issue is a research
objective mismatch: squared-error mean residuals were added to a median forecast.**
The feature experiments are valid as specified mean-margin overlays, but they do
not settle whether those statistics improve a properly refitted ATS median.
No production grading or live decision was changed by this audit.

## Production map and ATS logic

- Production calls the weekly median fitter, not the retained legacy W-L optimizer.
- All **64** exported weekly rules reproduce exactly. Independently evaluating
  weighted absolute loss confirms every band output is a weighted median/L1
  minimizer. All current maps are monotone, although monotonicity is not forced.
- Maps use strictly earlier weeks. Poisoning every target/future result leaves
  each rule unchanged. Losses enter as negative signed margins and tied finals
  enter as zero; the median is not fitted only on wins or absolute final margins.
- Pipeline: model win probability -> continuous signed home margin -> absolute
  confidence band (<3 / 3–<7 / 7–<10 / 10+) -> signed historical median margin.
  The public season CSV's `model_spread` already contains this mapped prediction;
  applying the map to it again would be wrong. The research did not double-map it.
- `spread_line` is the market-implied **home margin**, not the home betting
  handicap. Predicted margin above that line selects home at `-spread_line`;
  below selects away at `+spread_line`. For example, prediction +4 vs line +3
  takes home -3. A push requires actual margin == line, not merely a tied game.
- Exact model/market equality within 1e-10 takes the market favorite; zero/zero
  pick'em skips. This is an explicit policy, not evidence of a priced ATS edge.
- Independently reconstructed all **137** saved public grades and handicaps,
  **952** historical mapped grades, and **57,204** saved research pick/grade rows.
  The research's strict comparisons vs production's EPS comparisons produce no
  differences on these frozen rows. No sign, push or return arithmetic bug found.
- At risk 1u per bet, the public 75-56-6 is **+12.18u at assumed -110** and
  **+11.97u at its mixed saved/estimated prices**. Both calculations reproduce.

## The mean-versus-median mismatch

| Evaluation year | Earlier training games | Mean residual | Median residual |
|---|---:|---:|---:|
| 2024 | 272 | +1.3493 | 0.0000 |
| 2025 | 544 | +1.0074 | 0.0000 |
| 2026 | 816 | +0.9767 | 0.0000 |

Residual is actual home margin minus mapped prediction. The least-squares
intercept is the residual mean; an absolute-error/median intercept is zero in
all three training windows. Thus a zero median residual does not establish a
missing +0.98 point median correction. It can simply reflect asymmetric errors.

On the same 137 2026 games:

| Rule | ATS W-L-P | -110 units |
|---|---|---:|
| Original mapped median | 75-56-6 | +12.18 |
| Add prior residual **mean** only (+0.9767) | 67-64-6 | -3.09 |
| Add prior residual **median** only (0) | 75-56-6 | +12.18 |

The mean intercept changes **38 picks**, eight from original zero-edge games.
Its effect exists before any pressure feature is added. Original-vs-overlay
underperformance cannot all be attributed to the new features. Comparisons
against the identical mean-intercept control isolate their incremental value
within that mean-regression experiment, but still do not test a median refit.
The Gaussian cover probabilities are research approximations, not calibrated
production ATS probabilities; NFL key-number/push mass needs separate treatment.

**Correct next comparison:** fit conditional median/quantile residuals using
previous seasons only, compare with a median-aligned intercept control and the
unchanged original, and assess cover probabilities/price-aware value separately.
Do not select an objective or feature rule using the LAC/PHI slice or returns.

## Zero-edge and map-only controls

Of 137 2026 games, **20** have mapped prediction equal to the market line. The
favorite-on-equality policy goes **9-7-4, +1.18u** on those; nonzero-edge games
are **66-49-2, +11.00u**. The overall gain is not entirely an equality artifact.
Nevertheless, small shifts near an equality or half-point edge can change a
pick discontinuously, so movement alone is not new predictive information.

Passing the **market line itself** through each game's exported weekly map,
without model team-stat inputs, gives **71-60-6, +4.55u**. Its pick agrees with
the public model on **115/137 games**. The model adds four net wins on the 22
remaining disagreements (+7.64u relative units). This is a reconstructed map-only
control, not a new locked or price-aware strategy, and is too small to establish
an independent edge. Raw reconstructed model margins cover only 136 matching
games and go 70-60-6; do not compare that record as if its denominator were 137.

## Validation and limits

161 targeted tests passed, including 83 subtests: fixed bands, weekly rules,
locking, season grading, ESPN price matching and all six feature-study suites. The standalone audit
adds independent weighted-L1, target/future poisoning, full receipt reproduction
and mean/median checks. Source hashes and receipts are in results.json and
games_2026.csv; reproduce with `python research/ats_median_sanity.py`.

These historical forecasts include reconstructed and owner-recovered decisions.
The base recipe/map policy were developed on exposed history. Strict earlier-week
median fitting does not erase research-selection exposure or turn the aggregate
2026 record into independent native-forward evidence. This audit does not verify
original source-publication times or certify every historical price as executable.
