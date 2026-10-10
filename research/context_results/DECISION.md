# Production challenger decision

The strongest primary historical ROI challenger is the shared product plus four
1 SD signed hinge contexts. Earlier-season penalty selection yields +27.24u,
+3.36% ROI ±2.50 percentage points SE on 811 common bets. Its paired ROI advantage
is +0.85pp over fixed_market_product and +1.46pp over production; both adjusted
intervals cross zero. Its log loss (0.608663) is worse than the fixed product
(0.607584), despite its better realized ROI.

The protocol's fixed-0.1 sensitivity is particularly relevant to a frozen
production challenger: the same 1 SD feature extension gives +30.06u, +3.71%
ROI, LL 0.605605. The 1.5 SD extension gives +28.73u, +3.54%, LL 0.605986.
Fixed product is +20.32u, +2.51%, LL 0.607584; production is +15.38u, +1.90%,
LL 0.631630; market favorite is +1.18u, +0.15%. All prices imply a selected-side
market-correct null of approximately -4.10% ROI. The frozen 1 SD extension's
ROI difference vs fixed is +1.20pp, descriptive 95% week-cluster interval
[-0.41,+2.88]pp. It changes 13 sides. This supplemental comparison is development,
not a second independent confirmatory test.

For a forward battle, nominate raw main h8 ridge 0.1, raw pass h16, fixed market
logit coefficient 1, shared product plus 1 SD hinges with interaction ridge 0.1.
This is also the nominee from minimum 2021–2025 development LL for the primary
ROI-leading family. Freeze the formula and penalty; refit coefficients weekly
using earlier weeks. Keep fixed_market_product and current production as
comparators, with identical captured pregame input/grading quotes and unchanged
flat 1u model-side scoring. The 1.5 SD / ridge 0.1 variant is a secondary
candidate if running another forward arm is practical. No deployment is made by
this research commit.

No additional context beyond 1 SD has displaced that candidate on historical
ROI. Wider extremes have little support: across the 816 games, both offense
and opposing defense exceed 1.5 SD on only 16 team-side matchup observations;
there are none at 2 SD. The 2 SD variant changes one betting side because adding
historical training features can alter the shared fitted coefficients even when
the additional held-out hinges are zero. Its bootstrap ROI interval starts at
zero, not above zero; a single favorable flip is not reliable evidence of a
2 SD context effect. Multiscale, one-extreme, market-competitiveness and
season-stage extensions did not outperform the 1 SD candidate on primary ROI.

All models still lose money in 2025. In the primary comparison, fixed product
has -1.38% ROI, 1 SD selected has -2.16%, and production -6.46%. The frozen 1 SD
sensitivity is -1.42%; its aggregate gain comes from 2023–2024. Do not interpret
the aggregate ranking as established temporal stability.

A new exact model abstention (2024_17_GB_MIN) changes the common bet sample from
812 to 811. Consequently baseline totals differ from the previous report.
Probability comparisons retain the same 815 binary games. The complete
protocol, selected penalties, paired intervals, season results, source/input
hashes, predictions and side changes accompany this decision. All historical
results are exposed development and use quotes without independent capture
timestamps; forward evidence remains outstanding.
