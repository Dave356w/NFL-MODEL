# Pre-registration: forward hypotheses for `boxscore-composite-v1.9`, 2026 season

Committed 2026-10-07, before the forward ledger's first snapshot (`data/ledger_report.txt`:
"No snapshots recorded yet"; the first eligible game is 2026_05_TB_DAL, Thu Oct 8).
The rules below are fixed now. They may not be edited after the first snapshot; a
correction goes in a dated addendum at the bottom and does not change these rules.

## Sample

- **Rows**: `data/forward_ledger.csv`, experiment = the frozen 2026 recipe
  `rates_core_avail_cs_h8_r0.1` under `boxscore-composite-v1.9` (config signature
  `61cdea39…435cc2e`). First pregame snapshot per game only, as the ledger records it.
- **Bets**: 1u flat on the model's side at the moneyline saved in the snapshot
  (`units` column). Pushes count 0u. Games without both moneylines are excluded.
- **Market**: no-vig home probability from the two snapshot moneylines,
  q = implied(home) / (implied(home) + implied(away)).
- **Stopping**: the sample ends if the frozen recipe, `REVISION` or config signature
  changes. A new revision starts a new sample; it is never pooled with this one.
- **Checkpoints**: results are judged only at the end of the 2026 regular season
  (week 18) and after the 2026 postseason, then once per season. Interim numbers
  are reported but not acted on.

## H1: big disagreements carry the edge

**Source.** Post-hoc slice of the 2023–25 held-out reconstructions:
|model − market| > 0.17 gave +31.7% ± 18.5 ROI on n = 48. The threshold was chosen
after looking at those seasons, so the slice is a hypothesis, not evidence.

**Rule.** Rows with |model_wp − q| > 0.17.

**Report.** n, units, ROI ± SE, the market-correct null (mean of `null_ev` on the
same rows), the same-row market-favorite ROI, and paired log loss vs q.

**Decision** (cumulative over seasons, at the checkpoints):
- **Supported**: ROI − null ≥ 2 SE. Then a sizing or filter rule may be proposed as
  a new `REVISION`.
- **Falsified**: n ≥ 50 and ROI ≤ null.
- Otherwise **unresolved**.

**Power, stated now.** About 16 qualifying bets a season. With a per-bet SD near 1.2u,
the SE after one season is about 30 pts, so one season cannot resolve even a true
+20 pt edge. Expect "unresolved" at the end of 2026.

## H2: the model fades late in the season

**Source.** Post-hoc week-group diagnostics on 2023–25 (research tests 8–9, and the
model/market blend weights by week). The model's log loss relative to the market was
worst in weeks 14+. Basis 3 (post-hoc): a hypothesis only.

**Rule.** Per-game log-loss gain g = LL(market q) − LL(model), positive = model better.
Compare **weeks 14–18** (late) against **weeks 5–13** (mid). The ledger starts in week 5,
so weeks 1–4 are not observed in 2026. Postseason is reported separately and excluded.

**Report.** Mean g in each group ± SE, and the difference late − mid ± SE (Welch).
ROI in each group, with the null and the same-row favorite, as secondary.

**Decision** (at the end-of-regular-season checkpoint and cumulatively after that):
- **Supported**: late − mid ≤ −2 SE. Then the adaptive slow-early/fast-late decay
  (research test 9) is the first candidate for the next `REVISION`, built for a new
  season and never switched in mid-season.
- **Falsified**: late − mid ≥ 0.
- Otherwise **unresolved**.

## Not pre-registered

- The "early-season MOV fade" hypothesis from the 2026-10-07 research note has no
  written definition yet. It cannot be tested forward until one is committed here as
  an addendum, before the rows it would use exist.
- Everything else on the ledger (bands, sides, teams, weeks) is exploratory. With two
  pre-registered tests, read a single 2 SE result with that multiplicity in mind.

## Addenda

(none)
