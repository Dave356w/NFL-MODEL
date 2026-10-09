# Can availability-adjusted player value replace or improve v1.15? (research Test 30, 2026-10-09)

**Basis: held-out walk-forward seasons 2023–2025 (development evidence, not forward confirmation).**
815 games, 811 priced at the nflverse schedule moneyline (a close with no quote timestamp, not a
pregame snapshot). Every variant is scored on the identical games; each season's recipe is the minimum
mean walk-forward log loss on earlier seasons; nothing was selected on ROI. Revision under test:
`boxscore-composite-v1.15` (control A). Player value is **rAV, a reconstruction of PFR AV, not PFR AV**
(see "Data" below).

## Verdict

**Do not replace v1.15, and do not adopt an AV hybrid on this evidence.**

* **Pure AV fails.** Every AV-only model (B1, B2, D1, D2) scores worse than v1.15 in log loss: −0.009 to
  −0.013 per game (B1's 95% interval excludes zero). Each loses 3.5–5.0 ROI points against v1.15 (B2's
  interval excludes zero). Each is also further from the market.
* **The hybrid is unresolved, and mixed in sign.**
  * C1 (unit absence shares replaced by rAV unit losses): log loss +0.0030 ± 0.0026, ROI −2.0 ± 1.7 points.
  * C2 (both representations): log loss +0.0027 ± 0.0021, ROI −2.3 ± 1.2 points.
  * The log-loss gain comes from 2024; 2023 loses about 5–6 ROI points. Neither is stable year to year.
* **Injury responsiveness was not demonstrated.** In the pre-specified high-absence and backup-QB games,
  no AV variant beats v1.15 beyond its standard error.
* **What restores the lost information is team performance.** Two comparisons on the same games:
  * Adding v1.15's box-score rates and QB efficiency term to AV (C1 vs B2): +0.013 ± 0.007 log loss.
  * Adding a shrunk team residual to the roster prior (D1 vs its base): +0.022 ± 0.005.
  * Even so, roster prior + residual stays below v1.15.
  * Replacing v1.15's QB efficiency with QB rAV (C3) costs 4.5 ± 2.0 ROI points. QB rAV does not carry
    the QB term's information.

## Goal metric: flat 1u moneyline ROI on the model's side (same 811 priced games)

Market-correct null −4.1% (negative by the hold); same-row market favorite +0.0%.

| ID | Model | Units | ROI ± SE | vs A, paired (pts, week-clustered 95%) | Model ≠ favorite: games, units (favorite units) |
|---|---|---:|---:|---:|---:|
| A | v1.15 (control, reproduced exactly) | +16.30 | +2.0% ± 2.7 | — | 116, +4.09 (−12.03) |
| B1 | pure rAV, linear | −14.28 | −1.8% ± 2.8 | −3.77 ± 2.54 [−8.6, +1.1] | 151, −14.47 (−0.01) |
| B2 | pure rAV, replacement + weak-link | −24.57 | −3.0% ± 2.7 | −5.04 ± 2.50 [−9.9, −0.3] | 149, −19.96 (+4.79) |
| C1 | v1.15 + rAV unit losses (replace) | −0.17 | −0.0% ± 2.6 | −2.03 ± 1.65 [−5.2, +1.2] | 118, −6.75 (−6.40) |
| C2 | v1.15 + both availability forms | −2.37 | −0.3% ± 2.7 | −2.30 ± 1.21 [−4.7, +0.1] | 125, −7.55 (−5.00) |
| D1 | rAV roster prior + team residual | −20.87 | −2.6% ± 2.7 | −4.58 ± 2.58 [−9.6, +0.2] | 136, −15.58 (+5.47) |
| D2 | D1, opponent-adjusted residual | −11.72 | −1.4% ± 2.7 | −3.46 ± 2.48 [−8.2, +1.2] | 135, −10.29 (+1.60) |

## Proper scores, calibration, margins

The no-vig moneyline market on the same games: log loss 0.6081, Brier 0.2103.

