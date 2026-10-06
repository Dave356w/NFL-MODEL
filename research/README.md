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

_(First run's numbers; confirmation re-run from this script pending.)_

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
