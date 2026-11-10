import datetime as dt
import json
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

import ats_locks as a
import lock_refresh as refresh
import lock_watcher as watcher
import nfl_model as m
from test_ats_locks import TimedATS, CUTOFF, KO


@pytest.fixture
def legacy_board():
    fixture = TimedATS()
    fixture.setUp()
    yield fixture
    fixture.doCleanups()


def offer(fixture, stamp, home_price=-118):
    import espn_spreads as e
    side = lambda h, p: dict(pointSpread={'american': str(h)}, spread={'american': str(p)},
                            moneyLine={'american': '-180' if h < 0 else '+155'})
    row = dict(game_id=fixture.raw['game_id'], season=2026, week=7, home='IND', away='TEN',
        event_id='fixture', completed=False, captured_utc=stamp.isoformat(), kickoff_utc=KO.isoformat(),
        odds_url='https://example.test/odds', movements=[], odds_pages=[{'items': [dict(
            provider={'id': '100', 'name': 'Draft Kings'}, homeTeamOdds={'current': side(-7, home_price)},
            awayTeamOdds={'current': side(7, -102)})]}])
    row['evidence_sha256'] = a.digest(row)
    a.append(fixture.data/e.STORE, [row])
    return row


def candidate(fixture, minutes=2):
    stamp = CUTOFF-dt.timedelta(minutes=minutes)
    offer(fixture, stamp)
    fixture.board(stamp)
    a.record(fixture.data, stamp, policy_version=a.WATCHER_POLICY, finalize=False)
    return a.read(fixture.data/a.CANDIDATES)[-1]


def receipt(fixture, row, when):
    a.append(fixture.data/a.RECEIPTS, [dict(candidate_sha256=row['candidate_sha256'],
        commit='a'*40, committed_utc=when.isoformat())])


def test_undurable_or_late_commit_never_locks(legacy_board):
    row = candidate(legacy_board)
    a.record(legacy_board.data, CUTOFF, policy_version=a.WATCHER_POLICY)
    assert legacy_board.locks() == []
    receipt(legacy_board, row, CUTOFF+dt.timedelta(seconds=1))
    a.record(legacy_board.data, CUTOFF+dt.timedelta(minutes=2), policy_version=a.WATCHER_POLICY)
    assert legacy_board.locks() == []


def test_restart_finalizes_saved_inputs_and_price_without_refresh(legacy_board):
    row = candidate(legacy_board)
    receipt(legacy_board, row, CUTOFF-dt.timedelta(minutes=1))
    # The rolling board subsequently flips; post-cutoff inputs cannot be selected.
    legacy_board.board(CUTOFF+dt.timedelta(minutes=2), model_wp=.2, spread_line=6.5)
    a.record(legacy_board.data, CUTOFF+dt.timedelta(minutes=3), policy_version=a.WATCHER_POLICY)
    saved, = legacy_board.locks()
    assert saved['candidate_sha256'] == row['candidate_sha256']
    assert saved['espn_quote'] == row['espn_quote']
    before = (legacy_board.data/a.LOCKS).read_bytes()
    a.record(legacy_board.data, CUTOFF+dt.timedelta(minutes=10), policy_version=a.WATCHER_POLICY)
    assert (legacy_board.data/a.LOCKS).read_bytes() == before
    a.validate_store(legacy_board.data)


def test_newer_unacknowledged_candidate_cannot_replace_durable_one(legacy_board):
    row = candidate(legacy_board, 3)
    receipt(legacy_board, row, CUTOFF-dt.timedelta(minutes=2))
    candidate(legacy_board, 1)
    a.record(legacy_board.data, CUTOFF, policy_version=a.WATCHER_POLICY)
    assert legacy_board.locks()[0]['candidate_sha256'] == row['candidate_sha256']


def test_stale_forecast_or_quote_is_blocked(legacy_board):
    stamp = CUTOFF-dt.timedelta(minutes=15)
    offer(legacy_board, stamp)
    legacy_board.board(stamp)
    a.record(legacy_board.data, stamp, policy_version=a.WATCHER_POLICY)
    assert not a.read(legacy_board.data/a.CANDIDATES)
    legacy_board.board(CUTOFF-dt.timedelta(minutes=1))
    a.record(legacy_board.data, CUTOFF, policy_version=a.WATCHER_POLICY)
    assert not a.read(legacy_board.data/a.CANDIDATES)


def test_quote_offset_and_handicap_come_from_same_fresh_capture(legacy_board):
    row = offer(legacy_board, CUTOFF-dt.timedelta(minutes=2))
    q = refresh.current_quotes([row], CUTOFF)[row['game_id']]
    assert (q['home_moneyline'], q['away_moneyline'], q['quote']['home_handicap']) == (-180, 155, -7)
    assert not refresh.current_quotes([row], CUTOFF+dt.timedelta(minutes=5))
    assert not refresh.current_quotes([row], CUTOFF-dt.timedelta(minutes=3))


