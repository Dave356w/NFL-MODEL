# Test 35 protocol: which de-vig method gives the best market anchor?

Research only; production, frozen recipes and the forward ledger are unchanged. Owner go-ahead
2026-10-14. This file is committed and pushed before any outcome has been scored under a de-vig
method other than production's.

## Question and where it came from

Every market baseline in the repo removes the hold **proportionally**:
`q = i_home / (i_home + i_away)` (`nfl_model.market_ml_wp`; pinned by
`tests/test_devig_robustness.py`). Proportional de-vig assigns the hold to both sides in
proportion to their implied probability, so it leaves the most hold on the favorite. At -350/+280
it gives 0.747, while additive de-vig gives 0.757 and power de-vig gives 0.763. If the market's
true favorite-longshot pattern matches one of those methods better, production's anchor is biased
by about 1–1.5 points on heavy favorites.

## What it can and cannot change

All three methods are monotone and agree on which side is favored, so the model's side, the
market-favorite baseline and **flat 1u ROI (the goal metric) are the same under every method**.
The method changes q and everything computed from it: the market-correct null (proportional:
`1/overround − 1` on both sides; the others: less negative on favorites, more negative on
underdogs), excess win rate, the log-loss/Brier market benchmark, the Kalshi ladder's `fav_wp`,
the favorite penalty, and the `q` model input. Because q is a model input, adopting a different
method would change `config_signature()` and need a new `REVISION`. That is the owner's call,
and this test only informs it.

## Exposure, disclosed in advance

* The proportional q has already been scored against outcomes in many earlier tests, as the
  market baseline. The Kalshi ladder table was built from 2006–2024 favorites under proportional q.
* **No additive or power q has been computed against outcomes for any season** in this
  repository. The only numbers seen are single-quote examples (-350/+280) with no results attached.
* Prior: the NFL moneyline favorite-longshot bias is reported in the literature as small and
  unstable, so the expected verdict is "unresolved".

## Arms (fixed, parameter-free)

* **P (production):** proportional, `q = a / (a + b)`.
* **A (additive):** `q = a − (a + b − 1) / 2`. For two outcomes this is identical to Shin's method,
  which is therefore not a separate arm.
* **W (power):** `q = a^k` with `k` solving `a^k + b^k = 1`.

Here `a, b` are the home and away American-odds implied probabilities. No other method is tried.

## Data

nflverse schedules (`nflreadpy.load_schedules`), regular season 2006–2025. A game is included when
both moneylines are finite with |ML| ≥ 100 and the game is decided (a tie has no binary label and is
excluded). The capture time of the schedule quotes is unknown (as in earlier research). The 2026
season is excluded: it is the forward ledger's season.

## Selection and held-out confirmation

1. **Selection, 2006–2016:** the arm with the lowest mean log loss (home-win probability vs home
   won) is selected. Ties go to P.
2. **Held-out, 2017–2025:** scored once. The primary statistic is the selected arm's paired per-game
   log-loss gain over P (P minus arm; positive = arm better), with a two-sided **97.5%** interval
   (normal, per-game SE). The 97.5% level allows for the two non-production arms.

**Verdict:**
* **Propose a change** (to the owner, as a candidate new `REVISION`) only if the selected arm is not
  P and its held-out gain over P is positive with an interval that excludes zero.
* **Keep P** if P is selected, or if the held-out gain is negative with an interval that excludes
  zero.
* **Unresolved, keep P** otherwise. A crossing interval does not show the methods are equal.

## Reported, not gating

On the held-out seasons, for every arm: n, log loss, Brier, the paired gain over P with 97.5%
interval, and the logistic calibration intercept and slope of the outcome on `logit(q)`.

* Per favorite band of production `fav_wp` (0.50–0.60, 0.60–0.70, 0.70–0.80, ≥ 0.80): n and each
  arm's paired gain over P.
* Season by season: the sign of each arm's gain over P.
* **ROI (goal metric).** Flat 1u ROI ± SE at the moneyline, for the favorite and underdog sides per
  band. These are the same under every method. Next to each, every arm's mean market-correct null
  on the same rows. The null that best matches realized ROI is a description, not a test.
* The same tables for 2006–2016, labelled as selection data.

## Falsification

The claim that production's proportional anchor is biased on favorites is falsified for practical
purposes if A or W loses to P on the held-out seasons with an interval that excludes zero. It is
not falsified by an interval that crosses zero.

## Outputs

`research/devig_methods.py` writes `research/devig_methods_results/` (REPORT.md, results.json,
provenance.json with the data hash). Tests: `tests/test_devig_methods.py`.
