# The model and its pipeline

`nfl_model.py` is the single source of truth. Its module docstring is the
version history (v1 to v1.18), newest first; this page describes what the code
does **today** and how the repository runs it.

## The current model: `boxscore-composite-v1.18`

**v1.16 with the favorite-confidence penalty (owner decision 2026-10-13).** New `REVISION`,
`OUTPUT_NAME` (`nfl_boxscore_output_v1_18`) and config signature. Same features, fit and
coefficients as v1.16 below. The recipe carries `favorite_penalty: 0.2`, and `apply_fit` applies it
after the market offset: where v1.16 backs the market favorite more strongly than the no-vig q, the
forecast keeps 0.2 of its log-odds departure from q; elsewhere it is v1.16's. The result lies between
q and v1.16 on the same side of 50%, so **every pick and flat bet is v1.16's**; only probabilities on
favorite-bullish games change. The board's model range applies the same map to its bounds.

**v1.16 shadow lock.** Each build also locks the unpenalized v1.16 forecast for the same games,
under v1.16's own frozen recipe and signature (`9dad9b9a…`), with the same injury-report gate and
first-snapshot rule. This keeps the pre-registered H1/H2/H6 sample (first v1.16 snapshots from 2026
week 6) and the penalty's forward verdict (`research/FAVORITE_PENALTY.md`: 200 graded native games)
running as registered. Shadow rows are graded in `ledger_report.txt` only.

**Public site.** The pages show the production revision only. Earlier revisions, the shadow lock,
the competing-model comparison and snapshot replays are in `ledger_report.txt`; the published copy
appends `version_report.md` and `regraded_ledger_report.md`.

Evidence for the penalty (log-loss gain vs v1.16; picks identical): +0.0040 ± 0.0027 on 2017–20 out
of sample and +0.0023 ± 0.0017 on 2021–25 (both exposed; λ chosen on 2021–25), +0.026 ± 0.025 on
2026 weeks 1–5 and +0.147 on 13 native games. It still trails the market. No profit claim follows:
ROI is identical to v1.16 by construction.

## v1.16: the shared base model

**Production restored (2026-10-12).** Owner-directed return to the exact original
market-offset **Product + 1 SD** recipe: raw main h8, passing h16, fixed no-vig
moneyline logit coefficient 1, and main/context ridge 0.1. Weekly fits use only
earlier games. The original configuration hash and frozen recipe resume; no
new hyperparameters, confidence caps, target forecasts or outcome-driven tuning
are introduced. v1.17 remains an independently reproducible research/archive
specification in `PASS_TOTAL_RECIPE` and `research/adopt_pass_total.py`.

Every original snapshot is preserved. The build refreshes all historical and
current-season projection tables with v1.16 and separately replays every saved
snapshot at its original moneylines. Retrospective summaries use each game's
earliest snapshot; original-revision groups overlap and must not be pooled.
Pending games remain pending, ties push in returns and are excluded from binary
scores. Native reports continue to grade each original version unchanged.

The grades page also reports every committed competing-model arm, separating
historical development, frozen archived-input counterfactuals and native locks.
`research/version_report.py` regenerates these comparisons each build without
fitting or selecting another model. Full scores, uncertainty and sources are
published as CSVs and `version_report.md`. The frozen restoration check is
`python research/restore_v116.py`; its inputs/results live under the matching
research directories. No restored model is claimed reliably profitable.

### Archived v1.17 adoption: `boxscore-composite-v1.17`

**Production adoption (2026-10-10).** Owner-selected **Passing × predicted total** after exposed historical comparisons, with a new revision/output folder. This is the exact `pass_total` candidate from `research/market_residual_models.py`, not a new blend or a refit on retrospective ROI. Win coefficients still fit penalized log loss. The production formula retains all v1.16 main and signed passing terms and adds:

* `(predicted margin − market spread)/10`;
* `site × (predicted total − 45)/10`;
* `pass_product × (predicted total − 45)/10`.

Margin/total means use fixed ridge 0.1 on market prices and strictly earlier actual outcomes. Their rules are selected once per season by strictly earlier-season weekly OOF integer-bin NLL among market relationships and four shrunk residual rules (half-life 4/16, pseudo-games 4/12, .5 offseason retention, three prior seasons). The tested winner includes this selection mechanism: totals used a residual rule in 2023–24; 2026 selects market relationships alone for both targets. Forecast dispersion uses earlier weekly errors, with an earlier-market-error warm-up. Box profiles enter only the win stack, trained on ready priced binary OOF rows from 2020 onward. Missing target prices or OOF inputs yield no prediction.

