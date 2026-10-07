import datetime as dt

import pandas as pd
import pytest

import nfl_model as m
import validate_data_files as v


def fixture():
    targets=pd.DataFrame([{'season':2026,'week':5,'team':t,'gameday':'2026-10-11'} for t in ('PHI','BAL')])
    snaps=pd.DataFrame([{'season':2026,'week':w,'game_id':f'{t}{w}','team':t,'gsis_id':pid,
                        'position':'T','offense_snaps':n,'defense_snaps':0}
                       for t in ('PHI','BAL') for w in range(1,5) for pid,n in (('p',60),('q',40))])
    rost=pd.DataFrame([{'season':2026,'week':4,'team':t,'gsis_id':pid,'position':'T','status':'ACT',
                       'full_name':pid} for t in ('PHI','BAL') for pid in ('p','q')])
    inj=pd.DataFrame(columns=['season','week','team','gsis_id','report_status'])
    return targets,snaps,rost,inj


def event(day='2026-10-09',code='retired',team='PHI',pid='p'):
    return pd.DataFrame([[dt.date.fromisoformat(day),team,pid,'Player',code,'fixture']],columns=m.PERSONNEL_COLUMNS)


def avail(events=None,gameday=True):
    t,s,r,i=fixture()
    return m.availability_table(t,None,s,i,r,events=events,gameday=t if gameday else None).set_index('team')


def test_retirement_before_game_and_team_isolation():
    result=avail(event())
    assert result.loc['PHI','OL_out']==pytest.approx(.6)
    assert result.loc['PHI','OL_out_cs']==pytest.approx(.6)
    assert result.loc['BAL','OL_out']==0
    assert result.loc['BAL','OL_out_cs']==0


@pytest.mark.parametrize('day,code', [('2026-10-12','traded'),('2026-10-11','retired'),
                                    ('2026-10-09','signed'),('2026-10-09','activated')])
def test_negative_events_are_identical_to_baseline(day,code):
    pd.testing.assert_frame_equal(avail(event(day,code)),avail())


def test_missing_schedule_date_is_noop():
    pd.testing.assert_frame_equal(avail(event(),gameday=False),avail())


def test_event_notes_without_injury_report():
    t,s,r,i=fixture()
    notes=m.report_notes(None,s,['PHI','BAL'],2026,5,rost=r,events=event(),gameday=t)
    assert len(notes)==1
    assert notes.iloc[0]['this_week']=='Retired Oct 9 (personnel event)'
    assert notes.iloc[0]['counted']==1
    assert notes.iloc[0]['player']=='Player'
    for day,code in [('2026-10-11','traded'),('2026-10-12','retired'),('2026-10-09','signed')]:
        assert m.report_notes(None,s,['PHI'],2026,5,rost=r,events=event(day,code),gameday=t).empty


def test_loader_missing_file(tmp_path):
    result=m.load_personnel_events(tmp_path/'missing.csv')
    assert result.empty and list(result.columns)==m.PERSONNEL_COLUMNS
    assert m.AUDIT[-1]['missing'] and m.AUDIT[-1]['rows_loaded']==0


def test_loader_normalization_duplicates_and_audit(tmp_path):
    p=tmp_path/'personnel_events.csv'
    e=pd.concat([event(team='OAK'),event(team='OAK'),event(code='signed',pid='q')])
    e.to_csv(p,index=False)
    out=m.load_personnel_events(p)
    assert len(out)==2 and out.iloc[0].team=='LV'
    assert isinstance(out.iloc[0].event_date,dt.date)
    assert m.AUDIT[-1]['duplicates_dropped']==1
    assert m.AUDIT[-1]['out_events']==m.AUDIT[-1]['inert_events']==1
    v.validate_personnel_events(p)


@pytest.mark.parametrize('column,value', [('event','teleported'),('event_date','not-a-date'),
    ('event_date','2026-02-30'),('event_date','20261009'),('team','XYZ'),('gsis_id','')])
def test_loader_and_schema_reject_bad_rows(tmp_path,column,value):
    p=tmp_path/'personnel_events.csv'
    e=event();e[column]=value;e.to_csv(p,index=False)
    with pytest.raises(ValueError,match='offending row'): m.load_personnel_events(p)
    with pytest.raises(ValueError,match='offending row'): v.validate_personnel_events(p)


def test_missing_required_column_and_optional_columns(tmp_path):
    p=tmp_path/'personnel_events.csv'
    event().drop(columns='event').to_csv(p,index=False)
    with pytest.raises(ValueError,match='missing required columns'): m.load_personnel_events(p)
    event().drop(columns=['player','note']).to_csv(p,index=False)
    assert list(m.load_personnel_events(p).columns)==m.PERSONNEL_COLUMNS
    with pytest.raises(ValueError,match='header'): v.validate_personnel_events(p)


def test_cache_invalidated_by_events_and_schedule(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'CACHE_DIR',str(tmp_path))
    t,s,r,i=fixture()
    def run(e=None,dates=t):
        return m.availability_cached(t,None,s,i,r,2027,events=e,gameday=dates)
    base,info=run();assert info['rebuilt_seasons']==[2026]
    _,info=run();assert info['cached_seasons']==[2026]
    changed,info=run(event());assert info['rebuilt_seasons']==[2026]
    assert changed.set_index('team').loc['PHI','OL_out']==pytest.approx(.6)
    late=t.assign(gameday='2026-10-08')
    changed,info=run(event(),late);assert info['rebuilt_seasons']==[2026]
    pd.testing.assert_frame_equal(base,changed)


