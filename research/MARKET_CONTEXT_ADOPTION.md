# v1.19: market baseline with all 29 inputs

**Status: ON HOLD — DO NOT MERGE OR DEPLOY.** The latest owner instruction
on 2026-10-19 supersedes the promotion request: hold until the candidate
demonstrates improvement over the market in every evaluated season.
Production remains v1.18 with its median ATS policy. No production data,
forecasts or public pages were replaced by this branch.

Evaluate each season separately against the same predeclared market-only
baseline on identical eligible games, with strictly earlier-week fits and
consistent prices. Keep probability accuracy and price-aware ATS returns
separate; the market-favorite ATS control is not itself a market probability
forecast. A pooled historical gain cannot compensate for a failing season.
Beating a losing control does not establish profitability, and per-season
point gains alone do not establish statistical reliability. Retain the prior
requirement for fresh validation at actual quotes. Keep failed seasons visible
and do not tune a separate candidate to each evaluation season to force a pass.

v1.19 currently fails this requirement: its 2026 winner log loss is worse than
the no-vig market benchmark and its ATS return trails the market-favorite
control. Keep the implementation and retrospective evidence for research.

Original owner request, superseded by the hold: promote the previously evaluated
`spread_total::group:full::g1` forecast, use its raw continuous margin for ATS,
and retrospectively regenerate all picks, results and performance. This is an
explicit production choice after exposed development, not a new research gate
passing or a claim of a proven edge.

The full-source rebuild exposes a material current-season regression: on the
same 92 completed 2026 games, v1.19 returns **−13.45u (−14.62% ROI)** versus
rebuilt v1.18 median **+9.45u (+10.28%)**. The requested model is implemented,
but these results do not support claiming maintained current ROI.

The new-minus-old decline is **−22.91u** across 39 changed ATS selections.
The current-season proper scores also worsen: winner log loss 0.701607 versus
0.680961 for v1.18 and 0.665784 for the no-vig moneyline benchmark (91 decisive
games). Six current-season week clusters limit uncertainty estimates. These
diagnostics were exposed during development and do not form a fresh test.
See the [matched-source comparison](market_context_adoption/matched_source_comparison.csv),
[proper scores](market_context_adoption/matched_source_proper_scores.csv),
[game-level replay](market_context_adoption/matched_source_games.csv.gz),
[cutoff audit](market_context_adoption/matched_source_cutoffs.csv) and
[source audit](market_context_adoption/matched_source_audit.json).

## Exact implemented candidate

`boxscore-composite-v1.19`, output `nfl_boxscore_output_v1_19`, recipe architecture
`market_spread_total`. Fit before each week using only earlier weeks:

- Market baseline: logistic home-win model on intercept, spread/7,
  (total−44)/7 and their product; mean-weighted ridge `0.01 / ESS`.
- Full correction: retain all 29 v1.18 inputs; h8 main and h16 passing
  profiles; training weighted SD scaling without centering; main/context ridge
  0.1 and site 0.01. Hold the market-stage coefficients fixed. Use the full
  regularized correction, gamma 1; remove the separate favorite penalty.
- Both stages use normalized outcome weights `2^(−age/38)` with 19-week
  seasons. Main missing values are neutral zero. Forecast eligibility retains
  finite moneyline and passing contexts, and additionally requires spread and
  total. Moneylines are a comparator/eligibility input, not the new offset.
- Convert probability to projected home margin with
  `12.37 * ndtri(clip(p, .005, .995))`. Compare with signed market home margin.
  No median mapping. At absolute edge ≤1e−10, take the market favorite;
  a pick'em zero edge skips. Flat 1u risk, assumed −110 each side.

The independent production tests compare fitting with a separate SciPy
implementation and replay frozen pre-adoption forecasts. They also test
strictly prior-week training, quote serialization and contribution sums.

## Frozen research comparison

Same 816 games in 2023–25, 19 ATS pushes, no skips. Cover rates exclude pushes;
ROI includes them. The earlier production comparator is v1.18 with its actual
2021+ prior-season median policy. These forecasts preceded promotion and are
retained without refitting in [game-level data](market_context_adoption/season_comparison_games.csv.gz).

| Season | v1.18 median W–L–P | v1.18 units | v1.19 raw W–L–P | v1.19 units | v1.19 ROI ± SE |
|---|---|---:|---|---:|---:|
| 2023 | 136–122–14 | +1.64 | 142–116–14 | +13.09 | +4.81% ±5.62 pp |
| 2024 | 142–126–4 | +3.09 | 146–122–4 | +10.73 | +3.94% ±5.73 pp |
| 2025 | 152–119–1 | +19.18 | 155–116–1 | +24.91 | +9.16% ±5.73 pp |
| Total | 430–367–19 | +23.91 | 443–354–19 | +48.73 | +5.97% ±3.28 pp |

