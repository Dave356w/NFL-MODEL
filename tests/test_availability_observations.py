"""Availability corrections must change the right lineup without contaminating history or locks."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

import nfl_model as m
from set_availability import append_observation

UTC=dt.timezone.utc
NOW=dt.datetime(2026,11,4,20,tzinfo=UTC)
KO='2026-11-06T01:15:00+00:00'
GAME='2026_09_JAX_BAL'
STARTER='00-0000001'
BACKUP='00-0000002'
ARRIVAL='00-0000003'


def fact(field='qb_starter',pid=BACKUP,value=True,**changes):
    row=dict(game_id=GAME,team='BAL',gsis_id=pid,player='Backup',position='QB',field=field,value=value,
             source_url='https://www.baltimoreravens.com/news/fixture',published_utc='2026-11-04T19:00:00Z',
             observed_utc='2026-11-04T19:30:00Z',effective_utc='2026-11-04T19:00:00Z',reason='Fixture announcement')
    if field in ('report_complete','inactives_complete'):
        for name in ('gsis_id','player','position'): row.pop(name)
    return dict(row,**changes)


def inputs(status='final'):
    target=pd.DataFrame([dict(game_id=GAME,season=2026,week=9,team=t,gameday='2026-11-05',kickoff=KO,result=np.nan)
                         for t in ('BAL','JAX')])
    qb=pd.DataFrame([dict(season=2026,week=w,game_id=f'{t}{w}',team=t,gsis_id=p,name=name,
                         dropbacks=n,net_yards=n*eff,leader=start,starter=start)
                     for t in ('BAL','JAX') for w in range(5,9)
                     for p,name,n,eff,start in [(STARTER,'Starter',30,8,True),(BACKUP,'Backup',5,4,False)]])
    arrival=qb.loc[qb.team.eq('JAX')&qb.gsis_id.eq(BACKUP)].assign(gsis_id=ARRIVAL,name='Arrival')
    qb=pd.concat([qb,arrival],ignore_index=True)
    rost=pd.DataFrame([dict(season=2026,week=8,team=t,gsis_id=p,position='QB',status='ACT',full_name=name)
                       for t in ('BAL','JAX') for p,name in [(STARTER,'Starter'),(BACKUP,'Backup')]])
    rost=pd.concat([rost,pd.DataFrame([dict(season=2026,week=8,team='ARI',gsis_id=ARRIVAL,
                                         position='QB',status='ACT',full_name='Arrival')])],ignore_index=True)
    snaps=pd.DataFrame(columns=['season','week','game_id','team','gsis_id','position','offense_snaps','defense_snaps'])
    inj=pd.DataFrame([dict(season=2026,week=9,team=t,gsis_id='00-0000009',
                          report_status='Questionable' if status=='final' else None,date_modified='2026-11-04T18:00:00Z')
                      for t in ('BAL','JAX')])
    base=m.availability_table(target,qb,snaps,inj,rost)
    return target,base,qb,snaps,inj,rost


def resolve(observations=(),**kwargs):
    return m.resolve_game_availability(*inputs(),observations=observations,asof=NOW,**kwargs).set_index('team')


def evidence(resolved,team='BAL'):
    return json.loads(resolved.loc[team,'availability_evidence'])


def board(resolved):
    return dict(game_id=GAME,home='BAL',away='JAX',availability_policy=m.AVAILABILITY_POLICY,
                **{f'{side}_{c}':resolved.loc[team,c] for side,team in [('home','BAL'),('away','JAX')]
                   for c in ['availability_evidence','availability_evidence_sha256']})


def test_confirmed_starter_beats_history_and_preserves_other_team():
    original=resolve()
    changed=resolve([fact()])
    assert changed.loc['BAL','qb_expected']=='Backup'
    assert changed.loc['BAL','qb_source']=='confirmed_starter'
    assert changed.loc['BAL','qb_delta']<original.loc['BAL','qb_delta']
    assert changed.loc['JAX','qb_delta']==original.loc['JAX','qb_delta']
    assert not evidence(changed)['blockers']
    assert m.injury_reports_ready(board(changed),pd.Timestamp(KO),NOW)


@pytest.mark.parametrize('changes',[{'status':'pending'},{'observed_utc':'2026-11-04T21:00:00Z'},
    {'effective_utc':'2026-11-04T21:00:00Z'},{'game_id':'2026_10_JAX_BAL'}, {'team':'JAX'}])
def test_pending_late_future_or_other_game_never_changes_bal(changes):
    base=resolve()
    changed=resolve([fact(**changes)])
    assert changed.loc['BAL','qb_expected']==base.loc['BAL','qb_expected']
    assert changed.loc['BAL','qb_delta']==base.loc['BAL','qb_delta']


def test_later_capture_cannot_change_an_earlier_asof():
    observation=fact(observed_utc='2026-11-04T21:00:00Z')
    args=inputs()
    early=m.resolve_game_availability(*args,observations=[observation],asof=NOW).set_index('team')
    late=m.resolve_game_availability(*args,observations=[observation],asof=NOW+dt.timedelta(hours=2)).set_index('team')
    assert early.loc['BAL','qb_expected']=='Starter' and late.loc['BAL','qb_expected']=='Backup'


def test_same_week_addition_requires_separate_eligibility_fact():
    starter=fact(pid=ARRIVAL,player='Arrival')
    blocked=resolve([starter])
    assert evidence(blocked)['blockers']
    assert not m.injury_reports_ready(board(blocked),pd.Timestamp(KO),NOW)
    allowed=resolve([starter,fact('eligible',ARRIVAL,player='Arrival')])
    assert allowed.loc['BAL','qb_expected']=='Arrival' and not evidence(allowed)['blockers']


def test_medical_out_cannot_be_cleared_by_membership_or_starter_fact():
    args=list(inputs())
    args[4]=pd.concat([args[4],pd.DataFrame([dict(season=2026,week=9,team='BAL',gsis_id=BACKUP,
        report_status='Out',date_modified='2026-11-04T18:00:00Z')])],ignore_index=True)
    blocked=m.resolve_game_availability(*args,observations=[fact(),fact('eligible')],asof=NOW).set_index('team')
    assert evidence(blocked)['blockers'] and not m.injury_reports_ready(board(blocked),pd.Timestamp(KO),NOW)
    cleared=m.resolve_game_availability(*args,observations=[fact(),fact('eligible'),fact('report_status',value='Available')],asof=NOW).set_index('team')
    assert cleared.loc['BAL','qb_expected']=='Backup' and not evidence(cleared)['blockers']


@pytest.mark.parametrize('reverse',[False,True])
def test_ineligible_fact_wins_over_medical_clearance_regardless_of_file_order(reverse):
    facts=[fact(),fact('eligible',value=False),fact('report_status',value='Available')]
    blocked=resolve(facts[::-1] if reverse else facts)
    assert evidence(blocked)['blockers']


def test_dated_game_eligibility_can_supersede_legacy_permanent_event():
    events=pd.DataFrame([[dt.date(2026,11,1),'BAL',BACKUP,'Backup','released','old release']],columns=m.PERSONNEL_COLUMNS)
    allowed=resolve([fact(),fact('eligible')],events=events)
    assert allowed.loc['BAL','qb_expected']=='Backup' and not evidence(allowed)['blockers']


def test_newer_official_medical_status_wins_over_stale_correction():
    args=list(inputs())
    args[4]=pd.concat([args[4],pd.DataFrame([dict(season=2026,week=9,team='BAL',gsis_id=BACKUP,
        report_status='Out',date_modified='2026-11-04T19:45:00Z')])],ignore_index=True)
    result=m.resolve_game_availability(*args,observations=[fact(),fact('report_status',value='Available')],asof=NOW).set_index('team')
    assert evidence(result)['blockers']


def test_undated_medical_out_cannot_be_cleared():
    args=list(inputs())
    args[4]=pd.DataFrame([dict(season=2026,week=9,team='BAL',gsis_id=BACKUP,report_status='Out')])
    result=m.resolve_game_availability(*args,observations=[fact('report_status',value='Available')],asof=NOW).set_index('team')
    assert any('cannot date' in b for b in evidence(result)['blockers'])


def test_conflicting_or_unknown_starters_block_the_lock():
    conflict=resolve([fact(),fact(pid=STARTER,player='Starter')])
    assert evidence(conflict)['blockers']
    unknown=resolve([fact(pid='00-9999999')])
    assert evidence(unknown)['blockers']
    assert not m.injury_reports_ready(board(conflict),pd.Timestamp(KO),NOW)


def test_newer_starter_announcement_supersedes_older_announcement():
    older=fact(pid=STARTER,player='Starter',published_utc='2026-11-04T18:00:00Z',effective_utc='2026-11-04T18:00:00Z')
    changed=resolve([older,fact()])
    assert changed.loc['BAL','qb_expected']=='Backup' and not evidence(changed)['blockers']


def test_practice_only_does_not_become_a_final_report_as_time_runs_out():
    args=inputs('practice')
    asof=pd.Timestamp(KO)-pd.Timedelta(hours=2)
    unresolved=m.resolve_game_availability(*args,observations=[fact()],asof=asof).set_index('team')
    assert not m.injury_reports_ready(board(unresolved),pd.Timestamp(KO),asof)
    # A player update alone is not proof of an entire final report, including zero-designation reports.
    complete=m.resolve_game_availability(*args,observations=[fact('report_complete'),fact('report_complete',team='JAX')],asof=asof).set_index('team')
    assert m.injury_reports_ready(board(complete),pd.Timestamp(KO),asof)


def test_completed_games_are_never_rebuilt_by_new_observations():
    args=list(inputs())
    args[0]=args[0].assign(result=3.)
    assert m.resolve_game_availability(*args,observations=[fact()],asof=NOW).empty
    args[0]=args[0].assign(result=np.nan)
    assert m.resolve_game_availability(*args,observations=[fact()],asof=pd.Timestamp(KO)).empty


@pytest.mark.parametrize('changes',[{'team':'ARI'},{'gsis_id':'bad'},{'observed_utc':'2026-11-04'},
    {'published_utc':'2026-11-05T00:00:00Z'},{'source_url':'http://example.com'},
    {'field':'typo'},{'value':'true'},{'position':'WR'},{'status':'rumor'}])
def test_invalid_observation_is_rejected(changes,tmp_path):
    with pytest.raises(ValueError): m.validate_availability_observation(fact(**changes))
    import validate_data_files as v
    path=tmp_path/'availability_observations.jsonl'
    path.write_text(json.dumps(fact(**changes))+'\n')
    with pytest.raises(ValueError): v.validate_availability_observations(path)


def test_capture_stamps_first_seen_time_and_never_rewrites_existing_lines(tmp_path):
    path=tmp_path/'observations.jsonl'
    first=append_observation(path,fact(observed_utc='2020-01-01T00:00:00Z'),now=NOW)
    assert first['observed_utc']==NOW.isoformat()
    prefix=path.read_bytes()
    append_observation(path,fact('report_status',value='Out'),now=NOW+dt.timedelta(minutes=1))
    assert path.read_bytes().startswith(prefix) and len(m.load_availability_observations(path))==2
    with pytest.raises(ValueError):
        append_observation(path,fact(published_utc='2026-11-05T00:00:00Z'),now=NOW)


def test_loader_missing_duplicates_and_corruption(tmp_path):
    path=tmp_path/'observations.jsonl'
    assert m.load_availability_observations(path)==[]
    line=json.dumps(fact())+'\n'
    path.write_text(line+line)
    assert len(m.load_availability_observations(path))==1
    path.write_text(line+'{bad}')
    with pytest.raises(ValueError,match=':2:'): m.load_availability_observations(path)


def test_evidence_tampering_wrong_game_and_future_capture_fail_closed():
    good=board(resolve([fact()]))
    assert m.availability_snapshot(good,pd.Timestamp(KO),NOW)
    for change in [{'game_id':'2026_10_JAX_BAL'},{'home_availability_evidence_sha256':'bad'}]:
        assert m.availability_snapshot(dict(good,**change),pd.Timestamp(KO),NOW) is None
    assert m.availability_snapshot(good,pd.Timestamp(KO),NOW-dt.timedelta(seconds=1)) is None


def test_overlay_changes_only_target_game_and_does_not_mutate_base():
    resolved=resolve([fact()]).reset_index()
    frame=pd.DataFrame([dict(game_id=g,home='BAL',away='JAX',**{
        f'{s}__avail__{c}':0. for s in ('home','away') for c in m.ALL_AVAIL_COLS}) for g in (GAME,'old')])
    original=frame.copy(deep=True)
    changed=m.apply_game_availability(frame,resolved)
    pd.testing.assert_frame_equal(frame,original)
    assert changed.loc[0,'home_qb_expected']=='Backup'
    assert changed.loc[1,'home__avail__qb_delta']==0
    assert changed.loc[0,'d__avail__qb_delta']==pytest.approx(
        changed.loc[0,'home__avail__qb_delta']-changed.loc[0,'away__avail__qb_delta'])


def test_v120_identity_keeps_old_frozen_signatures_and_ten_terms():
    assert m.REVISION=='boxscore-composite-v1.23'
    sig20,cfg=m.config_signature()
    assert cfg['availability_observations']['policy']==m.AVAILABILITY_POLICY
    assert len(sum(m.model_terms(m.PRODUCT_RECIPE),[]))==10
    with m.revision_identity('boxscore-composite-v1.19',m.PRODUCT_RECIPE):
        sig19,old=m.config_signature()
        assert 'availability_observations' not in old
    assert sig20!=sig19


def test_production_overlay_keeps_coefficients_historical_rows_and_shadow_inputs():
    from test_product_production import fixture
    train,test=fixture()
    for c in m.ALL_AVAIL_COLS:
        for side in ('home','away'): test[f'{side}__avail__{c}']=0.
    source={8.:pd.concat([train,test],ignore_index=True)}
    original=source[8.].copy(deep=True)
    before_shadow={}; after_shadow={}
    before,fit=m.current_predictions(source,m.PRODUCT_RECIPE,2023,1,before_shadow)
    correction=dict(game_id='a',team='H',qb_expected='Announced QB',qb_usual='Starter',injury_report='final',
                    availability_evidence='{}',availability_evidence_sha256='fixture',**{c:2. if c=='qb_delta' else 0. for c in m.ALL_AVAIL_COLS})
    after,refit=m.current_predictions(source,m.PRODUCT_RECIPE,2023,1,after_shadow,availability=pd.DataFrame([correction]))
    assert fit==refit
    assert after.loc[after.game_id.eq('a'),'model_wp'].iloc[0]!=before.loc[before.game_id.eq('a'),'model_wp'].iloc[0]
    np.testing.assert_array_equal(after.loc[~after.game_id.eq('a'),'model_wp'],before.loc[~before.game_id.eq('a'),'model_wp'])
    pd.testing.assert_frame_equal(before_shadow['board'],after_shadow['board'])
    pd.testing.assert_frame_equal(source[8.],original)


def test_ats_candidate_and_lock_preserve_evidence_and_reject_missing_or_bad_evidence(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'REVISION','boxscore-composite-v1.20')  # original manual-evidence contract
    import ats_locks as a
    resolved=resolve([fact()])
    raw=dict(board(resolved),season=2026,week=9,gameday='2026-11-05',gametime='20:15',result='',ready=True,
             model_wp=.7,spread_line=3.,home_injury_report='final',away_injury_report='final')
    latest=tmp_path/'latest';latest.mkdir()
    generated=pd.Timestamp(KO)-pd.Timedelta(hours=2)
    (latest/'manifest.json').write_text(json.dumps(dict(revision=m.REVISION,generated_utc=generated.isoformat(),
        recipe=m.PRODUCT_RECIPE,config_signature=m.config_signature()[0])))
    rule=dict(season=2026,week=9,training_max_season=2026,training_max_week=8,training_games=1400,
              cuts=[3.,7.,10.],magnitudes=[3.,4.,7.,14.],method='weighted_median_signed_mov_weekly_decay')
    (latest/'fixed_band_rules.json').write_text(json.dumps([rule]))
    pd.DataFrame([dict(raw,home_availability_evidence_sha256='bad')]).to_csv(latest/'board.csv',index=False)
    assert a.record(tmp_path,generated)==dict(candidates=0,locks=0)
    pd.DataFrame([{k:v for k,v in raw.items() if k!='availability_policy'}]).to_csv(latest/'board.csv',index=False)
    assert a.record(tmp_path,generated)==dict(candidates=0,locks=0)
    pd.DataFrame([raw]).to_csv(latest/'board.csv',index=False)
    assert a.record(tmp_path,generated)==dict(candidates=1,locks=0)
    candidate=a.read(tmp_path/a.CANDIDATES)[0]
    assert candidate['availability']['home']['observations'][0]['gsis_id']==BACKUP
    assert a.record(tmp_path,a.deadline(KO))==dict(candidates=0,locks=1)
    locked=(tmp_path/a.LOCKS).read_bytes()
    assert a.read(tmp_path/a.LOCKS)[0]['availability']==candidate['availability']
    a.record(tmp_path,pd.Timestamp(KO)+pd.Timedelta(minutes=1))
    assert (tmp_path/a.LOCKS).read_bytes()==locked


def test_rehashing_cannot_authorize_post_forecast_availability(tmp_path):
    import ats_locks as a
    saved=dict(revision='boxscore-composite-v1.20',game_id=GAME,home='BAL',away='JAX',generated_utc=NOW.isoformat(),
               kickoff_utc=KO,availability_policy=m.AVAILABILITY_POLICY,
               availability=m.availability_snapshot(board(resolve([fact()])),pd.Timestamp(KO),NOW))
    a.validate_availability(saved)
    saved['availability']['home']['observations'][0]['observed_utc']=(NOW+dt.timedelta(seconds=1)).isoformat()
    with pytest.raises(ValueError,match='availability evidence invalid'): a.validate_availability(saved)


def test_report_notes_follow_resolved_sourced_facts():
    """Displayed injury details come from the facts the forecast applied, not the stale feed."""
    import json
    import pandas as pd
    import nfl_model as m
    snaps=pd.DataFrame([dict(season=2026,week=w,game_id=f'g{w}',team='BAL',gsis_id=g,position=pos,
                             offense_snaps=n,defense_snaps=0.) for w in (6,7,8)
                        for g,pos,n in (('qb1','QB',60.),('qb2','QB',1.),('wr','WR',50.),('rb','RB',30.))])
    detail=pd.DataFrame([dict(season=2026,week=9,team='BAL',gsis_id='qb1',full_name='Lamar QB',position='QB',
                              report_status=None,practice_status='Limited Participation in Practice'),
                         dict(season=2026,week=9,team='BAL',gsis_id='wr',full_name='Wide R',position='WR',
                              report_status=None,practice_status='Did Not Participate In Practice')])
    def frame(observations,blockers=()):
        evidence=dict(observations=observations,blockers=list(blockers))
        return pd.DataFrame([dict(season=2026,week=9,team='BAL',availability_evidence=json.dumps(evidence))])
    fact=lambda field,pid,value,name='Lamar QB',pos='QB':dict(field=field,gsis_id=pid,value=value,player=name,position=pos)
    base=m.resolved_report_notes(detail,snaps,['BAL'],2026,9).set_index('gsis_id')
    assert base.loc['qb1','report_state']=='practice' and base.loc['qb1','this_week'].startswith('practice')
    obs=[fact('report_status','qb1','Out'),fact('eligible','qb2',False,'Backup QB'),
         dict(field='report_complete',value=True,gsis_id='',player='',position='')]
    n=m.resolved_report_notes(detail,snaps,['BAL'],2026,9,resolved=frame(obs)).set_index('gsis_id')
    assert n.loc['qb1','this_week']=='Out' and n.loc['qb1','counted']==1
    assert n.loc['qb2','this_week']=='Inactive (official list)' and n.loc['qb2','counted']==1
    assert (n.report_state=='final').all() and n.loc['wr','counted']==0
    # A single sourced status does not by itself make the team's report final.
    partial=m.resolved_report_notes(detail,snaps,['BAL'],2026,9,resolved=frame(obs[:1])).set_index('gsis_id')
    assert partial.loc['qb1','this_week']=='Out' and (partial.report_state=='practice').all()
    assert partial.loc['wr','this_week'].startswith('practice')
    # Blocked resolutions are not applied by the model, so the display keeps the feed.
    blocked=m.resolved_report_notes(detail,snaps,['BAL'],2026,9,resolved=frame(obs,['starting quarterback unresolved']))
    assert blocked.set_index('gsis_id').loc['qb1','this_week'].startswith('practice')
    # Other weeks' resolutions never touch this week's notes.
    other=frame(obs).assign(week=8)
    assert m.resolved_report_notes(detail,snaps,['BAL'],2026,9,resolved=other).equals(m.resolved_report_notes(detail,snaps,['BAL'],2026,9))
