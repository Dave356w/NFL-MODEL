# NFL Box-Score Composite

Weekly NFL home-win probabilities from prior-game box-score profiles and
player availability, built and published as a static site by GitHub Actions.
Every game's first pregame forecast is locked into a forward ledger and graded
against the final score and the spread-implied market.

**<https://dave356w.github.io/NFL-MODEL/>**

Current model: `boxscore-composite-v1.9`. A ridge-penalized logistic composite
of decayed, opponent-adjusted (or raw) offense/defense rate profiles plus a
player-availability layer: injury-report status, roster membership and a
projected-starter QB term. Hyperparameters are frozen per season from earlier
seasons' walk-forward log loss; coefficients refit before every week. The
market spread is a benchmark only and never enters the model.

| Page | For |
|---|---|
| [Projections](https://dave356w.github.io/NFL-MODEL/) | This week's games: model vs market, largest drivers, availability, injury-report status |
| [Ledger](https://dave356w.github.io/NFL-MODEL/grades.html) | Every locked pregame snapshot, graded; record and log loss vs market |
| [Market calibration](https://dave356w.github.io/NFL-MODEL/market-calibration.html) | Model and market in matched probability bands, forward and held-out kept separate |
| [Model](https://dave356w.github.io/NFL-MODEL/model.html) | Recipe, held-out scorecards by season, coefficients, limitations |
| [Full board](https://dave356w.github.io/NFL-MODEL/board.html) | The model's own detailed weekly board |

| Where to look | For |
|---|---|
| [`MODEL.md`](MODEL.md) | What the model does today and how the pipeline fits together. The full version history is the docstring at the top of `nfl_model.py`. |
| [`CLAUDE.md`](CLAUDE.md) | Working standards: evidence ladder, ledger protection, versioning, validation before a PR. |
| [`data/ledger_report.txt`](data/ledger_report.txt) | Latest graded forward results (regenerated every build). |

## How it runs

`.github/workflows/build.yml` polls hourly. `schedule_gate.py` starts the full
build when a game is within 30 hours and not yet in the ledger, or within 150
minutes of kickoff; a 06:13 ET pass runs daily to grade and refresh. The build
runs the model, appends any new first pregame snapshots to
`data/forward_predictions.jsonl` (only once both teams' injury reports carry game
statuses), grades the ledger, commits `data/` through `commit_data.py` and
deploys `public/` to Pages. A failed model run deploys nothing, so the last
good site stays up.

## Local use

```bash
pip install -r requirements.txt
python build_site.py                 # full build into public/ (state in data/, caches in .nfl_cache/)
python build_site.py --pages-only    # re-render pages from committed data/
python grade_ledger.py               # regrade data/forward_ledger.csv + ledger_report.txt
python nfl_model.py --self-test      # synthetic regression suite

pip install pytest                   # deliberately not in requirements.txt
python validate_data_files.py        # run both before opening a PR
python -m pytest tests/ -q           # also CI-gated on every PR and push to main
```

Colab: `notebooks/NFL_C_B_MODEL.ipynb` is the same code in one cell, storing
outputs on Google Drive. It is generated from `nfl_model.py` by
`python sync_notebook.py`; a test fails if the two drift. A Colab run keeps its
own ledger on Drive; the Actions ledger in `data/` is the published one.

The first deploy needs **Settings → Pages → Source: GitHub Actions** if the
workflow's `configure-pages` step cannot enable it on its own.
