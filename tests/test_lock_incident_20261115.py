"""Regression cases for the five Nov 15 parser-blocked locks and their recovery."""
import copy
import datetime as dt
import json
from pathlib import Path

import pytest

import ats_locks as a
import availability_collect as c
import lock_watchdog as monitor
import retro_lock as r
from test_availability_collect import EVENT, NOW, PLAYERS, inactive_html


@pytest.mark.parametrize('prefix',['G/T','C/G','OL/DL','G / T'])
def test_compound_inactive_positions_resolve_exact_player(prefix):
    info=c.article(inactive_html(body='RAVENS\n'+prefix+' Dan Gamma\nJAGUARS\nWR Fred Epsilon'))
    result=c.parse_inactives(info,'BAL',EVENT,c.PlayerIndex(PLAYERS))
    assert result['complete'] and [p['gsis_id'] for p in result['rows']]==['00-0000003']


@pytest.mark.parametrize('prefix',['G/BOGUS','C/UNKNOWN'])
def test_unknown_compound_position_does_not_complete_list(prefix):
    info=c.article(inactive_html(body='RAVENS\n'+prefix+' Dan Gamma\nJAGUARS\nWR Fred Epsilon'))
    with pytest.raises(ValueError):c.parse_inactives(info,'BAL',EVENT,c.PlayerIndex(PLAYERS))


@pytest.mark.parametrize('pid,canonical,alias',[
    ('00-0036378','Michael Danna','Mike Danna'),
    ('00-0040886','Nicholas Singleton','Nick Singleton'),
    ('00-0040173','Tyrion Ingram-Dawkins','Tyroin Ingram-Dawkins')])
def test_name_aliases_are_bound_to_exact_roster_identity(pid,canonical,alias):
    row=dict(gsis_id=pid,full_name=canonical,team='BUF',position='DL')
    index=c.PlayerIndex([row])
    assert index.resolve(alias,'BUF')['gsis_id']==pid
    assert c.PlayerIndex([dict(row,full_name='Different Player')]).resolve(alias,'BUF') is None
    assert c.PlayerIndex([dict(row,gsis_id='00-9999999')]).resolve(alias,'BUF') is None
    assert index.resolve('Madeup '+canonical.split()[-1],'BUF') is None


@pytest.fixture
def recoveries():
    return [q for q in json.loads(r.REQUESTS.read_text()) if q['game_id'].startswith('2026_10_')]


def test_five_recoveries_preserve_exact_predeadline_snapshot_and_qb_overlay(tmp_path,recoveries):
    assert len(recoveries)==5
    now=dt.datetime(2026,11,15,20,tzinfo=dt.timezone.utc)
    expected={'BUF_NYJ':('away',-13.),'HOU_CLE':('away',-5.),'JAX_TEN':('away',-13.),
              'MIA_IND':('home',7.),'MIN_GB':('home',5.)}
    assert r.apply(tmp_path,recoveries,now)==5
    rows=a.read(tmp_path/a.LOCKS)
    for row in rows:
        assert (row['selected_side'],row['fixed_band_spread'])==expected[row['game_id'][8:]]
        assert row['observed_utc']==row['finalized_utc']==now.isoformat()
        assert a.utc(row['source_snapshot']['committed_utc'])<a.utc(row['lock_at_utc'])
        assert row['espn_quote']==json.loads(row['source_snapshot']['board_row']['score_quote'])
        assert not row.get('recovered_after_kickoff')  # retro recovery has its own explicit basis
        r.validate(row)
    before=(tmp_path/a.LOCKS).read_bytes()
    assert r.apply(tmp_path,recoveries,now)==0
    assert (tmp_path/a.LOCKS).read_bytes()==before
    assert not (tmp_path/a.CANDIDATES).exists()


def test_timing_recovery_rejects_changed_overlay_and_late_save(recoveries):
    source=r.source_snapshot(recoveries[0])
    changed=copy.deepcopy(source)
    changed['committed_utc']='2026-11-15T17:00:00Z'
    with pytest.raises(ValueError):r.decision(changed)
    changed=copy.deepcopy(source)
    changed['board_row']['qb_replacement_margin_adjustment']=99
    with pytest.raises(ValueError):r.decision(changed)


def test_existing_native_runtime_lock_wins_over_recovery(tmp_path,monkeypatch,recoveries):
    request=recoveries[0];source=r.source_snapshot(request)
    row=r.decision(source)
    # apply must consult all stores, not only the full builder's journal.
    store=tmp_path/'lock_runtime/2026_week10';store.mkdir(parents=True)
    a.append(store/a.LOCKS,[row])
    monkeypatch.setattr(a,'validate_store',lambda *_:None)
    assert r.apply(tmp_path,[request],dt.datetime(2026,11,15,20,tzinfo=dt.timezone.utc))==0
    assert not (tmp_path/a.LOCKS).exists()


