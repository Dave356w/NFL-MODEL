import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import log_loss_diagnostics as d


def fixture():
    return pd.DataFrame({'game_id':['a','b','c','d'],'season':[2023]*4,'week':[1,2,3,4],
        'home won':[1.,0.,1.,.5],'market':[.9,.1,.6,.5],'production':[.8,.2,.65,.5]})


def test_favorite_orientation_and_ties():
    f=d.prepare(fixture())
    assert len(f)==3
    assert f.market_favorite_probability.tolist()==[.9,.9,.6]
    assert f.market_favorite_won.tolist()==[1.,1.,1.]
    assert f.production_favorite_probability.tolist()==[.8,.8,.65]
    assert not f.upset.any()


def test_paired_loss_is_orientation_invariant():
    y=np.array([0.,1.]);q=np.array([.9,.6]);p=np.array([.8,.65])
    a=d.losses(y,q)-d.losses(y,p)
    b=d.losses(1-y,1-q)-d.losses(1-y,1-p)
    assert np.allclose(a,b)
    with pytest.raises(ValueError):d.losses([.5],[.5])
    with pytest.raises(ValueError):d.losses([1.],[1.])


def test_duplicate_games_rejected():
    f=fixture();f.loc[1,'game_id']='a'
    with pytest.raises(ValueError):d.prepare(f)


def test_null_identical_models_and_expected_penalty():
    f=d.prepare(fixture());f['production']=f.market
    f['ll_gain']=0.
    r=d.market_correct_null(f,reps=100)
    assert r['expected_gain_if_market_correct']==0.
    assert r['standard_error']==0.
    assert r['null_interval95']==[0.,0.]
    g=d.prepare(fixture());a=d.market_correct_null(g,reps=100,seed=7);b=d.market_correct_null(g,reps=100,seed=7)
    assert a==b and a['expected_gain_if_market_correct']<0.
