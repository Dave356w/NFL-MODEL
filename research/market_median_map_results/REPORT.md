# Test 51: a market-only median map, fitted on 2022–24 and tested on 2025–26

Protocol: [MARKET_MEDIAN_MAP.md](../MARKET_MEDIAN_MAP.md), pushed (`d4c316a`) before the map was fitted or scored. No model input. Production and the ledgers are unchanged. Exposed development (see the protocol).

## Fitted map (2022–24, 815 games)

| Band | Fit games | A | B low total | B high total |
|---|---:|---:|---:|---:|
| <3 | 205 | 3 | 1 (n=105) | 3 (n=100) |
| 3–<7 | 417 | 5 | 4 (n=206) | 5 (n=211) |
| 7–<10 | 112 | 6 | 5 (n=60) | 7 (n=52) |
| 10+ | 81 | 11 | 11 (n=37) | 10.5 (n=44) |

Total split: 43.5 (equal counts as low). * = fallback to A.

## Point forecast: absolute-error gain over the raw market line (points per game; positive = map better)

| Test | Games | MAE line | A: MAE, gain [95%] | B: MAE, gain [95%] |
|---|---:|---:|---|---|
| pooled 2025-26 | 393 | 9.676 | 9.700, −0.024 [−0.189, +0.122] | 9.729, −0.053 [−0.188, +0.060] |
| 2025 | 272 | 9.722 | 9.831, −0.108 [−0.319, +0.065] | 9.809, −0.086 [−0.273, +0.061] |
| 2026 | 121 | 9.570 | 9.405, +0.165 [−0.012, +0.329] | 9.550, +0.021 [−0.134, +0.160] |

Point verdict (pooled): A no detectable difference; B no detectable difference.

## ATS at −110 (W-L-P | units | ROI ± SE | cover | verdict)

**pooled 2025-26** (393 games)

| Arm | Record |
|---|---|
| A, ties take favorite (underdog share 39%) | 203-183-7 | +1.5 | +0.39% ± 4.77 | 52.6% | unresolved |
| A, ties skip | 203-183-7 | +1.5 | +0.39% ± 4.77 | 52.6% | unresolved |
| B, ties take favorite (underdog share 49%) | 204-182-7 | +3.5 | +0.88% ± 4.77 | 52.8% | unresolved |
| B, ties skip | 194-173-5 (21 skips) | +3.4 | +0.90% ± 4.91 | 52.9% | unresolved |
| Always favorite | 187-199-7 | −29.0 | −7.38% ± 4.78 | 48.4% | unresolved |
| Always underdog | 199-187-7 | −6.1 | −1.55% ± 4.78 | 51.6% | unresolved |
| Always home | 187-199-7 | −29.0 | −7.38% ± 4.78 | 48.4% | unresolved |

**2025** (272 games)

| Arm | Record |
|---|---|
| A, ties take favorite (underdog share 43%) | 135-136-1 | −13.3 | −4.88% ± 5.79 | 49.8% | unresolved |
| A, ties skip | 135-136-1 | −13.3 | −4.88% ± 5.79 | 49.8% | unresolved |
| B, ties take favorite (underdog share 52%) | 144-127-1 | +3.9 | +1.44% ± 5.78 | 53.1% | unresolved |
| B, ties skip | 135-121-1 (15 skips) | +1.7 | +0.67% ± 5.95 | 52.7% | unresolved |
| Always favorite | 131-140-1 | −20.9 | −7.69% ± 5.78 | 48.3% | unresolved |
| Always underdog | 140-131-1 | −3.7 | −1.37% ± 5.78 | 51.7% | unresolved |
| Always home | 135-136-1 | −13.3 | −4.88% ± 5.79 | 49.8% | unresolved |

**2026** (121 games)

| Arm | Record |
|---|---|
| A, ties take favorite (underdog share 31%) | 68-47-6 | +14.8 | +12.25% ± 8.36 | 59.1% | unresolved |
| A, ties skip | 68-47-6 | +14.8 | +12.25% ± 8.36 | 59.1% | unresolved |
| B, ties take favorite (underdog share 42%) | 60-55-6 | −0.5 | −0.38% ± 8.49 | 52.2% | unresolved |
| B, ties skip | 59-52-4 (6 skips) | +1.6 | +1.42% ± 8.77 | 53.2% | unresolved |
| Always favorite | 56-59-6 | −8.1 | −6.69% ± 8.49 | 48.7% | unresolved |
| Always underdog | 59-56-6 | −2.4 | −1.95% ± 8.49 | 51.3% | unresolved |
| Always home | 52-63-6 | −15.7 | −13.00% ± 8.46 | 45.2% | unresolved |

## References on the ledger's 393 test games (production tie rule)

| Arm | Record |
|---|---|
| Production median map (model input) | 217-169-7 | +28.3 | +7.19% ± 4.74 | 56.2% | unresolved |
| Line through production map (ledger control) | 207-179-7 | +9.2 | +2.34% ± 4.77 | 53.6% | unresolved |
| A, market-only | 203-183-7 | +1.5 | +0.39% ± 4.77 | 52.6% | unresolved |
| B, market-only | 204-182-7 | +3.5 | +0.88% ± 4.77 | 52.8% | unresolved |
| Production median map (model input) minus A | +26.7u, +0.0680 ± 0.0548 per game; sides differ on 125 |
| Line through production map (ledger control) minus A | +7.6u, +0.0194 ± 0.0457 per game; sides differ on 57 |

## By band and total half, pooled 2025–26 (descriptive; production tie rule)

| Band | Total | Games | A | B | Always favorite |
|---|---|---:|---|---|---|
| <3 | low | 48 | 25-23-0 -0.3u | 23-25-0 -4.1u | 25-23-0 |
| <3 | high | 51 | 27-24-0 +0.5u | 27-24-0 +0.5u | 27-24-0 |
| 3–<7 | low | 72 | 36-35-1 -2.3u | 40-31-1 +5.4u | 34-37-1 |
| 3–<7 | high | 111 | 51-57-3 -10.6u | 51-57-3 -10.6u | 55-53-3 |
| 7–<10 | low | 30 | 20-9-1 +9.2u | 20-9-1 +9.2u | 9-20-1 |
| 7–<10 | high | 39 | 24-13-2 +8.8u | 23-14-2 +6.9u | 13-24-2 |
| 10+ | low | 19 | 8-11-0 -3.7u | 8-11-0 -3.7u | 10-9-0 |
| 10+ | high | 23 | 12-11-0 -0.1u | 12-11-0 -0.1u | 14-9-0 |
