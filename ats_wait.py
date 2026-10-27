"""Hold a finished build until its next 60-minute ATS cutoff, then finalize.

GitHub drops and delays scheduled runs, so the five-minute poll cannot be
trusted to land between T−60 and kickoff (2026-10-19: no build ran from 22:38
to 00:33 UTC and WAS-SF was only recovered after kickoff; 2026-10-26: no
build between 21:49 and 23:39 UTC, so DAL-PHI locked 25 minutes late from a
4.5-hour-old forecast). Instead, a build that finishes within MAX_WAIT_MINUTES
(150) of a cutoff for an already-saved,
unlocked candidate stays alive until that cutoff:

  * if the newest saved candidate for the cutoff is older than the refresh
    point, run one full build REFRESH_LEAD_MINUTES before the cutoff, so the
    lock carries a recent line (a failed refresh keeps the older candidate);
  * at the cutoff, finalize with ats_locks.record, re-render the pages and
    commit.

This changes only when finalization happens, never what it may use:
ats_locks.record still freezes the latest candidate saved by the cutoff. The
run keeps the site-build concurrency group while it waits, so builds stay
serialized; polls that arrive meanwhile queue behind it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
import time
from pathlib import Path

import ats_locks

DATA = Path('data')
MAX_WAIT_MINUTES = 150
REFRESH_LEAD_MINUTES = 10
SETTLE_SECONDS = 20


def pending(data, now, horizon):
    """{cutoff: newest saved generated_utc} for unlocked candidates with now < cutoff <= horizon."""
    locked = {ats_locks.key(r) for r in ats_locks.read(Path(data) / ats_locks.LOCKS)}
    out = {}
    for row in ats_locks.read(Path(data) / ats_locks.CANDIDATES):
        cutoff = ats_locks.utc(row['lock_at_utc'])
        if ats_locks.key(row) in locked or not now < cutoff <= horizon:
            continue
        generated = ats_locks.utc(row['generated_utc'])
        out[cutoff] = max(out.get(cutoff, generated), generated)
    return out


def hold(data, horizon, refresh, finalize, clock, sleep):
    """Refresh at most once and finalize at each cutoff up to horizon. Returns the steps taken."""
    steps = []
    refreshed = set()
    while True:
        due = pending(data, clock(), horizon)
        if not due:
            return steps
        cutoff = min(due)
        refresh_at = cutoff - dt.timedelta(minutes=REFRESH_LEAD_MINUTES)
        if cutoff not in refreshed and due[cutoff] < refresh_at and clock() < refresh_at:
            sleep((refresh_at - clock()).total_seconds())
            refreshed.add(cutoff)
            steps.append(('refresh', cutoff, refresh()))
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


def refresh_build():
    code = run(sys.executable, 'build_site.py', check=False)
    commit(f'ledger {stamp(dt.datetime.now(dt.timezone.utc))} ATS refresh')
    return code


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
    print(f'ATS hold: {len(due)} cutoff(s) by {horizon.isoformat()}: '
          + (', '.join(c.isoformat() for c in sorted(due)) or 'none'), flush=True)
    for step in hold(DATA, horizon, refresh_build, finalize_locks, clock, time.sleep):
        print(f'ATS hold: {step[0]} for {step[1].isoformat()}: {step[2]}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
