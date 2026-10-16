# R003-MC1: observed outcomes conditional on market matchup context

Fixed locally before any candidate scoring. User-directed empirical alternative
to the earlier possible-score R003 interpretation. All historical years are
already exposed; no independent test or prospective qualification is claimed.
Original R003, RF1, R004 reservation and production outputs remain separate.

## Data and chronological forecast contract

Use only R000's frozen completed 2013–2026 regular-season input games with finite
spread, total and nonnegative integer final scores. No downloads or revised
outcomes. Predict from 2015 onward; main evaluation 2023–25 (816 games), 2017–22
separate development context, 2026 W1–5 separate diagnostic (79 games). For every
forecast use entire strictly earlier NFL weeks, current plus five prior seasons,
two-season recency half-life measured in season/week slots (19 slots per year).
No current target outcome or other same-week result can enter the distribution.

Context coordinates are signed home-favorite spread and total. Implied home/away
points (total +/- spread)/2 are displayed but not added as redundant dimensions.
Time-weighted historical game pairs form the only probability atoms. No Gaussian,
possible-score grid, reachability mask, rare-score penalty or learned team feature.

## Fixed iterations, not an outcome-driven search

Ten candidates, with all settings declared before scoring:
1. Direct observed scores: Gaussian similarity kernels with spread/total
   bandwidths (2,3), (4,6), (8,10) points, each with backoff pseudo-games 20 or 80.
2. Direct observed scores: nearest 100 or 250 historical games using distance
   scales (4,6), pseudo-games 80. No mirrored duplicate games.
3. Market-relative paired scores: kernel (4,6), pseudo-games 20 or 80. Translate
   each historical team's actual score by current minus historical implied team
   points; round each resulting score half-up to an integer. Remove negative
   transformed atoms and renormalize, logging lost mass and count (never clip
   into zero or impose an upper cap). This is explicitly a translated empirical
   residual experiment, not pure observed-score sampling.

Two controls: global time-weighted direct outcomes, and global time-weighted
translated outcomes. Local mixture weight alpha = n_eff/(n_eff+pseudo_games),
n_eff=(sum local_weights)^2/sum(local_weights^2). Final weights mix the normalized
local weights and normalized global time weights. No arbitrary density sum is
treated as a sample count. Effective support is reported before and after any
invalid-atom exclusion. No resampling randomness is needed for predictions.

Nearest-neighbor ties use game ID order. Kernel calculations use stable log
weights. Every output is a weighted empirical distribution of paired source
games (raw or explicitly translated). Derive winner/tie, cover/push and total
probabilities, means, CRPS, quantiles and intervals from those same atoms.

## Selection and evaluation

Primary loss is 0.5*(margin CRPS + total CRPS), in points; no exact-score NLL:
unseen pairs legitimately have zero empirical probability and no Gaussian or
likelihood floor may hide that. Binary log loss uses exact probabilities, with
infinite wrong endpoint losses retained and treated as failures, never clipped.
Exclude actual ties from decisive win scores and actual pushes from conditional
spread/total scores, reporting their counts separately.

For each season 2017 onward, choose one of the ten fixed candidates minimizing
primary loss on all strictly earlier OOF seasons, requiring at least two such
seasons. Exact ties resolve by fixed candidate declaration order. Also select
within direct-kernel, direct-neighbor, and residual families using the same rule.
All selected paths update selection annually and forecast coefficients/weights
only from earlier weeks. Publish every fixed candidate, not just winners. Annual
selection can use earlier-season outcomes from the main period, as an explicitly
adaptive prequential policy, without retrospective replacement.

Single primary new policy: all-family earlier-season selection versus unchanged
empirical R003 on identical 2023–25 games. Primary intervals: 10,000 paired
whole-week bootstrap draws within season, seed 20261016; 95% interval and 99.5%
ten-candidate sensitivity interval. Fixed-arm/family comparisons and other scores
are descriptive, not ten independent confirmatory claims. Existing design
exposure and conditioning on selected forecast paths remain uncorrected.

Retain for research only if primary gain >=.02 points and its 95% lower bound >0,
all primary seasons improve, primary loss also improves over direct global
history, and no winner/cover/total log loss worsens by >.002 versus original
R003. All cutoffs, probability, population and reproduction checks must pass.
These are forecasting gates, not proof of profitability. No post-result
bandwidth expansion, added information, score transform or tolerance change.

Report home/away/margin/total CRPS and location errors, conditional winner,
cover/total LL/Brier, tie and push calibration, 50/80/90 interval coverage/width,
reliability, support/ESS, yearly stability and influential games. Compare winner
scores with captured-in-file no-vig moneylines. Without actual two-sided spread
and total odds, 0.5 event controls are clearly labeled neutral proxies, not
bookmaker-implied distributions. No historical ATS/total ROI may be inferred.

Moneyline diagnostic: fixed flat 1u on probability >.5 side, same-game favorites
and proportional negative-hold null, ties push, market pick'ems excluded. Show
units, ROI +/- SE and paired week uncertainty. No ROI-based choice or threshold.
Optionally report highest-positive-EV moneyline selection as a separate frozen
diagnostic using both existing moneylines, never as a tuning objective.

## Integrity, use and limits

Preserve all pre-existing user changes and original R000–R003/RF1/data files.
Hash this protocol before scoring. Archive per-game full-precision scores,
annual selections and prior-week input cutoffs, source/input hashes and output
verification. Independent repeat must reproduce numerical results. Save a CLI
that reconstructs the selected empirical atoms for a game and prices externally
provided spread offers through the existing settlement evaluator. Forecasting
requires only game identity and prices; labels enter grading only.

No external prices, new outcomes, production change, deployment, wager or live
cohort activation. Historical price publication times remain unverifiable.
If the fixed experiment fails, retain that result without revising it to pass.
