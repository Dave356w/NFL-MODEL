# Test 37 protocol: where the model's wrong picks cluster, by input and context

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner request 2026-10-14. This file and the forward rules (H7, H8 in
[`PREREGISTRATION.md`](PREREGISTRATION.md)) are committed and pushed before any feature-level
residual below has been computed on any basis.

## Question

Do the model's wrong picks cluster on particular inputs within particular game contexts? If a
trend is found on earlier seasons, does it continue on later held-out seasons, and then forward?

"Wrong" is measured against the model's own probability, not raw wins and losses. About 94% of
the model's bets are the market favorite, so raw losses mostly mark upsets the price already
expected. The residual is `r = y − p`, with `y` the home result (1/0) and `p` production v1.18's
home win probability. An input `x` (home minus away) shows a **trend** in context `c` when
`Σ r·(x − mean_c x)` is far from zero: where `x` is high, the home team won more (or less) often
than the model said, so the model under-weights (over-weights) `x` in that context. Wrong picks
are the binary face of the same residual; the report also shows them directly (below).

## Exposure, disclosed in advance

* The three total bands were chosen on 2026-10-14 after aggregate v1.16 slices of 2017–20 and
  2023–25 were seen (departure slope and ROI by total; the H7 source).
* 2017–20 and 2023–25 have been scored with v1.16 several times (out-of-sample test, Tests 32–36).
  2021–22 are recipe-selection seasons. v1.16's design was chosen on 2023–25 comparisons.
* The author has seen the 1 SD hinge terms' role in SF@SEA and how many 2023–25 underdog picks
  depend on them (5 of 43).
* No residual-by-input-and-context scan has been computed for v1.16 or v1.18 on any basis. Test 10
  (v1.9) looked at coefficient signs and Test 15 at market weights, not at residuals by context.

## Bases, never pooled

1. **Discovery: 2017–2022** regular seasons, prior-week walk-forward fits (exposed history;
   hypothesis generation only). 2017–20: the v1.16 `production` arm of
   `out_of_sample_results/predictions.csv` with inputs from `frozen_features_2013_2020.csv.gz`.
   2021–22: v1.16 refit before every week from `shrinkage_results/frozen_training_features.csv.gz`;
   after the penalty it must reproduce `data/latest/retro_ledger.csv` (v1.18) to 1e-9.
2. **Confirmation: 2023–25** held-out reproduction (`restore_v116_results/historical_reproduction.csv`).
   Exposed development data, but the trends are chosen on basis 1 only.
3. **Diagnostic: 2026 weeks 1–5**, refit from the Test 36 pack (frozen at its build). A
   current-season walk-forward; reported, never used for selection or confirmation.
4. **Forward:** native v1.18 snapshots under H8 (`PREREGISTRATION.md`).

v1.18 is `favorite_penalized_wp(v1.16, q, 0.2)`, exactly what `apply_fit` does. v1.16 results are
reported as a secondary grid and never used for selection. Totals for history are the nflverse
schedule `total_line`, frozen once in `residual_trends_inputs/schedule_totals.csv` (download time
and SHA-256 in its provenance). Binary games only enter the residual statistics; ties push in ROI.

## Grid, fixed

* **Contexts (4):** all games; total ≤ 41; 41.5 ≤ total ≤ 47; total ≥ 47.5.
* **Inputs (30):** the 28 non-site production inputs (14 box-score rates, `qb_delta`, the six unit
  absences, largest lead and deficit, the pass product and the four 1 SD hinges), the market
  log-odds `logit(q)`, and production's departure `logit(p) − logit(q)`.

120 cells per basis.

## Statistic

Within context `c`, `x̃ = x − mean_c(x)`. `S = Σ r·x̃`, cluster-robust variance
`V = Σ_weeks (Σ_{i in week} r_i·x̃_i)²`, and `z = S / √V` (clusters are season-weeks, because each
week shares one fit). The effect size is one Newton step, `γ = S / Σ p(1−p)·x̃²`, reported per SD of
`x̃`: the log-odds per SD the data would add to the model in that context.

**Wrong-pick view** (descriptive). Sign the input toward the model's side (`x` if it backs home,
`−x` if away). Within the context, split at the discovery basis's tercile cut points of that
signed input. For each third: graded bets, the model side's wins minus its expected wins under
`p`, flat 1u units, and the same-row favorite's units.

## Selection on discovery

Candidates are cells with |z_D| ≥ 2.0, ranked by |z_D|, at most K = 10. With no real effect about
six of 120 cells pass by chance (fewer independent ones, since contexts nest and inputs
correlate). If no cell passes, the test ends with no trend.

