from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'research'))
import injury_efficiency as s

def test_no_fresh_lineup_change_adds_no_intercept_or_context_correction():
 b=np.ones((19,5))*999;scale=np.ones(18);baseline=np.array([30.,2.,30.,2.,50.])
 np.testing.assert_array_equal(s.efficiency_adjustment(np.zeros(12),b,scale,baseline),np.zeros(5))

def test_only_injury_component_propagates_and_rate_bounds_hold():
 b=np.zeros((19,5));b[1]=[-2,1,0,0,0];b[0]=999;b[13:]=999
 fresh=np.zeros(12);fresh[0]=.5;base=np.array([30.,2.,30.,2.,50.])
 np.testing.assert_allclose(s.efficiency_adjustment(fresh,b,np.ones(18),base),[-1,.5,0,0,0])
 b[1]=[-999,999,0,0,-999]
 a=base+s.efficiency_adjustment(fresh,b,np.ones(18),base)
 assert (a[:4]>=0).all() and (a[:4]<=100).all() and a[4]>=0

def test_efficiency_change_moves_frozen_probability_without_direct_points():
 fit={'names':['fd'],'beta':[.1],'scale':[2.],'recipe':{'favorite_penalty':1.}}
 assert s.propagate_probability({'fd':0},fit,.6)==pytest.approx(.6)
 assert s.propagate_probability({'fd':2},fit,.6)>.6

def test_ridge_recovers_planted_efficiency_injury_effect():
 rng=np.random.default_rng(3);x=rng.normal(size=(500,18));y=np.zeros((500,5));y[:,0]=-3*x[:,0]
 b,mu,sd=s.ridge_fit(x,y)
 assert b[1,0]<0
 assert abs(b[1,0]/sd[0]+3)<.1
