# H14: soft vs hard band ATS cover probabilities on the same locks

Pre-registered in research/PREREGISTRATION.md (2026-10-28). Reporting only; production, the median map and the archives are unchanged. Pushes at the lock line are excluded.

**Primary (boxscore-composite-v1.18 locks from 2026-10-29 00:00 UTC, 2026): interim (n = 0 < 100 scored locks): no verdict.** 0 locks, 0 pending.

- Conditional cover log loss: no scored rows
- (a) Paired ATS where sides differ: no differing sides graded

Diagnostics, exposed and never pooled with H14:

- Pre-cutoff 2026 locks: gain +0.0179 +/- 0.0173 (1 SE; positive = soft better), n = 14; log loss hard 0.7060, soft 0.6880, coin 0.6931; Brier hard 0.2564, soft 0.2474
  - Paired where sides differ: 4 locks; production 1-3-0 -2.09u, soft 3-1-0 +1.73u
- 2026 weeks 1-7 replay (fixed_band_ledger): gain -0.0087 +/- 0.0061 (1 SE; positive = soft better), n = 101; log loss hard 0.6903, soft 0.6990, coin 0.6931; Brier hard 0.2474, soft 0.2516
  - Paired where sides differ: 33 locks; production 16-14-3 +0.55u, soft 14-16-3 -3.27u

Reproduce: `python -m research.h14_soft_vs_hard_ats`
