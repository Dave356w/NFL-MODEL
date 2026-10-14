# Test 36 protocol: one-at-a-time sweep of the model's shrinkage settings

Research only; production, frozen recipes and the forward ledger are unchanged. Owner go-ahead
2026-10-14 (knobs and basis chosen by the owner). This file is committed and pushed before any arm
below has been built or scored.

## Question

Four shrinkage settings have never been tested on the current model (v1.16 core, which v1.18 wraps
with the favorite penalty):

| Knob | `nfl_model` setting | Production | Alternatives | Where it acts |
|---|---|---:|---|---|
| QB prior | `QB_PRIOR_DROPBACKS` | 150 | 75, 300, 600 | QB efficiency shrinkage toward backup level (`availability_table`) |
| Profile pseudo-games | `PRIOR_EQUIVALENT_GAMES` | 4 | 2, 8, 16 | every team profile's shrinkage toward the league (`lagged_features`) |
| Offseason retention | `OFFSEASON_RETENTION` | 0.5 | 0.25, 0.75 | weight kept by older-season games in team and QB profiles |
| Fit half-life | `FIT_HALF_LIFE_SEASONS` | 2 | 1, 4 | decay on old labeled games in the weekly coefficient fit |

These settings are out of scope because they were settled earlier: ridge (nested-selected every
season), team half-life (Tests 8–9), context-hinge ridge (context shrinkage and support cap tests),
and the favorite penalty (forward-gated).

## Exposure, disclosed in advance

* 2023–25 have been used in dozens of earlier tests. Test 3 (v1.9, a different model) found that
  QB prior 300 improved 2023–25 log loss by +0.0008 (about 2.7 SE), so that direction is already
  known on the selection seasons.
* 2017–20 were scored with v1.16 production three times (out-of-sample test, Test 32, Test 34).
  **None of these four settings has ever been varied on 2017–20.**
* The profile-robustness test (passing profiles only, +4 and +12 pseudo-games) was unresolved.

## Arms

One-at-a-time: production plus ten arms, each changing one setting to one alternative value. No
other value and no joint grid is tried. Each arm rebuilds every feature its setting touches from
raw inputs, including the prior-week normalization references. It then refits the fixed v1.16
recipe (`LEGACY_PRODUCT_RECIPE`: h8 main profiles, h16 pass contexts, ridge 0.1, market logit offset)
before every evaluation week, using only strictly earlier games. Recipe selection is not rerun.

Raw inputs are nflverse schedules, box scores, QB rows and availability for 2013–2025, downloaded
once and pickled. Each window uses only its own input seasons.

## Stage 1: selection, 2023–25

Window: input seasons 2019–2025, evaluation weeks 2021–2025 (2021–22 are used only for selection).
The production arm must reproduce `production_adoption_results/historical_reproduction.csv` to
1e-7; otherwise the run stops.

* **Annual nested selection (reported):** for each held-out season Y ∈ {2023, 2024, 2025} and each
  knob, the value (production included) with the lowest log loss on evaluation seasons 2021…Y−1
  forecasts season Y. This gives one honest selected arm per knob on 2023–25.
* **Chosen value (carried to stage 2):** for each knob, the value with the lowest log loss over all
  of 2021–2025. Exact ties go to production.

## Stage 2: confirmation, 2017–20 (scored once)

Window: input seasons 2013–2020, evaluation weeks 2017–2020 (training from 2015). The production arm
must reproduce `out_of_sample_results/predictions.csv` (production) to 1e-7.

Every knob whose chosen value is not production is scored on 2017–20 against production. The
**primary statistic** is the paired log-loss gain (production minus arm; positive = arm better),
with a paired week-cluster bootstrap interval at 1 − 0.05/k, where k is the number of confirmed
knobs (k ≤ 4, so at least 98.75%).

**Verdict per knob:**
* **Candidate for a new `REVISION`** (owner decides) if the gain is positive and its interval
  excludes zero.
* **Keep production** if production is chosen, or if the gain is negative with an interval that
  excludes zero.
* **Unresolved, keep production** otherwise. A crossing interval does not show the settings are
  equal.

## Reported, not gating

For both stages, every arm on the same rows:
* **Flat 1u ROI (goal metric):** W-L-P, units, ROI ± SE, market-correct null, the same-row market
  favorite, and the ROI difference vs production with interval and side flips. ROI is reported,
  not used for selection.
* Log loss and Brier, by season.
* The same metrics after the v1.18 favorite penalty (λ = 0.2), since v1.18 is production.
* If two or more knobs are confirmed: one combined arm with every chosen value, on 2017–20,
  descriptive only.

## Falsification

The Test 3 lead (more QB-prior shrinkage helps) is falsified for practical purposes if QB prior is
chosen at 300 or 600 and loses to production on 2017–20 with an interval that excludes zero.

## Outputs

`research/shrinkage_sweep.py` writes `research/shrinkage_sweep_results/` (REPORT.md, results.json,
predictions, provenance with input hashes). Unit tests: `tests/test_shrinkage_sweep.py`.
