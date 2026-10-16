# Future iterations must beat market-only benchmarks

The completed research supports the market as a strong baseline. R003 plain
has not established incremental winner/ATS information or a profitable edge.
The [separated analysis](spread_signal_separation/REPORT.md) distinguishes
market signal, added probability information and price costs. Historical
band winners and pass-only policies are not grounds for promotion.

## Runnable evaluation framework

`market_increment_gate.py` evaluates **one frozen candidate recipe** against
market-only forecasts, with outcomes supplied separately. It reports:

1. Margin absolute-error gain over the offered spread.
2. Winner log-loss gains over prior-trained spread-only, spread+total, and
   actual no-vig moneyline forecasts, all on the same available games.
3. Cover log-loss gain over market-neutral conditional 50/50.
4. At most one positive-EV 1u ATS offer per game, using the **actual supplied
   side odds**, with pushes, same-row spread-favorite returns and a fair
   negative-hold null. No implicit -110 proxy is inserted.

Use the fixed market-only fitting functions in `spread_signal_separation.py`
to produce baseline forecasts using only earlier data. Freeze benchmarks with
the candidate pregame; evaluating a winner classifier as an ATS probability
is invalid. Source/parameter versions and historical training-input manifests
must be retained with the candidate's recipe identity.

```bash
python research/market_increment_gate.py \
  --predictions /path/to/frozen_candidate_forecasts.csv \
  --outcomes /path/to/outcomes.csv \
  --basis development \
  --output-dir /path/to/research_evaluation
```

Development can never qualify as a forward result. The separate
`--basis forward_declared` mode enforces timestamp/retention checks, but the
word **declared** matters: the evaluator cannot authenticate providers, prove
first-snapshot completeness, or establish independent preregistration.
It never deploys or activates a capture job. Existing `forward_capture.py`
provides version/exclusive-write helpers; its 81×81 joint-PMF capture schema
is distinct and is not silently converted to an observed-atom capture format.

## Input contract

Forecast CSV fields (conditional probabilities exclude the relevant push/tie):

- Identity: `game_id,season,week,iteration,recipe_sha256`.
- Candidate: `margin_mean,p_home_win,p_home_cover,p_push`.
- Market: `spread_line,total_line,home_moneyline,away_moneyline,
  home_spread_odds,away_spread_odds,market_spread_win,market_spread_total_win`.

`spread_line` is the home-minus-away threshold: home -3 / away +3 means
`spread_line=3`. Both side odds refer to that exact opposite-handicap pair.
`p_push` is unconditional ATS push mass; `p_home_cover` is conditional on no
ATS push; `p_home_win` is conditional on a decisive game.

For declared forward records additionally require:

`forecast_utc,kickoff_utc,quote_utc,feature_available_utc,
benchmark_available_utc,retained_utc,training_cutoff_utc,
training_max_season,training_max_week,snapshot_sha256,retention_url,book`.

Every timestamp must carry an explicit timezone. Quotes must be at most five
minutes old at forecast; features/benchmarks available then; snapshots retained
after forecast and before kickoff; training excludes the entire forecast week.
The retention URL/hash must refer to an externally auditable original snapshot.
The CSV fields assert this provenance; verification against retained originals
is an independent review step. Local hashes alone are insufficient.

Outcome CSV: `game_id,home_score,away_score`. Duplicate games, missing/pending
outcomes, labels mixed into forecast input, invalid probabilities, stale quotes,
late features, missing prices and mixed recipe identities fail explicitly.
All decisions are made from probabilities/prices before settlement reads scores.

## Proposed fixed forward checkpoint — inactive

For the next independently registered candidate, lock eligibility, source code,
training/feature availability, recipe and provider adapter before first capture.
Start a new iteration ID if the recipe or selection rule changes. Do not replace
existing forecasts or backfill past games. Weekly refits need immutable parameter
versions linked to the same frozen recipe and independent retained originals.

The proposed primary checkpoint is **exactly 512 prespecified first eligible
games**, with every outcome present, >=200 bets and >=20 season-week clusters.
Do not select completed subsets, drop unfavorable games or issue repeated verdicts
at arbitrary sample sizes. A different registered design requires its own gates.

The evaluator requires ATS log-loss gain >=0.002 over fair 50/50 with a positive
95% week-bootstrap lower bound, and positive priced ROI lower bound. Winner and
margin comparisons remain separate diagnostics; reporting them prevents a
profitable-looking slice from hiding broad probability deterioration. A gate
pass means **eligible for independent forward review**, never automatic
production promotion or an independently established edge. Outcomes/provenance,
recipe registration, provider authenticity and cohort completeness still require
external verification; multiple candidates/checkpoints require a registered
multiple-testing plan. Insufficient/no-bet samples remain unresolved.

The next research hypothesis should be one predeclared pregame team/QB matchup
signal with verifiable available-at times. Fit and choose it on earlier proper
scores, not ROI. This PR builds the evaluation contract; it does not invent a
validated new signal or claim fresh evidence already exists. Native production,
its ledger and existing capture workflows are unchanged.

## Implementation validation

The full repository suite completed with **697 passed, 1 expected failure**.
Notebook synchronization and data validation also passed. All 192 preserved
original R003 artifacts retained their recorded SHA-256 hashes.

An end-to-end development replay of the 816 archived main-period games reproduced
plain's 560 ATS bets and **−32.545 units** under the explicit assumed −110 scenario.
The evaluator rejected forward eligibility and reported that an incremental ATS
edge was not established. This replay tests the evaluation plumbing; it is not a
new model result or evidence of actual archived ATS prices. Focused fixtures cover
price-sensitive selection, pushes, incomplete cohorts and invalid provenance.
