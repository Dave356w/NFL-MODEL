# Test 55 protocol: less noisy band numbers for the median ATS map

Research only. Production v1.19, the median map, the lock policy and the forward ledger are unchanged. Owner request
2026-11-04 after Test 54 and the band-variance analysis: explore making the map less noisy instead of abandoning it.
This protocol is committed and pushed before any arm is scored on outcomes.

## Motivation, disclosed

Signed margins cluster on 3 and 7, so a band's median can jump a full key number between fits (2023–26 maps for the
3–7 band: 3, 3, 5, 4; bootstrap SD of the median at 300 games about 0.8 points, with a 55% chance of a ≥ 1 point move).
That analysis pooled 2014–26 replay margins. It used no ATS result for any arm below.

## Arms (fixed here)

Same bands as production (|raw spread| cut at 3, 7 and 10), same training rows (strictly earlier seasons, finite model
spread and result, model spread ≠ 0, ties included as 0, losses negative), same minimums (two seasons, 300 games,
30 per band). Only the per-band statistic of the signed margin s = sign(raw spread) × result changes.

| Arm | Band number |
|---|---|
| M0 production | median of s (must reproduce `fixed_bands.fit` exactly) |
| M1 Harrell–Davis | Harrell–Davis median of s (Beta((n+1)/2, (n+1)/2) weights on order statistics) |
| M2 trimmed mean | 20% trimmed mean of s |
| M3 HD, off key numbers | M1 rounded to the nearest half point that is not a whole number (x.5) |

M3 can never equal a whole-number line, so its zero-edge favorite rule fires only on half-point lines. Picks follow
production: zero edge takes the market favorite; a pick'em line with zero edge skips.

## Bases, never pooled

* **2016–22 (primary):** the v1.19 replay from Test 51's harness, with maps fitted on this replay's earlier seasons
  from 2014 (as Test 54).
* **2023–26:** production's v1.19 ledger, with maps fitted on 2021+ history (as production).

Both bases are exposed: v1.19's terms were chosen on 2019–25, Test 54 reported map ATS on both, and the variance
analysis above pooled 2014–26 margins.

## Primary: ATS units against M0

Flat 1u at −110 on the same games. Per arm, units(arm) − units(M0) summed, with an SE from the per-game differences.
Three arms, so the bar is |z| ≥ 2.39 (Bonferroni 98.33%).

* **Better:** positive with z ≥ 2.39 on 2016–22, and positive on 2023–26.
* **Worse:** negative with z ≤ −2.39 on either basis.
* **Unresolved:** otherwise.

## Reported, not gating

* **Noise reduction (the mechanism):** for each arm and band, the season-to-season change in the band number (mean
  absolute change) and the bootstrap SD of the band number at each fit's own sample size (1,000 resamples, seed fixed).
* **Estimator accuracy:** out-of-sample mean absolute error of the band number against next-season signed margins, per
  band (the median's own loss).
* Per basis and season: W-L-P, skips, units, ROI ± SE (pushes in the denominator), cover rate, n, break-even 52.4%,
  same-row always-favorite and always-home baselines; flips against M0 with units on them; zero-edge counts.
* Band-level records, descriptive only.

## What a result means

Diagnostic only. Adopting any arm changes the ATS selection rule, which is a new policy version and the owner's
decision; the map would still be fitted to prior-season margins. Because both bases are exposed, even "better" would
next run as a reporting-only arm on native v1.19 locks, reviewed with the map-vs-raw question at 100 decided locks.

Run: `python research/smooth_map.py`.