def test_checkpoint_never_uses_later_forecast_or_changes_official_journal(tmp_path):
    rows = [dict(revision='r', game_id='g', kickoff_utc=KO.isoformat(),
        observed_utc=(CUTOFF+dt.timedelta(seconds=s)).isoformat(), snapshot_sha256=str(s)) for s in (-120, 30)]
    for i, row in enumerate(rows):
        path = tmp_path/watcher.FORECASTS/'g'/f'{i}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(row))
    watcher.checkpoints(tmp_path, CUTOFF+dt.timedelta(minutes=1))
    records = a.read(tmp_path/watcher.CHECKPOINTS)
    at60, = [r for r in records if r['lead_minutes']==60]
    assert at60['forecast_sha256']=='-120' and at60['fresh']
    at90, = [r for r in records if r['lead_minutes']==90]
    assert at90['forecast_sha256'] is None
    watcher.checkpoints(tmp_path, CUTOFF+dt.timedelta(minutes=2))
    assert records == a.read(tmp_path/watcher.CHECKPOINTS)
    assert not (tmp_path/a.LOCKS).exists()


def test_handoff_requires_acknowledged_successor(monkeypatch):
    monkeypatch.setenv('GITHUB_RUN_ID', '1')
    monkeypatch.setattr(watcher.subprocess, 'run', Mock())
    monkeypatch.setattr(watcher.time, 'sleep', lambda _: None)
    monkeypatch.setattr(watcher.subprocess, 'check_output', lambda *a, **k: b'[]')
    with pytest.raises(RuntimeError, match='No acknowledged successor'):
        watcher.handoff()


def test_successful_handoff_returns_the_successor_id(monkeypatch):
    monkeypatch.setenv('GITHUB_RUN_ID', '1')
    monkeypatch.setattr(watcher.subprocess, 'run', Mock())
    monkeypatch.setattr(watcher.subprocess, 'check_output', lambda *a, **k: json.dumps([
        dict(databaseId=2, event='workflow_dispatch', createdAt='2099-01-01T00:00:00Z', status='queued')]).encode())
    assert watcher.handoff() == 2


def test_failed_publication_retries_until_deployment_succeeds(tmp_path, monkeypatch):
    pending = tmp_path/'publish_pending.json'
    pending.write_text(json.dumps(dict(pending=True, run_id=1)))
    monkeypatch.setattr(watcher.subprocess, 'check_output', lambda *a, **k:
                        json.dumps(dict(status='completed', conclusion='failure')).encode())
    calls = []
    monkeypatch.setattr(watcher, 'dispatch', lambda workflow: calls.append(workflow) or 2)
    watcher.publish(pending)
    assert json.loads(pending.read_text()) == dict(pending=True, run_id=2)
    assert calls == ['publish.yml']
    monkeypatch.setattr(watcher.subprocess, 'check_output', lambda *a, **k:
                        json.dumps(dict(status='completed', conclusion='success')).encode())
    watcher.publish(pending)
    assert json.loads(pending.read_text()) == dict(pending=False)


def test_recovery_receipt_uses_committed_blob_not_unsent_local_forecast(tmp_path, monkeypatch):
    runtime = tmp_path/'lock_runtime'
    committed = dict(candidate_sha256='saved', observed_utc=(CUTOFF-dt.timedelta(minutes=2)).isoformat())
    unsent = dict(candidate_sha256='local', observed_utc=(CUTOFF-dt.timedelta(minutes=1)).isoformat())
    a.append(runtime/a.CANDIDATES, [committed, unsent])
    def git(*args):
        if args[0]=='log':
            return ('a'*40).encode()
        if '--format=%cI' in args:
            return (CUTOFF-dt.timedelta(minutes=1)).isoformat().encode()
        return (json.dumps(committed)+'\n').encode()
    monkeypatch.setattr(watcher, 'git', git)
    watcher.recover_receipts(tmp_path)
    rows = a.read(runtime/a.RECEIPTS)
    assert [r['candidate_sha256'] for r in rows] == ['saved']


def test_finalization_survives_source_failure_and_publication_remains_retryable(legacy_board, monkeypatch):
    row = candidate(legacy_board)
    receipt(legacy_board, row, CUTOFF-dt.timedelta(minutes=1))
    runtime = legacy_board.data/'lock_runtime'
    runtime.mkdir()
    for path in list(legacy_board.data.iterdir()):
        if path != runtime:
            path.replace(runtime/path.name)
    calls = []
    monkeypatch.setattr(watcher, 'persist', lambda data, message: calls.append(message) or 'a'*40)
    monkeypatch.setattr(watcher, 'refresh_prepared', lambda data: None)
    def unavailable(*args):
        raise OSError('provider outage')
    monkeypatch.setattr(refresh, 'score', unavailable)
    monkeypatch.setattr(watcher, 'publish', unavailable)
    health = watcher.tick(legacy_board.data, CUTOFF)
    assert a.read(runtime/a.LOCKS)[0]['candidate_sha256']==row['candidate_sha256']
    assert json.loads((runtime/'publish_pending.json').read_text())['pending']
    assert 'finalization' in calls[0] and health['errors']==['provider outage']


