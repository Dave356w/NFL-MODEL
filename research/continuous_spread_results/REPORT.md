# Continuous v1.18 spread: no replacement qualifies

Run October 17, 2026 UTC (October 16 Pacific). Base repository commit `6b421a52a38e9259739c9f672bceea148cdd1bb6`.

**Retain raw v1.18 and production fixed bands.** Three fixed continuous margin
calibrations were implemented and tested. None improves the primary 2023–25
mean-squared-error estimate over raw v1.18; none resolves an improvement over
both raw v1.18 and the market. The smaller 2026 slice favors shrinkage for
margin error, but that does not establish an ATS or general forecasting gain.

## What changed

New isolated research module `research/continuous_spread.py` estimates continuous
mean home-minus-away margins, with a reproducible comparison and a counterfactual
current board. Slopes fit squared margin error using only earlier seasons.
Production code, moneyline forecasts, fixed bands, build workflows and append-only
ledgers are unchanged. This is a failed replacement experiment, not a deployment.

The design was written locally in `research/CONTINUOUS_SPREAD.md` before these
challenger forecasts were computed; it was not externally preregistered.
Both the historical architecture and the outcome data were already exposed.

## Margin accuracy

Primary: 816 common games, 2023–25. Diagnostic: 79 games, 2026 Weeks 1–5.
Final ties are included. Lower is better; errors are points.

| Method | Primary MAE | Primary RMSE | 2026 MAE | 2026 RMSE |
|---|---:|---:|---:|---:|
| Raw v1.18 | 9.7159 | 12.6255 | 10.0054 | 12.6288 |
| Market spread | 9.7445 | 12.6533 | 9.7785 | 12.4289 |
| Production fixed bands | 9.8199 | 12.8407 | 9.8354 | 12.4864 |
| Market + shrunk raw gap | 9.7242 | 12.6295 | 9.8730 | 12.4804 |
| Market + isolated model signal | 9.7246 | 12.6422 | 9.8089 | 12.4469 |
| Market + split isolated signal | 9.7276 | 12.6460 | 9.8280 | 12.4565 |

The first candidate reduces all-period 2023–2026 RMSE from 12.6257 to
12.6164, only 0.0093 point. Pooling the 2026 diagnostic into the primary period
would hide that its 2023–25 estimate is worse than raw v1.18. The fixed bands
were fitted for ATS decisions, so their poorer point-error score does not by
itself invalidate their separate decision objective.

### Annual primary RMSE

| Method | 2023 | 2024 | 2025 |
|---|---:|---:|---:|
| Raw v1.18 | 13.1732 | 12.4814 | 12.2020 |
| Market spread | 13.0707 | 12.6051 | 12.2712 |
| Production fixed bands | 13.3821 | 12.5870 | 12.5354 |
| Market + shrunk raw gap | 13.0730 | 12.5770 | 12.2241 |
| Market + isolated model signal | 13.0692 | 12.5892 | 12.2550 |
| Market + split isolated signal | 13.0782 | 12.5929 | 12.2533 |

Shrinkage helps raw v1.18 in 2023 and hurts it in 2024 and 2025.
That instability is a reason to retain the benchmark rather than choose the
current-year winner.

## Uncertainty and fixed decision

Positive gain means the candidate reduces MSE, in squared points per game.
Paired whole weeks are resampled within each season: 10,000 draws, seed
20261017, 54 season-week blocks. The wider 98.333% intervals account for
the three candidates as a sensitivity check; they do not adjust the entire
prior research history, model selection or input-vintage uncertainty.

| Candidate | Comparator | MSE gain | 95% interval | 98.333% interval |
|---|---|---:|---:|---:|
| Market + shrunk raw gap | Raw v1.18 | -0.1026 | [-2.5576, +2.7664] | [-2.9827, +3.5421] |
| Market + shrunk raw gap | Market spread | +0.6004 | [-0.2312, +1.3886] | [-0.4183, +1.5788] |
| Market + isolated model signal | Raw v1.18 | -0.4237 | [-3.1240, +2.6525] | [-3.5797, +3.4754] |
| Market + isolated model signal | Market spread | +0.2794 | [-0.3602, +0.8769] | [-0.4921, +1.0024] |
| Market + split isolated signal | Raw v1.18 | -0.5187 | [-3.1104, +2.3833] | [-3.5815, +3.1411] |
| Market + split isolated signal | Market spread | +0.1843 | [-0.6374, +0.9512] | [-0.8200, +1.1100] |

**Decision: `retain_production_no_candidate_qualifies`.** The frozen
criterion required a positive 98.333% lower bound against both raw and market
MSE before nominating a fresh forward experiment. Every candidate fails.
Failure to resolve improvement does not prove that the true effect is zero.

## What the calibration tests

Let L be market home-margin spread, R the production inverse-probit spread,
and Q the same inverse-probit transform of the no-vig market moneyline.
`gap_anchor` forecasts L + beta(R−L). `signal_anchor` forecasts L + beta(R−Q),
so a pure moneyline/spread conversion discrepancy cannot masquerade as model
information. `split_signal_anchor` assigns different slopes to reinforcing
market-favorite confidence and the other signals, reflecting v1.18’s existing
asymmetric favorite penalty. Each slope is prior-season ridge 200, clipped
to [0,1], with no intercept, parameter search or ROI fitting.