def test_2026_events_do_not_change_historical_features():
    t,s,r,i=fixture()
    for frame in (t,s,r): frame['season']=2025
    t['gameday']='2025-10-11'
    base=m.availability_table(t,None,s,i,r)
    with_events=m.availability_table(t,None,s,i,r,events=event(),gameday=t)
    pd.testing.assert_frame_equal(base,with_events)


def test_personnel_out_overrides_questionable_and_signed_never_clears():
    t,s,r,i=fixture()
    i=pd.DataFrame([{'season':2026,'week':5,'team':'PHI','gsis_id':'p','report_status':'Questionable'}])
    e=pd.concat([event(),event('2026-10-10','signed')])
    result=m.availability_table(t,None,s,i,r,events=e,gameday=t).set_index('team')
    assert result.loc['PHI','OL_out']==pytest.approx(.6)


def test_personnel_event_excludes_projected_quarterback():
    t,s,r,i=fixture()
    qb=pd.DataFrame([{'season':2026,'week':w,'game_id':f'PHI{w}','team':'PHI','gsis_id':pid,
                      'name':name,'dropbacks':n,'net_yards':n*eff,'leader':start,'starter':start}
                     for w in range(1,5) for pid,name,n,eff,start in
                     [('starter','Starter',30,7,True),('backup','Backup',5,4,False)]])
    rr=pd.DataFrame([{'season':2026,'week':4,'team':'PHI','gsis_id':pid,'position':'QB','status':'ACT'}
                     for pid in ('starter','backup')])
    r=pd.concat([r,rr])
    base=m.availability_table(t,qb,s,i,r,gameday=t).set_index('team')
    out=m.availability_table(t,qb,s,i,r,events=event(pid='starter'),gameday=t).set_index('team')
    assert base.loc['PHI','qb_expected']=='Starter'
    assert out.loc['PHI','qb_expected']=='Backup'
    assert out.loc['PHI','qb_delta']<base.loc['PHI','qb_delta']


def test_personnel_note_resolves_optional_name_and_position_from_roster():
    t,s,r,i=fixture()
    e=event();e['player']=''
    notes=m.report_notes(None,s,['PHI'],2026,5,rost=r,events=e,gameday=t)
    assert notes.iloc[0].player=='p' and notes.iloc[0].position=='T'


def test_validator_directory_includes_personnel_schema(tmp_path):
    p=tmp_path/'personnel_events.csv'
    e=event();e['event']='invalid';e.to_csv(p,index=False)
    with pytest.raises(ValueError,match='unknown event'): v.validate_data_dir(tmp_path)


def test_loader_accepts_arrow_string_input(tmp_path,monkeypatch):
    """pandas 3 infers strict Arrow strings; dates must replace that column."""
    p=tmp_path/'personnel_events.csv'
    event().to_csv(p,index=False)
    read_csv=pd.read_csv
    def read_with_arrow_dates(*args,**kwargs):
        frame=read_csv(*args,**kwargs)
        frame['event_date']=frame.event_date.astype('string[pyarrow]')
        return frame
    monkeypatch.setattr(m.pd,'read_csv',read_with_arrow_dates)
    loaded=m.load_personnel_events(p)
    assert loaded.event_date.dtype==object
    assert loaded.iloc[0].event_date==dt.date(2026,10,9)


def test_default_path_uses_state_dir_for_colab(tmp_path, monkeypatch, capsys):
    # Colab/Drive: STATE_DIR is None and state_dir() is the output folder; the feed there is used.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, 'STATE_DIR', None)
    monkeypatch.setattr(m, 'OUTPUT_ROOT', tmp_path / 'drive_out')
    (tmp_path / 'drive_out').mkdir()
    (tmp_path / 'drive_out' / m.PERSONNEL_FILE).write_text(
        'event_date,team,gsis_id,player,event,note\n2026-10-06,PHI,00-0030561,Lane Johnson,retired,x\n')
    out = m.load_personnel_events()
    assert len(out) == 1 and m.AUDIT[-1]['path'].endswith(m.PERSONNEL_FILE) and not m.AUDIT[-1]['missing']
    assert 'WARNING' not in capsys.readouterr().out


def test_default_path_missing_warns_loudly(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, 'STATE_DIR', None)
    monkeypatch.setattr(m, 'OUTPUT_ROOT', tmp_path / 'drive_out')
    out = m.load_personnel_events()
    assert out.empty and m.AUDIT[-1]['missing']
    assert 'NOT applied' in capsys.readouterr().out


def test_availability_targets_carry_gameday():
    sched = pd.DataFrame({'season': [2026], 'week': [5], 'home_team': ['DAL'], 'away_team': ['TB'],
                          'gameday': ['2026-10-08'], 'gametime': ['20:15']})
    t = m.availability_targets(sched)
    assert t.gameday.tolist() == ['2026-10-08'] * 2 and m.personnel_gamedays(t)[(2026, 5, 'TB')].isoformat() == '2026-10-08'
