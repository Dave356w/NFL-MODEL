# Passing profile robustness protocol

Frozen before execution on 2026-10-10. Exposed historical development, not forward confirmation.
Production already uses four league-average pseudo-games. Test additional 4 and 12 pseudo-games (total 8 and 16) ONLY for raw net passing yards/pass-play profiles, in both h8 main effects and h16 contexts. Preserve decay, offseason retention, strictly prior-week league means, other features, market offset and ridge. Recompute each arm's prior-week normalization references and jointly refit weekly.

Separate tail hypothesis: clamp each normalized h16 passing profile to [-2,2] before products and 1 SD hinges, identically for training and evaluation. Test alone and combined with additional 4 pseudo-games. No probability cap or post-hoc SF-specific adjustment.

Five arms: production, profile_4, profile_12, bounded_2, combined_4_2; same-row market baseline. Evaluate 2023–25; use 2021–22 only for annual prior-season log-loss selection among all five arms. Report flat 1u ROI, SE, market-null, paired week-cluster bootstrap (98.75% for four fixed comparisons, 95% for selected), LL/Brier, annual results, production >=90% and >2 SD diagnostic slices. Slice membership frozen from production inputs; small slices descriptive only. No ROI tuning. Uncertainty excludes recipe-selection uncertainty.

Audit raw profile reproduction, all feature/reference/fit cutoffs, effective game and pass-play support (Kish of decayed observation mass), and archive replay. Archive probabilities use saved nonpassing inputs/prices and reconstructed earlier-game passing inputs, not new forward records. Save compact prior-week passing sufficient statistics for reproducible CI, source hashes, predictions and decisions under research/. Never alter production, bot data, or ledger.
