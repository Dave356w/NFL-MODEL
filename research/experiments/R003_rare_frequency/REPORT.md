# R003-RF1 — rare-score frequency results

**Decision: fails advancement gate.** Exposed historical development;
no independent validation, production promotion, live quote capture or wagering.
One prior-week fitted penalty on legal rare team scores {1,2,4,5}. Original
R003 and all original results are preserved; this is a separately versioned extension.

## Flat 1u moneyline results

| Basis | Arm | Bets | W–L–P | Units | ROI ± SE | Favorite units | Null ROI |
|---|---|---:|---|---:|---:|---:|---:|
| 2023-25 | empirical__R003_rare_frequency | 812 | 554–257–1 | -0.906 | -0.11% ± 2.47 pp | +0.180 | -4.10% |
| 2023-25 | empirical__R003_score_support | 812 | 554–257–1 | -0.906 | -0.11% ± 2.47 pp | +0.180 | -4.10% |
| 2017-22 | empirical__R003_rare_frequency | 1559 | 1028–524–7 | -62.027 | -3.98% ± 1.79 pp | -59.214 | -2.61% |
| 2017-22 | empirical__R003_score_support | 1559 | 1028–524–7 | -62.027 | -3.98% ± 1.79 pp | -59.214 | -2.61% |
| 2026 diagnostic | empirical__R003_rare_frequency | 79 | 50–28–1 | -3.703 | -4.69% ± 8.22 pp | -3.703 | -4.10% |
| 2026 diagnostic | empirical__R003_score_support | 79 | 50–28–1 | -3.703 | -4.69% ± 8.22 pp | -3.703 | -4.10% |

These use identical eligible games per basis; ties push, market pick'ems are
excluded identically. ROI was not used to select or fit. Paired return intervals,
market-favorite and underdog controls are in moneyline.json. Historical prices
have unknown capture timestamps. Actual spread/total prices are unavailable,
so no historical ATS/total ROI is claimed.

## Predictive scores: 816 games, 2023–25

| Metric | Original R003 | RF1 | Gain | 95% interval |
|---|---:|---:|---:|---|
| joint_nll | 7.125085 | 7.096967 | +0.028119 | [+0.024775, +0.030384] |
| team_nll | 3.573750 | 3.559234 | +0.014516 | [+0.012856, +0.015634] |
| margin_nll | 3.927311 | 3.930269 | -0.002958 | [-0.006216, +0.000121] |
| total_nll | 3.970556 | 3.969123 | +0.001433 | [-0.002539, +0.005104] |
| team_crps | 5.111296 | 5.120284 | -0.008988 | [-0.017535, -0.000186] |
| margin_crps | 7.112870 | 7.126421 | -0.013551 | [-0.024676, -0.002390] |
| total_crps | 7.240943 | 7.249975 | -0.009031 | [-0.030731, +0.013169] |
| win_ll | 0.611359 | 0.611852 | -0.000493 | [-0.000926, -0.000050] |
| win_brier | 0.211747 | 0.211948 | -0.000200 | [-0.000380, -0.000027] |
| cover_ll | 0.693888 | 0.694552 | -0.000665 | [-0.001841, +0.000499] |
| cover_brier | 0.250347 | 0.250681 | -0.000334 | [-0.000916, +0.000242] |
| over_ll | 0.694555 | 0.695963 | -0.001408 | [-0.003851, +0.001128] |
| tie_ll | 0.029811 | 0.030426 | -0.000615 | [-0.000650, -0.000560] |

Positive gain means R003 loss minus RF1 loss. Joint NLL is the single new primary
contrast: gain +0.028119; ten-contrast sensitivity 99.5% interval
[0.022853897630292355, 0.030927573092998744]. Bootstrap: 10,000 paired whole-week draws within season,
seed 20261016, conditional on forecast paths without refitting. All periods were
already exposed, including the diagnostic that motivated this candidate; neither
interval accounts for the full adaptive research process. Secondary intervals
are descriptive and are not separate discovery claims.

Annual primary gains: {2023: 0.033644, 2024: 0.024038, 2025: 0.026675}.
Complete annual and separate-period metrics, coverage/width, reliability, PIT,
influence and leave-one-week/season sensitivity accompany this report.

## Fit and integrity

One theta per week, normalized joint-NLL fit with ridge 0.01, bounds [0,8.0],
current plus five prior seasons, two-season decay, min 256 calibration games.
Calibration uses prior-week OOF distributions beginning 2015; whole-week updates
occur only after prediction. Evaluation begins 2017. No key-number, tie-hurdle,
OT correction, grid, or ROI filter was added. Rare legal scores retain positive
probability. All derived probabilities come from the same normalized joint PMF.

Theta range: 1.045358–1.229971; upper-bound hits:
0; lower-bound hits: 0.
Per-week cutoffs and sufficient statistics are saved. Provenance records baseline
reconstruction errors, source/input/protocol hashes, versions and serialization
integrity. Fixed decision gates: {'practical_gain': True, 'positive_interval': True, 'all_primary_seasons_positive': True, 'secondary_scores': False, 'winner_scores': True, 'integrity': True}.

Reproduce: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/r003_rare_frequency.py`.
For an independent repeat, copy PROTOCOL.md and registration_record.json to a new
directory under research/experiments, then pass that path with --output-dir.
Generated marginal PMFs are ignored by Git; all archived R000–R003 outputs remain
unchanged. The original spread-EV CLI keeps its default original-R003 arm.
