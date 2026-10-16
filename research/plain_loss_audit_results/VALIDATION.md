# Plain loss audit validation

- Full repository suite: **659 passed, 1 xfailed** (58.72 seconds).
- Five new tests cover payout arithmetic, negative EV despite >50% win
  probability, tie/pick'em denominators, corrupt records, source alignment,
  single-source influence and the exact mean decomposition.
- Separate-process reproduction matches all **11 numerical artifacts byte for
  byte**; the explanatory report is manually written from those artifacts.
- Reconstructed main-sample plain probabilities match stored values within
  1e-14, and the source-weight margin decomposition matches within 1e-12.
- The research backtest view contains **2,450 unique eligible games** across
  separately reported periods; the main period has 259 losses, seven favorite
  disagreements, and six disagreements sensitive to one source deletion.
- All **192** original protected experiment/production-data hashes remain
  unchanged. All audit source/input hashes, including the native forward
  ledger and its report, remain unchanged.
- Notebook already synchronized; **43 data files OK**; `git diff --check` passes.

No candidate was fitted, probability updated, forecast emitted, betting rule
adopted or forward-ledger row modified. All subgroup observations are post-hoc;
reproducibility does not turn them into independent predictive validation.
