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

**2026-10-08. New hypothesis H4 (pass-matchup interaction), committed before any H4 term is
recorded for a forward game. H1, H2, H3 and their rules are unchanged.**

*Source.* Research Test 24 (`research/README.md`): of four matchup interactions fixed before
running, only the pass term passed its Bonferroni bar on held-out 2023–25 (partial r with the
margin beyond the spread +0.099, 98.75% CI +0.004 to +0.193; +0.09 / +0.08 / +0.13 by season),
and it did not replicate in 2019–22 (−0.015). It is therefore a hypothesis, not evidence.
Independent of the model and its revision.

*Term (fixed).* `matchup.py`: z(home offense) × z(away defense allowed) − z(away offense) ×
z(home defense allowed) on net pass yards per pass play (`rates_core`, half-life 16 pregame
profiles); z = (value − mean over the season's games so far, pregame values only) / SD over
2019–22 games. Recorded once per game, at the run that locks it in the forward ledger, in
`data/h4_terms.jsonl`. With this season-to-date centring the held-out 2023–25 figure is +0.092
[+0.024, +0.159] (95%), essentially Test 24's.

*Sample.* Every graded game with a recorded term, one row per game whatever the experiment.

*Statistic.* Partial correlation of the term with the final home margin, controlling linearly
for the snapshot's market spread (both regressed on the spread), with a 2,000-draw game
bootstrap 95% CI (`h4_summary` in `grade_ledger.py`).

*Decision* (cumulative, at the season checkpoints above):
- **Supported**: the 95% CI lies above zero. Even then the term enters the model only as a new
  `REVISION`, by the owner's decision.
- **Falsified**: the CI's upper bound is below +0.05 (too small to matter), or n ≥ 600 and r ≤ 0.
- Otherwise **unresolved**.

*Power, stated now.* About 250–270 forward games a season give SE(r) ≈ 0.06, so a true r of
0.10 is likely unresolved after one season and needs about three. A 2026-only result will
probably read "unresolved"; that is not evidence against H4.


**2026-10-08, owner-selected v1.13: lead/deficit peaks replace final MOV.**
This changes production features and therefore starts a new experiment,
`boxscore-composite-v1.13`, with new candidate families and config signature.
Existing v1.12 and earlier frozen recipes and ledger rows are not altered or
pooled with v1.13. The development replacement comparison gave log-loss gain
0.000080 [-0.001767, +0.001872] on 815 games, with unresolved ROI improvement on
811 same-row directional bets. This adoption is an owner choice, not forward
confirmation. H1/H2 stopping and experiment-specific sample rules above remain
as written; this note does not silently extend them to the new revision. H3's
market-based frozen ladder and H4's separately recorded matchup term are unchanged.

**2026-10-08, owner-selected v1.14: omit separate offensive/defensive sack rates.**
This simplification starts `boxscore-composite-v1.14` with new active families,
output identity and configuration signature. Net passing retains sack yards and
sack plays; other features and the candidate grid keep their definitions.
Exploratory fixed-recipe ablation on 2023–2025 gave log loss 0.629536 versus
0.630226 and flat 1u ROI +0.77% versus +0.19% on 811 same-row games. The gain
was unresolved even before multiple-test correction and was not uniform by
season. This adoption does not establish superiority or reduced variance.
Existing v1.13 and earlier recipes/snapshots remain separate and intact.
H1/H2 stopping and experiment-specific sample rules remain as written; this
note does not silently extend them to v1.14. H3/H4 definitions are unchanged.

**2026-10-09. New hypothesis H5 (low-total moneyline underdogs), committed before any H5 record
exists. H1–H4, their rules and the v1.14 experiment are unchanged.**

*Source.* Owner's question whether moneyline prices reflect the spread of possible margins, not
only the expected margin. On 2006–2025 regular seasons (nflverse schedules, n = 5,199), realized
dispersion of (margin − spread) was flat at about 13.2 points across total quartiles and spread
sizes, and favorites won at their no-vig moneyline rate overall. One post-hoc slice stood out: in
the lowest-total quartile (total ≤ 41) favorites won 2.8 points less often than priced (±1.4), and
1u on every underdog there returned +5.8% ± 4.9 (n = 1,067) against a −2.5% market-correct null,
+4.8% in 2006–15 and +7.3% in 2016–25; underdogs in all other games returned −6.5%. The cut is
that quartile's edge, chosen after looking at four quartiles: a hypothesis, not evidence.
Independent of the model and its revision.

*Rule (fixed).* `totals.py` records, once per game at the build that locks it in the forward
ledger, the nflverse schedule's `total_line` and both moneylines in `data/h5_totals.jsonl`. Every
recorded game with total ≤ 41.0 gets 1u on the moneyline underdog (lower no-vig probability) at
the recorded price; a pick'em is skipped and a tie is a push.

*Sample.* Every graded qualifying game, one row per game whatever the experiment.

*Report* (`h5_summary` in `grade_ledger.py`). W-L-P, units, ROI ± SE, the market-correct null
(mean of q × payout − (1 − q) for the underdog), and the market favorite on the same rows.

*Decision* (cumulative, at the season checkpoints above):
- **Supported**: ROI minus the null, less 1.96 SE, is above zero. Even then nothing enters the
  model or the headline without the owner's decision.
- **Falsified**: n ≥ 300 and ROI at or below the null.
- Otherwise **unresolved**. No verdict before 10 graded bets.

*Power, stated now.* 11–92 qualifying games a season in 2016–2025 (median about 42). A per-bet SD
near 1.4u gives SE ≈ 20 points after one season, so a true edge of +8 points over the null is
very likely unresolved for several seasons, and the falsification bar needs about seven. A
2026-only result will read "unresolved"; that is not evidence against H5.

**2026-10-09, owner-selected v1.15: the game week's own reserve list counts out.**
This changes availability features and starts `boxscore-composite-v1.15`, with a new output
identity and configuration signature; families, the candidate grid and every other feature keep
their definitions. The evidence was research Test 28 (participation and closing-market
diagnostics, no game outcomes); the held-out comparison (Test 29) was run after the adoption
decision and is reported, not used as a gate. Existing v1.14 and earlier recipes/snapshots
remain separate and intact. H1/H2 stopping and experiment-specific sample rules remain as
written; this note does not silently extend them to v1.15. H3/H4/H5 definitions are unchanged.

**2026-10-13, owner decision, committed before any week-6 snapshot exists. H1 and H2 apply to
v1.16 from 2026 week 6; their rules are unchanged.**
The v1.12 sample ended when v1.13 was adopted, with one graded game, and no addendum extended
H1/H2 to v1.13–v1.17. The owner restored v1.16 as production on 2026-10-12. H1 and H2 now apply
to the forward rows of the `boxscore-composite-v1.16` experiment (config signature
`9dad9b9a…62dcd26`, frozen 2026 recipe `rates_core_avail_cs_peaks_nosacks_h8_r0.1_market_product_1sd_i0.1`)
for games in 2026 week 6 or later, first pregame snapshot per game only. When this was committed
the newest snapshot was written 2026-10-12 21:59 UTC for a week-5 game; no week-6 snapshot existed.

- **Excluded:** the 14 week-5 v1.16 rows. They were written and graded before this addendum, and
  the author has seen them: one qualified for H1 (2026_05_SF_SEA, model − q = +0.35, lost 1u).
  v1.17 and v1.12–v1.14 rows stay their own experiments; nothing is pooled.
- **Market:** q as in the Sample section, from the snapshot moneylines. For v1.16 it equals the
  stored `market_wp` and the model's own market input.
- **H2 groups:** weeks 14–18 against weeks 5–13 as written; in 2026 the mid group starts at
  week 6. The postseason stays excluded from H2.
- **Stopping:** unchanged. A change to `REVISION`, the config signature or the frozen recipe ends
  this sample. Reporting-only changes that leave all three unchanged (v1.16.1) do not.
- **Checkpoints and decision rules:** unchanged and cumulative: the end of the 2026 regular
  season, after the postseason, then once per season.
- **Grading:** `h1_summary` and `h2_summary` in `grade_ledger.py`, printed in
  `data/ledger_report.txt`.

*Source figures re-measured on v1.16, known to the author.*
- 2023–25 held-out reproduction (`research/restore_v116_results/historical_reproduction.csv`;
  exposed, since v1.16 was chosen on these seasons). H1: 10 of 816 rows qualify (4, 1, 5 by
  season), 7-2-1, +5.0u, +50.0% ± 34.1 against a −4.1% null and +20.8% for the same-row
  favorite; log-loss gain vs q +0.155 ± 0.194. H2: weeks 5–13 +0.0070 ± 0.0059 (n = 390),
  weeks 14–18 −0.0053 ± 0.0093 (n = 234), difference −0.0123 ± 0.0110; week 18 alone
  −0.0171 ± 0.0199 (n = 48).
- 2017–20 out of sample (`research/out_of_sample_results/predictions.csv`; protocol committed
  before any forecast existed). H1: 7 of 1,023 rows qualify, 2-4-1, −1.56u, −22.3% ± 42.3
  against a −2.4% null. H2: weeks 5–13 −0.0038 ± 0.0049 (n = 516), weeks 14–17 −0.0109 ± 0.0070
  (n = 256; no week 18 before 2021), difference −0.0071 ± 0.0086.

*Power, stated now.*
- **H1:** v1.16 starts from the market's log-odds, so it rarely departs from q by more than 0.17
  (median |model − q| about 0.03, 99th percentile 0.15–0.18). Expect two or three qualifying bets
  a season. With a per-bet SD near 1.1u, one season's SE is about 70 points, and the
  falsification bar (n ≥ 50) is roughly two decades away. H1 will read "unresolved" for many
  seasons, which is not evidence either way. A different threshold would be a new hypothesis,
  registered on its own, not a correction of this one.
- **H2:** about 110 mid and 80 late graded games in 2026, with a per-game SD of 0.12–0.14,
  give a difference SE near 0.019. The held-out difference (−0.012) is well inside that, so a
  2026 verdict is likely "unresolved". If that difference is the truth, the observed late − mid
  still lands at or above zero (the falsification bar) about a quarter of the time.

**2026-10-13, owner decision, committed before any week-6 snapshot exists. New hypothesis H6:
v1.16's market-underdog picks. H1–H5 and their rules are unchanged.**

*Source.* v1.16 bets the market favorite in every game except those where it makes the market
underdog its favorite, so only those games separate its flat-bet results from betting the
favorite. On v1.16's own predictions:
- 2023–25 held-out reproduction (`research/restore_v116_results/historical_reproduction.csv`;
  exposed, since v1.16 was chosen on these seasons): 42 picks (12, 14, 16 by season), 26-16-0,
  +14.35u, +34.2% ± 17.0 against a −4.2% null; the same-row favorite −34.6%; log-loss gain vs q
  on those games +0.043 ± 0.044.
- 2017–20 out of sample (`research/out_of_sample_results/predictions.csv`): 49 picks (11, 12, 11,
  15), 27-21-1, +9.46u, +19.3% ± 15.2 against a −2.4% null; the same-row favorite −19.0%;
  log-loss gain +0.023 ± 0.030.
Returns were positive in each of the seven seasons. The slice was proposed after both results
were seen, so it is a hypothesis, not evidence.

*Rule (fixed).* Rows: the H1/H2 sample of the addendum above (the first v1.16 snapshot per game
under configuration `9dad9b9a…62dcd26` and its frozen recipe, for games from 2026 week 6 on,
cumulative across seasons); H6 ends when that sample ends. A row qualifies when the no-vig
probability of the side v1.16 backs, from the snapshot moneylines, is below 0.5: v1.16 makes the
market underdog its favorite. Model pick'ems (no bet) and market pick'ems (q = 0.5) never
qualify. The bet is the model's ordinary flat 1u at the snapshot price; a tie is a push. There
is no other filter.

*Report* (`h6_summary` in `grade_ledger.py`, printed in `data/ledger_report.txt`). W-L-P, units,
ROI ± SE, the market-correct null (mean of `null_ev` on the same rows), the same-row market
favorite (the other side of the same games), and the paired log-loss gain vs q.

*Decision* (cumulative, at the season checkpoints above):
- **Supported**: ROI − null ≥ 2 SE. Even then nothing changes the model, the stake policy or the
  headline without the owner's decision.
- **Falsified**: n ≥ 50 and ROI at or below the null.
- Otherwise **unresolved**. No verdict before 10 graded bets.

*Power, stated now.* 11–16 qualifying games a season in 2017–25, all near-even (the mean no-vig
probability of the picked underdog is 0.45–0.46). A per-bet SD near 1.1u gives an SE of about
29 points after one season. If the true edge over the null equals the 2017–20 estimate
(+21.7 points), the expected z after k seasons is about 0.74 √k: support at 2 SE has even odds
only after about seven seasons. The falsification sample (n ≥ 50) arrives around the end of
2029; at that point a true edge of that size would still be called falsified about 8% of the
time, and no edge about half the time. A 2026-only result will read "unresolved"; that is not
evidence against H6.

*Overlap and multiplicity.* An H6 row can also be an H1 row (an underdog pick more than 0.17
from q), so H1 and H6 are not independent. With H1–H6 registered, read any single 2 SE result
with that multiplicity in mind. The 14 excluded week-5 v1.16 rows contain no underdog pick.

**2026-10-14, owner request, committed before any week-6 snapshot exists. New hypotheses H7
(departure slope by total) and H8 (input trends in wrong picks, Test 37). H1–H6 and their rules
are unchanged.**

*Total used by both.* The game's `total_line` in `data/h5_totals.jsonl` (the nflverse total at
the game's first lock); if a game has no row there, the nflverse schedule `total_line` at grading.
Bands: low ≤ 41, mid 41.5–47, high ≥ 47.5.

**H7: v1.16's departures from the market carry information in high-total games, not in
low-total ones.**

*Source.* Post-hoc slices of v1.16's own predictions, proposed after both were seen. The
departure slope `b` fits `logit P(home) = logit(q) + b·d` with `d = logit(p) − logit(q)` (b = 1:
departures right-sized; b = 0: no information), cluster-robust by week:
- 2017–20 out of sample: high +0.68 ± 0.49 (366 bets), mid −0.34 ± 0.48, low −0.32 ± 0.70 (162);
  high − low +1.00 ± 0.86.
- 2023–25 held-out (exposed): high +1.05 ± 0.49 (202), mid +0.81 ± 0.51, low −0.12 ± 0.56 (186);
  high − low +1.17 ± 0.74.

*Rule (fixed).* Rows: the H1/H2/H6 sample (the first v1.16 snapshot per game under configuration
`9dad9b9a…62dcd26` and its frozen recipe, games from 2026 week 6 on, cumulative across seasons);
H7 ends when that sample ends. Binary results only. `p` is the snapshot `model_wp`, `q` the no-vig
probability from the snapshot moneylines. Fit `b` separately in the high and low bands (Newton,
offset `logit(q)`, one coefficient), with cluster-robust SEs by season-week.
Δ = b_high − b_low, SE = √(se_high² + se_low²).

*Decision* (cumulative, at the season checkpoints):
- **Supported**: Δ ≥ 2 SE.
- **Falsified**: each band has at least 60 graded binary games and Δ ≤ 0.
- Otherwise **unresolved**. No verdict before each band has 30 graded binary games.

*Power, stated now.* High totals were 25–36% of games in 2017–25 and low totals 16–23%: about 55
high and 40 low graded games in 2026 weeks 6–18, then about 75 and 55 a season. Scaling the
held-out SEs gives an SE on Δ near 1.5 after 2026 and 1.3/√k after k full seasons. If the true Δ
is +1.1, support at 2 SE has even odds only after about six seasons. The falsification sample
arrives during 2027, when a true Δ of +1.1 would still read Δ ≤ 0 about one time in five. A 2026
result will read "unresolved".

**H8: input trends in the model's wrong picks continue forward (Test 37).**

*Source.* `research/RESIDUAL_TRENDS.md`: a scan of 30 inputs × 4 contexts (all games and the three
total bands) for residuals `y − p` that correlate with an input, discovered on 2017–22 and tested
on 2023–25. The forward set is fixed mechanically by that protocol (candidates with |z| ≥ 2 on
2017–22, then those whose 2023–25 z keeps the discovery sign, at most five) from committed
historical data only; the results file lists it. Nothing is chosen after this addendum.

*Rule (fixed).* Rows: the first v1.18 snapshot per game under configuration `73636f30…bca58a20`
and its frozen 2026 recipe, games from 2026 week 6 on, cumulative across seasons. A change to
`REVISION`, the configuration signature or the frozen recipe ends the sample. Binary results
only. Inputs are the snapshot's `model_inputs`, `p` its `model_wp`, `q` the no-vig probability
from its moneylines; the departure is `logit(p) − logit(q)`. For each trend, within its context:
`x̃ = x − mean(x)` over the forward rows, `z_F = Σ r·x̃ / √(Σ_weeks (Σ r·x̃)²)` with
`r = y − p`, and `z_F* = sign(z_discovery)·z_F`.

*Decision* (per trend; K_F trends; cumulative, at the season checkpoints):
- **Supported**: z_F* ≥ Φ⁻¹(1 − 0.05/K_F).
- **Falsified**: the context has at least 100 graded binary games and z_F* ≤ 0.
- Otherwise **unresolved**. No verdict before 30 graded binary games in the context.

A supported trend changes nothing by itself; acting on it is a new `REVISION` and the owner's
decision.

*Report.* `python research/residual_trends.py --forward` prints, per trend: n, z_F*, the effect
per SD, the wrong-pick view (model-side wins minus expected wins by third of the signed input)
and flat 1u ROI with the null and the same-row favorite.

*Power, stated now.* About 190 graded games in 2026 weeks 6–18 and 272 a season after that,
against 1,560 discovery games. If a trend's true effect equalled its discovery estimate (which
selection inflates), its expected forward z after one season would be about
|z_D|·√(n_F/n_D): roughly 0.35·|z_D| for an all-games trend, less inside a total band. Expect
"unresolved" after 2026; the 2023–25 confirmation is the informative step until then.

