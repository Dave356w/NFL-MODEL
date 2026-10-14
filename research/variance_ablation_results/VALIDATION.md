# Validation — 2026-10-14

* Full suite: **460 passed, 1 expected failure**; two existing pandas concatenation warnings.
* Eight new regression cases cover frozen-profile reconstruction, shared game multipliers,
  same/future-game exclusion, point-in-time reliability, nonconstant shrinkage,
  earlier-year pruning/simplicity/no-benefit gates, group-removal invariance,
  source-hash refusal, compressed export integrity and stable descriptive calibration.
* Strict replay: all 12 generated files agree within 1e-8, with exact
  row/schema/integer/text checks. This retained validation note is not generated.
* Reconstructed h8 main inputs match frozen profiles within 4.97e-14;
  missingness agrees. Every evaluated main input has finite bootstrap variance.
* Production matches archived forecasts within 2.30e-13 and an independent
  fitting implementation within 2.22e-16.
* All 67,056 feature-reliability records, weekly coefficient-fit cutoffs, and
  annual pruning selections were checked for strictly earlier reference data.
* All compressed artifacts were decompressed and validated. Large audit files
  are validated before atomic publication. Finite-difference calibration was
  replaced with an analytic Newton solve for platform-stable diagnostics;
  forecast probabilities, selection rules and score results are unchanged.
* `python validate_data_files.py`: 37 files OK. Notebook already synchronized.
* No production source, recipe/config signature, live build workflow, native
  forward ledger, `data/` or `public/` file changed.

This is exposed historical development, not a native forward test. The fixed
bootstrap measures conditional sampling sensitivity, not isolated coaching skill.
Shared game multipliers preserve common-game dependence; shrinkage uses marginal
per-input variances rather than a joint covariance optimizer. Availability and
passing contexts receive no invented uncertainty estimates.

Both challengers reduced model-minus-market log-odds dispersion on 2023-25:
reliability -20.78%, chronological pruning -13.35%. Neither improved forecasting
consistently across the three bases; all primary paired score intervals include
zero. The report recommends no production change.
