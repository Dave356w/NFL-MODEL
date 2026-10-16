# R003-MC1 — empirical market-context iterations

**Decision: fails advancement gate.** Historical development, not fresh
confirmation or an executable-price result. Distributions contain only weighted
observed score pairs, or explicitly labeled market-relative translations.
There is no Gaussian component, support enumeration, rare-score penalty or
production-model feature. Signed spread and total are the two context inputs.

## Flat 1u moneyline returns (reported, never used for selection)

| Basis | Policy | Bets | Units | ROI ± SE | Favorite units | Null ROI |
|---|---|---:|---:|---:|---:|---:|
| 2023-25 | reference_R003 | 812 | -0.91 | -0.11% ± 2.47 pp | +0.18 | -4.10% |
| 2023-25 | selected_all | 812 | -1.71 | -0.21% ± 2.47 pp | +0.18 | -4.10% |
| 2023-25 | selected_direct_kernel | 812 | -4.25 | -0.52% ± 2.48 pp | +0.18 | -4.10% |
| 2023-25 | selected_direct_neighbor | 812 | -2.86 | -0.35% ± 2.47 pp | +0.18 | -4.10% |
| 2023-25 | selected_residual | 812 | -1.71 | -0.21% ± 2.47 pp | +0.18 | -4.10% |
| 2017-22 | reference_R003 | 1559 | -62.03 | -3.98% ± 1.79 pp | -59.21 | -2.61% |
| 2017-22 | selected_all | 1559 | -66.62 | -4.27% ± 1.79 pp | -59.21 | -2.61% |
| 2017-22 | selected_direct_kernel | 1559 | -62.21 | -3.99% ± 1.79 pp | -59.21 | -2.61% |
| 2017-22 | selected_direct_neighbor | 1559 | -63.62 | -4.08% ± 1.80 pp | -59.21 | -2.61% |
| 2017-22 | selected_residual | 1559 | -66.62 | -4.27% ± 1.79 pp | -59.21 | -2.61% |
| 2026 diagnostic | reference_R003 | 79 | -3.70 | -4.69% ± 8.22 pp | -3.70 | -4.10% |
| 2026 diagnostic | selected_all | 79 | -3.70 | -4.69% ± 8.22 pp | -3.70 | -4.10% |
| 2026 diagnostic | selected_direct_kernel | 79 | -3.70 | -4.69% ± 8.22 pp | -3.70 | -4.10% |
| 2026 diagnostic | selected_direct_neighbor | 79 | -3.70 | -4.69% ± 8.22 pp | -3.70 | -4.10% |
| 2026 diagnostic | selected_residual | 79 | -3.70 | -4.69% ± 8.22 pp | -3.70 | -4.10% |

Ties push; market pick'ems and missing prices excluded identically across policies.
Full W-L-P, controls and paired week intervals are in moneyline.json. These returns
are not evidence of executable historical prices. No spread or total ROI is
computed because actual odds are absent.

## All fixed iterations and earlier-season selected policies, 2023–25

| Arm | Primary CRPS ↓ | Margin CRPS ↓ | Total CRPS ↓ | Win LL ↓ | Cover LL ↓ | Over LL ↓ |
|---|---:|---:|---:|---:|---:|---:|
| residual_p80 | 7.15332 | 7.08793 | 7.21871 | 0.607434 | 0.694792 | 0.692916 |
| selected_all | 7.15332 | 7.08793 | 7.21871 | 0.607434 | 0.694792 | 0.692916 |
| selected_residual | 7.15332 | 7.08793 | 7.21871 | 0.607434 | 0.694792 | 0.692916 |
| residual_p20 | 7.15425 | 7.08875 | 7.21976 | 0.607531 | 0.694959 | 0.692962 |
| global_residual | 7.15802 | 7.09280 | 7.22324 | 0.606063 | 0.694459 | 0.693137 |
| reference_R003 | 7.17691 | 7.11287 | 7.24094 | 0.611359 | 0.693888 | 0.694555 |
| selected_direct_kernel | 7.26406 | 7.21198 | 7.31614 | 0.619027 | 0.705191 | 0.699730 |
| direct_h2_t3_p20 | 7.26406 | 7.21198 | 7.31614 | 0.619027 | 0.705191 | 0.699730 |
| direct_h4_t6_p20 | 7.29883 | 7.21707 | 7.38060 | 0.618251 | 0.705704 | 0.706649 |
| selected_direct_neighbor | 7.33476 | 7.29874 | 7.37078 | 0.626403 | 0.710863 | 0.706775 |
| neighbors_250 | 7.33476 | 7.29874 | 7.37078 | 0.626403 | 0.710863 | 0.706775 |
| direct_h4_t6_p80 | 7.34531 | 7.28961 | 7.40102 | 0.625028 | 0.711091 | 0.708419 |
| direct_h2_t3_p80 | 7.37295 | 7.36928 | 7.37662 | 0.632810 | 0.716433 | 0.705556 |
| neighbors_100 | 7.40498 | 7.40955 | 7.40042 | 0.636693 | 0.717898 | 0.707763 |
| direct_h8_t10_p20 | 7.49305 | 7.50077 | 7.48533 | 0.643651 | 0.729357 | 0.716262 |
| direct_h8_t10_p80 | 7.51069 | 7.52965 | 7.49174 | 0.646259 | 0.731501 | 0.716828 |
| global_direct | 7.81042 | 8.02318 | 7.59766 | 0.690353 | 0.769715 | 0.726659 |

