# Research

Research-only scripts. They import `nfl_model.py` and change settings inside their
own process. They never write `data/`, the frozen recipe or the forward ledger.

**Method (all tests).** Each variant runs the production walk-forward grid
(team half-lives 4/8/16 × ridge 0.01/0.1/1/10) on 2021–2025. For each held-out season
2023, 2024 and 2025, the variant's recipe is the candidate with the lowest walk-forward
log loss on earlier seasons, which is the production selection rule. Every variant is
scored on the **same 811 priced games** with flat 1u moneyline ROI (the goal metric)
and log loss, and compared to production game by game (± is one standard error).
Same-row market favorite: +0.0% ROI. Market-correct null: −4.1%.

**Caveats.** These are held-out *reconstructions*, not forward evidence. The availability
layer was designed after these seasons were seen, so its gains are somewhat optimistic.
Trying several variants raises the chance that one looks good by luck.

Run from the repo root (warm cache ≈ 15 min and ≈ 25 min):

    python research/availability_ablation.py [CACHE_DIR]   # tests 1 and 2
    python research/qb_variants.py [CACHE_DIR]             # test 3

## Results — 2026-10-06, `boxscore-composite-v1.9`, held-out 2023–25

### Test 1: does the availability layer earn its place?

| Variant | Bets | Units | ROI ± SE | Log loss | LL vs ML market |
|---|---:|---:|---:|---:|---:|
| A no availability | 811 | −45.25 | −5.6% ± 2.7 | 0.6440 | −0.0360 |
| B QB term only | 811 | −23.30 | −2.9% ± 2.7 | 0.6374 | −0.0293 |
| C full layer (production) | 811 | +2.17 | +0.3% ± 2.7 | 0.6364 | −0.0283 |

| Comparison (same games) | ROI difference | Log-loss gain |
|---|---:|---:|
| C full vs A none | +5.85 pts ± 1.78 | +0.0076 ± 0.0036 |
| B QB only vs A none | +2.71 pts ± 1.43 | +0.0066 ± 0.0027 |
| C full vs B QB only | +3.14 pts ± 1.54 | +0.0010 ± 0.0023 |

**Yes.** Without availability the model loses money (−5.6%, worse than the −4.1%
market null). The QB term carries most of the log-loss gain, and the unit columns add
ROI with an unresolved log-loss gain. **Keep the layer.**

### Test 2: absence window length (production families)

| Variant | Bets | Units | ROI ± SE | Log loss | LL vs ML market |
|---|---:|---:|---:|---:|---:|
| window 4 (production) | 811 | +2.17 | +0.3% ± 2.7 | 0.6364 | −0.0283 |
| window 8 | 811 | +1.15 | +0.1% ± 2.7 | 0.6371 | −0.0291 |
| window 16 | 811 | +4.82 | +0.6% ± 2.7 | 0.6379 | −0.0298 |

| Comparison (same games) | ROI difference | Log-loss gain |
|---|---:|---:|
| window 8 vs 4 | −0.13 pts ± 0.82 | −0.0007 ± 0.0011 |
| window 16 vs 4 | +0.33 pts ± 1.14 | −0.0015 ± 0.0018 |

All three tables were reproduced exactly by the committed scripts; production matches the live held-out numbers (+2.17u, +0.3%).

**No.** Longer windows score slightly worse on log loss, and their ROI differences are
well inside noise. **Keep 4.**

### Test 3: QB-term variants

| Variant | Bets | Units | ROI ± SE | Log loss | LL vs ML market |
|---|---:|---:|---:|---:|---:|
| production (prior 150, half-life 8) | 811 | +2.17 | +0.3% ± 2.7 | 0.6364 | −0.0283 |
| prior 75 | 811 | +10.05 | +1.2% ± 2.7 | 0.6374 | −0.0293 |
| prior 300 | 811 | +5.45 | +0.7% ± 2.7 | 0.6355 | −0.0275 |
| QB half-life 4 | 811 | +7.80 | +1.0% ± 2.7 | 0.6375 | −0.0294 |
| QB half-life 16 | 811 | +5.16 | +0.6% ± 2.7 | 0.6363 | −0.0282 |
| + backup-start flag | 811 | −0.81 | −0.1% ± 2.7 | 0.6380 | −0.0299 |

