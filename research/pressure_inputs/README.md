# Frozen pressure and common forecast inputs

- `base_forecasts.csv`: fixed comparable mapped forecasts, 272 games each in
  2023/2024/2025 plus 137 saved/public 2026 graded games. Used by both studies.
- `ats_2026_results.csv`: the public snapshot used to freeze the current-season
  forecast rows; its side prices are not used for the common -110 comparison.
- `team_games.csv.gz`: 2018-2026 regular-season pressures, independently counted
  PBP pass/sack/scramble opportunities, and mirrored opponent defensive counts.
- `coverage.json`: game coverage, missing sources, rate-convention differences,
  and raw-file SHA256 hashes. 2018-25 pressure and PBP cover identical games.
  Pressure covers 136 2026 games through week 9; PBP additionally has WAS-NYG
  week 10. That missing pressure is excluded, not imputed as zero.
- `provenance.json`: base repository commit, source URLs, raw/frozen hashes,
  whole-asset timestamps, and the unavailable original-publication-time audit.

Use the frozen aggregates for exact replay:

```sh
python research/pressure_margin.py
python research/scoring_finishing.py
```

Raw rebuild (new upstream revisions may change hashes/results):

```sh
python research/pressure_margin.py --prepare --download --raw-dir work/pressure_raw
python research/scoring_finishing.py --prepare --raw-dir work/pressure_raw
```

Downloads preserve already-present raw files rather than silently replacing them.
The approximately 160MB of raw PBP is not committed. A fresh raw download does
not recreate original historical publication timestamps. Two-week and one-week
lags are reconstruction assumptions, not verified data-availability guarantees.

Definitions: pressure counts from nflverse's `pfr_advstats` weekly passing
release; opportunities and scoring events from its `pbp` release. Documentation:
https://nflreadr.nflverse.com/articles/dictionary_pfr_passing.html and
https://nflreadr.nflverse.com/articles/dictionary_pbp.html.