On the same 812 historical comparison bets, it returned +46.32u, 5.70% ±2.54 pp SE versus v1.16 +29.06u, 3.58% ±2.52 pp. The adjusted ROI-gain interval [-.27,+4.89] includes a decline. Win LL .606426 beats market .608072 but trails v1.16 .605605. The owner prioritizes the stronger historical return candidate; reliability remains unresolved. Exposed history, Gaussian approximations and unknown schedule quote capture times remain limitations. New native snapshots save target prices, means, selection, fits and cutoff metadata. Original forward snapshots are unchanged; all historical tables, prior current-season projection files and separate snapshot replays regenerate with the new revision.

**Target.** Binary home win. Ties are excluded from fitting and scoring, but
their box scores still feed later profiles.

**Profiles.** For each team and week, using only games completed in earlier
weeks, play-by-play is aggregated into team box scores (sacks counted once,
net passing includes sack yards, accepted-penalty proxy, deduplicated
possession time). Eight core rates per side: plays/game, net yards per
dropback, rush yards/attempt, first-down rate, fumbles lost/game, interception
%, sack %, penalty yards/game. v1.14 uses seven of these rates per side in the
regression, excluding the separate sack percentage. Profiles are ratios of decayed counts
(`2^(-age/half-life)`, halved again at each season boundary) shrunk toward four
league-average pseudo-games. The `_adj` family splits each stat into league
mean plus offense and defense effects with a weighted ridge fit, so a defense
is not credited for weak opponents.

**Availability (`*_avail_cs` families).** All of this uses information
published before kickoff:

* Unit columns (OL, WR/TE, RB, DL, LB, DB): the share of the unit's snaps over
  the team's last 4 games (this season only, once 2 exist) belonging to players
  listed Out/Doubtful (Questionable counts a quarter), moved off the most recent
  roster before the game, or no longer on it, or (v1.15) on the reserve list of the
  game week's own roster. They measure **fresh** absences.
  Returns and arrivals do not offset them.
* QB (v1.11): from 2025 on, the highest-ranked available QB on the team's
  latest timestamped depth chart (nflverse/ESPN) published at least 24 hours
  before kickoff. Available means not Out/Doubtful, on the most recent
  roster before the game and (v1.15) not on the game week's reserve list. A chart older than 7 days counts as missing. With no
  usable chart (and in every season before 2025, whose depth charts carry no
  publish time): the available rostered QB who started the team's most recent
  game (week 1: most starts last season), else the most team dropbacks, else a
  rostered QB with history elsewhere, else a league backup prior. A projected
  starter listed **Questionable** is a 50/50 blend with the next candidate
  (incumbents listed Questionable started 56% of the time, 2019–2026). The
  feature is the projected efficiency (shrunk net yards per dropback, all-team
  history) minus the team's recent dropback mix. `qb_source` in
  `availability_features.csv` says which rule applied.
* Roster codes counted as out: RES, CUT, TRD, RET, EXE, E01, and the codes used
  mainly in 2019–23 rosters (SUS, PUP, RSN, NWT, UFA, RFA, RSR, E14, TRT, TRC),
  plus any reserve/waived status description. Unrecognized codes are audited.
  They are read from the most recent roster before the game and, from week 2, from the
  game week's own roster (v1.15).

**The game week's own reserve list (v1.15, based on v1.14; owner decision 2026-10-09).**
From week 2, a player whose row on the game week's weekly roster carries one of the
roster-out codes above (IR, PUP, NFI, suspension, cut, traded, reserve/waived
descriptions) counts fully out, in the unit columns and for QB eligibility. Before v1.15
only the roster before the game week was read. A regular hurt on Sunday and placed on IR
by Tuesday was then on neither that roster nor the injury report, which never lists
reserve players, so he counted as available. Research Test 28 found 1,849 such regulars in
2019–25, 99.7% of whom did not play. In 2022–25 weeks 5+ they add 13.1% to the absence mass
already counted, and the closing moneyline prices them at +0.66 ± 0.17 of the model's unit
weight (+0.55 for the absences already counted). Only the reserve list is read from the game
week. Membership, activations and absence from that roster keep the prior-week rule, and
game-day inactives stay members; nothing on the game-week roster clears an out. Card notes
list these players ("… on wk N roster"), counted 100%.

