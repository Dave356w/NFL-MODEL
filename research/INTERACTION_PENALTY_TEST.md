# Joint interaction-penalty test

Owner-approved test, 2026-10-31. Register this protocol before candidate
results are computed. Research only: production v1.18, frozen recipes,
native snapshots, ATS locks, and public pages remain unchanged.

## Hypothesis and frozen arms

Increasing the penalty on the interaction block may improve later-period
probability accuracy by reducing excessive corrections from sparse contexts.
Refit every coefficient jointly before each evaluation week.

Keep production's main-feature ridge 0.1, h8 main and h16 pass profiles,
strictly prior-week normalization, two-season coefficient decay, fixed
market-logit offset, and v1.18 favorite penalty 0.2.

Arms:

- production: all five passing interactions, ridge 0.1;
- ridge_0.3, ridge_1, ridge_3: all five interactions with the named penalty;
- no_interactions: remove all five interactions in both training and
  prediction, and jointly refit the remaining coefficients;
- selected_stronger (primary): choose among 0.3, 1, and 3 by minimum
  earlier-season mean binary log loss. Exact ties prefer the stronger penalty.
- market: unchanged no-vig probability, a benchmark, not a fitted candidate.

The shared passing product and all four signed one-SD hinge terms belong
to the penalized block. No term is merely subtracted after fitting.
No new clipping, support rules, features, tuning grid, or betting filter.

## Chronology and evidence

Use the committed frozen pregame feature pack and normalization audit under
research/shrinkage_results. Generate weekly forecasts for 2021-2025, training
only on eligible binary games strictly before the forecast week.
For evaluation year 2023, select from 2021-2022; for 2024, from 2021-2023;
for 2025, from 2021-2024. Earlier predictions are genuinely weekly
out-of-sample relative to coefficient fitting. No evaluation-year outcome,
ROI, or Brier score enters annual penalty selection.

Main evaluation: identical 2023-2025 binary game rows for all arms, with
per-season log loss and Brier scores. Preserve each season's full results,
including declines. Ties are excluded from binary scores.
These seasons were exposed in earlier model development; this is not an
untouched confirmatory holdout.

Reproduce production against independent committed reference predictions.
Record feature and protocol hashes, training cutoffs, scales, coefficients,
selection cutoffs, candidate selection losses, and optimizer checks.

## Comparisons and decision gate

Report candidate-minus-production differences: negative is better.
Use paired whole-week bootstrap 95% intervals within season, with 10,000
draws and seed 20261031. For the aggregate historical comparison, resample
weeks within each season and retain season sample weights.
Fixed-arm comparisons are descriptive; the primary decision is the
predeclared selected_stronger rule, not the best evaluation-period arm.

Advance to native ATS shadow evaluation only if selected_stronger:

1. has lower log loss AND lower Brier in EACH of 2023, 2024, and 2025;
2. has aggregate paired 95% interval upper bounds below zero for BOTH
   differences against production; and
3. does not worsen aggregate log loss or Brier versus the market benchmark.

A failed gate means no production adoption and no launch justified by this
test. Report the failure without changing the protocol.

## ATS and native evidence

ATS replay is secondary and cannot select the penalty. Use the existing
production prior-season median map unchanged for every arm, the same market
handicap, favorite-on-zero-edge rule, flat 1u and assumed -110; pushes return
the stake and count in the ROI denominator. This isolates the interaction
fit change without optimizing a new spread map.

Audit existing native 60-minute locks for exact saved model inputs and
sufficient earlier training features. First moneyline snapshots are not
substitutes for timed ATS inputs. A candidate computed after an outcome is
a counterfactual, never a native challenger result.

If the historical gate passes, the next requirement is separately frozen
pregame challenger captures beside production, with the same timestamp,
map and line. Review at 100 decided paired locks as in the existing ATS
policy; report W-L-P, ROI, cover rate and same-game controls. No adoption
before that review. This protocol itself does not activate a new capture
workflow or change production.
