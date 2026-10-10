# Production qualification protocol

Fixed before this expanded run, October 9, 2026 Pacific time. Earlier exposure:
Tests 24–25, production development and the fixed-main-effect qualified-pass
experiment already used 2023–2025. This run is development screening, not a
pristine holdout or native forward confirmation.

Run `python research/production_qualification.py`. Default inputs are rebuilt
from nflverse into `.nfl_cache/production_qualification_inputs`; pass
`--input-dir research/qualified_output` to reuse the earlier experiment's inputs.
Input and source SHA-256 hashes and dependency versions are recorded. Pickle
inputs are local caches created by this repository, not arbitrary user uploads.

## Candidates and chronology

1. Current production additive selection, reproduced with the production selector.
2. Market-offset additive correction.
3. Market-offset shared pass product correction.
4. Market-offset four sign-qualified pass-context corrections.
5. Market-offset shared product plus four ±1 SD hinge corrections.
6. Previously proposed fixed market-offset product: raw h8, main ridge 0.1,
   interaction ridge 0.1, selected before this run.

Main grids use both current production families (raw/opponent-adjusted), team
half-lives 4/8/16 and main ridges 0.01/0.1/1/10. Interaction ridges independently
use 0.01/0.1/1/10. Pass descriptors stay raw h16, with the prior-week season
centering / trailing-four-season SD rule of the earlier experiment. Coefficients
are fit jointly before each week using earlier weeks, with two-season decay,
training-derived feature scales and production site-penalty treatment. Offset
coefficient on no-vig moneyline log-odds is fixed at 1. No outcome-derived bins.

Predictions cover 2021–2025; evaluate 2023–2025. Each season's candidate recipe
comes from earlier 2021+ seasons' walk-forward log loss. The production arm uses
the production selection implementation; offset arms minimize earlier log loss.
The fixed arm never reselects hyperparameters. ROI is not a selection objective.
Model training can use unpriced earlier games; market-offset training requires
valid earlier moneylines. All evaluation arms share the same priced games.

Historical schedule moneylines have no independent capture time. Offset inputs
and grading prices therefore represent a closing-price development benchmark,
not evidence of an executable advantage at earlier production lock times.
Historical availability files also have the existing v1.15 timing limitations.

## Backtest screening gate

Flat 1u on the forecast's favored side at the historical moneyline; market
pick'ems excluded identically from all primary paired betting comparisons.
Ties are pushes for ROI, excluded from binary proper scores. An arm's own exact
50% forecast abstains; use the intersection of eligible decided rows across all
arms so missing or abstained games cannot give a candidate a different sample.

For six candidate families, use two-sided confidence level 1−0.05/6 for each
week-cluster bootstrap interval (8,000 draws, seed 20261010). The gate is an
intersection of three required positive lower bounds:

* realized net ROI;
* same-game units difference versus the market favorite;
* realized units minus its chosen side's market-correct null expected units.

Bonferroni across candidate families controls opportunistic promotion; the
conjunction does not require a further correction across its three conditions.
Gate status: pass if all lower bounds exceed zero; adverse if any upper bound
is below zero; otherwise unresolved. Point-estimate improvement is not a pass.
Report log loss/Brier and their paired market differences as secondary scores,
ordinary 95% week-bootstrap intervals, all season results, recipe selections,
sample exclusions and probability/pick changes. Bootstrap holds the fitted
selection process fixed and does not capture all design-selection uncertainty.

## Selection and production status

Among backtest-passing arms choose lowest pooled evaluation log loss. If none
pass, nominate the lowest-loss market-offset arm for a forward experiment,
explicitly marked unqualified. Freeze its recipe by applying its fixed selection
rule to all completed 2021–2025 development predictions; preserve the already
fixed arm's recipe if it is nominated. Selection on exposed development results
cannot be described as confirmation.

No historical result automatically activates or changes production. A backtest
pass earns a prospective test, with the fixed capture and success contract in
the candidate specification. Reliable production qualification additionally
needs native, timestamped forward evidence at available prices. This command
never writes production recipes, ledger snapshots, `data/` or `public/`.
