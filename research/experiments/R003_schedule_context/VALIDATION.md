# R003-SC1 validation

- Full repository suite: **644 passed, 1 xfailed** (89.43 seconds).
- New schedule-context coverage: 15 tests, including sparse/unknown fallback,
  market-relevant support, shrinkage, timezone/DST handling, neutral games,
  rest, feature alignment and earlier-season selection with a plain option.
- Plain predictions and scores reproduce MC2 with maximum absolute error
  **3.55e-15**.
- Independent separate-process reproduction: exact byte equality for all
  12 checked feature, prediction, selection and result artifacts; see
  `deterministic_reproduction.json`.
- **11,966** individual/joint fallback rows have exactly equal home-win,
  cover-win and over-win probabilities to plain. Additive and selected rows
  are excluded from this check because they can combine non-fallback arms.
- All **192** original R000–R003 experiment and production-data files in the
  preservation snapshot remain unchanged. Baseline input hashes also match;
  see `functional_verification.json`.
- Notebook synchronization and 43 data-file checks pass. `git diff --check`
  passes.

The integrity checks pass; the performance advancement gates do not. The
historical sample was already exposed before this experiment and is not an
independent forward test. Sparse TNF/MNF contexts often revert to plain, so
these results cannot establish that the underlying schedule effects are zero.
No production configuration was changed.
