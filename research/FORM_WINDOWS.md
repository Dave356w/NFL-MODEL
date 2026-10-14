# Test 43 protocol: team profiles from the last 2, 3 or 4 games instead of long decay

Research only; production v1.18, its v1.16 shadow lock, frozen recipes and the forward ledger are
unchanged. Owner request 2026-10-14 ("test grouping per game into 2, 3, 4 game averages"). Committed
and pushed before any windowed profile has been built or scored.

## Question

Production describes each team by exponentially decayed averages of every earlier game: half-life 8
team games, halved again at each season boundary, shrunk toward the league by four pseudo-games.
Would short **recent-form** profiles do better, using equal-weight averages of a team's last 2, 3 or
4 games? Test 8 found shorter half-lives worse in the pre-market model; this asks the question in
production's market-offset architecture with flat windows.

## Rebuild

* **Box scores.** Team-game box scores and score peaks for 2013–2026, rebuilt with production's own
  `aggregate_boxscores`, `merge_score_peaks` and `validate_boxes`. Inputs are the nflverse play-by-play
  files downloaded for Test 40 (SHA-256s in `kalman_ratings_inputs/provenance.json`) and the nflverse
  schedule frozen for Test 37 (same download, hash-checked).
* **Fidelity check, run before any window is scored.** Production's half-life-8 profiles recomputed
  from the rebuilt boxes (`nfl_model.lagged_features`) are compared with the frozen packs' features.
  Exact agreement is not required, because upstream play-by-play can be revised. The difference is
  reported, and every arm, production included, is then scored on the rebuilt features, so
  comparisons share one data version. **Rebuilt production** (rebuilt profiles, the packs'
  availability and pass contexts) is the comparator; its agreement with the published forecasts is
  reported.

## Arms, fixed

Each window arm replaces only the main box-score profiles: the 14 non-sack rates and the two score
peaks. The window is an equal-weight average of the team's last N games before the game week,
crossing seasons, within production's three-season history limit. Production's four league
pseudo-games still apply (a monotone transform; inputs are SD-scaled before the fit). Availability,
the half-life-16 pass contexts, home field, the market offset, the weekly fit, ridge 0.1 and the
v1.18 penalty are production's.

**Primary (K = 3):** `window_2`, `window_3`, `window_4`.

**Descriptive:** nested selection among rebuilt production and the three windows. Each season from
2017 to 2025 takes whichever had the lowest pooled log loss on 2015 through the season before.

## Bases, metrics, decision rule

Bases (never pooled): 2015–16, 2017–22 and 2023–25. 2026 weeks 1–5 is a diagnostic. The metrics are
Test 40's: log-loss gain over rebuilt production (week-clustered, 98.33% interval), gain over the
market, flat 1u ROI (null, same-row favorite, units vs production, side flips) and results by total
band.

* **Better than production, worth a forward shadow test:** gain > 0 on all three bases, with the
  interval excluding zero on at least one.
* **Not better:** gain ≤ 0 on two or more bases.
* Otherwise **unresolved**.

Development evidence only. Adoption would be a new `REVISION` and the owner's decision.

Run: `python research/form_windows.py --boxes PBP_DIR GAMES_CSV` (rebuild and freeze the box scores;
needs the raw files), then `python research/form_windows.py`.
