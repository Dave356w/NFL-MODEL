# Decision: direct margin/total models and production interactions

Retain production v1.16. Separate margin/total targets were a logical test, but these fixed Gaussian ridge candidates do not establish better forecasting or a reliable improvement through interaction. Preserve the research candidates and continue the existing native forward experiment. No production formula or snapshots were modified.

## Direct distributions and market probabilities

Across 816 exposed 2023–25 games, the market-centered margin benchmark scored NLL 3.957840 and CRPS 7.0859. Market-plus-correction scored 3.959389 / 7.1117; standalone scored 3.987619 / 7.3045. The corrected model's NLL gain was -.001549, 98.75% week-cluster interval [-.013790,+.011041], unresolved. Standalone's gain -.029779 [-.051357,-.008248] was a resolved decline in this historical development test.

For total points, market-centered NLL/CRPS was 3.981466 / 7.2414, corrected 3.988114 / 7.3053, standalone 4.009772 / 7.4541. Corrected gain -.006647 [-.021090,+.007084] was unresolved; standalone -.028306 [-.047973,-.008524] was a resolved decline. The corrected total model scored worse in all three seasons. Mean-error measures agree: market margin/total RMSE 12.653 / 12.959 points versus corrected 12.675 / 13.043 and standalone 13.036 / 13.330.

Full-distribution comparisons use a labeled market-centered Gaussian benchmark, not a bookmaker-implied full distribution. At the actual lines, compared directly with two-sided no-vig quotes and excluding pushes identically, corrected cover LL was .694871 versus market .693588 (797 nonpush games, 19 pushes). Corrected over LL was .699999 versus .693319 (811, 5 pushes). Both gain intervals cross zero. Standalone event probabilities also scored worse, with unresolved intervals. Distribution dispersion used earlier out-of-sample errors rather than fitted training residuals.

## Do the new forecasts improve production?

On 812 common flat 1u moneyline bets (815 binary proper scores), full production returned +29.06u / +3.58% ±2.52 pp SE, LL .605605, Brier .208989. The same-row favorite returned +.18u / +.02% ±2.47; the market-correct null ROI was -4.10%. These are development returns, not native forward evidence.

Honest stage-one forecasts begin in 2020. Stage-two warm-up therefore shortens training; production refitted on exactly that matched cohort returned +27.19u / +3.35%, LL .607431. Full-history production is reported separately to avoid attributing that training-history difference to the new features.

Forecast features alone returned +19.99u / +2.46%, LL .605717. Margin-by-total returned +21.83u / +2.69%, LL .605814. Passing-product-by-total returned +29.76u / +3.67%, LL .605569. Against matched production, none of the three fixed 98.333% paired ROI or LL intervals resolves improvement. Against full production, passing-by-total's ROI gain was only +.09 pp [-2.46,+2.94], and LL gain +.000036 [-.006482,+.005572]. Its Brier was slightly worse (.209114).

Interactions were also compared with the additive forecast features, as supplemental diagnostics after the first run. Margin-by-total gained +.23 pp ROI but slightly worsened LL; passing-by-total gained +1.20 pp ROI and +.000148 LL. Both 97.5% intervals cross zero. Passing-by-total improved 2023/24 LL relative to full production but worsened 2025 (.603884 versus .602822). Its 2025 moneyline return was -5.75u versus production -3.85u. Earlier-season selection returned +29.98u / +3.69% but LL .606025, worse than full production, with no resolved improvement over matched production.

Direct margin-derived win probabilities were not stronger: corrected +4.83u / +.59%, LL .608977; standalone +17.72u / +2.18%, LL .628899. A distribution fit for scoring margin does not automatically produce better winner probabilities.

## Does the learned total add value beyond the market total?

Supplemental source ablation holds the margin forecast feature constant and replaces the predicted total by the market total in the passing interaction and total-homefield term. It returned +28.10u / +3.46%, LL .604746, Brier .208815. This had better proper scores than the predicted-total version but slightly lower ROI. Using the predicted total instead gained only +.21 pp ROI, 95% interval [-.76,+1.25], and worsened LL by .000823, gain interval [-.002229,+.000535]. The newly predicted total has no demonstrated incremental value here. Any promising total-context effect may largely come from the existing market total.

This ablation was added after seeing the initial run, with no parameter tuning, and was excluded from the original annual selector. Its better average proper scores warrant retaining it as a research candidate, not calling it a qualified replacement.

## SF at SEA and limitations

At archived production inputs, the direct corrected mean was Seattle by 16.735 points (predictive SD 12.592), compared with market Seattle by 3.0. Corrected total was 47.077 (SD 13.246), versus schedule total 45.5. Direct margin-derived conditional non-tie Seattle probability was 91.33%; passing-by-total production stack was 93.20%, versus original production 93.90%. The schedule total quote has no known archive-lock timestamp, so current total/interaction results are counterfactuals with that limitation.

The direct model shares production's passing contexts; its extreme forecast is not independent corroboration. Changing the training target did not eliminate the extreme SF–SEA inference. Historical distribution scores provide no basis to prefer that direct forecast over the market.

The Gaussian models are simple location/dispersion approximations: they do not model NFL key-number concentrations or a coherent joint score distribution, and the total Gaussian assigns small probability to negative totals. Margin/total likelihood levels cannot be compared with each other or with binary win LL. Compare gains within the same target. Schedule price capture times are unknown; the tests cannot establish executability at the original lock time. Historical design exposure and supplemental diagnostics also prevent treating nominal intervals as untouched confirmation.

All stage-one fits, variance calibration and stage-two fits precede each game's own week. Stage-two features are weekly out-of-sample predictions, with explicit cutoff metadata and an own/future-label rejection guard. Historical full production reproduced within 1.03e-10; archived forecasts within 2.22e-16. Production and append-only ledger are unchanged. The frozen feature/price pack supports CI replay without raw caches; raw source hashes accompany it. Detailed outputs, annual results, fits and audits are committed.
