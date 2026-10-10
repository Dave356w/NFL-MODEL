# Prospective qualification contract

The nomination in `qualification_results/nominated_candidate.json` is a
development-selected candidate, not a qualified production model. This document
specifies the next evidence stage; live capture is not implemented by the
backtest PR.

Freeze and hash the nominated recipe before recording any eligible future
prediction. Its numeric coefficients may refit before each week under its fixed
prior-week training rule; feature definitions, normalization, penalties, priors,
selection policy and comparison rules may not change within the experiment.
A changed recipe starts a distinct experiment and cannot borrow prior results.

Record the first qualifying production lock event before kickoff, after the
existing final-status injury gate or its six-hour fallback. Require valid
moneylines for both sides. The offset uses that snapshot's no-vig moneyline,
and ROI is graded at the same snapshot's side price. Save prediction, exact
inputs, quote/capture time, fitting cutoff and code/config hashes once per game.
Do not backfill missed captures or replace an earlier prediction with a later
one. Record all input/price exclusions before seeing the outcome.

The policy is one hypothetical flat unit on the candidate's favored side;
there is no discretion, value threshold or changing stake rule. This specifies
forecast tracking, not wagering execution. Record market-only and standalone
production controls. Use the same decided, priced rows for comparisons; market
pick'ems are excluded from the primary favorite comparison, and ties push in
ROI while being excluded from binary proper scores.

The single formal checkpoint is 1,000 unique eligible graded future games.
Interim results are descriptive and cannot declare success. At the checkpoint,
report paired week-cluster bootstrap 95% intervals for net ROI, units difference
versus the same-row market favorite, and units minus the chosen-side
market-correct null. Reliable profitability support requires all three lower
bounds above zero. Failure to clear the bounds is unresolved, not automatically
evidence that no effect exists; the sample does not guarantee adequate power.

Log loss and Brier versus the captured no-vig market are supporting evidence;
proper-score improvement alone does not establish profitability. Report
season consistency, W–L–P, units, exclusions and price bands. Diagnostic slices
cannot be used to revise the policy retrospectively. Exploratory shadow
candidates must be separately labeled and cannot replace the primary candidate
after outcomes are seen. Historical development and other revisions are never
pooled with this future sample.
