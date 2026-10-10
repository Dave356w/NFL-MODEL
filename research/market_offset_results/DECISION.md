# Market starting point decision

Retain production's market offset. This clean fixed-recipe ablation supports
it for probability forecasting, while its incremental betting ROI remains
unresolved. No production changes are warranted by this test.

Across 815 binary games in exposed 2023–2025 development, retaining the
offset improved log loss from 0.625832 to 0.605605 and Brier score from
0.217275 to 0.208989. The paired 95% week-cluster log-loss gain interval
was [+0.010003, +0.030187]; probability scores improved in each season.

On 812 common flat 1u bets, retaining the offset returned +29.06u / +3.58%
ROI, versus +19.01u / +2.34% without it. The ROI gain of +1.24 percentage
points had a 95% interval [-3.45, +5.79]. Without the offset, ROI was worse
in 2023 but better in 2024 and 2025; improved probability scores therefore
do not imply a proven, consistent profit advantage.

The same-row market favorite returned +0.18u / +0.02% ROI. Production's
paired ROI advantage over that control had a nominal 95% interval
[+0.46, +6.65] percentage points. These are already exposed development
seasons, not untouched evidence of reliable superiority or native forward
qualification. Feature-design selection uncertainty is not in the interval.

SF at SEA at the archived inputs remains 93.69% Seattle after jointly
refitting without the offset, compared with production's 93.90%. Removing
the starting point does not resolve this forecast's extreme confidence;
the learned coefficients redistribute information, and pass-context terms
remain in both arms. This is different from subtracting the existing
market contribution without refitting.

Both arms used identical training games, features, scaling, penalties and
prior-week training. Historical and archived production probabilities
reproduced to numerical precision. Production and snapshots are unchanged.
