# H13: H12 capped-residual fade, forward shadow on the ATS locks

Pre-registered in research/PREREGISTRATION.md (2026-10-27). Reporting only: never bet, no lock, pick or page changes. Assumed -110; pushes in the ROI denominator; break-even 52.4%.

**Forward (boxscore-composite-v1.18 locks from 2026-10-28 00:00 UTC): interim (n = 0 < 300 shadow bets): no verdict.** 0 locks, 0 pending (0 shadow bets pending).

| Arm | Bets | W-L-P | Cover [Wilson 95%] | Units | ROI ± SE |
|---|---|---|---|---|---|
| H12 fade (shadow) | 0 | — | — | — | — |
| Production median map | 0 | — | — | — | — |
| Always favorite | 0 | — | — | — | — |
| Always home | 0 | — | — | — | — |

Diagnostic, never pooled: 2026 replay on every completed regular-season game (exposed current season; 107 games with both histories; production pick where a saved or replayed mapped spread exists).

| Arm | Bets | W-L-P | Cover [Wilson 95%] | Units | ROI ± SE |
|---|---|---|---|---|---|
| H12 fade (shadow) | 42 | 18-21-3 | 46.2% [31.6, 61.4] | -4.64u | -11.0% ± 14.3 |
| Production median map | 42 | 25-14-3 | 64.1% [48.4, 77.3] | +8.73u | +20.8% ± 13.8 |
| Always favorite | 42 | 17-22-3 | 43.6% [29.3, 59.0] | -6.55u | -15.6% ± 14.3 |
| Always home | 42 | 17-22-3 | 43.6% [29.3, 59.0] | -6.55u | -15.6% ± 14.3 |

Reproduce: `python -m research.h13_shadow`
