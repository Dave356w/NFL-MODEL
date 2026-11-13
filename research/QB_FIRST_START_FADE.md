# Replacement first-start fade: fixed candidate

Owner follow-up 2026-11-13. Separate research hypothesis; no production change.
This protocol is fixed before fitting the candidate. Earlier backup residual
results are already known and count as exposed development evidence.

Use the same frozen 2021–2025 replay/input cohort and established-incumbent
replacement proxy as QB_BACKUP_RESIDUALS.md. For each projected replacement QB,
count his consecutive actual starts for this team in strictly earlier games of
this season; byes do not break the sequence. A change of actual QB or a season
boundary resets it. The target start number is one plus this prior count. This
measures current team-stint experience, not total career experience; a veteran
returning after another QB starts begins a new stint.

The single fixed exposure is replacement_flag * 2^(-(start_number-1)/2).
It equals 1 at the first start, 0.707 at the second, 0.5 at the third, and 0.25
at the fifth. Two starts is a prespecified half-life, not selected from outcomes.
It is not a claim that two starts is the true adaptation rate. Existing model
QB and team-profile adjustments remain in the baseline, so beta measures only
an additional residual correction beyond them.

Fit game-level actual home margin minus raw model projection on intercept and
(home exposure - away exposure). Estimate beta freely; do not constrain it
negative. Compare the same all-row intercept-only control and blanket replacement
term, plus the original model and same-game market/favorite/home baselines.
Train each 2023, 2024, 2025 forecast correction only on 2021 through the preceding
season; never fit the candidate with 2026 results. Use MSE gain versus intercept
only as primary, then MAE, Brier through the fixed 12.37-point normal mapping,
and flat 1u -110 ATS results descriptively. Use paired week-cluster 95% bootstrap
intervals, seed 20261113, 4,000 replicates. Report all eligible games and the same
replacement-involved games, including double-replacement games once each.

Support requires a negative pooled beta interval and positive prior-season
incremental MSE gain interval. Otherwise report unresolved or contradicted.
Do not sweep half-lives or split points after seeing results. Any future tuning
must use a new protocol and separate evidence. This tests team-stint adaptation;
it does not attribute play-calling, rushing, turnovers or field position separately.