The same-row market-favorite benchmark returned −12.36u (−1.52% ROI), and
always-home returned −33.36u (−4.09%). The new model's +3.04 pp ROI advantage
over the old production policy has an ordinary paired whole-week bootstrap
95% interval of [−4.17,+10.13] pp (4,000 draws, seed 20261019). That interval
includes zero and conditions on saved forecasts; it does not remove the earlier
search across 1,188 feature paths. Winner log loss was 0.604522 versus
production 0.606414; the advantage was not uniform across seasons.

The 327 changed ATS selections produced −2.18u versus the old policy's −27.00u;
the 489 shared selections generated +50.91u for both. Higher total return
therefore comes from losing less on disagreements. It does not establish a
profitable standalone signal for the changed picks.

- [Season metrics and paired intervals](market_context_adoption/season_comparison.csv)
- [Disagreement accounting](market_context_adoption/season_comparison_disagreements.csv)
- [Source hashes](market_context_adoption/season_comparison_audit.json)
- [Independent verification](market_context_adoption/season_comparison_verification.json)

## Retrospective rebuild and forward capture

Rebuild from current nflverse sources using the existing profile definitions
and 2019 warm-up. This includes completed games in the current week. Updated
upstream files can change reconstructed predictions relative to the frozen
research comparison; report those bases separately.

The actual rebuild reproduces 2023–25 exactly and covers every completed game
in the requested current-season cohort:

| Season | Games | v1.19 W–L–P | Units | ROI ± SE |
|---|---:|---|---:|---:|
| 2021 | 272 | 128–140–4 | −23.64 | −8.69% ±5.75 pp |
| 2022 | 271 | 132–129–10 | −9.00 | −3.32% ±5.70 pp |
| 2023 | 272 | 142–116–14 | +13.09 | +4.81% ±5.62 pp |
| 2024 | 272 | 146–122–4 | +10.73 | +3.94% ±5.73 pp |
| 2025 | 272 | 155–116–1 | +24.91 | +9.16% ±5.73 pp |
| 2026 through completed week 6 games | 92 | 38–48–6 | −13.45 | −14.62% ±9.62 pp |
| All | 1,451 | 741–671–39 | +2.64 | +0.18% ±2.47 pp |

The WAS–SF game remains pending. All six 2026 weekly projection files were
regenerated; current-season exports have 93 unique games and the all-season
export has 1,452, including the pending game. The 2021–22 seasons precede the
main 2023–25 comparison cohort. All of these outcomes have been exposed during
development; none is fresh native v1.19 validation.

- [Every rebuilt ATS pick and result](market_context_adoption/rebuilt_ats_history.csv.gz)
- [Annual results](market_context_adoption/rebuild_season_summary.csv)
- [Rebuild identity and input/output hashes](market_context_adoption/rebuild_audit.json)
- [Old archive integrity](market_context_adoption/rebuild_archive_integrity.json)
- [All six projection checks](market_context_adoption/rebuild_projection_verification.json)

Only derived projections, grading and page inputs are regenerated. Old forward
JSONL records, candidate/lock records and frozen recipes remain unchanged.
New native forecasts save both market-stage and football-stage coefficients,
training cutoffs and captured spread/total inputs. The v1.16 shadow is disabled
for v1.19: the new coefficients cannot be labeled a v1.16 forecast.

The new T−60 policy is `raw-spread-ats-t60-favtie-2026-10-19-v1`, adopted
2026-10-19 19:09:27 UTC. Both generated and observed times must precede the
cutoff; finalization must precede kickoff. Historical v1.19 replays are never
appended as native locks. A completed current-season game without a v1.19 lock
uses the authorized retrospective forecast; older-revision locks do not
override it. Backend reports retain the evidence basis. Public exports stay
ATS-only and use one row per game, plus annual performance for all rebuilt
seasons.

The existing `fixed_band_*` file/column names remain compatibility aliases for
v1.19 continuous margins. New rules are empty; archived median rules continue
to validate only their own records.

Any future promotion evaluation must satisfy the season-by-season market
comparison above and retain fresh validation at actual offered prices.
The retrospective ROI cannot establish future return or executable-price
profitability. No promotion or new production capture is authorized by this
research branch while the hold remains in force.

## Validation and publication

Full suite: 845 passed, one expected failure, 42 subtests passed. The final
backend comparator-label correction passed 24 targeted tests; UI refinements
passed 18 targeted tests and six subtests. Production sanity and validation of
44 isolated data files passed. Browser validation covered all three pages in
light/dark themes at desktop, 390px and 320px widths: 48 checks, with no script
errors or document overflow. External team-logo requests were unavailable in
this environment; team-code fallbacks worked.

The full rebuild and rendered previews were tested in an isolated state copy.
Tracked generated `data/` and `public/` are intentionally unchanged: the
serialized build workflow would regenerate and commit them if the source update
were merged. **Do not merge this branch while the hold remains in force.**
The source update, this frozen review record and its ATS results remain
available for research review.
