# R003 plain: loss audit and shortcomings

This analyzes **direct_ref_h2_t3_p0**, the plain observed-outcome model developed
for the owner's R003 market-context hypothesis: spread bandwidth 2, total
bandwidth 3, no global backoff or schedule/travel additions. It is separate
from the original R003 possible-score support mask and the production model.
These are frozen retrospective walk-forward research records, **not native
forward-ledger observations**. All slices below are post-hoc diagnostics.

## Financial result and what caused the difference from market favorites

| Basis | Bets | W–L–P | Plain units | ROI ± SE | Same-row favorite | Market null |
|---|---:|---|---:|---:|---:|---:|
| 2023–25 | 812 | 552–259–1 | −4.210 | −0.52% ±2.48 pp | +0.180u | −4.10% |
| 2017–22 development | 1,559 | 1,026–526–7 | −64.543 | −4.14% ±1.79 pp | −59.214u | −2.61% |
| 2026 diagnostic | 79 | 50–28–1 | −3.703 | −4.69% ±8.22 pp | −3.703u | −4.10% |

There are 816 forecast games in the main period. Four moneyline pick'ems are
excluded from the betting comparison. Returns include tie pushes; conditional
winner proper scores exclude ties. ROI uncertainty is substantial: main 95%
paired whole-week interval **[−5.38%,+4.49%]**. The market-correct null is negative
by the quote hold; losing money alone does not establish performance below it.

Plain and the favorite choose the same side on **805/812 bets (99.1%)**. Those
bets return **−1.710u for both**. The **seven disagreements** return **−2.500u**
versus **+1.890u** for favorites, accounting for the entire **−4.390u** gap.
Plain wins two of those seven; favorites win five. The paired ROI gap is −0.54
percentage points, interval **[−1.56,+0.50] pp**: unresolved, not proof that
every future disagreement should be suppressed.

| Season | Bets | Plain units | Same-row favorite units |
|---|---:|---:|---:|
| 2023 | 270 | +1.622 | +4.119 |
| 2024 | 271 | +12.216 | +14.109 |
| 2025 | 271 | −18.047 | −18.047 |

The net main-period loss is driven by 2025, when **every eligible plain bet
matches the favorite**. Those losses cannot be attributed to a distinctive
travel adjustment or contrarian plain-model pick. Probability quality can still
differ even when the bet side is identical.

## 1. The betting rule often contradicts the model's own price assessment

The recorded rule chooses the more likely winner using probability >50% and
bets 1u. It does not require that probability to beat the offered price.
For win profit b, conditional expected units are `p*b-(1-p)` and the break-even
probability is `1/(1+b)`, which can be much higher than 50%.

**567/812 bets (69.8%) have nonpositive expected value under plain's own
probabilities.** Across all bets its own conditional expected units sum to
**−28.692u**, while realized returns are −4.210u. The headline bet policy is
therefore capable of losing even if plain's probabilities are accurate.
These conditional quote calculations follow the repository convention;
realized ties push and are not forced into binary calibration.

Expensive favorites show the practical consequence. Bets at **−250 or shorter**
return **−15.004u on 309 bets**, with exactly the same returns for market
favorites. Their decisive-game win rate is **76.3%**, while the average quoted
break-even probability is about **80.1%**. High hit rate is insufficient at those
prices. This bucket made +8.099u in 2017–22, so its recent loss is not an
independently validated reason to exclude that entire price range.

## 2. Apparent value is less reliable than overall calibration suggests

Looking at all decisive eligible bets, plain predicts 65.9% picked-side wins
and observes 68.1%. That does **not** support a blanket overconfidence claim.
The more revealing conditioning is where plain itself claims positive value:

| Positive-EV subset | Bets | Plain win probability | Market fair probability | Actual decisive win rate | Predicted units | Actual units |
|---|---:|---:|---:|---:|---:|---:|
| 2023–25 | 245 | 65.70% | 60.59% | 61.63% | +10.442 | −7.991 |
| 2017–22 | 441 | 70.75% | 66.43% | 66.82% | +16.944 | −12.064 |

The four-point optimism repeats across both exposed periods, while market
probabilities are closer to observed frequencies. This is consistent with
noisy departures from the market being mistaken for value. The main
calibration-residual interval is **[−9.41,+1.13] pp** and the earlier-period
interval **[−8.23,+0.27] pp**, so neither individually resolves the discrepancy.
These forecasts and subsets are not independent fresh confirmation.

The main positive-EV subset returns −3.26% ±5.07 pp SE, versus −3.601u from
same-row favorites and a −4.13% market null. A simple positive-EV filter thus
does not repair these historical results. Probability calibration must earn
trust before an apparent price edge is treated as actionable.

## 3. Moneyline information is omitted from the distribution's conditioning

The plain distribution is weighted by signed spread, total and time, not the
actual moneyline probability. Moneylines are used for settlement and baseline
comparison afterward. Thus it can miss information or price distinctions in
moneylines even when a game has a similar spread and total.

