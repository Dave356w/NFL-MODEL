# R003-PT1: pooled travel density-ratio adjustment

Fixed before scoring this new family. All historical years are already exposed;
the positive SC1 travel point estimate motivated this test. No independent
confirmation or production promotion is available from this retrospective run.

## Inputs and baseline

Use unchanged R000 frozen inputs and SC1 schedule/rest features. Plain is MC2
direct_ref_h2_t3_p0. Its historical observed paired scores and spread/total
kernel weights remain the support. No score translation, new outcomes, prices,
team effects, Gaussian, or possible-score enumeration. Six-season window,
strictly earlier weeks, half-life 38 weeks, as in plain. Neutral/malformed
travel is unknown and receives exactly plain. Travel classes are small shift,
eastward >=2 zones, westward >=2 zones, inherited unchanged from SC1.

## Pooling estimator

Fit one three-class ridge multinomial logistic travel classifier per prior-week
window, pooling all valid-travel games across market contexts. Small shift is
the reference class. Predictors are market controls [1,s,t,s²,t²,s*t], where
s=spread/10 and t=(total-44)/10. Outcome-shape predictors are residual margin
r=(home-away-spread)/14 and total u=(home+away-total)/14, each clipped to [-4,4].
Linear shape uses [r,u]; quadratic adds [r²-1,u²-1,r*u]. No target outcome enters
prediction. On historical candidate atoms, r/u use the atom's score and the
TARGET lines; market controls use the target lines. This evaluates a conditional
travel likelihood for each possible observed atom, not its original travel label.

Fit weighted summed classification log loss + half ridge penalty. Weights are
time-decay normalized then multiplied by their overall Kish ESS. Non-intercept
market coefficients receive penalty 1, intercept 0.01, outcome coefficients
lambda in {20,100}. Fixed candidates: linear/quadratic x 20/100 = four. Start
coefficients zero, analytic gradient, L-BFGS-B, gtol=1e-7, ftol=1e-12, maxiter=1000.
Fail scoring on optimizer failure; do not silently substitute favorable results.

For target travel class c and each atom i, estimate p_i=P(c|target market,
atom outcome). The Bayes density ratio is p_i / sum_j(w_j*p_j). The denominator
is common to all atoms and cancels without capping; here cap the ratio to
[0.5,2], then normalize w_i*ratio_i to form the tilted distribution. This is an
approximate pooled conditional-density adjustment, not a causal travel effect.

Class support is Kish ESS of time weights among that class in the pooled
training set, not exact market/slot/rest matches. Below 20 support, or fewer
than 200 usable training games, return plain exactly. Otherwise mix tilted and
plain with alpha=class_support/(class_support+100). Outcome-coefficient ridge,
ratio cap and mixing shrinkage are distinct predeclared protections. A classifier
whose outcome coefficients are zero must produce exactly plain. Record fitted
coefficients, class counts/support, cutoffs, convergence, alpha and weight shifts.

## Selection, comparison and decision

Generate OOF paths starting 2015, select annually for 2017 onward from plain
(first tie break) plus the four fixed challengers. Selection minimizes conditional
winner log loss on strictly earlier OOF seasons (at least two), never ROI.
Primary comparison is this selected path vs plain on identical 816 games
2023–25. Also compare to SC1 fixed travel_k100 and SC1 selected_all, without
adding them to this selector. Earlier 2017–22 and 2026 are separate diagnostics.

Report all arms, margin/total/home/away CRPS, win/cover/total log loss and Brier,
tie/key-number shape, coverage/width, annual selection and travel slices. Lead
moneyline with units, ROI +/- SE, n, same-row favorite and market-correct null;
do not optimize returns. No ATS/total ROI without actual offered prices.

10,000 paired whole-week draws within season, seed 20261016, 95% intervals and
98.75% four-challenger sensitivity. Conditional on fitted forecast paths; not
full adaptive-research correction. Primary distribution loss is average margin
and total CRPS. Retain for research only if gain >=0.01, primary 95% lower bound
>0, all 2023–25 annual gains positive, no secondary margin/total CRPS or
win/cover/over log loss deteriorates by >0.002, and integrity checks pass.
No automatic production adoption even if these historical gates pass.

## Validation and preservation

Test analytic gradient, known planted travel-shape recovery, no-signal exact
plain, neutral/low-support fallback, strong regularization, positive normalized
weights and unchanged atoms, source/target alignment, future-data rejection,
earlier-only annual selection, and outcome-independent target prediction.
Reproduce plain, preserve source/protocol/input hashes, independently repeat
the full run, and leave original experiments, production and ledger unchanged.
No post-result candidate changes or expanded search in this experiment.
