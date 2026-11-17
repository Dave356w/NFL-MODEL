# The model and its pipeline

[LOCKING.md](LOCKING.md) defines the independent lock controller and its
durability and freshness policy. On 2026-11-16 the owner removed research code
and retired add-ons (v1.16 shadow lock, Kalshi, H1–H13 hypothesis grading,
moneyline ledger reporting, the build-held `ats_wait.py`); descriptions of them
below are history. The production recipe, fit and config signature are unchanged.

`nfl_model.py` is the single source of truth. Its module docstring is the
version history (v1 to v1.25), newest first. The next section describes what the
code does **today**, end to end; the sections after it record each version and
owner decision and are history unless the current section points to them.

## Current model, end to end

Production is `boxscore-composite-v1.25` (`nfl_model.REVISION`, output
`nfl_boxscore_output_v1_25`). Each step names the code that implements it.

### 1. Team profiles (`lagged_features`, `metric_profile`)

For every game, each team gets box-score rate profiles built only from its
earlier games: up to `MAX_HISTORY_SEASONS` (3) seasons back, weighted
2^(−age / half-life) with age counted in the team's own games, multiplied by
`OFFSEASON_RETENTION` (0.5) per season boundary. Rates are ratios of weighted
sums (for example first downs ÷ plays), not averages of per-game rates, and
each is shrunk toward the league with `PRIOR_EQUIVALENT_GAMES` (4) pseudo-games.
"For" profiles describe the team's offense; "allowed" profiles describe what its
opponents did against it. The main profiles use an 8-game half-life (h8) and the
pass profiles a 16-game half-life (h16). A feature named `d__…` is home minus away.

### 2. The ten fitted terms (`CORE_TERMS`, `model_terms`, `pass_contexts`)

| Term | Definition |
|---|---|
| `site` | 1 for a home game, 0 at a neutral site |
| `d__for__rates_core__first_down_rate` | offense first downs per 100 plays, home − away |
| `d__allowed__rates_core__first_down_rate` | first downs per 100 plays allowed, home − away |
| `d__for__rates_core__interception_pct` | interceptions thrown per 100 pass attempts, home − away |
| `d__allowed__rates_core__interception_pct` | interceptions forced per 100 opponent attempts, home − away |
| `d__allowed__rates_core__penalty_yards_per_game` | opponents' penalty yards per game, home − away |
| `d__avail__qb_delta` | projected QB's net yards per dropback minus the team's recent dropback-weighted QB mix, home − away |
| `pass_product` | z(home pass offense)·z(away pass defense) − z(away pass offense)·z(home pass defense) |
| `pass_1sd_pn` | the same product built from the parts beyond 1 SD: max(z_off − 1, 0)·max(−z_def − 1, 0), home side minus away side |
| `pass_1sd_np` | likewise with max(−z_off − 1, 0)·max(z_def − 1, 0) |

The pass z-scores standardize h16 net yards per dropback (offense, and allowed by
the defense) with the mean of the current season's earlier weeks (the previous
season's at week 1) and the SD of all earlier weeks in the current and previous
four seasons (`pass_contexts`). Other inputs (plays, rushing and
dropback yards, fumbles, own penalty yards, unit absences, largest lead and
deficit, the PP and NN hinges) are still built and audited but get no coefficient.

