# Validation record - iteration 2, R002/R003

- Both protocols committed together before either new run: efbbeefba35e6eb280bad81af66000cdf55deb37.
- R002 executed/reported/tested before R003 execution; R003's design did not adapt
  to R002. No candidate/grid or ROI selection and no new outcome/price data.
- R002 9 focused transition tests, then 40 combined tests passed before R003.
  R003 21 focused support tests passed. Final combined suite: **63 passed, zero
  current unit-test failures**, including 2 new gzip serialization regression tests.
- R002 22 and R003 20 final integrity checks pass. Every transformed full joint
  is finite, nonnegative and normalized; derived means/probabilities cohere;
  marginal PMFs/row ordering/game sets agree; prior-week cutoffs hold. Scores
  with zero realized probability would hard-fail; no NLL-floor substitution.
- R002 conditional winner and tie probabilities equal R001; settlements unchanged.
  Excess/transported/untransportable mass is accounted for. Boundary rules logged.
- R003 mask has 6,548 reachable / 6,561 cells, 13 excluded pairs. Rare valid
  (6,1)/(1,6) remain supported. Independent mathematical oracle, symmetry and
  proper-score conditioning identity tests pass. No observed support violation.
- R002/R003 primary n=816, 272/season; all arms 2,462 games. 2017-22 and 2026
  diagnostics are separate. 2026 sample remains 79 snapshot games, no updates.
- Reconstruction of raw and R001 baselines agrees within 2.14e-14 (1e-10 gate).
- Both final independent reruns: exact prediction CSV-gzip bytes, transform
  audits, provenance and every stored PMF array. R003 support mask matches too.
- All R000/R001 artifact hashes match ITERATION_2_PRIOR_ARTIFACTS.json. Original
  model modules, frozen source data, production forecasts/pages and ledgers
  were not changed. Full production test suite/data validator were not run.

## Preserved execution failures and engineering revision

R003's first CSV-gzip output was truncated (EOF marker absent). Its first
report therefore failed at input parsing. Initial independent repetition also
failed prediction-file byte equality; PMFs, audits, support and provenance
matched. Decompressible file rows: 9,613 including the partial last row, versus
9,849 expected including the header. The corrupt output, exception logs,
failed repeat JSON and incident hash remain in
experiments/R003_score_support/failures/initial_write/.

The root cause was not established; do not call this a model failure or claim a
proven platform cause. A serialization-only engineering revision builds and
checks complete compressed bytes, writes/fsyncs a temporary file, atomically
publishes it and checks the published stream. Two regression tests verify
multi-megabyte roundtrip/repeat identity and preservation of an old file when
publication fails. Both final independent experiment reruns pass. R002's
canonical decompressed CSV SHA-256 is identical before/after the I/O revision;
its old provenance and validation comparison are retained. Neither predictive
formula, weight, support mask, baseline, sample, bootstrap nor protocol changed.
The repaired run is not a new independent candidate or second validation set.

The final reports additionally require complete row counts and serialized file
hashes. Every final prediction CSV-gzip passes EOF validation. The intentionally
corrupt failure artifact is retained for evidence, never consumed for metrics.

## Statistical/evidence limits

Two primary hypotheses were registered before results; adjusted 97.5% intervals
use Bonferroni for that family. Nine-contrast sensitivity adds the original six
residual contrasts and R001; this cannot erase previous research exposure.
All secondary intervals are descriptive. Week bootstrap conditions on forecasts
and does not refit overlapping training windows. Logical prior-week checks pass;
historical market capture times remain unknown and actual pregame availability
cannot be certified. There is no native forward or independent validation cohort.

The frozen pack has no regulation/OT/possession fields. A mechanistic overtime
process is not identifiable from it; R002 is explicitly a hypothetical terminal
mass-transport correction. Official current Rule 11 scoring/try primitives and
Rule 16 OT context were verified via the NFL rulebook page/PDF. Historical
indexed PDF URLs returned 404 on direct open, retained in RULE_SOURCES.json;
no historical rule-era model or transition-frequency fit is claimed. Joint
additive reachability is a mathematical inference, not an NFL probability table.

## Reproduction

From bundle root with pinned requirements installed, run R002 runner, report,
repeat check; then R003 runner, report, repeat check; finally the combined tests.
Exact commands are in RESULTS_SUMMARY.md and each experiment REPORT.md. Original
R000/R001 reproduction commands are retained in their reports. Runners require
no network. Python/package/thread configuration remains in ENVIRONMENT.json.

## Previous iteration validation record (unchanged historical record)

# Validation record - this iteration

## Passed

- Source archive: all 38 manifest entries verified on intake.
- Recorded repository base e93b936b9de03bab8e97a6b7ae71fb6d3a224fa7 inspected
  read-only: recursive tree, working agreement, market-residual code/tests,
  validation code and exact committed schedule/total input files. No AGENTS.md
  appeared in that tree. Relevant source evidence is retained in audit_sources/.
