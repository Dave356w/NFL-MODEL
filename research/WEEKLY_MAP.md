# Test 59 protocol: weekly refits of the median ATS map, and a linear-trend map

Research only. Production v1.19, the annual median map, lock policy v2 and the forward ledger are unchanged. Owner
view 2026-11-04: season-to-season changes are linear, so the map should be fitted week by week, not season by season.
This protocol is committed and pushed before any arm is scored.

## Disclosed before the run

A descriptive look the same day found single-season band medians with linear trends of 0.07–0.14 points per season and
negative lag-1 autocorrelation of yearly changes (−0.27 to −0.75), and weeks 1–9 vs 10+ band medians within 1 point.
No arm below was scored on outcomes.

## Arms (fixed here)

Same bands (|raw spread| cut at 3, 7, 10), training rows (finite model spread and result, model spread ≠ 0, ties as 0,
losses negative) and minimums (two seasons, 300 games, 30 per band) as production. Signed margin s = sign(raw spread) ×
result. The map for each game uses only games before that game's (season, week).

| Arm | Band number for games in week w of season Y |
|---|---|
| A annual (production) | median of s over seasons before Y (one fit per season) |
| W weekly, expanding | median of s over all games before (Y, w): earlier seasons and this season's earlier weeks |
| D weekly, decayed | weighted median of s over all games before (Y, w), weight 2^(−age), age = ((Y − season)·19 + (w − week))/19 (one-season half-life) |
| T linear trend | A + the least-squares slope of earlier seasons' single-season band medians (at least three seasons) × (Y − mean earlier season) |

The weighted median is the smallest value whose cumulative weight reaches half the total, averaging with the next
value at an exact half; with equal weights it equals `np.median`. W must equal A in week 1 of each season (check).

## Bases, never pooled

* **2016–22:** v1.19 replay, history from 2014 (as Tests 54–58).
* **2023–26:** production's v1.19 ledger, history from 2021 (as production).

Both are exposed: v1.19's terms were chosen on 2019–25, and Tests 54–58 reported map ATS on these seasons.

## Primary: accuracy of the band number

Per game, |s − band number| (the median's own loss), arm minus A, mean per game with a week-clustered SE. Negative
means the arm's number is closer to that week's realized margins. Three contrasts, bar |z| ≥ 2.39.

* **Better than A:** lower error with z ≤ −2.39 on one basis and lower on the other.
* **Worse than A:** higher error with z ≥ 2.39 on either basis.
* **Unresolved:** otherwise.

## Reported, not gating

* ATS at −110 (production's pick rule, zero edge takes the favorite): W-L-P, units, ROI ± SE, cover rate, n, break-even
  52.4%, same-row always-favorite and always-home baselines; units against A with SE; flips against A.
* Stability: mean absolute week-to-week change of each band number within a season, and how many picks change because
  the number moved between weeks.
* Band numbers by season and week.

## What a result means

Diagnostic only. A weekly or trend map would be a new ATS policy version and the owner's decision. Each lock already
saves the rule in force, so a weekly map could be locked without lookahead. A better arm would next run as a
reporting-only arm on native v1.19 locks.

Run: `python research/weekly_map.py`.
