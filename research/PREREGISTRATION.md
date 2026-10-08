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

**2026-10-07, before the first snapshot. Source figures re-measured; rules unchanged.**
The production held-out predictions (research test 11) give:
- **H1 rule:** n = 68, +13.4% ± 11.4, same-row favorite −7.4%, log-loss gain vs the
  market −0.081 ± 0.053 (the model is worse). The note's +31.7% on n = 48 came from a
  different recipe.
- **H2:** log-loss gain weeks 5–13 ≈ −0.028 ± 0.010 vs weeks 14–18 −0.055 ± 0.014,
  difference ≈ −0.026 ± 0.017.

**2026-10-07, before the first snapshot. H2 secondary split; the decision rule is unchanged.**
Research test 13 shows most of the held-out late gap is week 18 (gain −0.131 ± 0.044,
n = 48). Weeks 14–17 sit at −0.035 ± 0.013, the same as weeks 5–9. H2's report will
also show weeks 14–17 and week 18 separately. If H2 is supported but the gap is
confined to week 18, the candidate response is week-18 handling (motivation, rested
starters), not the adaptive decay.

**2026-10-07, before the first snapshot. The sample moves to v1.10; the rules are unchanged.**
The owner adopted v1.10 (decayed point margin) as production before any forward row
existed. H1 and H2 now apply to the forward rows of the `boxscore-composite-v1.10`
experiment: the 2026 recipe frozen in `data/frozen_recipe_2026_boxscore-composite-v1.10.json`
and its config signature. All other rules above are unchanged, including that a
later revision ends the sample.

v1.9 rows, if any are written before v1.10 reaches main, stay in the ledger as their
own experiment. They are reported separately and are not part of this sample.

The source figures above were measured on v1.9. v1.10's held-out probabilities differ
slightly (test 16), so H1's qualifying rows will differ a little.

**2026-10-07, before the first snapshot. The sample moves to v1.11; the rules are unchanged.**
The owner adopted v1.11 (depth-chart QB projection and the questionable-starter blend,
research test 21) as production before any forward row existed. H1 and H2 now apply to
the forward rows of the `boxscore-composite-v1.11` experiment: the 2026 recipe frozen in
`data/frozen_recipe_2026_boxscore-composite-v1.11.json` and its config signature. All other
rules above are unchanged, including that a later revision ends the sample.

v1.10 rows, if any are written before v1.11 reaches main (2026_05_TB_DAL can be recorded
once Wednesday's final report posts), stay in the ledger as their own experiment. They are
reported separately and are not part of this sample.

**2026-10-07. v1.12 (dated personnel events) proposed; the rules are unchanged.**
If the owner adopts `boxscore-composite-v1.12`, the revision change ends the v1.11 sample under
the stopping rule. H1 and H2 then apply to the forward rows of the v1.12 experiment (the 2026
recipe frozen in `data/frozen_recipe_2026_boxscore-composite-v1.12.json` and its config
signature) from its first snapshot. Any v1.11 rows written before v1.12 reaches main stay in
the ledger as their own experiment, reported separately and never pooled. v1.12 has no
historical personnel events, so its held-out reconstructions match v1.11 (research test 21).

**2026-10-08. New hypothesis H3 (Kalshi ladder pricing), committed before any Kalshi
capture exists and before its backtest result was seen. H1, H2 and their rules are unchanged.**

*Source.* Research discussion 2026-10-08: once the moneyline is known, the margin's spread
is about the same at every win probability (research tests on quantile widths), and the
model adds nothing measurable to a moneyline-based margin estimate (held-out 2023–25). So
the only plausible ladder edge is the shape of real margins (3, 7, 10) against how Kalshi
prices its "wins by over X.5" rungs. Independent of the model.

*Reference (frozen).* `data/kalshi_ladder_reference.csv`, built once by
`research/ladder_pricing.py --build` from 2006–2024 games: for each favorite no-vig
moneyline probability (0.01 grid; games within ±0.03, widened to ±0.05 below 150), the
share in which the favorite's margin exceeded each half-point strike, and the tie share.
It is not refit while H3 runs.

*Rule.* Every game with a Kalshi capture in `data/kalshi_snapshots.jsonl` (games locked in
the forward ledger). Using the snapshot's two moneylines, price every captured rung with
strike ≤ 17.5 on both teams' ladders and both game-winner markets (a tie pays $0.50). Buy
at most **one** rung per game: the one with the largest expected profit per contract after
the estimated fee, est − ask − 0.07 × ask × (1 − ask), and only if that is ≥ $0.03.
1u staked at the captured ask (`ladder_units`).

*Report.* n, W-L, units, ROI ± SE, and the Kalshi-mid null on the same bets (`ladder_null`:
the ROI if each bought rung's captured mid were exactly right).

*Decision* (cumulative, at the season checkpoints above):
- **Supported**: ROI − null ≥ 2 SE with n ≥ 50.
- **Falsified**: n ≥ 50 and ROI ≤ null.
- Otherwise **unresolved**.

*Power, stated now.* Kalshi's ladder sat within 1–3¢ of the reference on every TB@DAL rung
(best edge 1.9¢), so qualifying bets may be rare; the count is reported each week. Most
bought rungs will be deep, low-priced ones with a per-bet SD of 2–4u, so even 50 bets
resolve only a large edge. The backtest on Kalshi's 2025–26 books (out of sample for the
2006–2024 table) is development evidence and will be reported as such.
