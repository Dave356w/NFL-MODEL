# Locked forward protocol - R001-F1

Prepared 2026-10-16. Status: **planned, not activated**. No real prospective
forecasts, provider quotes or results were collected in this session. Synthetic
capture fixtures are unit tests only. Deployment and betting require explicit
owner approval. No automation or live provider connection has been enabled.

## Start, cohort and locking

Before activation, publish the protocol/model hashes to a trustworthy external
timestamped, append-only store. Connect and validate one provider adapter with
documented market orientation, game matching, UTC event/receipt timestamps and
overtime/void settlement conventions. The current writer preserves provider
declarations but cannot independently authenticate them. Local file permissions
and SHA-256 checks are not external notarization or deletion-proof retention.

Start with the first NFL regular-season game after successful registration and
adapter acceptance. Evaluate the first **512 eligible games**, without optional
stopping or interim model selection. Both empirical A and its R001 tie hurdle
must be captured for each game from exactly the same provider quote and input
data. Smooth is an optional fixed diagnostic and cannot replace empirical A as
the primary comparator. No 2017-2026 historical forecast is backfilled into this
cohort. If R002 is tested, it requires a new registration and a clearly separate
fresh cohort; don't select it using R001's forward outcomes.

Freeze model formulas, window, penalties, support and prior. Weekly coefficients
and tie counts may update under those rules with strictly prior-week outcomes.
Each weekly parameter artifact receives its own content hash and immutable
version including code, config and training-input hashes. Archive source and
parameter bytes with the manifest; never reuse a version ID after any change.

## Capture

Take the first eligible snapshot at **T-60 minutes, allowed window T-65 to T-55**.
Provider event time must precede receipt, both precede generation, and the quote
must be no more than 300 seconds old. Record timezone-aware UTC kickoff,
generation, provider-event and local-receipt times. Features and parameters use
only the previous NFL week or earlier, with all source records available by the
declared weekly cutoff. Log that cutoff and max training season/week.

Embed one normalized 81x81 joint PMF and the exact provider quote JSON in each
snapshot, plus record and provider-payload hashes. Derive every probability from
that PMF. Record score/total/spread orientation explicitly in provider acceptance.
Quotes must contain valid two-sided American moneylines and the spread/total
used by the forecast. No substitute provider, stale line, inferred timestamp or
model fallback. Reject ineligible snapshots and append the reason to a separate
failure log before viewing outcomes; keep failed/missing games in an attrition
table. Missing either primary arm excludes the game from paired scoring, with
reason retained; never backfill. Pause qualification if attrition exceeds 5%.

`research/forward_capture.py` implements version registration, first-write-only
snapshot storage, timestamp/market-input/PMF guards and local hash verification.
It accepts already generated forecasts and provider payloads. It does not fetch
quotes, construct current production features, schedule jobs, grade results or
prove an upstream timestamp is truthful. A provider adapter and independently
timestamped retention must be added and tested before activation.

Example command shapes (these require real validated files, not supplied mocks):

```bash
python research/forward_capture.py --store research/forward/R001-F1 register MODEL_SPEC.json
python research/forward_capture.py --store research/forward/R001-F1 capture VERSION_SHA256 REQUEST.json JOINT.npz
python research/forward_capture.py --store research/forward/R001-F1 verify
```

Model spec fields: `model_name`, `config`, `source_files`, `parameter_files`,
`training_input_sha256`. File paths are relative to `--root`. Request fields and
strict timestamp fixtures are documented by `tests/test_forward_capture.py`.
`JOINT.npz` must contain `joint`. Register all weekly mean/covariance/tie
parameters, not just the static formula. Protect `data/`, `public/` and the source
root against capture output. Keep research captures outside existing ledgers.

## Evaluation and decision

Primary: paired empirical-A-minus-R001 exact joint NLL, nats/game. At the locked
512-game end, compute 10,000 season-stratified whole-week bootstrap draws,
seed 20261016, two-sided 95% interval. Single primary comparison; no selection
among secondary targets. Publish seasonal counts/gains, leave-one-week/season
stability and individual influences. Keep outcomes in a separate append-only
grading file referencing immutable snapshot hashes. Corrections append a new
grading revision; forecasts never change.

Secondary: every home/away/MOV/total NLL and CRPS, unconditional H/T/A NLL/Brier,
conditional decisive-winner LL/Brier, tie LL/Brier, 50/80/90 coverage and width,
and reliability/PIT diagnostics. The tie count will remain small; do not claim
tie calibration is established just because pooled joint NLL improves.

Advance for owner review only if primary gain >=0.005 nats/game, the 95% lower
bound >0, no marginal NLL or CRPS worsens by >0.01, winner losses do not worsen
numerically beyond tolerance, and gains remain positive in each adequately
populated season (>=100 observations). Report smaller seasons without a pass/fail
claim. Require no leakage/timestamp violations, attrition <=5%, and disclose all
earlier research exposure. This is consideration for further review, never an
automatic production promotion.

Independent betting diagnostics: one flat 1u hypothetical moneyline bet on the
larger conditional winner probability, abstain on exact 0.5, exclude market
pick'ems identically, ties push only when confirmed by provider settlement.
Report n, units, ROI, SE/interval, no-vig moneyline LL/Brier, same-row favorites,
underdogs and the negative-hold null. No ROI threshold or best ROI can select the
model. Spread/total/team-total ROI requires actually captured prices and a new
locked settlement/evaluation specification; otherwise report probabilities only.
