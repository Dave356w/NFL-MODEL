# Qualified pass interactions: protocol fixed before execution

Written 2026-10-10 UTC; base commit 966b308bb1be06ecaa9b0ec81f9897345dd4ac60.
This is a new development experiment after exposure to Tests 24 and 25, not
independent forward confirmation. Production and all ledger files stay intact.

Question: Does preserving offense/defense direction and relative magnitude
improve over a shared product interaction and additive production features?

Sources: nflverse regular-season schedules and play-by-play 2019–2025;
production v1.15 lagged profiles and availability reconstruction. Main effects
use the current raw production family, profile half-life 8, ridge 0.1, held
constant across arms. These settings were selected previously on these seasons;
the comparison is development evidence, not a fresh pristine holdout.

All fits use strictly earlier weeks; predictions begin 2021. Report evaluation
on 2023–2025, each season's interaction penalty selected by mean walk-forward
log loss in earlier 2021+ seasons. Penalty candidates 0.01, 0.1, 1, 10.
Additive coefficients and interaction coefficients are jointly refit weekly.

Pass descriptors use half-life-16 raw net passing yards per dropback (sack yards
and sacks included), matching H4. Center each offense/defense role using that
season's earlier-week pregame profiles, pooling both team orientations; before
any current-season profiles, use prior-season profiles. Scale from earlier-week
profiles in trailing four seasons. These reference distributions contain no
current-week data or future seasons. Same normalization for both orientations.

Arms: additive baseline; shared product; four sign-qualified hinge products;
four extreme hinge products beyond ±1 SD. Hinge terms are home attack against
away defense minus away attack against home defense. Positive defense-allowed z
means permissive defense. Retain main effects. Four-sign arm captures continuous
magnitude with separate strong/permissive, strong/restrictive, weak/permissive,
weak/restrictive coefficients. Extreme arm includes the shared product plus four
additional terms using max(z-1,0), max(-z-1,0). Ridge regularization pools sparse
effects toward zero, leaving the additive baseline (or shared product for the
extreme arm). Context-specific historical fits are thus joint regularized fits,
not independent bins or a repeat of broad kNN Test 25.

Primary comparisons: four-sign versus shared product, extreme versus shared
product. Primary proper-score endpoint: pooled held-out log-loss improvement,
week-cluster bootstrap 97.5% confidence intervals (two tests). Report flat 1u
moneyline ROI, units, SE, market-correct null, same-row market favorite and
paired ROI intervals, Brier, per-season results, flips, and context sample sizes.
Secondary: repeat on a closing-moneyline logit offset, fitting additive and
interaction terms only to deviations from market; closing prices are a benchmark,
not proof of executable pregame advantage. Market-offset fits use the same
penalty scheme. No thresholds or variants selected by held-out ROI.

Evidence supports adoption only if qualified terms improve proper scores beyond
shared interaction, do not rely on one season, and survive the market benchmark.
Otherwise report unresolved or adverse evidence in proportion to uncertainty.
