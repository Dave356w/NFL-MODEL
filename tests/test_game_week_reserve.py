"""v1.15: the game week's own reserve list counts out; nothing else on that roster is read."""
import pandas as pd
import pytest

import nfl_model as m


def fixture():
    """Two teams, two tackles each (p 60%, q 40% of OL snaps), weeks 1-4 played, forecast week 5."""
    targets=pd.DataFrame([{'season':2026,'week':5,'team':t} for t in ('PHI','BAL')])
    snaps=pd.DataFrame([{'season':2026,'week':w,'game_id':f'{t}{w}','team':t,'gsis_id':f'{t}_{pid}',
                         'position':'T','offense_snaps':n,'defense_snaps':0}
                        for t in ('PHI','BAL') for w in range(1,5) for pid,n in (('p',60),('q',40))])
    rost=pd.DataFrame([{'season':2026,'week':4,'team':t,'gsis_id':f'{t}_{pid}','position':'T','status':'ACT',
                        'status_description_abbr':None,'full_name':f'{t} {pid}'} for t in ('PHI','BAL') for pid in ('p','q')])
    inj=pd.DataFrame(columns=['season','week','team','gsis_id','report_status'])
    return targets,snaps,rost,inj


def game_week(rows):
    return pd.DataFrame([{'season':2026,'team':'PHI','position':'T','full_name':'PHI p','status_description_abbr':None,**r}
                         for r in rows])


def avail(extra=None,on=True,inj=None,week=5):
    t,s,r,i=fixture()
    if extra is not None: r=pd.concat([r,extra],ignore_index=True)
    old=m.GAME_WEEK_RESERVE; m.GAME_WEEK_RESERVE=on
    try: return m.availability_table(t.assign(week=week),None,s,i if inj is None else inj,r).set_index('team')
    finally: m.GAME_WEEK_RESERVE=old


IR=game_week([{'week':5,'gsis_id':'PHI_p','status':'RES','status_description_abbr':'R01'},
              {'week':5,'gsis_id':'PHI_q','status':'ACT'}])


def test_game_week_reserve_counts_out_for_that_team_only():
    a=avail(IR)
    assert a.loc['PHI','OL_out_cs']==pytest.approx(.6)
    assert a.loc['BAL','OL_out_cs']==0


@pytest.mark.parametrize('code,desc',[('CUT','W03'),('TRD',None),('ACT','R48'),('PUP',None)])
def test_other_roster_out_codes_on_the_game_week_roster(code,desc):
    rows=game_week([{'week':5,'gsis_id':'PHI_p','status':code,'status_description_abbr':desc}])
    assert avail(rows).loc['PHI','OL_out_cs']==pytest.approx(.6)


def test_switch_off_reproduces_v114():
    pd.testing.assert_frame_equal(avail(IR,on=False),avail())


@pytest.mark.parametrize('rows',[
    [{'week':5,'gsis_id':'PHI_p','status':'ACT'},{'week':5,'gsis_id':'PHI_q','status':'ACT'}],  # active
    [{'week':5,'gsis_id':'PHI_p','status':'INA'}],                                              # game-day inactive stays a member
    [{'week':5,'gsis_id':'PHI_q','status':'ACT'}],                                              # absent from game-week roster: not read
    [{'week':6,'gsis_id':'PHI_p','status':'RES','status_description_abbr':'R01'}],              # a LATER week never applies
    [{'week':5,'gsis_id':'PHI_p','status':'RES','team':'BAL'}],                                 # another team's reserve list
])
def test_negative_cases_identical_to_baseline(rows):
    pd.testing.assert_frame_equal(avail(game_week(rows)),avail())


def test_game_week_activation_does_not_clear_prior_week_reserve():
    t,s,r,i=fixture()
    r.loc[r.gsis_id=='PHI_p',['status','status_description_abbr']]=['RES','R01']  # on IR in week 4
    back=pd.concat([r,game_week([{'week':5,'gsis_id':'PHI_p','status':'ACT'}])],ignore_index=True)
    assert m.availability_table(t,None,s,i,back).set_index('team').loc['PHI','OL_out_cs']==pytest.approx(.6)


