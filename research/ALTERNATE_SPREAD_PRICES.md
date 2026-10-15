# Historical NFL alternate-spread quotes: source research (2026-10-15)

Research-only companion to [ORIGINAL_SPREAD_ALTLINE.md](ORIGINAL_SPREAD_ALTLINE.md). No production model, board, pick rule, ledger, or pregame lock is changed. These findings are sourced from **provider documentation** and public examples, not from a purchased/API-authenticated historical-quote export. The provider's sample may be illustrative. The data sources and coverage have not been independently audited.

## Main finding

The prior 3 percentage points of fair cover probability per point moved was a **scenario**, not a measured bookmaker quoting rule. There is no defensible universal cents-per-point or percentage-points-per-point schedule: relative handicap, odds tail, key 3/7, ties/pushes, game total, sportsbook, and time all matter. Actual alternate spread prices with both sides at each handicap can be retrieved from commercial archives for **2023 onward**; no qualifying actual historical alternate-spread quotes have yet been joined to the 1,438-game model replay.

## Source matrix (verified against provider documentation 2026-10-15)

| Source | Documented history | Alternate spreads | Granularity / keys | Access / limitation |
|---|---|---|---|---|
| [EndzoneAPI get_alt_lines](https://endzoneapi.com/docs/get-alt-lines) | 2023–present | `alternate_spreads` for sportsbook, team side, point, American price, capture timestamp; opening/closing ladder | NFL IDs such as `2025_01_KC_LAC`, matching nflverse-style IDs; easy to join to our `game_id` | 10 credits per NFL game; claims 500 free monthly credits (50 games); closing is last recorded pregame, **not necessarily v1.18's pregame lock timestamp**. For 2024–25 some game-day records are several hours before kickoff. |
| [The Odds API v4](https://the-odds-api.com/liveapi/guides/v4/) / [market key list](https://the-odds-api.com/sports-odds-data/betting-markets.html) | Historical additional markets after 2023-05-03; 5-minute snapshots from September 2022 | Explicit `alternate_spreads` via historical **event** odds endpoint | Provider event IDs must be joined to NFL IDs; choose nearest snapshot **at or before** the model lock time | Paid historical API; historical event market cost documented as 10 credits per market per region per event. Confirm specific sportsbook's market availability before counting games. |
| [SportsDataIO NFL docs](https://sportsdata.io/developers/api-documentation/nfl) | Subscription-dependent; no particular archived-alt coverage period independently verified | `AlternateMarketGameOddsByWeek/{season}/{week}`; `AlternateMarketGameOddsLineMovement/{scoreid}` | Native SportsDataIO ScoreIDs; mapping required | Subscription; confirm alternate ladders vs other period/alternate market naming and snapshots before purchase. |
| [Oddize](https://oddize.com/odds-api) | Claims continuously observed archive since January 2024 | `/api/v1/events/{sport}/{event_id}/alts` for available alternate spreads/totals; full quote-history endpoints | Separate IDs; check historical alt market retention and terms | Advertises 10,000 free credits monthly; no authenticated verification of NFL historical alt-ladder coverage. |

**Do not substitute** nflverse `spread_line` or the CSV's standard `home_spread_odds` and `away_spread_odds` for historical alternate prices. Those only describe the main handicap. The publicly available 1999–2025 standard-market datasets do not solve this problem.

## Published price example (not independently checked against a sportsbook ticket)

EndzoneAPI [get_alt_lines docs](https://endzoneapi.com/docs/get-alt-lines) show a sample response with DraftKings `alternate_spreads` entries for `2025_01_KC_LAC`, captured `2025-09-05T21:53:39Z`:

| Away-team handicap (book's own team-line convention) | Quoted price | Raw implied probability |
|---|---:|---:|
| −14.5 | +360 | 100/(360+100) = 21.74% |
| −15.5 | +388 | 100/(388+100) = 20.49% |
| −16.5 | +426 | 100/(426+100) = 19.01% |

Across that short tail-ladder, the **raw vig-inclusive** implied probability drops by about 1.25 and 1.48 percentage points per moved point. These sample values are **not** a calibrated model for handicaps near pick'em/3/7, and they do not establish realized payout availability at a model pick time.

The [nflverse-derived key-number tabulation](https://nflanalytic.com/betting-key-numbers.html) reports unconditional absolute final margin exactly 3 in roughly 15.1% of 1999–2025 NFL games and exactly 7 in roughly 9.0%. These are **unconditional** final margins, not the conditional probability of landing on those numbers when the market spread is near them. NFL spread pricing must preserve their discrete mass (also 6, 10 and 14). Never interpolate **linearly across 3 or 7** without a key-number-aware conditional model.

## Proposed empirical experiment (when authenticated quote data is available)

1. **Time lock:** for genuinely native picks, align quote timestamp to each `generated_utc` or decision/lock time, requiring `captured_at <= lock_utc` and a defined maximum staleness (e.g. 30 minutes). Report unavailable quotes as missing. For the **2021–2026 v1.18 replay**, forecasts are reconstructed historically and were not native locks; say that explicitly. Quotes with only "closing" dates are a *closing-quote retrospective*, not executable v1.18 locked-price returns.
2. **Book/side identity:** map `game_id`, sportsbook, selection team (`home` or `away`), market key, and absolute handicap. The model file stores `model_spread` as signed *home margin*; the bookmaker `point` is team handicap (home point = `−model_spread`, away point = `+model_spread` after chosen rounding). A sign inversion here reverses the intended wager.
3. **Same side at both lines:** select sign(`model_spread - spread_line`) as in Test 47; compare that identical team at the available standard market line and at the **nearest actually published alternate handicap**. Do **not** invent an unlisted quote. Prioritize exact half-point line; separate a ±0.5 point tolerance/extrapolation sensitivity.
4. **Same sportsbook / snapshot:** take both actual quoted odds at the same sportsbook and time; record which book, when, the offer/market IDs, and any price/trading unavailability. Compare availability % by game, year, book, target line and time.
5. **Grade and report** at **actual American price** with 1u *risked*: win profit = `odds/100` for positive American price or `100/abs(odds)` for negative; loss −1; push 0. Keep matched game cohorts; report per-year and paired season-week confidence intervals; never claim ROI on selectively quoted cases is representative of all 1,438 games.
6. **De-vig carefully:** at a fixed handicap/snapshot, pair both opposing selections when offered, convert each American price to implied probability, compute `overround = p_home + p_away − 1`. Proportional or power normalization estimates the **conditional nonpush** split, not unconditional push mass. Handle an integer handicap's push probability explicitly; report total overround by alternate-line distance and crossings of 3/7.
7. **Market-implied margin ladder:** monotonically regress fair paired probabilities by handicap and fit a discrete integer-margin distribution whose bin mass around key numbers is measured out-of-fold. Use this distribution to evaluate cover probabilities, not the model's win-probability inverse as if it were a calibrated point-margin forecast.
8. **Distinguish evidence cohorts:** 2021–2022 no 2023+ alternate archive; 2023–25 historical recipe-selected development games; 2026 W1–5 current-recipe replay; only subsequently **natively locked** 2026 games count as actual prospective picks with point-in-time quotes.

## Implementation order

- Audit **five representative games** first: a spread near 0, near ±3, near ±7, an underdog pick and a larger (>3-point) model–market discrepancy. Save all quote records from each game, not selected favorable lines. Check actual quoted point changes and overround near key numbers.
- Using EndzoneAPI's published quote format, build a read-only importer from JSON into `research/alt_spread_quotes.csv` or an untracked input location; never store API credentials.
- Repeat the original-spread-vs-market-spread paired comparison with **actual historical quotes** on matched games; keep Test 47's synthetic price assumptions as a separate benchmark.
- If sourcing a timestamp-specific archive, prefer The Odds API historical **event** odds endpoint with `markets=alternate_spreads`, exact sportsbook filters and a `date` at or before the model's lock.

**Research conclusion:** Access to NFL alternate-line ladders is documented, but pricing cannot yet be measured robustly from the repo's current `retro_ledger.csv`. The existing fixed 3pp/point backtest is an illustrative stress test, not a verified sportsbook-price backtest.
