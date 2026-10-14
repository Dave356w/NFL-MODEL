# Test 41 protocol: iterations of the Test 40 ratings model

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner request 2026-10-14 ("try iterations of your model, test and report"). Committed
and pushed before any iteration below has been built or scored.

## Why a fixed ladder

Iterating on the same seasons until something looks good would mostly find luck. So every
iteration is defined here, before any is scored, and judged by one rule. A **nested-selection arm**
then picks among them each season using only earlier seasons. Its result is the honest estimate of
what iterating is worth.

## Starting point (Test 40)

`kalman_epa`: market offset + [pass_edge, rush_edge, qb_delta, site] from opponent-adjusted Kalman
EPA ratings. It was not better than production on log loss (−0.93, +2.65, −2.74 ×10⁻³). It sat within
±1.1×10⁻³ of the market and gave up production's underdog bets, and its pass-edge weight flipped
sign across eras.

## Iterations, fixed

All keep Test 40's machinery: the frozen team-game observations; Kalman filters tuned only on
2013–14 (observation likelihood); production's fit, decay, ridge 0.1 (site 0.01) and market offset;
the v1.18 penalty applied last; the same packs, row sets and bases.

1. **`k2_margin`**: Test 40's inputs plus `margin_edge`, from a one-state-per-team Kalman rating on
   final point margin (opponent-adjusted margin of victory). Margin carries what per-play efficiency
   misses: turnovers, special teams, finishing.
2. **`k3_ats`**: Test 40's inputs plus `ats_edge`, from a one-state-per-team Kalman rating on the
   margin beyond the closing spread (`result − spread_line`). It asks whether teams persistently beat
   or trail the market. Under market efficiency it carries nothing.
3. **`k4_combined`**: pass and rush collapsed into one all-play EPA rating, giving `[eff_edge, qb_delta,
   site]`. This addresses the pass-edge sign instability with fewer parameters.
4. **`k5_ridge1`**: Test 40's inputs with ridge 1.0 (site 0.1), in case its weights are noise-driven.
5. **`k6_compact`**: `[eff_edge, margin_edge, ats_edge, qb_delta, site]`, the all-in compact version.

**Selected (nested).** For each evaluation season Y from 2017 to 2025, choose among production,
`kalman_epa`, `k2`–`k6` the arm with the lowest pooled log loss over seasons 2015 … Y−1 of their
walk-forward forecasts. Use that arm's forecasts for season Y. Ties go to production. It is reported
on 2017–22 and 2023–25 only, since 2015–16 is its warm-up.

**Margin and ATS ratings.** One state per team. Observation: home value = s_H − s_A + home effect +
ε, where the home effect is the mean over strictly earlier games (2013 week 1 uses its own week).
ε has variance σ², the 2013–14 variance of the home-effect-adjusted observation. Drift q per week,
season regression ρ and prior P₀ are chosen by 2013–14 predictive likelihood over
q ∈ {0.25, 0.5, 1, 2, 4} × 10⁻³·σ², ρ ∈ {0.4, 0.6, 0.8} and P₀ ∈ {0.5, 1, 2} × the 2013–14 variance of
team-season mean margins. Margins and closing spreads come from the frozen packs (2013–20 from the
2013–20 pack, 2021–26 from the Test 36 pack); overlapping seasons must agree. Pregame snapshots only.

## Bases, metrics, decision rule

Bases (never pooled): 2015–16, 2017–22 and 2023–25, with production reproducing its published
forecasts. 2026 weeks 1–5 is a diagnostic. The metrics are Test 40's: the log-loss gain over
production (week-clustered), gain over the market, flat 1u ROI (null, same-row favorite, units vs
production, side flips) and results by total band.

Primary arms: `k2`–`k6` and Selected, so K = 6 and the interval is 99.17% (Bonferroni).
* **Better than production, worth a forward shadow test:** gain > 0 on every basis it is scored
  on, with the interval excluding zero on at least one.
* **Not better:** gain ≤ 0 on at least half of its bases.
* Otherwise **unresolved**.

Development evidence only. Adoption would be a new `REVISION` and the owner's decision.

Run: `python research/kalman_iterations.py`.
