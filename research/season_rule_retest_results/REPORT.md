# No variant clears the every-season market rule

**Keep the promotion hold.** Retested 330 fixed feature corrections on all
1,451 completed games in 2021–2025 and 2026 to date. None improves winner
probabilities over the market in every season. None of the raw-spread variants
is profitable in every season at −110. No policy clears the combined rule,
including when the comparison is restricted to the common 2023–2026 window.

Production, public pages and native archives are unchanged. The v1.19 branch
remains held; this research does not nominate a replacement.

## What was tested

Two anchors: paired no-vig moneyline probabilities and a strictly earlier-fit
spread/total winner baseline. Around each, fit the 29 individual existing inputs,
three prespecified additive pairs and the full 29-input correction. Apply one
fixed shrinkage of 5%, 10%, 25%, 50% or 100% for all seasons. Gamma zero is the
market-only control; v1.18 is a separate incumbent comparator. Coefficients
refit using strictly earlier weeks, with the existing profile definitions,
training scaling and ridge penalties.

Evaluate raw continuous spreads, each generator's own prior-season median map,
and the shared incumbent median map: **990 feature/conversion paths**. Annual
medians use the original 2021 history floor and minimum support rules. Their
2021/22 results are unavailable, not assumed losses or manufactured forecasts.
Report the common 2023–2026 window separately rather than dropping early years
from the six-season rule.

Winner log loss and Brier always use the **original winner forecast**, regardless
of the ATS mapping. The median map changes the bet, not the underlying winner
probability. Five tied finals are excluded from proper scores and retained in
ATS grading. Returns assume flat 1u risk at −110, with pushes in the denominator.

The [frozen protocol](../EVERY_SEASON_MARKET_RULE.md) and
[recorded design](DESIGN.md) define the family and separate gates. Strict
improvements require score gain >1e−12 or ROI gain >1e−10; floating-point ties
do not count as wins. No target-season-specific feature or shrinkage is selected.

## Results under the full rule

| Requirement, 2021–2026 YTD | Result |
|---|---:|
| Lower log loss and Brier than both market probability baselines every season | 0/330 forecasts |
| Lower log loss and Brier than just its own anchor every season | 0/330 forecasts |
| Lower log loss and Brier than just no-vig moneylines every season | 0/330 forecasts |
| Positive raw-spread ATS ROI every season | 0/330 raw paths |
| Positive ROI and beat own-anchor policy plus favorite every season | 0/330 fully covered raw paths |
| Combined probability and ATS requirements | 0 qualifying policies |

The 660 median paths each have four supported ATS seasons; none can certify
six-season ATS coverage. All six years of their winner scores are available,
and those also fail the probability rule. Even removing partial 2026 leaves
no joint pass across completed 2021–2025.

The best raw variants pass the strict probability or ATS components in only
**three of six seasons**. Even relaxing the probability benchmark to the
variant's own anchor yields at most four of six. Four raw variants outperform
the favorite ATS control in all six years, but each loses money in some years.
Losing less than that control does not establish an edge at −110.

| Season | Feature forecasts passing both probability benchmarks | Raw paths passing all ATS checks |
|---|---:|---:|
| 2021 | 25/330 | 21/330 |
| 2022 | 50/330 | 2/330 |
| 2023 | 48/330 | 6/330 |
| 2024 | 91/330 | 23/330 |
| 2025 | 73/330 | 11/330 |
| 2026 YTD | 45/330 | 1/330 |

Different features succeed in different seasons. Choosing a separate winner
after inspecting each year would be an oracle comparison, not one strategy
that could have been followed using earlier information.

## One narrower ATS-only result

In the common 2023–2026 window, exactly one path is profitable and beats both
its same-map market anchor and the favorite in every year: **spread/total
baseline + 25% of the full 29-input correction, with its own annual medians**.
This is a descriptive survivor of the exposed search, not a validated selection.

| Season | Quarter correction + own median ROI | Market-only + own median ROI | Favorite ROI | v1.18 recipe + own median ROI |
|---|---:|---:|---:|---:|
| 2023 | +2.71% | −4.31% | +1.30% | +0.60% |
| 2024 | +2.54% | −7.29% | +1.84% | +1.14% |
| 2025 | +7.75% | +0.74% | −7.69% | +7.05% |
| 2026 YTD | +1.98% | −2.17% | −12.55% | +10.28% |

