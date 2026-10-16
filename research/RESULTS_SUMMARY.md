# NFL research iteration 2 - October 16, 2026

**Market-only benchmark separation:** [analysis](spread_signal_separation/REPORT.md)
shows substantial spread signal: main margin MAE 9.744 versus spread-free
11.098; spread-only winner LL .607050 versus home-rate .690352. Plain adds
no demonstrated information (MAE9.835, winner LL .612332); AC1 returns closer
to market baselines without surpassing them. Plain's existing 560 ATS bets
lose 8u at even money plus 24.545u in −110 payout reduction. Moneyline market-
only benchmarks and matched favorite/null controls are reported separately.

**ATS improvement experiment:** [R003-AC1](ATS_CALIBRATION.md) calibrates raw
cover probabilities using strictly earlier OOF outcomes, with six fixed settings,
fair/raw controls and an earlier-cover-log-loss selector. Main selected loss
improves .700040 → .693345 but remains slightly worse than fair .693147.
Both selected ATS policies make zero bets at assumed −110, so no edge is
established. All active fixed calibrated variants lose in 2023–25. The coherent
selected score distribution also improves margin/total CRPS to 7.182768;
probability repair and profitable betting remain separate conclusions.

**Plain loss audit:** [descriptive findings](plain_loss_audit_results/REPORT.md)
analyze MC2 direct_ref_h2_t3_p0, not the original R003 support mask or native
forward ledger. Of 812 main bets, 805 match favorites; seven disagreements
explain the full −4.390u relative shortfall, and six can flip after deleting one
historical source. About 70% of bets have nonpositive EV under plain's own
probabilities. Its positive-EV subset is about four points optimistic on win
frequency in both exposed periods, with uncertainty spanning zero. No model
or betting rule changes follow; price-aware calibration and source stability
are stronger next hypotheses than adopting a favorable raw context slice.

**Pooled travel follow-up:** [R003-PT1](POOLED_TRAVEL_EMPIRICAL.md) increases
usable travel support by sharing a regularized score-shape relationship across
market contexts. All four fixed variants slightly worsen distribution CRPS.
Earlier-season winner-log-loss selection yields CRPS gain −0.002723,
95% [−0.008766,+0.003291]; winner-score gain remains unresolved. Main moneyline
returns worsen to −6.057u from plain −4.210u on 812 bets, versus +0.180u for
same-row favorites. No qualified improvement; no production/default change.

**Schedule/location follow-up:** [R003-SC1](SCHEDULE_CONTEXT_EMPIRICAL.md)
tests kickoff slot, rest, travel direction, body clock, venue region and season
phase, with sparse contexts shrinking to the plain MC2 empirical distribution.
The earlier-season-selected rule gains only 0.001075 CRPS on 2023–25
(95% interval [−0.000235,+0.002714]); no qualified improvement. Moneyline bets
remain −4.21u on 812 bets (−0.52% ROI), versus +0.18u for same-row favorites.
Travel has the strongest positive descriptive estimate, but remains unresolved.
TNF/MNF fall back to plain on 98.0%/93.4% of games, limiting conclusions about
their effects. These remain exposed historical development results.

**Owner-intent market-context follow-up:** [MC1/MC2](MARKET_CONTEXT_EMPIRICAL.md)
use observed historical score pairs qualified by spread/total, without a Gaussian
or possible-score enumeration. Across 20 fixed settings in two declared batches,
the refined direct model improves its earlier direct version but still trails
original R003 (CRPS 7.21413 vs 7.17691). The separate relative-score variant
scores 7.15332, with unresolved improvement and distorted key-number/tie shape.
Both fail advancement; moneyline returns remain negative, with no ATS price claim.
All preceding R003/RF1 findings below are preserved.

**Subsequent R003-RF1 extension:** [executed results](experiments/R003_rare_frequency/REPORT.md)
improve joint NLL 7.125085 → 7.096967 (+0.028119, 95% [0.024775, 0.030384])
using one prior-week learned rare-score penalty. **Do not advance:** margin CRPS
worsens 7.112870 → 7.126421, exceeding the locked 0.01 tolerance; winner/cover
proper scores also worsen slightly. The 812 2023–25 moneyline bets remain
−0.9055u, −0.11% ±2.47 pp versus +0.1801u for favorites and a −4.10% null.
These are exposed development results. Original R000–R003 results below remain
unchanged; RF1 is a distinct research arm, not a replacement or production update.

