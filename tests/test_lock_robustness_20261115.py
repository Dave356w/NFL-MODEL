"""Regression cases for the week-10 missed locks (SF-DAL, PIT-CIN) and lock durability."""
import datetime as dt

import pytest

import availability_collect as c
from test_availability_collect import EVENT, NOW, PLAYERS, SCHEDULE, Sources, report


def own_table_only(team, **kwargs):
    """dallascowboys.com shape: the selected week and this club's table only."""
    text = report(team, **kwargs)
    start = text.index('<div class="nfl-o-injury-report__container">')
    tables = text[start:].split('<div class="nfl-o-injury-report__container">')[1:]
    keep = next(t for t in tables if c.TEAMS[team][0] in t)
    return text[:start] + '<div class="nfl-o-injury-report__container">' + keep


# --- Club page publishes only its own table ---------------------------------

def test_club_page_with_only_its_own_table_is_complete():
    parsed = c.parse_injury_report(own_table_only('BAL'), 'BAL', EVENT, c.PlayerIndex(PLAYERS))
    assert parsed['complete'] and {r['gsis_id'] for r in parsed['rows']} >= {'00-0000001', '00-0000003'}


def test_club_page_without_its_own_table_is_rejected():
    with pytest.raises(ValueError, match='this club'):
        c.parse_injury_report(own_table_only('JAX'), 'BAL', EVENT, c.PlayerIndex(PLAYERS))


def test_club_page_with_a_foreign_club_is_still_rejected():
    # BAL's page shows BAL and JAX, but the scheduled opponent is BUF: stale page.
    with pytest.raises(ValueError, match='opponent'):
        c.parse_injury_report(report('BAL'), 'BAL', dict(EVENT, away='BUF'), c.PlayerIndex(PLAYERS))


# --- Blank final-day cell next to a published designation --------------------

def blank_final(team, status):
    """One player added after the final practice: blank last practice cell."""
    return report(team).replace('<td>LP</td><td>LP</td><td>FP</td><td>OUT</td>',
                                f'<td>LP</td><td>LP</td><td></td><td>{status}</td>', 1)


@pytest.mark.parametrize('status', ['QUESTIONABLE', 'OUT', 'DOUBTFUL'])
def test_late_addition_with_designation_keeps_report_complete(status):
    text = blank_final('BAL', status)
    assert '<td></td><td>' + status in text
    assert c.parse_injury_report(text, 'BAL', EVENT, c.PlayerIndex(PLAYERS))['complete']


def test_blank_final_day_without_designation_is_still_unpublished():
    text = report('BAL').replace('<td>FP</td><td>(-)</td>', '<td></td><td></td>', 1)
    assert not c.parse_injury_report(text, 'BAL', EVENT, c.PlayerIndex(PLAYERS))['complete']


def test_designations_with_no_final_day_entries_are_not_complete():
    """Designations alone cannot prove the final-day column is out."""
    text = report('BAL', last='')
    assert not c.parse_injury_report(text, 'BAL', EVENT, c.PlayerIndex(PLAYERS))['complete']


# --- Failed pages are kept for diagnosis --------------------------------------

def test_failed_report_page_is_saved_once_inside_lock_window(tmp_path):
    class Broken(Sources):
        def __call__(self, url):
            r = super().__call__(url)
            if url.endswith('/team/injury-report/') and 'baltimoreravens' in url:
                r = dict(r, text='<p>maintenance</p>', body_sha256=c.digest('<p>maintenance</p>'))
            return r
    source = Broken()
    state = c.refresh(tmp_path, SCHEDULE, PLAYERS, now=source.now, fetcher=source, force=True)
    saved = state['teams']['BAL']['report']['failure_capture']
    assert saved and (tmp_path/saved).read_text().endswith('<p>maintenance</p>')
    assert 'does not identify the forecast week' in (tmp_path/saved).read_text().splitlines()[0]
    source.now += dt.timedelta(minutes=1)
    c.refresh(tmp_path, SCHEDULE, PLAYERS, now=source.now, fetcher=source, force=True)
    assert len(list((tmp_path/c.FAILURES).iterdir())) == 1
    assert c.validate_store(tmp_path)


def test_failed_report_page_is_not_saved_days_before_kickoff(tmp_path):
    class Broken(Sources):
        def __call__(self, url):
            r = super().__call__(url)
            if url.endswith('/team/injury-report/'):
                r = dict(r, text='<p>old week</p>')
            return r
    source = Broken();source.now = NOW - dt.timedelta(days=2)
    state = c.refresh(tmp_path, SCHEDULE, PLAYERS, now=source.now, fetcher=source, force=True)
    assert state['teams']['BAL']['report'].get('failure_capture') is None
    assert not (tmp_path/c.FAILURES).exists()


# --- Lock continuity across revisions (owner decision 2026-11-15) --------------

import copy
import json
from pathlib import Path

import ats_locks as a
import lock_watchdog as monitor

T0 = dt.datetime(2026, 11, 15, 17, tzinfo=dt.timezone.utc)


def lock(rev, game='g', minutes=0, **extra):
    return dict(revision=rev, game_id=game, lock_at_utc=T0.isoformat(),
                finalized_utc=(T0 + dt.timedelta(minutes=minutes)).isoformat(), **extra)