*Timing.* Weekly roster rows have no publish time. Of the players newly on a game-week out
list in 2019–25, 10 of 6,086 (0.16%, 9 of them in 2020–21) took an offensive or defensive snap
in that game, so the file is pregame. The
2026 week-5 rows were already published on the Friday. Forward snapshots read the file as
it stands at lock. Historical rows use the final weekly file, which can include a move
made between the final injury report and kickoff. A team with no game-week rows yet falls
back to the prior-week rule. `GAME_WEEK_RESERVE = False` reproduces v1.14. The output
folder is `nfl_boxscore_output_v1_15`; v1.14 and earlier recipes and snapshots remain
intact.

Held-out development comparison (research Test 29, run after adoption, not a gate; 2023–25, 811
priced games, the same recipe in every season): log loss +0.0001 ± 0.0010, flat 1u ROI +2.0% ±
2.7 against +3.2% ± 2.7 for v1.14 (paired −1.2 pts ± 0.9), same-row favorite +0.0%,
market-correct null −4.1%; 15 of 815 picked sides change. The effect is unresolved: the rule
fixes a measured input error, but the held-out seasons cannot show whether that moves results.

**Dated personnel events (v1.12, based on v1.11).** The hand-curated
`data/personnel_events.csv` identifies the losing team and roster-resolved GSIS
ID. Retired, traded, waived, released and suspended players count fully out
only when `event_date < gameday` for that team's scheduled game. Same-day and
later events do not apply. Signed/activated rows are audit-only and never
cancel an out. This is a narrow exception to the prior-week roster rule using
knowable transaction dates; all other roster timing stays unchanged. Unit
shares and QB selection consume the same out map. Card notes show the event
label and date. Events and schedule dates are hashed in availability caches.
A missing file is an audited no-op with a printed warning (Colab: copy `data/personnel_events.csv` into the Drive output folder); bad rows fail validation; duplicate
(id, date, event) rows are audited and dropped. The 2026-only seed changes no
historical availability; source-noted historical backfill is optional later
work. No replacement weighting or receiving-team contribution is introduced.
The output folder is `nfl_boxscore_output_v1_12`; earlier frozen recipes
and forward-ledger rows are preserved. With no historical events, held-out seasons
match v1.11 (research test 21).

**Largest lead and deficit (v1.13).** Final MOV is replaced by two inputs:
each team's decayed average largest lead and largest deficit from its earlier
games. The full-game score peaks come from actual nflverse scoring events (`sp=1`),
including overtime, extra points and two-point conversions; deleted plays and
stale non-scoring administrative rows are excluded. Quarter/clock ordering,
monotonic score checks and agreement with official final scores protect the source.
A team that never led has largest lead zero; a team that never trailed has largest
deficit zero. Each uses the same team-game decay, offseason retention and history
window as the profiles, with four zero pseudo-games. The regression receives the
home-minus-away difference of each profile. Neither peak is clipped or
opponent-adjusted. Time spent leading is not included.

This is an owner-selected new experiment following a development comparison on
2023–2025: replacing MOV with both peaks scored log loss 0.63240 versus 0.63248
for MOV (gain 0.000080, paired 95% interval -0.001767 to +0.001872). Flat 1u ROI
was +2.02% versus +1.06% on 811 same-row directional bets; the ROI difference
was unresolved. These figures do not establish superiority. The comparison
selected each year's recipe on earlier seasons and refit coefficients weekly,
but the feature design followed prior historical research. Future v1.13 snapshots
start a distinct experiment; earlier recipes and forward rows are preserved.
Legacy margin families remain available for historical research, but `d__margin`
is absent from both production candidate families.

PBP-derived box caches are revision-specific and are rebuilt for each new revision. A custom
`TEAM_GAME_CSV` must supply finite nonnegative `max_lead` and `max_deficit` for both
teams in every prior game, with each team's lead equal to its opponent's deficit.
Missing peaks are an error, rather than a silent zero or inference from final MOV.