**Retain R002 for research; reject advancement of R003.** Both protocols were
committed in efbbeef before either new candidate was executed. They were run
sequentially, with R002 reported/tested before R003 execution. These are exposed
historical diagnostics, not independent test sets or prospective results.

## Completed experiments and primary comparisons

All comparisons use the same 816 2023-25 regular-season games, 272 per season.
Positive gain means baseline joint NLL minus candidate NLL. The adjusted
intervals have nominal 97.5% coverage each for two new primary contrasts.

| Experiment | Primary empirical comparator | Baseline NLL | Candidate NLL | Gain | Adjusted interval | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| R002 terminal OT-inspired transport | R001 tie hurdle | 7.106782 | 7.099695 | +0.007088 | [0.003099, 0.011391] | Retain for research |
| R003 joint score support | Raw market-only A | 7.125372 | 7.125085 | +0.000286 | [0.000253, 0.000325] | Reject advancement |

R002-versus-raw-A descriptive joint gain is +0.025677. R003 is independent of
R001/R002; it is not a combined model. Smooth counterparts, every season and
every unfavorable metric are retained in their separate experiment directories.

Bootstrap: 10,000 paired whole-week resamples within season, seed 20261016.
R002 ordinary 95% interval [0.003590, 0.010804]; nine-contrast sensitivity
[0.002228, 0.012436]. R003 ordinary 95% [0.000257, 0.000319]; sensitivity
[0.000246, 0.000338]. The finite-family adjustments do not erase prior research
selection. Intervals condition on existing forecast paths without refitting
training windows. No ROI, parameter grid or test result selected a specification.

## R002 method, evidence and limits

Starting with raw A, use R001's unchanged prior-week Jeffreys Beta(.5,.5) tie
rate over the current plus five earlier seasons. Replace the excess raw diagonal
mass's uniform decisive allocation with explicit equal-weight +2/+3/+6 terminal
increments, allocated to the home/away winner using the baseline conditional
win probability. Both final tie mass and conditional winner probabilities remain
identical to R001. Cap-boundary and near-cap mass handling is explicit and
logged; no probability mass is deleted or clipped into score 80.

The pack contains final scores only, with no regulation, overtime or possession
labels. A genuine regulation-to-overtime process is **not identifiable** here;
raw A already forecasts final scores including overtime. These are hypothetical
score-distribution corrections, not fitted overtime frequencies or a possession/
clock simulator. Rule sources are recorded in RULE_SOURCES.json; model weights
are fixed assumptions rather than rule-implied probabilities.

Annual primary gains: 2023 +0.005717; 2024 +0.011843; 2025 +0.003703.
All leave-one-week and leave-one-season estimates remain positive. However,
2024 contributes about 56% of pooled gain; excluding it leaves +0.004710,
below the pooled practical threshold. Top ten absolute influences contribute
8.24% of total absolute contribution. No material secondary tolerance is breached.

| Secondary empirical metric | R001 | R002 | Change |
| --- | --- | --- | --- |
| Team marginal NLL | 3.573044 | 3.573933 | Slightly worse |
| Team CRPS | 5.109106 | 5.110848 | Slightly worse |
| MOV CRPS | 7.112072 | 7.111436 | Slightly better |
| Total CRPS | 7.241027 | 7.241554 | Slightly worse |
| Conditional winner LL | 0.611353 | 0.611353 | Unchanged |
| Mean tie probability | 0.4195% | 0.4195% | Unchanged |
| MOV 90% coverage / width | 89.216% / 41.695 | 89.093% / 41.411 | Narrower, lower coverage |

The fixed historical primary gates pass, including gain >=0.005 and the positive
adjusted lower bound. Recommendation is **retain for research**, with a planned
fresh forward comparison. No mechanistic OT or betting-edge claim is justified.

## R003 method and rejection

Build additive joint scoring reachability from safety, field goal, touchdown,
try and opponent try-score generators, with side swaps. Condition raw A on this
fixed mask. Exactly 13 pairs are excluded; valid rare (6,1)/(1,6) and related
one-point outcomes remain. No marginal score-1 blanket ban, frequency weighting,
R001 tie correction, R002 transport or covariance change is used.

