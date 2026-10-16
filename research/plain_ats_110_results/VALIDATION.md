# R003 plain ATS −110 scenario validation

- **37 focused tests pass**, including four new decision/settlement tests and
  existing spread-EV coverage.
- New tests cover exact break-even/pass, both selection directions,
  conditional cover probability with pushes, full-push fallback, signed lines,
  half points and malformed probabilities.
- Predictions are read from frozen plain direct_ref_h2_t3_p0 forecasts. No
  model or probability is refitted; the policy is a separate research scenario.
- Main population: 816 games = 560 bets + 256 passes; 560 = 270 wins + 278
  losses + 12 pushes. Net units = 270*(10/11)−278 = −32.5454545.
- No odds, thresholds, minimum edges or subgroups are searched using ROI.
- Both −110 prices are user-specified assumptions for historical replay, not
  independently archived historical quotes. Return uncertainty is conditional
  on the frozen forecasts and scenario prices.
- Original protected-file hashes and forward ledger remain unchanged;
  numerical/report artifacts reproduce exactly on a second run.
