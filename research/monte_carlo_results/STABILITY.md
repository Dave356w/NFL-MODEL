# Simulation stability check

Repeat uses an independent seed and doubles profile draws (256 → 512) and coefficient refits (64 → 128). Outcome draws remain 8,192; exact weighted outcome probabilities are scored.

Seed-independent market, production and empirical outcome arms match to 0. Common historical return cohorts: 811 / 812.

| Arm | Mean probability change, pp | Maximum change, pp | Changed sides | First LL | Repeat LL |
|---|---:|---:|---:|---:|---:|
| feature_bootstrap | 0.275 | 3.570 | 1 | 0.605852 | 0.605908 |
| coefficient_bootstrap | 0.516 | 6.456 | 4 | 0.606422 | 0.605584 |
| combined | 0.610 | 3.191 | 6 | 0.606113 | 0.605676 |

The repeat does not establish a predictive gain over production. Bootstrap averages near 50% can change direction with numerical sampling. Use uncertainty ranges for reporting; increase coefficient refits before treating tiny probability differences as meaningful. Two runs check sensitivity, not full convergence.
