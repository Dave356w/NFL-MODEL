# NFL ATS

NFL against-the-spread picks and results, built and published as a static site
by GitHub Actions: **<https://dave356w.github.io/NFL-MODEL/>**

| Page | For |
|---|---|
| [Projections](https://dave356w.github.io/NFL-MODEL/) | This week's games: model vs market spread, the pick, biggest factors, injury reports |
| [Results](https://dave356w.github.io/NFL-MODEL/grades.html) | 2026 ATS results by week and game, with downloads |
| [Performance](https://dave356w.github.io/NFL-MODEL/market-calibration.html) | 2026 ATS record, running units and same-game spread baselines |
| [Calibration](https://dave356w.github.io/NFL-MODEL/historical-calibration.html) | 2023 onward: market/model WP calibration with median MOV, ATS ROI by spread band |

**Goal: flat 1-unit ATS results.** The signed difference between the model's
mapped home margin and the market margin chooses the side. A zero edge takes the
market favorite (a pick'em line skips); pushes return the stake. Returns use the
game's captured spread price where one exists, else −110 (counted).

## Model

Production is `boxscore-composite-v1.24` (`nfl_model.py`; `MODEL.md` describes
current behavior and the version history):

- **Probability:** no-vig moneyline log-odds as the baseline, plus ten fitted
  terms (home field, offense/defense first-down rate and INT %, defense penalty
  yards, QB projection, pass product and two pass hinges), ridge-fitted before
  every week on earlier weeks only, with a 0.2 favorite-confidence penalty.
- **Availability:** official injury reports and both teams' complete inactive
  lists gate every ATS candidate (`availability_collect.py`, `AVAILABILITY.md`).
- **Spread map:** the implied spread is banded and mapped to weekly decayed
  median signed margins of earlier games (one-season half-life; `fixed_bands.py`).
- **QB replacement:** −2 points to a team starting a replacement QB, applied
  after the map (`qb_replacement.py`).

## Locks and results

An independent watcher (`lock_watcher.py`, `LOCKING.md`) freezes each game's pick
60 minutes before kickoff into `data/ats_locks.jsonl` from a forecast and ESPN
quote captured by the cutoff; `lock_watchdog.py` alerts on at-risk or missed
games. Locks are append-only. Owner-authorized recoveries go through
`retro_lock.py` and `ats_retro_requests.json`.

Public 2026 results show the current revision's regrade: v1.24's own saved locks
at their lock line and price, and v1.24's walk-forward replay for every other
game (`season_ats.py`). Spread prices come from ESPN evidence at the exact
handicap (`espn_spreads.py`, `ESPN_SPREAD_PRICING.md`); final scores from
`score_updates.py`.

The repository report `data/ledger_report.txt` carries the forward ledger's
proper scores, the independent production audit (`production_sanity.py`), the
lock journal and native-lock ATS baselines. It is not published on the site.

## Workflows

| Workflow | Does |
|---|---|
| `build.yml` | Gated by `schedule_gate.py`: runs the model, snapshots `data/latest`, grades the ledger, commits `data/` (`commit_data.py`) and deploys pages. A failed model run deploys nothing. |
| `lock-watcher.yml` / `lock-watchdog.yml` | T−60 lock capture and coverage alerts. |
| `availability.yml` | Official injury-report and inactive-list collection. |
| `scores.yml` | Final scores every 15 minutes after kickoff and daily; republishes saved state. |
| `publish.yml` / `publish-saved.yml` | Serialized page publication. |
| `tests.yml` | `pytest` on every PR and push to main (never in the build). |

## Local use

```bash
pip install -r requirements.txt
python build_site.py                 # full build into public/ (state in data/, caches in .nfl_cache/)
python build_site.py --pages-only    # re-render pages from committed data/
python score_updates.py --season 2026
python grade_ledger.py               # regrade data/forward_ledger.csv + ledger_report.txt
python production_sanity.py          # independent audit of the committed exports
python nfl_model.py --self-test

pip install pytest                   # deliberately not in requirements.txt
python sync_notebook.py              # run all three before opening a PR
python validate_data_files.py
python -m pytest tests/ -q
```

`NFL_PROFILE_MODE=production python build_site.py` builds only the profiles the
production recipe uses.

Colab: `notebooks/NFL_C_B_MODEL.ipynb` is the same code in one cell, generated
by `python sync_notebook.py`; a test fails if they drift.

Research code, earlier experiments and retired add-ons (v1.16 shadow, Kalshi,
H1–H13 hypotheses, moneyline reporting) were removed on 2026-11-16 and remain
in git history.