On **815 decisive main-period forecasts**, winner log loss is **0.612332 for
plain versus 0.608072 for the no-vig moneyline**. Gain is −0.004260 nats/game,
95% paired week interval **[−0.010101,+0.001675]**. Brier is also slightly worse
(0.212262 vs 0.210334). Each of 2023–25 has a negative point estimate, as does
the separate 2017–22 block. Superiority or inferiority is not resolved by the
main interval, but there is no established incremental winner edge.

This is not solely a handful of spectacular upsets: the ten largest negative
proper-score contributions account for only **10.7% of gross negative
contributions**. All individual contributions are retained, including games
where plain earns money but assigns a worse probability than the market.

## 4. Thin extreme-market contexts can create fragile picks

Rebuilding the unchanged plain weights reveals that removing a single source
game can flip **six of the seven** main-period favorite disagreements. This is
an influence diagnostic, not a forecast confidence interval or a fitted deletion
rule. Among the 805 same-side bets, only four have that property.

Disagreements have median effective support **34.3**, versus **216.8** for
agreements. All seven have totals **38.5 or lower**. Plain has zero global
backoff and no minimum-support fallback of its own; its p0 setting does not
inherit SC1's sparse-context protections.

One example is **2023 W18 NYJ at NE**: only **8.44 effective source games**;
one 2022 NO–CLE score pair receives **26.1%** of total weight. Plain gives NYJ
62.9% versus market 43.7%, and deleting one source can reverse its pick.
NYJ actually wins, illustrating why fragility does not mean every affected bet
loses. Indeed, the nine bets with ESS <=25 return +1.894u versus favorite
−2.606u. A support filter is not validated merely by identifying uncertainty.

Finite bandwidths also pull the source market contexts toward common totals.
For target totals <=35, source totals average about **3.81 points higher**;
for target totals >50, about **2.16 points lower**. This is a context-matching
boundary issue, not proof the score mean should equal the betting total
(a market total is not an exact mean constraint). Detailed source-weight and
mean-decomposition checks are retained in `source_influence.csv`.

## 5. Raw context losses do not establish missing schedule effects

On the main sample, totals <=40 lose −8.331u versus favorite −3.941u; the
entire model/favorite gap sits there. But in 2017–22 that same total band
returns −4.388u versus favorite −13.442u. The relative result reverses.
The profitable recent 45–50 total bucket also loses money in the earlier block.

MNF loses −7.132u on 60 bets, **identical to favorites**; TNF returns +2.528u
on 51 bets, also identical. Eastward travel returns +5.009u on 107 bets,
again identical to favorites. Such slices describe market-wide outcomes as well
as the model. They do not establish a missing temporal/travel correction.
All slot, rest, venue, phase, travel, price, confidence and support slices are
retained, including small or contradictory groups.

The broad distribution is not obviously collapsing: nominal 90% margin/total
intervals cover **90.3%/90.6%**; predicted 3-point margin frequency is
14.64% versus observed 14.22%, and 7-point frequency 7.83% versus 8.33%.
These aggregate checks can hide conditional errors, but they do not support
replacing observed score support as the first response to moneyline losses.

## Recommended next tests

1. **A coherent moneyline anchor with uncertainty-aware shrinkage.** Adjust
   decisive home/away probability mass toward same-time no-vig moneylines while
   preserving each within-outcome empirical score distribution and tie handling.
   Fit shrinkage only on earlier winner log loss; compare with both plain and
   moneyline alone. Require gains beyond moneyline, conditional value calibration,
   and fresh forward evidence before claiming a betting edge. Matching the
   market more closely by itself does not establish profitability.
2. **A separately fixed market-context boundary correction.** Test nonnegative
   reweighting that better balances historical spread/total contexts against the
   target, keeping every atom an observed score pair and using an explicit
   fallback where support is inadequate. Judge distribution proper scores,
   stability and source leverage; retain plain and all unfavorable results.

These are hypotheses, not implemented/adopted rules. The strongest current
shortcomings are price-insensitive betting, unreliable claimed value and
fragility in sparse market extremes. The audit does not establish a specific
missing football feature as the cause of loss.

## Reproduction and integrity

`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/plain_loss_audit.py`

`bet_ledger.csv` is a **research backtest view**, not the append-only live ledger.
It retains all 2,450 eligible bets across the separate 2017–2026 bases. Main
losses, all seven disagreements, full proper-score contributions, subgroup
denominators, value-claim calibration, source influence, shape checks and input
hashes accompany this report. Bootstrap: 10,000 paired whole-week draws within
season, seed 20261016, conditional on frozen forecast paths. Many post-hoc
slices have no multiplicity-corrected qualification; quote timestamps and
historical schedule availability remain unaudited.

No model, forecast, bet policy, production file or forward-ledger row was changed.
