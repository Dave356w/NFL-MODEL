# Test 47 (exploratory): original model spread as an alternate line

Research-only analysis of the committed `data/latest/retro_ledger.csv`. **Not a new production selection rule, and not executable betting returns.** Written **after** the 2021–2026 outcomes and the alternate-price sensitivity had already been examined. No preregistered claim is made. Production `nfl_model.py`, fixed-band rules, site, and forward ledger are unchanged by this research.

## Question

Instead of backing the original model's ATS-selected team against the *market spread* at an assumed −110, back that **same team** against the model's **own original implied spread**, treated as a hypothetical alternative handicap. Does the extra payout assumed for accepting a tougher line cover the reduction in wins?

This specifically uses `model_spread` (the original v1.18 probability-to-margin transformation) **not** the optimized `fixed_band_spread`. Selection is `sign(model_spread − spread_line)`; positive = home side, negative = away side. The market spread is in home-margin sign convention (positive favors home).

## Reproducible pricing and grading

- Market benchmark: one unit **risked** at −110 on the original ATS-selected side, `+0.9090909u` for a win, `−1u` for a loss, `0` for a push.
- Proposed alternate handicap: round `model_spread` to the nearest **0.5 point**, preserving the selected team. The alternate is a tougher handicap than the market's for the selected side, unless rounding produces the same line.
- Assume fair nonpush cover probability at the moved line drops **3 percentage points per adverse point**, from 50% at the market spread: `p_fair_alt = 0.5 − 0.03 × abs(alt_spread − market_spread)`.
- **Hold constant at every point:** apply the original two-sided −110/−110 implied-probability multiplier `110/105 = 1.047619`, so `p_quote = p_fair_alt × 110/105`, and win profit per 1u risked is `1/p_quote − 1`. With no movement this is exactly −110.
- Primary feasibility diagnostic: exclude raw `abs(model_spread − spread_line) > 7` points. This is a **research diagnostic cap, not evidence that books offer all lines within it**. Six observations excluded. No observed alternate odds are available.
- Grade against final home-minus-away margin using identical games for both strategies; any exactly matching line pushes and refunds the stake. Market pushes can differ from alternate-line pushes.
- Sensitivities: a flat probability slope of 2, 2.5, 3, 3.5 or 4 percentage points per point; exact unrounded model spread versus half-point executable-style rounding. Same seven-point gap restriction throughout.
- Paired ROI interval: normal approximation using season-week clustered residual sums over the same games (95%; descriptive/exploratory, not multiplicity adjusted).

Run: `python -m research.original_spread_altline`. To audit every proposed quote/pick: `python -m research.original_spread_altline --export /tmp/alt_spread_picks.csv`.

## Main results: rounded half-point handicap, 3 pp per point, gap ≤ 7

| Period | Games | At market spread W–L–P | Market units / ROI | At model-spread alt W–L–P | Alt units / ROI | Alt − market ROI |
|---|---:|---:|---:|---:|---:|---:|
| **All 2021–2026** | **1,432** | **700–693–39** | **−56.64u / −3.96%** | **660–747–25** | **−59.71u / −4.17%** | **−0.21 pp** |
| 2021 | 270 | 131–135–4 | −15.91u / −5.89% | 124–142–4 | −13.40u / −4.96% | +0.93 pp |
| 2022 | 271 | 125–136–10 | −22.36u / −8.25% | 117–147–7 | −24.39u / −9.00% | −0.75 pp |
| 2023 | 270 | 124–132–14 | −19.27u / −7.14% | 116–148–6 | −31.58u / −11.70% | −4.56 pp |
| 2024 | 271 | 137–130–4 | −5.45u / −2.01% | 132–137–2 | −0.35u / −0.13% | +1.88 pp |
| 2025 | 272 | 147–124–1 | +9.64u / +3.54% | 137–130–5 | +17.43u / +6.41% | +2.87 pp |
| **2026 replay W1–5** | **78** | **36–36–6** | **−3.27u / −4.20%** | **34–43–1** | **−7.41u / −9.50%** | **−5.31 pp** |

**Paired result:** −0.21 percentage points on 1,432 games. Approximate season-week-clustered 95% confidence interval **[−1.81, +1.38] pp** (95 clusters). No clear improvement. The model-line wager wins fewer bets and its compensating hypothetical payout is insufficient at the 3 pp/point assumption.

## Price-per-point sensitivity (same 1,432 games, rounded to half-points)

| Price sensitivity: fair-probability decline per point | Alt units | Alt ROI | Alt minus market ROI |
|---|---:|---:|---:|
| 2.0 pp/point | −91.53u | −6.39% | −2.44 pp |
| 2.5 pp/point | −76.03u | −5.31% | −1.35 pp |
| **3.0 pp/point (primary)** | **−59.71u** | **−4.17%** | **−0.21 pp** |
| 3.5 pp/point | −42.45u | −2.96% | +0.99 pp |
| 4.0 pp/point | −24.10u | −1.68% | +2.27 pp |

An exact, **unrounded** model spread at 3 pp/point is −4.40% ROI, versus the same −3.96% market comparator (−0.45 pp). This illustrates rounding sensitivity and is not a routinely quoted sportsbook line.

Of the 1,432 eligible games, **244** round back to the market handicap, making the pair identical. On the remaining 1,188, a real alternate sportsbook quote is needed before assessing tradability.

## Critical uncapped pricing failure

There are six discrepancies greater than seven points. One game, `2023_16_BAL_SF`, had `spread_line=+6.5`, `model_spread=−12.66` and realized home margin −14. With the 3 pp/point *linear probability* rule, rounding gives a **19-point shift** and a theoretical win profit of **+189.91 units** (approximately American **+18,991**), a clearly implausible extrapolated quote. The uncapped backtest would then misleadingly read **+8.71% alternate-line ROI** against −4.22% at the market line across 1,438 games. **Do not treat that figure as evidence.** The seven-point cap and slope sensitivity expose why a result depends entirely on pricing assumptions.

## Interpretation and limitations

1. **No observed alternate prices.** The assumption preserves a mathematical bookmaker overround, **not real NFL line-by-line quoting**. Real odds per point are nonlinear, especially at key margins of 3 and 7; a constant price slope can be wrong even for modest moves.
2. The -110 ATS baseline is also a common proxy, not saved ATS quote data. Prices and lock times are not matched to a real alternate market.
3. Market spreads need not be calibrated means of a score-margin distribution. The projected `model_spread` comes from a win-probability inversion, not an independently validated cover-distribution forecast.
4. **Exposed history:** 2021–2025 are development/backtest seasons selected with outcomes already seen. The 2026 Weeks 1–5 block is replayed under current v1.18, not previously locked native v1.18 ATS wagers. The live Week 6 game is excluded while ungraded.
5. No transaction frictions, stake limits, voided quotations, missing alt markets, liquidity or line shopping are incorporated.

**Decision:** do not promote this to the board as a validated ROI improvement. At 3 pp per adverse point it loses 0.21 pp ROI against the original-side market-spread wager, with broad uncertainty; the sign is highly dependent on imagined prices. Collect actual sportsbook alternate spread/odds snapshots before betting or interpreting any apparent positive backtest. Maintain research-only status.
