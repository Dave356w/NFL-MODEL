# NFL Box-Score Composite

Weekly NFL win probabilities from prior-game box-score profiles and player
availability, built and published as a static site by GitHub Actions.

**Goal: flat 1-unit ROI.** Every game the model decides gets 1u on the side it
makes the favorite, graded at that side's moneyline. Every game's first pregame
forecast is locked into a forward ledger with the moneyline it saw, then graded
on units and ROI against the same-row market favorite and the market-correct
null. Log loss is kept as a secondary score.

**<https://dave356w.github.io/NFL-MODEL/>**

Current model (2026-10-13): `boxscore-composite-v1.18`, the v1.16 model with a favorite-confidence
penalty: where v1.16 backs the market favorite more strongly than the no-vig price, only 0.2 of that
lean is kept. Picks and bets are identical to v1.16's; only those probabilities change. v1.16 keeps
locking as a shadow for its pre-registered tests, reported in the ledger report only.
v1.16 is the owner-fixed **Product + 1 SD**
market-offset model. No-vig moneyline log-odds form its baseline. Raw h8 offense,
defense, availability and prior lead/deficit profiles provide additive corrections;
raw h16 pass profiles provide the shared product and four signed 1 SD contexts.
Both penalties are fixed at 0.1; coefficients refit before every week using earlier
weeks only. Missing market quotes produce no forecast. Original pregame snapshots
remain unchanged; retrospective replay at their original quotes is separately labelled.
Adoption follows exposed historical development, with reliable profit superiority
still unresolved.

**Production ATS v2 (2026-10-16)** is a separate scoring-aware *selection*
policy; the v1.18 moneyline model and frozen fixed-band benchmarks are unchanged.
The board still shows the historical fixed-band **Model spread** magnitude (2026:
4/5/7/13 for raw spread magnitudes <3, 3–<7, 7–<10 and >=10), but the displayed
**ATS v2** selection is no longer mechanically determined by its difference
from the market line. The original raw spread and fixed band each propose a
side; an earlier-season-trained discrete scoring-margin model calculates
home-cover, away-cover and push probabilities. At an assumed -110 payout,
only a candidate with positive modeled expected units is selected. When the
raw and fixed-band sides disagree, the probability model confirms one or
abstains; forced reversals and coverage targets do not apply. An exact
raw/fixed equality with the market offers no candidate from that source.
No ATS sportsbook prices have been verified.

The Ledger and Market calibration pages display the live v2 policy's
*retrospectively reconstructed* scores and separately retain the original
fixed-band benchmark with its 2023-2026 unchanged selections. Public and
committed audits: `ats_v2_ledger.csv`, `ats_v2_summary.csv`,
`ats_v2_board.csv`, and `ats_v2_policy.json` under `data/latest/`; new
native pregame ATS shadow records also freeze v2 decisions and policy IDs.
The old fixed-band history was used in deciding to build this policy and is
**not** independent evidence of profitability. The model's moneyline picks
retain the v1.18 recipe.

