# Frozen prospective v1.16 comparison

Owner-authorized freeze on 2026-10-12 Pacific time. The machine-readable `forward_v116_protocol.json` records the exact UTC start, production recipe/config signature and SHA-256 of these rules. Earlier native locks, including pending games, remain historical/descriptive and cannot enter this new cohort. Earlier preregistrations are preserved; this is a separate prospective comparison, not a rewrite of their results.

## Sample and controls

Use the first native pre-kickoff lock per game matching frozen v1.16 recipe and configuration, generated strictly after the protocol start. A later copy cannot rescue a first matching lock made before the freeze. Require finite 0<p<1 and both valid American moneylines (absolute value at least 100). The recorded final-status injury gate/six-hour fallback remains production's eligibility rule. No reconstruction, backfill, refreshed input, later price or another revision enters the sample. Record every exclusion, including first locks before the start.

Recompute no-vig home q from the two moneylines in that same lock. Compare production with that q and the market favorite at those prices. Never substitute the spread-derived `market_wp` field, closing prices or Kalshi. Historical schedule quotes still have no independent source capture time; lock time documents when the model saw the quote, not proof of quote freshness. Final results come from the regenerated native grade view; conflicting official grades fail validation. Ties push in historical-unit accounting and are excluded from LL/Brier. Market/production pick'ems are excluded only from same-row directional return comparisons, with fixed native numerical tolerance 5.01e-6 around .5.

Keep the model recipe, features, priors, h8/h16, ridge penalties, normalization and weekly prior-game refit rule unchanged. Across future seasons, combine only this same frozen revision/config/recipe under this new umbrella protocol, and report each season separately. Another production revision/config ends enrollment; continuing requires a separately frozen protocol. No automatic model adoption, filter or sizing change is allowed.

## Predetermined checkpoints

Order eligible unique games by kickoff UTC then game ID. A checkpoint is available only once the entire earliest N-game prefix is settled, so delayed grades cannot change which games are assessed.

| Checkpoint | Purpose | Decision authority |
|---|---|---|
| 100 settled eligible games | Descriptive monitoring | None |
| 250 settled eligible games | Descriptive monitoring | None |
| 500 settled eligible games | Descriptive monitoring | None |
| 2026 regular-season review, no earlier than 2027-01-15 UTC and after captured regular-season games settle | Descriptive season consistency | None |
| 1,000 settled eligible games | Single formal assessment | May nominate a new separately reviewed experiment; never automatically change production |

This retains the existing qualification contract's 1,000-game formal checkpoint. The intermediate and season reviews cannot declare success, stop early for apparent gains, or select a new model. No formal checkpoint is added after looking at results. Daily reports may show enrollment/pending counts and descriptive current estimates; only the frozen checkpoint prefixes receive assessment labels. Future corrections to official results are explicitly new report versions, not silently overwritten prior decisions.

## Fixed metrics and interpretation

Primary financial qualification: same-row flat-unit net ROI, units difference versus the market favorite, and units minus the model-side market-correct null. At 1,000 games, require all three 95% season/week cluster-bootstrap lower bounds >0, as in the existing contract. This is an intersection-union gate; every component must pass. It is forecast tracking and does not execute wagers. Failing the gate is unresolved; an adverse interval is reported, without an automatic model switch.

Probability comparisons: paired LL(market)-LL(production) and paired Brier(market)-Brier(production). Two predefined LL hypotheses are overall improvement and improvement where max(q,1-q)<.60. Use 97.5% two-sided season/week-cluster bootstrap intervals for those two formal comparisons (Bonferroni family protection); Brier and calibration tables are supporting diagnostics. Directionally positive estimates with intervals crossing zero are encouraging but unresolved. LL support alone is not financial qualification.

Always report N, unique games, ties/pushes, pending rows, exclusions, W-L-P, units, ROI ± SE, same-row favorite and market-null results, LL/Brier, market confidence bands 50–60/60–70/70–80/80–90/90–100%, and season consistency. Bands beyond the predefined close-game hypothesis, upset slices, contribution trimming, calibration and team/weekly slices remain descriptive and cannot become post-hoc policies.

Bootstrap 8,000 draws, seed 20261012, resampling season/week clusters; at least two distinct clusters are required for intervals. Simulation-derived challengers are not part of this formal comparison: no prospective challenger capture has been implemented, so reconstructed shadow predictions cannot later be relabeled forward. A challenger needs its own frozen recipe and pre-kickoff append-only capture before a future comparison starts.

## Operation

`python research/forward_v116_assessment.py` is read-only with respect to production and native ledgers. It validates the protocol hash and writes enrollment, exclusions, descriptive metrics, and ready checkpoint assessments under `research/forward_v116_assessment_results/`. It fails rather than mutating an existing different checkpoint file. A separate manual/daily workflow uploads versioned assessment artifacts; the production build is unaffected. A daily condition watch notifies the owner only when a predetermined checkpoint first becomes available.
