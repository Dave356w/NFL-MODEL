# Test 60: model band versus the line's own band through the same median map

Protocol: [MAP_VS_LINE.md](../MAP_VS_LINE.md), committed (`b91ca42`) before the line-only arm was scored before 2023. Flat 1u at -110; break-even cover 52.4%; ROI SE has pushes in the denominator. Both bases exposed; diagnostic only.

Reproduction of v1.19: v1.19 retro_ledger 2021-25 2.2e-16, Test 50 S3 2014-20 (6-digit CSV) 5.0e-07.
Checks: annual map vs harness 0.0e+00; discovery map vs ledger 0.0e+00; discovery D model - D line-only +55.36u on 139 of 952 (reproduced: True); Test 59 rows 2017-22 D model 785-740-41 (Test 59: 785-740-41), A model 741-784-41 (Test 59: 741-784-41).

**Primary (test 2016-22): D model - D line-only = +43.7u ± 31.4 (z +1.39, n 1822, sides differ on 289, model record there 149-125-15) -> unresolved.**

## Paired contrasts

| Basis | Period | Contrast | Games | Sides differ | First arm on differing | Units | z |
|---|---|---|---:|---:|---|---:|---:|
| test | 2016-2022 | D model - D line-only | 1822 | 289 | 149-125-15 | +43.7 ± 31.4 | +1.39 |
| test | 2016-2022 | A model - A line-only | 1822 | 269 | 136-119-14 | +30.4 ± 30.3 | +1.00 |
| test | 2016-2022 | D model - R raw | 1822 | 714 | 366-335-13 | +59.2 ± 50.5 | +1.17 |
| test | 2016-2022 | D model - A model | 1822 | 347 | 191-151-5 | +76.4 ± 35.3 | +2.17 |
| test | 2016 | D model - D line-only | 256 | 33 | 16-14-3 | +4.7 ± 10.3 | +0.46 |
| test | 2016 | A model - A line-only | 256 | 48 | 26-18-4 | +16.2 ± 12.5 | +1.29 |
| test | 2016 | D model - R raw | 256 | 129 | 70-58-1 | +22.9 ± 21.6 | +1.06 |
| test | 2016 | D model - A model | 256 | 51 | 23-27-1 | -7.6 ± 13.5 | -0.56 |
| test | 2017 | D model - D line-only | 255 | 29 | 16-13-0 | +2.7 ± 9.9 | +0.28 |
| test | 2017 | A model - A line-only | 255 | 26 | 16-10-0 | +8.5 ± 9.3 | +0.91 |
| test | 2017 | D model - R raw | 255 | 119 | 56-58-5 | -3.8 ± 20.4 | -0.19 |
| test | 2017 | D model - A model | 255 | 43 | 22-21-0 | +1.9 ± 12.5 | +0.15 |
| test | 2018 | D model - D line-only | 256 | 30 | 14-15-1 | -1.9 ± 10.3 | -0.19 |
| test | 2018 | A model - A line-only | 256 | 31 | 14-16-1 | -3.8 ± 10.5 | -0.36 |
| test | 2018 | D model - R raw | 256 | 101 | 46-54-1 | -15.3 ± 19.1 | -0.80 |
| test | 2018 | D model - A model | 256 | 28 | 14-14-0 | +0.0 ± 10.1 | +0.00 |
| test | 2019 | D model - D line-only | 256 | 34 | 13-16-5 | -5.7 ± 10.3 | -0.56 |
| test | 2019 | A model - A line-only | 256 | 24 | 10-11-3 | -1.9 ± 8.8 | -0.22 |
| test | 2019 | D model - R raw | 256 | 102 | 53-45-4 | +15.3 ± 18.9 | +0.81 |
| test | 2019 | D model - A model | 256 | 41 | 23-16-2 | +13.4 ± 11.9 | +1.12 |
| test | 2020 | D model - D line-only | 256 | 47 | 28-19-0 | +17.2 ± 13.1 | +1.31 |
| test | 2020 | A model - A line-only | 256 | 31 | 17-14-0 | +5.7 ± 10.6 | +0.54 |
| test | 2020 | D model - R raw | 256 | 86 | 46-40-0 | +11.5 ± 17.7 | +0.65 |
| test | 2020 | D model - A model | 256 | 64 | 35-29-0 | +11.5 ± 15.3 | +0.75 |
| test | 2021 | D model - D line-only | 272 | 59 | 36-22-1 | +26.7 ± 14.5 | +1.85 |
| test | 2021 | A model - A line-only | 272 | 51 | 23-27-1 | -7.6 ± 13.5 | -0.56 |
| test | 2021 | D model - R raw | 272 | 89 | 50-37-2 | +24.8 ± 17.8 | +1.40 |
| test | 2021 | D model - A model | 272 | 98 | 61-35-2 | +49.6 ± 18.5 | +2.68 |
| test | 2022 | D model - D line-only | 271 | 57 | 26-26-5 | +0.0 ± 13.8 | +0.00 |
| test | 2022 | A model - A line-only | 271 | 58 | 30-23-5 | +13.4 ± 13.9 | +0.96 |
| test | 2022 | D model - R raw | 271 | 88 | 45-43-0 | +3.8 ± 17.9 | +0.21 |
| test | 2022 | D model - A model | 271 | 22 | 13-9-0 | +7.6 ± 9.0 | +0.85 |
| discovery | 2023-2026 | D model - D line-only | 952 | 139 | 83-54-2 | +55.4 ± 22.3 | +2.48 |
| discovery | 2023-2026 | A model - A line-only | 952 | 172 | 92-75-5 | +32.5 ± 24.7 | +1.32 |
| discovery | 2023-2026 | D model - R raw | 952 | 435 | 248-181-6 | +127.9 ± 39.3 | +3.25 |
| discovery | 2023-2026 | D model - A model | 952 | 201 | 113-84-4 | +55.4 ± 26.7 | +2.07 |
| discovery | 2023 | D model - D line-only | 272 | 37 | 21-14-2 | +13.4 ± 11.3 | +1.18 |
| discovery | 2023 | A model - A line-only | 272 | 50 | 23-23-4 | -0.0 ± 13.0 | -0.00 |
| discovery | 2023 | D model - R raw | 272 | 125 | 73-50-2 | +43.9 ± 21.0 | +2.09 |
| discovery | 2023 | D model - A model | 272 | 69 | 37-29-3 | +15.3 ± 15.5 | +0.98 |
| discovery | 2024 | D model - D line-only | 272 | 36 | 23-13-0 | +19.1 ± 11.4 | +1.67 |
| discovery | 2024 | A model - A line-only | 272 | 51 | 26-24-1 | +3.8 ± 13.5 | +0.28 |
| discovery | 2024 | D model - R raw | 272 | 140 | 85-53-2 | +61.1 ± 22.2 | +2.76 |
| discovery | 2024 | D model - A model | 272 | 109 | 65-43-1 | +42.0 ± 19.7 | +2.13 |
| discovery | 2025 | D model - D line-only | 272 | 44 | 25-19-0 | +11.5 ± 12.7 | +0.90 |
| discovery | 2025 | A model - A line-only | 272 | 48 | 28-20-0 | +15.3 ± 13.2 | +1.16 |
| discovery | 2025 | D model - R raw | 272 | 105 | 55-49-1 | +11.5 ± 19.5 | +0.59 |
| discovery | 2025 | D model - A model | 272 | 18 | 9-9-0 | +0.0 ± 8.1 | +0.00 |
| discovery | 2026 | D model - D line-only | 136 | 22 | 14-8-0 | +11.5 ± 8.9 | +1.28 |
| discovery | 2026 | A model - A line-only | 136 | 23 | 15-8-0 | +13.4 ± 9.1 | +1.47 |
| discovery | 2026 | D model - R raw | 136 | 65 | 35-29-1 | +11.5 ± 15.3 | +0.75 |
| discovery | 2026 | D model - A model | 136 | 5 | 2-3-0 | -1.9 ± 4.3 | -0.45 |

