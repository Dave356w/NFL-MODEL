"""Chronological ATS calibration, stability and empirical-score coherence."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import check_grad
from scipy.special import expit, logit

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import ats_calibration as a


def history(n=1200):
    rng=np.random.default_rng(42)
    raw=rng.uniform(.2,.8,n)
    y=rng.random(n)<expit(.35*logit(raw))
    return pd.DataFrame(dict(game_id=[f'g{i}' for i in range(n)],season=np.where(np.arange(n)%2,2021,2022),
        week=5,cover_conditional=raw,home_score=np.where(y,27,14),away_score=20,
        spread_line=0.,total_line=44.,final_ess=100.))


@pytest.mark.parametrize('family',['temperature','platt','context'])
def test_analytic_gradient(family):
    h=history(30);c=a.Config('test',family,10);x=a.design(h,c)
    y=(h.home_score>h.away_score).to_numpy(float)
    coef=np.full(x.shape[1],.2);penalty=np.arange(x.shape[1])+1;w=np.linspace(.1,1,len(h))
    assert check_grad(lambda z:a.objective(z,x,y,w,penalty)[0],
                      lambda z:a.objective(z,x,y,w,penalty)[1],coef)<1e-5


def test_recovers_shrunken_signal_and_more_ridge_shrinks_further():
    h=history();t=dict(season=2023,week=5)
    c=a.MAP['temperature_r10'];fit=a.fit(h,t,c)
    strong=a.fit(h,t,a.MAP['temperature_r100'])
    assert .05<fit['coef'][0]<.6
    assert 0<=strong['coef'][0]<fit['coef'][0]
    test=h.iloc[:10].assign(season=2023,week=5)
    predicted=a.predict(test,fit,c)
    assert np.mean(np.abs(predicted-.5))<np.mean(np.abs(test.cover_conditional-.5))


def test_training_and_prediction_reject_future_information():
    h=history();c=a.MAP['platt_r10'];t=dict(season=2023,week=5)
    for poisoned in [h.assign(season=2023,week=5),h.assign(season=2024),h.assign(season=2017)]:
        with pytest.raises(ValueError,match='prior-week'):a.fit(poisoned,t,c)
    fitted=a.fit(h,t,c)
    test=h.iloc[:5].assign(season=2023,week=5)
    with pytest.raises(ValueError,match='Future'):
        a.predict(test,fitted|{'training_max_season':2023,'training_max_week':5},c)
    first=a.predict(test,fitted,c)
    assert np.array_equal(first,a.predict(test.assign(home_score=999,away_score=0),fitted,c))


def test_minimum_data_and_push_exclusion():
    h=history();t=dict(season=2023,week=5);c=a.MAP['platt_r10']
    f=a.fit(h.iloc[:100],t,c)
    assert f['coef'] is None
    assert np.array_equal(a.predict(h.iloc[:3].assign(season=2023),f,c),np.full(3,.5))
    f=a.fit(h.assign(home_score=20),t,c)
    assert f['training_games']==0 and f['coef'] is None


def test_stability_requires_same_side_positive_ev_and_support():
    assert a.decision(.56,.55,.1,100,'Stable')['side']=='home'
    assert a.decision(.56,.52,.1,100,'Stable')['side']=='pass'
    assert a.decision(.56,.44,.1,100,'Stable')['side']=='pass'
    assert a.decision(.56,.55,.1,49,'Stable')['side']=='pass'
    assert a.decision(.44,.45,.1,100,'Stable')['side']=='away'
    assert a.decision(.56,.44,.1,10,'EV')['side']=='home'
    assert a.decision(.56,.55,.1,100,'EV',True)['side']=='pass'
    with pytest.raises(ValueError):a.decision(.56,.55,.1,100,'invalid')


def test_reweight_preserves_atoms_push_and_within_group_shape():
    base=dict(home=np.array([10.,23.,30.,37.]),away=np.array([17.,20.,20.,20.]),
              weights=np.array([.2,.3,.2,.3]),audit={})
    dist,fallback=a.reweight(base,3,.6)
    assert not fallback
    assert np.allclose(dist['weights'],[.28,.3,.168,.252])
    assert dist['home'] is base['home'] and dist['away'] is base['away']
    assert dist['weights'][2]/dist['weights'][3]==pytest.approx(2/3)
    assert dist['weights'][1]==base['weights'][1]
    assert np.array_equal(base['weights'],np.array([.2,.3,.2,.3]))
    only_home=dict(base,weights=np.array([0.,0.,.4,.6]))
    unchanged,fallback=a.reweight(only_home,3,.6)
    assert fallback and unchanged is only_home
    with pytest.raises(ValueError):a.reweight(base,3,np.nan)


def test_selection_is_earlier_only_loss_based_with_fair_tie_break():
    f=pd.DataFrame([dict(configuration=c.name,season=y,cover_ll=.693,units=i*100)
                    for i,c in enumerate(a.CONFIGS) for y in [2017,2018,2019]])
    f.loc[(f.season==2019)&f.configuration.eq('raw'),'cover_ll']=0
    assert a.select(f,2019)[0]=='fair'
    assert a.select(f,2019)[1]['selection_max_season']==2018
    f.loc[(f.season==2018)&f.configuration.eq('temperature_r10'),'cover_ll']=.69
    assert a.select(f,2019)[0]=='temperature_r10'
    with pytest.raises(ValueError,match='two earlier'):a.select(f,2018)