*Multiplicity.* H1–H8 are now registered, and H8 holds up to five trends. H6 and H7 overlap with
H8's departure and market cells. Read any single 2 SE result with that in mind.

**2026-10-15, owner request ("build and test items"), committed and pushed before any 2006–2012
disagreement was compared with an outcome and before H9 has any graded row. New: the 2006–2012
allocation and H9. H1–H8 and their rules are unchanged.**

*2006–2012 allocation.* Test 46 (`research/ML_SPREAD_2006_12.md`, market only) is this block's
first and only named consumer and runs once. A later reduced-model test on 2008–2012 may still be
proposed. It must disclose that Test 46 looked at these seasons' market residuals, and it must name
its own multiplicity.

**H9: when the moneyline and the spread disagree, the outcome leans toward the spread's view
(model-independent).**

*Source.* Test 42's disagreement coefficient (negative in every era; "the one lead worth a forward
look") and the 2013–2026 re-estimates, each about 1 SE. Test 46 replicates it once on 2006–2012. H9's
definition and threshold are frozen here, before Test 46 runs, so the replication cannot tune them.

*Rule (fixed).* Rows: one per game, from 2026 week 6 on, cumulative across seasons. Each row is the
first production snapshot for the game: `boxscore-composite-v1.18` under configuration
`73636f30…bca58a20`, or a later production revision's first snapshot if production changes. H9 uses
only the snapshot's prices, so a model change does not end the sample. From those prices:
* `q` is the no-vig home probability from the snapshot moneylines;
* `q_s = Φ(spread_line/12.37)` uses the snapshot `spread_line`;
* `dis = logit(q) − logit(q_s)`, both clipped to [1e-4, 1 − 1e-4].