Primary score = half the sum of margin and total empirical CRPS, in points.
Winner scores condition on decisive results; cover/total scores condition on
nonpush results. Ties and pushes are retained in distributions and audited.
Exact-score NLL is not scored: zero mass at unseen score pairs is not concealed
by a Gaussian or a probability floor. Wrong binary endpoint losses remain infinite.

Primary selected-policy gain versus original R003: **+0.023585**,
95% paired week interval **[-0.0009924553199839893, 0.050190878093184045]**; 99.5% ten-candidate sensitivity
[-0.012649633984455982, 0.06254704230359238]. Bootstrap uses 10,000 whole-week draws within season, seed
20261016, without refitting forecasts or selection. These intervals do not remove
prior historical exposure or full adaptive research uncertainty. Every fixed arm,
including worse ones, remains reported. Fixed-arm/family intervals are descriptive.

## Selection, support and interpretation

Settings were fixed before candidate scoring in PROTOCOL.md. Annual selection
minimizes earlier-season primary CRPS only, with two OOF seasons required.
Selections: [(2017, 'residual_p80'), (2018, 'residual_p80'), (2019, 'residual_p80'), (2020, 'residual_p80'), (2021, 'residual_p80'), (2022, 'residual_p80'), (2023, 'residual_p80'), (2024, 'residual_p80'), (2025, 'residual_p80'), (2026, 'residual_p80')].
Candidate order resolves ties. Family-selected paths are reported separately.

MC1: kernel widths (2/3,4/6,8/10), pseudo-games (20/80), neighbor counts (100/250), and two residual translations.
Settings are fixed within each batch. MC1 results remain separately reported.
Global controls test whether localization helps.
Local ESS governs shrinkage into broader historical frequencies; uncertainty in
those frequencies is not itself a per-game predictive interval.

Residual atoms translate each observed pair by implied-team-point differences,
round half-up, and discard negative transformed scores with lost mass logged.
They are labeled synthetic translations of observations, not unmodified history.
Direct arms never drop or invent score pairs. No mirrored games inflate counts.

Annual selected-policy primary gains versus R003: {'2023': 0.02446540353008953, '2024': 0.03039294329967278, '2025': 0.01589663713014829}. Winner/cover/total LL gains: {'win_ll': 0.003925437987589597, 'cover_ll': -0.0009046118033149142, 'over_ll': 0.0016384901778961902}.

Forecasting gates: {'practical_gain': True, 'positive_interval': False, 'annual_consistency': True, 'better_than_global': True, 'event_scores': True, 'integrity': True}. Any failed gate prevents advancement;
net profitability requires separate evidence regardless of forecast-score gains.
Compare winner probabilities with the actual no-vig moneyline in market_controls.json.
Neutral 0.5 spread/total controls are proxies, not recorded bookmaker probabilities.

## Files, integrity and reproduction

Per-game predictions include original prices/outcomes, configuration, source cutoff,
ESS, backoff fraction, removed residual mass, probabilities and scores. Full annual
metrics, coverage/width, reliability, stability, market controls, source/protocol
hashes and deterministic-repeat checks accompany this report. Historical quote
times are unknown; production forecasts, original research and ledgers are unchanged.

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/market_context_empirical.py`.
For an independent repeat, copy PROTOCOL.md and registration_record.json into a
new separate directory under research/experiments and use --output-dir.
Use --forecast REQUEST.json with explicit --arm to reconstruct source atoms and
price supplied spread offers. No network, deployment, quote capture or wagering.
