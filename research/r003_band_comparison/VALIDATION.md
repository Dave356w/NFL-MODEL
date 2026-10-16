# R003 band comparison validation

- Full suite: **678 passed, 1 xfailed** (58.66s).
- Six new tests cover band endpoints, break-even inclusion, fixed-side common
  cohorts, push/pass denominators, payouts, projected-value orientation,
  missing means, invalid probabilities and Wilson interval behavior.
- **69 models**, each with the same 816 primary forecast games. Source outcomes,
  spread/total lines and identities agree exactly across all model populations.
- Every model/period/axis partitions games, bet counts and net units exactly.
- Common-plain cohort sizes and observed calibration-side labels agree across
  every model. Probability/spread intersections sum to 816 games per model.
- Frozen plain ATS replay reproduces: 560 main bets, −32.5454545u.
- Independent separate-process run: **eight generated artifacts byte-identical**;
  the explanatory report is manually written from those artifacts.
- Interactive JavaScript syntax passes Node checks; a DOM smoke test exercises
  headline/all-model views and period, band and metric filters, verifying 9/69
  model rows and expected band columns. This is not a visual browser inspection.
- All **192** original protected hashes and all declared input/source hashes
  remain unchanged. No model is refitted or threshold chosen from these slices.

This is a descriptive, exposed-history comparison. Reproducibility and favorable
band returns do not establish predictive validation or an executable ATS edge.
