# R002 brief finding

The fixed +2/+3/+6 terminal transport improves empirical joint NLL over R001:
7.106782 -> 7.099695; gain +0.007088 nats/game on 816 exposed 2023-25 games.
Paired season-stratified week-bootstrap 95% interval [0.003590, 0.010804];
two-new-contrast adjusted 97.5% interval [0.003099, 0.011391]. All three annual
gains are positive: 2023 +0.005717, 2024 +0.011843, 2025 +0.003703.

The narrow historical hypothesis passes its fixed gates. Recommendation:
**retain for research**. Exact-score concentration improves; conditional winner,
final tie probability, H/T/A calibration and moneyline bets are unchanged from
R001. Team NLL, team CRPS and total CRPS deteriorate slightly and remain below
the preregistered 0.01 materiality tolerance. These negative metrics are retained.

2024 contributes about 56% of pooled gain; excluding it leaves +0.004710, below
the pooled practical threshold although positive. Largest ten absolute game
contributions comprise 8.24% of total absolute contributions. Leave-one-week
means remain positive. This supports a fixed historical distribution correction,
not a mechanistic overtime model. No regulation/OT labels exist in the frozen
pack, so estimating actual overtime transitions remains blocked.

40 unit tests passed before R003; final combined suite has 63 passing tests.
22 current output checks pass. Independent rerun is exact; see
deterministic_reproduction.json. The serialization-only revision leaves its
canonical prediction CSV unchanged, as recorded in io_revision_validation.json. Quote timestamps are still
unknown and all outcomes are exposed. No prospective result or production
promotion. Next: execute separately registered R003 without modifying its design.
