"""Holding a build until the T−60 cutoff instead of trusting the next cron."""
import csv
import datetime as dt
import json
import subprocess
from pathlib import Path
from statistics import NormalDist

import pytest

import ats_locks as a
import ats_wait as w
import nfl_model as m

UTC = dt.timezone.utc
KO = dt.datetime(2026, 10, 25, 17, tzinfo=UTC)
CUTOFF = KO - dt.timedelta(hours=1)
RULE = dict(season=2026, week=7, training_max_season=2026, training_max_week=6, training_games=1450,
            training_band_counts=[500, 510, 270, 170], cuts=[3., 7., 10.], magnitudes=[3., 4., 7., 14.],
            method='weighted_median_signed_mov_weekly_decay', policy_version='median-mov-weekly-decay-2026-11-04-v2',
            half_life_seasons=1.)
RAW = dict(game_id='2026_07_TEN_IND', season=2026, week=7, home='IND', away='TEN',
           gameday='2026-10-25', gametime='13:00', result='', ready=True,
           model_wp=NormalDist().cdf(8 / 12.37), spread_line=7.,
           home_injury_report='final', away_injury_report='final')


class Clock:
    def __init__(self, now):
        self.now = now
        self.slept = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        assert seconds >= 0
        self.slept.append(seconds)
        self.now += dt.timedelta(seconds=seconds)


def board(data, now, **changes):
    (data / 'latest').mkdir(exist_ok=True)
    (data / 'latest/fixed_band_rules.json').write_text(json.dumps([RULE]))
    manifest = dict(revision='boxscore-composite-v1.19', season=2026, week=7, generated_utc=now.isoformat(),
                    config_signature='test', recipe={'family': 'rates_core_avail_cs'})
    (data / 'latest/manifest.json').write_text(json.dumps(manifest))
    row = dict(RAW, **changes)
    with (data / 'latest/board.csv').open('w', newline='') as f:
        out = csv.DictWriter(f, fieldnames=list(row))
        out.writeheader()
        out.writerow(row)


def candidate(data, generated, game_id='g1', lock=CUTOFF):
    a.append(data / a.CANDIDATES, [dict(revision=m.REVISION, game_id=game_id, lock_at_utc=lock.isoformat(),
                                        generated_utc=generated.isoformat())])


def test_pending_only_counts_saved_unlocked_future_cutoffs_inside_horizon(tmp_path):
    now = CUTOFF - dt.timedelta(minutes=40)
    horizon = now + dt.timedelta(minutes=90)
    candidate(tmp_path, now - dt.timedelta(minutes=30))
    candidate(tmp_path, now - dt.timedelta(minutes=5))
    candidate(tmp_path, now, game_id='locked')
    candidate(tmp_path, now, game_id='past', lock=now - dt.timedelta(seconds=1))
    candidate(tmp_path, now, game_id='far', lock=horizon + dt.timedelta(seconds=1))
    a.append(tmp_path / a.LOCKS, [dict(revision=m.REVISION, game_id='locked')])
    assert w.pending(tmp_path, now, horizon) == {CUTOFF: now - dt.timedelta(minutes=5)}
    assert w.pending(tmp_path / 'empty', now, horizon) == {}


def test_no_pending_cutoff_returns_immediately(tmp_path):
    clock = Clock(CUTOFF - dt.timedelta(minutes=40))
    candidate(tmp_path, clock.now, lock=clock.now + dt.timedelta(minutes=91))  # beyond the hold horizon
    steps = w.hold(tmp_path, clock.now + dt.timedelta(minutes=90), lambda: pytest.fail('refresh'),
                   lambda: pytest.fail('finalize'), clock, clock.sleep)
    assert steps == [] and clock.slept == []