A row without both moneylines or a spread is excluded before grading.
* **Primary**: `b` in the logistic regression of the home win on an intercept, logit(q) and dis
  (free slopes), with cluster-robust SEs by season-week. Binary results only.
* **Secondary rule**: 1u at the snapshot moneyline on the side the spread favors more when
  |dis| ≥ T = 0.11133 (away if dis > 0, home if dis < 0). Ties push. Reported with the market-correct
  null and the same-row favorite.

*Decision* (cumulative, at the season checkpoints):
- **Supported**: b ≤ −2 SE.
- **Falsified**: at least 600 graded binary games and b ≥ 0.
- Otherwise **unresolved**. No verdict before 300 graded binary games.
- **The rule**: falsified at 100 or more bets if ROI ≤ its null; supported if ROI − null ≥ 2 SE.

*Power, stated now.* About 193 games in 2026 weeks 6–18, then 272 a season. At b = −0.85 per unit
the SE reaches about 0.67 only after about 1,650 games (roughly 2032). A 2026 or 2027 result will
read "unresolved"; that is not evidence against H9. With T at the 75th percentile, the rule sees
about a quarter of games: about 48 bets in 2026 and 68 a season after that.

*Multiplicity.* H1–H9 are now registered. H9 is model-independent and does not overlap the
model-side tests, but read any single 2 SE result with nine hypotheses in mind.

