# Backup and replacement QB margin residual fit

Owner request 2026-11-13. Research only; do not change production penalties.

Outcome is actual home margin minus projected home margin. For a backup team,
flip the sign when it is away, so negative means its team underperformed.
Fit raw model margins as the primary projection; report the production weekly
mapped margin and market line as separate comparators. Never equate realized
QB net yards/dropback with the team's margin residual.

## Cohorts fixed before fitting

* Strict chart backup: the projected QB ranks below QB1 on the latest timestamped
  chart at least 24 hours before kickoff, no older than seven days. Only 2025 has
  usable prior-season timestamped charts. Historical projections are replay,
  not saved live locks.
* Longer-history replacement proxy: week >=3, projected QB differs from the
  incumbent with the most strictly prior starts this season (ties use latest
  start), incumbent has >=2 starts and remains on the team's latest earlier
  roster at QB. This avoids treating offseason transfers as backups. It still
  includes benchings and misses long-running backups who became incumbents.
* Match projected and actual first QB-position passer IDs from play order separately. Primary
  deployable regression uses projected flags, without filtering on eventual
  actual starter. Correct-starter and wrong-starter subsets are diagnostics.
* A Questionable blend or ambiguous name is unresolved. Exclude unresolved
  pregame classifications from fitting; report coverage rather than fabricate.

## Model and evaluation

Use frozen historical v1.22 ten-term model replays for 2021–2025. Earlier model
features were reconstructed under v1.22, not rerun under the v1.23 label repair.
Fit at the game level (no duplicated outcomes when both teams have backups):

    actual_margin - raw_model_margin = intercept + beta*(home_flag-away_flag)

Negative beta means an additional replacement-team downgrade. Fit separate
raw/mapped/market targets. Primary beta is the replacement proxy; the strict
chart fit is descriptive 2025-only and cannot supply a prior-season test.

Evaluate 2023, 2024, 2025 with coefficients fitted only to strictly earlier
seasons (2021 onward). A correction changes the home projection by intercept +
beta*x. Also compare intercept-only correction, so a global model bias cannot
masquerade as a backup benefit. Use paired squared-error gain on all eligible
and replacement-involved games, MAE, signed residual, same-game ATS W-L-P and
flat 1u -110 ROI/SE, favorite and home baselines. Report proper Brier scores for
raw-margin forecasts through the model's 12.37-point normal mapping; label this
mapping separately from ATS median margins. No fitting on ATS ROI.

Use 4,000-replicate 95% week-cluster bootstrap intervals for coefficients and paired gains,
seed 20261113. Descriptive per-season means and 2025 chart results are exposed
research; these historical seasons informed model development. Do not claim
new held-out confirmation. 2026 is excluded from training and from this test.
Adoption requires a negative effect with an interval below zero and improvement
on the prior-season walk-forward comparisons; otherwise unresolved or contradicted.
No threshold, cohort or penalty magnitude is selected from these results.

Actual-label correction before interpreting fits: schedule QB IDs can retain stale projections.
Use earliest actual QB-position passer on the game-week roster; exclude gadget
players and leave unknown positions unresolved. Prior incumbent histories use
these corrected earlier-game outcomes. Schedule IDs are retained only for discrepancy auditing.
