# Seasonal rule uncertainty

1451 games; 31680 planned contrasts, 25186 nondegenerate available contrasts.
9,999 paired whole-week resamples within season; simultaneous 95% max-standardized-deviation critical value 4.355.

Full 2021–2026 rule, including partial 2026: 0 point-estimate passes and 0 simultaneous-evidence passes across feature/policy combinations.
Completed 2021–2025 only: 0 point-estimate passes and 0 simultaneous-evidence passes.

The narrower common 2023–2026 window has 1 ATS-only point-estimate pass; 0 joint passes. It is a secondary diagnostic, not the six-season promotion rule.

Positive gains mean lower loss or higher ROI. LL and Brier each compare with both moneyline and spread/total probabilities. ATS compares positive ROI, the same-path anchor policy, and the favorite; always-home is diagnostic only.
Each ROI ratio resamples its own return numerator and stake denominator. Pushes count as stakes; skips do not. Candidate, comparator and common-stake counts are retained for every contrast. Missing early median policies remain unavailable.
Median unavailability in 2021–2022 is a coverage limitation, not evidence of losses: this experiment starts candidate forecast history in 2021. Earlier chronological forecasts would be needed to fit candidate maps for those early years.
The simultaneous family includes all available feature, season, metric, comparator and ATS-path contrasts, including home diagnostics. A zero empirical SE receives no positive-evidence verdict.

These intervals condition on already fitted, historically exposed forecasts. They do not include model-refitting uncertainty, undo earlier design selection, or establish a future betting edge. The partial 2026 season has few independent week clusters; this bootstrap is approximate and is not exact small-sample inference.
Requiring improvement in every season is an intersection rule. One small or noisy season can prevent certification even when average performance improves. Ranking variants by their weakest year and then treating that selected minimum as fresh evidence would add selection bias. No candidate is nominated by this uncertainty module.

Files: `contrasts.csv`, `candidate_evidence.csv`, and `audit.json`.
