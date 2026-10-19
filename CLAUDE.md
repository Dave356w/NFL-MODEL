# Claude — working agreement for `Dave356w/NFL-MODEL`

This repository runs the NFL box-score composite and publishes it through
GitHub Actions and Pages. Be a rigorous, constructive collaborator: inspect real
code and data, report what the evidence establishes in proportion to its
strength, and turn criticism into a measurable next step. The owner directs the
product and decides which experiments to run.

Public presentation (owner decision 2026-10-19 UTC) is ATS-only: picks, frozen
handicaps, results, cover rates, units and ROI. Probability/moneyline calculations
and the original archives remain internal and in repository research reports.
Do not publish moneyline picks, win-probability values or moneyline CSV columns.
**Promotion hold (latest owner decision, 2026-10-19): do not merge or deploy
v1.19 until it demonstrates improvement over the market in every evaluated
season.** This supersedes the earlier promotion request. Production remains
v1.18 with its median ATS policy. v1.19 is an implemented research candidate:
a spread/total market winner baseline plus all 29 football inputs, converted
to a continuous spread without median mapping or a favorite-confidence penalty.
Its code and retrospective artifacts remain isolated on the candidate branch.
Use the same predeclared market-only benchmark, game cohort, fitting cutoff
and price basis for every season; a pooled gain cannot override a failing
season. Keep probability-score comparisons distinct from ATS returns and
report uncertainty. Beating a negative-return favorite control alone does not
establish an ATS edge. Keep failed seasons visible and do not tune a separate
candidate to each evaluation season to force a pass.
The public 2026 headline, weekly/game results, running units, same-game controls
and season CSV use the active production revision, one row per game. The
offline candidate rebuild includes all completed historical games with v1.19, including games
after the earlier median-policy adoption. These are retrospective forecasts,
not newly recorded bets. Only saved v1.19 ATS selections take priority over
v1.19 replay in candidate evaluation; never substitute older-revision locks. Keep source
tracking in backend reporting only, without source labels or breakdowns on the
public pages or season CSV; the pooled total is descriptive.
Show earlier seasons in the annual ATS performance table and history download;
detailed research stays in repository reports.

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
coefficient fitting stay on log loss. The v1.19 candidate implements the
previously tested full spread/total correction after exposed development.
Its promotion is on hold: its historical point ROI advantage is unresolved,
and its 2026 performance declines. Fresh validation at actual quotes is still
required. The former median-versus-raw comparison remains legacy research.

**Zero edge takes the market favorite** (owner decision 2026-10-19; lock policy
v2). Only a pick'em line with a zero projected spread skips. It applies
retrospectively. By owner decision (2026-10-19), saved zero-edge skips are
backfilled as favorite bets in grading and display, tracked as **Backfilled
recorded skip** in backend reporting and kept out of forward evidence. The saved files are never
rewritten. v1.19's retrospective rebuild remains offline under its own
revision and continuous ATS policy while promotion is on hold.

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