**2026-10-15 (same day, separate change): favorite-penalty verdict.** The forward verdict in
`research/FAVORITE_PENALTY.md` is replaced by a three-way rule judged at the January checkpoints. It
uses 97.5% week-cluster bounds; falsification means the data exclude the adopted +0.002 gain. The
addendum there gives the reason (the rule as written falsified a true +0.0023 gain 35–50% of the
time) and the simulated error rates. It was written after the 13 week-5 native rows were seen and
does not use their values. H1–H9 are unchanged and stay judged only at the season checkpoints.

**2026-10-15 (later the same day): favorite-penalty bounds corrected.** The three-way penalty rule
now uses t(G − 1) critical values, where G is the number of season-weeks, in place of z = 2.24.
* Its first error rates came from Gaussian paths with a known SE.
* Resampling historical weeks with an estimated SE shows that z = 2.24 falsifies a true +0.0023
  gain 3.0% → 6.4% of the time over five looks.
* With t(G − 1), the rate is 1.9% → 5.1%, and false support at 0 is 0.6% → 2.2%.
* The 13 graded week-5 rows are already in the registered sample. Given them, falsification is out
  of reach through 2031: a true 0 is falsified 0.8% of the time by January 2031.
* A checkpoint is the first report after week 18 is fully graded.