def test_stale_candidate_refreshes_once_then_finalizes_after_cutoff(tmp_path):
    clock = Clock(CUTOFF - dt.timedelta(minutes=38))
    candidate(tmp_path, clock.now - dt.timedelta(minutes=1))
    calls = []

    def refresh():
        calls.append(('refresh', clock.now))
        candidate(tmp_path, clock.now + dt.timedelta(minutes=1))
        return 0

    def finalize():
        calls.append(('finalize', clock.now))
        a.append(tmp_path / a.LOCKS, [dict(revision=m.REVISION, game_id='g1')])
        return {'locks': 1}

    steps = w.hold(tmp_path, clock.now + dt.timedelta(minutes=90), refresh, finalize, clock, clock.sleep)
    assert [s[0] for s in steps] == ['refresh', 'finalize']
    assert calls[0][1] == CUTOFF - dt.timedelta(minutes=w.REFRESH_LEAD_MINUTES)
    assert CUTOFF < calls[1][1] < KO


def test_fresh_candidate_skips_refresh_and_failed_refresh_is_retried_once(tmp_path):
    clock = Clock(CUTOFF - dt.timedelta(minutes=5))
    candidate(tmp_path, clock.now)
    finalize = lambda: a.append(tmp_path / a.LOCKS, [dict(revision=m.REVISION, game_id='g1')])  # noqa: E731
    steps = w.hold(tmp_path, clock.now + dt.timedelta(minutes=90), lambda: pytest.fail('refresh'),
                   finalize, clock, clock.sleep)
    assert [s[0] for s in steps] == ['finalize']

    (tmp_path / a.LOCKS).unlink()
    (tmp_path / a.CANDIDATES).unlink()
    clock = Clock(CUTOFF - dt.timedelta(minutes=30))
    candidate(tmp_path, clock.now - dt.timedelta(minutes=30))
    steps = w.hold(tmp_path, clock.now + dt.timedelta(minutes=90), lambda: 1, finalize, clock, clock.sleep)
    assert [s[0] for s in steps] == ['refresh', 'refresh', 'finalize']


def test_unfinalizable_candidate_does_not_loop(tmp_path):
    # e.g. the provider moved kickoff, so record() declines to lock it.
    clock = Clock(CUTOFF - dt.timedelta(minutes=5))
    candidate(tmp_path, clock.now)
    steps = w.hold(tmp_path, clock.now + dt.timedelta(minutes=90), lambda: 0, lambda: {'locks': 0},
                   clock, clock.sleep)
    assert [s[0] for s in steps] == ['finalize']


def test_failed_early_refresh_can_recover_before_cutoff(tmp_path):
    saved = CUTOFF - dt.timedelta(minutes=40)
    board(tmp_path, saved)
    a.record(tmp_path, saved)
    clock = Clock(saved)
    calls = []

    def refresh():
        calls.append(clock.now)
        if len(calls) == 1:
            return 1
        board(tmp_path, clock.now)
        a.record(tmp_path, clock.now)
        return 0

    steps = w.hold(tmp_path, KO, refresh, lambda: a.record(tmp_path, clock.now), clock, clock.sleep)
    assert calls == [CUTOFF - dt.timedelta(minutes=20), CUTOFF - dt.timedelta(minutes=10)]
    assert [s[0] for s in steps] == ['refresh', 'refresh', 'finalize']
    lock, = a.read(tmp_path / a.LOCKS)
    assert a.utc(lock['generated_utc']) == calls[-1]
    assert a.utc(lock['finalized_utc']) < KO


def test_slow_refresh_crossing_cutoff_finalizes_earlier_saved_candidate(tmp_path):
    saved = CUTOFF - dt.timedelta(minutes=40)
    board(tmp_path, saved)
    a.record(tmp_path, saved)
    clock = Clock(saved)

    def refresh():
        clock.sleep(21 * 60)
        board(tmp_path, clock.now)  # post-cutoff inputs cannot become a candidate
        a.record(tmp_path, clock.now)
        return 0

    steps = w.hold(tmp_path, KO, refresh, lambda: a.record(tmp_path, clock.now), clock, clock.sleep)
    assert [s[0] for s in steps] == ['refresh', 'finalize']
    lock, = a.read(tmp_path / a.LOCKS)
    assert a.utc(lock['generated_utc']) == saved
    assert a.utc(lock['finalized_utc']) == CUTOFF + dt.timedelta(minutes=1)


