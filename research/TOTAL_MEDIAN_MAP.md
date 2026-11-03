# Test 50 protocol: a total-conditioned median map

Research only. Production v1.18, the median map (`fixed_bands.py`, `median-mov-ats-2026-10-17-v1`),
the lock policy (`median-mov-ats-t60-favtie-2026-10-19-v2`), `data/` and the ledgers are unchanged.
Owner request 2026-11-03 ("test total-conditioned median map"). This protocol is committed and pushed
before any total-conditioned magnitude is fitted or scored.

## Question

The production map turns the model's probability-derived spread into one of four magnitudes: the
prior-season median margin, signed toward the model's pick, within each |spread| band (0–3, 3–7,
7–10, 10+). Margins spread out as the expected total rises, and low totals put more mass on 3. Would
magnitudes fitted separately for low- and high-total games describe outcomes better?

**Disclosed exposure.** The idea came from an exploratory market-only analysis on 2026-11-03 (line ×
total cross-tab and walk-forward distribution-mass rules, 2006–2026), which covers these seasons. That
analysis found no market-only ATS guideline. Every basis below is already exposed; this is development
evidence, not forward confirmation.

## Arms

All arms keep production's bands, its fit rule (strictly earlier seasons, at least two seasons and
300 games, at least 30 games per band, ties count as zero, exact-zero spreads excluded), its sign
convention, and its selection rule (`fixed_bands.pick`: zero edge takes the market favorite; a pick'em
line with a zero mapped spread skips).

* **M, production (comparator):** `fixed_bands.fit` / `fixed_bands.apply`.
* **T2, primary:** the same median, fitted per band × total half. The split is the median
  `total_line` of the training rows (a total equal to the split counts as low). A cell with fewer than
  30 training games uses M's magnitude for that band. If M cannot fit a season, neither can T2.
* **T3, descriptive only:** the same with training-row total terciles (cutoffs at the 1/3 and 2/3
  quantiles, numpy linear) and the same fallback.

## Bases (never pooled for the decision)

* **R, production replay.** `data/latest/fixed_band_ledger.csv` (frozen copy of the needed columns
  committed with its SHA-256): the probability-derived `model_spread`, the schedule `spread_line` and
  `result`, 2021–2026. Training starts in 2021, as production. **Primary seasons 2023–2025.** These
  rows are "backtest (recipe chosen on these seasons)" and the map was adopted with them in view.
* **O, out-of-sample reconstruction.** `research/out_of_sample_results/predictions.csv`
  (`production` column → `nfl_model.implied_spread`), 2017–2020, trained only within this basis, so
  scored seasons are 2019–2020.
* **Diagnostic:** 2026 to date on R (current-season walk-forward).
* **Totals:** nflverse `games.csv` `total_line` (capture time unknown, like `spread_line`), frozen for
  every game in R and O with the source SHA-256.

Fidelity check before any score: M on R must reproduce the published `fixed_band_spread` exactly and
the 2023–26 replay record (489-409-25, +35.5u).

## Metrics

* **Primary (decides): absolute-error gain** of the mapped spread against the final home margin,
  production minus arm, per game (positive = arm better). A median is the minimizer of expected
  absolute error, so this is the score consistent with how the map is fitted. 95% intervals from a
  season-week cluster bootstrap (2,000 draws, seed 20261103).
* **Goal metric, reported and never used to decide or tune:** flat 1u ATS at −110 against the
  schedule spread. W-L-P, skips, units, ROI ± SE (pushes in the denominator), cover rate excluding
  pushes, n, break-even 52.4%, and same-row always-favorite, always-home and line-only-map
  baselines. Also paired units arm minus M (week-cluster SE), side flips and the record on flipped
  games.
* **Descriptive:** fitted magnitudes per season and cell, fallback counts, results by total half.

## Decision rule (T2 only)

* **Supported for a forward shadow:** the absolute-error gain is > 0 on both R (2023–25) and O
  (2019–20), and its 95% interval excludes zero on at least one.
* **Not supported:** the gain is ≤ 0 on either basis.
* Otherwise **unresolved**.

"Supported" changes nothing by itself. A forward shadow is the only clean test: the ATS locks already
save `raw_spread` and `market_spread`, and `data/h5_totals.jsonl` records the nflverse total pregame for
each locked game, so it needs no new capture. Resolving an ATS difference of the replay's size takes
on the order of 1,400+ locks (2026-11-03 analysis). Adoption would be a new ATS policy version and the
owner's decision.

## Outputs

Script `research/total_median_map.py`; tests `tests/test_total_median_map.py`; frozen inputs
`research/total_median_map_inputs/`; results `research/total_median_map_results/` (REPORT.md).

Run: `python research/total_median_map.py --freeze GAMES_CSV` (freeze inputs; needs the nflverse
file), then `python research/total_median_map.py` (fidelity check and scores; no network).
