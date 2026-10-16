# R002 - Explicit overtime-inspired score transitions

Design locked 2026-10-16 before generating any R002 forecasts. All historical
evaluation data have already been exposed. This is a fixed exploratory ablation,
not fresh validation, prospective research or identification of an overtime law.

## Audit and scope

The frozen 15-column dataset has final scores, not regulation scores, overtime
flags, coin tosses, possessions or drive increments. The existing PMF forecasts
final scores including overtime. Therefore applying an overtime simulator as
though that PMF were a regulation PMF would double count overtime. A fitted
mechanistic model is not identifiable from these files. Do NOT fabricate a
regulation label, use final winning margins as observed OT increments, or fit
transition frequencies on the evaluation outcomes. Such a model remains blocked
pending a separately frozen, audited regulation/OT dataset.

Here the testable hypothesis is narrower: place the mass removed from the raw
final-score diagonal in explicit plausible terminal score cells instead of
spreading it across all decisive cells as R001 does. The amounts moved are
hypothetical distribution corrections, not estimated frequencies of overtime.

## Locked specification

Primary comparator: empirical market-only R001 tie hurdle. Raw empirical A is
an additional locked descriptive comparator. Apply the same formulas to smooth
A/R001 as a secondary transportability check, never an alternative primary.
No feature, mean, covariance, empirical mixture or tie-rate parameter changes.

For raw normalized joint PMF P, let t=trace(P), r=R001's prior-week Jeffreys tie
rate, B=R001(P,r), and q=P(home wins)/(1-t). Let e=max(t-r,0).
For each tied cell (s,s), assign source mass a_s=e*P(s,s)/t. Candidate Q starts
at B. Replace that source's uniform decisive allocation with explicit positive
score increments d in {2,3,6}, equally weighted among increments within cap 80:
(s+d,s) receives a_s*q and (s,s+d) receives a_s*(1-q), divided equally over d.
These are safety/field-goal/touchdown terminal increments, a restricted subset
of possible overtime endings. Weights 1/3 are fixed modeling assumptions, not
empirical estimates or NFL-rule probabilities. No rule-era adaptation or
possession/clock process is claimed. Both teams scoring, conversion decisions,
and many valid endings are intentionally absent from this minimal kernel.

For s=79 or 80 no positive increment fits. Its source allocation stays in B's
conditional decisive distribution; the untransportable source mass is explicitly
logged. For other near-cap states, renormalize only the representable increments
and log affected mass. No clipping to score 80, score decreases, mass deletion,
negative probabilities or silent fallback. If r>=t, e=0 and Q=B by specification;
count these games. Conditional winner probability and final tie rate must equal B.
Formally subtract transported_mass*B_offdiag/(1-r) from B, then add the positive
terminal allocations. Retain all original strictly positive decisive support.

## Training, samples and evaluation

Use precisely the frozen R000 inputs and weekly coefficient audits. Reconstruct
market-only full joints and assert agreement with locked A and R001 forecasts.
Tie counts use only strictly prior-week eligible games, current plus five prior
seasons, unweighted Jeffreys Beta(0.5,0.5); no new fitted kernel parameters.
2013+ training; 2017-22 exposed development (1,567 games); 2023-25 historical
comparison (816; 272/season; 815 decisive); 2026 W1-5 separate diagnostic (79).
Quotes have no verifiable historical capture timestamp. No independent selection,
validation or test split exists. No current-week labels or ROI tune a parameter.

Primary: empirical R001-minus-R002 joint NLL. Positive is improvement. Two new
primary contrasts are registered this iteration (R002 and independent R003).
Season-stratified paired whole-week bootstrap, 10,000 draws, seed 20261016.
Report 95% descriptive and 97.5% two-comparison Bonferroni intervals. Also report
99.4444% sensitivity interval across six original residual contrasts + R001 +
R002 + R003 (nine); this cannot erase arbitrary prior research selection.
All secondary metrics, raw-A and smooth contrasts are descriptive.

Report joint and all marginal NLL/CRPS, conditional winner LL/Brier, unconditional
H/T/A and tie scores, spread/total/nontraded team-location diagnostics, 50/80/90
interval coverage/width, reliability, PIT, paired CIs, annual/leave-week/season
stability, influences, and hypothetical moneyline controls. No absent-price
spread/total/team-total ROI; no model selection by ROI. All metrics share a joint.

Support the narrow historical hypothesis only if primary gain >=0.005 nats/game,
two-comparison interval lower bound >0, all three annual gains positive, and no
marginal NLL/CRPS worsens >0.01. Winner/tie invariance is mandatory. Otherwise
reject advancement of this fixed kernel or mark unresolved, without revising it
on these outcomes. Historical exposure forbids independent validation claims.
Even a passing diagnostic cannot qualify a mechanistic overtime process.

Next: finish tests, report and registry before executing R003. Both protocols
are fixed now so R003's design cannot react to R002's results.
