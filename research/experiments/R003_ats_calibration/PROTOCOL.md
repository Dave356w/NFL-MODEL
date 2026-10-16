# R003-AC1: chronological ATS probability calibration and stable selection

Locally frozen before fitting/scoring this new family. The user explicitly
requests ATS improvement at -110 each side. Prior ATS losses and calibration
gaps are exposed; every historical season is development, not fresh evidence.
No ROI optimization, threshold search, production change or wager is authorized.

## Inputs and chronological fitting

Plain is unchanged MC2 direct_ref_h2_t3_p0. Read its 2017+ frozen predictions
from PT1; reconstruct 2015–16 prior-week predictions from unchanged R000 inputs
to obtain earlier OOF calibration examples. Each base forecast uses earlier
weeks only, current plus five earlier seasons and two-season time decay.
Use signed spread, total, effective sample size and raw conditional home-cover
probability only. Binary labels are home margin > spread; actual pushes are
excluded from calibration fitting/proper scores and refunded in settlement.

For each forecast week, calibration trains only on prior-week OOF records from
current plus five earlier seasons; time half-life 38 weeks. At least 300
decisive examples spanning two seasons; otherwise predict 0.5. Use time weights
normalized then multiplied by Kish ESS. Target outcomes never enter prediction.

## Six fixed calibration variants and controls

Raw logit z uses conditional cover probability clipped to [1e-6,1-1e-6] for
predictors only; raw baseline endpoint losses remain exact. Candidates:

1. Temperature: logit(p_cal)=beta*z, beta constrained to [0,1].
2. Platt: intercept + beta*z, beta in [0,1].
3. Context: intercept + beta*z + c*s + d*t + e*s*t + f*z*50/(ESS+50),
   s=spread/7, t=(total-44)/7, beta in [0,1]. Other coefficients unrestricted.

Each uses ridge 10 or 100 toward zero for all non-intercept coefficients;
intercept penalty is 100. Minimize weighted summed binary log loss plus
half penalty. Zero coefficients mean the market's conditional 0.5 ATS baseline.
Analytic gradient, zero start, L-BFGS-B, gtol 1e-7, ftol 1e-12, maxiter 1000,
maxls 100 (numerical amendment described below);
fail on optimizer failure. Also retain raw and fair-0.5 controls.

Retain raw push mass. New unconditional home/away cover masses are
(1-push)*p_cal and (1-push)*(1-p_cal). At the quoted line, rescale each of the
three groups' historical score weights to those masses. Within-group shapes
and observed paired-score atoms are retained; no score synthesis or translation.
If positive target mass lacks a historical source group, use raw and pass that
calibrated offer. This is one coherent distribution per game at its forecast
line, not independently calibrated alternative lines. Grade other distribution
markets descriptively, without silently changing their models/defaults.

## Selection rules, fixed before results

At -110 per side risk 1u; win profit 10/11, push zero. Raw/fair controls and
each calibration get two separately reported rules:
- EV: choose the greater strictly positive cover*(10/11)-loss, else pass.
- Stable: same, but require raw market-context ESS >=50 and positive EV on the
  SAME side under both the full calibration and one refit excluding the most
  recent available training season. Fallback fair predictions give no support.
  This is a sensitivity check, not a confidence interval. Raw's second forecast
  is raw, so its stable control is an ESS guard only; fair always passes.

Annual model choice from fair first, raw, then six calibrations uses mean cover
log loss on strictly earlier OOF seasons starting 2017, minimum two seasons;
thus selected paths start 2019. Exact ties choose fair first. Recipe selection
never sees ROI. Primary selected policy is Stable; EV is a fixed secondary
decision policy, not chosen from its observed ROI. All fixed variants retained.

## Evaluation, uncertainty and advancement

Main: same 816 games 2023–25. Separate common development 2019–22 and 2026
diagnostic. Earlier 2017–18 fixed-arm predictions feed annual choice but are not
mixed with the common selected-policy development population. Report annual
choices, fit/cutoff audits, all-game cover log loss/Brier/calibration, within-bet
predicted/realized cover rate, units, ROI +/- SE, same-row spread-favorite
control (home at zero), pass counts and push-adjusted 50/50 negative-hold null.
Also paired per-calendar-game returns against raw EV, counting passes as zero.

10,000 whole-week paired draws within season, seed 20261016. Ordinary 95%
intervals and 99.642857% sensitivity (14 non-fair fixed policies; the two derived
selected paths use the same sensitivity).
These condition on fitted forecasts and do not correct all earlier research.
Fair-control pass-only cohorts have undefined per-bet ROI, not positive evidence.

Retain an ATS-edge hypothesis only if selected Stable has >=200 main bets,
>=50 bets in each primary season, positive units in all three years, ROI lower
bound >0 under both intervals, all-game cover-log-loss gain vs fair >=.0005
and vs raw >=.002 with positive ordinary 95% lower bounds, and integrity passes.
Improved calibration or avoiding losses by passing is useful but is not an edge.
Even a historical gate pass still requires separately registered fresh forecasts
and contemporaneous actual prices before any established/executable-edge claim.

No historical line timing is certified; uniformly -110 prices are the user's
scenario assumption. Tests must cover gradients, calibration recovery, shrinkage,
future/target-label rejection, minimum-data fallback, same-side stability gate,
push/half-point settlement, annual selection and coherent observed-atom weights.
Independently reproduce outputs and preserve original files and ledger.

## Numerical amendment after the aborted first run

Before any comparison report was produced, the initial run stopped at 2018 W10
Platt/ridge10 full calibration: L-BFGS-B's default 20 line-search steps returned
ABNORMAL at a boundary slope of zero, intercept gradient 1.39e-6. Increasing
the line-search limit to 100 returns successful relative-objective convergence
at the same coefficients (objective change -1.14e-13). Retain that limit for all
fits. Objective, predictors, penalties, tolerances, selection and all performance
gates are unchanged. Failure still aborts; no window or candidate is discarded.
This computational repair is recorded after fitting began and is not claimed
as part of an untouched preregistration.
