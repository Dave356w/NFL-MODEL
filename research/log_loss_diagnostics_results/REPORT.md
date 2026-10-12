# Log loss: favorites, upsets and inherent variability

**Finding:** the observed gain survives excluding heavy favorites and removing the largest absolute contributions. The strongest positive band is 50–60% market confidence. Calibration is compatible with appropriate probability dispersion. Overall paired uncertainty remains wide.

Exposed historical development; fixed v1.16 weekly prior-game forecasts, 2023–2025. No recipe or probability refits.

815 binary games; 1 tie excluded. Positive gain means production improves on the same-row market.

## Historical return context

| Arm | N | Units | ROI ± SE | Market-correct null |
|---|---:|---:|---:|---:|
| market | 811 | +0.18 | +0.02% ± 2.47 | -4.10% |
| production | 811 | +29.06 | +3.58% ± 2.53 | -4.10% |

## Overall paired probability scores

Market LL 0.608072; production LL 0.605605; gain +0.002467, 95% week-cluster interval [-0.005517, +0.010503].
Market Brier 0.210334; production Brier 0.208989; gain +0.001346, interval [-0.002259, +0.004877].
Expected market loss under its own probabilities: 0.617915. Realized loss need not equal entropy in a finite sample.

## Market favorite probability bands

| Band | N | Upsets | Market LL | Model LL | LL gain [95% CI] | Brier gain |
|---|---:|---:|---:|---:|---|---:|
| 50–60% | 294 | 117 | 0.671079 | 0.661702 | +0.009377 [-0.004793, +0.023324] | +0.004512 |
| 60–70% | 254 | 84 | 0.639890 | 0.640416 | -0.000526 [-0.013557, +0.012466] | -0.000249 |
| 70–80% | 182 | 49 | 0.590298 | 0.595004 | -0.004706 [-0.026835, +0.016306] | -0.000873 |
| 80–90% | 79 | 9 | 0.351448 | 0.349341 | +0.002107 [-0.013690, +0.016094] | -0.000195 |
| 90–100% | 6 | 0 | 0.091765 | 0.078912 | +0.012853 [-0.007149, +0.032092] | +0.001292 |

Bands use market confidence fixed before outcomes; intervals are descriptive. 99% simultaneous band intervals are in results.json. Do not compare raw losses across bands as if game difficulty were equal.

## Sensitivity to favorite mix and realized upsets

| Slice | N | LL gain [95% CI] | Brier gain |
|---|---:|---|---:|
| market confidence <80% | 730 | +0.002420 [-0.006658, +0.011216] | +0.001513 |
| market confidence <90% | 809 | +0.002390 [-0.005684, +0.010524] | +0.001346 |
| favorite wins | 556 | +0.009620 [+0.002404, +0.016556] | +0.003094 |
| upsets | 259 | -0.012889 [-0.032080, +0.006080] | -0.002408 |

Favorite-win/upset slices condition on realized outcomes and are diagnostic only, never usable pregame selection rules.

## Contribution concentration

| Removed largest absolute contributions | Remaining N | Mean LL gain [95% CI] |
|---|---:|---|
| drop 1 largest absolute contributions | 814 | +0.001000 [-0.007126, +0.009077] |
| drop 5 largest absolute contributions | 810 | +0.004459 [-0.002511, +0.011690] |
| drop 10 largest absolute contributions | 805 | +0.006142 [-0.000615, +0.012997] |
| drop 20 largest absolute contributions | 795 | +0.004638 [-0.001844, +0.011118] |

Net summed gain +2.0104; gross positive 32.8809; gross negative 30.8705. 448 positive and 367 negative games.
Top 10 games contribute 12.6% of gross positive gains and 16.9% of gross negative losses.
Outcome-based trimming changes the target and is a fragility diagnostic, not a revised performance estimate.
Leave-one-week LL gain range: [+0.001512, +0.004082]. Leave-one-season gains: {'2023': 0.005438127921374093, '2024': 0.0015387200157309501, '2025': 0.00042716877835037093}.

## Calibration

Ideal intercept 0 and slope 1. Slopes below 1 suggest overconfident probability variation; above 1 suggests underconfident variation. These are retrospective diagnostics, with week-cluster sandwich intervals; they do not recalibrate production.

| Arm | Intercept [95% CI] | Slope [95% CI] |
|---|---|---|
| market | -0.0357 [-0.178808, +0.107479] | 1.0931 [+0.892992, +1.293263] |
| production | +0.0157 [-0.131565, +0.162933] | 1.0060 [+0.821301, +1.190716] |

## Inherent variability diagnostic

Under a market-correct fixed-forecast null, expected model LL gain is -0.007639; observed gain is +0.002467. The 20,000-draw null interval is [-0.015903, +0.000964]; upper-tail fraction 0.0104.

Fixed forecasts and independent Bernoulli outcomes at supplied no-vig q; excludes recipe-selection uncertainty and refitting feedback. This is a conditional reference calculation, not a selection-adjusted significance test. It is different from the paired week bootstrap, which estimates sampling uncertainty around observed historical gains.

## Interpretation

Assess favorite mix through paired same-row gains, then examine Brier, calibration, concentration and season stability together. Heavy favorites reduce expected raw log loss while rare upsets increase realized variability. A coherent gain across proper scores is supportive evidence; neither historical design selection nor uncertainty disappears when inspecting slices.

No production settings, probabilities, or native snapshots changed. All slices and concentration analyses are exploratory.
