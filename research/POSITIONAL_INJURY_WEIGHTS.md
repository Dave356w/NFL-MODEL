# Saved 2026 injury replay and positional-weight learning

Owner-requested research. Fixed before fitting/scoring these injury weights.
No production revision, existing forecast, report, candidate, lock or journal is
rewritten. Final all-2026 weights are future-use diagnostics, not backtest scores.

Two explicitly separate evidence cohorts:
1. Saved pre-T60 model-input vectors: latest eligible vector with six positional
   absence columns plus QB delta, selected by generated timestamp, one per game.
   These use production's absence proxy, including roster departures. They are
   saved injury features, not preserved original medical-report HTML.
2. Saved official-report snapshots: latest complete/issue-free report for BOTH
   teams captured and (when provided) published by T60. Rebuild medical-only
   snap-weighted unit burdens from those exact statuses and strictly earlier
   snaps. Historical snap/roster source-publication times remain unverified;
   this is a report-backed reconstruction, not native execution evidence.
   A newer incomplete/failed report blocks the game; never fall back to an older
   complete report after a potentially updated designation could not be parsed.

Initial coverage audit: cohort1 72 games, weeks5-10; cohort2 13 games, weeks9-10.
The stricter latest-report guard excludes GB-NE because its newer report is
incomplete, leaving 12 official-report games. This input-quality correction is
not based on returns. Missing games are excluded, never filled as healthy.
Both compare to the same frozen published mapped median on their own eligible
games. Saved vectors can predate final inactives and the final public forecast;
the replay does not pretend all information was captured simultaneously.

Features: home-minus-away OL, WR/TE, RB, DL, LB and DB absence shares plus an
incremental QB-delta correction. QB delta is already in the base win model, so
its learned coefficient is additional point correction, not a replacement of
that logit coefficient. All coefficients are pooled across teams, unconstrained:
they measure residual information AFTER the market/base forecast, not intrinsic
injury costs. No LAC/PHI-specific fitting or manual injury point deductions.

Historical training: 2023-25 mapped base forecasts joined to earlier reconstructed
injury inputs. Cohort1 uses frozen production-absence vectors; cohort2 uses final
historical medical designations, reconstructed identically to report burdens.
These histories are exposed research and do not establish historical publication
timing. Only outcomes from earlier years/weeks can train a replay forecast.
Medical-only historical training additionally requires both team-week report
states to be `final`; practice/missing reports are excluded and counted.

Medical burden: Out/Doubtful=1, Questionable=.25, Available=0; most severe status
per player. Denominator is prior four team-games' positional snaps, using this
season only once two prior games exist. No target-game snaps. Non-QB unit roles
match production. Players with no recent team snaps contribute no known snap
share; audit those counts rather than interpreting them as medically healthy.
Healthy scratches are not silently relabelled injuries.

Fit exact median (.5 quantile) regression on actual margin minus base median,
with unpenalized intercept and L1 penalty alpha=.02 on seven training-standardized
coefficients. Equal game weights, no hyperparameter or ROI search. Solve via
SciPy HiGHS linear programming; objective is mean pinball + alpha*sum(abs(beta)).
No squared-error mean intercept. Compare original median and prior-only median
intercept control, frozen 2023-25 injury fit, and weekly updated injury fit using
2023-25 plus strictly earlier saved 2026 games in the same evidence cohort.

Replay all eligible games with each week's parameters frozen across that week.
After scoring, learn final weights on history plus all completed eligible 2026
games; publish prior/final weights and updates but no fitted-on-test performance.
Report incremental points per +10pp non-QB absence difference, and per +1 QB
net-yard/dropback difference; these are NOT causal player valuations. The six
non-QB positions and QB correction stay separate throughout.

Metrics: median residual, MAE/median pinball, RMSE secondary, ATS W-L-P/skips,
flat 1u -110 units/ROI, market-favorite/home controls, and conditional-cover
LL/Brier/reliability. Cover probabilities use each prior fit's empirical residual
distribution with .5 pseudo-count per tail and integer-margin continuity bounds;
fractional margins interpolate between adjacent integer outcomes (equivalently,
uniform dequantization before rounding), retaining integer push mass.
this is a research probability approximation, not saved production ATS odds.
Paired whole-week bootstrap of held-out MAE/cover LL, 5000 draws seed20261113;
12 official-report games over two weeks cannot support strong inference.
Final coefficient stability: 200 whole-week bootstrap refits, seed20261113;
ranges are descriptive and do not correct prior feature/recipe selection.

Checks: pre-T60 report/vector eligibility; both-team completeness; future sources
and target snaps cannot change features; one report/vector per game/team; source
hashes; median rather than mean intercept; quantile solver objective; planted
injury signal; no current-week labels in rolling fits; exact sign/push/price
logic; immutable journal hashes and deterministic replay.

Scope clarification: this is a residual-margin overlay, not an injury -> team
efficiency -> base model -> median-map propagation test. No positional starter's
replacement efficiency is estimated, and no rolling team-stat profile is rebuilt
under a counterfactual lineup. Zero incremental margin coefficients do not rule
out that efficiency mechanism. The owner raised this distinction after the first
replay; it is retained explicitly rather than relabelling this as that test.

Post-hoc solver/shrinkage check: alpha=0 coefficient estimates on historical and
all-completed-2026 samples are saved separately, with no backtest scores. They
check why the prespecified penalized fit selected zero. They do not choose alpha,
replace the main fit, or establish prospective value.
