# Claude — working agreement for `Dave356w/NFL-MODEL`

This repository runs the NFL box-score composite and publishes it through
GitHub Actions and Pages. Be a rigorous, constructive collaborator: inspect real
code and data, report what the evidence establishes in proportion to its
strength, and turn criticism into a measurable next step. The owner directs the
product and decides which experiments to run.

## Sources of truth

- `nfl_model.py`: the model. Its docstring is the version history; `MODEL.md`
  describes current behavior. Verify disputed behavior in code and tests, not in prose.
- `build_site.py` (pages, `data/latest` snapshot), `grade_ledger.py` (grading),
  `schedule_gate.py` (when builds run), `commit_data.py` (signed data commits),
  `validate_data_files.py` (data invariants), `kalshi.py` (secondary Kalshi quotes at lock,
  `data/kalshi_snapshots.jsonl`, append-only like the ledger).
- `data/forward_predictions.jsonl` is the forward ledger, and it is **append-only
  evidence**. `data/forward_ledger.csv` and `data/ledger_report.txt` are
  regenerated views. Quote live numbers from the current report, not from old PRs.
- `notebooks/NFL_C_B_MODEL.ipynb` is generated from `nfl_model.py`
  (`python sync_notebook.py`); never edit the notebook by hand.

## Evidence: keep the bases separate

1. **Forward ledger**: first pregame snapshots, injury-report gated. This is
   the only native forward evidence.
2. **Held-out walk-forward seasons**: reconstructions with recipe selection
   restricted to earlier seasons. Use them for development and calibration
   shape; they are not forward confirmation.
3. **Current-season walk-forward and post-hoc slices**: diagnostics and
   hypotheses only.

**The owner's goal metric is flat 1u ROI at the moneyline on the model's side**
(see `MODEL.md`). Lead with it: units, ROI ± SE, n, the market-correct null
(negative by the hold, not zero) and the same-row market-favorite baseline.
Log loss/Brier are secondary. ROI is reported, not optimized: recipe selection
and coefficient fitting stay on log loss unless the owner decides otherwise.
That would be a new `REVISION`.

Report each comparison with its basis, n, revision, the same-row market
baseline, a proper score and uncertainty. A confidence
interval that crosses zero means the effect is unresolved; it does not show the
effect is zero. Pick accuracy is not calibration.

## Engineering contract

- **No lookahead.** Never let a game's own or later stats, snaps or labels
  into its features. Same-week roster status is ignored, and only the most
  recent roster before the game is used.
- **Protect the ledger.** Never rewrite, backfill or delete snapshots. A
  change to features, the selection grid or config that changes
  `config_signature()` needs a new `REVISION` and `OUTPUT_NAME`. That starts a
  new experiment rather than altering a frozen one.
- **Protect the build.** Keep `site-build` serialized with
  `cancel-in-progress: false`. Keep the commit step running after a failed
  render (`!cancelled()`). Keep tests out of `build.yml`: a red test must never
  cost a pregame snapshot. Do not hand-commit bot-generated `data/` or `public/`.
- **Test behavior.** Add positive and negative fixtures for any new rule.
  `nfl_model.self_test()` runs inside pytest.

Before a PR:

    python sync_notebook.py
    python validate_data_files.py
    python -m pytest tests/ -q

If a check cannot run, say exactly what was and was not verified.

## Communicating

For research questions, cover: what works today (with basis), the open
questions, one to three candidate changes with what would falsify each, and
the recommended next test. For implementation requests, deliver the change,
then summarize the files, behavior preserved, tests run and remaining
limitations.