def test_runtime_locks_are_authoritative_in_page_and_download(legacy_board):
    import build_site as b
    runtime = legacy_board.data/'lock_runtime'
    runtime.mkdir()
    row = candidate(legacy_board)
    receipt(legacy_board, row, CUTOFF-dt.timedelta(minutes=1))
    a.record(legacy_board.data, CUTOFF, policy_version=a.WATCHER_POLICY)
    for name in (a.LOCKS, a.CANDIDATES, a.RECEIPTS):
        (legacy_board.data/name).replace(runtime/name)
    displayed = a.display_records(legacy_board.data)
    assert displayed[a.key(row)]['candidate_sha256'] == row['candidate_sha256']
    latest = dict(manifest=dict(revision=m.REVISION), ats_locks=displayed)
    changed = dict(legacy_board.raw, model_wp=.2, fixed_band_spread=-14, spread_line=6.5)
    state = b.ats_card_state(latest, changed, CUTOFF+dt.timedelta(minutes=2))
    assert state['status']=='locked' and state['spread_line']==row['market_spread']


def test_prepare_load_hashes_and_preserves_full_precision(tmp_path):
    from scipy.special import ndtr
    fit = dict(names=['site'], beta=[.12345678912345], scale=[1], fit_season=2026, fit_week=10,
               training_max_season=2026, training_max_week_in_latest_season=9, recipe=m.PRODUCT_RECIPE)
    board = pd.DataFrame([dict(season=2026, week=10, site=1., model_wp=.543210987654321)])
    history = pd.DataFrame([dict(season=year, week=1, model_wp=float(ndtr(x/12.37)), result=x)
                           for year in (2024, 2025) for x in (1., 4., 8., 12.) for _ in range(50)])
    refresh.prepare(tmp_path, fit, board, pd.DataFrame(), None, {}, pd.DataFrame(),
                    pd.DataFrame(), None, history)
    manifest, frames = refresh.load(tmp_path)
    assert frames['board'].model_wp.iloc[0] == board.model_wp.iloc[0]
    assert manifest['fit']==fit
    (tmp_path/refresh.INPUTS/'board.parquet').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='hash mismatch'):
        refresh.load(tmp_path)


def test_fast_score_reuses_fit_but_updates_quote_and_availability(tmp_path, monkeypatch, legacy_board):
    import espn_spreads as e
    now = KO-dt.timedelta(minutes=90)
    evidence = offer(legacy_board, now)
    board = dict(legacy_board.raw, season=2026, week=7, site=1., ready=True,
                 home_moneyline=-110., away_moneyline=-110.,
                 **{c: 0. for c in m.PRODUCT_CONTEXT_NAMES})
    fit = dict(names=['site', 'd__avail__qb_delta'], beta=[.1, 1.], scale=[1., 1.],
        fit_season=2026, fit_week=7, training_max_season=2026,
        training_max_week_in_latest_season=6, market_offset=True,
        recipe=dict(architecture='market_product_1sd'))
    manifest = dict(season=2026, week=7, sha256='bundle', fit=fit, rule=legacy_board.rule)
    frames = dict(board=pd.DataFrame([board]), schedules=pd.DataFrame([dict(game_id=board['game_id'])]),
                  targets=pd.DataFrame([dict(game_id=board['game_id'])]), availability=pd.DataFrame(),
                  snaps=pd.DataFrame(), inj=pd.DataFrame(), rost=pd.DataFrame())
    resolved=[]
    for team, delta in [('IND', .2), ('TEN', .05)]:
        row=dict(game_id=board['game_id'], team=team, **{c: 0. for c in m.ALL_AVAIL_COLS})
        row['qb_delta']=delta
        row.update(qb_expected='fixture', qb_usual='fixture', injury_report='final',
                   availability_evidence='{}', availability_evidence_sha256='fixture')
        resolved.append(row)
    monkeypatch.setattr(refresh, 'load', lambda data: (manifest, frames))
    monkeypatch.setattr(refresh.ac, 'refresh', lambda *args, **kwargs: {})
    monkeypatch.setattr(e, 'refresh', lambda *args, **kwargs: None)
    monkeypatch.setattr(e, 'read', lambda *args: [evidence])
    monkeypatch.setattr(m, 'resolve_game_availability', lambda *args, **kwargs: pd.DataFrame(resolved))
    _, scored = refresh.score(tmp_path, now=now, clock=lambda: now)
    expected=scored.copy()
    assert scored.home_moneyline.iloc[0]==-180 and scored.away_moneyline.iloc[0]==155
    assert scored.spread_line.iloc[0]==7 and scored.d__avail__qb_delta.iloc[0]==pytest.approx(.15)
    assert scored.model_wp.iloc[0]==pytest.approx(m.apply_fit(expected, fit)[0])
    assert json.loads(scored.score_quote.iloc[0])['provider_id']=='100'