Every observed result is supported. Had a result been unsupported, the run would
have aborted, without an NLL floor or row deletion. Positive realized-outcome
NLL gain is exactly -log(1-removed_mass). Its small positive interval therefore
does not establish a learned scoring-frequency model. Gain 0.000286 is far below
the locked 0.005 threshold. Team/MOV/total CRPS and winner scores worsen slightly.
Reject advancement while preserving the small mathematically valid effect.

## Betting, calibration and prospective scope

Both empirical candidates happen to retain the original 812 hypothetical
moneyline picks: -0.9055u, -0.1115% ROI, SE 2.4716 percentage points. Same-row
favorites +0.1801u / +0.0222%; underdogs -89.8201u / -11.0616%; negative-hold
null about -4.0995%. R002 preserves winner scores exactly; R003 slightly worsens
them. No-vig moneyline comparisons remain separately reported. Missing actual
spread/total/team-total prices preclude their ROI evaluation.

All marginal and event probabilities come from each candidate's single joint
PMF. Reports include every marginal NLL/CRPS, winner/H-T-A/tie LL/Brier,
50/80/90 interval coverage and width, reliability bins with uncertainty,
midpoint PIT, paired metric intervals, seasons and influential observations.
Only one primary-sample tie: calibrated rare-event performance remains uncertain.
Historical quote capture times remain unknown; actual pregame availability
cannot be certified. No prospective forecasts or quotes were captured.

## Tests, failures and reproduction

R002 passed 9 new transition tests and the 40-test combined suite before R003.
R003 passed 21 support tests. Final suite: **63 passed, zero current failures**,
including two serialization regression tests. R002 has 22 final output checks;
R003 has 20. Independent same-spec reruns reproduce predictions, audits,
provenance and all PMF arrays exactly. R000/R001 artifacts remain hash-identical.

One execution failure is preserved: R003's initial compressed predictions were
truncated, causing its first report and repeat byte check to fail. Other PMF/
audit/support results matched. Root cause was not established. The serializer
now verifies the complete compressed stream, fsyncs and atomically publishes it,
then validates the written bytes. No forecast specification or parameter changed.
R002 canonical CSV is identical before/after this engineering revision. The
corrupt output and logs remain in R003/failures/initial_write. All final CSVs pass.

Full production-repository tests and production data validation were not run;
this is an isolated research checkout. Prior 517-test statements remain prior
source evidence. No production forecasts, pages, existing betting ledgers,
original attachments or previously delivered R000/R001 results were changed.

## Recommendation and next iteration

R002 merits consideration for a **new locked forward comparison**, once quote
capture and independent timestamped retention are validated. Do not silently
alter the existing planned R001-F1 cohort. No activation or production promotion.
R003 fails the practical gate and is not advanced. Original residual-feature
negative findings remain unchanged in the registry.

Next priorities: obtain audited regulation/OT/possession labels before claiming
a mechanistic overtime model; register one football-score-frequency hypothesis
with fresh evaluation, rather than extending the support mask using these
outcomes. The code does not start another candidate automatically.

Reproduce from the bundle root after installing requirements:

```bash
OPENBLAS_NUM_THREADS=1 python research/distribution_ablations.py R002
OPENBLAS_NUM_THREADS=1 python research/distribution_ablation_report.py R002
OPENBLAS_NUM_THREADS=1 python research/check_ablation_determinism.py R002
OPENBLAS_NUM_THREADS=1 python research/distribution_ablations.py R003
OPENBLAS_NUM_THREADS=1 python research/distribution_ablation_report.py R003
OPENBLAS_NUM_THREADS=1 python research/check_ablation_determinism.py R003
OPENBLAS_NUM_THREADS=1 python -m pytest tests -q
```

The bundle includes updated EXPERIMENT_REGISTRY.md, RESEARCH_ROADMAP.md,
RESULTS_SUMMARY.md, VALIDATION.md; experiment-specific reports, metrics and PMFs;
new runner/report/reproduction modules; three new test modules; rule provenance,
source/input/protocol hashes and local branch history.
