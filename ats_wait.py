"""Hold a finished build until its next 60-minute ATS cutoff, then finalize.

GitHub drops and delays scheduled runs, so the five-minute poll cannot be
trusted to land between T−60 and kickoff (2026-10-19: no build ran from 22:38
to 00:33 UTC and WAS-SF was only recovered after kickoff; 2026-10-26: no
build between 21:49 and 23:39 UTC, so DAL-PHI locked 25 minutes late from a
4.5-hour-old forecast). Instead, a build that finishes within MAX_WAIT_MINUTES
(240) of a cutoff for an unlocked candidate or v1.21 scheduled game stays
alive until that cutoff:

  * if a v1.21 game has no candidate yet, or the newest saved candidate is older than the refresh
    point, run one full build REFRESH_LEAD_MINUTES before the cutoff, so the
    lock carries a recent line; retry at T-70 if inputs remain missing;
  * at the cutoff, finalize with ats_locks.record, re-render the pages and
    commit.

This changes only when finalization happens, never what it may use:
ats_locks.record still freezes the latest candidate saved by the cutoff. The
run keeps the site-build concurrency group while it waits, so builds stay
serialized; polls that arrive meanwhile queue behind it.
An earlier delivered run watches games up to eight hours before their cutoff,
handing off after at most four hours to stay within GitHub's six-hour job limit.
The workflow publishes before waiting and after the first cutoff it processes.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

import ats_locks
from schedule_gate import kickoff

DATA = Path('data')
MAX_WAIT_MINUTES = 240
# Stay on a runner even when the next cutoff is beyond this job's wait
# budget. A queued poll can then take over before the deadline, rather than
# requiring GitHub to deliver a new cron in a narrow pregame window.
WATCH_AHEAD_MINUTES = 480
REFRESH_LEAD_MINUTES = 20
RETRY_LEAD_MINUTES = 10
SETTLE_SECONDS = 20
COLLECTION_INTERVAL_SECONDS = 15 * 60


def pending(data, now, horizon):
    """{cutoff: newest saved generated_utc} for unlocked candidates with now < cutoff <= horizon."""
    locked = {ats_locks.key(r) for r in ats_locks.read(Path(data) / ats_locks.LOCKS)}
    by_game = {}
    for row in ats_locks.read(Path(data) / ats_locks.CANDIDATES):
        cutoff = ats_locks.utc(row['lock_at_utc'])
        if ats_locks.key(row) in locked or not now < cutoff <= horizon:
            continue
        generated = ats_locks.utc(row['generated_utc'])
        identity = (cutoff, ats_locks.key(row))
        by_game[identity] = max(by_game.get(identity, generated), generated)
    # v1.21 cannot save a candidate until official inactive lists arrive (~T-90).
    # Hold scheduled games even with no candidate, so the T-70 refresh can collect
    # the lists. This never creates a candidate or authorizes a late input.
    latest=Path(data)/'latest'
    if (latest/'manifest.json').exists() and (latest/'board.csv').exists():
        manifest=json.loads((latest/'manifest.json').read_text())
        if manifest.get('revision')=='boxscore-composite-v1.21':
            with (latest/'board.csv').open(newline='') as src:
                for row in csv.DictReader(src):
                    ko=kickoff(row)
                    if ko is None or row.get('result','').strip():continue
                    cutoff=ats_locks.deadline(ko)
                    if (manifest['revision'],row['game_id']) not in locked and now<cutoff<=horizon:
                        # An epoch sentinel means no candidate exists yet: refresh even if
                        # this board was generated recently but had unresolved availability.
                        identity = (cutoff, (manifest['revision'],row['game_id']))
                        by_game.setdefault(identity, dt.datetime(1970,1,1,tzinfo=dt.timezone.utc))
    # Every game at a shared kickoff needs fresh inputs. A fresh candidate for
    # one game must never suppress retries for another missing/stale candidate.
    out = {}
    for (cutoff, _), generated in by_game.items():
        out[cutoff] = min(out.get(cutoff, generated), generated)
    return out


def hold(data, horizon, refresh, finalize, clock, sleep):
    """Refresh, retry missing inputs once, and finalize each cutoff up to horizon."""
    steps = []
    refreshed = set()
    while True:
        due = pending(data, clock(), horizon)
        if not due:
            return steps
        cutoff = min(due)
        refresh_at = cutoff - dt.timedelta(minutes=REFRESH_LEAD_MINUTES)
        attempts = [cutoff - dt.timedelta(minutes=lead)
                    for lead in (REFRESH_LEAD_MINUTES, RETRY_LEAD_MINUTES)]
        attempt = next((point for point in attempts if (cutoff, point) not in refreshed), None)
        if attempt is not None and due[cutoff] < refresh_at:
            sleep(max(0.,(attempt - clock()).total_seconds()))
            refreshed.add((cutoff, attempt))
            steps.append(('refresh', cutoff, refresh()))
            # A slow refresh can cross the deadline. Finalize an earlier saved
            # candidate immediately; pending() deliberately excludes past cutoffs.
            if clock() >= cutoff:
                steps.append(('finalize', cutoff, finalize()))
            continue
        sleep(max(0., (cutoff - clock()).total_seconds()) + SETTLE_SECONDS)
        steps.append(('finalize', cutoff, finalize()))


def run(*cmd, check=True):
    print('+', ' '.join(cmd), flush=True)
    return subprocess.run(cmd, check=check).returncode


def sync():
    """Move the checkout to main's tip when that loses nothing in data/.

    commit_data.py pins its first attempt to the checked-out HEAD. After any
    earlier commit in this job (including the build's own commit step), a
    stale checkout reads that commit as a clashing write and falls back to an
    unverified push. Reset only when data/ already matches the tip; otherwise
    keep the checkout and let commit_data's clash check decide.
    """
    if run('git', 'fetch', '--quiet', 'origin', 'main', check=False) != 0:
        print('sync: fetch failed; keeping the checkout', flush=True)
        return False
    if run('git', 'diff', '--quiet', 'FETCH_HEAD', '--', 'data', check=False) != 0:
        print('sync: data/ differs from main; keeping the checkout', flush=True)
        return False
    run('git', 'reset', '--quiet', '--hard', 'FETCH_HEAD')
    return True


def commit(message):
    """Commit data/, then move the checkout to the new tip. Never resets after a failed commit."""
    run(sys.executable, 'validate_data_files.py')
    run(sys.executable, 'commit_data.py', '--branch', 'main', '--message', message)
    sync()


def stamp(now):
    return now.strftime('%FT%H:%MZ')


def watch(data, horizon, refresh, finalize, clock, sleep):
    """Carry an early delivered poll forward, bounded by this job's wait budget."""
    steps = hold(data, horizon, refresh, finalize, clock, sleep)
    now = clock()
    upcoming = pending(data, now, now + dt.timedelta(minutes=WATCH_AHEAD_MINUTES))
    if now < horizon and upcoming:
        print(f'ATS watch: handing off at {horizon.isoformat()}; '
              f'next cutoff {min(upcoming).isoformat()}', flush=True)
        sleep((horizon - now).total_seconds())
        steps.append(('handoff', min(upcoming), None))
    return steps


def refresh_build():
    code = run(sys.executable, 'build_site.py', check=False)
    commit(f'ledger {stamp(dt.datetime.now(dt.timezone.utc))} ATS refresh')
    return code


def collect_availability():
    # The separate collector queues behind this held build. Keep its source
    # checks alive here instead of leaving monitoring silent for four hours.
    code = run(sys.executable, 'availability_collect.py', check=False)
    commit(f'availability {stamp(dt.datetime.now(dt.timezone.utc))} ATS watch')
    return code


def monitored_sleep(seconds, clock, sleep, collect):
    """Keep source collection alive during long waits, without extending the wake time."""
    wake = clock() + dt.timedelta(seconds=seconds)
    while (wake - clock()).total_seconds() > COLLECTION_INTERVAL_SECONDS:
        sleep(COLLECTION_INTERVAL_SECONDS)
        collect()
    sleep(max(0., (wake - clock()).total_seconds()))


def finalize_locks():
    result = ats_locks.record(DATA)
    print(f'ATS held capture: {result}', flush=True)
    run(sys.executable, 'build_site.py', '--pages-only')
    commit(f'ledger {stamp(dt.datetime.now(dt.timezone.utc))} ATS lock')
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--max-wait-minutes', type=float, default=MAX_WAIT_MINUTES)
    ap.add_argument('--sync-only', action='store_true', help='only move the checkout to main (see sync)')
    args = ap.parse_args(argv)
    sync()
    if args.sync_only:
        return 0
    clock = lambda: dt.datetime.now(dt.timezone.utc)  # noqa: E731
    horizon = clock() + dt.timedelta(minutes=args.max_wait_minutes)
    due = pending(DATA, clock(), horizon)
    # End at the first cutoff so the workflow publishes those locks immediately;
    # the queued run takes the next kickoff group with a fresh model build.
    if due:
        horizon = min(horizon, min(due))
    print(f'ATS hold: {len(due)} cutoff(s) by {horizon.isoformat()}: '
          + (', '.join(c.isoformat() for c in sorted(due)) or 'none'), flush=True)
    sleep = lambda seconds: monitored_sleep(seconds, clock, time.sleep, collect_availability)
    for step in watch(DATA, horizon, refresh_build, finalize_locks, clock, sleep):
        print(f'ATS hold: {step[0]} for {step[1].isoformat()}: {step[2]}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
