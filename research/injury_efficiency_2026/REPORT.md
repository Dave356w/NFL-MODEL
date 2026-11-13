# 2026 injury → efficiency → model → ATS median replay

All 137 completed 2026 games were inventoried. The reconstructed baseline and
updated policy with unadjusted fallback both grade **75–56–6, +12.18u** at fixed
−110. Forty games use the unadjusted baseline because the injury adjustment is
unavailable; this pooled figure is not evidence of 137 valid injury adjustments.
Original production locks and public results were not rewritten.

| Same eligible games | W–L–P | Units | ROI | Median margin MAE | Median residual |
|---|---:|---:|---:|---:|---:|
| Baseline | 48–44–5 | −0.36 | −0.37% | 9.361 | 0 |
| Injury-adjusted | 48–44–5 | −0.36 | −0.37% | 9.381 | 0 |

Eligible n=97; cover rate 52.17% excluding pushes, against 52.38% break-even.
The adjustment changes three mapped medians and two ATS picks: LV–LAC week 2
loses → wins; ATL–NO week 4 wins → loses; KC–SEA week 7 stays a win.
There is no net ATS improvement and mapped-margin error increases 0.021 points.
For 32 excluded games prior medical-report coverage is below 90%; eight have
unresolved current reports. Nothing was imputed as healthy to inflate coverage.
In production these conditions block a new ATS candidate; fallback here is only
an explicitly labelled retrospective accounting view.

Injury stage weights are frozen from 2,348 team-games in 2020–25. Weekly core
fits use only earlier weeks. Current medical burden is weighted by prior snaps,
then compared with historical burden already represented in each team profile.
Only the injury component changes five efficiency inputs; the core ten-term
model, QB adjustment, passing contexts, favorite penalty and approved weekly
median map remain fixed. Every adjusted row carries references, source cutoffs,
and efficiency deltas in games.csv.

This is a reconstruction using archived final injury tables. Their original
publication times are not established. Twelve game IDs have complete captured
report pairs from the separate saved-report audit, but **this replay still uses
archived tables for those IDs**. Their reconstructed grades remain 5–7 in both
arms; the earlier genuinely saved-input 12-game experiment was 5–7 → 6–6.
Different snapshots/quotes/reconstructed fits can cross median-map boundaries;
these two analyses must not be pooled or presented as the same execution.
The broad result does not support claiming an ATS benefit or a PHI/LAC fix.
No 2026 outcome tunes the frozen injury coefficients. The choice to examine
this feature was made after observing 2026, so this remains development evidence.

Run `python research/injury_efficiency_replay.py` from the repository root.
Frozen research inputs and SHA-256 receipts are in
`research/injury_efficiency_replay_inputs/`; archived schedules, availability,
injuries and snaps plus the approved weekly rules come from the committed data
snapshot. `results.json` gives machine-readable aggregates; `games.csv` includes
all 137 rows and the missing-evidence reason for every excluded adjustment.
