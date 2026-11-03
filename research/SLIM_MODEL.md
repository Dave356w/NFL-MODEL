# Test 50 protocol: slim models from the fit analysis (diagnostic)

Research only. Production v1.18, its v1.16 shadow lock, frozen recipes, the median map and the forward
ledger are unchanged. Owner request 2026-11-03. This protocol is committed and pushed before any slim
arm is built or scored.

## Question

Does a model with fewer of the 29 fitted terms forecast as well as production, and how do its ATS
picks compare on the same games?

## Exposure, disclosed in advance

The arms were chosen from analysis that had already seen every basis:

* Test 38 drop-column importance and attribution (2015–16, 2017–22, 2023–25).
* A 2026-11-03 sanity check of the live week-9 fit: contribution shares, coefficient stability over
  the week 5–9 snapshots, and an in-sample game bootstrap with per-season fits on the 2019–26
  (before week 9) training pack.

S3 was selected on bootstrap z-scores from 2019–25, which overlap 2017–22 and 2023–25, so those
bases cannot test S3 fairly. 2015–16 is the only basis S3's selection did not touch, though Test 38
had already seen it. None of these bases is a clean test. A clean test is forward.

## Arms (fixed here)

All arms use the v1.16 recipe (h8, ridge 0.1, market offset, h16 pass contexts, interaction ridge 0.1),
refit before every week on earlier rows only. The v1.18 favorite penalty (λ 0.2) is applied after.
A dropped term is zeroed in every row, which is the same as fitting without it.

| Arm | Terms | Change from production |
|---|---:|---|
| P | 29 | production v1.18 |
| S1 trim | 22 | drop largest lead, largest deficit, RB/LB/DB absences, offense and defense net yards per dropback |
| S2 trim + one INT term | 21 | S1, with offense INT % + defense INT % (same units, home minus away) as one term in place of the two |
| S3 core | 10 | keep only home field, offense and defense first-down rate, offense and defense INT %, defense penalty yards, QB projection, pass product, pass tail hinges PN and NP |

S1's terms are near-zero contributors (0.7% of week-9 corrections for the peaks; LB/DB/RB and both
pass-yards terms have coefficients near zero or bootstrap |z| < 0.6). The pass-context terms still use the
h16 net-yards-per-dropback profiles; only the box-rate regressors are removed.

## Bases, never pooled

2015–16, 2017–22 and 2023–25, built as in Test 38: `out_of_sample_results/frozen_features_2013_2020.csv.gz`
for 2014–20 and `shrinkage_results/frozen_training_features.csv.gz` for 2021–25. P must reproduce the
published forecasts to 1e-9 (Test 38's reproduction check). 2014 is forecast only so each arm's own median
map has prior seasons.

## Primary: log loss

Per basis, `LL(arm) − LL(P)` per binary game (×1000), mean with a week-clustered SE.
Negative means the slim arm is more accurate. Three arms, so the bar is |z| ≥ 2.39 (Bonferroni 98.33%).

* **Stop:** worse than P at z ≥ +2.39 on any basis.
* **Forward candidate:** not reliably worse on any basis, and nominally better (mean < 0) on at least
  two of three.
* **Unresolved:** otherwise.

For S3, only 2015–16 counts toward the verdict; the other two bases are reported as descriptive.

## Secondary: ATS (reported, not optimized)

Flat 1u at −110 against the market spread, same rows for every arm. Each arm's model spread is
`12.37·Φ⁻¹(p)` and its own median map is fitted on that arm's own prior-season forecasts with
`fixed_bands.fit`. Seasons without a map (fewer than two prior seasons or 300 games) are out of
the mapped comparison for every arm. Zero edge takes the favorite; a pick'em skips. Reported per basis: W-L-P,
skips, units, ROI ± SE (pushes in the denominator), cover rate excluding pushes, n, break-even 52.4%,
same-row always-favorite and always-home baselines, the raw (unmapped) spread version, and side flips
against P with the units on those flips. Moneyline flat units from the Test 38 harness are reported last.

## What a result means

Diagnostic only. Any slim arm changes `config_signature()` and would need a new `REVISION`, which is the
owner's decision. A forward candidate would next run as a reporting-only shadow on native locks. The
owner reviews it at 100 decided locks, comparing log loss and ATS units against v1.18 on the same games.

Run: `python research/slim_model.py`.
