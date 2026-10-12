# Exact v1.16 production restoration

Owner instruction: restore v1.16 production and retrospectively grade/report all
original forecasts and tested competing versions (2026-10-12).

`verification.json` checks the original configuration identity and reproduction
of all 816 historical games plus the 13 original v1.16 native snapshots.
`regraded_ledger.csv` preserves all 30 original snapshot identities across 15
unique games; `regraded_summary.csv` counts each game once at its first original
quote globally and within each original revision. Revision groups overlap.
One game is still pending at this frozen input capture. Ties push and do not
enter binary proper scores. No original or new native snapshot is written.

`version_report.md` and its three CSVs report 64 historical study arms, 28
frozen archived-input counterfactuals, and all five native revisions. Historical
controls repeat across studies, cohorts/training differ, and archived target
quote capture times are unknown. Do not pool these evidence bases.

Run `python research/restore_v116.py`; CI compares the regenerated results with
absolute numerical tolerance 1e-8 and exact schema/identity checks. The frozen
inputs under `research/restore_v116_inputs` are copied from commit
6b04beb7079897d01537a14edf533c36dd5bc24e. The live build independently regenerates
current results and exposes the reports/downloads on the grades page.

Validation: the complete raw-box/profile production smoke build in an isolated
state directory regenerated all five current-season weekly boards and all
three public pages. Native snapshots were unchanged. The full 244-test suite
passed, followed by the additional cache-coverage test and relevant checks.
The historical cache is invalidated for tie-as-push reporting without changing
v1.16's forecast identity. v1.17 remains independently verified as archived
research; its captured target-price replay is retained.
