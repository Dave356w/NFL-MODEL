# H11: soft band margin distributions vs the Kalshi spread ladder

Pre-registered in research/PREREGISTRATION.md (2026-10-27). Prediction only; no bets. Production, the median map and the archives are unchanged.

**Primary (boxscore-composite-v1.18, fresh forward games): interim (n = 0 < 100 fresh games): no verdict.**

- Soft band PMF vs Kalshi mid: no rows
- Excluded as exposed at registration: 28 games

Secondary, never decisive:

- (a) Exposed games (seen before H11 was registered): gain +0.0065 +/- 0.0085 (1 SE; positive = challenger better); 28 games, 672 rungs; log loss Kalshi 0.4960 vs challenger 0.4896
- (b) Soft vs hard, fresh games (positive = soft better): no rows
- (c) Near-line rungs (within 4 pts of the team's line): no rows
- (d) Development, exposed 2025-26 main-spread rung 2h pregame: gain +0.0026 +/- 0.0066 (1 SE; positive = challenger better); 350 games, 350 rungs; log loss Kalshi 0.6890 vs challenger 0.6864

Reproduce: `python -m research.soft_band_ladder_score`
