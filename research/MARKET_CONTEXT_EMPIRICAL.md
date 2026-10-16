# Observed outcomes in comparable market contexts

This implements the owner's intended empirical hypothesis: estimate outcome
probabilities from historical games with similar signed spread and total, rather
than constructing possible score combinations. Implied team points are derived
from those two coordinates and are not counted again in the similarity distance.
No team box-score model, Gaussian component or R003/RF1 score mask is used.

Two separately specified batches are retained:

- **MC1:** six direct kernels, two nearest-neighbor settings, and two explicitly
  translated market-relative variants. All ten use earlier-season selection.
- **MC2:** an exploratory refinement after MC1: ten direct-only settings with
  weaker/no global backoff. The original MC1 results and failed gate remain.

All forecasts use strictly earlier weeks. Settings are selected using earlier
OOF seasons only, never ROI or the current evaluation season. The main comparison
is 816 games from 2023–25; 2017–22 and 2026 are reported separately. History was
already exposed, and MC2 follows inspection of MC1; neither is fresh confirmation.

## What the iterations found

Lower scores are better. CRPS averages margin and total distribution scores.

| 2023–25 policy | CRPS | Winner LL | Cover LL | Moneyline units / 812 bets |
|---|---:|---:|---:|---:|
| Original R003 | 7.17691 | .611359 | .693888 | −0.91u |
| MC1 selected direct | 7.26406 | .619027 | .705191 | −4.25u |
| MC2 selected direct | 7.21413 | .612332 | .700040 | −4.21u |
| MC1 selected market-relative | 7.15332 | .607434 | .694792 | −1.71u |

The same-row favorite earns +0.18u; the proportional market null is approximately
−4.10% ROI. MC2 direct ROI is −0.52% ±2.48 pp SE; MC1 relative is −0.21% ±2.47 pp.
No historical spread/total ROI is computed: actual offered odds are missing.

MC2 improves direct matching by **0.04993 CRPS points**, descriptive 95% week
interval [0.01948,0.08285], after the first results had been seen. It still
trails R003 by 0.03723, interval [0.00429,0.06904] for the loss increase.
The relative variant beats R003 by 0.02359, but interval [−0.00099,0.05019]
includes deterioration. Both batches fail their locked advancement gates.

The relative variant's winner LL gain over the moneyline is only 0.000638,
interval [−0.003189,0.004755]. Context localization adds just 0.00470 CRPS points
over global translated residuals, interval [−0.01157,0.02024]. Strong net-return
or incremental market-information claims are unsupported.

## Why the direct model is still useful to retain

The selected direct refinement is `direct_ref_h2_t3_p0`: spread bandwidth 2,
total bandwidth 3, no unrelated global backoff. Earlier-season selection chose
it in every evaluated season. Its main-period mean effective sample size is
about 202 games. It uses only the historical paired final scores themselves.

It preserves football outcome concentrations much better than the translated
alternative:

| Pooled probability, 2023–25 | Direct MC2 | Translated MC1 | Observed |
|---|---:|---:|---:|
| Absolute margin exactly 3 | 14.64% | 6.69% | 14.22% |
| Absolute margin exactly 7 | 7.83% | 5.69% | 8.33% |
| Tie | 0.376% | 3.063% | 0.123% |

These are descriptive pooled diagnostics, not proof of game-by-game calibration.
The translated variant shifts/rounds historical outcomes, discards about 1.09%
negative-atom probability on average, and can produce rule-unreachable pairs:
mean mass 0.0267%, maximum 0.644%. No mask was added to hide this limitation.
Its better aggregate CRPS does not make it a faithful observed-score model or
a validated alternative-line pricer.

Retain the direct model as the transparent research implementation of the
original hypothesis, with the translated model as a separate benchmark. Do not
replace production or assert profitable spread prices. Actual paired prices
are needed to test whether the better key-number shape matters at tradable lines.

## Run or price an externally supplied offer

```bash
OPENBLAS_NUM_THREADS=1 python research/market_context_empirical.py
OPENBLAS_NUM_THREADS=1 python research/market_context_empirical.py --refine-direct
OPENBLAS_NUM_THREADS=1 python research/review_market_context.py
```

Create a request using a game identity, market spread/total and actual offered
handicap/odds. This is a **synthetic format example**, not a live quote:

```json
{
  "target": {
    "game_id": "EXAMPLE",
    "season": 2026,
    "week": 6,
    "spread_line": 3,
    "total_line": 48
  },
  "offers": [
    {"side": "home", "handicap": -3, "american_odds": -110},
    {"side": "away", "handicap": 3, "american_odds": -110}
  ]
}
```

```bash
python research/market_context_empirical.py --forecast /path/request.json --arm direct_ref_h2_t3_p0
```

The CLI reconstructs comparable games from the frozen input, emits probabilities,
ESS/backoff/cutoffs and the top 20 comparables, then evaluates supplied offers with
proper cover/push/loss settlement and at most one positive-model-EV offer. It
rejects outcome fields in the request. It makes no network request or file write.
The default source is a frozen historical pack, not a live data pipeline; use an
audited updated input via --input before any prospective experiment. Positive
model-estimated EV is not established real-world EV.

Full protocols/results: [MC1](experiments/R003_market_context/REPORT.md),
[MC2](experiments/R003_market_context_refinement/REPORT.md). Per-game data,
annual choices, all fixed candidates, coverage/width, reliability, paired
uncertainty, influence, hashes and repeat checks accompany those reports.