**QB projection.** The projected starter comes from a fresh depth chart (at least
24 hours before kickoff, at most 7 days old) among available QBs, else start
history. Historical starters are the earliest actual QB-position dropbacks
(v1.23). A projected starter listed Questionable who is not confirmed is an even
blend (`QB_QUESTIONABLE_START` = 0.5) with the next candidate; a confirmed starter
keeps his full estimate. Unit absences (Out/Doubtful at 100%, Questionable at 25%
of the player's unit snap share) are still computed for the board and audit, but
only `qb_delta` enters the fit.

### 3. The fit (`fit_composite`, refit before every week)

A logistic regression of "home won" with the no-vig moneyline log-odds as a fixed
offset (coefficient 1): logit(p) = logit(q) + Σ βᵢ·xᵢ/sᵢ. The ten terms are
scaled by their weighted SD (not centered, so a missing or neutral input
contributes zero). Training uses only labeled games from earlier weeks, weighted
2^(−age) with age in seasons over a two-season half-life (`FIT_HALF_LIFE_SEASONS`).
Ridge is 0.1 on the profile terms, 0.01 on `site` and 0.1 on the pass contexts.
Because the market price already carries home field and team strength, every
coefficient is an adjustment to the market, not a stand-alone rating. The latest
coefficients are in `data/latest/weights.csv`. The recipe is owner-fixed
(`PRODUCT_RECIPE`, `select_recipe`); it was chosen after exposed development, so
the held-out seasons are walk-forward for coefficients and medians, not for the
design.

### 4. Favorite-confidence penalty (`favorite_penalized_wp`)

Where the fitted probability backs the market favorite more strongly than q, the
forecast keeps 0.2 of its log-odds departure from q; elsewhere it is unchanged.
This never changes which team the model favors.

### 5. Raw spread (`implied_spread`)

raw = 12.37 × Φ⁻¹(p), with p clipped to 0.5–99.5% (about ±31.9 points). Positive
means home favored, the same sign as the market `spread_line`. 12.37
(`MARKET_SIGMA`) is a fixed conversion constant, not fitted.

### 6. Weekly median map (`fixed_bands.fit_weekly`, `apply`)

Before every week, each band of |raw| (<3, 3–7, 7–10, 10+) gets one number: the
weighted median of earlier games' margins signed toward the model's favorite
(losses negative, ties zero), weight 2^(−age) with a one-season half-life
(19 week slots per season). A rule needs two complete earlier seasons, 300 games
and 30 per band; otherwise there is no rule and no lock. The mapped spread is
sign(raw) × that band's number, so size within a band is discarded. For example,
the 2026 week-10 rule is 3/5/7/13 (`data/latest/fixed_band_rules.json`). Details
and evidence are under "Weekly decayed median map" below.

### 7. The pick (`fixed_bands.pick`)

Edge = mapped spread − market line. A positive edge takes home, a negative edge
takes away, and a zero edge takes the market favorite. Only a pick'em line with a
zero mapped spread skips. v1.25 applies no adjustment after the map (v1.24's −2
replacement-QB adjustment was removed).

### 8. Forecasts, snapshots and locks

* **Builds** (`build_site.py`, gated by `schedule_gate.py`) refit and refresh the
  board. The forward ledger (`data/forward_predictions.jsonl`) keeps each game's
  first pregame snapshot once both teams' injury reports carry game statuses
  (`record_forward`, `injury_reports_ready`).
* **T−60 locks** (`lock_watcher.py`, `ats_locks.py`, [LOCKING.md](LOCKING.md)) take
  the newest forecast generated within 10 minutes of the cutoff, with an ESPN quote
  within 5 minutes of that forecast, persisted before the cutoff. Lock policy v7
  (`ats_locks.FALLBACK_POLICY`) requires both teams' complete official inactive
  lists, or else complete and fresh final injury reports (`final_report_fallback`);
  see [AVAILABILITY.md](AVAILABILITY.md). Each lock saves `model_wp`, `raw_spread`,
  `market_spread`, `fixed_band_spread`, the full rule, the side and the evidence,
  and the store validator recomputes every step. Locks are append-only.

### 9. Grading and public results

`fixed_bands.grade` scores W/L/P against the line. Public Picks, Results,
Performance, Calibration and CSVs show the v1.25 regrade (`season_ats.py`):
v1.25's walk-forward replay for 2026 games whose deadline precedes 2026-11-18
00:00 UTC, and v1.25's own locks after. Returns use each game's ESPN spread price
at the exact handicap, else −110 (counted; [ESPN_SPREAD_PRICING.md](ESPN_SPREAD_PRICING.md)).
Earlier revisions' locks remain native forward evidence in `data/ledger_report.txt`.
`production_sanity.py` independently re-derives the weekly rules, grades and exports.

### What the map does in practice (development history, not forward evidence)

Diagnostics on the 2023–26 replay (952 games, −110 unless noted):

* When raw and the line fall in the same band (about 77% of games), the pick is
  identical to the line-only map (the market line passed through the same rule).
* Raw is a calibrated mean margin (slope about 1.04 on 2021–26), but between 4 and
  10 points the median margin sits 0.5–2.5 points below raw, plateauing at 7. ATS
  outcomes turn on the median, which is why the medians beat raw picks.
* The map's gain over line-only (+0.056 ± 0.023 u/game) comes almost entirely from
  games where raw is under 3 against a line of 3 or more, or where raw picks the
  other winner; elsewhere it is +0.009 ± 0.018 (at closing prices). These cells were identified after
  the fact; the map design was chosen on overlapping seasons.
* Resolving map minus line-only on forward locks at 2 SE needs about 650 locks.

## Version history and decisions (newest first)

## The current model: `boxscore-composite-v1.25`

**Owner decision 2026-11-16:** v1.25 is v1.24 without the replacement-QB margin
adjustment described below. The ten-term fit, favorite penalty, QB starter repairs,
availability gates and weekly median map are unchanged; the ATS margin is the median
map itself. Replayed on 2023–2026 with the production weekly maps, the adjustment
changed 93 picks, which went 35‑55‑3 with it and 55‑35‑3 without (−38.2u at flat −110;
it lost units in 2023, 2024 and 2025). This is development-history evidence, not forward
evidence. New T−60 candidates use lock policy v6 (`ats_locks.NO_REPLACEMENT_POLICY`): v4/v5
durability and freshness, and a lock may carry no replacement adjustment. Public 2026
results show the v1.25 regrade: its replay for every game whose T−60 deadline precedes
2026-11-18 00:00 UTC (all of week 10) and its own locks after that. v1.24's locks and
journals are unchanged. Output `nfl_boxscore_output_v1_25`, new configuration signature.

### v1.24 (production 2026-11-13 to 2026-11-16)

By owner decision on 2026-11-13, the broader replacement-starter rule applies
an additional **−2 team-margin points after the ATS median mapping**. The
projected QB is a replacement when he differs from the team's incumbent with
at least two strictly earlier starts that season and the most prior starts
(latest start breaks ties), while that incumbent remains at QB on the latest
earlier roster. Two replacements cancel in the home-minus-away margin.
Unknown identities or Questionable blends retain the unadjusted margin.
The fitted probability, raw spread, original QB term and median-map fitting
are unchanged. This is not a raw-margin adjustment or a fading penalty.

All 2026 games before adoption are replayed with the updated model. Public Picks,
Results, Performance, Calibration and exports pool this history with v1.24's own
live forward results, without earlier-version or source labels. Old saved rows
stay immutable backend evidence; they are not inherited as v1.24 forward picks.
The replay cutoff is 2026-11-14 00:00 UTC. New T−60 candidates use lock policy v5,
which audits the original mapped margin, binary replacement flags and exactly
one final adjustment while retaining v4 freshness/durability safeguards.
The output directory is `nfl_boxscore_output_v1_24` with a new signature. The
v1.16 shadow retains its original labels, features and probability series.

## v1.23 QB starter repairs

v1.23 repairs QB starter labels and confirmed-starter valuation (owner request
2026-11-13). Historical starters are the earliest actual QB-position passers, identified
from play order and game-week roster position. Gadget passers are excluded;
missing or conflicting position/order evidence remains unresolved. Schedule
QB IDs can be stale and are not accepted as actual starter labels.
Confirmed starters retain their full efficiency estimate despite a lingering
Questionable tag. Unconfirmed Questionable starters retain the existing blend.
No backup penalty, shrinkage setting or model recipe is increased. The new output
is `nfl_boxscore_output_v1_23`; previous signatures, saved decisions and append-only
journals stay intact. The v1.16 shadow is fit and scored from its original labels.
Existing v1.22 decisions (including its inherited v1.21 decisions) before
2026-11-14 00:00 UTC remain authoritative; new forecasts have a separate identity.

## v1.22 availability safeguards

v1.22 preserves the v1.19 ten-term fit and collects official game injury reports and inactive lists. RSS polling, team-news observations and news-freshness lock requirements are retired by owner request on 2026-11-09. The new revision, output name (`nfl_boxscore_output_v1_22`) and configuration signature keep earlier experiments intact. Both complete official inactive lists and fresh report checks remain required before a candidate is saved. Already-saved v1.21 selections from before retirement remain authoritative in normal public results; no stored row is rewritten or relabelled as a new native forecast. Historical training features, earlier signatures and the v1.16 shadow remain unchanged. See [AVAILABILITY.md](AVAILABILITY.md).

## v1.19 foundation: ten core terms

**v1.18 fitted on ten core terms (owner decision 2026-11-03).** New `REVISION`, `OUTPUT_NAME`
(`nfl_boxscore_output_v1_19`) and config signature. Everything else is v1.18 below: market offset,
h8 main and h16 pass profiles, ridge 0.1 on both blocks, weekly refits on earlier games only, and the
0.2 favorite-confidence penalty. The recipe carries `terms` (`CORE_TERMS`), and only these get a
coefficient:

| Term | Input |
|---|---|
| `site` | home field |
| offense / defense first-down rate | first downs per 100 plays, own and allowed |
| offense / defense INT % | interceptions thrown and forced |
| defense penalty yards | opponents' penalty yards per game |
| `d__avail__qb_delta` | QB projection |
| `pass_product`, `pass_1sd_pn`, `pass_1sd_np` | pass matchup product and two tail hinges |

The other 19 v1.18 inputs (plays, yards per rush and per dropback, fumbles, own penalty yards,
unit absences, largest lead and deficit, the PP and NN hinges) are still built and audited but
not fitted. `model_terms()` applies the restriction to the fit, the probability range and every
replay. Fitting without a term is identical to v1.18 with that column at zero (checked to 1e-17).

Evidence (research Test 50, arm S3, report in git history under `research/`; log loss vs v1.18 per 1000 games):
+1.22 ± 3.39 on 2015–16, the only basis not used to choose the terms; −2.68 ± 1.15 on 2017–22 and
−1.40 ± 1.38 on 2023–25, where the terms were chosen on overlapping 2019–25 bootstrap support. A 2026
weeks 1–8 replay, seen before adoption, gave −15.2 ± 4.6 (every model trailed the market there).
ATS differences against v1.18 are within noise and change order with the median-map history.

**Picks, results, performance and calibration** follow v1.19. The 2021–25 history and 2026 replay
regenerate under v1.19, and 2026 games whose ATS deadline precedes 2026-11-05 12:00 UTC show v1.19's
replayed pick (`season_ats.REPLAY_UNTIL`). Later games use v1.19's own 60-minute locks. v1.18's
snapshots and ATS locks stay unchanged in their append-only files.


### v1.18 (archived production, 2026-10-13 to 2026-11-03)

**v1.16 with the favorite-confidence penalty (owner decision 2026-10-13).** New `REVISION`,
`OUTPUT_NAME` (`nfl_boxscore_output_v1_18`) and config signature. Same features, fit and
coefficients as v1.16 below. The recipe carries `favorite_penalty: 0.2`, and `apply_fit` applies it
after the market offset: where v1.16 backs the market favorite more strongly than the no-vig q, the
forecast keeps 0.2 of its log-odds departure from q; elsewhere it is v1.16's. The result lies between
q and v1.16 on the same side of 50%, so **every pick and flat bet is v1.16's**; only probabilities on
favorite-bullish games change. The board's model range applies the same map to its bounds.

**v1.16 shadow lock (retired 2026-11-16).** Until 2026-11-16 each build also locked the
unpenalized v1.16 forecast; its rows stay in `forward_predictions.jsonl`.

**Public site.** The pages show the production revision only. The repository's
`data/ledger_report.txt` carries the forward ledger's proper scores, snapshot replays
(`regraded_ledger_report.md`), the independent production audit and the ATS lock
journal, idempotently. The customer navigation is Picks, Results, Performance and Calibration.

**Historical Calibration tab (owner request 2026-10-30).** The public
`historical-calibration.html` adds 2023 through the current season, with all-years
and individual season views. Only complete regular-season weeks enter; a final
current board week is included as soon as every game has a final score. The
existing build refreshes the page and `historical_calibration.csv` automatically.
The page labels reconstructed historical forecasts and exposed development
seasons, separately from the live season record. It does not change the recipe,
confidence penalty, median map, selections or forecast archives.

Market/model WP tables use the side's implied probability bands, with home,
away and both-side observations. Market bands also show approximate fair American
odds equivalents; rounded price labels do not change probability-band membership.
Actual and mean implied WP exclude tied finals;
signed median MOV includes them and includes losses. Standard errors cluster
paired observations by game. The two spread tables display ATS ROI only, with
bet counts and one standard error. The market table backs market favorites and
groups by market spread magnitude; the model table uses production ATS selections
and groups by mapped model spread magnitude (`<3`, `3–<7`, `7–<10`, `10+`). Both
grade against market handicaps at flat 1u at each game's actual spread price for the side
bet (owner decision 2026-11-04): the schedule's home/away spread odds, closing basis, carried in
`retro_ledger.csv` and the board (`nfl_model.attach_spread_prices`, reporting only). A win returns that
price's profit, losses −1u, pushes 0u; a game without a valid price uses −110 and is counted in the
CSV's `assumed_prices` and the page note. ROI divides net units by all bets including pushes. The
tables use identical eligible games, excluding market pick'ems and missing model
spreads. A zero model spread remains eligible against a nonzero market line;
zero edge follows the production favorite rule. The CSV includes aggregate
W-L-P and units supporting ROI, not per-game WP.

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
specification in `PASS_TOTAL_RECIPE` (its research scripts are in git history).

Every original snapshot is preserved. The build refreshes all historical and
current-season projection tables with v1.16 and separately replays every saved
snapshot at its original moneylines. Retrospective summaries use each game's
earliest snapshot; original-revision groups overlap and must not be pooled.
Pending games remain pending, ties push in returns and are excluded from binary
scores. Native reports continue to grade each original version unchanged.

## The goal: flat 1u ATS results at −110

**Owner decision 2026-10-19.** The model is judged by ATS results. After the
hold, break-even prices and variance, moneyline betting does not look
profitable, so moneyline betting is not reported. The
production probability engine (now v1.25), its log-loss fitting and the median
map are unchanged by this goal.

Every locked game gets 1u at an assumed −110 on the side its mapped spread
takes against the market line. When the mapped spread equals the line, the bet
is the market favorite (see "Zero edge takes the favorite" below). Only a
pick'em line with a zero mapped spread skips. A win pays +0.9091u and a loss
costs 1u. A push returns the stake and stays in ROI's denominator. A skip is
not a bet. Each ATS result is reported with:

* W-L-P, skips, units, ROI ± one standard error and n;
* cover rate excluding pushes, against the −110 break-even of 52.4%;
* the same-row baselines of always taking the favorite and always taking home;
* its basis: 60-minute lock, recorded pregame archive, replayed pregame
  forecast or historical replay. Only the 60-minute locks are native forward
  evidence. Season totals that mix bases are descriptive.

Per-band and edge-band records are descriptive, not per-game cover
probabilities. Walk-forward tests in which prior-season band rates and
exact-spread rates were used as cover probabilities did not beat a flat rate.
Spread point error (MAE) is a secondary diagnostic. On 2023–26 walk-forward
games the mapped spread, the raw spread and the market line have the same
error (9.74–9.76 points).

**Open question: median map vs raw spread.** On the 2023–26 replay under the
production weekly map (`data/ledger_report.txt`, "ATS same-row baselines"; 952
games, −110), the median map went 532‑395‑25 (57.4% cover, ROI +9.3% ± 3.0) and the
raw spread 465‑462‑25 (50.2%, −4.1% ± 3.1). This is exposed development history:
the map was adopted with it in view. On the saved locks the comparison is
unresolved. Every
60-minute lock saves `raw_spread` and `market_spread` with the mapped spread,
so the raw-spread pick can be graded on the same locked games without new
capture or backfill. The owner reviews the comparison at 100 decided locks.

The repository report (`data/ledger_report.txt`, "ATS same-row baselines")
grades the locks for the map, the raw spread, a line-only map, always-favorite
and always-home, all at assumed −110 on the same rows. The line-only map passes
the market line through the same frozen median map with no model input. The
map's paired difference from it is what the model adds beyond the line's own
band. In the development replay most map picks equal line-only picks, and the
line-only map alone returned +3.5% ± 3.0 on 2023–26. This is backend reporting
only; picks, the map and lock timing are unchanged.

## Bases of evidence: never pooled

1. **Forward ledger** (`data/forward_predictions.jsonl`): the first snapshot of
   each game written before kickoff, and only once both teams' injury reports
   carry game statuses (or practice-only teams within 6h). These are native
   forward observations. Snapshots are append-only; the experiment identity is
   `config signature : recipe : season`.
2. **Held-out seasons** (Calibration page): walk-forward predictions
   for seasons whose recipe came only from earlier seasons. They are
   reconstructions, and the design was revised after seeing them, so they are
   development evidence, not forward confirmation.
3. **This season so far**: weekly walk-forward reconstructions of games already
   played. They use current upstream data, not the data available at the time.
4. **Rebuilt history of the chosen recipe** (`data/latest/retro_ledger.csv`,
   backend only): the frozen recipe's weekly walk-forward predictions for every
   game since 2021 plus this season's earlier weeks. It trains the median map
   and feeds the ATS replay (`fixed_band_ledger.csv`). The recipe was chosen on
   those seasons, so it is hindsight, not a track record.

From v1.16 the market comparator is the model's own market input: the no-vig
probability q from the snapshot's moneylines (`market_wp` equals `market_no_vig_wp`).
The v1.12–v1.14 ledger rows stored `Φ(spread / 12.37)` from the schedule's spread
line instead. Neither nflverse quote has an independent timestamp.

Earlier out-of-sample and selection-adjusted research checks were removed on 2026-11-16 and remain in git history.

## How a week's forecast updates as injury reports arrive

This table describes the build and the forward-ledger snapshot gate
(nflverse injury statuses). T−60 ATS locks use a separate, stricter gate:
official inactive lists or the final-report fallback ([LOCKING.md](LOCKING.md),
[AVAILABILITY.md](AVAILABILITY.md)).

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
protocol committed first (the report was under `research/`, now only in git history). Weighting a
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
                       └─ render_all()          → public/ (index, grades, market-calibration,
                                                  historical-calibration), repo report appendices
validate_data_files.py ─► commit_data.py (signed commit of data/) ─► Pages deploy

lock_watcher.py / lock_watchdog.py   T−60 lock capture and coverage alerts (data/ats_locks.jsonl)
availability_collect.py              official injury reports and inactive lists
score_updates.py                     final scores (data/final_scores.json)
```

Workflows are listed in README.md.

Cold run (no caches): about 8 minutes. Warm runs reuse completed seasons'
play-by-play (weekly refresh), availability features and the historical
walk-forward grid.

### Weekly decayed median map (owner decision 2026-11-04; ATS lock policy v3)

**Owner decision 2026-11-04 (research Test 59 arm D).** The median map is refit before every week
instead of once per season. For games in week w of season Y, each band's number is the weighted
median of the signed margins of all earlier games (earlier seasons and this season's earlier weeks),
weight 2^(−age) with age = ((Y − season)·19 + (w − week))/19, a one-season half-life. Bands
(|raw spread| cut at 3, 7, 10), training rows (losses negative, ties 0, zero spreads excluded) and
minimums (two complete earlier seasons, 300 games, 30 per band) are the annual map's. Rules carry
`season`, `week`, `training_max_season`, `training_max_week`, `method=weighted_median_signed_mov_weekly_decay`
and `policy_version=median-mov-weekly-decay-2026-11-04-v2` (`fixed_bands.fit_weekly`). The zero-edge
favorite rule is unchanged.

The 60-minute locks use `median-mov-weekly-decay-ats-t60-favtie-2026-11-04-v3` and save the weekly rule
in force; `ats_locks.validate_store` requires it to be fitted for that game's week on earlier games
only. v1 and v2 locks keep validating under their saved annual rules and are not rewritten. Picks,
Results, Performance and Calibration regenerate under the weekly map: the 2021–25 history and the 2026
replay before 2026-11-05 12:00 UTC show weekly-map picks, and later games use v3 locks. v1.19, its
coefficients and `config_signature()` are unchanged. The independent audit
(`production_sanity.py`) recomputes the weekly rules and checks each export against the map
policy it declares.

Evidence (exposed development, not forward): ATS units against the annual map +76.4 ± 35.3 on 2016–22
(v1.19 replay) and +59.2 ± 26.5 on 2023–26 (production ledger), about 2.2 SE each; 92 of the 136 units
come from 2021 and 2024, and the mechanism differs by period (mostly underdogs on key-number ties
2016–22, mostly favorites 2023–26). The band numbers are no more accurate than the annual map's
(Test 59, unresolved), and a linear-trend map was reliably worse.

### Median-MOV displayed spread (2026-10-17)

Superseded as the active map on 2026-11-04 by the weekly decayed map above; `fixed_bands.fit` still
fits it for saved v1/v2 decisions, legacy exports and research.

The site's **Model spread** uses a prior-season median signed MOV calibration
in `fixed_bands.py`, replacing the earlier ATS W-L optimized values. The
v1.18 win probabilities, moneyline bets, config identity and original append-only
snapshots are unchanged. Original exports retain probability-derived
`model_spread`; compatibility exports use `fixed_band_spread` internally and
publish the calibrated value as `model_spread`.

For absolute probability-derived input groups [0,3), [3,7), [7,10), [10,infinity),
calculate the sample median of actual margin signed toward the model's pick.
These correspond to confidence cutpoints 59.5812%, 71.4264% and 79.0572% under
sigma 12.37. Include negative margins for losses and zero for tied finals;
exclude an exact 50%/zero-spread forecast from directed training. Fit once per
target season using strictly earlier seasons, at least two seasons/300 games
and 30 observations in every group. Even samples average the two central
values. No integer rounding, monotonic constraint, market line or ATS return
selects the values. A signed median may be negative; it is not forced to agree
with the outright winner probability.

The 2026 map fitted through 2025 is **3/4/7/14**. Earlier seasons independently
use **2/3/6.5/14.5** (2023), **3/3/7/14** (2024), and **3/4/6.5/14** (2025).
Rules include counts, `method=median_signed_mov` and policy identity
`median-mov-ats-2026-10-17-v1`. `fit_legacy` remains available only to reproduce
the superseded W-L optimizer; the production preparation path calls `fit`.

The owner selected this production mapping after reviewing historical tests;
statistical superiority was not established. The 895-game exposed replay at
assumed -110 is 412-349-13 with 121 skips, +25.55u on 774 selections. This is
reconstructed development, not locked native forward evidence. No historical
native prediction is rewritten to make it a median-MOV pick.

Results and Performance pages show the production median ATS results. The original
continuous-spread comparison stays in repository data and reports, on identical
eligible retrospective games. Evaluation includes tied finals;
zero edge (tolerance 1e-10) takes the market favorite before checking pushes,
and a pick'em zero edge skips; saved zero-edge skips are backfilled as favorite
bets under their own basis. At assumed −110,
risk 1u, win +0.9091u, loss −1u; pushes retain their stake in ROI's denominator,
skips do not. This is exposed development history with unknown quote-capture
times, not native forward or executable-price evidence. ATS accuracy and point
error diagnostics are separate from probability calibration. Missing training
history displays an unavailable spread rather than the superseded value.

### Zero edge takes the favorite (2026-10-19)

**Owner decision 2026-10-19.** When the median-mapped spread equals the market
line, the ATS selection is the market favorite instead of a skip. A pick'em line
(0) with a zero mapped spread still skips. The median map, its identity
`median-mov-ats-2026-10-17-v1`, v1.18 and `config_signature()` are unchanged.
The selection rule is `favorite-on-zero-edge-2026-10-19-v1` in `fixed_bands.py`,
and 60-minute locks use `median-mov-ats-t60-favtie-2026-10-19-v2`.

The rule applies retrospectively everywhere: the historical replay from 2021, the
pregame-snapshot replay, and, by a separate owner decision the same day, saved
zero-edge skips. The saved files are not rewritten. The archive and lock rows keep
their bytes, and `ats_locks.validate_store` checks each row against its own
version's rule (v1 `median-mov-ats-t60-2026-10-19-v1` skipped a zero edge).
Grading and display backfill a saved skip as a favorite bet under the separate
basis **Backfilled recorded skip**. This is a post-result backfill, not a recorded
pick or forward evidence. The two backfilled games, `2026_06_BAL_CLE` (BAL −3, lost
3–0) and `2026_06_TEN_IND` (IND −7, lost 20–26), went 0-2, −2.0u.

Evidence is exposed development history, chosen after reviewing the same games.
On the 895-game 2023–26 replay, the 121 former skips (78 at a line of 3, 17 at 7)
went 61-48-12 for the favorite, +7.5u, ROI +6.2% ± 8.2 (1 SE). The full replay
moves from 412-349-13, 121 skips, +25.5u (ROI +3.3% ± 3.4) to 473-397-25,
0 skips, +33.0u (ROI +3.7% ± 3.1). The difference is unresolved. The forward
check is the favorite's cover rate on locked zero-edge games against the 52.4%
break-even, reviewed with the map at 100 decided locks.

Each site build regenerates `data/latest/fixed_band_ledger.csv`,
`fixed_band_summary.csv`, `fixed_band_board.csv`, and `fixed_band_rules.json`,
and publishes downloadable copies. The deployment workflow commits these derived
data files; original snapshots are never rewritten.


Game cards show the ATS pick only; live moneyline picks are not published.
ATS edge is the absolute fixed-band minus market spread; zero edge takes the
market favorite, and an earlier saved zero-edge skip is shown as a backfilled
favorite bet.
The research-only historical reference helper uses fixed confidence bands 50–55%, 55–65%,
65–75%, 75–85%, 85–100% for moneyline picks, and edge bands (0,1], (1,3],
(3,7], (7,infinity) for ATS picks. Each reference excludes the game itself,
same-date and later games; absent historical dates, only earlier seasons qualify.
Records show W–L–P, sample size, skips, win/cover rates excluding pushes,
and flat 1u ROI including pushed stakes (recorded moneylines or assumed −110).
Fewer than 100 decisive bets is labeled small sample. These exposed historical
rates are descriptive references, not per-game cover probabilities. They are no
longer included on customer game cards. Partial coefficient-only probability
ranges, fitting details and confidence-to-margin diagnostics also stay off the
public pages; their source inputs and definitions remain in repository reports.

`python production_sanity.py` independently recomputes annual and weekly signed
medians, grading and denominators, checks source snapshot hashes and pregame
timestamps, and separates historical returns from native median ATS archives.
Native median-policy results come only from saved locks, never retroactive backfills.

