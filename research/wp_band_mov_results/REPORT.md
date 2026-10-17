# Model W% bands: average versus median MOV

**Median MOV is not established as statistically better.** On the primary
816-game 2023–25 sample, seven-band medians have slightly worse absolute
error than matching means. Four-group medians have slightly better absolute
error than matching means, but their paired interval crosses zero. Neither
median method demonstrates lower primary absolute error than raw v1.18.

The four-group median is an interesting ATS development candidate: +25.55u
in the pooled 895-game replay versus installed fixed bands +6.00u. Its paired
unit-gain interval crosses zero, and exact-line skips materially affect returns.
**No production replacement is made.**

## What was tested

For each target season, fit only strictly earlier seasons. Map model confidence
`max(p,1-p)` to the arithmetic mean or sample median of **signed pick margin**:
actual home margin multiplied by the sign of `p-.5`. Losses are negative, ties
zero; this is not the average size of wins. Forecasts return to home-margin sign.
No current-season outcome, market line or ATS reward enters these empirical fits.

The primary requested definition uses the existing seven production confidence
bands: 50–55%, 55–60%, 60–65%, 65–70%, 70–75%, 75–80%, 80%+. A definition
check retains the installed four groups, equivalent to confidence cuts
59.5812%, 71.4264%, 79.0572%, and replaces ATS W−L fitting by mean or median.
This tests both available group definitions; it does not claim to reconstruct
an unseen original average-MOV table. Weighted monotone means were also tested;
all prior seven-band means were already increasing, so they made no change.

The locally written mean protocol preceded its forecasts. The user requested
medians after mean results were known; the extension was specified before
median scoring. Historical outcomes and earlier research are exposed. This is
development, not an externally registered holdout or native forward test.

## Mean and median answer different questions

* A conditional **mean** minimizes expected squared error; use MSE/RMSE for
  this target. It describes expected margin and responds to blowout tails.
* A conditional **median** minimizes expected absolute error; use MAE. It is
  less sensitive to blowouts, but a sample band median is not guaranteed to
  generalize better than an estimated mean.
* Neither point estimate supplies cover and push probabilities at an arbitrary
  quoted handicap. An ATS comparison is a separate sign-decision diagnostic.

## Primary result: 2023–25, 816 matched games

Lower errors are better. Flat 1u risk at assumed −110; final ties included.

| Method | MAE | RMSE | ATS W–L–P | Skips | Units | ROI/bet |
|---|---:|---:|---:|---:|---:|---:|
| Raw v1.18 | 9.7159 | 12.6255 | 409–388–19 | 0 | -16.18 | -1.98% |
| Market spread | 9.7445 | 12.6533 | 0–0–0 | 816 | +0.00 | undefined |
| Installed fixed bands | 9.8199 | 12.8407 | 401–363–19 | 33 | +1.55 | +0.20% |
| 7 W% bands: mean | 9.7613 | 12.6935 | 413–384–19 | 0 | -8.55 | -1.05% |
| 7 W% bands: monotone mean | 9.7613 | 12.6935 | 413–384–19 | 0 | -8.55 | -1.05% |
| 4 existing groups: mean | 9.7806 | 12.7324 | 414–383–19 | 0 | -6.64 | -0.81% |
| 7 W% bands: median | 9.7776 | 12.7838 | 337–321–8 | 150 | -14.64 | -2.20% |
| 4 existing groups: median | 9.7653 | 12.8000 | 375–323–11 | 107 | +17.91 | +2.53% |

The market-spread point forecast equals the quoted line and thus has no
ATS side under this sign rule; its all-skip row is not a profit estimate.

### Is the median statistically better than the matching mean?

Positive gain means the median has lower absolute error, in points/game.
Paired whole-week bootstrap within seasons: 10,000 draws, seed 20261017,
54 primary blocks. The 99% bounds are a five-candidate sensitivity check,
not correction for the full history of adaptive research.

| Groups | MAE gain vs matching mean | 95% interval | 99% interval |
|---|---:|---:|---:|
| 7 W% bands: median | -0.0163 | [-0.1047, +0.0737] | [-0.1292, +0.1022] |
| 4 existing groups: median | +0.0153 | [-0.0506, +0.0805] | [-0.0744, +0.0999] |

Both intervals include zero. Seven-band median MAE is 0.0617 point
worse than raw v1.18 (95% gain interval −0.1821 to +0.0597); four-group median
is 0.0494 point worse (−0.1594 to +0.0591). These primary results do not support
a statistically better median spread forecast.

Means are assessed against MSE and medians against MAE for the nomination
criterion. No candidate has positive 99% lower bounds against both raw v1.18
and market on its respective target. Decision:
`retain_production_no_candidate_qualifies`.

## Separate 2026 diagnostic: Weeks 1–5, 79 games