- Both source-file SHA-256 values agree with original input_sources.json.
- One-to-one source merge exactly equals all 3,679 frozen rows. Duplicate game
  IDs: zero. Completed scores are nonnegative integers, max 70. Result equals
  home minus away for every complete row. Incomplete future 2026 rows are
  explicitly counted in R000/AUDIT.json; no imputation.
- Positive-home-favored spread orientation agrees with the original convention,
  derived location identities and non-pickem no-vig moneyline direction in
  99.682% of comparable complete rows. Small quote-sign disagreements are
  retained and enumerated, never repaired or excluded opportunistically.
- Original experiment rerun across 2017-2026: 19,696 arm-game predictions.
  Predictions, features, history audit, fit audit and coefficient files are
  byte identical to the supplied originals. All 29 comparable output/source
  checksums and original summary JSON agree. R000/AUDIT.json records details.
- Original 9 focused tests: passed. Original 10 output checks: passed.
- Combined current suite: **31 passed, 0 failed**, about 2.2 seconds, including
  original whole-week adversarial mutation, tie strata normalization, support,
  conditional winner invariance, analytic NLL gain identity, prior-week tie
  fitting, six-season window and invalid-input rejection.
- R001 14 output checks: passed. Every stored marginal is nonnegative and
  normalized, game sets/row ordering agree, probabilities and means cohere,
  prior-week cutoffs hold, tie mass matches fitted rate, winner choices/returns
  are invariant, and joint gain equals tie Bernoulli gain.
- Reconstructing market-only joint PMFs from original coefficient audits agrees
  with original numerical metrics to max absolute 2.14e-14 (tolerance 1e-10).
- Independent R001 rerun: predictions/tie audit/provenance byte-identical; all
  marginal/example PMF arrays exactly identical. NPZ archive metadata times
  are not compared as model content. See deterministic_reproduction.json.
- Forward writer tests: first-write-only versions/snapshots; code/parameter
  version changes; stale/future/naive timestamps; prior-week cutoff; input-line
  agreement; PMF rejection; hash tampering detection; production path guards.
  Tests use synthetic 2027 fixtures, not prospective evidence.

## Failed or unverifiable requirements and limitations

- **Actual historical market timestamp / pregame availability audit cannot
  pass:** original quote capture timestamps are absent. Logical label cutoffs
  pass, but this does not prove the inputs existed at the forecast cutoff.
- Full NFL-MODEL production checkout is not present. Full repository pytest,
  sync_notebook.py and validate_data_files.py were **not rerun**; the supplied
  517-pass/1-xfail record is prior evidence only. No PR or production change is
  being made. No product suite result is claimed for this isolated bundle.
- No actual provider adapter or external immutable timestamp store was enabled.
  Snapshot timestamps preserve declared provider events and local receipt;
  local hashes cannot prevent deletion or malicious authorized recomputation.
- All evaluation seasons were previously exposed; no independent validation
  sample exists. A result-inspired locked specification is still exploratory
  historical development. Week-bootstrap CIs condition on fitted forecasts and
  do not include earlier model search or retrain under each bootstrap draw.

## Environment / execution issues retained

- pytest initially absent; installed pinned pytest 8.3.5 before tests. No model
  dependency versions were changed. NumPy 2.3.5/pandas 2.2.3 match the original;
  matplotlib 3.10.8, scipy 1.17.0. scipy is used only for count-uncertainty output.
- Initial CLI smoke check used the parent working directory; corrected to the
  extracted research workspace before execution. No partial model output.
- A source-materialization shell command exceeded argument limits before file
  creation; source text was subsequently saved in bounded chunks and hashes
  verified. A guessed filename returned 404; corrected using the fetched tree.
- No modeling/unit-test failures occurred after dependency setup. No failed
  hypothesis was silently revised or rerun as a new independent test.

## Reproduce offline (after installing requirements)

```bash
OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals.py --output-dir research/experiments/R000_reproduction
OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals_report.py --output-dir research/experiments/R000_reproduction
OPENBLAS_NUM_THREADS=1 python research/audit_reproduction.py
OPENBLAS_NUM_THREADS=1 python research/tie_hurdle.py
OPENBLAS_NUM_THREADS=1 python research/tie_hurdle_report.py
OPENBLAS_NUM_THREADS=1 python research/check_determinism.py
OPENBLAS_NUM_THREADS=1 python -m pytest tests -q
```

R001 protocol was committed before computing its candidate forecasts. Execution
logs, input/code/protocol hashes and numerical outputs live under experiments/.
The large R000 marginal PMF file is regenerable by the first command; packaging
notes identify any omitted duplicate binary output. There are no network calls
in the research runners.
