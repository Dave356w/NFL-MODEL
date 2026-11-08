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
both graded against market handicaps at flat 1u, at each game's actual spread price for the side bet
(owner decision 2026-11-04; −110 only where no price exists, counted), with sample sizes and ROI SE.
Do not publish live moneyline picks, per-game probabilities or moneyline CSV columns.
The owner added two Calibration-page changes on 2026-11-04. The WP tables fold to the four 50%+
favorite bands, each game counted once; the CSV keeps the eight two-sided bands. The page also adds
aggregate historical moneyline ROI on MODEL.md's legacy flat 1u basis: the model favorite vs the
same-game market favorite, with the market-correct null and SE. This is page only, never in the CSV.
This presentation change does not change v1.18, the median map or lock timing.
The public 2026 headline, weekly/game results, running units, same-game controls
and season CSV pool replayed and recorded results, one row per game (owner
request 2026-10-19). Saved ATS selections take priority over replay. Keep source
tracking in backend reporting only, without source labels or breakdowns on the
public pages or season CSV; the pooled total is descriptive.
**v1.19 is production (owner decision 2026-11-03):** v1.18 fitted on ten core terms
(research Test 50 arm S3). Picks, Results, Performance and Calibration show v1.19:
2026 games whose ATS deadline precedes 2026-11-05 12:00 UTC use v1.19's replayed pick,
replacing v1.18's displayed locks; later games use v1.19's own 60-minute locks. No new page
tags or warnings. v1.18's snapshots and locks stay unchanged in their append-only files.
**The weekly decayed median map is production (owner decision 2026-11-04; research Test 59 arm D):**
the map is refit before every week with a one-season half-life (map policy v2), and 60-minute locks use
ATS lock policy v3. Picks, Results, Performance and Calibration regenerate under it; v1/v2 locks keep
their saved annual rules. v1.19 and `config_signature()` are unchanged.
Detailed research stays in repository reports; the historical Calibration tab
labels its reconstructed, exposed development basis separately from live results.

**v1.20 availability safeguards (owner request 2026-11-04) supersede the v1.19 production identity above.** The ten-term fit is unchanged. Only upcoming games can consume timestamped, sourced game observations; historical inputs and the v1.16 shadow remain unchanged. `data/availability_observations.jsonl` is a curated input, not a bot-generated snapshot. See `AVAILABILITY.md`. New injury coefficients still require separate validation.

**v1.21 automatic collection (owner request 2026-11-04) supersedes v1.20's production identity.** All 32 official club RSS feeds, game injury tables and official inactive announcements are collected automatically. The automatic journals are bot-generated and append-only; the curated journal remains separate. Both teams' fresh complete official inactive lists are required before an ATS candidate is saved. The cutoff hold watches games even before a candidate exists. All previous revision signatures, historical inputs and the v1.16 shadow are preserved. The generated single-cell notebook embeds the collector as well as the model.

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
earlier games' margins (weekly, one-season half-life, since 2026-11-04), unless the owner decides otherwise. That would be a new
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

Owner-requested TNF recovery (2026-11-05): `ats_retro_requests.json` explicitly
authorizes JAX-BAL's retro lock from the board committed before T-60. The workflow
applies it through `retro_lock.py` into the normal `ats_locks.jsonl` journal and
normal public picks/results/totals. Keep actual recovery time, original availability
blockers and source-commit hashes in the backend record. This is an explicit exception
to the no-backfill rule, not authorization to reconstruct other missing locks.

Owner-requested Sunday lock repair (2026-11-08): the eight additional entries
in `ats_retro_requests.json` recover CIN-ATL and the seven 13:00 ET games from
their last committed pre-cutoff boards. Keep these selections in normal public
results. Backend `ats_basis` identifies all retro locks separately from native
60-minute locks; never rewrite earlier journal rows or use post-cutoff inputs.
The follow-up activation request also covers HOU-LAC and LV-SF, which missed
their 12:05 Pacific cutoff; their pinned 19:57 UTC board remains the sole basis.

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

Owner activation follow-up (2026-11-08): GB-NE may also be recovered from the
pinned 20:17 UTC board after its 12:25 Pacific cutoff when no native lock exists.
The original collection/medical blockers remain in its source evidence.
