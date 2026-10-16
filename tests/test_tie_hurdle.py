import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import joint_market_residuals as j
import tie_hurdle as t


def test_hurdle_is_coherent_and_preserves_all_conditional_shapes():
    p=j.smooth_joint([25.,21.],[81.,100.,12.])
    q=t.tie_hurdle(p,.003)
    assert q.sum()==pytest.approx(1)
    assert np.trace(q)==pytest.approx(.003)
    assert (q>=0).all()
    diagonal=np.eye(len(p),dtype=bool)
    assert np.allclose(q[diagonal]/q[diagonal].sum(),p[diagonal]/p[diagonal].sum())
    assert np.allclose(q[~diagonal]/q[~diagonal].sum(),p[~diagonal]/p[~diagonal].sum())
    assert np.tril(q,-1).sum()/(1-np.trace(q))==pytest.approx(np.tril(p,-1).sum()/(1-np.trace(p)))
    m=j.marginals(q)
    assert m['total']@j.TOTAL_SUPPORT==pytest.approx(m['home']@j.SCORE_SUPPORT+m['away']@j.SCORE_SUPPORT)
    assert m['margin']@j.MOV_SUPPORT==pytest.approx(m['home']@j.SCORE_SUPPORT-m['away']@j.SCORE_SUPPORT)
    assert np.allclose(t.tie_hurdle(p.T,.003),q.T)


@pytest.mark.parametrize('rate',[0,1,-.1,np.nan])
def test_bad_rates_fail(rate):
    with pytest.raises(ValueError):t.tie_hurdle(np.ones((2,2))/4,rate)


@pytest.mark.parametrize('p',[np.eye(2)/2,np.array([[0,.5],[.5,0]]),np.ones((2,2)),np.array([[.5,-.1],[.1,.5]])])
def test_degenerate_support_and_invalid_pmfs_fail(p):
    with pytest.raises(ValueError):t.tie_hurdle(p,.01)


def test_tie_fit_excludes_whole_current_week_and_future_and_six_season_window():
    f=pd.DataFrame(dict(season=[2017,2018,2023,2023,2024],week=[1,1,1,2,1],
        home_score=[0.,0.,20.,30.,40.],away_score=[0.,0.,10.,30.,40.],
        spread_line=[3.]*5,total_line=[45.]*5))
    rate,a=t.fit_tie_rate(f,2023,2)
    assert rate==pytest.approx(1.5/3)
    assert a['training_games']==2
    assert (a['training_max_season'],a['training_max_week'])==(2023,1)
    f.loc[(f.season>2023)|((f.season==2023)&(f.week>=2)),['home_score','away_score']]=[80.,0.]
    assert t.fit_tie_rate(f,2023,2)==(rate,a)
    f.loc[(f.season==2023)&(f.week==1),'away_score']=20
    assert t.fit_tie_rate(f,2023,2)[0]>rate
    with pytest.raises(ValueError):t.fit_tie_rate(f,2013,1)


def test_joint_gain_equals_tie_bernoulli_gain_for_both_outcomes():
    p=j.smooth_joint([25.,21.],[81.,100.,12.]);q=t.tie_hurdle(p,.004)
    for h,a in [(24,21),(21,21)]:
        y=float(h==a)
        actual=np.log(q[h,a]/p[h,a])
        expected=j.binary_loss(y,np.trace(p))-j.binary_loss(y,.004)
        assert actual==pytest.approx(expected)