It returns +37.18u on 908 bets across those four years, versus the matched
v1.18 median replay's +33.36u. Its annual rules, fitted solely from earlier
seasons, are 2/3/7/12.5, 2/3/7/13, 2/4/6/14 and 2/4/7/13.

It still fails the rule:

- Winner probability scores fail against the market in 2021, 2022, 2025 and
  2026. In 2025 it improves its spread/total anchor but trails moneylines.
- In 2026 its winner log loss is 0.671868 versus 0.665784 for moneylines and
  0.665543 for spread/total only; Brier is worse than both as well.
- Its 2026 ATS record is 46–40–6, +1.82u, versus the same-source incumbent's
  50–36–6, +9.45u. It does not maintain current production's point return.
- Its early median coverage is unavailable, and every annual interval for
  profitability and the required ATS advantages includes zero.

The 50% correction/own-median path does **not** beat the favorite in every
available year: its 2023 137–121–14 equals the favorite's record. A numerical
equality check prevents that tie being reported as improvement.

These rows are matched-source retrospective recipe replays, not saved native
production bets. Their purpose is to compare model mechanics on identical games.
See [the annual comparison](quarter_median_comparison.csv).

## Uncertainty and independent verification

Used 9,999 paired whole-week resamples within season, shared across the fixed
family: 31,680 planned contrasts and 25,186 available nondegenerate contrasts.
The simultaneous 95% critical value is 4.355. **No candidate clears the
simultaneous evidence rule.** For the narrower quarter-correction path, all
annual ordinary and adjusted intervals for positive ROI, own-anchor advantage
and favorite advantage span zero. The 2026 season has only six week clusters.

ROI resampling preserves each policy's own return and stake denominators;
pushes are stakes, skips are not. These approximate intervals condition on
already fitted forecasts. They omit refitting uncertainty and the earlier
adaptive research and cannot establish an executable future edge.

Independent verification checked all 5,994 annual score/return rows, 999 policy
gates, settlement arrays and prior-season median maps. Separate SciPy BFGS
refits of 182 sampled week/models agree within 1.23e−7. A portable replay using
only the frozen input pack reproduces all forecast, margin, side and return
arrays exactly, and annual/gate/audit CSVs byte for byte. Fourteen focused
regression tests pass, including missing/duplicated years, floating ties,
push-inclusive stakes, future outcomes and paired ROI uncertainty.

## Artifacts and reproduction

- [Season heatmap](season_rule_heatmap.png) / [vector version](season_rule_heatmap.svg).
  Colors show point estimates, not significance; post-hoc rows are labeled.
- [Summary](review_summary.json), [every annual result](annual_scores.csv),
  [all policy gates](gate_summary.csv), [forecast definitions](variants.csv).
- [Portable inputs](frozen_inputs.csv.gz), [forecasts and decisions](predictions.npz),
  [source hashes and eligibility](provenance.json), [fit cutoffs](fit_audit.csv).
- [Independent verification](independent_verification.json),
  [portable replay verification](portable_replay_verification.json).
- [Uncertainty report](../season_rule_retest_uncertainty/REPORT.md),
  [quarter-correction intervals](../season_rule_retest_uncertainty/FOCUSED_COMPARISONS.md).

From the repository root, with the model's Python dependencies installed:

```bash
OPENBLAS_NUM_THREADS=1 python -m research.season_rule_retest --replay
OPENBLAS_NUM_THREADS=1 python -m research.verify_season_rule_retest research/season_rule_retest_results
OPENBLAS_NUM_THREADS=1 python -m research.season_rule_uncertainty
python -m pytest tests/test_season_rule_retest.py tests/test_season_rule_uncertainty.py -q
```

Regenerate the optional figure with `python research/plot_season_rule.py`
in a Python environment with matplotlib, pandas and numpy installed. Re-running
the primary fit rewrites its own research outputs; it never calls the production
build or capture routines. **Keep the production hold.**
