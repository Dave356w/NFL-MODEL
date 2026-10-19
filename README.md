# NFL ATS

NFL against-the-spread picks and results, built and published as a static site
by GitHub Actions. Public pages show ATS selections, projected and market
spreads, lock status, cover rates, units and ROI. Win probabilities and moneyline
research stay internal to the model and repository reports.

**Public goal: flat 1-unit ATS results.** The signed difference between the
projected home margin and market margin chooses the ATS side. Matching lines
take the market favorite (pick'em lines skip); pushes return the stake. Returns assume −110, with cover rates excluding
pushes and ROI including pushed stakes. Recorded and replayed results remain
identified separately. Picks freeze at the 60-minute pregame cutoff.

The v1.18 probability engine and prior-season median spread mapping are
unchanged. Original moneyline snapshots and research scoring remain available
in the repository, including their original pricing and capture times; the
public interface and public CSVs contain ATS data only.

**<https://dave356w.github.io/NFL-MODEL/>**

**ATS timing (adopted 2026-10-19 UTC):** spread picks remain provisional until
60 minutes before kickoff. Five-minute scheduled polls trigger model refreshes
from T−90 through T−50; outside that window they skip the expensive build.
Each build saves eligible forecasts in `data/ats_lock_candidates.jsonl`. At or
after T−60 it freezes the latest forecast both generated and observed by the
cutoff into `data/ats_locks.jsonl`. A delayed run cannot use a newer line or
forecast, and no lock may be backfilled after kickoff. The saved forecast time,
cutoff and finalization time are all retained; GitHub cron does not guarantee
delivery at an exact minute. Missing pre-cutoff forecasts show as unavailable.
Game cards and the saved-spread-picks download preserve locked handicaps and
selections, including zero-edge skips saved before the favorite rule. Earlier ATS and moneyline records retain their original timing;
the new capture policy has a separate identity and never rewrites those records.

The **2026 ATS season overview** pools historical replay and recorded selections,
one row per game. Saved ATS picks and skips override replay. A pre-adoption game
without an ATS archive can be replayed at its original pregame forecast and line;
it is labeled replay, not recorded ATS evidence. Missing post-adoption locks are
not reconstructed from early moneyline records. The headline, weekly results,
same-game ATS controls and `ats_2026_results.csv` use this deduplicated view.
Pricing is assumed −110 with 1-unit stakes; the download identifies each source.

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

The displayed **Model spread** uses prior-season median signed margins in four
fixed groups (2026: **3/4/7/14** points for original spread magnitudes below 3,
3–7, 7–10, and 10+). Losses are negative and tied finals count as zero. Results and
calibration pages show season-by-season retrospective ATS results at assumed
−110, including pushes and skips, with downloadable per-game data. Each mapping
uses earlier seasons only; these are exposed historical comparisons. Win
probabilities and moneyline picks retain the v1.18 recipe. See `fixed_bands.py`
and the fixed-band section in `MODEL.md` for the full rule and grading basis.

| Page | For |
|---|---|
| [Projections](https://dave356w.github.io/NFL-MODEL/) | This week's games: model vs market, the model's pick, biggest factors, injury reports |
| [Results](https://dave356w.github.io/NFL-MODEL/grades.html) | Recorded forecasts, season moneyline results, and separately labelled historical replay with median ATS results |
| [Performance](https://dave356w.github.io/NFL-MODEL/market-calibration.html) | Forecast confidence, market outcomes and spread performance |

The public pages show the production model only: W-L, win % and ROI. Standard errors, log loss,
held-out scorecards, recipe selection, earlier revisions, the v1.16 shadow lock and every research
arm are in [`data/ledger_report.txt`](data/ledger_report.txt) and `data/latest/`.
Each page build consolidates the version comparison, snapshot replay, independent
production checks and frozen WP-calibration research into the **repository** report.
The website links to that report as documentation; it does not publish research
pages or a separate `ledger_report.txt` download. Short historical-replay and
recorded-forecast labels remain on the customer pages so their evidence bases stay clear.

The median ATS archive has its own policy identity and source hashes. The native
ledger's older continuous-spread diagnostic is explicitly labelled as such; it
is not the median-MOV ATS record. Run the read-only check with:

```bash
python -m research.production_sanity
```

The win-probability calibration comparison remains research only. Both seven-band
empirical rates and monotone calibration were tested on v1.16 and v1.18 using
strictly earlier-season calibration; no replacement qualified. Reproduce it with
`python -m research.wp_probability_calibration`; see the
[protocol](research/WP_PROBABILITY_CALIBRATION.md) and
[results](research/wp_probability_calibration_results/REPORT.md).

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
