# H12: fade the band-capped team ATS residual, 2013-2018

Pre-registered in research/PREREGISTRATION.md (2026-10-27). One out-of-period run on exposed seasons; not forward evidence. Assumed -110; pushes in the ROI denominator; break-even 52.4%.

**Verdict: replicates: register a reporting-only forward shadow as its own hypothesis.**

Primary: N = 8, |x| >= 2.51 pts; 1536 scored games.

| Arm | Bets | W-L-P | Cover [Wilson 95%] | Units | ROI ± SE |
|---|---|---|---|---|---|
| Fade rule | 438 | 225-196-17 | 53.4% [48.7, 58.2] | +8.55u | +2.0% ± 4.5 |
| Always favorite (same rows) | 437 | 206-214-17 | 49.0% [44.3, 53.8] | -26.73u | -6.1% ± 4.5 |
| Always home (same rows) | 438 | 211-210-17 | 50.1% [45.4, 54.9] | -18.18u | -4.2% ± 4.5 |

Secondary: cover slope per 2.51 pts of x, all scored games: -0.060 ± 0.026 (negative = fading works)

| Season | Bets | W-L-P | Cover [Wilson 95%] | Units | ROI ± SE |
|---|---|---|---|---|---|
| 2013 | 80 | 43-32-5 | 57.3% [46.1, 67.9] | +7.09u | +8.9% ± 10.3 |
| 2014 | 69 | 35-31-3 | 53.0% [41.2, 64.6] | +0.82u | +1.2% ± 11.3 |
| 2015 | 83 | 45-36-2 | 55.6% [44.7, 65.9] | +4.91u | +5.9% ± 10.3 |
| 2016 | 57 | 26-30-1 | 46.4% [34.0, 59.3] | -6.36u | -11.2% ± 12.6 |
| 2017 | 85 | 44-38-3 | 53.7% [42.9, 64.0] | +2.00u | +2.4% ± 10.2 |
| 2018 | 64 | 32-29-3 | 52.5% [40.2, 64.5] | +0.09u | +0.1% ± 11.7 |

Secondary windows (never decisive):

| Arm | Bets | W-L-P | Cover [Wilson 95%] | Units | ROI ± SE |
|---|---|---|---|---|---|
| Fade, N = 4 | 682 | 337-329-16 | 50.6% [46.8, 54.4] | -22.64u | -3.3% ± 3.6 |
| Favorite, N = 4 rows | 681 | 340-325-16 | 51.1% [47.3, 54.9] | -15.91u | -2.3% ± 3.6 |
| Fade, N = 16 | 195 | 98-96-1 | 50.5% [43.5, 57.5] | -6.91u | -3.5% ± 6.8 |
| Favorite, N = 16 rows | 195 | 103-91-1 | 53.1% [46.1, 60.0] | +2.64u | +1.4% ± 6.8 |

Reproduce: `python -m research.h12_capped_residual`
