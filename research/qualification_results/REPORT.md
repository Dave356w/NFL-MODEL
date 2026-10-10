# Production model qualification backtest

**Production status: not qualified by native forward evidence.**

Backtest-passing families: none. Forward-test nomination: **market_product**.

Basis: exposed historical development, 2023–2025; 815 proper-score games and 812 common flat-1u bets.

## Betting qualification

Primary intervals: 99.1667% week-cluster bootstrap, Bonferroni across six families; 8,000 draws. Bounds below are percentage points.

| Candidate | W–L–P | Units | ROI ± SE | Market-correct null | ROI interval | Difference vs favorite interval | Null-excess interval | Gate |
|---|---:|---:|---:|---:|---|---|---|---|
| production | 547–264–1 | +16.30 | +2.01% ± 2.65 | -4.10% | [-5.25, +9.53] | [-4.02, +8.13] | [-1.15, +13.63] | unresolved |
| market_additive | 555–256–1 | +0.18 | +0.02% ± 2.47 | -4.10% | [-6.88, +6.97] | [+0.00, +0.00] | [-2.78, +11.07] | unresolved |
| market_product | 554–257–1 | -1.11 | -0.14% ± 2.47 | -4.10% | [-7.12, +6.63] | [-1.77, +1.50] | [-3.03, +10.72] | unresolved |
| market_qualified | 556–255–1 | +3.73 | +0.46% ± 2.48 | -4.10% | [-6.18, +7.02] | [-2.00, +2.67] | [-2.08, +11.11] | unresolved |
| market_extreme | 558–253–1 | +6.88 | +0.85% ± 2.47 | -4.10% | [-6.29, +7.88] | [-0.41, +2.35] | [-2.19, +11.98] | unresolved |
| fixed_market_product | 562–249–1 | +19.32 | +2.38% ± 2.49 | -4.10% | [-4.34, +8.97] | [-1.83, +6.79] | [-0.24, +13.07] | unresolved |
| q | 555–256–1 | +0.18 | +0.02% ± 2.47 | -4.10% | [-6.88, +6.97] | [+0.00, +0.00] | [-2.78, +11.07] | control |

The gate requires all three lower bounds above zero: net profitability, superiority to the market favorite on identical games, and performance beyond the selected-side market-correct null. A positive point estimate is insufficient.

## Probability forecasts

| Candidate | Log loss | Brier | LL gain vs market [95% CI] |
|---|---:|---:|---|
| production | 0.631630 | 0.220190 | -0.023558 [-0.034909, -0.012241] |
| market_additive | 0.608005 | 0.210290 | +0.000067 [-0.000298, +0.000429] |
| market_product | 0.606162 | 0.209390 | +0.001910 [-0.000285, +0.004004] |
| market_qualified | 0.607887 | 0.209938 | +0.000185 [-0.004666, +0.004716] |
| market_extreme | 0.607723 | 0.209985 | +0.000349 [-0.002737, +0.002934] |
| fixed_market_product | 0.607584 | 0.209859 | +0.000488 [-0.006290, +0.007375] |
| q | 0.608072 | 0.210334 | +0.000000 [+0.000000, +0.000000] |

## Season consistency

| Candidate | Season | Bets | ROI | Log loss |
|---|---:|---:|---:|---:|
| production | 2023 | 270 | -0.09% | 0.656505 |
| production | 2024 | 271 | +12.57% | 0.605772 |
| production | 2025 | 271 | -6.46% | 0.632615 |
| market_additive | 2023 | 270 | +1.53% | 0.627573 |
| market_additive | 2024 | 271 | +5.21% | 0.587161 |
| market_additive | 2025 | 271 | -6.66% | 0.609286 |
| market_product | 2023 | 270 | +1.53% | 0.627397 |
| market_product | 2024 | 271 | +4.60% | 0.586167 |
| market_product | 2025 | 271 | -6.53% | 0.604916 |
| market_qualified | 2023 | 270 | +2.24% | 0.627600 |
| market_qualified | 2024 | 271 | +5.93% | 0.584819 |
| market_qualified | 2025 | 271 | -6.78% | 0.611254 |
| market_extreme | 2023 | 270 | +1.53% | 0.627279 |
| market_extreme | 2024 | 271 | +6.22% | 0.588336 |
| market_extreme | 2025 | 271 | -5.20% | 0.607552 |
| fixed_market_product | 2023 | 270 | +1.43% | 0.636443 |
| fixed_market_product | 2024 | 271 | +7.09% | 0.581645 |
| fixed_market_product | 2025 | 271 | -1.38% | 0.604652 |
| q | 2023 | 270 | +1.53% | 0.627349 |
| q | 2024 | 271 | +5.21% | 0.587489 |
| q | 2025 | 271 | -6.66% | 0.609383 |

## Selected forward specification

```json
{
  "arm": "market_product",
  "key": "market_product__rates_core_adj_avail_cs_peaks_nosacks_h4_r10__i0.01",
  "recipe": {
    "arm": "market_product",
    "family": "rates_core_adj_avail_cs_peaks_nosacks",
    "half_life": 4.0,
    "ridge": 10.0,
    "interaction_ridge": 0.01
  },
  "selection_through_season": 2025,
  "status": "unqualified_forward_candidate",
  "market_offset": true,
  "market_quote_contract": "first qualifying pregame snapshot; input and grading use same moneylines",
  "pass_profile_half_life": 16.0,
  "normalization": "prior-week season center; trailing-four-season SD; orientations pooled",
  "coefficient_refit": "weekly, earlier weeks only, two-season fit decay",
  "extras": [
    "product"
  ]
}
```

This nomination is selected using exposed development results, not confirmed evidence. Hyperparameters are frozen in nominated_candidate.json; coefficients may refit weekly under the recorded rule. No production recipe or ledger was changed and live capture is not activated.

## Limits and reproduction

Historical market quotes have no independent capture timestamp; this is a closing-price benchmark. A prospective test must capture both market input and grading price before kickoff. Feature design already used these evaluation seasons. Bootstrap intervals condition on the fitted selection process and do not capture all design uncertainty.

Run `python research/production_qualification.py`. Full candidate grids, feature caches and fit timing audits are kept under .nfl_cache or the specified cache directory; compact per-game evaluation predictions, selections, input/source hashes and results are committed alongside this report. See research/PRODUCTION_QUALIFICATION.md for the fixed protocol.
