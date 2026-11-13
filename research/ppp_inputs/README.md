# Frozen offensive points-per-possession inputs

`team_games.csv.gz` records offensive points and qualifying possessions, with
opponent counts mirrored exactly as points allowed / opponent possessions.
`coverage.json` records annual coverage, point/possession totals and the original
PBP file SHA256 hashes. Sources and publication-time limitations are shared with
`../pressure_inputs/provenance.json`; no new data provider is involved.

The possession denominator exactly matches `../punt_inputs/team_games.csv.gz`.
The numerator includes offensive TDs, FGs and attached PAT/two-point conversions;
defensive/return scores and nonoffensive PAT-only possessions are excluded.
This is offensive drive efficiency, not all scoreboard points for or against.

Replay:

```sh
python research/points_per_possession.py
```

Raw rebuild using the original frozen upstream cache:

```sh
python research/points_per_possession.py --prepare --raw-dir work/pressure_raw
```

See `../POINTS_PER_POSSESSION.md` for fixed fit/evaluation choices. The original
finishing bundle and the new isolated PPP arm are distinct experiments.
