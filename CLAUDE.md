# Claude — working agreement for `Dave356w/NFL-MODEL`

This repository runs the NFL box-score composite and publishes it through
GitHub Actions and Pages. Be a rigorous, constructive collaborator: inspect real
code and data, report what the evidence establishes in proportion to its
strength, and turn criticism into a measurable next step. The owner directs the
product and decides which experiments to run.

Picks, Results and Performance remain ATS-only: picks, frozen handicaps,
results, cover rates, units and ROI (owner decision 2026-10-19 UTC).
The owner added a public historical Calibration tab on 2026-10-30: aggregate
market/model WP calibration with signed median MOV and ATS pick ROI by spread band,
from 2023 through the current season, updated after complete weeks only.
Historical WP aggregates are authorized on that page and its aggregate CSV.
The owner requested ROI-only spread tables: market favorites grouped by market
spread magnitude and model ATS picks grouped by mapped model spread magnitude,
both graded against market handicaps at flat 1u and −110, with sample sizes and ROI SE.
Do not publish live moneyline picks, per-game probabilities or moneyline CSV columns.
This presentation change does not change v1.18, the median map or lock timing.
The public 2026 headline, weekly/game results, running units, same-game controls
and season CSV pool replayed and recorded results, one row per game (owner
request 2026-10-19). Saved ATS selections take priority over replay. Keep source
tracking in backend reporting only, without source labels or breakdowns on the
public pages or season CSV; the pooled total is descriptive.
Detailed research stays in repository reports; the historical Calibration tab
labels its reconstructed, exposed development basis separately from live results.

## Sources of truth

- `nfl_model.py`: the model. Its docstring is the version history; `MODEL.md`
  describes current behavior. Verify disputed behavior in code and tests, not in prose.
- `build_site.py` (pages, `data/latest` snapshot), `grade_ledger.py` (grading),
  `schedule_gate.py` (when builds run), `commit_data.py` (signed data commits),
  `validate_data_files.py` (data invariants), `kalshi.py` (secondary Kalshi quotes at lock,
  `data/kalshi_snapshots.jsonl`, append-only like the ledger), `matchup.py` (pre-registered
  H4 term at lock, `data/h4_terms.jsonl`, append-only).
- `data/forward_predictions.jsonl` is the forward ledger, and it is **append-only
  evidence**. `data/forward_ledger.csv` and `data/ledger_report.txt` are
  regenerated views. Quote live numbers from the current report, not from old PRs.
- `notebooks/NFL_C_B_MODEL.ipynb` is generated from `nfl_model.py`
  (`python sync_notebook.py`); never edit the notebook by hand.

## Evidence: keep the bases separate

1. **Forward ledger and ATS locks**: first pregame snapshots, injury-report
   gated, and the 60-minute ATS locks. These are the only native forward
   evidence.
2. **Held-out walk-forward seasons**: reconstructions with recipe selection
   restricted to earlier seasons. Use them for development and calibration
   shape; they are not forward confirmation.
3. **Current-season walk-forward and post-hoc slices**: diagnostics and
   hypotheses only.

**The goal is flat 1u ATS results at −110** (owner decision 2026-10-19: after
the hold, break-even prices and variance, moneyline betting does not look
profitable). The ATS evidence base is the 60-minute locks in
`data/ats_locks.jsonl`. Earlier ATS archives and replays are development
history. Lead ATS reports with W-L-P, skips, units, ROI ± SE (pushes in
the denominator), cover rate excluding pushes, n, the break-even cover rate of 52.4%
and the same-row always-favorite and always-home baselines. Per-band records
are descriptive, not per-game cover probabilities. Spread point error is a
secondary diagnostic. ROI is reported, not optimized: recipe selection and
coefficient fitting stay on log loss, and the median map stays fitted to
prior-season margins, unless the owner decides otherwise. That would be a new
`REVISION` or ATS policy version.

The open ATS question is whether the median map beats the raw model spread
(`raw_spread` against `market_spread` in the same lock). Compare both on the
same locked games; the owner reviews at 100 decided locks. Each lock already
saves both inputs, so this comparison needs no new capture.

**Zero edge takes the market favorite** (owner decision 2026-10-19; lock policy
v2). Only a pick'em line with a zero mapped spread skips. It applies
retrospectively. By owner decision (2026-10-19), saved zero-edge skips are
backfilled as favorite bets in grading and display, tracked as **Backfilled
recorded skip** in backend reporting and kept out of forward evidence. The saved files are never
rewritten; this exception covers only that grading rule.

**Moneyline is legacy research.** Its reports keep the flat 1u ROI basis in
`MODEL.md`: units, ROI ± SE, n, the market-correct null (negative by the hold,
not zero) and the same-row market-favorite baseline.

Report each comparison with its basis, n, revision, the same-row market
baseline, a proper score and uncertainty. A confidence
interval that crosses zero means the effect is unresolved; it does not show the
effect is zero. Pick accuracy is not calibration.

## Engineering contract

- **No lookahead.** Never let a game's own or later stats, snaps or labels
  into its features. Same-week roster status is ignored except the game week's
  own reserve list (v1.15, owner decision 2026-10-09). Membership and
  activations come only from the most recent roster before the game.
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
