# Test 57 protocol: a vig-aware map for picking underdogs worth the points

Research only. Production v1.19, the median map, lock policy v2 and the forward ledger are unchanged. Owner request
2026-11-04: the median map exists to pick which underdogs are worth the points; fit it with that goal. This protocol is
committed and pushed before any arm below is computed.

## Why the median is misaligned with the goal

The median rule bets the model side whenever its estimated cover chance is above 50%, bets every game, and sends exact
ties to the favorite. At −110 a side is worth a bet only if it covers at least 1.1/2.1 = 52.381% of decided games. The
arms below keep production's data and bands and change only the decision.

## Fit (prior seasons only, same rows as production)

Bands, training rows and minimums are production's (`fixed_bands.fit`): |raw spread| cut at 3, 7 and 10; strictly
earlier seasons; finite model spread and result; model spread ≠ 0; at least two seasons, 300 games and 30 per band.
Work in model-side terms: s = sign(raw spread), signed margin S = s × result, model-side line ℓ = s × market spread
(positive when the model side is the market favorite). The model side covers when S > ℓ, the other side when S < ℓ,
and S = ℓ is a push.

For a game in band k with line ℓ, from band k's training margins:
p_model = #(S > ℓ) / #(S ≠ ℓ), p_other = 1 − p_model.

## Arms (fixed here)

| Arm | Decision |
|---|---|
| P production | median map, zero edge takes the favorite (policy v2) |
| V vig-aware | bet the model side if p_model ≥ 0.52381; else the other side if p_other ≥ 0.52381; else skip |
| U underdog-only | V, but skip any bet on the market favorite (and pick'em lines) |

A check, not an arm: V with the threshold set to 0.5 should mostly agree with P; the agreement rate is reported.

## Bases, never pooled

* **2016–22:** v1.19 replay, fits on the replay's earlier seasons from 2014 (as Tests 54–56).
* **2023–26:** production's v1.19 ledger, fits on 2021+ history (as production).

**Exposure: both bases are fully exposed.** Tests 54–56 and the follow-up breakdowns reported production's underdog and
favorite picks by band and period on these seasons (map underdog picks covered 51.9% on 2016–22 and 52.8% on 2023–26).
The threshold is fixed by the price, not tuned. This test is descriptive; only forward locks can confirm.

## Contrasts and verdicts

Units against P on the same games (skips count 0), summed, SE from per-game differences. Two contrasts (V − P, U − P),
so the bar is |z| ≥ 2.24.

* **Favored over P:** positive with z ≥ 2.24 on one basis and positive on the other.
* **Worse than P:** negative with z ≤ −2.24 on either basis.
* **Unresolved:** otherwise.

Goal measure, reported with the verdicts: cover rate of U's bets against 52.4% and against all underdogs on the same
games, per basis.

## Reported

Per basis and season, for P, V and U: W-L-P, skips, bets, units, ROI ± SE (pushes in the denominator), cover rate, n,
break-even 52.4%, same-row always-favorite and always-home baselines, and the share of bets on underdogs; max drawdown
and longest weeks under water on weekly units; bets by band.

## What a result means

Diagnostic only. V or U would be a new ATS policy version and the owner's decision; both stay fitted to prior-season
margins. A favored arm would next run as a reporting-only arm on native v1.19 locks, reviewed at 100 decided locks.

Run: `python research/vig_aware_map.py`.