| Comparison (same games) | ROI difference | Log-loss gain |
|---|---:|---:|
| prior 75 vs production | +0.97 pts ± 0.58 | −0.0010 ± 0.0004 |
| prior 300 vs production | +0.40 pts ± 0.49 | +0.0008 ± 0.0003 |
| QB half-life 4 vs production | +0.69 pts ± 0.79 | −0.0011 ± 0.0007 |
| QB half-life 16 vs production | +0.37 pts ± 0.49 | +0.0001 ± 0.0004 |
| + backup-start flag vs production | −0.37 pts ± 0.53 | −0.0016 ± 0.0008 |

**The production QB term is close to well tuned.** No variant beats it on ROI by
more than noise. The variants with more ROI (prior 75, half-life 4) have clearly
*worse* log loss, so their ROI gain looks like lucky picks. The backup-start flag
hurts both measures, because the QB term already covers a change of starter. Only
**prior 300** improves log loss (+0.0008, ≈2.7 SE, which survives allowing for five
variants) with ROI +0.4 within noise. That is a small gain, recorded as a candidate
for the next revision and not worth a mid-season ledger restart.

### Test 4: game-state (garbage-time) filtering of the box-score profiles

`python research/game_state.py [CACHE_DIR]`. Box scores are rebuilt from play-by-play
keeping only plays whose offense pre-snap win probability (nflverse `wp`) is inside a
band. Availability and the QB term are unchanged.

| Variant | Bets | Units | ROI ± SE | Log loss | LL vs ML market |
|---|---:|---:|---:|---:|---:|
| production (all plays) | 811 | +2.17 | +0.3% ± 2.7 | 0.6364 | −0.0283 |
| G1 wp in [0.05, 0.95] (drops 15.5% of snaps) | 811 | +13.68 | +1.7% ± 2.7 | 0.6371 | −0.0290 |
| G2 wp in [0.10, 0.90] (drops 23.3% of snaps) | 811 | −6.99 | −0.9% ± 2.7 | 0.6371 | −0.0290 |

| Comparison (same games) | ROI difference | Log-loss gain |
|---|---:|---:|
| G1 vs production | +1.42 pts ± 1.72 | −0.0007 ± 0.0023 |
| G2 vs production | −1.13 pts ± 1.85 | −0.0007 ± 0.0029 |

**No.** The ROI differences are under one SE and flip sign between the two cutoffs.
Both filters score slightly worse on log loss. Dropping 15–23% of snaps costs sample,
and blowout plays still carry information about team quality. **Keep all plays.**

### Test 5: same-week roster with game-day inactives (a T−60 model)

`python research/same_week_roster.py [CACHE_DIR]`. Production uses only the most recent
roster *before* the game week. This variant uses the game week's own roster and counts
game-day inactives (INA) as out, as a forecast made about 60 minutes before kickoff would.
The week roster is pregame: in 2024–25 none of 6,857 INA players took a snap that week,
and 0.1% of players who played were flagged out that week.

| Variant | Bets | Units | ROI ± SE | Log loss | LL vs ML market |
|---|---:|---:|---:|---:|---:|
| production (prior-week roster) | 811 | +2.17 | +0.3% ± 2.7 | 0.6364 | −0.0283 |
| same-week roster + inactives | 811 | −10.49 | −1.3% ± 2.7 | 0.6356 | −0.0275 |

| Comparison (same games) | ROI difference | Log-loss gain |
|---|---:|---:|
| same-week + inactives vs production | −1.56 pts ± 1.12 | +0.0008 ± 0.0023 |

**No.** ROI is lower (≈1.4 SE, within noise) and the log-loss change is unresolved.
Players who matter and miss a game are almost always already Out/Doubtful on the Friday
final report, which the model counts. Inactives mostly add healthy scratches and backups
with few snaps. **No same-week-roster revision.** The live check of whether nflverse
publishes inactives before kickoff is moot and was not pursued.

### Tests 6–9: wrong-signed features, expected-points stats, decay speed (2026-10-07)

**Reported from an uncommitted prototype; not reproduced by a committed script.**
Paired SEs are game-level, not season-clustered.