def test_early_sunday_poll_stays_awake_for_a_queued_handoff(tmp_path):
    # Nov 8's early poll had no inactive-gated candidate and the next delivered
    # build was after London's cutoff. Watch the scheduled game across jobs.
    clock = Clock(CUTOFF - dt.timedelta(minutes=350))
    board(tmp_path, clock.now)
    manifest = tmp_path / 'latest/manifest.json'
    data = json.loads(manifest.read_text())
    data['revision'] = 'boxscore-composite-v1.21'
    manifest.write_text(json.dumps(data))
    horizon = clock.now + dt.timedelta(minutes=w.MAX_WAIT_MINUTES)
    steps = w.watch(tmp_path, horizon, lambda: pytest.fail('early refresh'),
                    lambda: pytest.fail('early finalization'), clock, clock.sleep)
    assert steps == [('handoff', CUTOFF, None)]
    assert clock.now == horizon < CUTOFF


def test_watch_does_not_wait_for_games_outside_its_window(tmp_path):
    clock = Clock(CUTOFF - dt.timedelta(minutes=w.WATCH_AHEAD_MINUTES + 1))
    candidate(tmp_path, clock.now)
    assert w.watch(tmp_path, clock.now + dt.timedelta(minutes=w.MAX_WAIT_MINUTES),
                   lambda: 0, lambda: 0, clock, clock.sleep) == []
    assert clock.slept == []


def test_consecutive_cutoffs_are_each_finalized_in_order(tmp_path):
    clock = Clock(CUTOFF - dt.timedelta(minutes=5))
    later = CUTOFF + dt.timedelta(minutes=20)
    candidate(tmp_path, clock.now, game_id='early')
    candidate(tmp_path, clock.now, game_id='late', lock=later)
    order = []

    def finalize():
        for gid, lock in (('early', CUTOFF), ('late', later)):
            if clock.now >= lock and gid not in order:
                order.append(gid)
                a.append(tmp_path / a.LOCKS, [dict(revision=m.REVISION, game_id=gid)])

    steps = w.hold(tmp_path, clock.now + dt.timedelta(minutes=90), lambda: 0, finalize, clock, clock.sleep)
    # The early candidate is fresh; the late one is stale by its own refresh point.
    assert [(s[0], s[1]) for s in steps] == [('finalize', CUTOFF), ('refresh', later),
                                          ('refresh', later), ('finalize', later)]
    assert order == ['early', 'late']


def test_held_build_records_a_pregame_lock_not_a_recovery(tmp_path):
    """The WAS-SF timeline: candidate saved 38 minutes before the cutoff, no later poll."""
    saved = CUTOFF - dt.timedelta(minutes=38)
    board(tmp_path, saved)
    assert a.record(tmp_path, saved) == {'candidates': 1, 'locks': 0}
    clock = Clock(saved + dt.timedelta(minutes=1))
    steps = w.hold(tmp_path, clock.now + dt.timedelta(minutes=90), lambda: 1,
                   lambda: a.record(tmp_path, clock.now), clock, clock.sleep)
    assert steps[-1][2] == {'candidates': 0, 'locks': 1}
    lock, = a.read(tmp_path / a.LOCKS)
    assert lock['generated_utc'] == saved.isoformat()
    assert CUTOFF <= a.utc(lock['finalized_utc']) < KO
    assert 'recovered_after_kickoff' not in lock
    a.validate_store(tmp_path)


