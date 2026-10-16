# R003-RF1 execution and validation

- Focused R003 support, rare-frequency, and spread-EV tests: **68 passed**.
- Full repository suite: **618 passed, 1 expected failure**, 63.20 seconds.
- `python sync_notebook.py`: notebook already in sync, no notebook changes.
- `python validate_data_files.py`: **43 files OK**.
- `git diff --check`: passed.
- Independent separate-process repeat: prediction/calibration CSVs, fit audits,
  metrics, contrasts, returns, provenance, decisions, reliability/PIT, stability
  and report are byte-identical. Every full marginal and example joint PMF array
  is exactly equal. See `deterministic_reproduction.json`.
- SHA-256 preservation check: **192 original R000–R003 and production-data files
  unchanged**, including the append-only forward ledger.
- Original R003 reconstructed with maximum score/metric error **7.11e-15**.
- Generated marginals re-read and checked for normalization, finiteness,
  nonnegativity, row identity and agreement with home-win/tie/cover/push fields.
- Spread-EV compatibility: **2,462 RF1 forecasts** checked at their recorded
  handicaps; maximum probability discrepancy **6.85e-9**, attributable to saved
  float32 rounding. Synthetic −110 was used only to exercise the evaluator;
  no historical spread ROI was computed. See `spread_ev_compatibility.json`.
- Original R003 remains the CLI default. RF1 requires explicit arm selection.

## Interpretation of the failed gate

On 816 exposed 2023–25 games, the rare-score correction improves joint NLL by
0.028119 nats/game, 95% [0.024775,0.030384]. Every primary season improves and
the ten-contrast sensitivity interval also excludes zero. These are conditional
historical diagnostics after design exposure, not fresh confirmation.

Margin CRPS worsens by **0.013551**, exceeding the registered 0.01 tolerance;
its descriptive loss-increase interval is [0.002390,0.024676]. Winner LL worsens
0.000493, Brier worsens 0.000200, and cover LL worsens 0.000665. Moneyline bets
and returns happen to be unchanged on the tested games; the transform does not
guarantee unchanged decisions for every future input.

Suppressing rare low team scores renormalizes probability across all remaining
score pairs. It therefore changes forecast locations and dependence as well as
local frequencies. On the primary sample, mean predicted total rises from
**44.9498 to 45.4521** (+0.5023 points), while average tie probability rises
**2.4952% to 2.5573%**. This is consistent with the observed secondary-metric
tradeoff; it is not a fitted causal explanation.

The probability that either team finishes on {1,2,4,5} falls from **4.1720% to
1.3107%**; rarity is moderated, not fully calibrated. No parameter, tolerance,
training window or score set was changed after viewing these results. No tie,
key-number or recentering fix was added to rescue the failed candidate.

RF1 remains a versioned research result and **fails advancement**. Any subsequent
location-preserving or key-number-aware correction needs a new specification
and evaluation. Existing R003 decisions, production models and ledgers remain
unchanged. No live prices, prospective forecasts, deployment or wagering occurred.
