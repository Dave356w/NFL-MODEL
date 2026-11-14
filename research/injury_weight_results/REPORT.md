# Saved 2026 injuries: median replay and learned positional weights

Research only. Every scored forecast uses weights fitted before its evaluation week. Final updated weights use
all completed eligible games and are for future review only, never the weights used to claim their own backtest.
No production coefficient, report, lock, journal or public forecast is rewritten.

**Scope:** this fits injury-to-margin residual corrections. It does not estimate a starter-to-replacement
efficiency change, rebuild the team efficiency inputs, or propagate that change through the base fit/median map.
Zero coefficients here do not reject that separate injury-to-efficiency mechanism.

**Observed result:** every prespecified penalized positional/QB correction is zero in the historical,
weekly-updated and final fits. ATS picks and point forecasts are unchanged. Any rolling cover-score
difference from the original comes from the updated empirical error reference, not injury coefficients.

## Coverage

Saved pre-T60 vectors: 72 completed games. Both-team complete saved official reports: 12.
Historical training: 816 production-proxy games; 783 final-report medical-only games.
Historical medical exclusions for nonfinal/missing report state: 33 games.
The two evidence cohorts use different absence definitions and must not be pooled or treated as independent replicas.
Saved vectors include roster-departure proxies and can predate final inactives. Official reports are captured by T60,
but their snap weights use reconstructed earlier snap data whose original publication timestamps are unverified.

## Held-out 2026 replay

Flat 1u risk at assumed -110, pushes refunded/included in ROI denominator. Cover rates exclude pushes.
Original and control comparisons use identical eligible games within each cohort. Lower MAE/cover LL is better.

| Evidence | Arm | n | W-L-P | Units | ROI ± SE | MAE | Median residual | Cover LL |
|---|---|---:|---|---:|---:|---:|---:|---:|
| saved_vectors | always_favorite | 72 | 40-31-1 | +5.36 | +7.4% ± 11.2pp | — | — | 0.69315 |
| saved_vectors | always_home | 72 | 26-45-1 | -21.36 | -29.7% ± 10.8pp | — | — | 0.69315 |
| saved_vectors | original | 72 | 39-32-1 | +3.45 | +4.8% ± 11.2pp | 9.139 | -2.500 | 0.70444 |
| saved_vectors | prior_injury | 72 | 39-32-1 | +3.45 | +4.8% ± 11.2pp | 9.139 | -2.500 | 0.70444 |
| saved_vectors | prior_median_control | 72 | 39-32-1 | +3.45 | +4.8% ± 11.2pp | 9.139 | -2.500 | 0.70444 |
| saved_vectors | rolling_injury | 72 | 39-32-1 | +3.45 | +4.8% ± 11.2pp | 9.139 | -2.500 | 0.70308 |
| saved_vectors | rolling_median_control | 72 | 39-32-1 | +3.45 | +4.8% ± 11.2pp | 9.139 | -2.500 | 0.70308 |
| official_reports | always_favorite | 12 | 9-3-0 | +5.18 | +43.2% ± 24.9pp | — | — | 0.69315 |
| official_reports | always_home | 12 | 3-9-0 | -6.27 | -52.3% ± 24.9pp | — | — | 0.69315 |
| official_reports | original | 12 | 5-7-0 | -2.45 | -20.5% ± 28.4pp | 7.917 | -3.500 | 0.73474 |
| official_reports | prior_injury | 12 | 5-7-0 | -2.45 | -20.5% ± 28.4pp | 7.917 | -3.500 | 0.73474 |
| official_reports | prior_median_control | 12 | 5-7-0 | -2.45 | -20.5% ± 28.4pp | 7.917 | -3.500 | 0.73474 |
| official_reports | rolling_injury | 12 | 5-7-0 | -2.45 | -20.5% ± 28.4pp | 7.917 | -3.500 | 0.73382 |
| official_reports | rolling_median_control | 12 | 5-7-0 | -2.45 | -20.5% ± 28.4pp | 7.917 | -3.500 | 0.73382 |

## Learned corrections, not causal injury valuations

Non-QB units: points per +10 percentage points of home-minus-away absence share. QB: incremental points per
+1 net yard/dropback in home-minus-away projected-QB delta, beyond the base model's existing QB term.
Positive coefficients can reflect market overreaction or confounding; they are not evidence an injury helps a team.
Bootstrap ranges use 200 whole-week refits, are descriptive, and do not adjust the prior research selection.

