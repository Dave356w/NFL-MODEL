# Favorite-penalty forward verdict: operating characteristics

`python research/forward_monitoring.py`. Outcome-free with respect to the forward ledger: it uses
the historical per-game spread of the penalty's log-loss gain (2017–20 and 2021–25; SD 0.070,
effective 0.084 after the week-cluster design effect) and the January checkpoints (about 206, 478,
750, 1,022 and 1,294 graded native v1.16 games). Each cell is the probability of that verdict by
that look, with the first decisive verdict standing (20,000 simulated paths).

Full table: `operating_characteristics.csv`. The adopted rule is "proposed z=2.24, delta=+0.002",
recorded in the `FAVORITE_PENALTY.md` addendum of 2026-10-15.