def test_week_one_unchanged():
    t,s,r,i=fixture()
    w1=r.assign(week=1); s0=s.assign(season=2025)
    # q (40%) on IR in the week-1 roster; under half the window, so membership is not a data gap.
    ir=game_week([{'week':1,'gsis_id':'PHI_q','status':'RES','status_description_abbr':'R01'}])
    out=[]
    for on in (True,False):
        old=m.GAME_WEEK_RESERVE; m.GAME_WEEK_RESERVE=on
        try: out.append(m.availability_table(t.assign(week=1),None,s0,i,pd.concat([w1[w1.gsis_id!='PHI_q'],ir])))
        finally: m.GAME_WEEK_RESERVE=old
    pd.testing.assert_frame_equal(out[0],out[1])
    assert out[0].set_index('team').loc['PHI','OL_out']==pytest.approx(.4)  # week 1 already reads its own roster


def test_reserve_overrides_questionable_and_is_audited():
    q=pd.DataFrame([{'season':2026,'week':5,'team':'PHI','gsis_id':'PHI_p','report_status':'Questionable'}])
    assert avail(inj=q).loc['PHI','OL_out_cs']==pytest.approx(.6*.25)
    assert avail(IR,inj=q).loc['PHI','OL_out_cs']==pytest.approx(.6)
    t,s,r,i=fixture(); aud=[]
    m.availability_table(t,None,s,i,pd.concat([r,IR],ignore_index=True),audit=aud)
    assert aud[-1]['game_week_reserve_added']==1


def test_reserve_quarterback_is_not_projected():
    t,s,r,i=fixture()
    qb=pd.DataFrame([{'game_id':f'PHI{w}','season':2026,'week':w,'team':'PHI','gsis_id':g,'name':nm,
                      'dropbacks':db,'net_yards':db*e,'leader':ld,'starter':ld}
                     for w in range(1,5) for g,nm,db,e,ld in (('qa','Starter',36,7.,True),('qb','Backup',3,4.,False))])
    r=pd.concat([r,pd.DataFrame([{'season':2026,'week':4,'team':'PHI','gsis_id':g,'position':'QB','status':'ACT',
                                  'status_description_abbr':None} for g in ('qa','qb')])],ignore_index=True)
    base=m.availability_table(t,qb,s,i,r).set_index('team').loc['PHI']
    ir=pd.DataFrame([{'season':2026,'week':5,'team':'PHI','gsis_id':'qa','position':'QB','status':'RES','status_description_abbr':'R01'}])
    new=m.availability_table(t,qb,s,i,pd.concat([r,ir],ignore_index=True)).set_index('team').loc['PHI']
    assert base.qb_expected=='Starter' and new.qb_expected=='Backup' and new.qb_delta<base.qb_delta


def test_card_notes_show_the_game_week_reserve_list():
    t,s,r,i=fixture()
    notes=m.report_notes(None,s,['PHI','BAL'],2026,5,rost=pd.concat([r,IR],ignore_index=True))
    assert notes.gsis_id.tolist()==['PHI_p']
    assert notes.iloc[0].this_week=='Reserve/Injured (IR) on wk 5 roster' and notes.iloc[0].counted==1
    old=m.GAME_WEEK_RESERVE; m.GAME_WEEK_RESERVE=False
    try: assert m.report_notes(None,s,['PHI','BAL'],2026,5,rost=pd.concat([r,IR],ignore_index=True)).empty
    finally: m.GAME_WEEK_RESERVE=old


def test_new_experiment_identity():
    assert m.REVISION=='boxscore-composite-v1.16' and m.OUTPUT_NAME=='nfl_boxscore_output_v1_16'
    sig,cfg=m.config_signature()
    assert cfg['avail']['game_week_reserve']['enabled'] is True
    old=m.GAME_WEEK_RESERVE; m.GAME_WEEK_RESERVE=False
    try: assert m.config_signature()[0]!=sig
    finally: m.GAME_WEEK_RESERVE=old
