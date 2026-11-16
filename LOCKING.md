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
New publication requests retain an active deployment's run ID and queue one
follow-up after it finishes, ensuring that saved state created after its
checkout is delivered. Provider and persistence failures retry after one
minute; only a healthy watcher outside every game's collection window waits
five minutes. Updates to the weekly map, kickoff parser and coverage monitor
also restart a running controller so it cannot keep using imported old code.

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
`ats_wait.py` (removed 2026-11-16) concurrently as an additional journal writer.

## November 15 parser incident and recovery

The T-60 controller was running, but five 18:00 UTC games never produced an
eligible candidate. Their saved observations failed on C/G and G/T positions,
Mike/Michael Danna, Nick/Nicholas Singleton, and the official-list spelling
Tyroin/Tyrion Ingram-Dawkins. Compound positions now accept only known position
codes. Name exceptions require an exact GSIS ID and canonical roster name;
unknown or ambiguous players still block completeness.

The owner explicitly requested recovery on November 15. Five pinned timing
observations, generated at 16:56:42 UTC and committed at 16:58:26 UTC (before
the 17:00 UTC cutoff), are authorized in `ats_retro_requests.json`. Recovery
preserves the exact captured price, saved weekly map, original collection
errors, and v1.24 replacement-QB overlay. No current inputs or scores select
the picks. These join ordinary pooled results, while backend provenance remains
`Owner-requested retro lock`, outside native forward evidence. Existing native
locks in any runtime store take precedence. Nothing is backdated or rewritten.

The monitor now requires actual durable candidate coverage by T-65, reports
missed deadlines and late finalization independently of heartbeat health,
and the watcher records team-specific source/parser blockers. Missed-game
capture status references the last saved pre-cutoff observation rather than
a post-kickoff board that has lost its availability columns. A controller
code change stops the old serialized watcher, waits for it to finish, and
requests a new process from main; ordinary data commits do not restart it.
Authorized recoveries are committed before a full model refresh can fail.

Automatic fallback remains the newest eligible, durably saved pre-T-60
candidate, even if a later refresh or provider request fails. Earlier blocked
snapshots never silently become native locks; this incident's explicit recovery
is separate from that production contract.

Long-running watchers also refresh the builder-owned lock journal and schedule
from the same fetched main commit. This makes concurrent recoveries visible to
coverage monitoring without waiting for the next process restart. The lock
journal must extend its local prefix; a rewrite fails closed. Watcher-owned
runtime candidates, receipts and pending evidence are never replaced.

## Lock continuity and week-10 coverage fixes (2026-11-15)

Owner request: maintain picks robustly. A saved lock from any revision remains the game's
decision in every public view, CSV and calibration export (`ats_locks.current_records`;
`season_ats.LOCK_POLICY_VERSION`). A revision change can no longer swap a real pick for a
replay: e.g. the Thursday WAS-NYG lock saved under v1.22 now stays authoritative under v1.24.
Replay only fills games without a saved lock, and the QB overlay never alters a saved lock.

Week 10 also missed SF-DAL and PIT-CIN. DAL's club page lists only DAL's table (rejected by
the old both-opponents rule) and CIN's report had two Questionable late additions with blank
Friday cells (read as an unpublished day). Both rules are corrected in `availability_collect.py`;
see `AVAILABILITY.md`. The watchdog now treats any revision's lock as coverage, raises AT RISK
alerts from T-90 naming the latest saved blockers, and retains missed-cutoff alerts for 24 hours.
Owner follow-up (2026-11-15, "Repair all lost picks"): SF-DAL and PIT-CIN are recovered as
owner-requested retro locks in `ats_retro_requests.json`, each from the last watcher observation
committed before its T-60 cutoff (SF-DAL `b1399660`, 20:23:47 UTC; PIT-CIN `f5d0539e`, 00:19:56 UTC),
with its exact paired price, saved weekly map and v1.24 overlay. Original blockers are preserved. Every
other 2026 game with a T-60 deadline after ATS adoption already has a saved lock.

## Public regrade (2026-11-16)

Owner decision: the public pages switch to the current model's 2026 regrade, superseding the
display rule above. `ats_locks.public_records` shows only the current revision's own saved
locks (v1.24, at their lock line and price); every other graded game, including games locked by
v1.18–v1.22, shows v1.24's walk-forward replay. Capture and the watchdog still use
`current_records`, so a game saved by any revision is never relocked. The journals are unchanged,
and native-lock results against same-row baselines stay in `data/ledger_report.txt`.
