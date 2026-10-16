# ARCHIVED: Kalshi-only NFL pricing migration experiment (October 15, 2026)

> **ROLLED BACK (2026-10-15):** This document describes a completed research experiment, **not the active website or pick/ATS logic**. The site, native ATS shadow, and default price displays were restored exactly to commit [`608ffb7b22`](https://github.com/Dave356w/NFL-MODEL/commit/608ffb7b22344f955bab1bf01920f16b7a9b3d0b). Kalshi-only migration actions were disabled. The historical Kalshi API artifacts remain in `data/kalshi_historical/` solely for reproducibility. The legacy native Kalshi secondary snapshot mechanism, which predated this experiment, was restored too.



## Status and definition

**Kalshi quotes are now the primary, observed price source** for the current site board and for the historical **2025–2026** winner, Kalshi-defined main-spread and model-target alternate-spread *pricing/settlement* evaluation. Older sportsbook valuation is retained only under clearly labeled **legacy** sections/files so pre-2025 forecasts can be reproduced. All existing model forecasts and first pregame locks are preserved.

**Important technical limit:** The underlying **v1.18 probability model is not re-trained solely on Kalshi features**; some frozen model inputs and historical coefficient fits are based on the prior nflverse/bookmaker data. Kalshi's NFL spread markets did not exist for 2021–2024, so a genuine fully Kalshi-trained 2021–26 backtest or equivalent recalibration is not possible. Do not label the frozen model Kalshi-trained.

## Completed 2025–2026 API backfill

[Full backfill workflow](https://github.com/Dave356w/NFL-MODEL/actions/runs/38827189182): 23 separate weekly API retrieval jobs (2025 Weeks 1–18 and completed 2026 Weeks 1–5), **all passed**, plus successful merge and commit. Output is persisted and source auditable:

- `data/kalshi_historical/kalshi_quotes.csv`: 351 quote/game rows with game ID, Kalshi tickers, YES/NO ask, threshold, cutoff and actual source timestamp, missing/quote status.
- `data/kalshi_historical/kalshi_moneyline_graded.csv`: model-selected winner contract at Kalshi YES ask, including $0.50 tie settlement.
- `data/kalshi_historical/kalshi_ats_graded.csv`: original and fixed-band sides compared against **Kalshi's own quoted spread**, plus original-model target alternate contract if available. Final score is graded relative to the actual contract strike, not to a sportsbook handicap.
- `data/kalshi_historical/kalshi_summary.json`: counts, coverage and money-at-risk ROI; reproducible via `research/kalshi_backfill.py`.

Coverage of this *reconstructed model-pick* cohort:

| Year | Graded games | Winner quote pairs | Kalshi main-spread offers | Original-model target alternate offers |
|---:|---:|---:|---:|---:|
| 2025 | 272 | 272 | 272 | 170 |
| 2026 W1–5 | 79 | 79 | 79 | 67 |
| **Total** | **351** | **351** | **351** | **237** |

**The 237 alternates are a separate availability-selected subset**. Do not compare their ROI directly with an all-games strategy without restricting both to the same games.

## Observed price-based results

All results use actual captured Kalshi asks, $1 risked per contract, a *proxy* fee of `0.07 × price × (1 − price)` charged on entry and no slippage. Source timestamp is a completed one-minute bid/ask candle at or before **kickoff minus 2 hours**, max 30 minutes old. This is a fixed *research cutoff*, not the time at which each legacy model prediction was really locked.

| Season | Market | Bets | Units | ROI |
|---|---|---:|---:|---:|
| 2025 | Model winner YES | 272 | −1.28 | −0.47% |
| 2025 | Original ATS, Kalshi main | 272 | −1.25 | −0.46% |
| 2025 | Fixed-band ATS, Kalshi main | 272 | −4.92 | −1.81% |
| 2025 | Original-model alt | 170 | −2.98 | −1.75% |
| 2026 W1–5 | Model winner YES | 79 | −4.95 | −6.26% |
| 2026 W1–5 | Original ATS, Kalshi main | 79 | −7.40 | −9.36% |
| 2026 W1–5 | Fixed-band ATS, Kalshi main | 79 | +2.39 | +3.02% |
| 2026 W1–5 | Original-model alt | 67 | −1.09 | −1.63% |
| **Combined** | **Model winner YES** | **351** | **−6.23** | **−1.77%** |
| **Combined** | **Original ATS** | **351** | **−8.64** | **−2.46%** |
| **Combined** | **Fixed-band ATS** | **351** | **−2.53** | **−0.72%** |
| **Combined** | **Original-model alt** | **237** | **−4.08** | **−1.72%** |

These outcomes are **exploratory after historical exposure** and insufficient to establish edge. All four combined point estimates are negative. A prior four-game smoke test priced the main Kalshi contract but reused the bookmaker spread W/L result and is **superseded** by this corrected Kalshi-native settlement backtest.

## Implemented price convention

- Historical `research/kalshi_ats_prices.py` reads `KXNFLGAME`, `KXNFLSPREAD` events and archival/live historical candlesticks. It only uses **completed one-minute bid/ask candles**, never an after-game settlement price, and records quote timestamp and source ticker. Queries are routed to active or archived partitions.
- Kalshi main handicap is selected using the **closest-to-50% contemporaneous favorite YES midquote** across up to the 8 offered strikes nearest the spread magnitude suggested by the Kalshi winner market. No sportsbook main handicap is used to select the *priced* benchmark; its remaining column is only a legacy diagnostic. This defines a **research heuristic**, not an official venue canonical main line; alternative choices may change ATS picks and ROI.
- A positive `kalshi_spread_line` means a Kalshi contract on the home team's winning margin above its half-point strike; a negative line means the away favorite. Home and away ATS picks are YES and the opposite NO with ask `1 − YES bid`. Integer sportsbook lines are not mapped to imaginary pushes; all Kalshi ATS grades come from an **actual binary contract threshold**.
- Original-model alternate: the model's forecasted signed margin identifies the favorite and target half-point; its side is selected by discrepancy from Kalshi **market** threshold, not the bookmaker line; ask/YES/NO and exact contract settlement separately captured. No interpolation or fixed "price per point".
- Current `kalshi.safe_live_board` refreshes actual order-book winner and spread ladders for pregame games. `build_site.py` shows live Kalshi asks and market line only when source quote is within 4 hours, otherwise **"Kalshi quote unavailable"**. It never populates current price from the old schedule's bookmaker moneylines.
- Native forward `research/ats_forward_shadow.py`: first future snapshot and quote no more than 30 minutes after lock. **Absent quote means no priced candidate**. Existing locked predictions remain unchanged, and quotes after the snapshot are explicitly marked.

## Mandatory limitations / no false full replacement

1. **2021–2024 Kalshi NFL spread prices do not exist**, so those past games cannot be assigned an actual Kalshi price. Old sportsbook backtests are kept only as **legacy research**.
2. **The v1.18 model's underlying training features were built with sportsbook-market history.** Changing price displays and grading does not retroactively re-train coefficients. A new independently identified Kalshi-trained model would require sufficient data from its 2025+ launch and later genuinely forward results.
3. A completed-minute candle's bid/ask does not guarantee the displayed quote could fill one or more contracts at the exact minute close. Fee proxy ignores per-order rounding, depth, and slippage.
4. The quote cutoff is a retrospective common time, not each model's contemporaneous original lock. Hindsight recipe selection remains an additional source of leakage.
5. The Kalshi main-spread selection heuristic and quote availability are research definitions, not market-standard bookmaker spreads. Preserve them as versioned inputs, not assumptions about an official "market line".
6. **No automatic migration of immutable historical predictions:** old pregame snapshot price fields and native forward ledgers stay untouched by design; new versioned quote records reference them separately.

**Conclusion:** Full Kalshi price acquisition and Kalshi-contract settlement comparison are completed for every graded 2025–2026 game currently available to the model. Kalshi-only training for older NFL seasons remains structurally impossible. Production probability coefficients remain frozen until a legitimate forward redesign is validated.
