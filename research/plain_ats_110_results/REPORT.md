# R003 plain ATS at assumed −110 each side

**Retrospective scenario, not verified historical spread quotes or forward evidence.**
Plain probabilities are unchanged. No thresholds are searched or fitted.

Risk 1u; a win earns 10/11u, a loss costs 1u, a push refunds the stake.
EV(home)=(10/11)*P(home cover)−P(away cover); reverse for away.
Bet only if the selected conditional-on-no-push cover probability exceeds 11/21 = 52.38095%; otherwise pass.

| Basis | Bets | Passes | W–L–P | Units | ROI ± SE | Same-row spread favorite | Fair ATS null |
|---|---:|---:|---|---:|---:|---:|---:|
| 2023-25 | 560 | 256 | 270–278–12 | -32.545 | -5.81% ±3.99 pp | -0.091u | -4.45% |
| 2017-22 | 993 | 574 | 498–472–23 | -19.273 | -1.94% ±2.99 pp | -110.909u | -4.44% |
| 2026 diagnostic | 61 | 18 | 31–25–5 | +3.182 | +5.22% ±11.74 pp | -6.364u | -4.17% |

Main ROI 95% week-bootstrap interval: [-0.1278006364428317, 0.008864161072145816]. Mean predicted conditional cover probability 56.25%; realized 49.27%.
Selected-game cover log loss 0.702998, versus 0.693147 for a fair 50/50 ATS forecast.

Capability to choose a side does not establish calibrated cover probabilities or profitable value. Frozen retrospective line timestamps remain unaudited. This extends the user-specified price scenario to historical lines; it does not certify that both historical offers were available together at -110.

Moneyline records, original experiments, production and the forward ledger are unchanged. No wagers or live predictions are emitted.

Reproduce: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/plain_ats_110.py`
