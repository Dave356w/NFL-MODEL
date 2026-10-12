import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import monte_carlo as mc


def test_joint_score_projection():
    margin,total=mc.score_projection(np.array([3.,-7.,100.,0.]),np.array([45.,41.,10.,0.]))
    assert np.all(total>=abs(margin))
    assert np.all((total+margin)%2==0)
    assert margin[-1]==total[-1]==0


def test_tilt_conditional_prices_and_pushes():
    margins=np.array([-7.,-3.,0.,3.,7.]);totals=np.array([30.,40.,45.,50.,60.])
    row=pd.Series({'q':.6,'margin_line':3.,'total_line':45.,'market_cover_q':.5,'market_over_q':.6})
    # Independent Cartesian support provides feasible conditional constraints.
    margins=np.repeat(margins,5);totals=np.tile(totals,5)
    weights,error=mc.tilt(np.ones(25),mc.event_features(margins,totals,row))
    assert error<1e-6
    assert mc.conditional_probability(margins,0,weights)[0]==pytest.approx(.6,abs=1e-6)
    assert mc.conditional_probability(margins,3,weights)[0]==pytest.approx(.5,abs=1e-6)
    assert mc.conditional_probability(totals,45,weights)[0]==pytest.approx(.6,abs=1e-6)
    assert mc.conditional_probability(margins,0,weights)[1]>0


def test_tilt_rejects_infeasible_and_invalid_support():
    with pytest.raises(ValueError):mc.tilt(np.array([1.,0.]),np.array([[1.],[-1.]]))
    with pytest.raises(ValueError):mc.tilt(np.ones(3),np.ones((3,1)))
    with pytest.raises(ValueError):mc.conditional_probability(np.zeros(3),0,np.ones(3)/3)


def test_crps_matches_pairwise_definition():
    x=np.array([-3.,0.,7.]);w=np.array([.2,.3,.5]);y=2.
    expected=w@abs(x-y)-.5*np.sum(w[:,None]*w[None,:]*abs(x[:,None]-x[None,:]))
    assert mc.empirical_crps(x,w,y)==pytest.approx(expected)
    assert mc.empirical_crps(np.array([2.]),np.array([1.]),2.)==0.


def test_future_records_excluded_and_protected_paths():
    frame=pd.DataFrame({'season':[2023,2024,2024,2025],'week':[18,1,2,1],'value':[1,2,3,4]})
    earlier=mc.prior(frame,2024,2)
    assert earlier.value.tolist()==[1,2]
    frame.loc[2:,'value']=1000000
    pd.testing.assert_frame_equal(earlier,mc.prior(frame,2024,2))
    for path in [mc.ROOT/'data',mc.ROOT/'data/sub',mc.ROOT/'public/sub']:
        with pytest.raises(ValueError):mc.protected(path)
    assert mc.protected(mc.OUT)==mc.OUT.resolve()


def test_pass_hinges_recomputed_and_orientation_reversed():
    z=np.array([[2.,-2.,.5,.5],[.5,.5,2.,-2.]])
    terms=mc.pass_terms(z)
    assert np.allclose(terms[0],-terms[1])
    assert terms[0,2]==1.  # positive offense times negative defense
    assert terms[0,0]==-4.25


def test_quantile_boundary():
    assert np.array_equal(mc.quantile(np.array([0,1,2]),np.array([.2,.3,.5]),[0.,.5,1.]),[0,1,2])


def test_whole_game_profile_bootstrap_and_recentering():
    records=[]
    for i in range(4):
        r={'game_id':str(i),'season':2023,'week':i+1,'team':'A','opponent':'B','_game_index':i,
           'max_lead':float(i),'max_deficit':float(4-i)}
        for c in mc.m.COUNTS:
            r[c]=float(i+1);r['opp_'+c]=float(4-i)
        records.append(r)
    h=pd.DataFrame(records)
    multipliers=np.ones((3,4));multipliers[2]=[4.,1.,1.,1.]
    profiles,n=mc.profiles(h,'A',2024,multipliers)
    assert n==4
    assert profiles[(8.,'for','plays_per_game')][0]==profiles[(8.,'for','plays_per_game')][1]
    assert profiles[(8.,'for','plays_per_game')][2]!=profiles[(8.,'for','plays_per_game')][0]
    assert profiles[(8.,'for','net_pass_yards_per_pass_play')][0]==pytest.approx(1.)


def test_cluster_bootstrap_coefficients_are_reproducible():
    from test_context_shrinkage import fixture
    train=fixture();fit=mc.s.fit(train,2023,1)
    a=mc.bootstrap_coefficients(train,fit,2023,1,3,np.random.default_rng(9))
    b=mc.bootstrap_coefficients(train,fit,2023,1,3,np.random.default_rng(9))
    assert np.array_equal(a,b)
    assert np.isfinite(a).all() and not np.allclose(a[0],a[1])
