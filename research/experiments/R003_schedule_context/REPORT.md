# R003-SC1 — schedule, rest, travel and clock context

**Decision: no qualified improvement.**
Exposed historical development, not independent confirmation. Plain is the
observed-score MC2 kernel (spread bandwidth 2, total bandwidth 3, no global backoff).
All added distributions retain those same observed score atoms.

## Flat 1u moneyline results (not used to fit or select)

| Basis | Policy | Bets | W–L–P | Units | ROI ± SE | Favorite | Null |
|---|---|---:|---|---:|---:|---:|---:|
| 2023-25 | plain | 812 | 552–259–1 | -4.210 | -0.52% ± 2.48 pp | +0.180u | -4.10% |
| 2023-25 | selected_all | 812 | 552–259–1 | -4.210 | -0.52% ± 2.48 pp | +0.180u | -4.10% |
| 2017-22 | plain | 1559 | 1026–526–7 | -64.543 | -4.14% ± 1.79 pp | -59.214u | -2.61% |
| 2017-22 | selected_all | 1559 | 1025–527–7 | -65.937 | -4.23% ± 1.79 pp | -59.214u | -2.61% |
| 2026 diagnostic | plain | 79 | 50–28–1 | -3.703 | -4.69% ± 8.22 pp | -3.703u | -4.10% |
| 2026 diagnostic | selected_all | 79 | 50–28–1 | -3.703 | -4.69% ± 8.22 pp | -3.703u | -4.10% |

Identical eligible moneyline games, ties push, market pick'ems excluded. Full
fixed-arm returns and paired week intervals are in moneyline.json. No historical
spread/total ROI: actual two-sided prices are absent.

## All fixed variants and earlier-season selected paths, 816 games 2023–25

| Arm | Primary CRPS ↓ | Gain vs plain | Win LL ↓ | Cover LL ↓ | Total LL ↓ |
|---|---:|---:|---:|---:|---:|
| travel_k100 | 7.207066 | +0.007068 | 0.612007 | 0.698875 | 0.695124 |
| travel_k30 | 7.208325 | +0.005808 | 0.612209 | 0.698015 | 0.694479 |
| body_clock_k100 | 7.210210 | +0.003923 | 0.612633 | 0.699438 | 0.696220 |
| additive_k30 | 7.210741 | +0.003392 | 0.613097 | 0.700136 | 0.695148 |
| additive_k100 | 7.211341 | +0.002792 | 0.612769 | 0.700129 | 0.695675 |
| joint_k30 | 7.211597 | +0.002536 | 0.612142 | 0.700119 | 0.695466 |
| rest_k100 | 7.211671 | +0.002462 | 0.613190 | 0.700297 | 0.695254 |
| body_clock_k30 | 7.211838 | +0.002295 | 0.612751 | 0.699232 | 0.696650 |
| joint_k100 | 7.212654 | +0.001479 | 0.612244 | 0.700065 | 0.695974 |
| selected_all | 7.213058 | +0.001075 | 0.612263 | 0.700025 | 0.696021 |
| selected_joint | 7.213058 | +0.001075 | 0.612263 | 0.700025 | 0.696021 |
| rest_k30 | 7.213613 | +0.000520 | 0.613728 | 0.700386 | 0.694528 |
| selected_body_clock | 7.214133 | +0.000000 | 0.612332 | 0.700040 | 0.696454 |
| selected_phase | 7.214133 | +0.000000 | 0.612332 | 0.700040 | 0.696454 |
| selected_additive | 7.214133 | +0.000000 | 0.612332 | 0.700040 | 0.696454 |
| plain | 7.214133 | +0.000000 | 0.612332 | 0.700040 | 0.696454 |
| selected_venue | 7.214133 | +0.000000 | 0.612332 | 0.700040 | 0.696454 |
| selected_travel | 7.214133 | +0.000000 | 0.612332 | 0.700040 | 0.696454 |
| selected_rest | 7.214133 | +0.000000 | 0.612332 | 0.700040 | 0.696454 |
| selected_slot | 7.214133 | +0.000000 | 0.612332 | 0.700040 | 0.696454 |
| slot_k100 | 7.214512 | -0.000379 | 0.613398 | 0.700682 | 0.695721 |
| venue_k100 | 7.220580 | -0.006447 | 0.612894 | 0.701039 | 0.696157 |
| slot_k30 | 7.224828 | -0.010695 | 0.614413 | 0.701371 | 0.695860 |
| phase_k100 | 7.231873 | -0.017740 | 0.614071 | 0.702087 | 0.697851 |
| venue_k30 | 7.237540 | -0.023407 | 0.614434 | 0.702694 | 0.696804 |
| phase_k30 | 7.253821 | -0.039688 | 0.615943 | 0.704217 | 0.699546 |