def test_workflow_holds_after_committing_and_still_deploys():
    text = (Path(__file__).resolve().parents[1] / '.github/workflows/build.yml').read_text()
    build = text.split('\n  build:\n', 1)[1].split('\n  deploy:\n', 1)[0]
    order = ['python build_site.py', 'Commit ledger and snapshots', 'python ats_wait.py',
             'Commit ATS locks', 'Upload Pages artifact']
    assert [build.index(s) for s in order] == sorted(build.index(s) for s in order)
    hold = build.split('Hold for the 60-minute ATS cutoff', 1)[1].split('- name:', 1)[0]
    assert 'continue-on-error: true' in hold and 'GITHUB_TOKEN' in hold and '!cancelled()' in hold
    timeout = int(build.split('timeout-minutes: ', 1)[1].split()[0])
    hold_timeout = int(hold.split('timeout-minutes: ', 1)[1].split()[0])
    # The hold step needs room after the last cutoff to refresh pages and commit.
    assert hold_timeout >= w.MAX_WAIT_MINUTES + 20
    assert timeout >= 75 + hold_timeout
    assert build.index('name: Publish current board\n') < build.index('Hold for the 60-minute ATS cutoff')
    # Default GitHub concurrency replaces the pending run. Both journal writers
    # must retain the queue so an availability poll cannot discard the handoff.
    root = Path(__file__).resolve().parents[1]
    for workflow in ('build.yml', 'availability.yml'):
        source = (root / '.github/workflows' / workflow).read_text()
        assert 'group: site-build' in source and 'queue: max' in source


def test_default_hold_reaches_a_cutoff_150_minutes_out_and_no_further(tmp_path):
    now = CUTOFF - dt.timedelta(minutes=140)
    horizon = now + dt.timedelta(minutes=w.MAX_WAIT_MINUTES)
    candidate(tmp_path, now - dt.timedelta(minutes=5))
    candidate(tmp_path, now, game_id='beyond', lock=horizon + dt.timedelta(minutes=1))
    assert w.pending(tmp_path, now, horizon) == {CUTOFF: now - dt.timedelta(minutes=5)}


def test_monday_style_early_build_holds_refreshes_and_finalizes_at_the_cutoff(tmp_path):
    # A build finishing 86 minutes before the cutoff (as a 21:49 UTC Monday poll
    # would have) refreshes once at T-70 and finalizes just after T-60.
    clock = Clock(CUTOFF - dt.timedelta(minutes=86))
    candidate(tmp_path, clock.now - dt.timedelta(minutes=10))
    times = []

    def refresh():
        times.append(('refresh', clock.now))
        candidate(tmp_path, clock.now)
        return 0

    def finalize():
        times.append(('finalize', clock.now))
        a.append(tmp_path / a.LOCKS, [dict(revision=m.REVISION, game_id='g1')])
        return {'locks': 1}

    steps = w.hold(tmp_path, clock.now + dt.timedelta(minutes=w.MAX_WAIT_MINUTES), refresh, finalize,
                   clock, clock.sleep)
    assert [s[0] for s in steps] == ['refresh', 'finalize']
    assert times[0][1] == CUTOFF - dt.timedelta(minutes=w.REFRESH_LEAD_MINUTES)
    assert CUTOFF < times[1][1] <= CUTOFF + dt.timedelta(seconds=w.SETTLE_SECONDS)


def test_checkout_only_moves_after_a_successful_commit(monkeypatch):
    calls = []

    def run(*cmd, check=True):
        calls.append(cmd[1] if cmd[0] != 'git' else f'git {cmd[1]}')
        if cmd[1] == 'commit_data.py' and fail:
            raise w.subprocess.CalledProcessError(1, cmd)
        return 0

    monkeypatch.setattr(w, 'run', run)
    fail = False
    w.commit('ledger')
    assert calls == ['validate_data_files.py', 'commit_data.py', 'git fetch', 'git diff', 'git reset']
    calls.clear()
    fail = True
    with pytest.raises(w.subprocess.CalledProcessError):
        w.commit('ledger')
    assert calls == ['validate_data_files.py', 'commit_data.py']


