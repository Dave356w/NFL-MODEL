# R003-AC1 validation

- Full suite on the final implementation: **672 passed, 1 xfailed** (58.23s).
- Nine new calibration cases test analytic gradients across all three families,
  planted shrinkage recovery, stronger ridge, prior-week/window enforcement,
  target-outcome independence, minimum-data fallback, push exclusion, same-side
  stability, source-weight coherence and earlier-loss-only model selection.
- Full independent rerun produces **15 byte-identical artifacts**, including
  source OOF records, fits, predictions, decisions, annual selections, metrics,
  comparisons, report and descriptive review outputs.
- **512** earlier 2015–16 plain OOF records reconstructed under unchanged
  prior-week base-model contracts. **21,646** probability rows saved.
- **1,956** calibration windows: 1,950 successful fits, six minimum-data
  fallbacks. All calibration and annual-choice cutoffs strictly precede targets.
- The prior raw ATS scenario reproduces (560 bets, −32.5454545u in 2023–25).
- Main calibrated atom distributions match target cover probabilities within
  1e-12 and retain raw push mass within 1e-12. No unsupported atom groups occur.
- All **192** original protected file hashes remain unchanged; all declared
  input/source hashes still match. Production and native forward ledger untouched.

The initial evaluation aborted on numerical line-search failure. Increasing
L-BFGS-B maxls from 20 to 100 resolves it at unchanged coefficients/objective
to numerical precision; the protocol and registration history document this
computational amendment. No window, candidate or loss is discarded.

Integrity passes; ATS-edge advancement gates fail. The selected model passes
on every main-period bet. Undefined no-bet ROI is not counted as positive
evidence. Independent reproduction does not supply fresh predictive validation.
