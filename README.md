# NFL Box-Score Composite

Weekly NFL win probabilities from prior-game box-score profiles and player
availability, built and published as a static site by GitHub Actions.

**Goal: flat 1-unit ROI.** Every game the model decides gets 1u on the side it
makes the favorite, graded at that side's moneyline. Every game's first pregame
forecast is locked into a forward ledger with the moneyline it saw, then graded
on units and ROI against the same-row market favorite and the market-correct
null. Log loss is kept as a secondary score.

**<https://dave356w.github.io/NFL-MODEL/>**

Current model: `boxscore-composite-v1.15`. A ridge-penalized logistic composite
of decayed, opponent-adjusted (or raw) offense/defense rate profiles plus a
player-availability layer: injury-report status, roster membership (plus, from v1.15, the game week's own reserve list) and a
projected-starter QB term (depth chart from 2025), dated personnel events, plus each team's decayed largest lead and largest deficit from prior games. These two score peaks replace final MOV; time leading is excluded. v1.14 removes the separate offensive and defensive sack-rate regressors while retaining net passing efficiency, which includes sacks. This owner-selected simplification follows exploratory ablation; improvement remains unresolved. Hyperparameters are frozen per season from earlier
seasons' walk-forward log loss; coefficients refit before every week. The
market spread is a benchmark only and never enters the model.

| Page | For |
|---|---|
| [Projections](https://dave356w.github.io/NFL-MODEL/) | This week's games: model vs market, the model's pick, biggest factors, injury reports |
| [Ledger](https://dave356w.github.io/NFL-MODEL/grades.html) | Every locked pick graded at its moneyline, beside always-favorite and always-home on the same games; then the current model's rebuilt history since 2021 (hindsight) |
| [Market calibration](https://dave356w.github.io/NFL-MODEL/market-calibration.html) | What each moneyline implied vs what happened; how often the model's picks won at each confidence |

The public pages show W-L, win % and ROI only. Standard errors, log loss, held-out
scorecards and recipe selection are in [`data/ledger_report.txt`](data/ledger_report.txt)
and `data/latest/`.

| Where to look | For |
|---|---|
| [`MODEL.md`](MODEL.md) | What the model does today and how the pipeline fits together. The full version history is the docstring at the top of `nfl_model.py`. |
| [`CLAUDE.md`](CLAUDE.md) | Working standards: evidence ladder, ledger protection, versioning, validation before a PR. |
| [`data/ledger_report.txt`](data/ledger_report.txt) | Latest graded forward results (regenerated every build). |

## Production qualification research

The goal is a reliable out-of-sample advantage over the market. The current
model is an experimental baseline; deployment is not evidence of an edge.
[The qualification runner](research/production_qualification.py) compares the
full production grid with market-offset and context-dependent pass candidates,
using earlier-season recipe selection and weekly prior-game coefficient fits.

```bash
python research/production_qualification.py
```

See the [fixed protocol](research/PRODUCTION_QUALIFICATION.md),
[executed results](research/qualification_results/REPORT.md), and
[nominated candidate](research/qualification_results/nominated_candidate.json).
The [prospective qualification contract](research/FORWARD_QUALIFICATION.md)
defines the evidence required beyond historical screening.
The latest development run evaluated 337 configurations in six families;
none passed the multiplicity-adjusted profitability and market-comparison gate.
The command records input/source hashes, selections and per-game predictions.
The separate **Research production qualification** workflow reruns it and
uploads results; it neither deploys the site nor changes production recipes or
the append-only forward ledger.

## Site build

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
