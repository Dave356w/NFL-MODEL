# Joint-score research integration - October 16, 2026

This change imports the supplied R000-R003 research into NFL-MODEL at
`e93b936b9de03bab8e97a6b7ae71fb6d3a224fa7`. The numerical source, tests,
protocols and imported results are unchanged. This page records the repository
integration; the imported reports and VALIDATION.md retain their historical
statements about work performed before this PR.

## Decisions and relationship to production

The primary historical comparison has 816 games from 2023-25. Flat 1u empirical
moneyline results remain -0.9055u on 812 bets, -0.1115% ROI +/- 2.4716 percentage
points SE; same-row favorites +0.1801u / +0.0222%, negative-hold null about
-4.0995%. These are hypothetical returns with unknown quote capture times.
The no-vig market winner log loss (0.608072) is better than the empirical
market-only/R001/R002 point estimate (0.611353).

R001's historical tie hurdle and R002's additional +0.007088 joint-NLL gain
versus R001 warrant research retention. R002 is a correction to a final-score
distribution; missing regulation and possession labels prevent identifying an
overtime process. R003's +0.000286 gain versus raw market-only A fails the fixed
0.005 practical gate. Negative residual-feature results remain in the registry.
Nothing here establishes a betting edge or independent validation.

The runners have no production imports or network data fetches. No production
model, config signature, revision, generated notebook, Pages builder, workflow,
forecast, quote snapshot or ledger is changed. `forward_capture.py` is offline
infrastructure only. R001-F1 remains planned, and R002 has no activated cohort.
A future comparison requires a validated provider, external timestamped retention
and a separately locked protocol; it must not silently replace R001-F1.

## Intake and packaging

- The R002/R003 ZIP passed every ZIP CRC and all 174 supplied manifest entries.
  `JOINT_SCORE_IMPORT.json` records its SHA-256 and per-file imported hashes;
  `JOINT_SCORE_SOURCE_SHA256SUMS.json` retains the complete supplied manifest.
- The separate R000/R001 ZIP failed central-directory parsing. No content was
  recovered from that archive. The later archive contains the earlier source,
  frozen inputs and compact results needed for reproduction.
- Both current repository input CSVs match the frozen source hashes. The supplied
  Git bundle was inspected locally: `715d4d6` locks R001, and `efbbeef` locks
  R002/R003 before result commits `4e8d7ea` and `99cd300`. This verifies the local
  history, not an independent public registration or unseen test set.
- The root production README, requirements and ignore rules were not replaced
  by the standalone bundle's versions. Its optional pinned requirements are
  available as `research/joint_score_requirements.txt`.
- Large `marginal_probabilities.npz` files are generated locally and ignored.
  The earlier archive delivery already omitted R000/R001 PMFs; R002/R003 PMFs
  were available for numerical comparisons during integration. All four are
  reproducible with the commands below.
- Disposable hidden repeat directories and the 28 MB Git history bundle are
  excluded. Failure logs, incident hashes and failed checks are retained;
  the intentionally truncated prediction binaries remain in the source ZIP.
  Omitted paths are enumerated in `JOINT_SCORE_IMPORT.json`.

## Reproduce

Use Python 3.12. Install optional research packages in an isolated environment:

```bash
python -m pip install -r research/joint_score_requirements.txt
```

Run from the repository root with no data downloads. R000/R001 regeneration is
required before their validators can read the omitted full marginal PMFs:

```bash
OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals.py --output-dir research/experiments/R000_reproduction
OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals_report.py --output-dir research/experiments/R000_reproduction
OPENBLAS_NUM_THREADS=1 python research/audit_reproduction.py
OPENBLAS_NUM_THREADS=1 python research/tie_hurdle.py
OPENBLAS_NUM_THREADS=1 python research/tie_hurdle_report.py
OPENBLAS_NUM_THREADS=1 python research/check_determinism.py
OPENBLAS_NUM_THREADS=1 python research/distribution_ablations.py R002
OPENBLAS_NUM_THREADS=1 python research/distribution_ablation_report.py R002
OPENBLAS_NUM_THREADS=1 python research/check_ablation_determinism.py R002
OPENBLAS_NUM_THREADS=1 python research/distribution_ablations.py R003
OPENBLAS_NUM_THREADS=1 python research/distribution_ablation_report.py R003
OPENBLAS_NUM_THREADS=1 python research/check_ablation_determinism.py R003
```

These commands regenerate the named experiment outputs. To preserve committed
results while comparing, use a disposable directory under `research/experiments/`
and copy the experiment's protocol and registration record before running.
The R001 report uses its fixed experiment directory. Generated PMF archive
timestamps are not numerical model content; compare arrays, not NPZ file bytes.

## Current integration verification

- Full repository suite: **571 passed, 1 expected failure, zero failures**.
  Two pandas future warnings originate in the existing site code.
- Standalone research suite: **63 passed**.
- `python sync_notebook.py`: already in sync; generated notebook unchanged.
- `python validate_data_files.py`: **43 files OK**.
- Fresh isolated runs reproduce R000 prediction/feature/history/fit/coefficient
  bytes and its summary JSON exactly. Its 10 output checks pass.
- R001-R003 prediction, transform/tie-audit and provenance bytes match their
  supplied records. Metrics, paired-comparison intervals and decisions match
  exactly. R001/R002/R003 output checks: **14 / 22 / 20**, all pass.
- Example PMF arrays match for every experiment. R002/R003 full marginal arrays
  match the supplied files exactly. R000/R001 marginal files were absent from
  the delivery and were regenerated; no comparison to an unavailable original
  marginal array is claimed. R000's regenerated NPZ also matches the original
  manifest hash in its 29-file audit.
- All imported file hashes still match the supplied archive. No model formula
  or parameter changed. The working tree has no production/data/ledger changes.
- `git diff --cached --check`: clean.

`JOINT_SCORE_INTEGRATION_CHECKS.json` records current verification separately
from historical imported validation. The research environment matches pinned
NumPy 2.3.5, pandas 2.2.3 and SciPy 1.17.0. Production requirements remain
unchanged. Regeneration and checks use synthetic fixtures or frozen inputs;
no prospective quote, forecast or outcome has been captured.
