# Market starting point ablation protocol

Written before execution. One fixed contrast: production v1.16 with its
no-vig moneyline logit offset versus the identical feature model without
that offset. Main h8 profiles, pass h16 profiles, Product + 1 SD features,
prior-week reference values, ridge 0.1, site penalty 0.01, scaling,
two-season training decay, eligible training rows and optimizer are identical.
All coefficients are refitted jointly in each arm before each evaluation
week. No new intercept, tuning, probability cap or shrinkage is added.

Both arms train on the same priced, binary-outcome, ready games; removing
the offset does not expand training to unpriced games. Evaluation uses the
frozen pregame feature pack from the shrinkage experiment, 2023–2025, and
strictly prior training weeks. Ties push for ROI and are excluded from proper
scores. Same-row market-favorite control. No annual parameter selection.

Report flat 1u ROI, units, standard error, market-null ROI, log loss, Brier,
annual results and paired 95% week-cluster bootstrap intervals. Positive
differences/gains in the report favor retaining the market offset. Record
coverage, abstentions, side flips, fitting-time audit and reproduction of
the committed production comparator. Replay archived current inputs at
their captured prices with both refitted arms, labeled counterfactuals.

This isolates the market's direct starting probability in the forecast;
the no-offset arm can still learn relationships correlated with market
prices through team features. This is exposed historical development, not
forward qualification. Production and ledger are unchanged by this test.
