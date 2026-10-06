# The model and its pipeline

`nfl_model.py` is the single source of truth. Its module docstring is the
version history (v1 to v1.9), newest first; this page describes what the code
does **today** and how the repository runs it.

## The current model: `boxscore-composite-v1.9`

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

**Composite.** A logistic regression on home-minus-away differences plus a
site term, ridge-penalized, refit before every week on all earlier games
(older games discounted with a two-season half-life).

**Selection and freezing.** 24 candidates: 2 feature families × 3 team
half-lives (4, 8, 16 games) × 4 ridge strengths. The minimum walk-forward log
loss over earlier seasons picks the recipe, which is frozen for the season in
`data/frozen_recipe_<season>.json`. A config change that would alter the
signature refuses to run against an existing frozen record; that is why
feature changes ship as a new `REVISION`.

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

The market comparator is `Φ(spread / 12.37)` from the nflverse schedule line.
That line has no independent quote timestamp.

## Pipeline

```
schedule_gate.py ──► build_site.py
                       ├─ nfl_model.main()      → runs/<run>/ (transient), appends data/forward_predictions.jsonl,
                       │                          writes data/frozen_recipe_<season>.json, caches in .nfl_cache/
                       ├─ snapshot()            → data/latest/ (page inputs), data/projections/<season>_weekNN.csv
                       ├─ grade_ledger.main()   → data/forward_ledger.csv, data/ledger_report.txt
                       └─ render_all()          → public/ (index, grades, market-calibration, model, board)
validate_data_files.py ─► commit_data.py (signed commit of data/) ─► Pages deploy
```

Cold run (no caches): about 8 minutes. Warm runs reuse completed seasons'
play-by-play (weekly refresh), availability features and the historical
walk-forward grid.
