# Test 56 protocol: should zero-edge ATS games be bet at all?

Research only. Production v1.19, the median map, lock policy v2 (zero edge takes the market favorite; owner decision
2026-10-19) and the forward ledger are unchanged. Owner request 2026-11-04 after the Harrell–Davis exploration, which
found that about 70% of that arm's flips were production zero-edge games. This protocol is committed and pushed before
the three policies below are scored.

## Games

A zero-edge game is one where production's median-mapped spread equals the market spread within 1e-10 and the line is
not a pick'em (a pick'em with zero edge already skips under policy v2). Everything else in the selection is unchanged.

## Policies (fixed here)

| Policy | Zero-edge games |
|---|---|
| F favorite | bet the market favorite (production, policy v2) |
| D underdog | bet the market underdog |
| S skip | no bet |

All other games are bet exactly as production. Flat 1u at −110; pushes 0u.

## Prior expectation, stated in advance

Zero edge means the model has no view beyond the line. If a zero-edge game is a fair coin flip at the line (Test 55's
check found the book's no-vig price at −3 is 0.50 in every period), F and D each expect about −0.045u per bet before pushes,
and S expects 0. A result that favors F or D over S needs to beat that cost.

## Bases, never pooled

* **2016–22:** v1.19 replay with each season's map fitted on the replay's earlier seasons from 2014 (as Tests 54–55).
* **2023–26:** production's v1.19 ledger and exported map (2021+ history).

**Exposure: both bases are fully exposed.** Test 55's exploration already showed the underdog side of these ties gained
on 2016–22 and lost on 2023–26 (underdogs at +3 covered 53.9% then 44.4%), and production's 2023–26 zero-edge favorite
bets (68-53-12, +8.8u) were reported earlier. This test is descriptive. Only forward locks can confirm a policy.

## Comparisons

Two contrasts against production, on the zero-edge games of each basis: D − F and S − F (units, summed, SE from the
per-game differences). Two contrasts, so the bar is |z| ≥ 2.24.

* **Favored over F:** positive with z ≥ 2.24 on one basis and positive on the other.
* **Worse than F:** negative with z ≤ −2.24 on either basis.
* **Unresolved:** otherwise.

## Reported

* Per basis and season: number of zero-edge games and their share of all bets (how much S shrinks the bet count);
  W-L-P, units and ROI ± SE of F and D on zero-edge games; favorite cover rate on them.
* Whole-strategy records under each policy: W-L-P, skips, bets, units, ROI ± SE (pushes in the denominator), cover
  rate, break-even 52.4%, and the same-row always-favorite and always-home baselines.
* Zero-edge games by line (3, 7, other) and by band.

## What a result means

Diagnostic only. Changing the zero-edge rule is a new lock policy version and the owner's decision. Because the bases
are exposed, a favored policy would next run as a reporting-only arm on native v1.19 locks, reviewed with the
map-vs-raw question at 100 decided locks.

Run: `python research/zero_edge.py`.
