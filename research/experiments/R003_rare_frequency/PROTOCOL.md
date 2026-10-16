# R003-RF1: prior-week rare-score frequency correction

Specification frozen locally before executing this candidate. This follows the
October 16 R003 diagnostic on already exposed history; it is development research,
not independent preregistration or forward evidence. Original R003 is unchanged.
This versioned R003 extension does not redefine the reserved R004 experiment.

## Fixed candidate and fitting

Reference: empirical R003 joint score PMF on 0..80 with its fixed reachability
mask. R={1,2,4,5}; r(h,a)=I(h in R)+I(a in R). New Q_theta is proportional to
P_R003*exp(-theta*r), normalized over the joint support. No legal score is banned.
All marginal/event probabilities derive from Q, with no independent maps.
Do not combine R001, R002, a key-number multiplier, or a parameter grid.

Fit one theta per NFL week on earlier out-of-sample R003 forecasts and realized
scores, reconstructed from the frozen R000 prior-week mean/covariance fits and
neighbors. Calibration forecasts start in 2015; evaluation starts in 2017.
Use the current and five earlier seasons, entire prior weeks only, with weights
2^(-(target_year-training_season)/2), normalized to sum one. Require 256 prior
calibration games; otherwise theta=0 with an explicit warm-up flag.

Minimize sum_i w_i*[theta*r_i+log(sum_{k=0}^2 m_ik*exp(-theta*k))]
+ .5*.01*theta^2, where m_ik is baseline probability of r=k. Fixed bounds [0,8].
Use a deterministic monotone derivative root, endpoints when necessary, and
log every boundary hit. Ridge .01, rare set, bounds, window, minimum sample,
and decay are fixed without scoring any candidate outcome or tuning on ROI.
Publish the parameter, counts, observed/baseline rare frequency, and cutoffs.
Update the calibration archive only after predicting the whole week.

## Comparison, metrics and decisions

Primary: empirical R003 minus RF1 joint NLL on 816 2023–25 regular-season games.
One new primary contrast: ordinary 95% paired season-stratified whole-week
bootstrap, 10,000 draws, seed 20261016. Include a 99.5% ten-contrast sensitivity
interval (six original + R001/R002/R003 + RF1); neither covers adaptive research.
Bootstrap conditions on existing forecast paths, without refitting them.
2017–22 is a separate exposed development basis; 2026 W1–5 is diagnostic only.
Publish annual results, leave-one-week/season influence and negative metrics.

Retain for research only if primary mean gain >=.005, 95% lower bound >0, all
three primary seasons have positive mean gain, no team/margin/total NLL or CRPS
worsens by >.01, and binary winner LL/Brier worsen by <=.001 each. Integrity
and strict prior-week timing must pass. Report support for the frequency
hypothesis separately from any betting-quality claim. Do not revise the
candidate after seeing a failed gate.

Report home/away/team/margin/total NLL and CRPS, H/T/A, tie, decisive winner,
nonpush spread/total LL/Brier, coverage/width, reliability and midpoint PIT.
Check rare-score, tie, 3/7-margin and tail frequencies. Report same-game 1u
moneyline W-L-P, units, ROI +/- SE, favorite and negative-hold null, and paired
uncertainty. ROI cannot select the candidate. No historical spread/total ROI:
actual two-sided spread/total odds and capture times are absent.

## Integrity and reproducibility

Preserve original R000–R003 inputs, results, code and production ledger. Save
this protocol hash before fitting. Reproduce existing empirical R003 on every
overlapping game to <=1e-10. Fail on unsupported observations, malformed PMFs,
zero realized probability, duplicate/misaligned IDs or invalid cutoffs; no loss
floor or dropped observation can conceal a failure. Export full-precision
per-game metrics, calibration sufficient statistics, weekly fit audits,
source/input/protocol hashes, and ignored generated marginal PMFs. Independently
rerun in a disposable directory and compare forecasts, audits and PMF arrays.

There is no deployment, wagering, provider integration, or forward-cohort
activation in this task. The existing spread-EV CLI may expose RF1 only through
explicit arm selection; its original R003 default must remain unchanged.
