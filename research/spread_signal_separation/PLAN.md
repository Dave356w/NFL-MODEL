# Separate spread signal, added forecast information and ATS price

Fixed comparison design before new benchmark scores. All historical outcomes
are exposed development; no untouched test or new trading strategy is claimed.
Use R000 frozen inputs and saved plain/AC1/legacy forecasts unchanged.

Main cohort: same 816 games 2023–25; separate 2019–22 and 2026 diagnostics.
All new forecast parameters use strictly earlier weeks, current plus five prior
seasons, half-life 38 weeks. No recipe/threshold/ROI search.

1. Margin signal: compare raw signed spread, zero margin, earlier weighted
   mean home margin, earlier weighted linear margin-on-spread regression, and
   saved plain/AC1 margin means. MAE, RMSE, signed errors and paired loss
   intervals. Report descriptive spread/margin correlation, R² and same-cohort
   calibration regression with week-cluster intervals, clearly not forecasts.
2. Winner information: earlier weighted binary logistic on [1,spread/7], and
   [1,spread/7,(total-44)/7,spread*(total-44)/49]. Fixed ridge .01 on all
   coefficients, analytic gradient, zero start, L-BFGS-B gtol1e-7 ftol1e-12
   maxiter1000 maxls100; fail on nonconvergence. Exclude actual game ties.
   Compare proper scores with plain, coherent AC1 (main only), prior Jeffreys
   home-win rate, fair .5 and no-vig moneylines. No target outcome in prediction.
   A winner classifier is not used as an ATS cover classifier.
3. ATS probability information: fair conditional .5 vs saved raw and AC1 cover
   probabilities on identical decisive ATS games. Proper scores and paired
   week uncertainty; pushes excluded from scores, refunded in returns.
4. Price: retain the existing positive-EV-at--110 selection, without retuning
   at different prices. On those SAME selected bets, decompose actual units
   into wins-minus-losses at even-money and winning-payout reduction wins/11.
   Report W–L–P, units, ROI +/-SE, same-row spread-favorite baseline, negative-
   hold null and week intervals. Report original legacy R003 separately as a
   different construction, not as a replacement chosen on this historical ROI.

10,000 whole-week paired resamples within season, seed20261016. Descriptive
intervals condition on existing paths; five-comparison 99% sensitivity for
margin/winner primary contrasts, not full adaptive-search correction. No claim
of predictive edge from correlation, band counts, point accuracy or no-bet ROI.

Save per-game benchmarks, fit/cutoff audits, paired metrics, signed-spread
calibration bands, price decomposition, source hashes and independent repeat.
Test gradients, planted spread signal, future rejection, target-label exclusion,
correct margin sign, push denominators and exact payout decomposition. Preserve
all original models, artifacts and native forward ledger. No live wagers or
production promotion.
