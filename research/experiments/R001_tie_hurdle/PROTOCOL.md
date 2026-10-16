# R001 - Prior-week tie hurdle calibration

Registered before computing candidate forecasts on 2026-10-16. This is a
result-inspired historical development experiment, NOT an independent held-out
validation: the supplied October 16 report already exposed all evaluation years
and its excessive tie forecasts motivated this hypothesis. Fresh forward data
are required to validate the hypothesis independently.

## Hypothesis and fixed specifications

Replacing the excessive tie mass with a training-only tie frequency will improve
joint-score NLL while preserving coherent joint probabilities. This tests tie
versus decisive-result mass calibration, NOT a mechanistic overtime simulator.

Locked primary baseline: empirical__A_market from the supplied fixed experiment.
Candidate: retain its conditional joint distributions within diagonal and
non-diagonal cells; set diagonal total mass to p=(T+0.5)/(N+1), the Jeffreys
Beta(0.5,0.5) posterior mean from completed eligible training games in the same
six-season window (current and five earlier seasons), strictly before the
forecast week. Unweighted tie counts; no smoothing/decay selection. Non-diagonal
mass is 1-p. This preserves conditional decisive-game winner probabilities.
No rule lookup, external outcomes, or quote revisions are introduced.

Exactly the same transformation of smooth__A_market is one prespecified
secondary transportability check, never an alternative primary winner.
All residual-feature arms remain unchanged and archived; no new residual model.
No parameter grid, validation-based parameter selection, or ROI selection.

## Samples, scoring and uncertainty

Training begins 2013; base mean fits/prequential covariance as originally fixed.
2017-2022: supplementary exposed development; 2023-2025: 816 historical evaluation
games; 2026 W1-5: separate 79-game diagnostic. Weekly refits can use earlier
weeks within an evaluation season; no within-week outcomes may enter.
No independent validation/test set exists in this snapshot. No selection split
is required for fixed parameters. Prediction cutoff is logical prior-week only;
historical quote capture timestamps remain UNKNOWN.

Primary: paired baseline-minus-candidate joint NLL on empirical market-only,
whole-week bootstrap stratified within season, 10,000 draws, seed 20261016,
95% interval for the single new primary contrast. Also give conservative
99.2857% sensitivity interval for seven contrasts (six old plus this new one);
this does not account for unrecorded earlier research exposure. All other
metrics/intervals, including smooth, are descriptive; no secondary significance
or ROI may qualify the candidate.

Report all four marginal NLL/CRPS, team averages, conditional winner LL/Brier,
unconditional H/T/A LL/Brier, tie LL/Brier, nonpush spread/total scores,
50/80/90% coverage and width, winner/tie/spread/total reliability, midpoint PIT,
season and leave-one-week-out stability, largest influences, prior cutoff audit,
normalization and conditional-win invariance. Moneyline flat 1u side selection
and favorite/underdog/hold controls are independent diagnostics only. No priced
spread/total/team-total ROI is valid without those price fields. Derived team
locations may be used for threshold diagnostics, never called traded quotes.

## Decision rule

Consider further research if primary gain is >=0.005 nats/game, 95% lower bound
>0, all three annual point gains positive, no secondary marginal NLL or CRPS
increase >0.01, and no conditional winner degradation. Exposed results alone
cannot satisfy independent validation. Default recommendation is retain for
research with a locked fresh forward protocol, never production promotion.
A failed rule is recorded as reject or unresolved; do not revise this candidate
against these outcomes. Next hypothesis receives a new ID and fresh evaluation.
