# Selection-adjusted benchmark

Basis: Exposed 2023-2025 held-out walk-forward; fixed committed forecasts; not forward evidence.

Across 53 committed arms on the same 809 games, if the market were exactly right the best arm would beat the same-row favorite by a median +16.7u by luck alone (95th percentile +44.7u).
Observed best: market_residual:pass_total beats it by +46.1u (market-correct p 0.042; Reality Check p 0.037). v1.16 beats it by +30.6u (p 0.180 against the best-arm null; 0.007 unadjusted). v1.17 beats it by +46.1u (p 0.042).
Log loss: best arm margin_total:pass_market_total gains +0.0035 over the market (market-correct p 0.047; Reality Check p 0.697).
Forecasts are fixed and only committed arms are included. Many more configurations were tried, so the real selection adjustment is larger and these p-values are optimistic.

Seed 20261013; 20000 market-correct draws; 10000 week-cluster bootstrap draws. Per-arm observed values are in `arms.csv`.

Run: `python research/selection_benchmark.py`.
