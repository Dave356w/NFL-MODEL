# Earlier-season calibration follow-up

2026-10-12 research protocol, specified before executing this follow-up. The design follows exposed favorite-band diagnostics, so all 2023–2025 comparisons remain historical development.

Reconstruct exact v1.16 weekly predictions from frozen pregame features for 2021–2025. For every game, coefficient fits use strictly earlier weeks. Reproduce committed 2023–2025 production probabilities within 1e-7. All secondary calibration fits and scale selections for season Y use only OOF forecasts and outcomes in seasons <Y; no calibration on evaluation-season outcomes.

Compare unchanged production, no-vig market, global market-offset recalibration, close-game-only recalibration and prior-season correction-scale selection. Recalibration is sigmoid(logit(q)+a+b*(logit(p)-logit(q))), normalized earlier-season log loss with fixed .01 ridge toward a=0,b=1, and a fixed two-season age half-life. The close-only arm fits/applies only where max(q,1-q)<.60 and leaves other probabilities unchanged. Selection chooses among correction multipliers 0,.25,.5,.75,1,1.25 by earlier-season log loss; tie-break prefers 1 then the smaller multiplier. No return-driven choice.

Report paired LL/Brier and 95% week-cluster intervals, simultaneous intervals for three challenger comparisons, annual and 50–60% strata, historical same-row return diagnostics, source cutoffs, exact-production reproduction and sensitivity excluding largest contributions in the close band. The fixed calibration penalty/scale grid are research choices; this tests them, not an optimized calibration system. No production or ledger writes. A favorable result would nominate an untouched forward experiment, not establish a new edge.
