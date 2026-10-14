# Test 36: one-at-a-time shrinkage sweep

Protocol: [SHRINKAGE_SWEEP.md](../SHRINKAGE_SWEEP.md), pushed before any arm was built. Stage 1 choices were committed before any 2017–20 candidate arm was scored. Basis: held-out walk-forward reconstructions (2023–25 heavily exposed; 2017–20 never used for these settings). Not forward evidence.

Production reproduction: 2023–25 816 games, max error 1.0e-10; 2017–20 1023 games, max error 2.8e-16.

## Verdicts (2017–20 confirmation, v1.16 forecasts)

* **qb_prior** → qb_prior=600: unresolved, keep production
* **pseudo_games** → pseudo_games=8: unresolved, keep production
* **retention** → retention=0.25: unresolved, keep production
* **fit_half_life** → fit_half_life=4: candidate for a new REVISION (owner decides)

## Stage 2: 2017–20, 1016 common bets, 1019 binary games, 98.75% week-cluster intervals

| Arm | W-L-P | Units | ROI ± SE | Null | Log loss | Brier |
|---|---|---:|---:|---:|---:|---:|
| production | 691-321-4 | +0.58 | +0.06% ± 2.23 | -2.55% | 0.605604 | 0.208494 |
| qb_prior=600 | 692-320-4 | +2.68 | +0.26% ± 2.23 | -2.55% | 0.605492 | 0.208463 |
| pseudo_games=8 | 691-321-4 | +1.54 | +0.15% ± 2.23 | -2.55% | 0.605515 | 0.208470 |
| retention=0.25 | 687-325-4 | -5.88 | -0.58% ± 2.24 | -2.55% | 0.605371 | 0.208563 |
| fit_half_life=4 | 692-320-4 | +2.02 | +0.20% ± 2.23 | -2.55% | 0.603682 | 0.207735 |
| market favorite | 685-327-4 | -18.18 | -1.79% ± 2.20 | -2.55% | 0.600368 | 0.206481 |

| Arm vs production | LL gain [CI] | ROI Δ pts [CI] | Side flips |
|---|---:|---:|---:|
| qb_prior=600 | +0.00011 [-0.00016, +0.00037] | +0.21 [+0.00, +0.83] | 1 |
| pseudo_games=8 | +0.00009 [-0.00064, +0.00088] | +0.09 [-0.58, +1.06] | 2 |
| retention=0.25 | +0.00023 [-0.00194, +0.00250] | -0.64 [-2.68, +1.37] | 16 |
| fit_half_life=4 | +0.00192 [+0.00000, +0.00392] | +0.14 [-1.60, +1.99] | 13 |

Same comparisons after the v1.18 favorite penalty (λ = 0.2):

| Arm vs production | LL gain [CI] | ROI Δ pts [CI] | Side flips |
|---|---:|---:|---:|
| qb_prior=600 | +0.00001 [-0.00018, +0.00019] | +0.21 [+0.00, +0.83] | 1 |
| pseudo_games=8 | +0.00003 [-0.00038, +0.00048] | +0.09 [-0.58, +1.06] | 2 |
| retention=0.25 | +0.00006 [-0.00134, +0.00148] | -0.64 [-2.68, +1.37] | 16 |
| fit_half_life=4 | +0.00105 [-0.00006, +0.00224] | +0.14 [-1.60, +1.99] | 13 |

Combined arm (qb_prior=600, pseudo_games=8, retention=0.25, fit_half_life=4), descriptive, 95%: LL gain +0.00200 [-0.00033, +0.00439], ROI Δ -0.19 pts, 15 side flips.

| Season | production | qb_prior=600 | pseudo_games=8 | retention=0.25 | fit_half_life=4 |
|---|---:|---:|---:|---:|---:|
| 2017 | 0.58648 | 0.58642 | 0.58646 | 0.58555 | 0.58671 |
| 2018 | 0.61519 | 0.61496 | 0.61581 | 0.61738 | 0.61114 |
| 2019 | 0.63028 | 0.63027 | 0.62939 | 0.62854 | 0.62830 |
| 2020 | 0.59050 | 0.59036 | 0.59044 | 0.59006 | 0.58860 |

### Post-hoc sensitivity for fit_half_life=4 (not gating)

| Forecast | LL gain | Cluster SE | Normal interval | Bootstrap lower bound over seeds | Seeds excluding zero |
|---|---:|---:|---:|---:|---:|
| v1.16 | +0.00192 | 0.00079 | [-0.00005, +0.00390] | -0.000122 to +0.000058 | 30% of 20 |
| v1.18 | +0.00105 | 0.00047 | [-0.00012, +0.00223] | -0.000128 to -0.000052 | 0% of 20 |