It was chosen from the simulation alone, before any verdict point. See the second 2026-10-15
addendum in `research/FAVORITE_PENALTY.md`.

**2026-10-27, owner request ("pre-register option 3 and run it"), committed and pushed before
any H10 score exists. New hypothesis H10 (band margin distributions vs the Kalshi spread
ladder). H1–H9 and the favorite-penalty rule are unchanged.**

*Source.* Owner proposal 2026-10-27: alt-line suggestions so the ATS bet aligns with the band's
margin distribution rather than flipping on a half-point hook. An alt-line chooser would price
rungs from the production band's empirical margins. This test asks first whether those margins
predict "team wins by over X.5" better than Kalshi's own prices. It places no bets. SB1
(`research/SOFT_BAND_DISTRIBUTIONS.md`, 2026-10-26) found the same distributions no better
than the paired sportsbook price at the main line; H10 extends the question to whole ladders.

*Already seen when this was written.* Aggregate forward moneyline/ATS records, H3 ladder bets
and the Kalshi alt-line rule in `data/ledger_report.txt`; SB1's results; ladder quote widths and
rung counts (outcome-free). No rung-level comparison of band probabilities with Kalshi mids
against outcomes has been computed.

*Forecast (fixed).* SB1's hard empirical band PMFs (`research/soft_band_distributions.py`,
`fit_prior` on its frozen `games.csv`, seasons strictly before the target season). For 2026 this is
exactly the production median map's training sample: 2021–2025, 1,359 games, band counts
497/478/228/156, medians 3/4/7/14. Raw spread = `nfl_model.implied_spread(model_wp)`; band by
|raw| with cuts 3/7/10; the PMF of the actual margin signed toward the raw winner. A rung's
probability is the PMF mass on that team's margin > strike. No refit while H10 runs.

