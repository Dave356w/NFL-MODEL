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
| Pooled completed selections | 58–42–6 | 106 | +10.561626 | +9.963798% |
| Exact-handicap closing estimates | 49–33–4 | 86 | +11.379808 | +13.232335% |
| Assumed −110 selections | 9–9–2 | 20 | −0.818182 | −4.090909% |
| Verified historical pre-lock prices | 0–0–0 | 0 | — | — |

The main total pools 86 exact-handicap ESPN closing estimates with 20 explicit
−110 assumptions (owner decision 2026-10-26). It is an estimate, not verified
lock-time profit for all 106 picks. On the same 86 games, the old flat −110 reference is +11.545455u
(13.424947% ROI). The full 106-game −110 reference is +10.727273u (10.119940% ROI).

The 86 matched closing prices have a median of −112 and a mean payout of
0.902579u per winning 1u stake, equivalent to −110.793645. A −110 assumption
pays 0.909091u, so it is slightly generous relative to that average. Applying
the observed average payout to the 20 missing-price picks instead gives
+10.503018u and 9.908507% ROI. This is a sensitivity estimate, not evidence of
the missing picks' actual prices.

| Week | Full W–L–P | ESPN / assumed −110 | Pooled units | Pooled ROI |
| --- | --- | --- | ---: | ---: |
| 1 | 10–5–1 | 15 / 1 | +4.07 | +25.44% |
| 2 | 11–5–0 | 14 / 2 | +4.86 | +30.35% |
| 3 | 9–5–2 | 14 / 2 | +3.15 | +19.67% |
| 4 | 6–8–2 | 12 / 4 | -2.66 | -16.63% |
| 5 | 7–7–1 | 10 / 5 | -0.54 | -3.63% |
| 6 | 7–7–0 | 9 / 5 | -0.70 | -4.98% |
| 7 | 8–5–0 | 12 / 1 | +2.39 | +18.40% |

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
4. A reporting-only −110 assumption, explicitly labelled `assumed_minus110`,
   when no exact quote matches. The original match failure is retained as
   `ats_match_status`. No moneyline or different-handicap quote is substituted.

A known line move prevents resurrecting an older matching quote from that book.
The CSV retains quote age for recovered pre-lock quotes. Historical replay rows
without an original lock timestamp cannot be assigned an invented T−60 lock.

Each priced bet risks 1u: winning −120 returns 100/120u, winning +105 returns
1.05u, a loss costs 1u and a push returns the stake. ROI divides net profit by
all completed W/L/P stakes, including those with assumed −110 prices and pushes.
Matched prices always take precedence over assumptions. The strict matched-only
calculation remains available to research callers; assumptions never enter the
immutable quote archive or candidate hashes.
The chart, weekly table, cards, baselines and CSVs share these calculations.
Baselines use their own same-game matched subset, requiring ESPN prices for
both sides of the same line; their compared-game count is displayed.

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
