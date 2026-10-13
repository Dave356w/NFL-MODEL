# Margin-likelihood v1.16 protocol

Research only; production v1.16, frozen recipes and the forward ledger are
unchanged. Written and committed before the margin-likelihood code exists and
before any challenger forecast for 2017–2020 is computed. Owner request
2026-10-13: fit v1.16's features to the final score margin with a
key-number-aware distribution, convert to win probability, and test it on
2017–2020 out of sample.

## Exposure, disclosed in advance

* **2017–2020 have been scored once for v1.16** (`OUT_OF_SAMPLE_2017_2020.md`):
  −0.42u, −0.04% ± 2.23 on 1,017 bets, +18.76u vs the same-row favorite,
  log loss 0.605604 vs market 0.600368. The author of this protocol knows these
  numbers and has sliced the committed v1.16 predictions by price band,
  underdog picks and confidence in conversation. No margin-likelihood
  forecast has been computed.
* **Key-number structure** (more NFL margins land on 3, 7 and 10 than a normal
  curve predicts) is general knowledge; the multipliers below are estimated
  only from earlier seasons' outcomes inside the frozen pack.

## Data

The frozen 2013–2020 pack and scored-row definition of the out-of-sample run
(`research/out_of_sample_results/frozen_features_2013_2020.csv.gz`), unchanged:

* training rows: v1.16's `eligible` rows (ready, binary result, finite q and
  pass contexts) from strictly earlier weeks;
* scored rows: 2017–2020 regular-season games that are ready, priced on both
  moneylines and have finite pass contexts. Ties push in ROI and are excluded
  from binary scores.

The training rows are identical to v1.16's, so only the objective differs.

## The challenger: `margin_likelihood`

Same features, scaling, missing-value rule, two-season fit decay, penalties
(ridge 0.1, site × 0.1, contexts 0.1) and weekly refit as v1.16. What changes:

1. **Margin distribution.** Integer home-minus-away margin k ∈ [−70, 70].
   P(k | μ, σ) ∝ w(|k|) · [Φ((k+½−μ)/σ) − Φ((k−½−μ)/σ)].
2. **Key-number multipliers w.** Fixed once per scored season from strictly
   earlier seasons' training rows: for each |k| ≤ 40, observed count plus 5
   over the count the market-centered integer-normal predicts plus 5; w = 1
   beyond 40. Symmetric in sign.
3. **Dispersion σ.** Fixed once per scored season: the root mean square of
   (result − spread_line) over strictly earlier seasons' training rows.
4. **Market offset.** For each game, μ₀ is the location at which the
   distribution's conditional home-win probability P(k > 0 | k ≠ 0) equals
   the no-vig moneyline q. With zero coefficients the forecast is exactly q,
   as in v1.16.
5. **Model.** μ = μ₀ + c · Z·β, with c = σ√3/π, so β is in approximately
   logit units and the 0.1 penalties keep their v1.16 meaning.
6. **Objective.** Decay-weighted negative log probability of the observed
   integer margin plus the v1.16 ridge penalty. No grid, no selection, no
   ROI input.
7. **Forecast.** P(home win) = P(k > 0 | k ≠ 0).

`production` is v1.16 refit on the same weeks, as in the out-of-sample run.

## Pre-registered decision

Scored on all 2017–2020 scored rows; intervals are 97.5% week-cluster
bootstrap intervals as in the out-of-sample run.

* **L (log loss):** gain = v1.16 log loss − challenger log loss on binary rows.
* **U (underdog-pick units):** challenger units vs the same-row favorite minus
  v1.16 units vs the same-row favorite. Bets differ from the favorite only
  where the model backs the moneyline underdog, so this is the change in
  underdog-pick units.

**Falsified** if L ≤ 0 **or** U < 0, as the owner specified.
**Supported** only if L's interval lower bound is above 0 and U ≥ 0.
Otherwise **favored, unresolved**.

Also reported, not part of the decision: flat 1u ROI ± SE, market-correct
null, same-row favorite, Brier, log loss vs market, underdog-pick count and
units, per-season results, the fitted σ and multipliers at 3, 7 and 10.

## Scope

A favorable result would nominate a forward experiment (a new `REVISION`),
not adopt anything. Only research files are written:
`research/margin_likelihood.py`, `research/margin_likelihood_results/`,
`tests/test_margin_likelihood.py`.
