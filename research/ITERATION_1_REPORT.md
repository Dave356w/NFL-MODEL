# NFL research iteration - October 16, 2026

**Retain R001 for research. No production or betting promotion.** The historical
tie-calibration hypothesis is supported under its fixed decision rule, but it
was inspired by previously observed results and has no independent validation.

## Completed experiments

R000 reproduces the supplied original experiment on all 2,462 games per arm,
including the primary 816-game 2023-25 sample. Per-game predictions, features,
history audits, fitting audits and coefficients match byte for byte; all original
summary metrics and 29 comparable package checksums agree. The original source
schedule/total merge matches the frozen input exactly. No data revisions.

R001 applies a fixed Jeffreys Beta(0.5,0.5) tie-frequency hurdle to empirical
market-only A, with smooth A as a prespecified secondary check. Fit tie counts
on eligible completed games from the current and five prior seasons, strictly
before each forecast week. No candidate parameter tuning or ROI selection.
Rescale diagonal/off-diagonal joint-score cells while retaining their conditional
shapes. Original weekly means, covariance fits and empirical mixture remain fixed.

## Primary historical result

| Metric | Empirical A | R001 | Interpretation |
| --- | --- | --- | --- |
| Joint NLL | 7.125372 | 7.106782 | Gain 0.018589 nats/game |
| Team marginal NLL | 3.573907 | 3.573044 | Small improvement |
| MOV CRPS | 7.112852 | 7.112072 | Very small improvement; interval spans zero |
| Total CRPS | 7.240770 | 7.241027 | Slight deterioration of 0.000257 |
| Conditional winner log loss | 0.611353 | 0.611353 | Unchanged by design |
| Unconditional H/T/A log loss | 0.640421 | 0.621831 | Improvement from tie/decisive reweighting |
| Mean tie probability | 2.4958% | 0.4195% | Observed: 1/816 = 0.1225%; still uncertain |
| MOV 90% coverage / width | 89.093% / 41.411 | 89.216% / 41.695 | Slightly wider interval |
| Total 90% coverage / width | 90.564% / 42.091 | 90.564% / 42.086 | Essentially unchanged |

Paired season-stratified whole-week bootstrap: 10,000 draws, seed 20261016.
Primary gain 95% interval **[0.013490, 0.021287]**. Seven-contrast sensitivity
interval **[0.010956, 0.021401]**; earlier research exposure is not erased by
this adjustment. All other metric intervals are descriptive.

Annual empirical gains: 2023 +0.020772; 2024 +0.021409; 2025 +0.013586.
Every leave-one-week/season estimate remains positive. 815 decisive games gain
17.178 nats in aggregate, while the single tie loses 2.010 nats. All joint NLL
gain equals the tie Bernoulli gain: no conditional exact-score improvement was
created. Smooth joint NLL falls from 7.234615 to 7.212326, with MOV CRPS slightly
worse (+0.002000), a secondary check only.

The candidate tie rate is not established as calibrated: one event provides
little information. Unknown historical quote timestamps also mean actual
pregame market availability cannot be verified. All historical results are
conditional-on-input development diagnostics, never native forward evidence.

## Betting diagnostics and rejected claims

Empirical A and R001 have the same 812 moneyline bets: **-0.9055u, -0.1115% ROI,
SE 2.4716 percentage points**. Same-row favorites +0.1801u / +0.0222%; underdogs
-89.8201u / -11.0616%; conditional negative-hold null approximately -4.0995%.
Moneyline baseline winner log loss remains 0.608072, better than either empirical
arm's 0.611353 point estimate. Capture timestamps are unknown, so these are
hypothetical diagnostics, not executable-price claims. No spread/total/team-total
ROI is inferred from absent prices.

No new residual-history adoption is justified: all six original variants have
negative joint-NLL gains, and empirical absolute histories are adversely outside
the original adjusted interval. R001 establishes no betting edge, prospective
success, mechanistic overtime accuracy or complete solution to tie calibration.

## Validation and next iteration

31 focused unit tests pass; 10 original and 14 R001 output checks pass. R001
re-execution matches predictions, tie audits, provenance and every stored PMF
array. No tests currently fail. The full production repository suite and its
production data validator were not rerun; previous 517-test statements belong
to the supplied report, not this session. See VALIDATION.md for exact scope.

Most promising next candidates: explicit tie-resolution transitions, then a
separate football-score-support ablation. These are unproven. Defer additional
residual features until the distribution issues have separately been tested.
Prepare R002 without tuning on these exposed outcomes. R001 merits consideration
for a **locked, fresh forward comparison**, not qualification or deployment.

The forward writer stores timestamped full PMFs and raw quote payloads with
content-addressed code/parameter versions, exclusive first writes and integrity
checks. It is offline infrastructure; a validated provider adapter and trusted
external retention remain required. R001-F1 is planned, not activated.

## Files and scope

Required maintenance files: EXPERIMENT_REGISTRY.md, RESEARCH_ROADMAP.md,
RESULTS_SUMMARY.md and VALIDATION.md. R000/R001 outputs include reports, per-game
scores, PMFs, paired metrics/CIs, calibration/PIT diagnostics, audit/provenance,
reproduction commands and decisions. New isolated modules are tie_hurdle.py,
tie_hurdle_report.py, audit_reproduction.py, check_determinism.py and
forward_capture.py, with focused tests and FORWARD_PROTOCOL.md.

All work is in the local research/tie-hurdle-20261016 branch and this standalone
bundle. No GitHub writes, production forecasts, deployed pages, original
attachments or existing ledgers were changed.
