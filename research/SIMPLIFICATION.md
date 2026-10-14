# Fixed simplification comparison

Owner request: build and test the three suggestions from the 2026-10-14 review.
Development only: the single-removal results and every historical period have
already been examined. This is not a new independent confirmation test.

Compare v1.18 with exactly these fixed arms; no search or tuning:

* `no_peaks`: remove `d__max_lead` and `d__max_deficit` (27 fitted terms).
* `no_peaks_site`: remove both peaks and `site` (26 terms).
* `no_pass_tails`: remove all four `pass_1sd_*` terms, retaining `pass_product` (25 terms).

Zero the removed columns in training AND evaluation and refit before every week.
All other settings, market quotes, eligibility, h8/h16 profiles, penalties and
v1.18 favorite-confidence transformation stay fixed. A zero column receives a
zero coefficient, equivalent to dropping it while preserving the remaining
penalty positions (especially site's special penalty).

Use frozen packs already used by feature_importance.py. Keep 2015-16, 2017-22
and 2023-25 separate; 2026 weeks 1-5 is diagnostic only. Require baseline
reproduction to 1e-9 against published forecasts before accepting output.

Report flat 1u units, ROI +/- SE, same-row favorite and market-correct null,
paired ROI difference with week-cluster uncertainty, paired log loss/Brier,
side flips and annual results. Ties push in returns and are omitted from binary
scores. Historical prices are the frozen schedule's last recorded quotes,
with unknown capture times; they are not native lock prices.

For each primary arm, use a two-sided 98.333% normal interval on paired weekly
cluster means (Bonferroni for three arms within a basis). Total-band and annual
slices are descriptive; no across-basis multiplicity claim. Worth a forward
shadow test only if log-loss gain is positive on all three historical bases
and its adjusted interval excludes zero on at least one. Nonpositive gain on
two bases means not supported; otherwise unresolved. This is a development
screen, not a profitability gate. Never select settings on ROI.

Hash source and input files and protect the native ledger and config signature.
No production revision, recipe, automatic challenger adoption, or shadow-lock
change. Run `python research/simplification.py`; results go only to
`research/simplification_results/`.

Engineering work in the same change reconciles final forecast explanations
and adds an opt-in production-only profile path. Require probability/config
identity and shared-column equality against the complete path. These changes
do not alter the statistical experiment.