## Stage 1: 2023–25, 811 common bets, 815 binary games, 95% intervals

Chosen on 2021–25 log loss: qb_prior → qb_prior=600, pseudo_games → pseudo_games=8, retention → retention=0.25, fit_half_life → fit_half_life=4.
Annual picks: 2023: qb_prior=qb_prior=600, pseudo_games=production, retention=retention=0.25, fit_half_life=fit_half_life=4; 2024: qb_prior=qb_prior=600, pseudo_games=production, retention=retention=0.25, fit_half_life=fit_half_life=4; 2025: qb_prior=qb_prior=600, pseudo_games=pseudo_games=8, retention=retention=0.25, fit_half_life=fit_half_life=4.

| Arm | W-L-P | Units | ROI ± SE | Null | Log loss | Brier |
|---|---|---:|---:|---:|---:|---:|
| production | 564-246-1 | +28.35 | +3.50% ± 2.53 | -4.10% | 0.605605 | 0.208989 |
| qb_prior=75 | 563-247-1 | +25.81 | +3.18% ± 2.52 | -4.10% | 0.605824 | 0.209079 |
| qb_prior=300 | 564-246-1 | +28.06 | +3.46% ± 2.52 | -4.10% | 0.605409 | 0.208908 |
| qb_prior=600 | 564-246-1 | +28.06 | +3.46% ± 2.52 | -4.10% | 0.605271 | 0.208851 |
| pseudo_games=2 | 561-249-1 | +21.80 | +2.69% ± 2.52 | -4.10% | 0.606377 | 0.209319 |
| pseudo_games=8 | 565-245-1 | +30.65 | +3.78% ± 2.53 | -4.10% | 0.605394 | 0.208908 |
| pseudo_games=16 | 564-246-1 | +28.34 | +3.49% ± 2.53 | -4.10% | 0.605618 | 0.209060 |
| retention=0.25 | 564-246-1 | +29.54 | +3.64% ± 2.53 | -4.10% | 0.603601 | 0.208332 |
| retention=0.75 | 561-249-1 | +20.56 | +2.54% ± 2.52 | -4.10% | 0.608022 | 0.209869 |
| fit_half_life=1 | 566-244-1 | +37.02 | +4.56% ± 2.55 | -4.10% | 0.608423 | 0.210180 |
| fit_half_life=4 | 564-246-1 | +26.55 | +3.27% ± 2.52 | -4.10% | 0.604792 | 0.208622 |
| market favorite | 554-256-1 | -0.52 | -0.06% ± 2.47 | -4.10% | 0.608072 | 0.210334 |

| Arm vs production | LL gain [CI] | ROI Δ pts [CI] | Side flips |
|---|---:|---:|---:|
| qb_prior=75 | -0.00022 [-0.00051, +0.00006] | -0.31 [-1.34, +0.58] | 3 |
| qb_prior=300 | +0.00020 [-0.00004, +0.00046] | -0.04 [-0.74, +0.63] | 2 |
| qb_prior=600 | +0.00033 [-0.00008, +0.00078] | -0.04 [-0.74, +0.63] | 2 |
| pseudo_games=2 | -0.00077 [-0.00246, +0.00064] | -0.81 [-1.92, +0.21] | 6 |
| pseudo_games=8 | +0.00021 [-0.00082, +0.00132] | +0.28 [+0.00, +0.86] | 1 |
| pseudo_games=16 | -0.00001 [-0.00184, +0.00190] | -0.00 [-0.95, +0.97] | 4 |
| retention=0.25 | +0.00200 [-0.00084, +0.00498] | +0.15 [-1.46, +1.72] | 10 |
| retention=0.75 | -0.00242 [-0.00639, +0.00180] | -0.96 [-2.45, +0.44] | 9 |
| fit_half_life=1 | -0.00282 [-0.00579, +0.00040] | +1.07 [-0.73, +2.98] | 17 |
| fit_half_life=4 | +0.00081 [-0.00094, +0.00246] | -0.22 [-1.53, +1.05] | 10 |

Annually selected arms (each season chosen on earlier seasons only):

| Arm vs production | LL gain [CI] | ROI Δ pts [CI] | Side flips |
|---|---:|---:|---:|
| selected:qb_prior | +0.00033 [-0.00008, +0.00078] | -0.04 [-0.74, +0.63] | 2 |
| selected:pseudo_games | -0.00007 [-0.00033, +0.00019] | +0.28 [+0.00, +0.86] | 1 |
| selected:retention | +0.00200 [-0.00084, +0.00498] | +0.15 [-1.46, +1.72] | 10 |
| selected:fit_half_life | +0.00081 [-0.00094, +0.00246] | -0.22 [-1.53, +1.05] | 10 |
