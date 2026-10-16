"""Market-only baselines separate point prediction, probabilities and price."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import check_grad

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import spread_signal_separation as s


def history():
    rng=np.random.default_rng(7);n=600;spread=rng.normal(0,6,n)
    margin=1+1.4*spread
    return pd.DataFrame(dict(game_id=[f'g{i}' for i in range(n)],season=np.where(np.arange(n)%2,2021,2022),
        week=5,spread_line=spread,total_line=rng.normal(44,5,n),home_score=24+margin/2,away_score=24-margin/2))


@pytest.mark.parametrize('with_total',[False,True])
def test_market_logistic_gradient(with_total):
    h=history().iloc[:50];x=s.design(h.spread_line,h.total_line,with_total)
    y=(h.home_score>h.away_score).to_numpy(float);weights=np.linspace(.1,1,len(h));beta=np.ones(x.shape[1])*.3
    assert check_grad(lambda z:s.objective(z,x,y,weights)[0],lambda z:s.objective(z,x,y,weights)[1],beta)<1e-5


def test_prior_only_benchmarks_recover_known_margin_signal_and_win_direction():
    h=history();t=dict(season=2023,week=5,spread_line=7.,total_line=44.)
    fitted=s.fit(h,t);p=s.forecast(t,fitted)
    assert fitted['line_coefficients']==pytest.approx([1.,1.4*7])
    assert p['margin_market_spread']==7
    assert p['margin_market_linear']==pytest.approx(10.8)
    assert p['win_market_spread']>.9
    reverse=s.forecast(t|{'spread_line':-7},fitted)
    assert reverse['win_market_spread']<.1


def test_current_future_and_old_window_training_rejected():
    h=history();t=dict(season=2023,week=5,spread_line=3.,total_line=44.)
    for poisoned in [h.assign(season=2023,week=5),h.assign(season=2024),h.assign(season=2017)]:
        with pytest.raises(ValueError,match='earlier'):s.fit(poisoned,t)
    fitted=s.fit(h,t)
    assert s.forecast(t,fitted)==s.forecast(t|{'home_score':999,'away_score':0},fitted)
    with pytest.raises(ValueError,match='Future'):
        s.forecast(t,fitted|{'training_max_season':2023,'training_max_week':5})


def test_price_cost_decomposition_and_push_denominator():
    r=s.price_decomposition(270,278,12)
    assert r['bets']==560 and r['even_money_units']==-8
    assert r['price_cost']==pytest.approx(270/11)
    assert r['units']==pytest.approx(-32.54545454545455)
    assert r['fair_null_roi']==pytest.approx(-548/560/22)
    empty=s.price_decomposition(0,0,0)
    assert empty['units']==0 and np.isnan(empty['roi'])
    assert s.price_decomposition(0,0,5)['units']==0
    with pytest.raises(ValueError):s.price_decomposition(-1,2,0)


def test_exact_probability_endpoint_losses_and_tie_exclusion():
    y=np.array([1.,0.,np.nan]);p=np.array([0.,1.,.5]);ll=s.loss(y,p)
    assert np.isinf(ll[:2]).all() and np.isnan(ll[2])
    assert s.loss(np.array([1.,0.]),np.array([.5,.5])).mean()==pytest.approx(np.log(2))