**Separate sack-rate removal (v1.14).** Both active raw/adjusted candidate
families omit offensive and defensive `sacks_taken_pct` regressors. Net passing
yards per dropback retains sack yards and sack plays; source sack counts and
legacy family definitions are retained. First-down rates, lead/deficit peaks,
availability, fitting and the 24-candidate grid keep their existing definitions.
The active families are `rates_core_avail_cs_peaks_nosacks` and
`rates_core_adj_avail_cs_peaks_nosacks`, with 24 fitted terms each rather than 26.

The owner chose this simplification after exploratory 2023–2025 ablation.
Under the current raw h8/r0.1 settings, removing both sack rates scored log loss
0.629536 versus 0.630226; flat 1u ROI was +0.77% versus +0.19% on 811 same-row
games. The paired unadjusted week-bootstrap ROI-difference interval was
−1.90 to +3.26 percentage points. Chronological recipe selection also slightly
improved pooled scores, but improvement was not uniform by season and neither
gain nor variance reduction was established. This is development evidence,
not forward confirmation or a formal equivalence result. The new output folder
is `nfl_boxscore_output_v1_14`; v1.13 and earlier recipes/snapshots remain intact.

**Restored production composite (v1.16).** The owner-fixed Product + 1 SD recipe uses raw main
profiles at h8 and raw pass profiles at h16. Start from the two-moneyline
no-vig home probability q. The forecast is
`sigmoid(logit(q) + main_features @ beta + pass_contexts @ gamma)`.
The market logit coefficient is fixed at 1. Main and context penalties are
both 0.1, with the site penalty multiplied by 0.1. Coefficients refit each week
using earlier weeks only and two-season fit decay. Train only on priced,
ready binary outcomes with valid pass contexts. Missing moneylines or contexts
produce no forecast and cannot enter the native ledger.

Pass offense and opposing defense allowed are centered on earlier current-season
weeks (previous season at week 1), with SD from prior weeks of the trailing four
seasons; both home and away orientations are pooled for each role. The shared
interaction is `z(home offense)*z(away defense) - z(away offense)*z(home defense)`.
Four additional signed products use `max(sign*z-1,0)` on both offense and defense,
differenced home minus away. All historical rows retain their original pregame
normalization; later reference values never rewrite them.

**Freezing.** The formula, h8/h16 and both 0.1 penalties are owner-fixed after
exposed historical development. They are not annually reselected. The old
24-candidate additive grid remains available for legacy research and tests;
the production run fits one recipe. A new revision and frozen recipe file keep
all earlier experiments intact. The market contribution appears in the score
explanation; raw input values and the exact market q are saved in new snapshots.

**Adoption basis.** The fixed 1 SD extension returned +30.06u / +3.71% ROI
on the context battle's 811 common 2023–2025 bets, vs fixed product +2.51% and
old production +1.90%. Paired ROI uncertainty crosses zero; all still lost
money in 2025. These are development results, not demonstrated reliable profit.
See `research/context_results/DECISION.md`.

**Retrospective snapshot grading.** `regraded_ledger.csv` replays every ledger
snapshot at its original moneylines with reconstructed pregame features and
strictly prior-week fitted coefficients. It retains original probabilities,
revision and timestamp beside the new forecast. Repeated snapshots of one game
are not independent games. The native JSONL is never replaced or backfilled.

## The goal: flat 1u ROI at the moneyline

The model is judged by flat-stake betting results. Every game it decides
(model probability ≠ 50%) gets 1u on the side it makes the favorite, graded at
that side's posted American moneyline. A win pays the price, a loss costs 1u,
and a tie is a push. Each ROI is reported with:

* W-L-P, units, ROI ± one standard error;
* the no-vig market probability q of the picked side, and the win rate's excess over q;
* the **market-correct null** `q × payout − (1 − q)`: the ROI expected if the
  market were exactly right. It is negative by the hold, so it is the bar to
  beat, not zero;
* the same-row baseline of betting the market favorite (pick'ems excluded from both);
* the picked side's price band (≤ −250 … ≥ +250, the MLB site's bands). The
  bands are descriptive, not a betting filter.

Prices: historical seasons use the nflverse schedule moneyline. A ledger
snapshot saves the moneyline it saw at lock time, which is not necessarily the
close. Log loss still fits the coefficients (archived v1.17 also selects market target rules by prior-season NLL) (owner's
decision 2026-10-06: ROI is reported, not optimized). It is shown as a
secondary score.