| Forecast season | Prior games | Raw-gap slope | Isolated slope | Reinforcing slope | Other slope |
|---|---:|---:|---:|---:|---:|
| 2023 | 543 | 0.2027 | 0.1611 | 0.0000 | 0.2491 |
| 2024 | 815 | 0.1501 | 0.1456 | 0.0150 | 0.1481 |
| 2025 | 1087 | 0.3612 | 0.2862 | 0.3765 | 0.2516 |
| 2026 | 1359 | 0.4525 | 0.3283 | 0.6356 | 0.2708 |

## ATS diagnostics are a different question

At a positive slope, L + beta(R−L) stays on the same side of L as R.
Therefore the first candidate changes point accuracy but preserves every
raw ATS side here. It cannot fix ATS selection merely by shrinking the gap.
Isolating the model signal can change the selected side. That helps the
exposed 2023–25 ATS result but reverses sharply in 2026.

Flat 1u risk, assumed −110, ties graded against the spread. Exact model-market
equalities skip before push grading. Quotes and capture timestamps are unverified;
no actual-price profitability or forward performance is established. These are
mean-sign diagnostics, not calibrated cover probabilities or EV bets.

| Cohort | Method | Opportunities | W–L–P | Skips | Units | ROI/bet |
|---|---|---:|---:|---:|---:|---:|
| 2023–25 | Raw v1.18 | 816 | 409–388–19 | 0 | -16.18 | -1.98% |
| 2023–25 | Production fixed bands | 816 | 401–363–19 | 33 | +1.55 | +0.20% |
| 2023–25 | Market + shrunk raw gap | 816 | 409–388–19 | 0 | -16.18 | -1.98% |
| 2023–25 | Market + isolated model signal | 816 | 426–371–19 | 0 | +16.27 | +1.99% |
| 2023–25 | Market + split isolated signal | 816 | 352–307–11 | 146 | +13.00 | +1.94% |
| 2026 W1–5 | Raw v1.18 | 79 | 36–37–6 | 0 | -4.27 | -5.41% |
| 2026 W1–5 | Production fixed bands | 79 | 39–31–3 | 6 | +4.45 | +6.10% |
| 2026 W1–5 | Market + shrunk raw gap | 79 | 36–37–6 | 0 | -4.27 | -5.41% |
| 2026 W1–5 | Market + isolated model signal | 79 | 30–43–6 | 0 | -15.73 | -19.91% |
| 2026 W1–5 | Market + split isolated signal | 79 | 30–43–6 | 0 | -15.73 | -19.91% |

The full fixed-band benchmark exactly reproduces **440–394–22, 39 skips,
+6.00u on 856 selections**. No ATS return selects a candidate. The report
focuses inference on the prespecified point-forecast target; these ATS slices
remain descriptive and have no multiplicity-adjusted return claim.

## Reproduction and evidence limits

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m research.continuous_spread \
  --input research/continuous_spread_results/input.csv \
  --board research/continuous_spread_results/board_input.csv \
  --output-dir /tmp/continuous-spread-replay
python -m pytest tests/test_continuous_spread.py -q
```

`input.csv` freezes the needed 1,438 historical forecast rows; 2021–22 supply
warm-up and 895 later games are scored. `board_input.csv` freezes 14 current
Week 6 quotes/probabilities. `per_game.csv`, `fits.json`, `results.json` and
`current_counterfactuals.csv` retain every forecast and comparison. The current
board is a research counterfactual, never a native forward archive.

All six deterministic data artifacts reproduce byte-for-byte in a separate
process using the frozen inputs. Input/code/protocol hashes are in
`provenance.json`; `deterministic_reproduction.json` records the checks.

Historical upstream recipe selection and source-timestamp limitations remain.
This run reuses saved forecasts; it does not rebuild features from raw NFL
availability files. No new independent holdout or prospective edge is claimed.
Raw v1.18 is already close to market point-error performance in the primary
sample. The next meaningful improvement must add or better estimate pregame
margin information, rather than rescale the same signal and select a favorable
retrospective ROI slice. Test any next candidate against both raw and market.

## Validation in this run

* Full repository suite: **717 passed, 1 xfailed**, 149.06 seconds. The expected
  failure and two existing pandas warnings are outside the new module.
* New module: 14 tests cover margin-residual fitting, signal separation, slope
  bounds, missing inputs, invalid inputs, duplicates, season cutoffs, invariance
  to evaluation-label changes, ATS ties/pushes/skips, deterministic week pairing,
  and protected output paths.
* `python sync_notebook.py`: already in sync.
* `python validate_data_files.py`: **43 files OK**.
* Six data artifacts reproduce byte-for-byte in a separate process from frozen
  inputs. Every year-boundary coefficient, primary/current/pooled point metric
  and ATS grade was independently recomputed.
* `git diff` confirms no changes to production model, fixed bands, build,
  notebook, workflows or `data/`. `git diff --check` passes.