| Method | MAE | RMSE | ATS W–L–P | Skips | Units | ROI/bet |
|---|---:|---:|---:|---:|---:|---:|
| Raw v1.18 | 10.0054 | 12.6288 | 36–37–6 | 0 | -4.27 | -5.41% |
| Market spread | 9.7785 | 12.4289 | 0–0–0 | 79 | +0.00 | undefined |
| Installed fixed bands | 9.8354 | 12.4864 | 39–31–3 | 6 | +4.45 | +6.10% |
| 7 W% bands: mean | 10.0854 | 12.7717 | 36–37–6 | 0 | -4.27 | -5.41% |
| 7 W% bands: median | 9.8671 | 12.6262 | 30–26–2 | 21 | +1.27 | +2.19% |
| 4 existing groups: mean | 10.0309 | 12.5834 | 32–41–6 | 0 | -11.91 | -15.07% |
| 4 existing groups: median | 9.7468 | 12.4504 | 37–26–2 | 14 | +7.64 | +11.75% |

Medians beat matching means on this small slice, with positive descriptive
MAE intervals. There are only five week blocks; the intervals condition on
fixed fitted paths and are not independent prospective confirmation. The
larger primary sample does not establish the same improvement.

## What the 2026 mapping actually is

Training: 1,359 games through 2025. Values are signed margins on the model
pick side, before conversion to home-margin sign.

| Model confidence | Prior n | Mean MOV | Median MOV |
|---|---:|---:|---:|
| 50–55% | 254 | 1.165 | 2 |
| 55–60% | 259 | 3.012 | 3 |
| 60–65% | 224 | 4.156 | 3.5 |
| 65–70% | 189 | 5.720 | 5 |
| 70–75% | 163 | 8.086 | 7 |
| 75–80% | 134 | 8.604 | 7 |
| 80%+ | 136 | 14.632 | 14.5 |

For the four existing groups:

| Confidence | Prior n | Mean MOV | Median MOV | Installed ATS value |
|---|---:|---:|---:|---:|
| 50–59.5812% | 497 | 2.191 | 3 | 4 |
| 59.5812–71.4264% | 478 | 4.810 | 4 | 5 |
| 71.4264–79.0572% | 228 | 8.877 | 7 | 7 |
| 79.0572%+ | 156 | 13.699 | 14 | 13 |

The four-group median mapping is **3/4/7/14**. These values were not
rounded or selected for ATS results. Earlier-season mappings are independently
fitted, never backfilled with the 2026 map.

## ATS evidence and exact-line sensitivity

Pooled 2023–2026 W5, 895 opportunities:

| Method | Bets | W–L–P | Skips | Units | ROI/bet |
|---|---:|---:|---:|---:|---:|
| Raw v1.18 | 895 | 445–425–25 | 0 | -20.45 | -2.29% |
| Installed fixed bands | 856 | 440–394–22 | 39 | +6.00 | +0.70% |
| 7 W% bands: mean | 895 | 449–421–25 | 0 | -12.82 | -1.43% |
| 7 W% bands: median | 724 | 367–347–10 | 171 | -13.36 | -1.85% |
| 4 existing groups: mean | 895 | 446–424–25 | 0 | -18.55 | -2.07% |
| 4 existing groups: median | 774 | 412–349–13 | 121 | +25.55 | +3.30% |

Four-group median gains +2.18 units per 100 opportunities over
installed fixed bands; the paired 95% interval is [-2.95, +7.23].
It includes no gain. Comparing units per opportunity retains all skips and
does not misattribute different betting coverage to prediction quality.

Four-group median by season:

| Season | W–L–P | Skips | Units | ROI/bet |
|---|---:|---:|---:|---:|
| 2023 | 124–112–9 | 27 | +0.73 | +0.30% |
| 2024 | 110–104–1 | 57 | -4.00 | -1.86% |
| 2025 | 141–107–1 | 23 | +21.18 | +8.51% |
| 2026 | 37–26–2 | 14 | +7.64 | +11.75% |

About 83% of pooled net units comes from 2025. This is concentration,
not a reason to select that year. Actual historical spread prices/capture
times are unverified; −110 is an assumed scenario.

Medians can land exactly on the market line. The unchanged rule skips those
games before checking spread pushes. After seeing results, this descriptive
±0.01-point diagnostic was added; no perturbation is adopted:

| Four-group median perturbation | W–L–P | Skips | Units |
|---|---:|---:|---:|
| -0.01 | 460–410–25 | 0 | +8.18 |
| 0.0 | 412–349–13 | 121 | +25.55 |
| 0.01 | 473–397–25 | 0 | +33.00 |

The return changes materially when exact equalities are filled from
either side. These are different selection rules, not uncertainty estimates
for the unchanged median rule. No favorable epsilon is selected.

## Reproduction and scope

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.wp_band_mov
python -m pytest tests/test_wp_band_mov.py -q
```

Inputs are the frozen `research/continuous_spread_results/input.csv` and
`board_input.csv`; 2021–22 supply warm-up. The new results directory retains
every scored forecast, current counterfactual, annual fit counts/means/medians,
point and ATS summaries, paired intervals, sensitivity checks and source hashes.
Current Week 6 forecasts are counterfactual research, never native forward rows.

Validation details are in `VALIDATION.md`. Production, moneylines, fixed bands,
build workflows and all original ledgers are unchanged. Historical architecture
and input-vintage uncertainty remain; raw NFL inputs were not rebuilt.
