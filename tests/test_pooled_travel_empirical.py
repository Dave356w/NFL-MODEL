"""Pooled travel model: inference safety and meaningful synthetic recovery."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import check_grad

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import pooled_travel_empirical as p


def fixture(n=900, signal=True):
    rng=np.random.default_rng(14)
    label=np.tile(np.arange(3),n//3)
    spread=rng.normal(0,5,n)
    total=rng.normal(44,5,n)
    margin=spread+rng.normal(0,14,n)+(np.where(label==1,7,np.where(label==2,-7,0)) if signal else 0)
    points=total+rng.normal(0,10,n)
    h=pd.DataFrame(dict(game_id=[f'g{i}' for i in range(n)],season=2022,week=5,
        feature_travel=np.array(p.CLASSES)[label],spread_line=spread,total_line=total,
        home_score=(points+margin)/2,away_score=(points-margin)/2))
    target=dict(game_id='new',season=2023,week=5,spread_line=0.,total_line=44.,feature_travel='eastward2plus')
    w=np.ones(n)/n
    base=dict(home=h.home_score.to_numpy(),away=h.away_score.to_numpy(),weights=w,source_ids=h.game_id.to_numpy(),audit={})
    return h,target,base


@pytest.mark.parametrize('quadratic',[False,True])
def test_analytic_gradient(quadratic):
    h,_,_=fixture(30)
    x=p.design(h.spread_line,h.total_line,h.home_score,h.away_score,quadratic)
    y=np.tile(np.arange(3),10)
    theta=np.random.default_rng(1).normal(0,.1,x.shape[1]*2)
    weights=np.linspace(.1,1,30)
    penalty=np.linspace(.01,20,x.shape[1])
    fun=lambda z:p.objective(z,x,y,weights,penalty)[0]
    jac=lambda z:p.objective(z,x,y,weights,penalty)[1]
    assert check_grad(fun,jac,theta)<1e-5


def test_planted_travel_signal_changes_shape_without_changing_atoms():
    h,t,base=fixture()
    c=p.CANDIDATES[1]
    f=p.fit(h,t,c)
    east=p.tilt(base,h,t,c,f)
    west=p.tilt(base,h,t|{'feature_travel':'westward2plus'},c,f)
    margin=base['home']-base['away']
    assert east['weights']@margin>base['weights']@margin+1
    assert west['weights']@margin<base['weights']@margin-1
    for result in [east,west]:
        assert np.isclose(result['weights'].sum(),1)
        assert (result['weights']>0).all()
        assert result['home'] is base['home'] and result['away'] is base['away']
        # [0.5,2] cap, renormalization and mixing bound relative movement.
        assert np.max(result['weights']/base['weights'])<=4


def test_stronger_ridge_reduces_outcome_coefficients():
    h,t,_=fixture()
    weak=p.fit(h,t,p.Config('weak',False,20))
    strong=p.fit(h,t,p.Config('strong',False,100))
    assert np.linalg.norm(strong['coef'][6:])<np.linalg.norm(weak['coef'][6:])


def test_market_only_fit_exactly_equals_plain():
    h,t,base=fixture()
    f=p.fit(h,t,p.CANDIDATES[1]);f['coef'][6:]=0
    f['coef'][:6]=np.random.default_rng(2).normal(size=(6,2))
    result=p.tilt(base,h,t,p.CANDIDATES[1],f)
    assert np.array_equal(result['weights'],base['weights'])
    assert result['audit']['travel_fallback']


def test_unknown_and_low_support_fallback_and_no_unknown_training():
    h,t,base=fixture()
    c=p.CANDIDATES[1];f=p.fit(h,t,c)
    unknown=p.tilt(base,h,t|{'feature_travel':None},c,f)
    assert np.array_equal(unknown['weights'],base['weights'])
    f['class_support'][1]=19.9
    assert np.array_equal(p.tilt(base,h,t,c,f)['weights'],base['weights'])
    for training in [h.iloc[:30],h.assign(feature_travel=None)]:
        f=p.fit(training,t,c)
        assert f['coef'] is None


def test_target_outcomes_and_source_travel_labels_do_not_assign_atom_likelihoods():
    h,t,base=fixture()
    c=p.CANDIDATES[1];f=p.fit(h,t,c)
    original=p.tilt(base,h,t,c,f)
    changed=p.tilt(base,h.assign(feature_travel='small_shift'),t|{'home_score':999,'away_score':-99},c,f)
    assert np.array_equal(original['weights'],changed['weights'])


def test_future_training_fit_and_misaligned_atoms_rejected():
    h,t,base=fixture()
    c=p.CANDIDATES[1]
    for training in [h.assign(season=2023,week=5),h.assign(season=2024),h.assign(season=2017)]:
        with pytest.raises(ValueError,match='prior-week'):p.fit(training,t,c)
    f=p.fit(h,t,c)
    with pytest.raises(ValueError,match='alignment'):p.tilt(base,h.iloc[::-1],t,c,f)
    with pytest.raises(ValueError,match='Future'):p.tilt(base,h,t,c,f|{'training_max_season':2023,'training_max_week':5})


def test_selector_uses_earlier_winner_loss_and_plain_tie_break():
    rows=[dict(arm=c.name,season=y,win_ll=.6,primary_crps=100-i)
          for i,c in enumerate(p.CANDIDATES) for y in [2021,2022,2023]]
    frame=pd.DataFrame(rows)
    frame.loc[(frame.season==2023)&frame.arm.eq(p.CANDIDATES[1].name),'win_ll']=0
    name,audit=p.select(frame,2023)
    assert name=='plain' and audit['selection_max_season']==2022
    with pytest.raises(ValueError,match='two earlier'):p.select(frame,2022)
    frame.loc[(frame.season==2022)&frame.arm.eq(p.CANDIDATES[1].name),'win_ll']=.5
    assert p.select(frame,2023)[0]==p.CANDIDATES[1].name


def test_design_residuals_and_prediction_market_are_target_relative():
    x=p.design(3,45,np.array([24,31]),np.array([21,14]),False)
    assert np.array_equal(x[:,1],np.array([.3,.3]))
    assert np.array_equal(x[:,6],np.array([0.,1.]))
    assert np.array_equal(x[:,7],np.array([0.,0.]))
    with pytest.raises(ValueError,match='Nonfinite'):p.design(np.nan,45,24,21,False)