**Is the recipe chosen by ROI?** The owner restored v1.16 on 2026-10-12 after
reviewing returns, probability scores and complexity. Its original formula is
fixed; coefficients still fit penalized log loss. The earlier v1.17 adoption
followed exposed historical ROI comparisons and is retained as archived research.
Neither decision establishes native forward superiority.

### Where the model's bets differ from the favorite's (reporting only, v1.14.2)

Wherever the model's favorite is also the market favorite, the model's flat bet is the same as
always betting the favorite. On held-out 2023–25 that was 694 of 811 games (86%), so the
headline ROI mostly reflects how favorites fared. Only the games where the model picks the
market underdog separate it from the favorite baseline; they carry the whole difference in
units. `disagreement_table` reports them: `data/latest/disagree_roi_by_season.csv` (held-out),
a line in `data/ledger_report.txt` per revision, and a note on the ledger page for locked picks
and the rebuilt history. Held-out 2023–25: 117 games, model +9.4u (+8.1% ± 10.4) against
−16.4u for the favorite, unresolved (−4.8% / +23.0% / +4.4% by season).

The model's probabilities are not used as prices. On the same held-out games, betting whichever
side the model calls positive expected value at the moneyline returned −9.6% ± 5.2 on 661 bets,
below the −4.1% null: the model is less sharp than the market (log-odds SD 0.73 against 0.85) and
adds nothing beyond it in the market-blend fit, so it rates most underdogs as value.

### Pre-registered H5: low-total underdogs (reporting only, v1.14.2)

`totals.py` records each newly locked game's total and moneylines in `data/h5_totals.jsonl`;
`data/ledger_report.txt` grades 1u on the moneyline underdog whenever the total is ≤ 41, beside
the market-correct null and the favorite on the same rows, with the verdict fixed in
`research/PREREGISTRATION.md`. Independent of the model; nothing here changes the model, the
recipe or the headline.

### Model-implied spread (reporting only, v1.12.1)

`model_spread = 12.37 × Φ⁻¹(model_wp)`: the inverse of the fixed spread-to-probability map
`Φ(spread / 12.37)` (`MARKET_SIGMA`, the market comparator before v1.16), in
points with the schedule's `spread_line` sign (positive = home favored). It appears in
`data/latest/board.csv`, `retro_ledger.csv` and `data/forward_ledger.csv`; it is
derived from `model_wp`, never stored in the forward JSONL, and does not change the
config signature. On held-out 2023–25 (n=815) it misses the realized margin by
13.10 points RMSE against 12.66 for the market spread; a linear recalibration fit on
earlier held-out seasons did not help.

`forward_ledger.csv` also carries `spread_gap` (`model_spread − spread_line`), the
side that gap takes against the snapshot spread (`ats_side`) and its W/L/P
(`ats_result`). The ledger report shows this as a **diagnostic, not the goal metric**,
for all games and for |gap| ≥ 3 points, against the 52.4% break-even at −110. The
3-point cut was chosen after the held-out seasons were seen (held-out: 136-118, 53.5%
± 3.1), so only forward games can test it.

### Kalshi: a second, timestamped market (reporting only, v1.12.2)

The sportsbook moneyline in a ledger snapshot comes from the nflverse schedule and has no
independent quote time. For every game newly locked, the build now also captures Kalshi's
public order book (best bid and ask) for both game-winner markets and the "team wins by over
X.5 points" ladder into `data/kalshi_snapshots.jsonl` (append-only, separate from the
forward ledger). A game is captured again when a later revision locks it after its last
capture, and each snapshot is graded at its first capture at or after its lock;
`kalshi_lag_hours` records how long after the lock that was. Snapshots locked before
this rule (v1.13/v1.14 for 2026_05_TB_DAL) have only an earlier capture: their lag is
negative and the report counts them as captured before lock. A Kalshi
failure is logged and skipped; it never costs a pregame snapshot.

`data/ledger_report.txt` then adds, as **secondary** lines (the moneyline headline is unchanged):

* the model's side at the Kalshi ask, including an estimated taker fee of 0.07 × P × (1 − P)
  per contract, beside the Kalshi favorite on the same rows, and the **Kalshi-correct null**
  (about −1% to −2%: half the 1¢ spread plus the fee, against about −4% at the sportsbook);
