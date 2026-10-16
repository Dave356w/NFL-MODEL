# R003 ATS probability and selection improvements: AC1

**Probability calibration improves; no ATS edge is established.** The
earlier-season-selected probability model makes no -110 ATS bets under either
rule in 2023–25. The primary Stable policy also makes no bets in the separate
2019–22 development and 2026 diagnostic periods. The secondary EV policy makes
27 earlier development bets, losing 5u, and no 2026 bets. Passing avoids the
raw policy's losses in the main period but provides
no positive-return betting evidence; per-bet ROI is undefined when there are
no bets. This remains a separate research variant, not a production update.

## What was changed

Starting from unchanged R003 plain `direct_ref_h2_t3_p0`, three calibration
families each use two fixed ridge strengths, giving six challengers:

- Temperature shrinkage of raw cover-probability logits toward the market's
  conditional 50/50 baseline.
- Platt calibration, also allowing a home-cover intercept correction.
- A limited spread/total-context correction, including an effective-support
  interaction to address unreliable extreme-context probability departures.

Every weekly fit uses only earlier **out-of-sample base forecasts and outcomes**,
with a six-season window and two-season time decay. No same-week outcome enters
calibration. Minimum data is 300 decisive examples spanning two seasons;
insufficient data returns 0.5. Pushes are excluded from binary fitting and
refunded in settlement. Earlier 2015–16 plain forecasts were reconstructed
strictly prior-week to supply calibration history.

Annual choice includes fair 0.5 and raw, selecting by strictly earlier OOF
**cover log loss**, never ROI. Choices begin in 2019 after two years of
calibrated OOF paths. These procedures are chronological, but all historical
years were already exposed and motivated this family; they are not fresh tests.

For selection, the fixed EV rule requires cover probability above 52.38095%
conditional on no push at -110. The primary Stable rule additionally requires
raw context ESS >=50 and positive EV on the same side after excluding the
latest available training season. This stability refit is a sensitivity check,
not a forecast confidence interval. Neither rule's threshold is chosen by ROI.

## Probability results: 816 games, 2023–25

| Forecast | All-game conditional cover log loss ↓ | Mean absolute departure from 50% |
|---|---:|---:|
| Original plain | 0.700040 | 4.66 pp |
| Earlier-season-selected calibration | 0.693345 | 0.36 pp |
| Fair 50/50 reference | 0.693147 | 0.00 pp |

Selected gain versus raw is **0.006695**, ordinary 95% paired week interval
**[0.000008,0.013235]**. The 14-policy sensitivity interval includes zero,
so this is not a fully adjusted confirmation. Against fair 0.5, selected gain
is **−0.000198**, interval [−0.001017,+0.000620]. No incremental ATS signal
beyond the simple reference is established.

On the **same original 560 raw bets**, with 548 decisive results, predicted
cover rate changes from **56.25% to 50.17%**, versus actual **49.27%**.
The raw calibration residual is −6.98 pp, interval [−10.73,−3.37] pp;
the calibrated residual is −0.90 pp, interval [−4.63,+2.68] pp. This is a
descriptive common-cohort check, not a newly selected betting strategy.

The selected model is Platt/ridge100 in 2023 and fair in 2024–26. Earlier
choices are fair in 2019 and Platt/ridge100 in 2020–22. Thus the probability
correction itself eliminates the apparent tradable edges: both selected EV
and selected Stable pass. The stability gate is not responsible for all-pass.

## All active fixed approaches fail to earn an ATS-edge claim

Uniform -110 on both sides is the user's historical scenario assumption,
not independently archived offers. Returns risk 1u, win 10/11u and push 0u.

| Main policy | Bets | Units | ROI ± SE | Same-row spread favorite | Fair ATS null |
|---|---:|---:|---:|---:|---:|
| Original EV | 560 | −32.545 | −5.81% ±3.99 pp | −0.091u | −4.45% |
| Raw with ESS guard | 531 | −34.182 | −6.44% ±4.11 pp | +0.182u | −4.46% |
| Context/ridge10 EV | 235 | −8.455 | −3.60% ±6.15 pp | −25.636u | −4.41% |
| Context/ridge10 Stable | 164 | −6.364 | −3.88% ±7.41 pp | −2.545u | −4.46% |
| Context/ridge100 EV | 99 | −17.727 | −17.91% ±9.40 pp | +5.182u | −4.41% |
| Selected EV / Stable | 0 | 0 | Undefined | No selected rows | Undefined |

All other fixed calibrated arms that place bets also lose in the main period;
all arms, including pass-only and small samples, are retained in the full
report. No favorable ROI rank replaces the earlier-loss-selected model. The
ESS guard alone worsens raw returns here, supporting the earlier warning that
finding uncertainty does not validate an arbitrary support filter.

The primary edge gates fail: no qualified sample, no positive ROI interval,
no all-year positive returns and no proper-score advantage over fair 0.5.
Zero wagers are a decision to withhold unsupported bets, not a profitable
strategy or evidence of an ATS advantage.

## Observed scores and coherent distributions are preserved

Calibration rescales historical score weights within the three groups
home-covers / pushes / away-covers at the forecast line. Raw push mass and
within-group relative weights remain intact. Every atom is still an observed
paired score; no scores are generated, translated or enumerated. This creates
one coherent line-specific score distribution, not independent inconsistent
probability corrections for alternative handicaps.

The selected distribution's average margin/total CRPS improves from
**7.214133 to 7.182768**, descriptive gain 0.031366, interval
[0.010194,0.052993]. Margin CRPS drives most of the improvement. Winner log
loss improves in point estimate from 0.612332 to 0.608176, with unresolved
paired uncertainty. Fair anchoring scores slightly better than selected on
primary CRPS (7.181155). These are useful probability-repair diagnostics,
separate from the failed ATS-edge claim and from earlier experiments' gates.

## Implication and next test

The raw model's apparent cover edges were mostly unsupported departures from
a competitive market line. Better calibration makes the forecasts less
assertive; it does not manufacture profitable information. Retain AC1 as a
reproducible probability-repair experiment, with the original default unchanged.

The next useful edge test needs a separately specified pregame signal, such as
a timestamped team/QB matchup measure, compared against both the market and
this calibrated reference. Select predictive specifications on earlier proper
scores and retain new actual quotes/forecasts before outcomes. Further tuning
these exposed ROI slices cannot establish the desired forward edge.

## Reproduction and validation

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/ats_calibration.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/review_ats_calibration.py
```

**672 passed, 1 xfailed**; nine new calibration behavior cases plus existing
ATS coverage. Independent full run: **15 artifacts byte-identical**. There are
1,956 calibration windows: 1,950 converged fits and six minimum-data fallbacks.
All calibration/selection cutoffs precede their targets; raw ATS results and
push masses reproduce. Original 192 protected files remain unchanged.

The [full report](experiments/R003_ats_calibration/REPORT.md),
[protocol](experiments/R003_ats_calibration/PROTOCOL.md), registration history,
predictions, decisions, coefficient audits, comparisons, distribution side
effects and validation records are retained. A documented numerical line-search
repair occurred during an aborted first run; objectives, models and performance
gates were unchanged. Historical quote timing remains unaudited. Nothing was
deployed, wagered or written to the native forward ledger.
