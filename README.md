# NFL ATS

**v1.19 promotion is on hold (owner decision 2026-10-19). Do not merge or
deploy this candidate until it demonstrates improvement over the market in
every evaluated season. Production remains v1.18 with its median ATS policy.**
The v1.19 implementation and rebuilt results below are research artifacts;
they have not replaced the live model. See the
[hold and evaluation requirements](research/MARKET_CONTEXT_ADOPTION.md).

The [every-season variant retest](research/season_rule_retest_results/REPORT.md)
evaluates 330 corrections and 990 ATS conversion paths. None clears the
combined market rule; the promotion hold remains in place.

NFL against-the-spread picks and results, built and published as a static site
by GitHub Actions. Public pages and CSVs show ATS selections, projected and
market spreads, lock status, cover rates, units and ROI. Win probabilities and
moneyline research remain internal.

**<https://dave356w.github.io/NFL-MODEL/>**

Implemented candidate, held from production: **`boxscore-composite-v1.19`**.
It first fits a market-based home-win forecast from the offered spread, total
and their interaction. It then corrects that baseline using **all 29 football
inputs**, jointly fitted with ridge shrinkage. Both stages fit before each week
using earlier weeks only. There is no favorite-confidence penalty.

The model converts its corrected win forecast into a continuous projected home
margin: `12.37 × inverse_normal(clamp(p, 0.005, 0.995))`. Its difference from the
market home margin chooses the ATS side. No median or fixed-band mapping is
applied. A zero edge within 1e-10 takes the market favorite; a zero edge at a
pick'em line skips. Returns assume flat 1u risk at −110: a win pays +0.9091u,
a loss costs 1u and a push returns the stake. Cover rates exclude pushes;
ROI includes pushed stakes.

**Retrospective update.** Historical picks, results and performance are rebuilt
with v1.19. The 2026 overview, weekly/game results, running units and season
CSV use one current-revision row per game. Completed games without v1.19 locks
are retrospective forecasts, including games after the older policy's adoption.
Only a saved v1.19 lock overrides this replay. Earlier revisions' snapshots,
frozen recipes and ATS locks retain their original bytes and grading identity.
Source distinctions remain in repository reports. The Performance page also
shows all available seasons and an ATS history download.

**ATS timing:** picks remain provisional until kickoff minus 60 minutes.
Five-minute scheduled polls trigger refreshes from T−90 through T−50. Each
build saves eligible forecasts in `data/ats_lock_candidates.jsonl`; at or after
T−60 it freezes the latest forecast both generated and observed by the cutoff
into `data/ats_locks.jsonl`. A delayed run cannot use post-cutoff inputs or
backfill a lock after kickoff. GitHub cron delivery can be delayed. The new
continuous-spread policy has its own identity; legacy median-policy records
continue to validate against their original rules.

The owner selected the previously tested `spread_total::group:full::g1` raw
variant after reviewing historical comparisons. In the frozen 2023–25 research
cohort it returned **+48.73u / 5.97% ROI** versus v1.18's median-policy
**+23.91u / 2.93%** on the same 816 games. These are exposed development results;
the paired improvement interval includes zero. Fresh performance at actual
quotes is needed before claiming an established edge. Updated source data can
change reconstructed results; the frozen comparison and a full rebuild have
different input vintages. See [the adoption record](research/MARKET_CONTEXT_ADOPTION.md).

| Page | For |
|---|---|
| [Projections](https://dave356w.github.io/NFL-MODEL/) | Current games, continuous model and market spreads, ATS picks and lock status |
| [Results](https://dave356w.github.io/NFL-MODEL/grades.html) | Current-season ATS results by week and game, with downloads |
| [Performance](https://dave356w.github.io/NFL-MODEL/market-calibration.html) | Current-season running units, same-game baselines and annual ATS performance |

| Where to look | For |
|---|---|
| [MODEL.md](MODEL.md) | Exact production fitting, features, selection and historical policy descriptions |
| [CLAUDE.md](CLAUDE.md) | Evidence standards, archive protection, versioning and required validation |
| [data/ledger_report.txt](data/ledger_report.txt) | Regenerated forward grading and research appendices |

Run the independent read-only production check with:

```bash
python -m research.production_sanity
```

The v1.16/v1.18 probability-calibration comparison remains archived research;
no calibration replacement qualified. Its [protocol](research/WP_PROBABILITY_CALIBRATION.md)
and [report](research/wp_probability_calibration_results/REPORT.md) retain their
original experiment identities.

## Production qualification research

The archived qualification experiments below concern earlier model revisions. Current production is the owner-adopted v1.19 spread/total baseline with the full 29-input correction; see [MODEL.md](MODEL.md). Historical development does not establish a durable betting edge.


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
