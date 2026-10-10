# Context battle protocol — frozen before execution

Goal: compare additional pass-matchup contexts to fixed_market_product and actual
production, leading with the owner's flat 1u model-side moneyline ROI.
This is exposed historical development, not native forward confirmation.

All challengers retain the fixed market logit offset (coefficient 1), raw main
features h8 / ridge 0.1, raw pass profiles h16, prior-week normalization, weekly
prior-week fits with two-season decay, and the shared product. Add:

1. Four signed hinge products at thresholds 0.5, 1.0 (existing control), 1.5, 2.0 SD.
2. Multiscale: all four hinge products at 0.5, 1.0, 1.5 SD.
3. One-extreme: signed hinge on either offense or defense at 1 SD, multiplied by
   the other unthresholded z score, averaged and differenced home minus away.
4. Market context: product multiplied by absolute no-vig home probability
   distance from 0.5, scaled to [0,1].
5. Early-season context: product multiplied by exp(-(week-1)/4).

Eight context families, each interaction block ridge {0.01,0.1,1,10}; the same
ridge applies to shared product and additions, as in the prior extreme test.
Choose ridge each evaluation season by minimum earlier 2021+ validation log
loss; evaluate 2023–2025. Also disclose all fixed-ridge-0.1 arms to distinguish
context effects from penalty selection. No ROI optimization or new thresholds
after reading results. Production and fixed comparator predictions must match
existing complete-grid reconstruction and committed evaluation predictions.

Primary sample is the intersection of valid flat bets across eight selected
arms, eight fixed-0.1 arms, production, fixed_market_product and q. Market
pickems and exact model abstentions are excluded; ties push. Proper scores
exclude ties. Report units, ROI ± SE, market-correct null, favorite baseline,
paired ROI and LL changes vs fixed and production, season breakdowns and
side-flip counts. Week-cluster bootstrap 8000 draws, seed 20261010; simultaneous
primary intervals use confidence 1-0.05/16 for eight families against two
comparators. Unadjusted 95% intervals are also descriptive; supplemental fixed
arms and conditional context slices do not establish confirmatory significance.

No automatic deployment. Name the strongest historical ROI challenger and
freeze its earlier-validation-selected forward penalty using 2021–2025, while
keeping fixed_market_product as a forward comparator. Profitability and paired
intervals govern interpretation; LL is secondary and governs fitting/selection.
Historical quotes lack capture timestamps (closing-price benchmark). Outputs
and source/input hashes are committed; no ledger, data or public writes.