## Records

| Basis | Period | Arm | W-L-P | Skips | Units | ROI ± SE | Cover |
|---|---|---|---|---:|---:|---:|---:|
| test | 2016-2022 | D model | 920-856-46 | 0 | -19.6 | -1.1% ± 2.2 | 51.8% |
| test | 2016-2022 | D line-only | 895-877-46 | 4 | -63.4 | -3.5% ± 2.2 | 50.5% |
| test | 2016-2022 | A model | 880-896-46 | 0 | -96.0 | -5.3% ± 2.2 | 49.5% |
| test | 2016-2022 | A line-only | 862-910-46 | 4 | -126.4 | -7.0% ± 2.2 | 48.6% |
| test | 2016-2022 | R raw | 889-887-46 | 0 | -78.8 | -4.3% ± 2.2 | 50.1% |
| test | 2016-2022 | always favorite | 843-929-46 | 4 | -162.6 | -8.9% ± 2.2 | 47.6% |
| test | 2016-2022 | always home | 862-914-46 | 0 | -130.4 | -7.2% ± 2.2 | 48.5% |
| test | 2016 | D model | 135-116-5 | 0 | +6.7 | +2.6% ± 5.9 | 53.8% |
| test | 2016 | D line-only | 132-118-5 | 1 | +2.0 | +0.8% ± 5.9 | 52.8% |
| test | 2016 | A model | 139-112-5 | 0 | +14.4 | +5.6% ± 5.9 | 55.4% |
| test | 2016 | A line-only | 130-120-5 | 1 | -1.8 | -0.7% ± 5.9 | 52.0% |
| test | 2016 | R raw | 123-128-5 | 0 | -16.2 | -6.3% ± 5.9 | 49.0% |
| test | 2016 | always favorite | 128-122-5 | 1 | -5.6 | -2.2% ± 5.9 | 51.2% |
| test | 2016 | always home | 123-128-5 | 0 | -16.2 | -6.3% ± 5.9 | 49.0% |
| test | 2017 | D model | 132-115-8 | 0 | +5.0 | +2.0% ± 5.9 | 53.4% |
| test | 2017 | D line-only | 129-115-8 | 3 | +2.3 | +0.9% ± 5.9 | 52.9% |
| test | 2017 | A model | 131-116-8 | 0 | +3.1 | +1.2% ± 5.9 | 53.0% |
| test | 2017 | A line-only | 125-119-8 | 3 | -5.4 | -2.1% ± 5.9 | 51.2% |
| test | 2017 | R raw | 134-113-8 | 0 | +8.8 | +3.5% ± 5.9 | 54.3% |
| test | 2017 | always favorite | 131-113-8 | 3 | +6.1 | +2.4% ± 5.9 | 53.7% |
| test | 2017 | always home | 129-118-8 | 0 | -0.7 | -0.3% ± 5.9 | 52.2% |
| test | 2018 | D model | 114-133-9 | 0 | -29.4 | -11.5% ± 5.9 | 46.2% |
| test | 2018 | D line-only | 115-132-9 | 0 | -27.5 | -10.7% ± 5.9 | 46.6% |
| test | 2018 | A model | 114-133-9 | 0 | -29.4 | -11.5% ± 5.9 | 46.2% |
| test | 2018 | A line-only | 116-131-9 | 0 | -25.5 | -10.0% ± 5.9 | 47.0% |
| test | 2018 | R raw | 122-125-9 | 0 | -14.1 | -5.5% ± 5.9 | 49.4% |
| test | 2018 | always favorite | 114-133-9 | 0 | -29.4 | -11.5% ± 5.9 | 46.2% |
| test | 2018 | always home | 119-128-9 | 0 | -19.8 | -7.7% ± 5.9 | 48.2% |
| test | 2019 | D model | 122-124-10 | 0 | -13.1 | -5.1% ± 5.9 | 49.6% |
| test | 2019 | D line-only | 125-121-10 | 0 | -7.4 | -2.9% ± 5.9 | 50.8% |
| test | 2019 | A model | 115-131-10 | 0 | -26.5 | -10.3% ± 5.8 | 46.7% |
| test | 2019 | A line-only | 116-130-10 | 0 | -24.5 | -9.6% ± 5.9 | 47.2% |
| test | 2019 | R raw | 114-132-10 | 0 | -28.4 | -11.1% ± 5.8 | 46.3% |
| test | 2019 | always favorite | 113-133-10 | 0 | -30.3 | -11.8% ± 5.8 | 45.9% |
| test | 2019 | always home | 106-140-10 | 0 | -43.6 | -17.0% ± 5.8 | 43.1% |
| test | 2020 | D model | 131-125-0 | 0 | -5.9 | -2.3% ± 6.0 | 51.2% |
| test | 2020 | D line-only | 122-134-0 | 0 | -23.1 | -9.0% ± 6.0 | 47.7% |
| test | 2020 | A model | 125-131-0 | 0 | -17.4 | -6.8% ± 6.0 | 48.8% |
| test | 2020 | A line-only | 122-134-0 | 0 | -23.1 | -9.0% ± 6.0 | 47.7% |
| test | 2020 | R raw | 125-131-0 | 0 | -17.4 | -6.8% ± 6.0 | 48.8% |
| test | 2020 | always favorite | 114-142-0 | 0 | -38.4 | -15.0% ± 5.9 | 44.5% |
| test | 2020 | always home | 127-129-0 | 0 | -13.5 | -5.3% ± 6.0 | 49.6% |
| test | 2021 | D model | 150-118-4 | 0 | +18.4 | +6.8% ± 5.7 | 56.0% |
| test | 2021 | D line-only | 136-132-4 | 0 | -8.4 | -3.1% ± 5.8 | 50.7% |
| test | 2021 | A model | 124-144-4 | 0 | -31.3 | -11.5% ± 5.7 | 46.3% |
| test | 2021 | A line-only | 128-140-4 | 0 | -23.6 | -8.7% ± 5.8 | 47.8% |
| test | 2021 | R raw | 137-131-4 | 0 | -6.5 | -2.4% ± 5.8 | 51.1% |
| test | 2021 | always favorite | 125-143-4 | 0 | -29.4 | -10.8% ± 5.7 | 46.6% |
| test | 2021 | always home | 129-139-4 | 0 | -21.7 | -8.0% ± 5.8 | 48.1% |
| test | 2022 | D model | 136-125-10 | 0 | -1.4 | -0.5% ± 5.7 | 52.1% |
| test | 2022 | D line-only | 136-125-10 | 0 | -1.4 | -0.5% ± 5.7 | 52.1% |
| test | 2022 | A model | 132-129-10 | 0 | -9.0 | -3.3% ± 5.7 | 50.6% |
| test | 2022 | A line-only | 125-136-10 | 0 | -22.4 | -8.3% ± 5.7 | 47.9% |
| test | 2022 | R raw | 134-127-10 | 0 | -5.2 | -1.9% ± 5.7 | 51.3% |
| test | 2022 | always favorite | 118-143-10 | 0 | -35.7 | -13.2% ± 5.7 | 45.2% |
| test | 2022 | always home | 129-132-10 | 0 | -14.7 | -5.4% ± 5.7 | 49.4% |
| discovery | 2023-2026 | D model | 532-395-25 | 0 | +88.6 | +9.3% ± 3.0 | 57.4% |
| discovery | 2023-2026 | D line-only | 503-424-25 | 0 | +33.3 | +3.5% ± 3.0 | 54.3% |
| discovery | 2023-2026 | A model | 503-424-25 | 0 | +33.3 | +3.5% ± 3.0 | 54.3% |
| discovery | 2023-2026 | A line-only | 486-441-25 | 0 | +0.8 | +0.1% ± 3.1 | 52.4% |
| discovery | 2023-2026 | R raw | 465-462-25 | 0 | -39.3 | -4.1% ± 3.1 | 50.2% |
| discovery | 2023-2026 | always favorite | 478-449-25 | 0 | -14.5 | -1.5% ± 3.1 | 51.6% |
| discovery | 2023-2026 | always home | 456-471-25 | 0 | -56.5 | -5.9% ± 3.1 | 49.2% |
| discovery | 2023 | D model | 141-117-14 | 0 | +11.2 | +4.1% ± 5.6 | 54.7% |
| discovery | 2023 | D line-only | 134-124-14 | 0 | -2.2 | -0.8% ± 5.6 | 51.9% |
| discovery | 2023 | A model | 133-125-14 | 0 | -4.1 | -1.5% ± 5.6 | 51.6% |
| discovery | 2023 | A line-only | 133-125-14 | 0 | -4.1 | -1.5% ± 5.6 | 51.6% |
| discovery | 2023 | R raw | 118-140-14 | 0 | -32.7 | -12.0% ± 5.6 | 45.7% |
| discovery | 2023 | always favorite | 137-121-14 | 0 | +3.5 | +1.3% ± 5.6 | 53.1% |
| discovery | 2023 | always home | 128-130-14 | 0 | -13.6 | -5.0% ± 5.6 | 49.6% |
| discovery | 2024 | D model | 165-103-4 | 0 | +47.0 | +17.3% ± 5.6 | 61.6% |
| discovery | 2024 | D line-only | 155-113-4 | 0 | +27.9 | +10.3% ± 5.7 | 57.8% |
| discovery | 2024 | A model | 143-125-4 | 0 | +5.0 | +1.8% ± 5.7 | 53.4% |
| discovery | 2024 | A line-only | 141-127-4 | 0 | +1.2 | +0.4% ± 5.7 | 52.6% |
| discovery | 2024 | R raw | 133-135-4 | 0 | -14.1 | -5.2% ± 5.8 | 49.6% |
| discovery | 2024 | always favorite | 143-125-4 | 0 | +5.0 | +1.8% ± 5.7 | 53.4% |
| discovery | 2024 | always home | 137-131-4 | 0 | -6.5 | -2.4% ± 5.8 | 51.1% |
| discovery | 2025 | D model | 151-120-1 | 0 | +17.3 | +6.4% ± 5.7 | 55.7% |
| discovery | 2025 | D line-only | 145-126-1 | 0 | +5.8 | +2.1% ± 5.8 | 53.5% |
| discovery | 2025 | A model | 151-120-1 | 0 | +17.3 | +6.4% ± 5.7 | 55.7% |
| discovery | 2025 | A line-only | 143-128-1 | 0 | +2.0 | +0.7% ± 5.8 | 52.8% |
| discovery | 2025 | R raw | 145-126-1 | 0 | +5.8 | +2.1% ± 5.8 | 53.5% |
| discovery | 2025 | always favorite | 131-140-1 | 0 | -20.9 | -7.7% ± 5.8 | 48.3% |
| discovery | 2025 | always home | 135-136-1 | 0 | -13.3 | -4.9% ± 5.8 | 49.8% |
| discovery | 2026 | D model | 75-55-6 | 0 | +13.2 | +9.7% ± 7.9 | 57.7% |
| discovery | 2026 | D line-only | 69-61-6 | 0 | +1.7 | +1.3% ± 8.0 | 53.1% |
| discovery | 2026 | A model | 76-54-6 | 0 | +15.1 | +11.1% ± 7.9 | 58.5% |
| discovery | 2026 | A line-only | 69-61-6 | 0 | +1.7 | +1.3% ± 8.0 | 53.1% |
| discovery | 2026 | R raw | 69-61-6 | 0 | +1.7 | +1.3% ± 8.0 | 53.1% |
| discovery | 2026 | always favorite | 67-63-6 | 0 | -2.1 | -1.5% ± 8.0 | 51.5% |
| discovery | 2026 | always home | 56-74-6 | 0 | -23.1 | -17.0% ± 8.0 | 43.1% |
| test | 2017-2022 (Test 59 rows) | D model | 785-740-41 | 0 | -26.4 | -1.7% ± 2.4 | 51.5% |
| test | 2017-2022 (Test 59 rows) | D line-only | 763-759-41 | 3 | -65.4 | -4.2% ± 2.4 | 50.1% |
| test | 2017-2022 (Test 59 rows) | A model | 741-784-41 | 0 | -110.4 | -7.0% ± 2.4 | 48.6% |
| test | 2017-2022 (Test 59 rows) | A line-only | 732-790-41 | 3 | -124.5 | -8.0% ± 2.4 | 48.1% |
| test | 2017-2022 (Test 59 rows) | R raw | 766-759-41 | 0 | -62.6 | -4.0% ± 2.4 | 50.2% |
| test | 2017-2022 (Test 59 rows) | always favorite | 715-807-41 | 3 | -157.0 | -10.0% ± 2.4 | 47.0% |
| test | 2017-2022 (Test 59 rows) | always home | 739-786-41 | 0 | -114.2 | -7.3% ± 2.4 | 48.5% |
