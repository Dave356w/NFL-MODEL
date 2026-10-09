# Availability-adjusted player value (AV) vs v1.15 — walk-forward research

Research only. Nothing here changes `nfl_model.py`, the frozen recipes, the forward ledger, `data/`
or the build: the code imports `nfl_model` and changes module settings inside its own process, as
every other `research/` script does. Results: [`REPORT.md`](REPORT.md).

## Run

```
pip install -r requirements.txt pytest
python research/av/prepare_data.py .nfl_cache     # nflverse player inputs 2013-2025 (~1 min cold)
python research/av/walkforward.py .nfl_cache      # A, B, C, D walk-forward (~60 min cold; cached stages)
python research/av/audit_inputs.py .nfl_cache     # input audit -> output/data_audit.md
python research/av/evaluate.py                    # paired tables -> output/results.md, output/summary.csv
python -m pytest tests/test_av_research.py -q     # leakage/behaviour tests (+ the control check once outputs exist)
```

Stages cache under `.nfl_cache/av/` (git-ignored): raw nflverse tables, `pgv.parquet` (per-game rAV),
`av_features.parquet`, `av_player_audit.parquet` (every projected player share, ~1M rows),
`bd_predictions.parquet`, `oof_ac.parquet`. Delete a file to rebuild that stage. Committed outputs in
`output/`: `heldout_predictions.csv` (every variant on every held-out game), `selection.json`,
`control_check.json`, `av_team_week_features.csv.gz` (feature audit, all 2019–25 team-weeks),
`provenance.json`, `data_audit.md`, `results.md`, `summary.csv`.

## The AV blocker, and what is used instead

Per-season **PFR Approximate Value could not be acquired**: pro-football-reference.com returns HTTP 403
to this environment (and Sports Reference's terms restrict automated collection); nflverse carries
only PFR *career* AV (`draft_picks.w_av`, `car_av`, `dr_av`), scraped after the fact, so any use of it
as a feature is lookahead by construction. No other legitimate per-season source was found.

So the experiment uses **rAV**, a per-game reconstruction of PFR's published allocation scheme from
nflverse box scores and snap counts (`player_value.py`). It is labelled rAV throughout and is **not PFR
AV**. Building it per game is also what makes an as-of-week value possible (spec §4.4) without
retro-allocating a final-season total. PFR career AV is used once, to validate the reconstruction
(`output/data_audit.md`).

To run the same experiment on true PFR AV, a licensed per-season AV table keyed by `pfr_player_id`
would replace the season totals in `player_value.season_table` for *prior seasons only*; in-season
updates would still need a game-level allocation like rAV.

## Definitions and time boundaries

| Piece | Definition | Uses only |
|---|---|---|
| rAV per game | team offensive pool `6.25 × off. points / league` (5/11 OL by snaps; 6/11 skill: rush by rushing yards, pass 26% passers / 74% receivers by yards); defensive pool `6.25 × max(0, 2 − opp. off. points / league)` (2/3 DL+LB, 1/3 DB; half by snaps, half by an impact score). K/P/returners not modelled | that game's box score; league mean of the **previous** season |
| rate | rAV per full game = Σ rAV / Σ snap share | — |
| pregame rate | `(Σ_s .5^(y−1−s) rAV_s [+ rAV_ytd] + 4 μ0) / (Σ_s .5^(y−1−s) G_s [+ G_ytd] + 4)`, 3 prior seasons; `prior` mode never uses season y, `blend` adds season-y games **before week w** from week 5 | earlier seasons; earlier weeks |
| μ0 prior | rookies: `a_u ln(pick) + b_u` (WLS on earlier cohorts' rookie seasons); undrafted rookies: earlier undrafted mean; everyone else: veteran mean of the 3 prior seasons | cohorts with rookie season < y |
| replacement | 25th percentile of player-season rates (≥ 4 full games), 3 prior seasons, per unit (QB, OL, RB, WR/TE, DL, LB, DB) | seasons < y |
| membership, outs | v1.15's rules exactly: week's injury report, roster before the game week, game week's own reserve list, departures, membership data-gap rule | published before kickoff (see the timing audit) |
| participation multiplier | Out 0, Doubtful .15, Questionable .65, available 1, roster-out/departed 0 (hypotheses, not calibrated) | — |
| base share | mean snap share over the player's last 4 games with snaps (any team, seasons y−1..y) | earlier games |
| projected share | fill by descending base share up to the unit's slots (team's recent summed share), then give the shortfall to available players by headroom `m − p`; QB = v1.15's projected starter (50/50 if Questionable) | — |
| unit value | linear `Σ p (rate − rep)` (raw: `Σ p rate`); weak-link OL top-5 `5 × [.15,.15,.20,.25,.25]` and DB top-4 `4 × [.2,.2,.3,.3]` on value-ordered starters (weakest weighted most) | — |
| AV loss (Model C) | unit value at kickoff minus the same with everyone healthy and still on the team | — |

## Variants (all on identical games; each season's recipe on earlier seasons by log loss)

| ID | Model | Candidates |
|---|---|---|
| A | exact v1.15 (production families, grid and selection) | 24 |
| B1 | pure rAV, raw linear units → ridge margin → Φ(μ/σ) | 2 rate modes × 4 ridges |
| B2 | pure rAV, replacement-relative + weak-link | 8 |
| C1 | v1.15 with unit absence shares replaced by rAV unit losses (QB efficiency kept) | 24 |
| C2 | v1.15 with both availability representations | 24 |
| D1 | B2 roster margin (walk-forward, never in-sample) + shrunk team residual, λ ∈ {.85,.90,.92}, γ ∈ {1,4,12} | 72 |
| D2 | D1 with opponent-adjusted residuals (`MOV − μ_roster + α_opp`, pregame α) | 72 |
| ablations | C3 (QB rAV loss replaces QB efficiency), B2 prior-only vs blended rates, replacement-relative linear, min-starter | — |

## Known limitations

* rAV is a reconstruction; per-season agreement with PFR AV is unverified (only career totals exist).
  OL and team-pool shares make a lineman's rAV largely his team's past offensive output, i.e. team
  performance re-enters through players.
* Base shares come from past snaps only: a week-1 rookie starter has no base share and gets snaps only
  through redistribution. Pre-2025 depth charts carry no publish time and are not used.
* Historical weekly rosters have no publish time (timing audit in `output/data_audit.md`); historical
  moneylines and spreads are nflverse schedule closes with no quote time, not pregame snapshots.
* Model C's AV loss uses the blended estimator only (fixed before results, to limit the grid).
