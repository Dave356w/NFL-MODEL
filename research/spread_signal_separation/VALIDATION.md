# Market-signal separation validation

- Full suite: **684 passed, 1 xfailed** (58.25s).
- Six new cases cover analytic gradients, planted market/margin relationship,
  proper spread sign, future/window rejection, target-outcome independence,
  exact price decomposition and push/empty denominators, and exact endpoint loss.
- **129** prior-week fit windows and **1,950** unique forecast games. All fit
  cutoffs strictly precede their target week. Optimizer failure aborts evaluation.
- Main matched populations: 816 margin observations, 815 decisive game-winner
  outcomes and 797 decisive ATS outcomes. Baseline and model score populations
  agree; paired counts exclude unavailable comparator probabilities.
- Raw ATS reproduces 560 bets and −32.5454545u. Every payout decomposition
  exactly satisfies units = wins−losses−wins/11, including pushes and passes.
- Independent separate-process repeat: **nine data artifacts byte-identical**.
  Provenance is identical after normalizing the copied PLAN.md's directory path;
  the plan contents and all input/source hashes match.
- All **192** original protected experiment/production-data files remain
  unchanged. No deployed model or append-only ledger change.

Historical data are exposed. Benchmark prediction skill and exact reproducibility
do not establish an incremental trading edge or certify historical price timing.
