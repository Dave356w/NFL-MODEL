# Win-probability calibration test — fixed exploratory design

Specified October 17, 2026 before computing challenger scores. The historical
model architecture, lambda=0.2 favorite adjustment, and outcomes are exposed.
This is development research, not a new independent holdout or forward test.

Question: Does replacing the model's probability with empirical win frequencies
improve probability forecasts, analogous to empirical median margin calibration?
For binary outcomes use win frequencies, not medians of 0/1 labels.

Inputs: frozen current historical ledger (1438 games, 2021 through 2026 W5),
from Dave356w/NFL-MODEL main 690c0c6740f7a5a6c4ef3c2abe244cc0df0dca2d.
Five final ties are excluded from binary evaluation and calibration.
v1.18 is directly observed. Recover v1.16 by analytically reversing the fixed
favorite-confidence transformation with lambda=0.2 and the recorded no-vig
market probability. Verify the round trip and, where available, compare with
the separately frozen v1.16 research inputs.

Fit each calibration separately for v1.16 and v1.18, using strictly prior seasons
only (2021-22 warm-up, expanding history thereafter). Four fixed challengers:

1. Seven confidence bands: 50-55, 55-60, 60-65, 65-70, 70-75, 75-80, 80%+.
   Predict empirical model-choice success frequency with Jeffreys smoothing:
   (wins+0.5)/(games+1). Empty groups use 0.5. No outcome-driven cuts or tuning.
   Return to home orientation. Rates below 50%, if any, are permitted.
   An exactly 50% parent forecast remains 50%.
2. Symmetric isotonic probability calibration: fit home p->home outcome with
   mirrored (1-p, 1-y) pairs, each orientation weighted 0.5 per original game.
   Increasing fit, out-of-training-range predictions clipped to the nearest
   endpoint. Fixed probability bounds [.005,.995] prevent endpoint log losses.
   This is a standard monotone step/linear-interpolation calibrator; it is
   not guaranteed to produce a perfectly smooth curve. Mirrors do not increase
   the number of independent games.

Primary period: 2023-25 (815 decisive games), primary metric binary log loss.
Secondary proper score: Brier loss. Report confidence-bin ECE descriptively;
ECE depends on grouping and does not isolate general forecasting improvement.
Compare four challengers with current v1.18 and no-vig market probabilities.
Keep 2026 W1-5 (78 decisive games; five week blocks) separate as a diagnostic.
No current-season outcome enters that season's mapping. No annual recipe
selection or profit/ATS tuning. No production changes.

Uncertainty: 10,000 paired whole-week bootstrap draws stratified by season,
seed 20261017, conditional on fitted paths. Show 95% descriptive intervals and
99.375% intervals as an eight-primary-comparison Bonferroni sensitivity check.
These do not adjust the wider prior research history, uncertain source vintage,
or refitting uncertainty. A replacement is not supported unless primary log-loss
gains over both current v1.18 and market have positive adjusted lower bounds.
Brier results, annual stability, and 2026 diagnostics inform interpretation.

Deliverables: code, source ledger and hashes, annual fits and probability maps,
per-game predictions, proper scores, calibration tables, paired comparisons,
current-board counterfactuals and a concise report. No wagering recommendations.

Repository integration: ROI is additionally reported on each identical decisive-game cohort, with 1 SE, market-correct null and an explicitly common-row favorite control. This descriptive addition does not change candidates, fits, proper-score selection or the previously reported conclusion. The NumPy weighted PAV implementation reproduces the independently checked monotone reference without adding a dependency.
