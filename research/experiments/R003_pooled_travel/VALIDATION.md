# R003-PT1 validation

- Full suite: **654 passed, 1 xfailed** (58.41 seconds).
- Ten new tests cover analytic gradients, planted signal recovery, regularization,
  exact no-shape fallback, unknown/sparse fallback, positive normalized weights,
  unchanged paired-score atoms, target-outcome independence, source-label
  independence at prediction, earlier-season selection, alignment and cutoffs.
- **788** pooled weekly fits converge; all use strictly earlier weeks.
- Plain reproduction maximum absolute error: **3.552713678800501e-15**.
- **184** challenger fallback rows exactly equal plain for conditional home-win,
  cover-win and over-win probabilities and primary CRPS.
- Independent separate-process run reproduces **15 artifacts byte for byte**,
  including predictions, features, coefficients, selections, support reviews
  and reports; see `deterministic_reproduction.json`.
- All **192** original protected experiment/production-data hashes remain
  unchanged; all new-run input/source hashes still match.
- Notebook already synchronized; **43 data files OK**; `git diff --check` passes.

The technical integrity checks pass. The performance advancement gates fail.
Independent reproduction is not independent predictive validation: these
historical outcomes were exposed and motivated this family. No production or
append-only ledger change was made.