## Confirmation on 2023–25

`z_C* = sign(z_D)·z_C`. **Confirmed**: z_C* ≥ Φ⁻¹(1 − 0.05/K), one-sided and Bonferroni-adjusted
over the K candidates. **Direction holds**: 0 < z_C* below that bar. **Not replicated**: z_C* ≤ 0.
A direction that holds is not confirmation.

## Forward carry, mechanical

H8's forward set is every candidate with z_C* > 0, at most five, ranked by z_C* (ties by |z_D|).
Nothing is re-selected after the confirmation result is seen. The forward rules are in
`PREREGISTRATION.md` (H8); `python research/residual_trends.py --forward` grades them from the
native ledger.

## Report

Per basis: the full grid with z and γ; the candidates with discovery and confirmation z, their
verdicts and wrong-pick views; flat 1u ROI per context (W-L-P, units, ROI ± SE, market-correct
null, same-row favorite); the v1.16 grid; and the 2026 diagnostic.

**Reproduction gates.** 2021–22 refit vs `retro_ledger.csv` within 1e-9; 2017–20 and 2023–25 bet
counts and units match the published totals (1,017 bets −0.42u; 812 bets +29.06u).

**What a result means.** A confirmed trend says the model mis-weighted an input in a context on
past seasons. It changes nothing by itself. A context interaction would be a new `REVISION`, the
owner's decision, and should wait for forward evidence.

Run: `python research/residual_trends.py` (history) and `--forward` (native ledger).

## Addendum 2026-10-14: replication on 2015–16, never scored (owner request)

The owner asked to test the trends on data already available instead of waiting for forward games.
This addendum is committed and pushed before any 2013–16 forecast has been compared with an outcome.
It adds a historical replication. It does not replace or change H7, H8 or their forward rules.

*Data.* The 2013–16 regular seasons in `out_of_sample_results/frozen_features_2013_2020.csv.gz`.
Until now they served only as training history (the 2017–20 out-of-sample test and Test 36's
confirmation stage). No test has scored a model forecast for them. Before writing this, only
non-outcome facts were checked:
* every 2014–16 game is priced and ready (2013: 191 of 256 ready);
* the first week with `MIN_TRAIN_GAMES` earlier complete rows is 2013 week 16, 2014 week 1 (190
  rows), 2015 week 1 (445) and 2016 week 1 (701);
* refitting 2017–20 from this pack reproduces `predictions.csv` to 1.1e-16;
* 2015–16 has 512 games: 63 with totals ≤ 41, 301 in 41.5–47 and 148 at ≥ 47.5.

*Basis.* **Primary: 2015–16**, with v1.16 refit before every week from earlier pack rows only
(training from 2013) and v1.18 via the favorite penalty. **Sensitivity: 2014** (256 games, trained
on 190 rows of 2013). It is reported separately and never used for a verdict, because thin
training inflates departures and would bias the departure trends toward replicating. 2015–16 is
a basis of its own, never pooled with 2017–22 or 2023–25. Totals for 2013–16 come from the frozen
`schedule_totals.csv`, extended from the same download (provenance updated; the 2017–26 rows are
unchanged).

*Tested; nothing is re-selected.* The four H8 trends (Test 37's forward set) and H7, with the same
statistics, cut points and code paths as the main test.
* **Trends**, `z* = sign(z_discovery)·z`: **replicated** if z* ≥ Φ⁻¹(1 − 0.05/4) = 2.24;
  **direction holds** if 0 < z* < 2.24; **reversed** if z* ≤ 0.
* **H7** (v1.16 departures, binary rows): **supported** if Δ ≥ 2 SE; **contradicted** if Δ ≤ 0;
  otherwise **unresolved**.
* Also reported: the wrong-pick views at the 2017–22 cut points, and flat 1u ROI by context with
  the null and the same-row favorite.

*Power, stated now.* If a trend's true effect equalled its discovery estimate (which selection
inflates), its expected z* on 2015–16 would be about |z_D|·√(n/n_D): 1.7 for all games ×
departure, 1.7 for total 41.5–47 × departure, 1.4 for total ≥ 47.5 × offensive INT % and 1.0
for total ≤ 41 × departure. H7's expected z is about 0.7 (SE near 1.3 with 148 and 63 band
games). So "replicated" needs luck even if a trend is real. "Direction holds" is the likely best
case, and "reversed" counts against a trend. This is a backward replication: rules, play styles
and pre-2017 data quality differ. It cannot replace the forward test.

Run: `python research/residual_trends.py --replicate`.
