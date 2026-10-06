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
