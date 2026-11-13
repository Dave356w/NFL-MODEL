# Frozen punt-rate inputs

`team_games.csv.gz` holds regular-season punt attempts and qualifying possessions
for each team, with the opponent's counts mirrored for defensive forced-punt rate.
Source PBP snapshots are the same 2018-2026 files already recorded in
`../pressure_inputs/provenance.json`. Raw SHA256 hashes and possession/punt totals
are repeated in `coverage.json`; no source game is silently imputed.

Possessions consisting only of kneels/spikes are excluded. Turnover and failed
fourth-down possessions remain in the denominator. Blocked punts count as
attempts. No observed possession has multiple punt attempts in this snapshot;
the audit retains that count explicitly.

Replay with `python research/punts_per_possession.py`. Raw rebuild:

```sh
python research/punts_per_possession.py --prepare --raw-dir work/pressure_raw
```

Use the original raw cache for matching hashes. New upstream downloads may be
revised and cannot prove when each historical row first became available.
The original publication-timing limitation remains applicable to this study.
