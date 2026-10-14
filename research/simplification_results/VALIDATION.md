# Validation

Run locally on 2026-10-14, Python 3.12, one BLAS thread for research/tests.

* `python sync_notebook.py`: generated notebook synchronized.
* `python validate_data_files.py`: 37 files OK.
* `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python -m pytest tests/ -q`:
  452 passed, 1 expected failure. Two existing pandas concatenation warnings.
* `python research/simplification.py`: all three challengers executed on all
  four stated bases. Baseline reproduction errors <= 6.94e-16. No arm passed
  the predefined historical screen; no production adoption.
* `python research/profile_runtime.py`: every retained column bitwise equal;
  final forecasts bitwise equal for 2014 weeks 1, 8, 17. Profile generation
  12.04s full vs 5.90s compact in the clean repeat (2.04x). Single-run timing,
  not end-to-end build speed. Availability omitted identically for this benchmark.
* Twelve new regression cases cover arm definitions, weekly cutoff rejection,
  removed-input invariance, coverage rejection, protected research destinations,
  profile equality, skipped opponent adjustment, compact cache reuse, and final
  contribution reconciliation for both market favorites and disagreements.
* Production configuration signature remains
  `73636f306d54de2c12a0d8ba394f0aecae9d58d2cd9aa415a87c4b22bca58a20`.
  Research execution verified the forward ledger's SHA-256 was unchanged.
  No tracked `data/` or `public/` file changed; live build workflow unchanged.

The faster mode is opt-in via `NFL_PROFILE_MODE=production`; default full
exports remain available. No live upstream rebuild or deployment was run.
Historical challenger results use frozen prices with unknown capture times,
and every historical period was exposed before this study.
