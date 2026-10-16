# R003-MC2 — empirical market-context iterations

**Decision: fails advancement gate.** Historical development, not fresh
confirmation or an executable-price result. Distributions contain only weighted
observed score pairs, or explicitly labeled market-relative translations.
There is no Gaussian component, support enumeration, rare-score penalty or
production-model feature. Signed spread and total are the two context inputs.

## Flat 1u moneyline returns (reported, never used for selection)

| Basis | Policy | Bets | Units | ROI ± SE | Favorite units | Null ROI |
|---|---|---:|---:|---:|---:|---:|
| 2023-25 | reference_R003 | 812 | -0.91 | -0.11% ± 2.47 pp | +0.18 | -4.10% |
| 2023-25 | selected_all | 812 | -4.21 | -0.52% ± 2.48 pp | +0.18 | -4.10% |
| 2023-25 | selected_direct_kernel | 812 | -4.21 | -0.52% ± 2.48 pp | +0.18 | -4.10% |
| 2023-25 | selected_direct_neighbor | 812 | -2.13 | -0.26% ± 2.48 pp | +0.18 | -4.10% |
| 2017-22 | reference_R003 | 1559 | -62.03 | -3.98% ± 1.79 pp | -59.21 | -2.61% |
| 2017-22 | selected_all | 1559 | -64.54 | -4.14% ± 1.79 pp | -59.21 | -2.61% |
| 2017-22 | selected_direct_kernel | 1559 | -64.54 | -4.14% ± 1.79 pp | -59.21 | -2.61% |
| 2017-22 | selected_direct_neighbor | 1559 | -48.06 | -3.08% ± 1.84 pp | -59.21 | -2.61% |
| 2026 diagnostic | reference_R003 | 79 | -3.70 | -4.69% ± 8.22 pp | -3.70 | -4.10% |
| 2026 diagnostic | selected_all | 79 | -3.70 | -4.69% ± 8.22 pp | -3.70 | -4.10% |
| 2026 diagnostic | selected_direct_kernel | 79 | -3.70 | -4.69% ± 8.22 pp | -3.70 | -4.10% |
| 2026 diagnostic | selected_direct_neighbor | 79 | -3.70 | -4.69% ± 8.22 pp | -3.70 | -4.10% |

Ties push; market pick'ems and missing prices excluded identically across policies.
Full W-L-P, controls and paired week intervals are in moneyline.json. These returns
are not evidence of executable historical prices. No spread or total ROI is
computed because actual odds are absent.

## All fixed iterations and earlier-season selected policies, 2023–25

| Arm | Primary CRPS ↓ | Margin CRPS ↓ | Total CRPS ↓ | Win LL ↓ | Cover LL ↓ | Over LL ↓ |
|---|---:|---:|---:|---:|---:|---:|
| global_residual | 7.15802 | 7.09280 | 7.22324 | 0.606063 | 0.694459 | 0.693137 |
| reference_R003 | 7.17691 | 7.11287 | 7.24094 | 0.611359 | 0.693888 | 0.694555 |
| selected_all | 7.21413 | 7.14701 | 7.28125 | 0.612332 | 0.700040 | 0.696454 |
| direct_ref_h2_t3_p0 | 7.21413 | 7.14701 | 7.28125 | 0.612332 | 0.700040 | 0.696454 |
| selected_direct_kernel | 7.21413 | 7.14701 | 7.28125 | 0.612332 | 0.700040 | 0.696454 |
| direct_ref_h2_t3_p5 | 7.22679 | 7.16247 | 7.29111 | 0.614114 | 0.701453 | 0.697360 |
| neighbors_ref_250_p0 | 7.25378 | 7.17363 | 7.33392 | 0.615242 | 0.702002 | 0.703974 |
| neighbors_ref_250_p5 | 7.25812 | 7.18042 | 7.33582 | 0.615810 | 0.702471 | 0.704102 |
| neighbors_ref_100_p0 | 7.27313 | 7.17231 | 7.37394 | 0.615329 | 0.700294 | 0.705163 |
| neighbors_ref_100_p5 | 7.27387 | 7.17981 | 7.36793 | 0.615661 | 0.700847 | 0.704664 |
| selected_direct_neighbor | 7.27464 | 7.17805 | 7.37122 | 0.616345 | 0.700564 | 0.704850 |
| direct_ref_h4_t6_p0 | 7.28143 | 7.19000 | 7.37286 | 0.615577 | 0.703638 | 0.705971 |
| direct_ref_h4_t6_p5 | 7.28586 | 7.19689 | 7.37484 | 0.616270 | 0.704171 | 0.706145 |
| direct_ref_h1_t2_p0 | 7.29330 | 7.24573 | 7.34087 | 0.625152 | 0.707160 | 0.696146 |
| direct_ref_h1_t2_p5 | 7.30016 | 7.25628 | 7.34405 | 0.623362 | 0.709036 | 0.697441 |
| global_direct | 7.81042 | 8.02318 | 7.59766 | 0.690353 | 0.769715 | 0.726659 |

