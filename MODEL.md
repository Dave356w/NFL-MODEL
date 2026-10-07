# The model and its pipeline

`nfl_model.py` is the single source of truth. Its module docstring is the
version history (v1 to v1.11), newest first; this page describes what the code
does **today** and how the repository runs it.

## The current model: `boxscore-composite-v1.11`

**Target.** Binary home win. Ties are excluded from fitting and scoring, but
their box scores still feed later profiles.

**Profiles.** For each team and week, using only games completed in earlier
weeks, play-by-play is aggregated into team box scores (sacks counted once,
net passing includes sack yards, accepted-penalty proxy, deduplicated
possession time). Eight core rates per side: plays/game, net yards per
dropback, rush yards/attempt, first-down rate, fumbles lost/game, interception
%, sack %, penalty yards/game. Profiles are ratios of decayed counts
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
* QB: the available rostered QB who started the team's most recent game (week
  1: most starts last season), else the most team dropbacks, else a rostered QB
  with history elsewhere, else a league backup prior. The feature is his shrunk
  net yards per dropback (all-team history) minus the team's recent dropback
  mix.
* Roster codes counted as out: RES, CUT, TRD, RET, EXE, E01, and the codes used
  mainly in 2019–23 rosters (SUS, PUP, RSN, NWT, UFA, RFA, RSR, E14, TRT, TRC),
  plus any reserve/waived status description. Unrecognized codes are audited.

**Dated personnel events (v1.11, based on v1.10).** The hand-curated
`data/personnel_events.csv` identifies the losing team and roster-resolved GSIS
ID. Retired, traded, waived, released and suspended players count fully out
only when `event_date < gameday` for that team's scheduled game. Same-day and
later events do not apply. Signed/activated rows are audit-only and never
cancel an out. This is a narrow exception to the prior-week roster rule using
knowable transaction dates; all other roster timing stays unchanged. Unit
shares and QB selection consume the same out map. Card notes show the event
label and date. Events and schedule dates are hashed in availability caches.
Missing files are audited no-ops; bad rows fail validation; duplicate
(id, date, event) rows are audited and dropped. The 2026-only seed changes no
historical availability; source-noted historical backfill is optional later
work. No replacement weighting or receiving-team contribution is introduced.
The new output folder is `nfl_boxscore_output_v1_11`; earlier frozen recipes
and forward-ledger rows are preserved.

**Point margin (v1.10).** Each team's decayed average point margin per game,
from the official result of every earlier game in its history. It uses the same
weighting as the profiles and is shrunk toward zero with four pseudo-games. Box-score
rates leave out red-zone finishing, special teams, return and defensive TDs and
kicking; margin carries them. The input is the home-minus-away difference. On the
2023–25 held-out seasons it improved log loss by 0.0028 ± 0.0010 per game over v1.9.
The ROI change was +0.6 ± 0.9 pts, which is unresolved (research test 16; the input
was found on those seasons, so the estimate is optimistic).

**Composite.** A logistic regression on home-minus-away differences plus a
site term, ridge-penalized, refit before every week on all earlier games
(older games discounted with a two-season half-life).

**Selection and freezing.** 24 candidates: 2 feature families (unadjusted and
opponent-adjusted rates, both with availability and point margin) × 3 team
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

## Bases of evidence: never pooled

1. **Forward ledger** (`data/forward_predictions.jsonl`): the first snapshot of
   each game written before kickoff, and only once both teams' injury reports
   carry game statuses (or practice-only teams within 24h). These are native
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
games run one day later (Saturday). A team with no designations at all still locks within 24h of kickoff.
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
