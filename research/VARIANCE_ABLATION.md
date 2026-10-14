# Variance-aware shrinkage and chronological group ablation

Owner request (2026-10-14): build, test and report variance and ablation. Research only. Production v1.18, its recipe/signature, shadow lock, live workflow and native ledger remain unchanged. All historical periods and previous ablations were already exposed; this is development evidence, not an independent forward confirmation.

## Three fixed primary arms

1. Production, unchanged.
2. `reliability`: point-in-time reliability shrinkage of the 14 raw h8 box-rate differences plus the two lead/deficit differences. Availability, site, h16 passing contexts, fit decay, standardization, ridge, market offset and final favorite penalty remain unchanged.
3. `chronological_prune`: remove at most one of the eight existing feature groups, chosen once per season solely on earlier-season weekly OOF log loss. No reliability shrinkage in this arm.

No joint arm, added statistic, ROI tuning, or parameter sweep.

## Measurement variability and fidelity

Use the committed form_windows team-game boxes and the frozen OOS (history starts 2013) and Test 36 (history starts 2019) packs. Match each pack's game universe/history start, aliases, three-season history limit, h8 decay, 0.5 offseason retention and four league pseudo-games. Reconstruct the 16 main inputs and require shared finite values to agree with frozen production within 1e-8 on 2014-25. Missingness must agree. No invented measurement uncertainty for availability, QB or interaction inputs.

For each week, use 128 fixed-seed Poisson(1) whole-game multiplier-bootstrap draws on strictly earlier team-game boxes. Share each game's multiplier across both teams and all stats, preserving offense/defense and feature covariance. Keep the prior league pseudo-game mean fixed; uncertainty is conditional on that prior and observed opponents/personnel. Compute sampling variance of each home-minus-away difference. These are historical sampling-sensitivity estimates, not isolated coaching variance or a complete uncertainty model. Bootstrap assumes past games are exchangeable after decay and may include genuine form variation.

For each row/feature, use only earlier ready priced rows with finite pass contexts from at most three prior seasons plus earlier current-season weeks (minimum 64 rows). Estimate observed matchup-profile variance V and average bootstrap noise N; S=max(V-N,0). Set r=S/(S+noise_for_this_row), or 1 before adequate reference support; zero if both signal and noise are zero. Transform x to r*x (neutral difference remains zero). Compute each training row's factor before its own week; do not estimate all training-row factors using the evaluation cutoff. This makes factors vary by row, avoiding a constant scaling that standardization would cancel. Report coverage, r distribution, variance components, and how many inputs lose all signal.

## Fixed ablation groups and earlier-season selection

Use feature_importance.GROUPS unchanged: offensive box rates, defensive box rates, QB projection, unit absences, lead/deficit peaks, pass product, four pass-tail hinges, and site. Zero each group's inputs in training AND evaluation and refit production weekly. Produce the eight fixed group-drop arms as diagnostics, never pick based on evaluation-period returns.

Selection for season Y uses the most recent three completed seasons of weekly OOF forecasts strictly before Y; require at least two earlier seasons, otherwise retain production. A deletion is eligible only if its paired mean LL gain over production exceeds one week-cluster SE. Among eligible arms, identify the best mean LL; retain arms within one paired SE of that best. Choose the arm removing the most inputs, then break ties alphabetically. If none qualify, retain production. Freeze the choice for the whole evaluation season. This is a fixed conservative simplicity gate, not a significance claim or proof of equivalence.

## Bases, scores and decisions

Generate OOF forecasts beginning in 2014 where production has enough training history. Keep 2015-16, 2017-22 and 2023-25 evaluations separate. No current-season challenger or native shadow adoption in this first study. Archived production checks (2017-20, 2021-22, 2023-25) must agree within 1e-9; independently compare fitting implementations. Freeze references before scoring.

Lead with flat 1u returns, ROI +/- SE, same-row market-favorite returns and market-correct null. Report paired ROI differences, side flips, LL/Brier, calibration, forecast-departure dispersion, annual choices/cutoff audits and group-drop effects. Ties push in returns and are excluded from binary scores. Same-row directional samples follow existing repo conventions.

For the two primary challengers, use 97.5% two-sided normal week-cluster intervals within each basis. Eight group-drop diagnostics use 99.375% intervals (eight comparisons) within a basis. Annual and feature-variance tables are descriptive; no across-basis or across-metric confirmation claim. Development nomination requires positive LL gains on all three bases and a positive adjusted lower bound on at least one, with Brier/calibration and return deterioration disclosed. Otherwise unresolved/no nomination. Only a future pre-specified native test can provide forward evidence.

## Reproducibility and safeguards

Freeze source hashes, high-precision archived reference probabilities, bootstrap variances and fidelity audits under research/variance_ablation_inputs. A source mismatch requires an explicit rebuilt input snapshot; never silently regenerate it during a replay. Deterministic outputs include predictions, paired scores, selections, feature variability and coefficient/cutoff audits. Keep live-ledger integrity checks out of saved deterministic metadata. Add dependency-complete workflow triggers and strict comparison with committed results. Run meaningful positive/negative tests, the full suite, data validation and notebook-sync check before publishing. Do not modify data/ or public/.
