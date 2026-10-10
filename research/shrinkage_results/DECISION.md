# Context support shrinkage decision

Keep v1.16 production. The tested shrinkage methods did not demonstrate an
improvement sufficient to replace it. This is an empirical decision about
these candidate rules, not a conclusion that shrinkage cannot help.

On 812 common flat 1u moneyline bets from 2023–2025, production returned
+29.06u / +3.58% ROI. Primary active-support K=30 returned +25.50u / +3.14%;
its paired ROI difference was -0.44 percentage points, with the adjusted
week-cluster interval [-1.34, 0.00]. Its log-loss gain was only 0.000056,
interval [-0.001695, +0.002209], unresolved. Information-support K=30 lowered
ROI to +2.19% and worsened both proper scores. Selecting candidates from
earlier seasons also worsened ROI and proper scores against production.

The 31 PN-active games had production log loss 0.589829, compared with
0.603024 for active K=30 and 0.642568 for information K=30. Production's
15 forecasts at >=90% confidence all won; that tiny, exposed sample cannot
establish calibrated 94% forecasts, but it supplies no observed evidence
that this tail needs the tested additional shrinkage.

SF at SEA counterfactuals (Seattle): production 93.90%, active K=10 93.11%,
active K=30 91.68%, active K=100 88.04%, information K=30 84.69%, and a
jointly refitted product-only model 74.96%. These are refits on earlier
games at archived inputs, not probability caps or new ledger snapshots.

Current PN active support is 43.14 effective games, whereas information
support is only 6.17: a few extremes concentrate the feature's leverage.
This explains why the information-based rule shrinks the forecast most,
but historical performance did not reward that rule.

The production comparator was reproduced within 1.1e-10 historically and
3.4e-16 for archived current predictions. Inputs, recipe, market-offset
math, prior-week training, no-vig moneylines and frozen snapshots were held
consistent. The model, frozen production recipe and forward ledger were
not altered. The 812-bet cohort differs from the earlier context battle's
811-bet all-arm cohort because that earlier cohort excluded one additional
legacy-model abstention. Compare methods within the same table.

History was already exposed during model development. Any further rule for
extreme-input support should be separately specified and evaluated, rather
than tuned to make this one Seattle forecast look plausible.
