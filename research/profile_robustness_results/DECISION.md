# Decision after outstanding experiments

Keep production v1.16 for now. None of the four fixed robustness rules produced a resolved incremental improvement on exposed 2023–25 development. This does not establish that shrinkage or bounded inputs have zero value; it means these particular candidates have not earned a change on these results. Production's native forward advantage remains untested: 13 snapshots, zero graded games as of the committed 2026-10-10 16:18 UTC report.

## Improvement and decline

On 812 common flat 1u bets, production returned +29.06u / +3.58% ±2.52 percentage points SE, versus the same-row market favorite +0.18u / +0.02% ±2.47. Market-correct null ROI is -4.10%. Probability scores use 815 binary games. Model design used these seasons; all comparisons are development rather than untouched confirmation.

Adding four pseudo-games (total eight) improved average LL from .605605 to .605271 and Brier .208989 to .208849, but returned +25.34u / +3.12% ROI. Two side changes lost 3.72u, both in 2023. LL improved principally in 2024; it slightly declined in 2023 and 2025. The paired LL gain interval [-.000931,+.001724] and ROI change interval [-1.39,+0.00] pp do not resolve improvement.

Adding twelve pseudo-games (total sixteen) returned +29.19u / +3.60%, with LL .605358. Four side changes produced just +0.13u overall: the 2023 decline was offset by 2024/2025 gains. Paired ROI change +.02 pp [-1.18,+1.24] and LL gain +.000247 [-.001953,+.002597] remain unresolved.

Clamping normalized passing profiles to ±2 SD returned +31.92u / +3.93%, with four changed picks. This is a +.35 pp ROI change [-.58,+1.57], not a resolved advantage. LL worsened to .605829 and Brier to .209167: 2023 declined more than later seasons improved. In the fixed 123-game >2 SD slice, LL worsened from .565984 to .570277. Bounding inputs moderates extrapolation, but can remove useful signal too.

The combined rule returned +24.62u / +3.03%, with LL .605700, worse on both aggregate measures. It improved 2025 but declined in 2023/2024 ROI. Prior-season LL selection chose production for 2023 and 2024, and profile_4 for 2025. Selected ROI was identical to production, while LL was slightly worse (.605610). The annual selection offers no demonstrated improvement.

All fixed intervals above are paired week-cluster 98.75% intervals for the four comparisons. They omit design-selection uncertainty. The 15-game production >=90% slice is too small and exposed to validate 94% confidence; every robustness arm slightly worsened its LL.

## Why SF–SEA remains extreme

Archived Seattle probability was 93.90% in production, 92.04% with four extra prior games, 89.67% with twelve, 91.86% bounded, and 91.20% combined; market 59.34%. These are joint refits at archived nonpassing inputs and prices, not new snapshots.

Passing profiles already have substantial smoothing. For this game's h16 profiles, the league prior accounts for about 27–30% of denominator mass; Kish effective game support is 20.74, while pass-play-weighted effective game support spans 18.02–22.86. These are weighted game counts, not independent pass-play observations. They include downweighted previous seasons. More prior mass pulls raw rates toward league means, but recomputing each arm's normalization also compresses its reference spread, partly preserving standardized extremes.

The current PN contribution decreases from +1.704 logit in production to +1.443 (profile_4), +1.164 (profile_12), +1.496 (bounded), or +1.412 (combined). The passing/context features and their scaling/coefficients are refitted, so moderation is not equivalent to subtracting a fixed term. Lower confidence for one game is not evidence of better calibration.

## Verification and next evidence

212 repository tests passed; notebook sync, 28-file data validation, pages-only rendering and diff checks passed. Feature reproduction error 2.63e-14; historical prediction error 1.94e-10; archived forecast error 3.33e-16. All feature, reference and coefficient cutoffs precede evaluation weeks. Future-box perturbation and future-reference perturbation tests passed. Frozen sufficient statistics allow CI replay without raw caches. Production settings, forecasts and append-only ledger were not altered.

Deployed desktop SF–SEA disclosure passed visual inspection in light and dark themes: intuitive labels, subtitles, explicit direction text and common-scale bars were readable. No page-origin console errors were observed; browser-extension metadata errors were unrelated. Mobile screenshot QA remains unverified: the cloud browser exposes no viewport resizing and local official headless-browser downloads failed. Automated site tests and HTML rendering passed, but they do not substitute for a mobile screenshot.

Continue the existing frozen native forward ledger. No future outcomes can be tested now and no reconstructed rows should be appended. Profile_4 is the strongest modest-shrinkage candidate on average LL alone, but its ROI and annual selection results do not support adopting it now. Avoid another outcome-driven search through priors or caps just to make SF–SEA look comfortable.
