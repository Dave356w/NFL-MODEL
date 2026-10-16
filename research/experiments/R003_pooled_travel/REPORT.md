# R003-PT1 — pooled travel adjustment

**Decision: no qualified improvement.** Exposed historical development, not forward confirmation.

## Flat 1u moneyline returns

| Basis | Arm | Bets | Units | ROI ± SE | Favorite units | Market null |
|---|---|---:|---:|---:|---:|---:|
| 2023-25 | plain | 812 | -4.210 | -0.52% ±2.48 pp | +0.180 | -4.10% |
| 2023-25 | selected | 812 | -6.057 | -0.75% ±2.48 pp | +0.180 | -4.10% |
| 2017-22 | plain | 1559 | -64.543 | -4.14% ±1.79 pp | -59.214 | -2.61% |
| 2017-22 | selected | 1559 | -65.439 | -4.20% ±1.80 pp | -59.214 | -2.61% |
| 2026 diagnostic | plain | 79 | -3.703 | -4.69% ±8.22 pp | -3.703 | -4.10% |
| 2026 diagnostic | selected | 79 | -3.703 | -4.69% ±8.22 pp | -3.703 | -4.10% |

Same-row eligible games; ties push. Full W–L–P, paired intervals and all fixed arms are in moneyline.json. No ATS/total ROI without offered prices.

## Distribution scores, 816 games 2023–25

| Arm | Primary CRPS ↓ | Gain vs plain | Win LL ↓ | Cover LL ↓ | Over LL ↓ |
|---|---:|---:|---:|---:|---:|
| SC1_selected | 7.213058 | +0.001075 | 0.612263 | 0.700025 | 0.696021 |
| SC1_travel_k100 | 7.207066 | +0.007068 | 0.612007 | 0.698875 | 0.695124 |
| linear_r100 | 7.215555 | -0.001422 | 0.612224 | 0.700694 | 0.696351 |
| linear_r20 | 7.217057 | -0.002924 | 0.612195 | 0.701225 | 0.696329 |
| plain | 7.214133 | +0.000000 | 0.612332 | 0.700040 | 0.696454 |
| quadratic_r100 | 7.215451 | -0.001318 | 0.612186 | 0.700687 | 0.696237 |
| quadratic_r20 | 7.216857 | -0.002723 | 0.612151 | 0.701200 | 0.696161 |
| selected | 7.216857 | -0.002723 | 0.612151 | 0.701200 | 0.696161 |

Selected-policy gain: -0.002723; 95% paired week interval [-0.00876641966700182, 0.0032908230164171944]; four-challenger sensitivity [-0.010733819333130914, 0.004956588254575993].
Annual gains: {2023: -0.00010879942320901614, 2024: -0.002614818139803297, 2025: -0.005446765724302083}. Gates: {'practical_gain': False, 'positive_interval': False, 'annual_consistency': False, 'secondary_scores': False, 'integrity': True}.
Annual choices: [(2017, 'quadratic_r20'), (2018, 'linear_r20'), (2019, 'linear_r20'), (2020, 'quadratic_r100'), (2021, 'quadratic_r100'), (2022, 'quadratic_r20'), (2023, 'quadratic_r20'), (2024, 'quadratic_r20'), (2025, 'quadratic_r20'), (2026, 'quadratic_r20')].

## Interpretation and limits

The multinomial classifier shares prior-game evidence across market contexts and both travel directions. It estimates travel likelihood from market controls and residual score shape; capped Bayes density ratios reweight the SAME observed paired-score atoms. Ridge, ratio cap and class-support shrinkage constrain the adjustment. Target outcomes and source travel labels are not used to assign atom likelihoods at prediction time.

Selection uses winner log loss from strictly earlier OOF seasons, including plain. The primary distribution score is average margin/total CRPS. All fixed arms and comparisons to earlier SC1 travel and selected paths are retained; post-hoc best-arm rank is not qualification.

Pooling replaces exact-market travel subgroup scarcity with assumptions about a common relationship across market contexts. Travel labels are home-base timezone proxies, not actual itineraries or acclimation; neutral/unknown locations revert to plain. Team geography and market selection can confound the association. No causal travel effect is established.

All historical years were exposed, and SC1 motivated this family. Bootstrap intervals condition on fitted forecast paths (10,000 whole-week resamples within season, seed 20261016); four-arm sensitivity does not correct all earlier adaptive research. Schedule revisions and historical quote timestamps remain unaudited. Nothing here establishes a forward betting edge.

See PROTOCOL.md, registration_record.json, fitted_windows.json, feature_table.csv.gz, per-game predictions, provenance and travel_slices.json. Production and original experiments remain unchanged.

Reproduce: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/pooled_travel_empirical.py`