def test_current_records_keeps_one_saved_lock_per_game_from_any_revision():
    old, retro = lock('v1', minutes=0), lock('v2', minutes=-30, retro_locked=True)
    legacy = lock('v0', game='legacy', legacy_lock=True)
    records = {a.key(r): r for r in (old, retro, legacy)}
    before = copy.deepcopy(records)
    out = a.current_records(records, 'v3')
    assert out == {('v3', 'g'): old}            # native beats an earlier retro lock
    assert records == before                     # journals are never rewritten
    later = lock('v2', minutes=5)
    records[a.key(later)] = later
    assert a.current_records(records, 'v3')[('v3', 'g')] is old   # earliest native wins
    own_tie = lock('v3')
    records[a.key(own_tie)] = own_tie
    assert a.current_records(records, 'v3')[('v3', 'g')] is own_tie  # exact tie -> current revision
    assert ('v3', 'legacy') not in a.current_records(records, 'v3')


def test_real_thursday_lock_survives_the_v124_revision_change():
    root = Path(__file__).resolve().parents[1]
    records = a.display_records(root/'data')
    saved = a.current_records(records, 'boxscore-composite-v1.24')
    thursday = saved[('boxscore-composite-v1.24', '2026_10_WAS_NYG')]
    assert (thursday['revision'], thursday['selected_side']) == ('boxscore-composite-v1.22', 'home')
    assert sum(r['revision'] == 'boxscore-composite-v1.18' for r in saved.values()) >= 28


# --- Coverage monitor -----------------------------------------------------------

def monitored(tmp_path, revision='r'):
    latest = tmp_path/'latest';latest.mkdir()
    (latest/'manifest.json').write_text(json.dumps(dict(revision=revision)))
    (latest/'board.csv').write_text('game_id,gameday,gametime,result\ng,2026-11-15,13:00,\n')
    return T0  # 13:00 ET kickoff -> 17:00 UTC cutoff


def blocked_observation(tmp_path, observed, revision='r'):
    store = tmp_path/'lock_runtime/2026_week10'
    folder = store/'timing_forecasts/g';folder.mkdir(parents=True, exist_ok=True)
    evidence = dict(team='DAL', collection=dict(report=dict(error='injury report for this club not yet published'),
                                                 inactives=dict(complete=True)))
    board = dict(home='DAL', away='SF', quote_ready=True, home_availability_evidence=json.dumps(evidence),
                 away_availability_evidence=json.dumps(dict(team='SF', collection=dict(report=dict(complete=True),
                                                                                        inactives=dict(complete=True)))))
    row = dict(revision=revision, game_id='g', observed_utc=observed.isoformat(), board=board)
    (folder/f'{observed:%H%M%S}.json').write_text(json.dumps(row))
    return store


def test_monitor_counts_an_earlier_revision_lock_as_covered(tmp_path):
    cutoff = monitored(tmp_path)
    a.append(tmp_path/a.LOCKS, [lock('older')])
    assert not monitor.coverage_issues(tmp_path, cutoff + dt.timedelta(minutes=10))


def test_monitor_warns_at_risk_names_blockers_and_keeps_missed_games_visible(tmp_path, monkeypatch):
    cutoff = monitored(tmp_path)
    store = blocked_observation(tmp_path, cutoff - dt.timedelta(minutes=25))
    monkeypatch.setattr(a, 'runtime_stores', lambda data: [store])
    risk = monitor.coverage_issues(tmp_path, cutoff - dt.timedelta(minutes=20))
    assert len(risk) == 1 and 'AT RISK' in risk[0] and 'DAL report: injury report for this club' in risk[0]
    assert not monitor.coverage_issues(tmp_path, cutoff - dt.timedelta(minutes=31))
    missed = monitor.coverage_issues(tmp_path, cutoff + dt.timedelta(hours=20))
    assert 'MISSED CUTOFF' in missed[0] and 'DAL report' in missed[0]
    assert not monitor.coverage_issues(tmp_path, cutoff + dt.timedelta(hours=26))


def test_monitor_is_quiet_before_risk_window_without_observations(tmp_path):
    cutoff = monitored(tmp_path)
    assert not monitor.coverage_issues(tmp_path, cutoff - dt.timedelta(minutes=20))
    assert 'no saved forecast observation' in monitor.coverage_issues(tmp_path, cutoff - dt.timedelta(minutes=4))[0]


# --- Owner-requested repair of the two remaining lost week-10 picks ---------------

import retro_lock as r


def test_sf_dal_and_pit_cin_repairs_use_last_pre_cutoff_observation(tmp_path):
    requests = [q for q in json.loads(r.REQUESTS.read_text())
                if q['game_id'] in ('2026_10_SF_DAL', '2026_10_PIT_CIN')]
    assert len(requests) == 2
    now = dt.datetime(2026, 11, 16, 6, tzinfo=dt.timezone.utc)
    assert r.apply(tmp_path, requests, now) == 2
    rows = {row['game_id']: row for row in a.read(tmp_path/a.LOCKS)}
    expected = {'2026_10_SF_DAL': ('away', -5., -4.5), '2026_10_PIT_CIN': ('home', 5., 3.5)}
    for game, row in rows.items():
        assert (row['selected_side'], row['fixed_band_spread'], row['market_spread']) == expected[game]
        assert a.utc(row['source_snapshot']['committed_utc']) + dt.timedelta(seconds=1) <= a.utc(row['lock_at_utc'])
        assert row['retro_locked'] and row['finalized_utc'] == now.isoformat()
        r.validate(row)
    assert r.apply(tmp_path, requests, now) == 0   # idempotent


def test_monitor_reports_evidence_blockers_even_when_collection_is_complete():
    complete = dict(report=dict(complete=True), inactives=dict(complete=True))
    board = dict(home='BAL', away='JAX', quote_ready=True,
                 home_availability_evidence=json.dumps(dict(team='BAL', collection=complete,
                                                            blockers=['starting quarterback unresolved'])),
                 away_availability_evidence=json.dumps(dict(team='JAX', collection=complete, blockers=[])))
    assert monitor.observation_blockers(board) == ['BAL: starting quarterback unresolved']
