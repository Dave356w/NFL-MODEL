# Validation (2026-10-14)

* Full pytest suite: 459 passed, 1 expected failure; two existing pandas concatenation warnings.
* New replacement and existing YBC tests: 13 passed.
* Strict replay: 10 files (including this retained validation note) agree within 1e-8; integer, text, row identity and schema checks exact.
* Data validation: 37 files OK. Generated notebook already synchronized.
* Every evaluation and eligible training row has finite offensive and defensive YBC.
* Production is checked against both an independent `fit_composite` implementation
  (maximum difference 2.22e-16) and archived probabilities (maximum 9.15e-11).
* Every fit uses only earlier weeks; the fit audit records weekly cutoffs and coefficients.
* No production model, configuration signature, shadow lock, native ledger or generated site data changed.

Results do not support adopting the replacement. On 2023-25, replacement returns
+24.36u (3.00% +/- 2.52 pp SE) versus +29.06u (3.58% +/- 2.52 pp) for production
and the no-peaks control. The paired difference is -4.70u; uncertainty includes
zero. The earlier 2021-22 basis also loses units versus both controls. All history
was exposed; 2026 is a separate reconstruction diagnostic.

## Receiving follow-up

Inspected the official nflverse 2025 weekly PFR receiving release:
`https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_rec_2025.parquet`.
SHA-256 `b4fcae8322c17b021283cba924a35f6452b831a2959c4adb2c357866b8975b97`.
Its schema has identifiers, broken tackles, drops, interceptions and receiver rating;
it contains no yards-before-contact field. The season receiving release has YBC/YAC
columns, but annual season totals cannot be substituted into a weekly pregame model.
No receiving proxy or season-final receiving totals were used in this experiment.
