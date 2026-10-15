# Kalshi-only NFL pricing migration — partial, verified 2026-10-15

**Scope:** Replace sportsbook/flat-110 *pricing* inside the separate ATS research and new ATS forward-shadow comparison, with actual Kalshi prices where available. **Do not overwrite** old bookmaker source columns, price-incompatible v1.18 coefficient fits or historical forward locks. Original production winner model, frozen recipe, and append-only `data/forward_predictions.jsonl` stay unchanged pending complete coverage + new full training / validation. **No fake replacement values.**

## Documented API endpoints

Official [historical-data guide](https://docs.kalshi.com/getting_started/historical_data) requires using `GET /historical/cutoff` to route settled markets to `GET /historical/markets?event_ticker=...` and `GET /historical/markets/{ticker}/candlesticks`. Newer markets use `GET /markets?event_ticker=...` and `GET /series/{series_ticker}/markets/{ticker}/candlesticks`. `GET /events?series_ticker=...&min_close_ts=...` continues to list events after market archival.

The model's existing `kalshi.py` identifies `KXNFLGAME` winner and `KXNFLSPREAD` alternative-spread markets. Historical quote adapter: `research/kalshi_ats_prices.py`. Fresh native capture: `kalshi.py` plus `research/ats_forward_shadow.py`.

**Historical coverage limit:** Kalshi football spread/total event contracts launched in August 2025. There is no actual Kalshi NFL alternative-spread quote in 2021–24. Every unavailable game must remain excluded or tagged `unavailable` in Kalshi-only analysis, never priced at retrospective book −110 or assigned invented fair odds.

## Price point, side, and settlement convention

- Historical research quotes are **completed 1-minute candlesticks at or before kickoff minus 2 hours**, with at most 30 minutes' staleness; labeled a *retrospective cutoff*, **not** the actual first v1.18 native model lock. `yes_bid.close_dollars` and `yes_ask.close_dollars` are required; don't use last trade or settled price as a tradable bid/ask.
- Favorited home team and `spread_line=+3.5`: YES contract `home wins by >3.5`; home ATS side buys YES at its ask, away ATS side buys **NO** at `1−YES bid`. For `spread_line=−3.5`, favorite is away, with respective sides reversed. Both positions share a single contract; exact half-integer only, since integer sportsbook lines can **push**, unlike this Kalshi event contract.
- Winning margin has integer support. A contract at X.5 settles without a margin push. Expected-vs-book `P(cover)` must be evaluated at exactly the quoted contract threshold; no linear "price per point", no interpolation and no fictitious −110.
- Return per *unit risked* at YES/NO ask `a` is `+1/a−1−f(a)/a` for winning contract, and `−1−f(a)/a` for losing contract; `f(a)≈0.07a(1−a)` is a **fee approximation**. Real venue fee schedule, rounding, depth, partial fills and slippage still need confirmation.
- Original model alt target: nearest advertised half-integer threshold to `abs(model_spread)`; choose the original model's market-ATS **same side**, YES or NO as appropriate. Only an exact listed, time-matched alternative contract can be graded. No guess when missing.
- Winner markets: separate YES asks for home and away. In the existing forward comparison, a final tied game has a $0.50 outcome, not an NFL "push" in a fixed-priced book; explicitly grade `0.5/ask−1−fee`.

## API smoke test completed (October 15, 2026)

[Audited GitHub run for five 2025 Week 1 games](https://github.com/Dave356w/NFL-MODEL/actions/runs/38826039620) fetched historical candlesticks, archived/active market metadata, resolved game IDs, and uploaded a three-file artifact.

| Item | Available |
|---|---:|
| Both Kalshi winner asks | 5/5 |
| Exact Kalshi main-line ATS ask/NO complement | 4/5 |
| Nonmatching integer sportsbook spread | 1/5 |
| Original signal across matched 4 (fee-adjusted, descriptive) | −1.0408u |
| Fixed-band signal across matched 4 (fee-adjusted, descriptive) | +0.8125u |

**These four results are smoke-test coverage, not model validation or an ROI claim.** They are conditioned on available Kalshi lines. The original 2021–26 895-game assumed −110 result is not directly comparable to this sample.

The workflow `.github/workflows/kalshi-ats-prices.yml` can be dispatched with NFL season (2025/2026), week and maximum games. It builds a refreshed historical Test 48 prediction table, fetches Kalshi markets/candlesticks, then exports raw audit rows, matched main-spread ATS grading, original-model alternate-spread results and Kalshi winner price grading. No API key is needed for these public-market-data endpoints. Each row preserves market ticker, contract side, ask and price timestamp.

## New forward ATS shadow

Starting after the previously registered shadow launch cutoff, `research/ats_forward_shadow.py` reads only `data/kalshi_snapshots.jsonl` records captured **after** a newly locked forecast and within 30 minutes, before kickoff. It chooses the identical game, favorite and exact half-integer strike, stores both YES and implied NO asks, both winner asks (if available), the captured timestamp, and its source snapshot hash.

The probability decision uses `P(cover)` at the observed Kalshi ask with the fee proxy. No matching price means `probability_side=""`, `quote_basis="no_matching_kalshi_quote"`; no −110 substitution. Research-only graded returns `*_units_kalshi` are calculated using the recorded quote. The 2026 native winner model continues unchanged, and old locked predictions remain untouched.

## Not yet done / important distinction

1. **Full archive backfill, 2025 onward**, and coverage diagnostics by season, week, time, sportsbook main line, Kalshi threshold and missingness (limited to five-game audit so far); the API provides retrievable data but exact quote coverage over whole seasons is unverified.
2. **Production replacement of underlying market features:** v1.18 was fitted using nflverse sportsbook moneylines and spread inputs in prior seasons. Swapping a few current-season price rows under a frozen recipe would be a different, unvalidated model. 2021–24 Kalshi spread data are nonexistent. Proper Kalshi-only refit requires a new cohort start after Kalshi market availability, adequate training history, and a separately identified revision; do not silently relabel the existing v1.18 as Kalshi-trained.
3. **Historical point-in-time accuracy**: 2h pregame research quote does not equal when an old model was genuinely locked. Archive bid/ask candle is a summary of that minute, not guaranteed executable size at the candle close. PnL is approximate.
4. **Live Kalshi capture is distinct from model feature lock**: forward shadow requires a quote after the pregame forecast; this is marked so it cannot be called the model's original lock price.
5. A model expected scoring margin is **not** a calibrated cover probability. Test 48 found tiny unresolved score gains and negative ROI at −110. Re-estimate price-adjusted cover events on a Kalshi-only cohort before ranking selections.

**Current decision:** observed Kalshi prices replace hypothetical bookmaker prices **inside the new matched research grade and native shadow**. The full production/historical sportsbook-price replacement remains **incomplete** and must not be represented as delivered until the distinct Kalshi-supported backtest and quote coverage pass.
