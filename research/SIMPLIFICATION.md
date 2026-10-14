# Fixed simplification comparison

Owner request: build and test the three suggestions from the 2026-10-14 review.
Development only: the single-removal results and every historical period have already been examined. This is not a new independent confirmation test.

Fixed arms against v1.18: no_peaks removes d__max_lead and d__max_deficit (27 terms); no_peaks_site also removes site (26); no_pass_tails removes the four pass_1sd_* terms, retaining pass_product (25). Zero removed columns in training and evaluation and refit before each week. All other settings and eligibility stay fixed.

Use feature_importance.py's frozen packs; report 2015-16, 2017-22, 2023-25 separately, plus diagnostic 2026 weeks 1-5. Require baseline reproduction to 1e-9. Lead with flat 1u units, ROI +/- SE, same-row favorite, market-correct null, paired ROI difference with weekly clustered uncertainty; also log loss/Brier, side flips and annual results. Ties push in returns and are excluded from binary scores. Historical prices have unknown capture times.

For each arm, use two-sided 98.333% normal paired-week-cluster intervals (three-arm Bonferroni within each basis). Annual/total slices are descriptive. Worth a forward shadow test only if log-loss gain is positive on all three historical bases and adjusted interval excludes zero on at least one. Nonpositive gain on two bases means not supported; otherwise unresolved. This is development screening, not a profitability gate; no ROI tuning or across-basis multiplicity claim.

Hash inputs/source and protect ledger/config identity. No production or shadow-lock changes. Engineering scope also reconciles forecast explanations and adds an opt-in production-only profile path, with equality tests.
