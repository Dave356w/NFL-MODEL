# Context support shrinkage protocol

Research only; production v1.16, frozen recipes and snapshots are unchanged.
Written before candidate backtests. Trigger: SF@SEA's large PN contribution.

Keep production's h8 main profiles, h16 pass profiles, market logit offset,
prior-week feature references, main ridge 0.1 and context ridge 0.1.
Refit all coefficients jointly before each evaluation week.

For each of the four 1 SD hinge contexts, increase its ridge penalty to
`0.1 * (1 + K / max(n_eff, 1))`. Product and main-effect penalties stay fixed.
Compute support only from eligible earlier training games, with production's
two-season coefficient-fitting decay. Active support uses Kish effective size
of weights on nonzero context rows. Information support uses Kish effective
size of `weight * raw_context**2`, detecting concentration in a few tail games.
Neither method uses current matchup inputs or evaluation outcomes for support.

Fixed candidates: active K=10, 30, 100 and information K=30. Primary candidate
is active K=30; others are sensitivity analyses. Also evaluate an annual
candidate selection using log loss on earlier evaluation seasons only;
include unmodified production among the options. Evaluate 2023–2025; use
2021–2022 for the first annual choice. Profiles and coefficients refit weekly.
Include ties as pushes in ROI; exclude them from binary proper scores.

Report same-row flat 1u moneyline ROI, units, standard error, market-null ROI,
market favorite baseline, log loss, Brier, annual results, and paired
week-cluster bootstrap intervals. Also report the union of active hinge games,
PN-active games and model confidence >=90%; slices are diagnostics and not
used for selection. Use 98.75% intervals for four fixed candidate comparisons
to production (Bonferroni within each metric), plus 95% for annual selection.

Reproduce zero-shrinkage production math and compare historical probabilities
to committed v1.16 reproductions. Audit strictly prior training and reference
weeks. Replay current locked inputs at their archived moneylines, refitting
candidate coefficients from prior games; label these counterfactuals.

History is already exposed development data. These experiments cannot provide
native forward confirmation or establish reliable profit. No confidence cap,
post-hoc probability multiplier, or production adoption is part of this task.