| Evidence | Term | Historical prior | After completed eligible 2026 games | Update | Bootstrap range |
|---|---|---:|---:|---:|---|
| saved_vectors | inj_OL | +0.000 | +0.000 | +0.000 | [-0.575, +0.000] |
| saved_vectors | inj_WRTE | +0.000 | +0.000 | +0.000 | [+0.000, +0.148] |
| saved_vectors | inj_RB | +0.000 | +0.000 | +0.000 | [-0.261, +0.000] |
| saved_vectors | inj_DL | +0.000 | +0.000 | +0.000 | [+0.000, +0.149] |
| saved_vectors | inj_LB | +0.000 | +0.000 | +0.000 | [-0.126, +0.107] |
| saved_vectors | inj_DB | +0.000 | +0.000 | +0.000 | [-0.451, +0.112] |
| saved_vectors | qb_delta | +0.000 | +0.000 | +0.000 | [+0.000, +2.109] |
| official_reports | inj_OL | +0.000 | +0.000 | +0.000 | [-0.744, +0.000] |
| official_reports | inj_WRTE | +0.000 | +0.000 | +0.000 | [-0.301, +0.205] |
| official_reports | inj_RB | +0.000 | +0.000 | +0.000 | [-0.389, +0.000] |
| official_reports | inj_DL | +0.000 | +0.000 | +0.000 | [-0.122, +0.249] |
| official_reports | inj_LB | +0.000 | +0.000 | +0.000 | [-0.844, +0.020] |
| official_reports | inj_DB | +0.000 | +0.000 | +0.000 | [-0.424, +0.428] |
| official_reports | qb_delta | +0.000 | +0.000 | +0.000 | [-0.273, +1.814] |

## Unpenalized estimation diagnostic — not a backtest

Added after observing the zero penalized coefficients, solely to check shrinkage/solver behavior.
These estimates use alpha=0; they did not choose settings, generate the replay scores or replace
the prespecified alpha=.02 model. The all-2026 column is fitted on those outcomes and has NO held-out claim.
Units match the positional-weight table above. These are incremental residual corrections, not injury values.

| Evidence | Term | Earlier-season estimate | Estimate including completed 2026 games |
|---|---|---:|---:|
| saved_vectors | inj_OL | -0.226 | -0.249 |
| saved_vectors | inj_WRTE | +0.157 | +0.120 |
| saved_vectors | inj_RB | -0.084 | -0.093 |
| saved_vectors | inj_DL | +0.069 | +0.172 |
| saved_vectors | inj_LB | -0.023 | -0.049 |
| saved_vectors | inj_DB | -0.211 | -0.120 |
| saved_vectors | qb_delta | +0.941 | +0.864 |
| official_reports | inj_OL | -0.563 | -0.600 |
| official_reports | inj_WRTE | +0.078 | +0.050 |
| official_reports | inj_RB | -0.282 | -0.298 |
| official_reports | inj_DL | +0.134 | +0.168 |
| official_reports | inj_LB | -0.275 | -0.268 |
| official_reports | inj_DB | +0.109 | +0.179 |
| official_reports | qb_delta | +0.611 | +0.814 |

## Paired predictive uncertainty

Positive gains favor the challenger. 5000 whole-week resamples. The official-report cohort has only two weeks;
its interval is especially fragile and cannot establish dependable positional weights.

| Evidence | Comparison | MAE gain [95%] | Cover LL gain [95%] |
|---|---|---|---|
| saved_vectors | prior_injury vs original | +0.000 [+0.000, +0.000] | +0.00000 [+0.00000, +0.00000] |
| saved_vectors | prior_injury vs prior_median_control | +0.000 [+0.000, +0.000] | +0.00000 [+0.00000, +0.00000] |
| saved_vectors | rolling_injury vs original | +0.000 [+0.000, +0.000] | +0.00136 [-0.00264, +0.00509] |
| saved_vectors | rolling_injury vs rolling_median_control | +0.000 [+0.000, +0.000] | +0.00000 [+0.00000, +0.00000] |
| saved_vectors | rolling_injury vs prior_injury | +0.000 [+0.000, +0.000] | +0.00136 [-0.00264, +0.00509] |
| official_reports | prior_injury vs original | +0.000 [+0.000, +0.000] | +0.00000 [+0.00000, +0.00000] |
| official_reports | prior_injury vs prior_median_control | +0.000 [+0.000, +0.000] | +0.00000 [+0.00000, +0.00000] |
| official_reports | rolling_injury vs original | +0.000 [+0.000, +0.000] | +0.00093 [+0.00000, +0.01111] |
| official_reports | rolling_injury vs rolling_median_control | +0.000 [+0.000, +0.000] | +0.00000 [+0.00000, +0.00000] |
| official_reports | rolling_injury vs prior_injury | +0.000 [+0.000, +0.000] | +0.00093 [+0.00000, +0.01111] |

## Method and limitations

- Exact .5-quantile regression with fixed alpha=.02 L1 shrinkage; no squared-error mean correction.
- Weekly updates add only earlier saved 2026 games. No same-week or later outcome trains a scored prediction.
- Final all-2026 weights are separated from held-out scores; fitting and scoring them on the same games would be lookahead.
- Historical base recipes, injury inputs and all evaluated outcomes are exposed research; this is not independent confirmation.
- Injury collection/selection is audited separately from original capture/publication and from medical severity or player quality.
- Snap shares quantify recent dependence; players without prior team snaps have no measurable share and are counted in the input audit.
- Conditional cover probabilities use a prior empirical residual distribution with integer interpolation and half-count smoothing.
- Six non-QB units and the incremental QB correction have separate learned coefficients; no team-specific or injury-interaction terms.
- Coefficient changes may be unstable or shrink to zero; no larger penalty is imposed just to explain LAC/PHI.

Reproduce: `python research/positional_injury_weights.py`; rebuild frozen inputs with `--prepare`. See POSITIONAL_INJURY_WEIGHTS.md.