def test_coverage_monitor_requires_durable_candidates_and_reports_late_finalization(tmp_path):
    latest=tmp_path/'latest';latest.mkdir()
    (latest/'manifest.json').write_text(json.dumps(dict(revision='r')))
    (latest/'board.csv').write_text('game_id,gameday,gametime,result\ng,2026-11-15,13:00,\n')
    cutoff=dt.datetime(2026,11,15,17,tzinfo=dt.timezone.utc)
    assert not monitor.coverage_issues(tmp_path,cutoff-dt.timedelta(minutes=6))
    assert 'five minutes' in monitor.coverage_issues(tmp_path,cutoff-dt.timedelta(minutes=4))[0]
    row=dict(revision='r',game_id='g',policy_version=a.WATCHER_POLICY,candidate_sha256='h',
             observed_utc=(cutoff-dt.timedelta(minutes=2)).isoformat(),lock_at_utc=cutoff.isoformat())
    a.append(tmp_path/a.CANDIDATES,[row])
    assert 'MISSED' in monitor.coverage_issues(tmp_path,cutoff)[0]  # unsaved receipt is insufficient
    a.append(tmp_path/a.RECEIPTS,[dict(candidate_sha256='h',commit='a'*40,
             committed_utc=(cutoff-dt.timedelta(minutes=1)).isoformat())])
    assert not monitor.coverage_issues(tmp_path,cutoff)
    assert 'not finalized' in monitor.coverage_issues(tmp_path,cutoff+dt.timedelta(minutes=4))[0]
    a.append(tmp_path/a.LOCKS,[dict(revision='r',game_id='g')])
    assert not monitor.coverage_issues(tmp_path,cutoff+dt.timedelta(minutes=4))


def test_controller_upgrade_waits_for_old_writer_before_dispatch(monkeypatch):
    calls=[]
    def output(cmd,**kwargs):
        calls.append(cmd)
        if cmd[0]=='git':return 'availability_collect.py\n'
        if cmd[1:3]==['run','view']:return json.dumps(dict(status='completed')).encode()
        if cmd[1:3]==['run','list']:return b'[]'
        raise AssertionError(cmd)
    monkeypatch.setattr(monitor.subprocess,'check_output',output)
    monkeypatch.setattr(monitor.subprocess,'run',lambda cmd,**kwargs:calls.append(cmd))
    assert monitor.restart_outdated([dict(databaseId=1,status='in_progress',headSha='old')])
    cancel=next(i for i,x in enumerate(calls) if x[:3]==['gh','run','cancel'])
    stopped=next(i for i,x in enumerate(calls) if x[:3]==['gh','run','view'])
    dispatch=next(i for i,x in enumerate(calls) if x[:3]==['gh','workflow','run'])
    assert cancel<stopped<dispatch


def test_data_only_updates_do_not_restart_watcher(monkeypatch):
    monkeypatch.setattr(monitor.subprocess,'check_output',lambda *args,**kwargs:'')
    monkeypatch.setattr(monitor.subprocess,'run',lambda *_args,**_kwargs:pytest.fail('unexpected restart'))
    assert not monitor.restart_outdated([dict(databaseId=1,status='in_progress',headSha='old')])


def test_missed_status_preserves_original_parser_error_after_rolling_board_loses_evidence(tmp_path,recoveries):
    import csv
    source=r.source_snapshot(recoveries[0]);snapshot=source['timing_snapshot']
    latest=tmp_path/'latest';latest.mkdir()
    manifest=dict(source['manifest'],generated_utc='2026-11-15T18:06:39+00:00')
    (latest/'manifest.json').write_text(json.dumps(manifest))
    raw=dict(source['board_row'])
    for field in list(raw):
        if 'availability' in field:raw.pop(field)
    with (latest/'board.csv').open('w') as out:
        writer=csv.DictWriter(out,fieldnames=list(raw));writer.writeheader();writer.writerow(raw)
    path=tmp_path/'lock_runtime/2026_week10/timing_forecasts'/snapshot['game_id']/(snapshot['snapshot_sha256']+'.json')
    path.parent.mkdir(parents=True);path.write_text(json.dumps(snapshot))
    a.write_capture_status(tmp_path,dt.datetime(2026,11,15,18,10,tzinfo=dt.timezone.utc))
    status=json.loads((tmp_path/'ats_capture_status.json').read_text())['games'][0]
    assert status['state']=='missed cutoff'
    assert status['diagnostic_snapshot_sha256']==snapshot['snapshot_sha256']
    assert any('Mike Danna' in issue for issue in status['issues'])
    assert not any('evidence missing' in issue for issue in status['issues'])


def test_running_watcher_adopts_concurrent_recoveries_without_resetting_runtime(tmp_path,monkeypatch):
    import lock_watcher as watcher
    root=tmp_path/'data';(root/'latest').mkdir(parents=True)
    runtime=root/'lock_runtime';runtime.mkdir()
    (runtime/a.CANDIDATES).write_text('local-unsent-evidence\n')
    (root/a.LOCKS).write_bytes(b'old\n')
    saved={str(root/a.LOCKS):b'old\nrecovered\n',str(root/'latest/manifest.json'):b'{"revision":"new"}',
           str(root/'latest/board.csv'):b'new schedule\n'}
    def git(*args):
        if args[0]=='rev-parse':return b'new-blob\n'
        if args[0]=='hash-object':return b'old-blob\n'
        if args[0]=='show':return saved[args[1].split(':',1)[1]]
        raise AssertionError(args)
    monkeypatch.setattr(watcher,'git',git)
    watcher.refresh_reporting_inputs(root,'main-sha')
    assert (root/a.LOCKS).read_bytes()==b'old\nrecovered\n'
    assert (runtime/a.CANDIDATES).read_text()=='local-unsent-evidence\n'
    saved[str(root/a.LOCKS)]=b'rewritten\n'
    with pytest.raises(ValueError,match='rewritten'):watcher.refresh_reporting_inputs(root,'main-sha')
