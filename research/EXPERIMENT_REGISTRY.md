# Experiment registry

Owner scope: research only. Selection uses designated predictive losses, never
ROI. Historical results below are exposed development; no independent test set
or prospective result is claimed. No production promotion is authorized.

| ID | Status | Hypothesis / locked comparator | Finding | Recommendation |
| --- | --- | --- | --- | --- |
| R000 | Completed | Reproduce October 16 eight-arm joint-score experiment at base e93b936 | Original predictions, features, fit/history audits and coefficients match byte for byte; summaries identical; unknown market timestamps remain unverifiable | Retain market-only benchmarks |
| R001 | Completed | Training-only tie hurdle improves empirical A joint NLL; smooth is secondary | Gain 0.018589 nats/game, week-bootstrap 95% [0.013490, 0.021287]; each 2023-25 season improves | Retain for research; plan locked fresh forward comparison |
| R001-F1 | Planned, not activated | Fixed empirical A versus R001, first 512 eligible future games | No real quotes, forecasts or outcomes collected | Activate only after provider validation and external timestamped registration |
| R002 | Completed | Fixed +2/+3/+6 terminal transport vs empirical R001 | Joint-NLL gain +0.007088; two-contrast interval [0.003099, 0.011391]; mechanism unidentifiable | Retain for research; fresh validation required |
| R003 | Completed | Independent additive joint score-support mask vs raw empirical A | Gain +0.000286; two-contrast interval [0.000253, 0.000325]; below fixed 0.005 practical threshold | Reject advancement; preserve the small positive result |

## Original negative findings preserved

These six contrasts were fixed in the original research, then reproduced here.
Gains are baseline-minus-candidate joint NLL on 816 2023-25 games. Each comparison
uses matching distribution shape and market-only A. Family intervals are the
original six-comparison Bonferroni 99.1667% intervals. Do not erase unresolved or
adverse findings when adding new candidates.

| Original shape / information | Gain | Adjusted interval | Finding |
| --- | --- | --- | --- |
| Smooth / residual means B | -0.002796 | [-0.009401, +0.003619] | No demonstrated improvement |
| Smooth / absolute histories C | -0.004936 | [-0.018202, +0.007734] | No demonstrated improvement |
| Smooth / squared histories C | -0.005556 | [-0.015237, +0.004105] | No demonstrated improvement |
| Empirical / residual means B | -0.005149 | [-0.020102, +0.008381] | No demonstrated improvement |
| Empirical / absolute histories C | -0.022209 | [-0.042743, -0.001507] | Adverse under original adjusted interval |
| Empirical / squared histories C | -0.017044 | [-0.035504, +0.001479] | No demonstrated improvement |

Reject adding these fixed four-game residual implementations on this evidence;
this does not reject every residual-information hypothesis. Every original arm,
season, probability metric and betting diagnostic is retained in R000.

## R001 registration and exposure

`experiments/R001_tie_hurdle/PROTOCOL.md` was committed in local isolated commit
715d4d6 before candidate execution. Its SHA-256 is in the R001 provenance. The
hypothesis was inspired by excessive ties in the already published report.
Thus this is a preregistered specification for an exposed historical diagnostic,
not an independently preregistered test. There was no parameter search, failed
candidate revision or ROI-based winner selection in this iteration.

One new primary contrast has a 95% interval. A seven-contrast sensitivity
interval [0.010956, 0.021401] adds R001 to the six original primary contrasts;
it does not account for all previous research selection. Secondary metrics and
the smooth transport check remain descriptive. New result-inspired hypotheses
must receive new IDs and fresh evaluation.

## Iteration 2 registration

R002 and R003 protocols were committed together in efbbeef before either
new forecast run. R003 does not combine R002 or R001. Two new primary contrasts
use 97.5% Bonferroni intervals; nine-contrast sensitivity includes the six original
residual contrasts plus R001/R002/R003. All other metrics are descriptive;
previous historical exposure remains. Kernel weights and support are never
selected by ROI. R002 reports full primary/secondary negative findings.

R002 primary empirical NLL: R001 7.106782 -> R002 7.099695. Annual gains
+0.005717/+0.011843/+0.003703; excluding 2024 leaves +0.004710. Team NLL/CRPS
and total CRPS worsen slightly; winner/tie probabilities and moneyline choices
are invariant. This is a terminal mass-transport diagnostic; a fitted OT process
is blocked by missing regulation/possession labels. R003 raw empirical A
7.125372 -> 7.125085, no R001/R002 combination. Thirteen unreachable pairs
excluded while rare valid one-point outcomes remain. No candidate tuning.

R003 initially failed compressed-file EOF and repeat byte-integrity checks.
Corrupt artifacts/logs are preserved; an I/O-only atomic serialization revision
was applied without changing either forecast design. Final independent reruns
pass; R002 canonical prediction CSV is unchanged by that engineering revision.
No new candidate or independent validation was declared from the rerun.