*Primary sample (forward).* Every graded `boxscore-composite-v1.18` row in
`data/forward_ledger.csv` (first pregame snapshot per game) with a Kalshi capture, joined exactly
as `grade_ledger.kalshi_grades` does (first capture at or after `generated_utc`, else the last
earlier one; the count of earlier ones is reported). Every rung on both teams' ladders with
strike ≤ 17.5 (H3's cap) and a valid quote, 0 < bid ≤ ask < 1 and ask − bid ≤ 0.05. Game-winner
markets are excluded. Kalshi probability = (bid + ask) / 2, no further normalization.

*Score.* Binary log loss per rung; both probabilities clipped to [0.005, 0.995] (Kalshi's
half-tick floor). Per game, the mean over its rungs of Kalshi loss − band loss (positive = band
better). **Primary statistic: the mean of the per-game gains**, games weighted equally, SE = SD
across games / √n.

*Decision* (on the primary sample, at the first run after it reaches 100 graded games, then final):
- **Supported**: gain − 2 SE > 0 with n ≥ 100 games. Only then would option 1 or 2 (an alt-line
  chooser on the map's side) be worth a separate pre-registration.
- **Falsified**: n ≥ 100 games and gain ≤ 0. The band distributions then give no basis for
  choosing among Kalshi rungs; options 1 and 2 are not built.
- Otherwise **unresolved**. Earlier runs are interim readings with no verdict.

*Secondary, reported, never decisive.* (a) SB1's soft PMFs on the same rungs; (b) H3's frozen
moneyline reference (`kalshi.ladder_probability` at the row's no-vig moneyline) on the same rungs;
(c) the near-line subset, rungs with |strike − that team's sportsbook line margin| ≤ 4; (d) the
`boxscore-composite-v1.16` forward rows, overlapping games and not independent; (e) a development
cohort, exposed and not forward: `data/kalshi_historical/kalshi_quotes.csv` 2025–2026 main-spread
rung (favorite over the strike, mid of yes bid/ask, captured two hours pregame) scored with SB1's
`games.csv` raw spread and the fit for that season. Per-rung pooled numbers are descriptive.

*Power, stated now.* About 14 v1.18 games a week carry a Kalshi ladder, so n = 100 arrives around
2026 week 13. Rungs within a game are strongly correlated; the game is the unit.

*Multiplicity.* H1–H10 are now registered. H10 is a prediction test with no betting rule.

**2026-10-27 (later the same day), owner request ("run the soft band version as a separate
test"), committed and pushed before any H11 code exists. New hypothesis H11 (soft band margin
distributions vs the Kalshi spread ladder). H1–H10 are unchanged.**

*Source and exposure.* H10's first run reported the soft PMF as secondary (a): +0.0065 ± 0.0085
(1 SE) on 28 v1.18 games, against −0.0023 ± 0.0101 for H10's hard PMF. H11 was requested after
that was seen, so those 28 games are exposed. They are frozen in
`research/soft_band_ladder_inputs/exposed_games.txt` and **excluded from H11's primary sample**.

*Forecast (fixed).* SB1's soft neighboring-band PMFs: the same 2021–2025 fit as H10, linear
weights between adjacent band anchors (each band's prior-sample median |raw spread|), nearest
endpoint outside them (`soft_band_distributions.forecast(raw, fit, soft=True)`). No refit.

*Primary sample.* H10's primary definition (graded v1.18 forward rows with a Kalshi capture, the
ledger's capture join, rungs with strike ≤ 17.5 and a valid quote) minus the exposed games.

*Score.* H10's: binary log loss per rung, probabilities clipped to [0.005, 0.995], per-game mean
of Kalshi loss − soft loss, games weighted equally, SE across games.

*Decision* (first run with ≥ 100 primary games, then final):
- **Supported**: gain − 2 SE > 0. Only then is an alt-line chooser priced from the soft PMFs worth
  a separate pre-registration.
- **Falsified**: gain ≤ 0.
- Otherwise **unresolved**. Earlier runs are interim with no verdict.

*Secondary, never decisive.* (a) the 28 exposed games, reported as exposed; (b) soft − hard
paired on the primary games (per-game mean of hard loss − soft loss); (c) the near-line subset
(|strike − team line| ≤ 4); (d) the 2025–26 development cohort (H10 (e)) with soft PMFs.

*Power, stated now.* About 14 v1.18 games a week; n = 100 fresh games around 2026 week 15.

*Multiplicity.* H10 and H11 test two forecasts on largely the same future rungs, and H11 was
chosen after H10's interim reading. Read a single 2 SE result with H1–H11 in mind.

**2026-10-27 (later the same day), owner request ("set up H12 and run it on 2013–2018"),
committed and pushed before the 2013–2018 schedule is downloaded. New hypothesis H12 (fade the
band-capped team ATS residual). H1–H11 are unchanged.**

*Source and exposure.* An exploratory scan on 2006–12 and 2019–25 (exposed; done in chat on
2026-10-27, not committed) found that rolling team residuals (final margin − spread) are priced by
the market. Capped at the band's median number, they lean toward **fading** in cover terms:
about −0.04 to −0.05 cover units per SD of the signal (z ≈ −2 in 2006–12, −1.6 to −1.8 in
2019–25 at N = 4 and 8). The cell below was chosen from 24 correlated cells after that was seen.
2013–2018 spreads and results have been used by other repo tests (for example
`OUT_OF_SAMPLE_2017_2020.md` and the 2013–2020 feature packs), but never for team ATS residuals or
cover-by-history. This is an out-of-period check on exposed seasons, not forward evidence.

*Data (fixed).* nflverse `games.csv` (`research/ladder_pricing.py` GAMES_URL), downloaded once
after this commit, regular-season games 2013–2018 frozen with source and frozen SHA-256 in
`research/h12_inputs/`. Team histories are seeded with the 2012 regular season from the frozen
`research/ml_spread_inputs/games_2006_2012.csv` (history only, never scored). Franchise codes
continue across moves: STL → LA, SD → LAC (OAK stays OAK through 2018). Playoff games are excluded
from histories and scoring. Games without a spread or result are skipped.

*Signal (fixed).* For a game with spread s (positive = home favored) and home margin m, the home
residual is t = m − s, capped to ±c where c is the 2026 production median-map magnitude for |s|'s
band: 3 (|s| < 3), 4 (3–<7), 7 (7–<10), 14 (10+). The away team records −t with the same cap. A
team's signal is the mean of its last **8** capped residuals (across seasons; both teams need 8).
x = home signal − away signal.

*Rule (fixed).* Bet when |x| ≥ **2.51** points: the sample SD of x on 2019–25 with the same
definition (n = 1,739; about 31% of games pass). Take the **away** side if x > 0 and the **home**
side if x < 0, against the spread at assumed −110. Pushes return 0 and stay in the ROI denominator.

*Report.* W-L-P, cover rate excluding pushes with Wilson 95%, units, ROI ± SE, n, the 52.4%
break-even, the same-row always-favorite and always-home records, and per season. Secondary,
never decisive: the slope of the cover outcome (±1, pushes 0) on x / 2.51 over all scored games,
with SE; the same rule at N = 4 and 16.

*Decision* (one run, n ≥ 150 bets required):
- **Replicates**: cover rate > 52.4% **and** above the same-row always-favorite cover rate. Only
  then would a reporting-only forward shadow on the 60-minute locks be registered (as its own
  hypothesis), not adoption.
- **Falsified**: either condition fails. The idea is dropped.
- Fewer than 150 bets: inconclusive, dropped as untestable on this period.
A point-estimate gate: a replication is weak evidence; the cover-rate interval is reported with it.

*Multiplicity.* H1–H12 are now registered. H12 was selected from a scan of 24 correlated cells.