| ID | Log loss | Gain vs A (95%) | LL worse than market | Brier | Cal. intercept / slope | Margin MAE / RMSE | Side of the spread |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 0.6316 | — | 0.0236 | 0.2202 | +0.019 / 1.044 | 10.05 / 13.07 | 50.3% (796) |
| B1 | 0.6442 | −0.0125 [−0.0244, −0.0003] | 0.0361 | 0.2258 | −0.008 / 0.915 | 10.39 / 13.29 | 47.9% |
| B2 | 0.6420 | −0.0103 [−0.0224, +0.0018] | 0.0339 | 0.2250 | −0.013 / 0.951 | 10.37 / 13.28 | 47.9% |
| C1 | 0.6286 | +0.0030 [−0.0023, +0.0080] | 0.0205 | 0.2188 | +0.014 / 1.066 | 10.04 / 13.02 | 51.0% |
| C2 | 0.6289 | +0.0027 [−0.0014, +0.0067] | 0.0209 | 0.2189 | +0.020 / 1.045 | 10.04 / 13.03 | 50.3% |
| D1 | 0.6409 | −0.0093 [−0.0217, +0.0027] | 0.0328 | 0.2245 | −0.006 / 0.915 | 10.39 / 13.28 | 45.6% |
| D2 | 0.6414 | −0.0098 [−0.0221, +0.0021] | 0.0333 | 0.2248 | −0.005 / 0.909 | 10.40 / 13.28 | 45.5% |

Market spread on the same games: MAE 9.75 and RMSE 12.66. Every model's margin is worse. A and C
margins are `12.37 Φ⁻¹(p)`; B and D margins are the regression mean. The B and D models are
over-confident: calibration slope 0.91–0.95.

## By season (paired vs A; ROI points / log-loss gain)

| ID | 2023 (272) | 2024 (272) | 2025 (271) |
|---|---|---|---|
| B1 | −4.5 ± 4.0 / +0.002 ± 0.009 | −4.0 ± 5.1 / −0.013 ± 0.008 | −2.8 ± 3.9 / −0.027 ± 0.013 |
| B2 | −1.7 ± 3.5 / +0.004 ± 0.008 | −8.7 ± 4.8 / −0.011 ± 0.008 | −4.8 ± 4.6 / −0.024 ± 0.014 |
| C1 | **−6.1 ± 2.2** / +0.002 ± 0.004 | +0.3 ± 3.3 / **+0.010 ± 0.004** | −0.4 ± 2.5 / −0.002 ± 0.005 |
| C2 | **−4.8 ± 1.9** / +0.001 ± 0.003 | −1.4 ± 2.2 / +0.007 ± 0.003 | −0.7 ± 1.9 / +0.001 ± 0.004 |
| D1 | −0.9 ± 3.8 / +0.003 ± 0.010 | −8.6 ± 4.3 / −0.015 ± 0.009 | −4.2 ± 5.4 / −0.016 ± 0.013 |
| D2 | −1.4 ± 3.9 / +0.003 ± 0.010 | −6.6 ± 3.9 / −0.014 ± 0.008 | −2.3 ± 5.1 / −0.018 ± 0.013 |

Bold: the 95% interval excludes zero. These are three seasons with differing signs; that is not
stability.

## Pre-specified subgroups (definitions fixed in code before any held-out result)

The full table is in [`output/results.md`](output/results.md). There are 11 subgroups × 6 variants,
so about 3 intervals would exclude zero by chance alone.

* **Backup-QB games (170).** No AV variant improves on v1.15 beyond its SE. C2 is +1.5 ± 2.3 ROI and
  +0.002 ± 0.005 LL; B1 is −11.0 ± 5.3 ROI.
* **High absence, ≥ 3 starters out (287).** C2 is +0.007 ± 0.004 LL and −1.1 ± 2.6 ROI. The pure-AV
  variants are worse.
* **Low continuity (293).** The pure-AV variants are clearly worse: about −0.02 LL and −8 to −10 ROI.
  So the AV prior adapts *less* well to roster turnover than team box scores. C is neutral.
* **Week 18 (48).** Every AV-only model beats v1.15: B2 +0.037 ± 0.006 LL and +9.3 ± 4.2 ROI. This fits
  AV pricing rested starters that box-score form cannot see. But n = 48 and this is one of 11 subgroups.
  It is a hypothesis for a rest-aware term, not a finding.
* **Weeks 10–13 (173).** C1 and C2 gain +0.011 to +0.012 LL. Weeks 5–9 lose −0.006 to −0.008.

