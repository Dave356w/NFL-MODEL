import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import margin_total_models as t


def fixture():
    rng=np.random.default_rng(71);n=220
    f=pd.DataFrame({'season':2021,'week':np.tile(np.arange(1,12),20),'ready':True,'site':1.,'x':rng.normal(size=n),'margin_line':rng.normal(0,5,n),'total_line':45.})
    f['margin']=f.margin_line+3*f.x+rng.normal(0,10,n);f['total']=45+2*f.x+rng.normal(0,12,n)
    return f


def test_integer_bin_and_push_probabilities():
    assert t.normal_bin(0.,0.,10.)>0
    q,p=t.event_prob(np.array([3.,3.]),np.array([12.,12.]),np.array([3.,3.5]))
    assert q[0]==pytest.approx(.5);assert p[0]>0 and p[1]==0
    assert q[1]<.5
    a,pa=t.event_prob(np.array([4.]),np.array([10.]),np.array([3.]))
    b,pb=t.event_prob(np.array([-4.]),np.array([10.]),np.array([-3.]))
    assert a[0]==pytest.approx(1-b[0]);assert pa[0]==pytest.approx(pb[0])
    assert np.isfinite(-np.log(t.normal_bin(400.,0.,10.)))
    with pytest.raises(ValueError):t.normal_bin(0.,0.,-1.)


def test_no_vig_requires_both_valid_prices():
    assert t.price_probability([-110],[-110])[0]==pytest.approx(.5)
    assert t.price_probability([-200],[150])[0]>0.6
    assert np.isnan(t.price_probability([np.nan],[-110])[0])
    assert np.isnan(t.price_probability([0],[-110])[0])


def test_mean_fits_are_pregame_and_market_benchmark_is_exact():
    f=fixture();test=f.head(2).copy();test['season']=2022;test['week']=1
    pred,_=t.fit_mean(f,test,'margin',['site','x'],'market_centered')
    assert np.array_equal(pred,test.margin_line)
    mean,_=t.fit_mean(f,test,'margin',['site','x'],'corrected')
    altered=test.copy();altered['margin']=9999;altered['total']=-9999
    other,_=t.fit_mean(f,altered,'margin',['site','x'],'corrected')
    assert np.array_equal(mean,other)
    test2=test.copy();test2['margin_line']+=2
    shifted,_=t.fit_mean(f,test2,'margin',['site','x'],'corrected')
    assert np.allclose(shifted,mean+2)
    standalone,_=t.fit_mean(f,test,'margin',['site','x'],'standalone')
    standalone2,_=t.fit_mean(f,test2,'margin',['site','x'],'standalone')
    assert np.array_equal(standalone,standalone2)
    with pytest.raises(ValueError):t.fit_mean(f,test.assign(season=2021,week=5),'margin',['x'],'corrected')


def test_dispersion_uses_prior_forecast_residuals_and_rejects_future():
    f=fixture();f['margin__corrected__mean']=f.margin+7
    sd,a=t.dispersion(f,f,'margin','corrected',2022,1)
    assert sd==pytest.approx(7.) and a['dispersion_source']=='prior_weekly_forecast_errors'
    with pytest.raises(ValueError):t.dispersion(f,f,'margin','corrected',2021,5)
    fallback,a=t.dispersion(pd.DataFrame(),f,'margin','corrected',2022,1)
    assert fallback>3 and a['dispersion_source']=='prior_market_residual_fallback'


def test_interaction_symmetry_and_neutral_homefield():
    f=pd.DataFrame({'margin__corrected__mean':[6.,-6.],'margin_line':[3.,-3.],
                    'total__corrected__mean':[50.,50.],'total_line':[45.,45.],'site':[0.,0.],'pass_product':[2.,-2.]})
    a=t.stack_features(f)
    for name in ('margin_edge','margin_total_interaction','pass_total_interaction'):
        assert a[name].iloc[0]==pytest.approx(-a[name].iloc[1])
    assert (a.total_homefield==0).all()
    assert (a.total_context==.5).all()


def test_matched_stack_reproduces_production_fit():
    from test_context_shrinkage import fixture as original
    f=original();f['stage1_through_season']=2021;f['stage1_through_week']=18;test=f.head(3).copy();test['season']=2023;test['week']=1
    pp,_=t.stack_fit(f,test,'production_matched');fit=t.s.fit(f,2023,1)
    assert np.allclose(pp,t.s.predict(test,fit),atol=1e-10,rtol=0)
    with pytest.raises(ValueError):t.stack_fit(f,test.assign(season=2022,week=5),'production_matched')


def test_protected_output():
    with pytest.raises(ValueError):t.run(t.ROOT/'data'/'x')


def test_oof_guard_rejects_in_sample_and_missing_metadata():
    f=pd.DataFrame({'season':[2022,2022],'week':[1,2],
                    'stage1_through_season':[2021,2022],'stage1_through_week':[18,1]})
    t.validate_oof(f)
    with pytest.raises(ValueError):t.validate_oof(f.assign(stage1_through_season=2022,stage1_through_week=2))
    with pytest.raises(ValueError):t.validate_oof(f.drop(columns='stage1_through_week'))


def test_market_total_ablation_does_not_consume_total_forecast():
    f=pd.DataFrame({'margin__corrected__mean':[6.],'margin_line':[3.],
                    'total__corrected__mean':[50.],'total_line':[45.5],'site':[1.],'pass_product':[2.]})
    a=t.stack_features(f);b=t.stack_features(f.assign(total__corrected__mean=60.))
    for name in t.EXTRAS['pass_market_total']:assert a[name].iloc[0]==b[name].iloc[0]
    assert a.pass_total_interaction.iloc[0]!=b.pass_total_interaction.iloc[0]
