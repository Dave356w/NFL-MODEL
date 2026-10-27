# H10: band margin distributions vs the Kalshi spread ladder

Pre-registered in research/PREREGISTRATION.md (2026-10-27). Prediction only; no bets. Production, the median map and the archives are unchanged.

**Primary (boxscore-composite-v1.18, forward): interim (n = 28 < 100 games): no verdict.**

- Hard band PMF vs Kalshi mid: gain -0.0023 +/- 0.0101 (1 SE; positive = challenger better); 28 games, 672 rungs; log loss Kalshi 0.4960 vs challenger 0.4983
- Captures before the lock: 0 games; invalid quotes excluded: 0 rungs

Secondary, never decisive:

- (a) Soft band PMF: gain +0.0065 +/- 0.0085 (1 SE; positive = challenger better); 28 games, 672 rungs; log loss Kalshi 0.4960 vs challenger 0.4896
- (b) H3 moneyline reference: gain -0.0021 +/- 0.0064 (1 SE; positive = challenger better); 28 games, 672 rungs; log loss Kalshi 0.4960 vs challenger 0.4981
- (c) Near-line rungs (within 4 pts of the team's line): gain -0.0111 +/- 0.0171 (1 SE; positive = challenger better); 28 games, 187 rungs; log loss Kalshi 0.6835 vs challenger 0.6958
- (d) boxscore-composite-v1.16 forward rows (overlapping games): gain -0.0070 +/- 0.0144 (1 SE; positive = challenger better); 41 games, 984 rungs; log loss Kalshi 0.4979 vs challenger 0.5049
- (e) Development, exposed 2025-26 main-spread rung 2h pregame: gain -0.0018 +/- 0.0074 (1 SE; positive = challenger better); 350 games, 350 rungs; log loss Kalshi 0.6890 vs challenger 0.6908
  - 2025: gain +0.0014 +/- 0.0078 (1 SE; positive = challenger better); 271 games, 271 rungs; log loss Kalshi 0.6910 vs challenger 0.6895
  - 2026: gain -0.0128 +/- 0.0191 (1 SE; positive = challenger better); 79 games, 79 rungs; log loss Kalshi 0.6823 vs challenger 0.6951

Reproduce: `python -m research.band_ladder_score`