* a **diagnostic** for the alt-line rule: when the model and the market spread make the same
  team the favorite and the model's spread is smaller, buy "favorite wins by over X.5" at the
  largest Kalshi strike below the model's spread (the game-winner market when none is below
  it), beside the favorite's game-winner ask on the same rows. The rule was chosen after
  seeing held-out data; only these forward rows test it.

* **pre-registered H3** (`research/PREREGISTRATION.md`): price every rung (strike ≤ 17.5)
  from the frozen 2006–2024 margin distribution at the snapshot's no-vig moneyline
  (`data/kalshi_ladder_reference.csv`, built by `research/ladder_pricing.py --build`) and buy
  the one rung per game whose expected profit after the fee is at least $0.03, beside the
  Kalshi-mid null on the same bets. Independent of the model.

Is Kalshi a good benchmark? `research/kalshi_calibration.py` (2025 held-out games with a
Kalshi price 1 hour before kickoff, n = 271): Kalshi log loss 0.6117 against 0.6094 for the
margin-free sportsbook moneyline (difference −0.0023, 95% −0.0054 to +0.0008, unresolved) and
0.6335 for the model; calibration slope 0.94 ± 0.16. Kalshi agrees with the book to about one
point of win probability, so it is a cheaper, timestamped price, not a better forecast.

### Pre-registered H4: the pass matchup (reporting only, v1.12.3)

`matchup.py` records, for each newly locked game, home pass offense × away pass defense
allowed minus the reverse (net pass yards per pass play, half-life 16 profiles, centred on the
season so far) in `data/h4_terms.jsonl`. `data/ledger_report.txt` reports its partial
correlation with the final margin beyond the market spread, with the pre-registered verdict
(`research/PREREGISTRATION.md`). Held out it was +0.09 in 2023–25 and −0.02 in 2019–22
(research Test 24), so it remains a separate forward hypothesis. Its recorded term and normalization are distinct from the v1.16 production pass contexts.

### Realized margin on the calibration page (reporting only, v1.12.4)

`market-calibration.html` shows, per moneyline band, the side's average realized margin beside
its average market spread, and per model confidence band the model pick's average margin beside
the spread (`band_records`: `avg pick margin`, `avg pick spread`). Descriptive only.

### Closing-line value (reporting only)

`grade_ledger.py` also reads nflverse's moneylines once a game is final and treats
them as its closing line; the schedule has no quote timestamp, so "close" means the
last price nflverse recorded. `forward_ledger.csv` adds `close_home_moneyline`,
`close_away_moneyline`, `close_q` (no-vig) and `clv_pp`: how far the no-vig
probability of the model's side moved from the snapshot's lock price to the close, in
percentage points (positive = toward the model). Pending games have no close.
`data/ledger_report.txt` shows, per revision, the mean ± SE, the mean on the model's
underdog picks, and the slope of the logit line move on the model's logit departure
from the lock price (positive = the market moved toward the model). Price moves are
far less noisy than game results, so this answers sooner whether the model's
departures anticipate the market. It is a diagnostic, not profit and not the goal
metric.

### Pre-registered H1, H2 and H6 grading (reporting only)

`data/ledger_report.txt` grades H1 (|model − q| > 0.17) and H2 (late-season log-loss
fade, with ROI per week group as secondary) exactly as `research/PREREGISTRATION.md`
fixes them. The owner's addendum of 2026-10-13, committed before any week-6 snapshot,
applies them to the first v1.16 snapshot of each game under its frozen configuration,
for games from 2026 week 6 on (cumulative across seasons), with q from the snapshot
moneylines. The 14 week-5 v1.16 rows predate it and are excluded. The earlier samples
(through v1.12) ended under the stopping rule; a change of revision, configuration
signature or recipe ends this one too. Because v1.16 starts from the market's log-odds,
only about 1% of its games move more than 0.17 from q (10 of 816 in 2023–25), so H1
will read unresolved for many seasons; H2 is likely unresolved after 2026.

H6 (a second owner addendum the same day) grades, on the same sample, the bets where
v1.16 backs the market underdog. Those are the only games where its flat bets differ
from betting the favorite. In 2017–20 its 49 such picks returned +19.3% ± 15.2 against
a −2.4% null (2023–25, exposed: 42 picks, +34.2% ± 17.0); the slice was proposed after
both were seen. At 11–16 picks a season it needs several seasons: no verdict before 10
bets, falsified at n ≥ 50 with ROI at or below the null.

