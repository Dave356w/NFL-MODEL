# Test 34 protocol: explosive share of offensive yardage, 2017–2020

Research only; production, frozen recipes and the forward ledger are unchanged. Owner go-ahead
2026-10-13. This file is committed and pushed before any explosive-share number exists for any
season.

## Hypothesis and where it came from

Test 33 (`explosive_plays.py`, 2021–26) added explosive pass and rush rates to v1.16. It failed its
gate, but the weekly refits gave the **offensive** explosive rates negative coefficients (median
−0.045 and −0.042; positive in 31% and 14% of fits) while yards per play stayed in the model.
Reading: at equal yards per play, a team that gets more of its yardage from big plays does slightly
worse than the market expects, because big plays repeat less than steady gains. That reading was
formed after looking at 2021–26, so those seasons cannot test it.

## Exposure, disclosed in advance

* 2021–26 are spent for this question (Test 33).
* 2017–20 were scored once with v1.16 under `OUT_OF_SAMPLE_2017_2020.md`, and once with a
  v1.12-era model (the unmerged branch's Test 32). Those results are known. **No explosive-play
  quantity has ever been computed for 2010–2020** in this repository.
* Power is low. Test 33's effects were about 0.001 in log loss. On about 1,000 games the standard
  error is about 0.001–0.002, so the expected verdict is "unresolved".

## Feature (fixed)

Per team-game, from nflverse play-by-play with the box-score filters (regular season; no two-point
tries, deleted plays or `no_play` rows; a pass play is a pass attempt or a sack; a rush is a rush
attempt that is not a pass play):

* explosive yards = yards gained on passes of ≥ 20 yards plus runs of ≥ 10 yards;
* net yards = yards gained on all pass plays and rushes (sacks count negative), as in the box scores.

Profile: **offense only**, explosive yards / net yards, with production's main-profile rule (games
strictly before the game week, the last three seasons, 2^(−age/8) by team game, halved at each
season boundary, ratio of decayed sums with four league-average pseudo-games). The feature is the
home-minus-away difference `d__for__explosive__share_of_net_yards`. One feature, one arm. No
defensive version and no other thresholds will be tried on these seasons.

## Arms and data

* `production`: exact v1.16 (`LEGACY_PRODUCT_RECIPE`) on the frozen 2013–2020 pack
  (`research/out_of_sample_results/frozen_features_2013_2020.csv.gz`). It must reproduce that
  directory's `predictions.csv` to 1e-7, or the run stops.
* `explosive_share`: the same, plus the one feature as a main feature at ridge 0.1.
* Both are refit before every scored week on strictly earlier eligible games from 2013 on (the
  same training rows the 2017–20 test used). Scored rows: 2017–2020 regular season, ready, priced,
  with finite pass contexts. Ties push in ROI and are excluded from binary scores.

## Decision rules (fixed)

* **Falsified** if the log-loss gain over v1.16 is ≤ 0, or if the feature's coefficient is negative
  in fewer than half of the weekly fits.
* **Candidate for a new `REVISION`** only if the gain is positive with a 95% week-clustered bootstrap
  interval above zero, the coefficient is negative in most fits, and the flat 1u ROI difference's
  95% interval is not entirely below zero. Even then, adoption is the owner's decision and needs a
  forward test.
* **Otherwise: unresolved.** No change, and these seasons are not reused for this question.

Reported in every case: flat 1u moneyline ROI ± SE for both arms, the market-correct null and the
same-row market favorite, log loss and Brier for both arms and the market, the paired differences
with intervals, the coefficient's median and sign share, and results by season.
