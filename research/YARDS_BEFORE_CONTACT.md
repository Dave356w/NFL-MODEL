# Test 44 protocol: yards before contact, offense and defense

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner request 2026-10-14 ("yards before contact off and def?"). Committed and pushed
before any yards-before-contact profile has been built or scored. Only the files' columns, coverage
and seasons (2018–2026; 2017 does not exist) were checked.

## Question

Production uses each team's rush yards per attempt, offense and defense. Pro Football Reference's
charting splits every carry into **yards before contact**, mostly line play, and **yards after
contact**, the runner (or, on defense, tackling). Does the split carry information the total and
the market do not?

## Data, frozen

nflverse's weekly PFR advanced rushing stats (`pfr_advstats/advstats_week_rush_{2018..2026}`), regular
season, summed to team games: carries, yards before contact, yards after contact and broken tackles.
They are frozen in `ybc_inputs/team_games.csv`, with source URLs and SHA-256s; raw files are not
committed. A team's defensive line is its opponents' offensive line in the same games. Team codes
use production's aliases.

## Profiles (no lookahead)

Per team and game week, from strictly earlier games within production's three-season history limit,
weighted exactly as production weights team profiles: half-life 8 team games, halved at each season
boundary, with four league-average pseudo-games. The inputs are ratios of weighted sums, home minus
away:

* `d_ybc_off`, `d_yac_off`: yards before / after contact per carry, offense;
* `d_ybc_def`, `d_yac_def`: the same allowed by the defense.

## Arms, fixed

Each arm is refit before every week on strictly earlier rows of the 2019–26 pack (production's
training rows), with production's fit, decay and ridge 0.1, and the v1.18 penalty applied last.

**Primary (K = 3):**
1. **`plus_ybc`**: production's 29 inputs + `d_ybc_off`, `d_ybc_def`. This is the request as asked.
2. **`plus_ybc_yac`**: production + all four split inputs.
3. **`swap_rush`**: production with its two rush-yards-per-attempt inputs replaced by the four split
   inputs. It asks whether the split is better than the total.

## Bases, metrics, decision rule

Bases (never pooled): **2021–22** and **2023–25**. The data starts in 2018 and the 2019–26 pack
supports weekly fits from 2021, so 2015–20 cannot be scored. 2026 weeks 1–5 is a diagnostic.
Production is the comparator and reproduces its published forecasts. The metrics are Test 40's:
log-loss gain over production (week-clustered, 98.33% interval), gain over the market, flat 1u ROI
(null, same-row favorite, units vs production, side flips) and results by total band. Also
reported: the mean fitted coefficients and how the four inputs correlate with production's rush
yards per attempt.

* **Better than production, worth a forward shadow test:** gain > 0 on both bases, with the
  interval excluding zero on at least one.
* **Not better:** gain ≤ 0 on at least one base.
* Otherwise **unresolved**.

Development evidence only. Adoption would be a new `REVISION` and the owner's decision.

Run: `python research/yards_before_contact.py --build DIR` (raw files), then `python research/yards_before_contact.py`.

## Addendum, same day: tackles for loss

Owner follow-up ("also tackles for loss?"). Committed and pushed before any yards-before-contact or
tackles-for-loss profile has been built or scored. The only checks on the play-by-play were
definitional: in nflverse play-by-play, `tackled_for_loss` is flagged only on run plays, never on
passes or sacks. Every flagged play loses yards, and almost every run that loses yards is flagged.

**Data.** The Test 40 play-by-play download, 2013–2026 (same files, same SHA-256s as
`kalman_ratings_inputs/provenance.json`), regular season. Plays are designed runs: `play_type == 'run'`,
not a QB scramble, not deleted, not a two-point try. Per team game: designed runs and runs tackled
for a loss. Frozen in `ybc_inputs/tfl_team_games.csv`.

**Inputs.** These use the same weighting and ratio form as above, home minus away:

* `d_tfl_off`: share of the offense's designed runs stopped for a loss (higher is worse);
* `d_tfl_def`: share of opponents' designed runs the defense stops for a loss.

**Arm 4, `plus_tfl`**: production's 29 inputs + `d_tfl_off`, `d_tfl_def`. Because the play-by-play
starts in 2013, it is scored on Tests 40–43's three bases: **2015–16**, **2017–22** and
**2023–25**. 2026 weeks 1–5 is the diagnostic. Its rule is those tests' rule:

* **better**: gain > 0 on all three, with one interval excluding zero;
* **not better**: gain ≤ 0 on at least two;
* otherwise **unresolved**.

**Multiplicity.** The primary family is now **K = 4**, so every arm's interval is **98.75%**
(1 − 0.05/4). This tightens the 98.33% registered above for arms 1–3, and it is set before scoring.
Also reported: the coefficients and how the two inputs correlate with production's rush yards per
attempt.
