# Test 51 protocol: a market-only median map, fitted on 2022–24 and tested on 2025–26

Research only. Production v1.18, the median map (`fixed_bands.py`), the lock policy, `data/` and the
ledgers are unchanged. Owner design 2026-11-03: "fit a median map only on pregame market lines for
spread and totals vs actual MOV ... no model inputs"; "fit on 2022–2024 and test on 2025–2026". This
protocol is committed and pushed before the map is fitted or scored.

## Question

Can a median map built from market lines alone (no model input) pick ATS sides on later seasons? It
also gives the cleanest "what does the line alone do" control for the production map. The current
ledger control pushes the line through the model-fitted magnitudes.

**Disclosed exposure.** 2022–2026 were already seen on 2026-11-03: the exploratory market-only line-band
and line × total distribution-mass analyses (2006–2026; walk-forward, about a coin flip at −4% ROI) and
Test 50. 2026 is the current season. This is development evidence, not forward confirmation.

## Data

nflverse `games.csv` regular season, 2022–2026, games with a final result. `spread_line` (positive =
home favored) and `total_line` (capture time unknown, close to kickoff). Frozen in
`research/market_median_map_inputs/` with the source SHA-256. Fit seasons 2022–2024, fitted once.
Test seasons 2025 and 2026 to date, reported separately and pooled.

## Arms (fitted once on 2022–24; pick'em lines excluded from the fit)

Production's bands on the absolute line, |spread| in [0,3), [3,7), [7,10), [10,∞). The favorite's
margin is `sign(spread_line) × result`; ties count as zero. Each band needs at least 30 fit games.

* **A, spread only:** magnitude = median favorite margin in the band. Mapped home margin =
  `sign(spread_line) × magnitude`.
* **B, spread × total:** the same per band × total half. The split is the fit games' median total (a
  total equal to the split counts as low). A cell with fewer than 30 fit games uses A's band magnitude.

Selection is `fixed_bands.pick` against the same line. **Primary tie rule:** production's (zero edge
takes the favorite; a pick'em line with a zero mapped spread skips). **Secondary:** ties skip.

## Metrics

* **Point forecast:** absolute-error gain of the mapped margin over the raw market line,
  `|line − result| − |mapped − result|` (positive = map better). A median minimizes absolute error, so
  the line, the market's own forecast, is the hurdle. 95% season-week cluster bootstrap (2,000 draws,
  seed 20261103).
* **ATS at −110:** W-L-P, skips, units, ROI ± SE (pushes in the denominator), cover excluding pushes, n,
  break-even 52.4%. Same-row baselines: always favorite, always underdog, always home.
* **References on the games in `data/latest/fixed_band_ledger.csv`** (frozen copy): the production
  median map (model input) and the line through production's per-season model-fitted map (the current
  ledger control), with paired units against arm A.
* **Descriptive:** fitted magnitudes and cell counts; results by band and total half.

## Verdicts (stated in advance; pooled 2025–26)

* **Point forecast:** "beats the line" if the 95% interval of the gain lies above zero; "worse than the
  line" if it lies below; otherwise "no detectable difference".
* **ATS:** "beats −110" if ROI − 2 SE > 0; "loses to −110" if ROI + 2 SE < 0; otherwise "unresolved".
  Break-even is ROI 0 (cover 52.4%).

Nothing here changes production. A market-only ATS rule or a new ledger control would be the owner's
decision and a new policy version.

## Outputs

Script `research/market_median_map.py`; tests `tests/test_market_median_map.py`; inputs
`research/market_median_map_inputs/`; results `research/market_median_map_results/` (REPORT.md).

Run: `python research/market_median_map.py --freeze GAMES_CSV`, then `python research/market_median_map.py`.