| Page | For |
|---|---|
| [Projections](https://dave356w.github.io/NFL-MODEL/) | This week's games: model vs market, the model's pick, biggest factors, injury reports |
| [Ledger](https://dave356w.github.io/NFL-MODEL/grades.html) | Every locked pick graded at its moneyline, beside always-favorite and always-home on the same games; then the current model's rebuilt history since 2021 (hindsight) |
| [Market calibration](https://dave356w.github.io/NFL-MODEL/market-calibration.html) | What each moneyline implied vs what happened; how often the model's picks won at each confidence |

The public pages show the production model only: W-L, win % and ROI. Standard errors, log loss,
held-out scorecards, recipe selection, earlier revisions, the v1.16 shadow lock and every research
arm are in [`data/ledger_report.txt`](data/ledger_report.txt) and `data/latest/`; the site's
published `ledger_report.txt` carries the version comparison and snapshot replays as appendices.

| Where to look | For |
|---|---|
| [`MODEL.md`](MODEL.md) | What the model does today and how the pipeline fits together. The full version history is the docstring at the top of `nfl_model.py`. |
| [`CLAUDE.md`](CLAUDE.md) | Working standards: evidence ladder, ledger protection, versioning, validation before a PR. |
| [`data/ledger_report.txt`](data/ledger_report.txt) | Latest graded forward results (regenerated every build). |

## Production qualification research

Production now uses the owner-adopted fixed **market-offset Product + 1 SD** recipe (raw h8 main, raw h16 pass contexts, both penalties 0.1). Adoption follows exposed historical development; reliable profit superiority remains unresolved. Original snapshots are preserved, with a separately labelled retrospective replay at their own quotes. See [MODEL.md](MODEL.md).


The goal is a reliable out-of-sample advantage over the market. The current
model is an experimental baseline; deployment is not evidence of an edge.
[The qualification runner](research/production_qualification.py) compares the
legacy v1.15 additive grid with market-offset and context-dependent pass candidates,
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

## Monte Carlo uncertainty research

[Protocol](research/MONTE_CARLO.md) and [results](research/monte_carlo_results/REPORT.md)
test joint empirical market outcomes, price calibration, whole-game feature
bootstrap, week-cluster coefficient refits and combined uncertainty on 2023–2025.
The experiments provide outcome ranges and forecast sensitivity diagnostics;
no challenger establishes improved predictive accuracy. Production remains v1.16.
Run `python research/monte_carlo.py --prepare-boxes`, then
`python research/monte_carlo.py`. The separate **Monte Carlo uncertainty research**
workflow runs the experiment and a doubled-draw stability check without deployment.

[Favorite-mix and upset diagnostics](research/log_loss_diagnostics_results/REPORT.md)
compare paired log loss/Brier by market probability band, calibration,
contribution concentration, leave-one-week/season sensitivity and a conditional
market-correct simulation. Run `python research/log_loss_diagnostics.py`.

[Earlier-season calibration follow-up](research/chronological_calibration_results/REPORT.md)
tests close-matchup annual consistency and calibration fitted on earlier-season
OOF predictions only. Run `python research/chronological_calibration.py`.

## Research checks of v1.16 (2026-10-13)

Each runs from committed frozen inputs, has its own replay workflow, and changes
neither production nor the ledger.

- [Context support cap](research/support_cap_results/REPORT.md)
  ([protocol](research/CONTEXT_SUPPORT_CAP.md)): capping the pass contexts at their
  training support was not supported (2023–25 log-loss gain −0.00044, interval
  −0.0046 to +0.0032; 7 side flips worth −5.03u). `python research/context_support_cap.py`
- [2017–2020 out of sample](research/out_of_sample_results/REPORT.md)
  ([protocol](research/OUT_OF_SAMPLE_2017_2020.md), pushed before any forecast existed):
  v1.16 beat the same-row favorite by +18.76u on 1,017 bets, unresolved (+1.84 pts per
  bet, 97.5% interval −0.81 to +4.61); the close-game challenger was not supported.
  `python research/out_of_sample_2017_2020.py`
- [Availability weighting](research/availability_weights_results/REPORT.md)
  ([protocol](research/AVAILABILITY_WEIGHTS.md)): Questionable weights by final practice
  participation are unresolved (pooled log-loss gain +0.0003, interval crosses zero; −11.4u
  on 12 changed picks); separate WR/TE and CB/S units are falsified.
  `python research/availability_weights.py --prepare`, then `python research/availability_weights.py`
- [Selection-adjusted benchmark](research/selection_benchmark_results/REPORT.md): if the
  market were exactly right, the best of the 53 committed arms would beat the favorite
  by a median +16.7u on 2023–25 by luck alone; v1.16's +30.6u has p 0.180 against that
  bar. `python research/selection_benchmark.py`

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

Optional runtime optimization: `NFL_PROFILE_MODE=production python build_site.py`
builds only raw h8/h16 profiles for the fixed production recipe, skipping unused
h4 and opponent-adjusted profiles. Shared inputs and forecasts are unchanged;
the default `full` mode retains the complete research exports. The compact
export has its own content-derived walk-forward cache. Configuration identity,
production revision and the ledger are unchanged.

`python research/simplification.py` reruns the three fixed feature-removal
challengers from frozen inputs; [protocol](research/SIMPLIFICATION.md) and
[results](research/simplification_results/REPORT.md). This is exposed historical
development, with no automatic production adoption. The contribution table now
allocates v1.18's favorite-confidence shrinkage across the fitted terms so that
their sum plus the market baseline reconstructs the displayed probability.

`python research/peaks_to_ybc.py` tests replacing both lead/deficit peaks with
offensive and defensive-allowed rushing yards before contact per carry, against
production and a peaks-removed control. See the [fixed protocol](research/PEAKS_TO_YBC.md)
and [executed results](research/peaks_to_ybc_results/REPORT.md). All are exposed
historical comparisons; the test changes no production forecast or ledger.

Colab: `notebooks/NFL_C_B_MODEL.ipynb` is the same code in one cell, storing
outputs on Google Drive. It is generated from `nfl_model.py` by
`python sync_notebook.py`; a test fails if the two drift. A Colab run keeps its
own ledger on Drive; the Actions ledger in `data/` is the published one.

The first deploy needs **Settings → Pages → Source: GitHub Actions** if the
workflow's `configure-pages` step cannot enable it on its own.

## Additional interaction context battle

[Protocol](research/CONTEXT_BATTLE.md) and [executed results](research/context_results/REPORT.md) compare eight context families and fixed-penalty sensitivities against `fixed_market_product` and production. Run `python research/context_battle.py`; the separate research workflow also executes it. These are historical development results for selecting a forward challenger. No production deployment or ledger change is made.