def git(cwd, *args):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def stale_checkout(tmp_path, monkeypatch):
    """A job checkout one commit behind main, as after the build's own commit step."""
    remote, job, bot = tmp_path / 'remote.git', tmp_path / 'job', tmp_path / 'bot'
    git(tmp_path, 'init', '-q', '--bare', '-b', 'main', str(remote))
    git(tmp_path, 'clone', '-q', str(remote), str(bot))
    git(bot, 'config', 'user.email', 't@t'), git(bot, 'config', 'user.name', 't')
    (bot / 'data').mkdir()
    (bot / 'data/ledger.jsonl').write_text('a\n')
    git(bot, 'add', '.'), git(bot, 'commit', '-qm', 'base'), git(bot, 'push', '-q', 'origin', 'main')
    git(tmp_path, 'clone', '-q', str(remote), str(job))
    (bot / 'data/ledger.jsonl').write_text('a\nb\n')  # what the build's commit step landed
    git(bot, 'commit', '-qam', 'ledger'), git(bot, 'push', '-q', 'origin', 'main')
    (job / 'data/ledger.jsonl').write_text('a\nb\n')  # the job's working tree after that commit
    monkeypatch.chdir(job)
    return job, bot


def test_sync_moves_a_stale_checkout_when_data_matches_main(stale_checkout):
    job, bot = stale_checkout
    assert git(job, 'status', '--porcelain', 'data')  # the bug: committed data looks uncommitted
    assert w.sync() is True
    assert git(job, 'rev-parse', 'HEAD') == git(bot, 'rev-parse', 'HEAD')
    assert git(job, 'status', '--porcelain', 'data') == ''


def test_sync_keeps_uncommitted_data(stale_checkout):
    job, bot = stale_checkout
    (job / 'data/ledger.jsonl').write_text('a\nb\nlock\n')  # a lock row the hold never committed
    before = git(job, 'rev-parse', 'HEAD')
    assert w.sync() is False
    assert git(job, 'rev-parse', 'HEAD') == before
    assert (job / 'data/ledger.jsonl').read_text() == 'a\nb\nlock\n'


def test_sync_survives_an_unreachable_remote(stale_checkout):
    job, bot = stale_checkout
    git(job, 'remote', 'set-url', 'origin', str(job.parent / 'missing.git'))
    before = git(job, 'rev-parse', 'HEAD')
    assert w.sync() is False
    assert git(job, 'rev-parse', 'HEAD') == before


def test_missing_game_is_not_masked_by_fresh_candidate_at_same_cutoff(tmp_path):
    clock = Clock(CUTOFF - dt.timedelta(minutes=8))
    board(tmp_path, clock.now)
    path = tmp_path / 'latest/manifest.json'
    manifest = json.loads(path.read_text())
    manifest['revision'] = m.REVISION
    path.write_text(json.dumps(manifest))
    # A different game has fresh inputs, but TEN-IND still has no candidate.
    candidate(tmp_path, clock.now, game_id='other')
    assert w.pending(tmp_path, clock.now, KO)[CUTOFF] == dt.datetime(1970, 1, 1, tzinfo=UTC)
    calls = []
    w.hold(tmp_path, CUTOFF, lambda: calls.append('retry'), lambda: None, clock, clock.sleep)
    assert calls == ['retry', 'retry']


def test_stale_game_is_not_masked_by_fresh_candidate_at_same_cutoff(tmp_path):
    now = CUTOFF - dt.timedelta(minutes=8)
    candidate(tmp_path, now, game_id='fresh')
    old = CUTOFF - dt.timedelta(minutes=40)
    candidate(tmp_path, old, game_id='stale')
    assert w.pending(tmp_path, now, KO)[CUTOFF] == old


def test_long_wait_collects_sources_and_preserves_wake_time():
    clock = Clock(CUTOFF - dt.timedelta(hours=3))
    wake = clock.now + dt.timedelta(minutes=65)
    checks = []
    def collect():
        checks.append(clock.now)
        clock.sleep(5)  # collection work consumes part of the wait, never extends it
    w.monitored_sleep(65 * 60, clock, clock.sleep, collect)
    assert len(checks) == 4 and clock.now == wake
    assert all(b-a <= dt.timedelta(minutes=16) for a,b in zip(checks,checks[1:]))


def test_collection_commit_failure_keeps_deadline_watch_alive(monkeypatch):
    monkeypatch.setattr(w,'run',lambda *args,**kwargs:0)
    def failed(message):raise subprocess.CalledProcessError(1,['commit_data.py'])
    monkeypatch.setattr(w,'commit',failed)
    assert w.collect_availability()==1
