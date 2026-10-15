# Test 48: Key-number-aware ATS cover probabilities (exploratory)

**Run date:** 2026-10-15. **Version:** research only; production v1.18, frozen moneyline recipe, existing fixed-band selection, and forward ledger unchanged. **Primary source:** `data/latest/fixed_band_ledger.csv` (2021–2026 reconstructed weekly predictions). **[Successful reproducible GitHub run](https://github.com/Dave356w/NFL-MODEL/actions/runs/38824337016)** includes the full 895-row output CSV and machine-readable JSON as downloadable workflow artifacts. This report reflects observed output, not estimated numbers.

## Question and fixed design

Does a pregame key-number-aware final-margin probability distribution with one corrected-model feature improve prediction and/or ATS returns relative to the existing original-implied-spread and fixed-band classifier? A separate append-only research shadow records *future first native locks* for genuine forward validation; see below.

### Methods

1. Score every game in 2023–2026 W1–5 where an earlier-season fixed-band mapping exists. **Strictly prior SEASONS only** for the probability model, even for Week 5 of 2026. The model being retroactively replayed is the current historically selected recipe; this is not independent evaluation.
2. Model the integer home scoring margin on the grid −70…+70. Baseline mass comes from a Gaussian centered on the market's home-margin spread (`sigma=12.37`), multiplied by empirically estimated prior-season absolute-margin frequency ratios; additive pseudocount 8 per absolute margin (0–40) and ratios bounded [0.5,2.5]. This retains discrete 3/7/10 masses without modifying the original moneyline prediction.
3. Adjust baseline location by bisection to **50% home cover conditional on no push** at the main market line; integer spreads can push.
4. Fit **one scalar coefficient per target season** to predict realized home-margin-minus-market-line from the original `model_spread − spread_line`. Fixed shrinkage denominator +200; coefficient constrained to [−1,1]. Tilt/recenter the same discrete PMF by this earlier-season coefficient × model-minus-market disagreement. No current-season outcomes in calibration.
5. Choose home or away only when estimated net EV at assumed **−110** is positive: `EV_home = (10/11)*P(home cover) − P(away cover)`, including pushes as 0. Compare to (a) the raw implied-spread selection, (b) the already deployed fixed-band W−L-optimized selection, and (c) an always-market-favorite control, on the same 895 games. Skips are 0 units per opportunity, and ROI per **bet** excludes skips. Quotes are **not archived**, so these are −110 proxies.
6. Compare binary cover log loss/Brier on all 870 non-push games and full integer-margin negative log likelihood on all 895; predictions calibrated from strictly prior seasons.
7. The design and chosen reported metrics were specified in code before this specific test execution, but the historical model recipe, fixed bands, and overall ATS development were already exposed to these seasons. No selection claim from nominal best ROI.

### Year-boundary calibration

| Target season | Last training season | Prior games | Model spread beta | 3-point multiplier | 7-point multiplier |
|---:|---:|---:|---:|---:|---:|
| 2023 | 2022 | 543 | 0.203 | 2.390 | 1.278 |
| 2024 | 2023 | 815 | 0.150 | 2.411 | 1.365 |
| 2025 | 2024 | 1,087 | 0.361 | 2.406 | 1.381 |
| 2026 | 2025 | 1,359 | 0.452 | 2.459 | 1.473 |

These empirical multipliers are **prior-season unconditioned absolute-margin corrections** to the market-centered normal, not bookmaker ATS price adjustments.

### Empirical results

| ATS decision arm | Graded opportunities | Bets | Record W–L–P | Units | ROI per bet | Units per opportunity |
|---|---:|---:|---:|---:|---:|---:|
| Original implied spread | 895 | 895 | 445–425–25 | −20.45 | −2.29% | −2.29% |
| Existing fixed bands | 895 | 856 | 440–394–22 | **+6.00** | **+0.70%** | +0.67% |
| Key-number-aware probability-EV rule | 895 | 53 | 26–27–0 | **−3.36** | **−6.35%** | −0.38% |
| Always market favorite | 895 | 895 | 445–425–25 | −20.45 | −2.29% | −2.29% |

On the 856 same games actually selected by fixed bands, the fixed-band **units-per-game difference** from the original ATS signal is +3.35 percentage points; the descriptive normal **95% season-week clustered interval is −5.35 to +12.04 percentage points** (59 season-week clusters). It does not resolve a positive fixed-band advantage.

| Season | Original ROI (bets) | Fixed-band ROI (bets) | Cover-probability W–L–P, ROI |
|---:|---:|---:|---|
| 2023 | −7.12% | +0.10% | 1–1–0; −4.55% (2 bets) |
| 2024 | −2.37% | −0.36% | 0–1–0; −100.00% (1 bet) |
| 2025 | +3.54% | +0.81% | 19–16–0; +3.64% (35 bets) |
| 2026 W1–5 | −5.41% | +6.10% | 6–9–0; −23.64% (15 bets) |

**Proper prediction metrics** (lower better):

| Metric | Market-centered PMF | Model-corrected PMF | Gain |
|---|---:|---:|---:|
| Binary cover log loss, 870 nonpush | 0.693147 | 0.692556 | +0.000591 |
| Binary cover Brier, 870 nonpush | 0.250000 | 0.249698 | +0.000302 |
| Discrete margin negative log likelihood, 895 | 3.839425 | 3.838538 | +0.000887 |

There is a tiny improvement in proper scores but **no demonstrated financial edge and no independent evidence**. The no-push market cover baseline is necessarily 50/50 by construction and is **not a reconstruction from actual two-sided spread odds**. The slight fit gains are not paired confidence-interval tested and should not be called significant.

### Conclusion

**Do not adopt the proposed probability-EV ATS selection.** On the assumed −110 quote, it selects 53/895 games (5.9%) and loses 6.35% per selected bet, including 2026 replay −23.64% (15 bets). The fixed-band classifier remains a separate reporting/research control, not a validated expected-margin or cover-probability forecast; its own +0.70% historical return has wide uncertainty. Neither is evidence of an executable strategy, because actual historical ATS odds and quote timestamps are missing.

Next substantive experiment: **calibrate to recorded paired spread prices and their push-adjusted conditional probabilities**, and test a price-matched discrete-margin probability forecast prospectively, not another selection on exposed historical ROI.

## Immutable forward research shadow

The builder invokes `research/ats_forward_shadow.py` after the ordinary model and site build. New shadow records start **2026-10-16 00:00 UTC** only; it uses the *earliest* pregame v1.18 snapshot per game, requires source generation within three hours of shadow capture, requires game not to have started, and never backfills older v1.18 games. No Week 6 games are retroactively declared shadow picks from the older native record.

Records are **append-only** in `data/ats_forward_shadow.jsonl`: source prediction hash, timestamp, home/away, original/fixed spread and side, probability-rule side, the prior-year model calibration hash, fixed-band mapping, conditional probabilities and simulated −110 EV. The data workflow commits only future new rows. The shadow makes no claim of contemporaneous executable ATS bookmaker odds; its price basis is explicitly `unverified_proxy_only`. Actual outcome joining is a separate read-only operation (`python -m research.ats_forward_shadow --grade-only`) and does not change stored predictions.

## Reproduction

```bash
pip install -r requirements.txt pytest
python -m pytest -q tests/test_ats_cover_probability.py
python -m research.ats_cover_probability \
  --input data/latest/fixed_band_ledger.csv \
  --output-dir research/ats_cover_probability_results
python -m research.ats_forward_shadow --grade-only
```

The workflow `.github/workflows/ats-cover-research.yml` executes the tests and historical comparison, then uploads `results.json` and the **per-game** `predictions.csv` under the `ats-cover-probability-research` artifact. The source/proper-score exercise does not affect production predictions.