### Favorite-confidence penalty (v1.16.2 reporting; production from v1.18)

v1.18 makes this the production forecast (see the top of this page); `retro_ledger.csv` no longer
carries `model_wp_fp`, because its `model_wp` is already penalized. As first added in v1.16.2:
where v1.16 backs the market favorite more strongly than the no-vig price q, `model_wp_fp` keeps
`FAVORITE_PENALTY` (0.2) of its log-odds departure from q; everywhere else it equals `model_wp`.
It always lies between q and the model on the same side of 50%, so **no pick and no bet changes**.
v1.16's forecasts, snapshots, recipe, `REVISION` and `config_signature()` are unchanged: the column
is added to `retro_ledger.csv`, and `grade_ledger.py` writes `fp_wp`/`fp_log_loss` to
`forward_ledger.csv` and a v1.16 line to `ledger_report.txt`. Protocol and verdict rules:
`research/FAVORITE_PENALTY.md`; results: `research/favorite_penalty_results/`.

| Basis | n | LL v1.16 | LL penalized | LL market | Gain vs v1.16 (week-cluster SE) |
|---|---:|---:|---:|---:|---:|
| 2017–20 out of sample (exposed) | 1,019 | 0.6056 | 0.6016 | 0.6004 | +0.0040 ± 0.0027 |
| 2021–25 rebuilt (exposed; λ chosen here) | 1,355 | 0.6143 | 0.6120 | 0.6109 | +0.0023 ± 0.0017 |
| 2026 weeks 1–5 walk-forward (unseen) | 78 | 0.6983 | 0.6720 | 0.6508 | +0.0263 ± 0.0254 |
| native v1.16 ledger (unseen, one week) | 13 | 0.7659 | 0.6194 | 0.5714 | +0.1465 |

The penalty improves v1.16's probabilities on every basis but still trails the market. The
exposed rows confirm the implementation, not the idea. The forward verdict waits for 200 graded
native v1.16 games: falsified if the penalized log loss is not lower than v1.16's. Making it the
live forecast would be a new `REVISION`.

### Model range on the board (reporting only)

Board rows carry `offset_se`, `model_wp_lo` and `model_wp_hi`, and the card shows
**Model range**: a 90% range for the model's probability from the uncertainty in its
fitted weights alone (`offset_band`: the penalized fit's curvature at the weekly fit,
scaled by the decay weights' effective size). On 2023–25 the range averages 18 points
wide (probability SD 5.7 points, against 4.1 for the Monte Carlo week-cluster
coefficient bootstrap). It leaves out uncertainty in the team profiles, which the
Monte Carlo research put at about the same size again (feature bootstrap 4.6; both
together 7.1), so the real range is wider. It is never written to snapshots, does
not enter the config signature, and is blank when the fit's training rows cannot be
rebuilt exactly.

## Bases of evidence: never pooled

1. **Forward ledger** (`data/forward_predictions.jsonl`): the first snapshot of
   each game written before kickoff, and only once both teams' injury reports
   carry game statuses (or practice-only teams within 6h). These are native
   forward observations. Snapshots are append-only; the experiment identity is
   `config signature : recipe : season`.
2. **Held-out seasons** (Model and Calibration pages): walk-forward predictions
   for seasons whose recipe came only from earlier seasons. They are
   reconstructions, and the design was revised after seeing them, so they are
   development evidence, not forward confirmation.
3. **This season so far**: weekly walk-forward reconstructions of games already
   played. They use current upstream data, not the data available at the time.
4. **Rebuilt history of the chosen recipe** (Ledger page, below the forward
   record): the frozen recipe's weekly walk-forward predictions for every game
   since 2021 plus this season's earlier weeks, graded as flat 1u moneyline
   bets game by game (`data/latest/retro_ledger.csv`). This is the MLB site's
   "rebuilt" history. The recipe was chosen on those seasons, so it is
   hindsight, not a track record.

From v1.16 the market comparator is the model's own market input: the no-vig
probability q from the snapshot's moneylines (`market_wp` equals `market_no_vig_wp`).
The v1.12–v1.14 ledger rows stored `Φ(spread / 12.37)` from the schedule's spread
line instead. Neither nflverse quote has an independent timestamp.

**2017–2020 out of sample** (`research/out_of_sample_results/REPORT.md`): a one-time
reconstruction of the repository's least-used seasons (not untouched: an earlier
test scored them once and 2019–20 were warm-up training seasons; the protocol lists
the exposure). 2013–2016 are the only training history, and the protocol was pushed
before any forecast existed. It is held-out evidence of the second kind, not forward
evidence. v1.16 beat the same-row favorite by +18.76u on
1,017 bets (+1.84 pts per bet, 97.5% interval −0.81 to +4.61): unresolved. Its log
loss trailed the market's (−0.0052, interval −0.0144 to +0.0034). The close-game
challenger did not beat v1.16 (−22.64u; not supported).

