# H15: do the model's small favorites beat their moneyline?

Pre-registered in research/PREREGISTRATION.md (2026-10-28). Legacy moneyline research; nothing is published. Rows: first v1.18 pregame snapshots with |raw spread| < 3, decided games only.

**Primary (snapshots from 2026-10-29 00:00 UTC): interim (n = 0 < 150 games): no verdict.**

- no graded rows

Diagnostic, exposed and never pooled with H15:

- 2026 snapshots before the cutoff: n = 17; won 64.7% vs moneyline 57.2% and model 55.8%; excess +0.075 +/- 0.118 (1 SE). Win log loss: moneyline 0.6512, model 0.6753, soft band 0.6541, hard band 0.6544. 1u on the model's side +1.38u, ROI +8.1% +/- 20.1 (null -4.2%; same-row market favorite +1.34u)

Reproduce: `python -m research.h15_small_favorites`
