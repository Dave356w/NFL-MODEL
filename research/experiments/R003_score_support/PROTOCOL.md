# R003 - Independent football-score-support ablation

Design locked 2026-10-16 before computing R002 or R003 forecasts. Execute only
after R002 is individually reported and tested. No design adaptation based on
R002 results. Existing historical outcomes are exposed development, not fresh
independent validation. No new data or production changes.

## Hypothesis and fixed support

Does removing rule-unreachable final score pairs improve market-only joint NLL
with practical magnitude? Primary baseline: raw empirical__A_market. Candidate:
condition that same joint PMF on a fixed football scoring reachability mask.
Do not combine with R001 tie calibration or R002 transitions. Apply the same
mask to raw smooth A as a prespecified descriptive check.

Use additive joint scoring generators, with side swaps, within score cap 80:
(2,0) safety; (3,0) field goal; (6,0) touchdown without a successful try;
(7,0) touchdown plus one; (8,0) touchdown plus two;
(6,1) touchdown plus a one-point try safety awarded to the opponent;
(6,2) touchdown plus a two-point defensive try return.
Begin at (0,0), take the full nonnegative additive closure within 0..80 per side.
Do not allow an independent (1,0) generator. Preserve valid rare (6,1)/(1,6)
pairs; do not ban an entire team's score 1 or assign observed-frequency weights.
This reachability abstraction covers ordinary scoring and rare try scores;
it is not a play/clock/possession simulator, nor a model of their frequencies.
Forfeits/administrative exceptional score awards are outside this completed-game
scoring abstraction and must not be silently graded under it in a future feed.

Q(h,a)=P(h,a)*mask(h,a)/sum(P*mask). No smoothing parameter, support learning,
empirical-frequency tuning, football key-number weighting, tie correction or
covariance refit. Report the full mask and every excluded score pair, removed
probability mass by game and predicted rare one-point mass. Impossible observed
outcomes MUST hard-fail with game ID; never replace zero probability by an NLL
floor, remove those games or revise the mask after looking at them.

All means, totals, MOV, winner, tie, cover and total-event probabilities derive
from Q. Conditioning may change them; no independent recalibration maps.

## Data, cutoffs, metrics and decision

Same frozen R000 inputs, 2013+ training, original prior-week weekly fits.
2017-22 exposed supplementary development: 1,567 games; 2023-25 historical
comparison: 816 games, 272/season; 2026 W1-5 separate 79-game diagnostic.
No new fitted parameters or selection split. Historical quote timestamps remain
unknown. No test-set ROI tuning, no future/current-week labels in forecasts.

Primary: empirical A-minus-R003 joint NLL. Two new primary comparisons in this
iteration, with R002: paired season-stratified whole-week bootstrap, 10,000 draws,
seed 20261016. Report 95% and 97.5% two-comparison Bonferroni intervals; nine-
contrast 99.4444% sensitivity interval to include prior six residual contrasts
and R001. Selection exposure remains uncorrected beyond that finite family.
Secondary metrics, smooth and every other contrast are descriptive.

Report joint/marginal NLL, CRPS, conditional winner LL/Brier, unconditional H/T/A,
tie scores, interval coverage/width, reliability/PIT, paired/season/stability/
influence diagnostics, and hypothetical moneyline/favorite/underdog/hold controls.
No actual team-total prices or spread/total prices are available, so do not
invent market ROI from the derived locations. Preserve original negative arms.

Advance for further research only if primary gain >=0.005 nats/game, adjusted
lower interval >0, all three seasons improve, no marginal NLL/CRPS worsens >0.01,
and winner LL/Brier deteriorate by <=0.001 each. No observed support violations,
normalization failures or leakage failures. A tiny mathematically guaranteed
support gain does not demonstrate practically useful football-score modeling.
Reject advancement on a failed rule; preserve any scientifically valid but
small effect. No production promotion or betting deployment. A genuine future
validation cohort and provider timestamps remain prerequisites.