Primary loss is 0.5*(margin CRPS+total CRPS), lower better. Single new primary
comparison: selected_all minus plain policy, positive gain = plain loss minus
selected loss. Gain **+0.001075**, 95% interval **[-0.0002349212697739054, 0.0027135156774000034]**;
16-challenger sensitivity interval [-0.0008114115126584457, 0.0035515713354994233]. Bootstrap:
10,000 paired whole-week draws within season, seed 20261016, conditional on
fixed forecast/selection paths, without removing historical design exposure.
Other arms/slices are descriptive; no best-arm historical rank is qualification.

Annual all-family choices: [(2017, 'travel_k100'), (2018, 'travel_k100'), (2019, 'travel_k100'), (2020, 'travel_k100'), (2021, 'plain'), (2022, 'plain'), (2023, 'plain'), (2024, 'joint_k100'), (2025, 'joint_k100'), (2026, 'joint_k100')]. Plain is an explicit first-choice
tie-break/control in every selector. Selection uses strictly earlier OOF seasons,
min two seasons, never ROI. Annual primary gains: {2023: 0.0, 2024: 0.003208846943330834, 2025: 1.5772641273409056e-05}.
Gates: {'practical_gain': False, 'positive_interval': False, 'annual_consistency': False, 'secondary_scores': True, 'integrity': True}. A zero-gain plain selection cannot establish improvement.

## Shrinking sparse contexts to the plain distribution

For matching context rows, support=min(Kish ESS_subset, ESS_plain*context_mass).
Below 20 relevant games, on unknown features or empty matching mass, weights
equal plain exactly. Otherwise context weight alpha=support/(support+K), K=30
or 100. Final weights are (1-alpha)*plain+alpha*matching_context. No outcome-driven
strength fit; no unrelated context is fabricated. Additive averages six coherent
shrunk distributions; joint requires all six keys to match. These are separately
tested combinations, not extra independent samples.

| Variant | Mean support | Mean context weight | Fallback |
|---|---:|---:|---:|
| additive_k100 | 75.2 | 34.2% | 1.6% |
| body_clock_k100 | 90.8 | 36.0% | 30.1% |
| joint_k100 | 2.4 | 0.4% | 98.2% |
| phase_k100 | 66.8 | 35.1% | 13.2% |
| rest_k100 | 54.8 | 25.3% | 40.6% |
| slot_k100 | 62.7 | 30.0% | 31.2% |
| travel_k100 | 107.8 | 43.9% | 11.3% |
| venue_k100 | 68.3 | 34.6% | 16.4% |

Full support/alpha/fallback and feature-category scores are saved. A subgroup's
sample size is not the same as its market-relevant support. Many historical TNF
games can still leave few comparable spread/total games for a particular TNF.

## Feature definitions and limits

Slot distinguishes TNF/Thursday daytime/MNF/SNF/Sunday early/Sunday late/other.
Rest uses both teams (short <=6 days, normal 7–9, long >=10) and rest-gap class;
week 1 is opener. Travel is a home-base to home-venue >=2-hour east/west proxy.
Body clock uses home/away local kickoff bins and venue uses home time-zone region.
Phase separates early/mid/late/final week. ZoneInfo handles Arizona DST and
historical LA/St. Louis location. Neutral sites fall back for slot/venue/travel/
clock; rest and phase remain usable. No itinerary, actual sleep, acclimation,
weather or rested-starter outcome is inferred.

Schedule fields are frozen retrospective records, not timestamp-certified feeds.
Neutral-site kickoff ambiguities are not silently corrected. Inputs have the
same historical price-time limitations as the plain model. Earlier standalone
schedule diagnostics found mostly unresolved market residuals; these results
test empirical distribution context, not a claim those old tests were untouched.

## Reproduction

`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/schedule_context_empirical.py`

The protocol and local registration hash precede scoring. Feature table,
per-game full-precision results, all arms, annual selections, cutoffs, source/
input hashes, stability and independent repeat accompany the report. Original
experiments, prior user changes, production models and ledger are preserved.
No live forecast, price-provider connection, deployment or wager occurred.
