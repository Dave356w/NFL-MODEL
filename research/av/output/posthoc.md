## Post-hoc diagnostics (after the primary results; not used for any selection)

| Comparison (same 815 held-out games) | ROI difference (pts) | Log-loss gain |
|---|---:|---:|
| D1 vs its own B2 roster prior (residual restores) | +1.39 ± 2.41 [-3.0, +6.2] | +0.0219 ± 0.0052 [+0.0121, +0.0321] |
| D2 vs the same roster prior | +2.52 ± 2.33 [-1.9, +7.2] | +0.0214 ± 0.0051 [+0.0117, +0.0314] |
| C1 vs B2 (box-score team rates + v1.15 QB term restore) | +3.01 ± 2.70 [-2.3, +8.3] | +0.0133 ± 0.0066 [+0.0008, +0.0262] |

D1 with gamma ∈ {1, 4, 12, 24, 48, 96} (λ = .9 for the added values), selected per season on earlier seasons: picks {2023: 'D1_B2_prior_r1_l0.9_g12', 2024: 'D1_B2_prior_r100_l0.9_g12', 2025: 'D1_B2_prior_r100_l0.9_g12'}; held-out log loss 0.6409, ROI -2.6% ± 2.7; vs A: ROI -4.58 ± 2.58 [-9.6, +0.2], log-loss gain -0.0093 ± 0.0062 [-0.0217, +0.0027].
