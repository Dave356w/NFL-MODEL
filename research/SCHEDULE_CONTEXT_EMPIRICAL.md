# Does schedule, rest or travel improve the market-context model?

**No qualified improvement in this test.** Six feature groups and two combination
methods were evaluated at shrinkage K=30 and K=100, preserving the plain model
as a candidate in every earlier-season selector. No production change follows.
This is exposed historical development, not an independent forward result.

## What was added

- Kickoff slot: TNF, Thursday daytime, MNF, SNF, Sunday early/late, other.
- Both teams' rest: <=6 days, 7–9, >=10, plus the rest-day advantage class.
- Away-team home-base to home-venue time-zone direction: east/west >=2 hours
  or smaller shift. This is not actual travel itinerary/acclimation.
- Home/away body-clock kickoff bands and home venue time-zone region.
- Early/mid/late/final-week season phase as a separately tested temporal group.

ZoneInfo handles DST and Arizona, and LA/St. Louis relocations are explicit.
Neutral games fall back for venue, travel and kickoff-clock features because
the pack does not provide reliably audited venue-local timing. Rest and season
phase can remain usable. No weather, team identity effect or actual resting
starter information was added. Historical calendar and price snapshots are not
timestamp-certified; future schedule/line revisions remain a limitation.

## Shrinkage to the plain empirical distribution

The plain distribution is MC2's observed-score kernel with spread bandwidth 2
points and total bandwidth 3, using strictly earlier weeks. For each feature,
match historical games on that feature while retaining the market-context
weights. Relevant support is the smaller of matching Kish ESS and the plain
ESS multiplied by matching probability mass. This prevents many distant games
with tiny market relevance from receiving undue trust.

Below **20 effective relevant games**, or if a target feature is unknown, use
plain exactly. Otherwise mix:

`P = (1-alpha) * P_plain + alpha * P_matching_context`

`alpha = relevant_support / (relevant_support + K)`

For K=100, support 25 gives 20% context / 80% plain; support 100 gives 50/50.
The shrinkage creates no new score combinations. Joint matching requires all
six context keys; additive pooling averages the six already-shrunk distributions
without pretending their correlated evidence consists of extra independent games.

## Results: 816 games, 2023–25

Positive CRPS gain means a better margin/total distribution than plain. These
fixed-arm intervals are descriptive, without full adaptive-research correction.

| Feature, K=100 | CRPS gain | 95% paired week interval |
|---|---:|---|
| Travel direction | +0.007068 | [−0.003844,+0.017697] |
| Body clock | +0.003923 | [−0.007787,+0.015324] |
| Both teams' rest | +0.002462 | [−0.007057,+0.011549] |
| Kickoff slot | −0.000379 | [−0.011186,+0.010958] |
| Venue time-zone region | −0.006447 | [−0.017643,+0.004953] |
| Season phase | −0.017740 | [−0.030412,−0.005237] |

The season-phase loss interval excludes zero nominally but not under the
16-challenger sensitivity adjustment. The positive travel/rest/clock averages
do not resolve superiority, and travel is the strongest point estimate only
after looking at these outcomes.

The primary all-family rule chooses settings using **earlier seasons only**.
It selects plain in 2023 and strong-shrinkage joint context in 2024–25. Its gain
is just **+0.001075**, interval **[−0.000235,+0.002714]**, below the registered
0.01 practical threshold. The 16-challenger sensitivity interval also includes
deterioration. None of the individual feature-family selectors chose an addition
over plain in 2023–25. Do not retrospectively replace them with the best fixed arm.

Main moneyline results are unchanged: **−4.21u on 812 bets, ROI −0.52% ±2.48 pp
SE**, same-row favorite +0.18u, proportional market-correct null approximately
−4.10%. On separate 2017–22 development, the selector is slightly worse than
plain (−65.94u vs −64.54u). On 2026 W1–5 the bets remain unchanged. No spread
or total ROI is claimed because actual two-sided offered prices are missing.

## How sparse are the requested contexts?

For K=100 on the main sample:

| Context | Games | Median relevant support | Exact plain fallback |
|---|---:|---:|---:|
| TNF | 51 | 10.1 | 98.0% |
| MNF | 61 | 14.7 | 93.4% |
| SNF | 54 | 15.6 | 83.3% |
| Sunday early | 395 | 103.1 | 4.1% |
| Eastward >=2 zones | 108 | 26.2 | 27.8% |
| Westward >=2 zones | 111 | 25.8 | 31.5% |
| Away early body clock, home afternoon | 90 | 19.6 | 52.2% |

Full six-way intersections fall back on **98.2%** of games. Therefore this
experiment has little power to identify a TNF-specific, MNF-specific or detailed
travel/rest/slot intersection effect. “No qualified improvement” is not proof
that the underlying football effect is zero. Market prices may already absorb
much of it, and a fine-grained empirical conditional distribution needs many
more matching games than a pooled effect model would.

Keep plain as the default research distribution. Retain strongly shrunk travel
as a separate hypothesis; do not adopt it from its historical rank. A future
continuous/hierarchical rest/travel model could borrow evidence more efficiently,
but that requires a new fixed design and evaluation, not lowering the support
threshold after seeing these results.

**Executed follow-up:** [PT1 pooled travel](POOLED_TRAVEL_EMPIRICAL.md) now tests
that shared-evidence approach with four fixed regularized score-shape models.
It increases usable support but produces no qualified gain; all four slightly
worsen primary CRPS. Plain remains the recommendation.

## Reproduce

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/schedule_context_empirical.py
python research/review_schedule_context.py
python -m pytest tests/test_schedule_context_empirical.py -q
```

The [full report](experiments/R003_schedule_context/REPORT.md) contains all 16
challengers, family selectors, coverage/width, category slices and paired
uncertainty. Feature table, per-game predictions, cutoffs, support/fallback,
protocol/source/input hashes and independent reproduction are retained alongside it.
