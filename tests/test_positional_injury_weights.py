"""Chronology, saved-report eligibility and exact median-loss behavior."""
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RESEARCH=Path(__file__).parents[1]/'research'
if str(RESEARCH) not in sys.path:sys.path.insert(0,str(RESEARCH))
import injury_saved_inputs as s
import positional_injury_weights as p


def test_saved_report_requires_complete_predeadline_capture_and_publication():
    cutoff=pd.Timestamp('2026-11-08T17:00:00Z')
    good=dict(game_id='g',team='A',kind='official_injury_report',captured_utc='2026-11-08T16:00:00Z',
              source_published_utc=None,source_capture_sha256='a',parsed={'complete':True,'issues':[],
              'rows':[{'gsis_id':'id','status':'Out'}]})
    rows=[good,dict(good,captured_utc='2026-11-08T17:00:01Z',source_capture_sha256='late'),
          dict(good,source_published_utc='2026-11-08T18:00:00Z',source_capture_sha256='futurepub'),
          dict(good,captured_utc='2026-11-08T15:00:00Z',parsed={'complete':False,'rows':[]},source_capture_sha256='incomplete')]
    before=deepcopy(rows);assert s.choose_report(rows,'g','A',cutoff)==good;assert rows==before
    assert s.choose_report(rows,'g','B',cutoff) is None
    assert s.choose_report([dict(good,captured_utc='2026-11-08T16:00:00')],'g','A',cutoff) is None
    incomplete=dict(good,captured_utc='2026-11-08T16:30:00Z',parsed={'complete':False,'rows':[]})
    assert s.choose_report([good,incomplete],'g','A',cutoff) is None


def test_latest_saved_vector_rejects_postdeadline_or_missing_positions():
    cutoff=pd.Timestamp('2026-11-08T17:00:00Z')
    make=lambda t:dict(game_id='g',revision='v',generated_utc=t,model_inputs={c:0. for c in s.VECTOR_NAMES})
    old=make('2026-11-08T15:00:00Z');new=make('2026-11-08T16:00:00Z');late=make('2026-11-08T18:00:00Z')
    assert s.choose_vector([old,new,late],'g',cutoff)==new
    missing=make('2026-11-08T16:30:00Z');del missing['model_inputs'][s.VECTOR_NAMES[0]]
    assert s.choose_vector([missing],'g',cutoff) is None


def snaps():
    rows=[]
    for week in [1,2,3,4,5]:
        for unit in s.GROUPS:
            for pid,n in ([(unit+'a',80),(unit+'b',20)] if unit=='OL' else [(unit,100)]):
                rows.append(dict(team='A',season=2026,week=week,game_id=str(week),gsis_id=pid,position='WR' if unit=='WRTE' else unit,
                                 offense_snaps=n if unit in ['OL','WRTE','RB'] else 0,
                                 defense_snaps=n if unit in ['DL','LB','DB'] else 0))
    return pd.DataFrame(rows)


def test_burden_uses_only_earlier_role_snaps_and_exposes_unseen_players():
    status=[{'gsis_id':'OLa','status':'Out'},{'gsis_id':'OLb','status':'Questionable'},
            {'gsis_id':'unknown','status':'Out'},{'gsis_id':'DB','status':'Available'}]
    f=snaps();a,unseen=s.burden(s.SnapWindows(f),'A',2026,4,status)
    assert a['OL']==pytest.approx(.85) and a['DB']==0 and unseen==1
    f.loc[f.week>=4,['offense_snaps','defense_snaps']]=9999
    b,_=s.burden(s.SnapWindows(f),'A',2026,4,status);assert a==b


def test_median_intercept_is_not_outlier_driven_mean():
    f=pd.DataFrame({'prediction':[0.,0.,0.],'result':[0.,0.,100.]})
    fit=p.fit_median(f,[]);assert fit['intercept']==0
    np.testing.assert_array_equal(p.predict(f,fit),[0,0,0])


def test_quantile_solver_recovers_planted_positional_signal():
    rng=np.random.default_rng(15);x=rng.uniform(-1,1,(300,2))
    f=pd.DataFrame(x,columns=['inj_OL','inj_DB']);f['prediction']=0.;f['result']=-4*x[:,0]+3*x[:,1]
    f.loc[:9,'result']+=100
    fit=p.fit_median(f,['inj_OL','inj_DB'])
    assert fit['beta'][0]<0 and fit['beta'][1]>0
    assert np.median(abs(p.predict(f,fit)-(-4*x[:,0]+3*x[:,1])))<.1
    before=p.predict(f,fit);f['result']=-999;np.testing.assert_array_equal(before,p.predict(f,fit))


def test_rolling_weights_never_use_same_week_or_future_labels():
    h=pd.DataFrame({'season':[2025],'week':[18],'result':[1.]})
    c=pd.DataFrame({'season':[2026,2026,2026],'week':[5,6,7],'result':[2.,3.,4.]})
    before=p.earlier_training(h,c,6);c.loc[c.week>=6,'result']=999
    pd.testing.assert_frame_equal(before,p.earlier_training(h,c,6))
    assert list(before.result)==[1.,2.]
    with pytest.raises(ValueError):p.earlier_training(h.assign(season=2026),c,6)


def test_empirical_cover_probabilities_preserve_push_mass_and_sign_symmetry():
    errors=np.array([-7.,-3.,0.,3.,7.])
    a=p.cover_probability(np.array([0.,2.]),errors,np.array([0.,2.]))
    np.testing.assert_allclose(a,[.5,.5])
    b=p.cover_probability(np.array([1.2]),errors,np.array([3.]))
    c=p.cover_probability(np.array([-1.2]),-errors,np.array([-3.]))
    assert b[0]+c[0]==pytest.approx(1)
    assert 0<b[0]<1


def test_ats_pushes_refund_and_leave_cover_scoring_denominator():
    f=pd.DataFrame({'result':[7.,0.,3.],'spread_line':[3.,3.,3.],'adjusted_median':[5.,5.,5.],
                    'p_home_cover':[.6,.6,.99],'arm':['rolling_injury']*3})
    a=p.metrics(f);assert (a['wins'],a['losses'],a['pushes'],a['cover_n'])==(1,1,1,2)
    assert a['units']==pytest.approx(100/110-1)
