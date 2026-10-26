# ESPN spread pricing

The public season report now prices the saved ATS side at its saved handicap.
The model probabilities, mapped spreads, selected sides and original forecast
archives are unchanged. ESPN final scores update outcomes only.

## Backfill at 2026-10-26

- 106 completed 2026 regular-season games retrieved; all have ESPN odds evidence.
- One upcoming game also captured. Preseason and 2025-season January games excluded.
- Every available provider's movement endpoint was checked, including pagination.
  ESPN returned **zero movement items**. No historical lock-time price was recovered.
- 86 completed selections have an exact-handicap closing-price match; 20 do not.
  A closing price at another handicap is never borrowed.

| Cohort | W–L–P | Stakes | Units | ROI |
| --- | --- | ---: | ---: | ---: |
| All completed selections | 58–42–6 | 106 | — | — |
| Exact-handicap closing estimates | 49–33–4 | 86 | +11.379808 | +13.232335% |
| Unpriced selections | 9–9–2 | 20 | — | — |
| Verified historical pre-lock prices | 0–0–0 | 0 | — | — |

These are estimated returns on a priced subset, not verified lock-time profit
for all 106 picks. On the same 86 games, the old flat −110 reference is +11.545455u
(13.424947% ROI). The full 106-game −110 reference is +10.727273u (10.119940% ROI).

| Week | Full W–L–P | Priced / completed | Estimated units | Estimated ROI |
| --- | --- | --- | ---: | ---: |
| 1 | 10–5–1 | 15 / 16 | +3.16 | +21.07% |
| 2 | 11–5–0 | 14 / 16 | +3.04 | +21.70% |
| 3 | 9–5–2 | 14 / 16 | +5.15 | +36.76% |
| 4 | 6–8–2 | 12 / 16 | -5.39 | -44.90% |
| 5 | 7–7–1 | 10 / 15 | +3.46 | +34.56% |
| 6 | 7–7–0 | 9 / 14 | +0.48 | +5.38% |
| 7 | 8–5–0 | 12 / 13 | +1.48 | +12.35% |

## Evidence and matching

`data/espn_spreads.jsonl` is append-only. Each record retains the event ID,
normalized NFL game identity, final scores or pending status, retrieval time,
raw odds pages, movement pages or request errors, source URLs and a SHA-256
digest. Successful completed backfills are reused; request failures are retried.
Team aliases include ESPN LAR → nflverse LA and WSH → WAS.

Pricing priority:

1. The exact pre-lock ESPN quote embedded in an immutable saved candidate.
2. The latest eligible timestamped movement or locally received pre-lock current
   quote per provider, when its selected-side handicap matches the saved pick.
3. An exact-handicap final close, explicitly labelled `closing_estimate`.
4. Unpriced. No −110 substitute, moneyline substitute, or unmatched-line price.

A known line move prevents resurrecting an older matching quote from that book.
The CSV retains quote age for recovered pre-lock quotes. Historical replay rows
without an original lock timestamp cannot be assigned an invented T−60 lock.

Each priced bet risks 1u: winning −120 returns 100/120u, winning +105 returns
1.05u, a loss costs 1u and a push returns the stake. ROI divides net profit by
the number of **priced** W/L/P stakes. Unpriced wins, losses and pushes all stay
in the full ATS record and all stay out of priced profit and its denominator.
The chart, weekly table, cards, baselines and CSVs share these calculations.
Baselines additionally require valid prices for both sides of the same line.

## Future locks

Full builds refresh ESPN before the model and again before candidate capture.
The latter capture supplies a recent independently received price. Each new
candidate embeds its matching quote and evidence digest **before** its own
candidate hash is calculated. Finalization copies the saved candidate, including
its prices. The hold/recovery path never fetches a post-cutoff quote into a lock.
If ESPN is unavailable or the handicap differs, the candidate records
`no_matching_prelock_price`; forecasts still save and later reports show any
closing estimate honestly. Scheduling and provider availability cannot guarantee
a matching pre-lock price for every game.

## Reproduce

```sh
python espn_spreads.py --season 2026
python build_site.py --pages-only
python validate_data_files.py
python -m pytest tests/ -q
```

`data/latest/ats_pricing_results.csv` retains per-pick provenance, timestamps,
prices, priced stakes, cumulative returns and the −110 comparison. Public
downloads expose spread prices and pricing basis without model probabilities.
The unchanged raw forecast archives remain authoritative for original decisions.