## Ablations

* **Prior-only vs blended rates (B2).** Blending completed current-season games, from week 5 and only
  games before kickoff, gains +0.021 LL. Prior-season-only rAV is clearly worse: LL 0.6633, ROI −4.2%.
* **Replacement-relative and weak-link aggregation.**
  * LL: replacement-relative linear 0.6421, weak-link 0.6420, min-starter 0.6421, raw linear (B1) 0.6442.
  * With opportunity redistributed to a fixed slot total, subtracting a per-unit replacement constant
    nearly cancels in home-minus-away differences.
  * Weak-link weighting and the min-starter summary change almost nothing.
  * Raw vs relative is unresolved: B1 is worse in LL but better in ROI.
* **C3: QB rAV instead of the QB efficiency term.** −4.48 ± 2.00 ROI and −0.002 ± 0.004 LL. v1.15's
  projected-QB efficiency carries information QB rAV does not.

## Post-hoc diagnostics (after the results; see [`output/posthoc.md`](output/posthoc.md))

* **D's residual vs its own rAV prior.** +0.022 ± 0.005 LL and +1.4 ± 2.4 ROI. Team history restores
  most of what AV-only lacks. Here the selected D bases were the prior-only rates.
* **The γ = 12 edge.** D's selected shrinkage sat at the strongest value of its pre-registered grid
  every season. Extending γ to {24, 48, 96} leaves the selection at γ = 12, so the edge was not binding.
* **Weakly shrunk residuals.** γ = 1 chases noise: it adds 1–2 points of margin RMSE.

## Data, and what this does and does not establish

* **PFR AV.** Per-season PFR AV was not obtainable:
  * pro-football-reference.com returns HTTP 403 here, and its terms restrict scraping;
  * nflverse has only career AV.
* **rAV instead.** rAV reconstructs PFR's published allocation game by game from nflverse box scores and
  snap counts (2013–2025). Against PFR career weighted AV for 2,127 players drafted 2013–21:
  * Pearson 0.956 overall, 0.96–0.997 by unit;
  * per game, removing career length, 0.891 overall and 0.79–0.99 by unit.
* **Not tested: true PFR AV.** A licensed season table could swap in for prior seasons only.
* **The construction carries team performance.** By construction, an offensive lineman's rAV is mostly
  his team's past points. Part of "pure AV" is team performance seen through players, which makes its
  failure more informative, not less.
* **Coverage.** 99.98% of snaps map to GSIS ids; 0.007% of box-score yards lack a snap row. v1.15's
  projected QB maps to an id in 99.1% of team-weeks.
* **Timing.** Rules use only pregame information: v1.15's membership, reserve, injury and QB rules.
  Weekly rosters have no publish time; 0.16% of newly listed reserve players took a snap that game.
  Historical moneylines are closes.
* **Fixed choices and limitations.**
  * The participation multipliers (Out 0, Doubtful .15, Questionable .65) are not calibrated.
  * Model C uses the blended estimator only (fixed before results).
  * A week-1 rookie starter has no base share.
* **Out of scope.** This establishes nothing about forward performance. All held-out ROI differences
  except B2's are unresolved: an interval crossing zero does not show the effect is zero.

## Recommended next steps (owner's call)

1. **Shadow-log C2 forward without adopting it.** Record C2's probability beside each v1.15 snapshot,
   in a separate research file, never the ledger.
   * *Falsified if* after a full season the paired log-loss gain's interval is below zero, or the ROI
     difference is ≤ −2 points.
   * A new `REVISION` would be needed only if the owner later adopts it.
2. **Pre-register a week-18 rest term:** the projected rAV share of rested regulars, as an input to v1.15.
   * *Falsified if* it shows no log-loss gain in the 2021–22 week-18 walk-forward games. Those rows
     informed recipe selection, but the week-18 subgroup was never inspected there.
   * The 2026 week-18 forward games are the final test.
3. **Calibrate the participation multipliers** against realized snap shares, by status, in 2019–22
   only, then re-run C1/C2.
   * *Falsified if* calibrated multipliers move C's held-out log loss by less than its SE.

Reproduce: see [README.md](README.md). Per-game predictions of every variant are in
`output/heldout_predictions.csv`. The feature audit is `output/av_team_week_features.csv.gz`.
