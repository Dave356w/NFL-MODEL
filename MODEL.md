# The model and its pipeline

`nfl_model.py` is the single source of truth. Its module docstring is the
version history (v1 to v1.14), newest first; this page describes what the code
does **today** and how the repository runs it.

## The current model: `boxscore-composite-v1.14`

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
  roster before the game, or no longer on it. They measure **fresh** absences.
  Returns and arrivals do not offset them.
* QB (v1.11): from 2025 on, the highest-ranked available QB on the team's
  latest timestamped depth chart (nflverse/ESPN) published at least 24 hours
  before kickoff. Available means not Out/Doubtful and on the most recent
  roster before the game. A chart older than 7 days counts as missing. With no
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

**Composite.** A logistic regression on home-minus-away differences plus a
site term, ridge-penalized, refit before every week on all earlier games
(older games discounted with a two-season half-life).

**Selection and freezing.** 24 candidates: 2 feature families (unadjusted and
opponent-adjusted rates, both with availability and lead/deficit peaks) × 3 team
half-lives (4, 8, 16 games) × 4 ridge strengths. The minimum walk-forward log
loss over earlier seasons picks the recipe, which is frozen for the season in
`data/frozen_recipe_<season>_<REVISION>.json` (v1.9's record keeps its old name,
`data/frozen_recipe_2026.json`). A config change that would alter the
signature refuses to run against an existing frozen record; that is why
feature changes ship as a new `REVISION`.

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
close. Log loss still fits the coefficients and selects the recipe (owner's
decision 2026-10-06: ROI is reported, not optimized). It is shown as a
secondary score.

**Is the recipe chosen by ROI? No.** Selection is the lowest walk-forward log
loss over earlier seasons. `data/latest/candidate_roi.csv` lists all 24 candidates'
flat ROI on the same games beside their log loss, for comparison only. Under real data
(2021–25) the top log-loss group ranged −0.5% to +0.7% ROI, all with SE ≈
±2.2 pts, so ROI cannot separate them. Switching selection to ROI would need a
new `REVISION`.

### Model-implied spread (reporting only, v1.12.1)

`model_spread = 12.37 × Φ⁻¹(model_wp)`: the inverse of the market comparator, in
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
X.5 points" ladder, once, into `data/kalshi_snapshots.jsonl` (append-only, separate from the
forward ledger; `kalshi_lag_hours` records how long after the lock it was taken). A Kalshi
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
(research Test 24), so it is a forward hypothesis, not a model input.

### Realized margin on the calibration page (reporting only, v1.12.4)

`market-calibration.html` shows, per moneyline band, the side's average realized margin beside
its average market spread, and per model confidence band the model pick's average margin beside
the spread (`band_records`: `avg pick margin`, `avg pick spread`). Descriptive only.

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

The market comparator is `Φ(spread / 12.37)` from the nflverse schedule line.
That line has no independent quote timestamp.

## How a week's forecast updates as injury reports arrive

| When (Sunday game) | Injury data for the week | Model counts | Card shows | Ledger |
|---|---|---|---|---|
| Tue (daily 06:13 ET build) | none yet | everyone on the latest roster as available (IR/departures already out) | last week's Out/Doubtful/Questionable players: "not on a week-N report yet", 0% counted; "Report pending" | waits |
| Wed–Thu | practice participation only | still available | each listed player's practice status (DNP/Limited) | waits |
| Fri ~4pm ET | final report: game statuses | Out/Doubtful 100%, Questionable 25% of the player's unit-snap share | the statuses as counted; last week's players absent from the report: "cleared" | locks at the first build after nflverse publishes it: the daily pass, or hourly builds from 30h before kickoff |
| ≤150 min before kickoff | final | final | final | already locked; board refreshes once more |

Thursday games run the same schedule two days earlier (final report Wednesday). Monday
games run one day later (Saturday). A team with no designations at all still locks within 6h of kickoff (nflverse rebuilds injuries once a day, so a Thursday game waits for Thursday's file).
The gate also needs nflverse to have published the report. Its injury file refreshes at
least daily, and every build re-reads it. Same-week roster moves (for example a Friday IR
move) are not used; the report's Out status covers them.

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
