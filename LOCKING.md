# Durable T−60 locking

Adopted 2026-11-10 at the owner's request. The probability recipe, weekly
spread map, side-selection rule and T−60 cutoff are unchanged. Historical
candidate and lock files remain byte-for-byte intact. New captures use
`median-mov-weekly-decay-ats-t60-durable-2026-11-10-v4`.

Full builds prepare `data/lock_inputs`: the prior-week coefficient fit, full
precision board inputs, availability inputs, weekly map and hashed Parquet
files. Preparing a new bundle never changes an existing selection. A separate
watcher loads and verifies this bundle, then collects official reports,
inactives and paired prices and rescores the current games without refitting
or rerunning historical research. It starts collecting within three hours of
kickoff and refreshes approximately once per minute (plus provider/commit
latency). Outside that window it checks for new bundles every five minutes.

## Eligibility and durability

An official candidate requires both complete, fresh official inactive lists,
valid final-report/QB evidence and a paired captured price for the exact
handicap. Unknown players, conflicts and parser failures block eligibility;
absence of evidence never means healthy or active. The probability offset,
spread and price use the same captured bookmaker offer.

The forecast must be generated within the last ten minutes before T−60 and
the quote must have been captured within five minutes before that forecast.
The watcher commits the candidate and source evidence before acknowledging
it. A receipt names the server-created commit and a conservative upper bound
on its timestamp (the end of its recorded second). Only candidates whose
confirmed save is at or before T−60 can finalize. A commit that crosses the
deadline is ineligible. At T−60 the newest eligible durable candidate is
immutable, including its handicap and price. No eligible candidate means no
official pick. Later forecasts cannot repair it with later inputs.

Receipts can be reconstructed after a crash only from commits already
reachable on `origin/main`. This handles a crash between saving a candidate
and saving its receipt. Recovery retains the existing 48-hour finalization
limit and records actual finalization times.

## Ownership, restart and publication

`lock-watcher.yml` owns `data/lock_runtime/` and uses its own concurrency group.
Game evidence is partitioned by season/week. Quote and diagnostic captures
are immutable individual files, so each commit sends only new captures rather
than repeatedly uploading an entire season's observations.
The full model and ordinary collector write separate paths. Old append-only
evidence is preserved; reporting combines old locks with runtime locks and
rejects conflicting decisions for the same revision/game.

The watcher finalizes saved candidates before trying any slow source request.
Commit failures retain local evidence for retry; a fatal workflow failure also
uploads a recovery artifact. Each runner requests and verifies a queued
successor after 270 minutes, leaving 30 minutes of job budget. Hourly wakeups
and a separate health monitor are backups. The monitor restarts an absent
watcher and fails visibly when the committed heartbeat is over ten minutes
old. Handoff acknowledgement means queued, not guaranteed runner availability.
GitHub outages/runner starvation can still delay work; the controller fails
closed and records the gap rather than inventing an on-time capture.

Page publication has one shared queue. Every publisher checks out latest main
after entering that queue and renders saved state; it never deploys a stale
full-build artifact. Lock commits and publication intents are saved together.
Failed publication is retried until the deployment run succeeds. Provisional
cards expire in an already-open browser at T−60; only backend saved decisions
can appear as locked. A publisher failure cannot change a saved pick.

## Timing diagnostics

Immutable files in `timing_forecasts/` preserve blocked and eligible observations. At
T−120, T−90, T−60, T−45 and T−30, `timing_checkpoints.jsonl` references the
latest observation actually captured by that deadline, with its age and a
five-minute freshness flag. Missing observations stay missing. Post-T−60
snapshots remain diagnostics and cannot create candidates or change locks.
Compare identical games and retain missingness/readiness and price provenance;
do not select a new deadline from retrospective profit alone.

For one operational heartbeat use the watcher's `once` dispatch input.
For a publication retry dispatch `publish.yml`. Dispatch `lock-watchdog.yml`
to check or restart the continuous watcher. Do not run the old build-held
`ats_wait.py` concurrently as an additional journal writer.