These tests used their own re-run baseline, `rates_core_avail_cs` only, picking h16_r0.1
in all three held-out seasons: 811 bets, +2.43u, +0.3% ± 2.7, LL 0.6352. **It is not
production.** Production searches both families, and its held-out picks are
`rates_core_adj_avail_cs_h16_r0.1` in all three seasons (+2.17u, LL 0.6364, the tables
above; confirmed by test 10's run). The 2026 frozen recipe, `rates_core_avail_cs_h8_r0.1`,
was selected on all five seasons and is different again. The paired differences are still internally
valid. On the same 811 rows, the market-correct null is −4.1% and the same-row market
favorite is +0.0%. The model's ROI is level with simply betting favorites.

| Test | Change vs re-run baseline | ROI difference | Log-loss gain | Verdict |
|---|---|---:|---:|---|
| 6 | drop offense interception % and offense penalty yards | −1.83 pts ± 1.57 | −0.0033 ± 0.0023 | No change. The effect is unresolved; it was not shown to hurt. |
| 7 | + EPA/play, dropback EPA, rush EPA, success rate, red-zone TD % | −0.79 pts ± 1.30 | +0.0024 ± 0.0023 | No change. The log-loss gain is unresolved and may be an upper bound (see below). |
| 8 | team half-life sweep {2, 4, 8, 16, 32} | – | – | No change: nested selection picked h16 every season. |
| 9 | adaptive decay w(n)·2^(−age/2) + (1−w)·2^(−age/16), w = n/(n+k), k ∈ {4, 8, 12} | – | – | No change: nested selection picked h16 every season. |

**Corrections and caveats to the original note:**
- **Test 6 missed a wrong sign.** In the current fit (`data/latest/weights.csv`, h8),
  *Defense: opponents' penalty yards* is −0.091, against the direction map. That is
  larger than either feature the test dropped. Test 10 shows it is the only stable
  wrong sign; of the two features the test dropped, one is transient and one is noise.
- **Tests 8–9 week-group tables** (fast decay is worse in weeks 1–4 and better in 14+)
  use fixed recipes on the same 2023–25 seasons and have no SEs. Test 9 was designed
  from test 8's crossover on those same seasons. Both are post-hoc diagnostics. Only
  the nested selections count as evidence, and they rejected both variants.
- **Test 7 EPA** comes from nflverse's pretrained expected-points model. If its
  training seasons include 2023–25, that is lookahead favoring the variant.
- **The production half-life surface is flat:** h16 trails h8 by 0.00045 LL
  (paired season SE 0.0027) in `data/latest/recipe_selection.csv`.
- **The model adds little beyond the market.** In `data/latest/market_blend.csv`, the
  pooled model weight given the market is −0.12 (CI −0.56 to +0.26). This holds
  across the whole held-out sample, not just late in the season.
- **Forward test.** The forward ledger starts in **week 5** (TB@DAL, Oct 8), not week 6.
  The two forward hypotheses from this note are fixed in `PREREGISTRATION.md`.

### Tests 10–11: coefficient signs, and where the held-out ROI comes from (2026-10-07)

`python research/signs_and_disagreement.py [CACHE_DIR]` (≈ 7 min with a cold cache).
The production held-out rows reproduce exactly: 811 bets, +2.17u, +0.3% ± 2.7.
Diagnostics only; nothing here changes the model.

#### Test 10: are the wrong-signed coefficients stable?

The frozen recipe (`rates_core_avail_cs_h8_r0.1`) was refit before each of 90
walk-forward weeks, 2021–2025. The table shows how often each directed coefficient
had the sign the direction map expects. Rows not shown matched in 100% of fits.

| Feature | Expected | Median coef | Expected sign, all fits | 2023–25 fits | Current 2026 fit |
|---|:---:|---:|---:|---:|---:|
| Off interception % | − | −0.072 | 100% | 100% | +0.041 |
| Off penalty yards | − | +0.006 | 38% | 41% | +0.041 |
| Off fumbles lost | − | −0.003 | 54% | 54% | −0.007 |
| Def opponents' first downs/100 | − | −0.020 | 66% | 46% | −0.017 |
| Def opponents' sack % | + | +0.025 | 76% | 72% | +0.009 |
| **Def opponents' penalty yards** | + | **−0.048** | **3%** | **6%** | **−0.091** |
| Avail LB snaps out | − | −0.007 | 58% | 48% | −0.036 |
| Avail OL / RB / DB snaps out | − | −0.04 to −0.05 | 87–96% | 100% | expected |

- **Offense interception %** has the expected sign in every 2021–25 fit. The +0.041
  appears only in the 2026 refit, after four weeks of new data. Watch it; don't drop it.
- **Offense penalty yards, offense fumbles, opponents' first downs and LB snaps out**
  hover around zero and flip often. That is noise, and ridge keeps them small.
- **Opponents' penalty yards** has the wrong sign in 97% of fits. It is a stable
  suppressor or a real effect: more penalty yards by a team's opponents predicts that team *losing*,
  once the other 20 inputs are held fixed. It is the only candidate for a pruning or
  sign-constraint test, which would need a new `REVISION`.

#### Test 11: where does the held-out ROI come from?

Production held-out predictions (each season's recipe chosen on earlier seasons only).
"LL gain" is the no-vig moneyline market's log loss minus the model's (positive = model
better), paired on the same games.

| Rows (held-out 2023–25) | Bets | Units | Model ROI ± SE | Same-row favorite | Market null | LL gain vs ML market |
|---|---:|---:|---:|---:|---:|---:|
| All games | 811 | +2.17 | +0.3% ± 2.7 | +0.0% | −4.1% | −0.0283 ± 0.0071 |
| Model agrees with ML favorite | 675 | +7.77 | +1.2% ± 2.6 | +1.2% | −4.1% | −0.0267 ± 0.0069 |
| Model picks ML underdog | 136 | −5.61 | −4.1% ± 9.5 | −5.6% | −4.1% | −0.0362 ± 0.0251 |
| \|model − ML market\| ≥ 0.10 | 245 | +4.09 | +1.7% ± 5.5 | −2.1% | −4.1% | −0.0681 ± 0.0206 |
| \|model − ML market\| > 0.17 (H1 rule) | 68 | +9.12 | +13.4% ± 11.4 | −7.4% | −4.1% | −0.0814 ± 0.0526 |
| \|model − spread market\| > 0.17 | 64 | +5.89 | +9.2% ± 12.3 | −13.0% | −4.1% | −0.1025 ± 0.0547 |
| Weeks 1–4 | 189 | +10.40 | +5.5% ± 5.8 | −0.7% | −4.1% | +0.0039 ± 0.0149 |
| Weeks 5–9 | 217 | −0.52 | −0.2% ± 5.2 | +5.6% | −4.1% | −0.0349 ± 0.0134 |
| Weeks 10–13 | 171 | +8.17 | +4.8% ± 5.5 | −1.6% | −4.1% | −0.0202 ± 0.0143 |
| Weeks 14–18 | 234 | −15.89 | −6.8% ± 4.9 | −3.3% | −4.1% | −0.0545 ± 0.0140 |

(Postseason games are not in the walk-forward rows.)

- **The edge is not where the model disagrees with the market.** When the model picks
  the moneyline underdog (136 bets), ROI is −4.1%, exactly the market-correct null.
  The model's profit comes from the 675 games where it agrees with the favorite, and
  there it ties the same-row favorite (+1.2% each).
- **The big-gap slice does not reproduce at the production recipe.** At the H1 rule,
  production gives +13.4% ± 11.4 on 68 bets (≈ 1.5 SE above the null), not +31.7% ± 18.5
  on 48. On the same rows the model's log loss is 0.081 *worse* than the market's. The
  model is directionally right more often than its probabilities deserve on those rows,
  which looks more like luck than a calibrated edge. H1 stays pre-registered, but
  expect it to fail.
- **The late-season fade is visible in the honest held-out rows.** The log-loss gain
  falls from about −0.028 ± 0.010 (weeks 5–13) to −0.055 ± 0.014 (weeks 14–18). The
  difference is about −0.026 ± 0.017 (≈ −1.5 SE). Weeks 1–4 tie the market. This is the
  same data H2 came from, so it is consistent, not confirmation.

### Tests 12–14: the market as an input, the market's phases, and what it prices (2026-10-07)

`python research/market_info.py [CACHE_DIR]` (≈ 5 min warm). Production held-out
2023–25, the same 811 priced games. Market = no-vig closing moneyline.

#### Test 12: what if the model is trained with the market as an input?

The box-score features are fit to what the market misses. *Offset* fixes the market's
log-odds at weight 1; *free* gives it an unpenalized weight. Both are refit weekly
over the production grid (24 candidates per mode), with recipes chosen on earlier
seasons only.

| Model | Bets | Units | Model-side ROI ± SE | Same-row favorite | Market null | Log loss | LL gain vs market |
|---|---:|---:|---:|---:|---:|---:|---:|
| Market alone | 811 | +0.18 | +0.0% ± 2.5 | +0.0% | −4.1% | 0.6077 | 0 |
| Production composite | 811 | +2.17 | +0.3% ± 2.7 | +0.0% | −4.1% | 0.6359 | −0.0282 ± 0.0071 |
| Market-aware, offset | 811 | +2.11 | +0.3% ± 2.5 | +0.0% | −4.1% | 0.6076 | +0.0000 ± 0.0002 |
| Market-aware, free weight | 811 | +2.11 | +0.3% ± 2.5 | +0.0% | −4.1% | 0.6078 | −0.0002 ± 0.0011 |

Exploratory value rule: bet the side the model prices ≥ 2 pts above the no-vig market.

| Model | Bets | Units | ROI ± SE | Market null |
|---|---:|---:|---:|---:|
| Production composite | 684 | −65.08 | −9.5% ± 5.0 | −4.1% |
| Market-aware, offset | 0 | – | – | – |
| Market-aware, free weight | 131 | −5.21 | −4.0% ± 4.8 | −4.1% |

- **The market-aware model becomes the market.** Nested selection chose the strongest
  ridge (10) in every season for both modes. The features add nothing to the closing
  line (+0.0000 LL), and the offset model never moves 2 pts off it.
- **The production model's departures from the market carry no value.** Betting
  wherever the production model sees 2+ pts of value loses −9.5% ± 5.0, about 1 SE worse
  than the null.
- **Limit.** Only closing lines exist historically. The forward ledger bets the snapshot
  line (often a day or more before close), and how that differs from the close cannot be
  tested backward.

#### Test 13: why the market's performance moves in phases

| Weeks | Games | Market LL | Model LL | Gain vs market ± SE | Market confidence \|q − ½\| | Blend weight: market | Blend weight: model |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1–4 | 189 | 0.6364 | 0.6331 | +0.0033 ± 0.0150 | 0.138 | +0.53 ± 0.38 | +0.71 ± 0.40 |
| 5–9 | 217 | 0.6081 | 0.6429 | −0.0349 ± 0.0134 | 0.153 | +1.36 ± 0.36 | −0.34 ± 0.41 |
| 10–13 | 171 | 0.5918 | 0.6104 | −0.0186 ± 0.0144 | 0.172 | +0.97 ± 0.41 | +0.25 ± 0.50 |
| 14–17 | 186 | 0.5962 | 0.6311 | −0.0349 ± 0.0132 | 0.170 | +1.38 ± 0.40 | −0.41 ± 0.47 |
| 18 | 48 | 0.5936 | 0.7243 | −0.1307 ± 0.0441 | 0.186 | +2.05 ± 0.74 | −1.46 ± 0.74 |

Weeks 14–18 vs weeks 1–13, by season: 2023 −0.045 vs −0.026; 2024 −0.055 vs −0.009;
2025 −0.064 vs −0.018. The late gap is worse in all three seasons.

- **The market learns the season and the model does not keep pace.** The market's log
  loss falls from 0.636 (weeks 1–4) to about 0.59 from week 10 on, and its confidence
  rises from 0.138 to 0.17–0.19. The model's log loss stays at 0.61–0.64.
- **Weeks 1–4 are the model's only competitive window.** Both start from priors there,
  and the in-sample blend gives the model a positive weight (+0.71 ± 0.40, ≈ 1.8 SE).
- **The "late fade" is mostly week 18.** Weeks 14–17 (−0.035) are no worse than weeks
  5–9 (−0.035). Week 18 is −0.131 ± 0.044 (≈ 3 SE). Clinched teams resting starters
  and eliminated teams are priced by the market and invisible to box-score rates.
  Faster decay (tests 8–9) cannot fix that.

#### Test 14: what does the market price that the model lacks?

One pregame covariate at a time, each scaled to 1 SD. Columns: how much it moves the
gap logit(market) − logit(model); whether it adds to y ~ logit(model); whether it adds
to y ~ logit(market). In-sample on the held-out rows.

| Covariate | Moves the gap | Beyond model: coef, LL gain | Beyond market: coef, LL gain |
|---|---:|---:|---:|
| Decayed point margin (h = 8 games), home − away | +0.134 ± 0.016 | +0.414 ± 0.133, +0.0061 | −0.068 ± 0.144, +0.0001 |
| Rest days, home − away | +0.045 ± 0.016 | +0.069 ± 0.075, +0.0005 | +0.026 ± 0.077, +0.0001 |
| Division game | −0.001 ± 0.016 | −0.033 ± 0.075, +0.0001 | −0.031 ± 0.077, +0.0001 |
| Wind (outdoor) | +0.035 ± 0.016 | +0.048 ± 0.074, +0.0003 | +0.014 ± 0.076, +0.0000 |
| Week 18 indicator | −0.001 ± 0.016 | +0.000 ± 0.076, +0.0000 | +0.004 ± 0.079, +0.0000 |

All five together explain 10% of the gap's variance (SD 0.46 log-odds).

- **Point margin is the clear missing input.** The market leans on it (8 SE on the gap).
  It adds to the model (+0.0061 LL, ≈ 3 SE), about a fifth of the 0.028 gap, and adds
  nothing to the market. Points carry what box-score rates drop: red-zone finishing,
  special teams, return and defensive TDs, kicking.
- **Rest and wind** are priced a little, and their added value is within noise.
  Division games are not priced.
- **The week-18 effect is game-specific** (which team rests), so a plain indicator
  shows nothing.
- **90% of the gap is unexplained here.** Plausible sources are preseason priors
  (roster moves, draft, coaching), player quality beyond snap share, news after the
  injury report, line moves, and the model's own estimation noise.

### Test 15: what the market learns, measured with the model's own pregame stats (2026-10-07)

`python research/market_mimic.py [CACHE_DIR]` (≈ 3.5 min warm). All ready, priced
regular-season games 2021–25 (n = 1,355). Market = no-vig closing moneyline log-odds.

#### A. How much of the market price do the model's stats reproduce?

Linear fit of the market log-odds. R² is out of season: each season is predicted from
the other four.

| Weeks | Games | 23 model features | + decayed margin | + last- and this-season margin | Composite log-odds alone |
|---|---:|---:|---:|---:|---:|
| 1–4 | 318 | 62% | 62% | 63% | 55% |
| 5–9 | 361 | 77% | 80% | 80% | 69% |
| 10–13 | 288 | 83% | 87% | 87% | 76% |
| 14–17 | 308 | 80% | 83% | 83% | 74% |
| 18 | 80 | 50% | 48% | 41% | 52% |
| All | 1,355 | 77% | 79% | 79% | 68% |

#### B. What the market weights vs what predicted the outcome (per 1 SD, log-odds)

| Weeks | Target | Composite | Last-season margin | This-season margin so far |
|---|---|---:|---:|---:|
| 1–4 | market | +0.27 ± 0.04 | +0.29 ± 0.03 | +0.11 ± 0.03 |
| 1–4 | outcome | +0.61 ± 0.19 | +0.28 ± 0.17 | −0.29 ± 0.14 |
| 5–9 | market | +0.35 ± 0.03 | +0.21 ± 0.02 | +0.30 ± 0.03 |
| 5–9 | outcome | +0.53 ± 0.20 | +0.16 ± 0.13 | +0.04 ± 0.17 |
| 10–13 | market | +0.39 ± 0.03 | +0.10 ± 0.02 | +0.40 ± 0.03 |
| 10–13 | outcome | +0.43 ± 0.23 | +0.01 ± 0.14 | +0.46 ± 0.22 |
| 14–17 | market | +0.44 ± 0.04 | +0.06 ± 0.02 | +0.41 ± 0.04 |
| 14–17 | outcome | +0.43 ± 0.22 | +0.09 ± 0.14 | +0.51 ± 0.22 |
| 18 | market | +0.37 ± 0.14 | +0.02 ± 0.08 | +0.46 ± 0.14 |
| 18 | outcome | −0.08 ± 0.46 | −0.42 ± 0.29 | +0.70 ± 0.47 |

#### C. The same features trained on market prices instead of outcomes

Refit before every week by weighted ridge on earlier games' closing log-odds (earlier
games only, so no lookahead). The ridge, and whether to add decayed margin, is chosen
per held-out season on earlier seasons. The baseline is the frozen recipe
(h8, unadjusted), walk-forward.

| Model (held-out 2023–25) | Bets | Units | Model-side ROI ± SE | Same-row favorite | Market null | Log loss | LL gain vs market |
|---|---:|---:|---:|---:|---:|---:|---:|
| Market alone | 811 | +0.18 | +0.0% ± 2.5 | +0.0% | −4.1% | 0.6077 | 0 |
| Frozen recipe, trained on outcomes | 811 | −4.71 | −0.6% ± 2.8 | +0.0% | −4.1% | 0.6333 | −0.0256 ± 0.0072 |
| Same features, trained on market prices | 811 | −25.63 | −3.2% ± 2.7 | +0.0% | −4.1% | 0.6284 | −0.0207 ± 0.0062 |

Market-trained minus outcome-trained, same games: LL gain +0.0049 ± 0.0041, ROI −2.58 pts
± 2.27. The two models pick different sides on 84 games.

**Reading.**
- **The market is mostly a reweighting of public stats.** The model's own 23 features
  reproduce 77% of the closing price out of season, rising to 83–87% from week 10 on.
  The rest (about 20%, about 50% in week 18) is information the stats don't hold.
- **The market's learning is visible as a shift in weight.** Its weight on last season's
  margin falls from 0.29 to 0.02 across the season, while its weight on this season's
  margin rises from 0.11 to 0.46. From week 10 on, those weights match what predicted
  outcomes, so the market reweights about right.
- **Early in the season the market leans on this season's margins, but they did not
  predict outcomes** (−0.29 ± 0.14 in weeks 1–4, about 2 SE). The composite gets more
  outcome weight than the market gives it (+0.61 vs +0.27). This fits the model's only
  competitive window, weeks 1–4, and is a post-hoc candidate for the "early-season MOV
  fade" (unregistered).
- **Training on market prices cleans up the probabilities a little** (+0.0049 ± 0.0041
  LL, unresolved), and ROI is unresolved (−2.6 ± 2.3). Copying the market's weighting
  of public stats leaves about 0.021 of log loss that only the market's private
  information closes.

### Test 16: decayed point margin as a composite input (2026-10-07)

`python research/point_margin.py [CACHE_DIR]` (≈ 5 min warm). Each production family
gains one input: the home-minus-away decayed average point margin from earlier games,
with the same weighting as the stat profiles. The production grid and nested selection
are unchanged. Both arms picked `…adj_avail_cs…_h16_r0.1` in every held-out season.

| Variant | Bets | Units | ROI ± SE | Log loss | LL vs ML market |
|---|---:|---:|---:|---:|---:|
| production | 811 | +2.17 | +0.3% ± 2.7 | 0.6364 | −0.0283 |
| + decayed point margin | 811 | +7.24 | +0.9% ± 2.7 | 0.6336 | −0.0255 |

| Comparison (same games) | ROI difference | Log-loss gain |
|---|---:|---:|
| + margin vs production | +0.62 pts ± 0.90 | +0.0028 ± 0.0010 |

| Weeks | Games | ROI difference | Log-loss gain |
|---|---:|---:|---:|
| 1–4 | 191 | −0.82 pts ± 0.82 | +0.0010 ± 0.0020 |
| 5–9 | 217 | +1.41 pts ± 2.08 | +0.0008 ± 0.0021 |
| 10–13 | 173 | −1.17 pts ± 1.63 | +0.0047 ± 0.0022 |
| 14–17 | 186 | +2.27 pts ± 2.45 | +0.0047 ± 0.0022 |
| 18 | 48 | +2.76 pts ± 2.76 | +0.0051 ± 0.0049 |

In the fit through 2025, point margin becomes the largest coefficient (+0.223 per
scaled unit, ahead of the QB term at +0.170).

**Candidate for the next `REVISION`.**
- **Log loss: +0.0028 ± 0.0010 (≈ 2.8 SE).** This is the strongest log-loss gain of
  any variant tested so far. It closes about 10% of the gap to the market.
- **The gain comes where the market pulls ahead:** weeks 10+, +0.0047 per game.
- **ROI: +0.6 pts ± 0.9, unresolved.**
- **Caveats.** Test 14 picked margin as a candidate using these same seasons, so the
  estimate is somewhat optimistic. Sixteen tests have now been run on these data.
  Point margin is a standard rating input, so the prior that it helps is high.
- Adopting it means changing the features, so it needs a new `REVISION` and
  `OUTPUT_NAME`. That is the owner's decision. Prior 300 (test 3) is the other
  candidate for that revision.
