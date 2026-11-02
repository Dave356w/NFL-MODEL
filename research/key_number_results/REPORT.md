# Key-number-aware conversion: results

Research only. Distribution for season Y is fit on nflverse games with seasons < Y (from 1999). Triangular kernel on |line|, bandwidth 1.0 widened by 0.5 until effective n >= 300.


## 0. Conversion check (fit on 1999-2025)

|   line |   win_prob |   P(fav margin > line | no push) |   probit win_prob |
|-------:|-----------:|---------------------------------:|------------------:|
|    1   |      0.515 |                            0.507 |             0.532 |
|    2.5 |      0.559 |                            0.503 |             0.58  |
|    3   |      0.584 |                            0.484 |             0.596 |
|    3.5 |      0.617 |                            0.475 |             0.611 |
|    6.5 |      0.723 |                            0.49  |             0.7   |
|    7   |      0.751 |                            0.49  |             0.714 |
|    7.5 |      0.757 |                            0.479 |             0.728 |
|   10   |      0.813 |                            0.463 |             0.791 |
|   14   |      0.869 |                            0.461 |             0.871 |

## 2017-20 OOS (v1.16)  (n=1023)

### 1. Market q converted to a spread, minus the posted line (toward favorite, pts)

| lb      |   n |   probit gap |   empirical gap |
|:--------|----:|-------------:|----------------:|
| <=2.5   | 218 |        -0.46 |           -0.18 |
| 3       | 142 |         0.07 |            0.21 |
| 3.5-6.5 | 345 |         0.58 |            0.04 |
| 7       |  67 |         0.67 |           -0.24 |
| 7.5-10  | 136 |         0.48 |           -0.04 |
| 10+     | 115 |        -0.54 |            0.45 |
- probit: MAE 0.58 pts; share >= 1 pt 13%; >= 2 pt 1%
- empirical: MAE 0.49 pts; share >= 1 pt 13%; >= 2 pt 2%
- win prob at the posted line vs no-vig q, MAE: empirical 0.013; probit 0.016

### 2. Home-cover LPM, week-clustered SE (probability space)

- market (c_q - .5): +0.17 ± 0.50 (t +0.3)
- model departure (c_m - c_q): +0.05 ± 0.24 (t +0.2)
- both: +0.21 ± 0.52 (t +0.4), +0.07 ± 0.25 (t +0.3)

### 3. Pick agreement

- probit raw picks identical to q-only picks: 69%
- empirical raw picks identical to q-only picks: 61%
- empirical raw picks identical to probit raw picks: 76%

### 4. Records (flat 1u at -110, pushes excluded from cover %)

| rule                              |   W |   L |   cover |    roi |   roi_se |
|:----------------------------------|----:|----:|--------:|-------:|---------:|
| probit raw edge                   | 484 | 512 |   0.486 | -0.072 |    0.03  |
| empirical raw (c_m vs .5)         | 502 | 494 |   0.504 | -0.038 |    0.03  |
| pure model departure (c_m vs c_q) | 434 | 443 |   0.495 | -0.055 |    0.032 |

### 5. Empirical raw: cover % by |c_m - 0.5|

| eb           |   n |   cover |    se |
|:-------------|----:|--------:|------:|
| (0.0, 0.01]  | 156 |   0.545 | 0.04  |
| (0.01, 0.02] | 134 |   0.463 | 0.043 |
| (0.02, 0.03] | 185 |   0.519 | 0.037 |
| (0.03, 0.05] | 208 |   0.452 | 0.035 |
| (0.05, 1.0]  | 313 |   0.527 | 0.028 |

### 6. Pure model departure: cover % by |c_m - c_q|

| db           |   n |   cover |    se |
|:-------------|----:|--------:|------:|
| (0.0, 0.01]  |  98 |   0.49  | 0.05  |
| (0.01, 0.02] | 150 |   0.493 | 0.041 |
| (0.02, 0.03] | 116 |   0.517 | 0.046 |
| (0.03, 0.05] | 217 |   0.461 | 0.034 |
| (0.05, 1.0]  | 296 |   0.514 | 0.029 |

## 2021-26 ledger (2021-25 in-sample)  (n=1466)

### 1. Market q converted to a spread, minus the posted line (toward favorite, pts)

| lb      |   n |   probit gap |   empirical gap |
|:--------|----:|-------------:|----------------:|
| <=2.5   | 351 |        -0.55 |            0    |
| 3       | 217 |        -0.06 |            0.23 |
| 3.5-6.5 | 495 |         0.48 |            0.1  |
| 7       |  73 |         0.93 |           -0.07 |
| 7.5-10  | 187 |         0.81 |            0.02 |
| 10+     | 143 |        -0.09 |            0.52 |
- probit: MAE 0.60 pts; share >= 1 pt 16%; >= 2 pt 1%
- empirical: MAE 0.46 pts; share >= 1 pt 11%; >= 2 pt 2%
- win prob at the posted line vs no-vig q, MAE: empirical 0.014; probit 0.017

### 2. Home-cover LPM, week-clustered SE (probability space)

- market (c_q - .5): +0.28 ± 0.63 (t +0.5)
- model departure (c_m - c_q): +0.39 ± 0.34 (t +1.1)
- both: +0.26 ± 0.63 (t +0.4), +0.38 ± 0.34 (t +1.1)

### 3. Pick agreement

- probit raw picks identical to q-only picks: 75%
- empirical raw picks identical to q-only picks: 77%
- empirical raw picks identical to probit raw picks: 64%

### 4. Records (flat 1u at -110, pushes excluded from cover %)

| rule                              |   W |   L |   cover |    roi |   roi_se |
|:----------------------------------|----:|----:|--------:|-------:|---------:|
| probit raw edge                   | 714 | 713 |   0.5   | -0.045 |    0.025 |
| empirical raw (c_m vs .5)         | 753 | 665 |   0.531 |  0.014 |    0.025 |
| pure model departure (c_m vs c_q) | 541 | 527 |   0.507 | -0.033 |    0.029 |

### 5. Empirical raw: cover % by |c_m - 0.5|

| eb           |   n |   cover |    se |
|:-------------|----:|--------:|------:|
| (0.0, 0.01]  | 308 |   0.506 | 0.028 |
| (0.01, 0.02] | 333 |   0.517 | 0.027 |
| (0.02, 0.03] | 218 |   0.555 | 0.034 |
| (0.03, 0.05] | 233 |   0.558 | 0.033 |
| (0.05, 1.0]  | 326 |   0.534 | 0.028 |

### 6. Pure model departure: cover % by |c_m - c_q|

| db           |   n |   cover |    se |
|:-------------|----:|--------:|------:|
| (0.0, 0.01]  | 217 |   0.447 | 0.034 |
| (0.01, 0.02] | 277 |   0.509 | 0.03  |
| (0.02, 0.03] | 172 |   0.512 | 0.038 |
| (0.03, 0.05] | 179 |   0.492 | 0.037 |
| (0.05, 1.0]  | 223 |   0.57  | 0.033 |
