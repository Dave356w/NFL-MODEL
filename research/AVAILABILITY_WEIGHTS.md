# Availability weighting candidates protocol

Research only; production v1.16, frozen recipes and the forward ledger are
unchanged. Written and committed before any candidate forecast exists. Trigger:
the owner asked whether position-group injuries are properly weighted, then
asked to test the suggestions that followed.

## Candidates

Everything not named here stays exactly as v1.16: the recipe, both penalties, the
fit decay, the QB term, the roster, reserve and membership rules, and every
non-availability feature.

* **A, Questionable by practice (primary).** A Questionable player's unavailable
  weight follows his final practice participation, at Test 28's calibrated
  weights estimated on 2019–22 snaps (snap loss beyond healthy regulars, scaled so
  Out = 1): full practice 0.06, limited 0.26, did not practise 0.55. Questionable
  with no practice entry keeps production's 0.25. Out and Doubtful stay 1. Labels
  use Test 28's `practice_label`.
* **B, split units.** Wide receivers and tight ends become separate units, as do
  cornerbacks and safeties (S, FS, SS, SAF); generic DB counts as a cornerback.
  That gives eight unit columns instead of six, each with its own fitted weight.

Not tested: separating 3-4 edge linebackers from off-ball linebackers (snap-count
labels list both as LB), player-quality weighting (Test 30) and the
lock-versus-close timing mismatch (no historical lock-time quotes exist).

## Method

* Rebuild only the availability unit columns, with production's
  `availability_table` and `lagged_features` difference rule, from raw nflverse
  injury reports (with practice status), weekly rosters and snap counts. The QB
  term and every other feature are the frozen values.
* **Pipeline check first.** Under production rules the rebuild must reproduce
  the frozen unit columns. If upstream data changed and it does not, the control
  arm is the rebuilt control, so control and candidates share raw data, and the
  difference from the frozen columns is reported.
* Weekly walk-forward refits exactly as production, before every evaluation week
  on earlier rows only, on two bases:
  1. **2017–2020**: `research/out_of_sample_results/frozen_features_2013_2020.csv.gz`,
     with 2013–2016 as the only earlier history and the out-of-sample protocol's
     eligibility rules.
  2. **2023–2025**: `research/shrinkage_results/frozen_training_features.csv.gz`,
     the restoration's features. Exposed: v1.16 was chosen on these seasons.
* Each candidate against the control on the same games: per-game log-loss gain;
  a week-cluster bootstrap (seed 20261013); flat 1u units, ROI ± SE, the
  market-correct null, the same-row favorite and side flips.

## Decision, per candidate

Log loss decides; ROI is reported, not optimized.

* **Supported** as a candidate for the next revision: the log-loss gain over the
  control is above zero on both bases, and the pooled two-basis 97.5%
  week-cluster interval (two candidates) lies above zero.
* **Falsified**: the pooled log-loss gain is at or below zero.
* Otherwise **unresolved**.

Even a supported candidate changes nothing in production without the owner's
decision and a new `REVISION`.

## Power and exposure, stated now

* v1.16's position-group weights are within one standard error of zero.
  Removing every availability input moved log loss by +0.0010 [−0.0014, +0.0034]
  on 2023–25 and +0.0005 [−0.0038, +0.0049] on 2017–20. Both candidates change
  the inputs far less, so the likely outcome is unresolved; a negative pooled
  gain falsifies.
* Known to the author before this protocol: Tests 28 and 30, drop-one-input
  ablations of the availability block on both bases, and a market-versus-outcome
  decomposition on 2013–18 and 2019–25. In that decomposition WR/TE and
  secondary absences leaned toward being under-priced by the market (z −1.6 and
  −1.8, not significant). Candidate B is partly motivated by that hint, so it is
  not an independent test of it. A forward test of the hint would need its own
  registration.
* Before writing this, only non-outcome data were examined: position labels in
  the snap counts and the practice-status fields. No candidate forecast exists.

Run `python research/availability_weights.py --prepare` once to download inputs
and freeze the rebuilt columns, then `python research/availability_weights.py`.
