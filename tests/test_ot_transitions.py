import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import distribution_ablations as d
import joint_market_residuals as j
import tie_hurdle as t


def test_exact_atoms_and_stratum_invariance():
    p=np.zeros((15,15));p[4,4]=.3;p[10,2]=.42;p[2,10]=.28
    q,a=d.ot_transport(p,.1)
    assert a['transported_mass']==pytest.approx(.2)
    assert np.trace(q)==pytest.approx(.1)
    assert q[10,2]==pytest.approx(.42)
    assert q[2,10]==pytest.approx(.28)
    for delta in [2,3,6]:
        assert q[4+delta,4]==pytest.approx(.2*.6/3)
        assert q[4,4+delta]==pytest.approx(.2*.4/3)
    assert q.sum()==pytest.approx(1)
    assert np.tril(q,-1).sum()/(1-np.trace(q))==pytest.approx(.6)


def test_whole_joint_positive_coherent_and_side_symmetric():
    p=j.smooth_joint([26.,20.],[81.,100.,8.])
    q,a=d.ot_transport(p,.003)
    assert np.all(q>0) and q.sum()==pytest.approx(1)
    assert np.allclose(d.ot_transport(p.T,.003)[0],q.T)
    m=j.marginals(q)
    assert m['total']@j.TOTAL_SUPPORT==pytest.approx(m['home']@j.SCORE_SUPPORT+m['away']@j.SCORE_SUPPORT)
    assert m['margin']@j.MOV_SUPPORT==pytest.approx(m['home']@j.SCORE_SUPPORT-m['away']@j.SCORE_SUPPORT)


def test_no_excess_is_explicit_identity_to_hurdle():
    p=j.smooth_joint([26.,20.],[81.,100.,8.])
    q,a=d.ot_transport(p,.2)
    assert np.array_equal(q,t.tie_hurdle(p,.2))
    assert a['no_excess'] and a['transported_mass']==0


def test_cap_mass_is_accounted_without_clipping_or_negative_score():
    p=np.zeros((11,11));p[10,10]=.1;p[8,8]=.2;p[6,1]=.35;p[1,6]=.35
    q,a=d.ot_transport(p,.1)
    assert a['excess_tie_mass']==pytest.approx(.2)
    assert a['untransportable_mass']==pytest.approx(.2/3)
    assert a['near_cap_renormalized_mass']==pytest.approx(.4/3)
    assert a['transported_mass']+a['untransportable_mass']==pytest.approx(.2)
    assert q[10,8]==pytest.approx((.4/3)/2)
    assert q[8,10]==pytest.approx((.4/3)/2)
    assert q.sum()==pytest.approx(1) and np.trace(q)==pytest.approx(.1)


@pytest.mark.parametrize('p',[np.ones((4,3)),np.eye(3)/3,np.ones((3,3)),np.array([[.6,-.1],[.1,.4]])])
def test_invalid_inputs_fail(p):
    with pytest.raises(ValueError):d.ot_transport(p,.01)


def test_labels_not_read_by_transform_and_prior_week_rate_unchanged():
    f=pd.DataFrame(dict(season=[2024,2024,2024,2025],week=[1,2,2,1],
        home_score=[21.,20.,30.,40.],away_score=[21.,10.,20.,40.],spread_line=[3.]*4,total_line=[45.]*4))
    p=j.smooth_joint([24.,21.],[81.,81.,0.]);rate,a=t.fit_tie_rate(f,2024,2)
    first=d.ot_transport(p,rate)[0]
    f.loc[f.index>0,['home_score','away_score']]=[70.,0.]
    changed,b=t.fit_tie_rate(f,2024,2)
    assert (rate,a)==(changed,b)
    assert np.array_equal(first,d.ot_transport(p,changed)[0])
