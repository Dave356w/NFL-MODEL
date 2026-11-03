# Test 50: a total-conditioned median map

Protocol: [TOTAL_MEDIAN_MAP.md](../TOTAL_MEDIAN_MAP.md), pushed (`ecb6168`) before any total-conditioned magnitude was fitted or scored. Production v1.18, the median map, the lock policy and the ledgers are unchanged. Development evidence on exposed seasons.

Fidelity: the production map reproduces the published `fixed_band_spread` on 937 replay rows and the published 2023-on replay record 495-417-25 | +33.0u | +3.52% ± 3.07 | 54.3% (937 games).

**Verdict (T2): not supported.**

## Primary: absolute-error gain of the mapped spread (production minus arm, points per game; positive = arm better)

| Basis | Games | MAE production | MAE T2 | T2 gain [95%] | MAE T3 | T3 gain [95%] (descriptive) | MAE line-only map |
|---|---:|---:|---:|---|---:|---|---:|
| R 2023-25 | 816 | 9.765 | 9.824 | −0.058 [−0.118, +0.009] | 9.862 | −0.097 [−0.195, +0.006] | 9.820 |
| O 2019-20 | 512 | 10.213 | 10.383 | −0.170 [−0.305, −0.038] | 10.414 | −0.201 [−0.334, −0.055] | 10.201 |
| R 2026 (diagnostic) | 121 | 9.579 | 9.603 | −0.025 [−0.101, +0.049] | 9.607 | −0.029 [−0.187, +0.119] | 9.521 |

## Goal metric, reported only: flat 1u ATS at −110 (W-L-P | units | ROI ± SE | cover)

**R 2023-25**

| Arm | Record |
|---|---|
| Production map | 430-367-19 | +23.9u | +2.93% ± 3.29 | 54.0% |
| T2 (primary) | 424-373-19 | +12.5u | +1.53% ± 3.30 | 53.2% |
| T3 (descriptive) | 421-376-19 | +6.7u | +0.82% ± 3.30 | 52.8% |
| Line-only map | 415-382-19 | −4.7u | −0.58% ± 3.30 | 52.1% |
| Always favorite | 411-386-19 | −12.4u | −1.52% ± 3.30 | 51.6% |
| Always home | 400-397-19 | −33.4u | −4.09% ± 3.30 | 50.2% |
| T2 minus production | −11.5u, −0.0140 ± 0.0288 per game; 153 flips: T2 72-78-3, production 78-72-3 |
| T3 minus production | −17.2u, −0.0211 ± 0.0270 per game; 168 flips: T3 79-88-1, production 88-79-1 |

**O 2019-20**

| Arm | Record |
|---|---|
| Production map | 246-256-10 | −32.4u | −6.32% ± 4.18 | 49.0% |
| T2 (primary) | 240-262-10 | −43.8u | −8.56% ± 4.18 | 47.8% |
| T3 (descriptive) | 246-256-10 | −32.4u | −6.32% ± 4.18 | 49.0% |
| Line-only map | 242-260-10 | −40.0u | −7.81% ± 4.18 | 48.2% |
| Always favorite | 227-275-10 | −68.6u | −13.41% ± 4.16 | 45.2% |
| Always home | 233-269-10 | −57.2u | −11.17% ± 4.17 | 46.4% |
| T2 minus production | −11.5u, −0.0224 ± 0.0360 per game; 119 flips: T2 56-62-1, production 62-56-1 |
| T3 minus production | +0.0u, +0.0000 ± 0.0399 per game; 94 flips: T3 47-47-0, production 47-47-0 |

**R 2026 (diagnostic)**

| Arm | Record |
|---|---|
| Production map | 65-50-6 | +9.1u | +7.51% ± 8.42 | 56.5% |
| T2 (primary) | 63-52-6 | +5.3u | +4.36% ± 8.46 | 54.8% |
| T3 (descriptive) | 64-51-6 | +7.2u | +5.94% ± 8.44 | 55.7% |
| Line-only map | 62-53-6 | +3.4u | +2.78% ± 8.47 | 53.9% |
| Always favorite | 56-59-6 | −8.1u | −6.69% ± 8.49 | 48.7% |
| Always home | 52-63-6 | −15.7u | −13.00% ± 8.46 | 45.2% |
| T2 minus production | −3.8u, −0.0316 ± 0.0614 per game; 34 flips: T2 15-17-2, production 17-15-2 |
| T3 minus production | −1.9u, −0.0158 ± 0.0569 per game; 28 flips: T3 12-13-3, production 13-12-3 |

## By the T2 rule's total half (descriptive)

| Basis | Half | Games | T2 abs-error gain | Production ATS | T2 ATS |
|---|---|---:|---:|---|---|
| R 2023-25 | low | 489 | −0.112 | 262-215-12 | +23.2u | +4.74% ± 4.25 | 54.9% | 245-232-12 | −9.3u | −1.90% ± 4.27 | 51.4% |
| R 2023-25 | high | 327 | +0.023 | 168-152-7 | +0.7u | +0.22% ± 5.22 | 52.5% | 179-141-7 | +21.7u | +6.64% ± 5.19 | 55.9% |
| O 2019-20 | low | 200 | −0.070 | 90-105-5 | −23.2u | −11.59% ± 6.66 | 46.2% | 90-105-5 | −23.2u | −11.59% ± 6.66 | 46.2% |
| O 2019-20 | high | 312 | −0.234 | 156-151-5 | −9.2u | −2.94% ± 5.37 | 50.8% | 150-157-5 | −20.6u | −6.61% ± 5.37 | 48.9% |
| R 2026 (diagnostic) | low | 65 | −0.077 | 36-25-4 | +7.7u | +11.89% ± 11.38 | 59.0% | 36-25-4 | +7.7u | +11.89% ± 11.38 | 59.0% |
| R 2026 (diagnostic) | high | 56 | +0.036 | 29-25-2 | +1.4u | +2.44% ± 12.60 | 53.7% | 27-27-2 | −2.5u | −4.38% ± 12.64 | 50.0% |

## Fitted magnitudes (bands <3, 3–<7, 7–<10, 10+; low / high total; * = fallback to production)

| Basis | Season | Split total | Production | T2 low | T2 high |
|---|---:|---:|---|---|---|
| R | 2023 | 45 | 2 / 3 / 6.5 / 14.5 | -1 / 4 / 9 / 14.5* | 3 / 3 / 6 / 14 |
| R | 2024 | 44.5 | 3 / 3 / 7 / 14 | 1 / 3 / 7 / 13.5 | 4 / 3 / 7 / 14 |
| R | 2025 | 44.5 | 3 / 4 / 6.5 / 14 | 2 / 4 / 7 / 14 | 3 / 5 / 6 / 14.5 |
| R | 2026 | 44.5 | 3 / 4 / 7 / 14 | 2 / 3 / 7 / 13 | 3 / 5 / 6 / 14 |
| O | 2019 | 45 | 3 / 4 / 7 / 10 | 3 / 3 / 8 / 12 | 4.5 / 6.5 / 3 / 7 |
| O | 2020 | 45 | 3 / 4 / 7 / 10 | 2 / 3 / 8 / 13 | 4 / 5 / 5 / 7 |