**Selection-adjusted benchmark** (`research/selection_benchmark_results/REPORT.md`):
the 2023–2025 numbers above are the best of many tried configurations. Across the 53
distinct committed arms, if the market were exactly right the best arm would beat
the same-row favorite by a median +16.7u on 809 games by luck alone (95th percentile
+44.7u). v1.16's +30.6u has p 0.180 against that best-arm null (0.007 unadjusted);
v1.17's +46.1u is the best arm (p 0.042; Reality Check p 0.037). Only committed arms
are included and forecasts are held fixed, so these p-values are optimistic. The
version report repeats this section each build from the committed results.

## How a week's forecast updates as injury reports arrive

| When (Sunday game) | Injury data for the week | Model counts | Card shows | Ledger |
|---|---|---|---|---|
| Tue (daily 06:13 ET build) | none yet | everyone on the latest roster as available (IR/departures already out, plus game-week reserve moves once that week's roster is published) | last week's Out/Doubtful/Questionable players: "not on a week-N report yet", 0% counted; "Report pending" | waits |
| Wed–Thu | practice participation only | still available | each listed player's practice status (DNP/Limited) | waits |
| Fri ~4pm ET | final report: game statuses | Out/Doubtful 100%, Questionable 25% of the player's unit-snap share | the statuses as counted; last week's players absent from the report: "cleared" | locks at the first build after nflverse publishes it: the daily pass, or hourly builds from 30h before kickoff |
| ≤150 min before kickoff | final | final | final | already locked; board refreshes once more |

Thursday games run the same schedule two days earlier (final report Wednesday). Monday
games run one day later (Saturday). A team with no designations at all still locks within 6h of kickoff (nflverse rebuilds injuries once a day, so a Thursday game waits for Thursday's file).
The gate also needs nflverse to have published the report. Its injury file refreshes at
least daily, and every build re-reads it. From v1.15 the game week's own reserve list counts
too, so a regular moved to IR before the report (hurt on Sunday, on IR by Tuesday) is out even
though the report never lists him (1,849 regular player-games in 2019–25, 99.7% of whom did not
play; research Test 28). Other same-week roster changes (activations, signings, game-day
inactives) are still not used.

Two changes to these weights were replayed against v1.16 on 2017–20 and 2023–25 with a
protocol committed first (`research/availability_weights_results/REPORT.md`). Weighting a
Questionable player by his final practice (Test 28's 0.06 full, 0.26 limited, 0.55 none) is
unresolved: log loss improved slightly on both bases (pooled +0.0003, 97.5% interval −0.0003
to +0.0009), and its 12 changed picks lost 11.4u. Separate WR/TE and CB/S units are falsified
(pooled log-loss gain −0.00003; −23.6u). Production keeps Questionable at 25% and the six units.

## Pipeline

```
schedule_gate.py ──► build_site.py
                       ├─ nfl_model.main()      → runs/<run>/ (transient), appends data/forward_predictions.jsonl,
                       │                          writes data/frozen_recipe_<season>_<REVISION>.json, caches in .nfl_cache/
                       ├─ snapshot()            → data/latest/ (page inputs), data/projections/<season>_weekNN.csv
                       ├─ grade_ledger.main()   → data/forward_ledger.csv, data/ledger_report.txt
                       └─ render_all()          → public/ (index, grades, market-calibration, model, board)
validate_data_files.py ─► commit_data.py (signed commit of data/) ─► Pages deploy
```

Cold run (no caches): about 8 minutes. Warm runs reuse completed seasons'
play-by-play (weekly refresh), availability features and the historical
walk-forward grid.
