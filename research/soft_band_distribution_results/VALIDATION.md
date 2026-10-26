# SB1 validation

- Full repository suite: 849 passed, one expected failure, 51 subtests passed.
- Dedicated SB1 suite: 17 passed, including after the boundary-table addition.
- Notebook synchronization and committed-data validation passed.
- Deterministic replay: generated JSON/CSV/Markdown agree within absolute 1e-8;
  integer counts, text, schema, missingness and game identities agree exactly.
- A separate implementation reconstructed each forecast directly from the
  frozen source samples, using interpolation and empirical tail counts rather
  than the SB1 PMF/event functions: all 922 forecasts matched, maximum probability
  difference 3.33e-16. All 3,648 soft/hard EV settlements in both price scenarios
  matched independently, as did main-period conditional cover log losses.
- Original data/, v1.18 probability engine, median mapping, timed lock machinery
  and public-site builder have no changes. No snapshots or live forecasts added.

Behavioral coverage includes strict prior-season training, own-season label
poisoning, convex neighboring weights, endpoint clamping, continuity at all
three old cutoffs, preservation of observed margin atoms, away/home orientation,
integer and half-point settlement, side-specific American odds and EV thresholds,
price/forecast separation, missing paired prices, all-push cohorts, corrupt fit
hashes/counts, invalid identities and production-output-path rejection.

The two primary score contrasts fail the fixed advancement gate. These tests
establish implementation correctness and reproducibility, not predictive or
financial superiority. Every historical period remains exposed development;
archived schedule/closing prices do not certify lock-time execution.