Primary score = half the sum of margin and total empirical CRPS, in points.
Winner scores condition on decisive results; cover/total scores condition on
nonpush results. Ties and pushes are retained in distributions and audited.
Exact-score NLL is not scored: zero mass at unseen score pairs is not concealed
by a Gaussian or a probability floor. Wrong binary endpoint losses remain infinite.

Primary selected-policy gain versus original R003: **-0.037226**,
95% paired week interval **[-0.0690432453304249, -0.004291915527438876]**; 99.5% ten-candidate sensitivity
[-0.08146022330468566, 0.00896723262628458]. Bootstrap uses 10,000 whole-week draws within season, seed
20261016, without refitting forecasts or selection. These intervals do not remove
prior historical exposure or full adaptive research uncertainty. Every fixed arm,
including worse ones, remains reported. Fixed-arm/family intervals are descriptive.

## Selection, support and interpretation

Settings were fixed before candidate scoring in PROTOCOL.md. Annual selection
minimizes earlier-season primary CRPS only, with two OOF seasons required.
Selections: [(2017, 'direct_ref_h2_t3_p0'), (2018, 'direct_ref_h2_t3_p0'), (2019, 'direct_ref_h2_t3_p0'), (2020, 'direct_ref_h2_t3_p0'), (2021, 'direct_ref_h2_t3_p0'), (2022, 'direct_ref_h2_t3_p0'), (2023, 'direct_ref_h2_t3_p0'), (2024, 'direct_ref_h2_t3_p0'), (2025, 'direct_ref_h2_t3_p0'), (2026, 'direct_ref_h2_t3_p0')].
Candidate order resolves ties. Family-selected paths are reported separately.

MC2: direct kernel widths (1/2,2/3,4/6), pseudo-games (0/5), nearest 100/250 with pseudo-games (0/5). No translated candidate. This exploratory batch was specified after MC1 results; it is not an independent confirmation.
Settings are fixed within each batch. MC1 results remain separately reported.
Global controls test whether localization helps.
Local ESS governs shrinkage into broader historical frequencies; uncertainty in
those frequencies is not itself a per-game predictive interval.

Residual atoms translate each observed pair by implied-team-point differences,
round half-up, and discard negative transformed scores with lost mass logged.
They are labeled synthetic translations of observations, not unmodified history.
Direct arms never drop or invent score pairs. No mirrored games inflate counts.

Annual selected-policy primary gains versus R003: {'2023': -0.007814602049125005, '2024': -0.04320273516349142, '2025': -0.060661905684077276}. Winner/cover/total LL gains: {'win_ll': -0.0009726527305904398, 'cover_ll': -0.006152156505951356, 'over_ll': -0.0018992391655366925}.

Forecasting gates: {'practical_gain': False, 'positive_interval': False, 'annual_consistency': False, 'better_than_global': True, 'event_scores': False, 'integrity': True}. Any failed gate prevents advancement;
net profitability requires separate evidence regardless of forecast-score gains.
Compare winner probabilities with the actual no-vig moneyline in market_controls.json.
Neutral 0.5 spread/total controls are proxies, not recorded bookmaker probabilities.

## Files, integrity and reproduction

Per-game predictions include original prices/outcomes, configuration, source cutoff,
ESS, backoff fraction, removed residual mass, probabilities and scores. Full annual
metrics, coverage/width, reliability, stability, market controls, source/protocol
hashes and deterministic-repeat checks accompany this report. Historical quote
times are unknown; production forecasts, original research and ledgers are unchanged.

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/market_context_empirical.py --refine-direct`.
For an independent repeat, copy PROTOCOL.md and registration_record.json into a
new separate directory under research/experiments and use --output-dir.
Use --forecast REQUEST.json with explicit --arm to reconstruct source atoms and
price supplied spread offers. No network, deployment, quote capture or wagering.
