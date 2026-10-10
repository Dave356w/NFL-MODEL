"""Qualification must reject weak evidence and preserve chronological selection."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'research'))
import production_qualification as p


def test_gate_requires_all_three_positive_lower_bounds():
    assert p.gate([[.01,.03],[.001,.02],[.01,.04]]) == 'pass'
    assert p.gate([[.01,.03],[-.001,.02],[.01,.04]]) == 'unresolved'
    assert p.gate([[-.04,-.01],[.001,.02],[.01,.04]]) == 'adverse'
    with pytest.raises(ValueError): p.gate([[np.nan,.1],[.1,.2],[.1,.2]])


def test_bootstrap_is_clustered_and_deterministic():
    assert p.cluster_interval([1.,1.,1.,1.],['a','a','b','b'],reps=100)==[1.,1.]
    assert p.cluster_interval([1.,-1.,.5,-.5],['a','a','b','b'],reps=100)==[0.,0.]
    with pytest.raises(ValueError): p.cluster_interval([1.,np.nan],['a','b'])


def test_selection_never_uses_current_season_outcomes(monkeypatch):
    monkeypatch.setattr(p,'ARMS',('market_product',))
    configs={'a':{'arm':'market_product'},'b':{'arm':'market_product'}}
    rows=[]
    for yr in range(2021,2026):
        for i in range(2):
            r={k:0 for k in p.BASE_COLS}; r.update(game_id=f'{yr}_{i}',season=yr,week=i+1,q=.5)
            r['home won']=float(i); r['a']=.8 if i else .2; r['b']=.2 if i else .8
            rows.append(r)
    d=pd.DataFrame(rows); _, a=p.select_outer(d,configs)
    altered=d.copy(); altered.loc[altered.season==2023,'home won']=1-altered.loc[altered.season==2023,'home won']
    _, b=p.select_outer(altered,configs)
    assert a[0]['key']==b[0]['key']=='a'
    assert a[0]['selection_through_season']==2022


def test_current_or_future_training_rows_are_rejected():
    train=pd.DataFrame({'season':[2023],'week':[1]})
    test=train.copy()
    with pytest.raises(ValueError,match='current or future'):
        p.fit_predict(train,test,[],[],.1,.1,True)


def test_research_fitter_matches_production_math():
    n=p.m.MIN_TRAIN_GAMES+10
    rng=np.random.default_rng(13)
    names=p.m.feature_names(p.q.BASE_FAMILY)
    t=pd.DataFrame(rng.normal(size=(n,len(names))),columns=names)
    t['site']=1.; t['season']=2021; t['week']=np.arange(n)%18+1
    t['home won']=rng.integers(0,2,n).astype(float); t['ready']=True; t['q']=.6
    te=t.iloc[:5].copy(); te['season']=2023; te['week']=1
    expected=p.m.apply_fit(te,p.m.fit_composite(t,{'family':p.q.BASE_FAMILY,'half_life':8.,'ridge':.1},2023,1))
    actual,_=p.fit_predict(t,te,names,[],.1,.1,False)
    assert np.allclose(actual,expected,atol=1e-10)


def test_market_pickem_and_candidate_abstention_use_common_sample():
    h=pd.DataFrame({'home_moneyline':[-110,-150,-150], 'away_moneyline':[-110,130,130],
                    'home won':[1.,0.,.5], 'q':[.5,.6,.6]})
    for arm in p.ARMS: h[arm]=[.6,.6,.6]
    h.loc[1,p.ARMS[0]]=.5
    bets,common=p.common_bets(h)
    assert common.tolist()==[False,False,True]
    assert all(b.loc[2,'units']==0. for b in bets.values())


def test_ties_push_for_roi_but_do_not_enter_proper_scores(monkeypatch):
    h=pd.DataFrame({'season':[2023,2023,2024,2024,2025,2025], 'week':[1,2]*3,
                    'game_id':[str(i) for i in range(6)],
                    'home_moneyline':[-150]*6, 'away_moneyline':[130]*6,
                    'home won':[1.,.5]*3, 'q':[.6]*6})
    for arm in p.ARMS: h[arm]=.65
    monkeypatch.setattr(p,'cluster_interval',lambda *a,**kw: [-1.,1.])
    rows,_,sample=p.summarize(h)
    assert sample['proper_score_games']==3 and sample['primary_bet_games']==6
    assert sample['ties_predicted']==3
    assert rows[0]['pushes']==3 and rows[0]['wins']==3
    assert rows[0]['log_loss']==pytest.approx(-np.log(.65))
