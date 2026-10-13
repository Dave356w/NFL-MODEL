# Out-of-sample 2017–2020 results

Protocol: [OUT_OF_SAMPLE_2017_2020.md](../OUT_OF_SAMPLE_2017_2020.md), pushed before any 2017–2020 forecast existed. Production v1.16 and its ledger are unchanged.

**Q1, does v1.16 beat the market favorite out of sample? unresolved.** Paired units vs the favorite +18.76u (+1.84 pts per bet, 97.5% interval [-0.81, +4.61] pts). Log-loss gain vs the market -0.005235 [-0.014430, +0.003390].

**Q2, does the close-game challenger beat v1.16? not supported.** Units vs v1.16 -22.64u (-2.23 pts per bet, [-5.80, +1.41]); close-game log-loss gain -0.013249 [-0.036473, +0.010486] on 289 games.

Basis: One-time out-of-sample basis: 2017-2020 regular seasons, 2013-2016 training history only; exposure disclosed in the protocol (Test 32, Test 24, warm-up use).

## All arms, 2017–2020

1017 common flat 1u bets; 1019 binary scores, 289 of them close games (favorite under 60%). v1.16 backed the market underdog 49 times.

| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Log loss | Close-game LL | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|
| production | 691-322-4 | -0.42 | -0.04% ± 2.23 | -2.55% | 0.605604 | 0.690945 | 0.208494 |
| close_fit | 677-336-4 | -23.06 | -2.27% ± 2.25 | -2.55% | 0.605807 | 0.704194 | 0.208936 |
| v116_close_only | 690-323-4 | -4.26 | -0.42% ± 2.22 | -2.55% | 0.602049 | 0.690945 | 0.207163 |
| market favorite | 685-328-4 | -19.18 | -1.89% ± 2.20 | -2.55% | 0.600368 | 0.685017 | 0.206481 |

## By season

| Season | v1.16 units vs favorite | v1.16 LL gain vs market | Underdog picks | close_fit units vs v1.16 |
|---|---:|---:|---:|---:|
| 2017 | +8.12 | +0.000225 | 11 | -10.50 |
| 2018 | +2.70 | -0.004041 | 12 | -13.54 |
| 2019 | +0.99 | -0.016677 | 11 | +3.86 |
| 2020 | +6.95 | -0.000445 | 15 | -2.46 |

2017–2018 only (least exposed): v1.16 vs favorite +10.82u, LL gain vs market -0.001904; close_fit vs v1.16 -24.04u.

## Underdog picks by favorite band (v1.16)

| Favorite band | Picks | Units vs favorite |
|---|---:|---:|
| 50-55% | 38 | +10.97 |
| 55-60% | 8 | +3.95 |
| 60-65% | 2 | +0.95 |
| 65-100% | 1 | +2.89 |

## Calibration and the value of v1.16's market departures

Calibration slope: v1.16 0.939 ± 0.080; market 1.111 ± 0.092 (1 SE). Offset multiplier k (1 = right-sized, 0 = no value): 2017 +0.51 ± 0.59; 2018 +0.29 ± 0.44; 2019 -1.06 ± 0.60; 2020 +0.43 ± 0.73; all +0.07 ± 0.28.

## Reproduction and limits

Pipeline check against the committed v1.16 pack (2019–2020 rebuilt alone): 512 games, max input difference 3.55e-15, 100.0% of games identical within 1e-9.
All 136 weekly fits train strictly before their scored week; all pass-context references are prior weeks.
These seasons were used once before (disclosed in the protocol). One use of about 1,000 bets has limited power; an unresolved verdict does not show a zero effect. Adoption would be an owner decision and a new REVISION.

Run: `python research/out_of_sample_2017_2020.py` (frozen pack); `--prepare` rebuilds inputs from nflverse.
