"""Behavior checks for the isolated pressure study, not the live production model."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location('pressure_margin', Path(__file__).parents[1]/'research/pressure_margin.py')
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def history():
    return pd.DataFrame([
        dict(game_id=f'{season}_{week}',season=season,week=week,team=team,
             times_pressured=pressure,opportunities=40,generated=16-pressure,def_opportunities=40)
        for season,week in [(2023,1),(2023,2),(2023,3),(2024,1),(2024,2)]
        for team,pressure in [('A',6+week),('B',10-week)]])


def fixture_forecast(home='A',away='B'):
    return pd.DataFrame([dict(game_id='target',season=2024,week=3,home=home,away=away,
                              result=3.,prediction=2.,spread_line=3.)])


def test_profiles_reject_current_future_and_recent_unavailable_weeks():
    h=history();f=fixture_forecast()
    before=p.profiles(f,h,2)
    future=~p.eligible(h,2024,3,2)
    h.loc[future,'times_pressured']=40
    h.loc[future,'generated']=0
    after=p.profiles(f,h,2)
    pd.testing.assert_frame_equal(before,after)
    assert before.source_max_season.iloc[0]==2024
    assert before.source_max_week.iloc[0]==1
    # A target result must not influence any pressure feature.
    f['result']=-99
    np.testing.assert_allclose(before[p.EXTRA],p.profiles(f,h,2)[p.EXTRA])


def test_team_swap_reverses_all_three_pressure_features():
    a=p.profiles(fixture_forecast(),history(),2)
    b=p.profiles(fixture_forecast('B','A'),history(),2)
    np.testing.assert_allclose(a[p.EXTRA],-b[p.EXTRA],atol=1e-12)


def test_missing_team_history_is_an_error():
    with pytest.raises(ValueError,match='No pressure history'):
        p.profiles(fixture_forecast(),history().query('team=="A"'),2)


def test_cover_probabilities_treat_integer_push_symmetrically():
    assert p.cover_probability(3,12,3)==pytest.approx(.5)
    assert p.cover_probability(3.5,12,3.5)==pytest.approx(.5)
    assert p.cover_probability(6,12,3)>.5
    assert p.cover_probability(-6,12,-3)<.5
    assert p.cover_probability(6,12,3)+p.cover_probability(-6,12,-3)==pytest.approx(1)


def test_pushes_are_refunded_and_excluded_from_cover_scoring():
    f=pd.DataFrame(dict(result=[7.,0.,3.],spread_line=[3.,3.,3.],mean=[5.,5.,5.],p_home_cover=[.6,.6,.99]))
    m=p.score(f)
    assert (m['wins'],m['losses'],m['pushes'],m['cover_n'])==(1,1,1,2)
    assert m['units']==pytest.approx(100/110-1)
    assert m['log_loss']==pytest.approx(-.5*(np.log(.6)+np.log(.4)))


def test_zero_edge_favorite_and_pickem_skip():
    np.testing.assert_array_equal(p.picked_side(np.array([3.,-3.,0.]),np.array([3.,-3.,0.])),[1,-1,0])


def test_fit_learns_planted_pressure_signal_and_predictions_ignore_labels():
    rng=np.random.default_rng(10)
    f=pd.DataFrame(rng.normal(size=(300,3)),columns=p.EXTRA)
    f['prediction']=0.
    f['result']=1+2*f[p.EXTRA[0]]-f[p.EXTRA[1]]
    fitted=p.fit(f,'prediction',True)
    assert fitted['coef'][1]>0 and fitted['coef'][2]<0
    a=p.predict(f,'prediction',fitted)
    f['result']=999
    np.testing.assert_array_equal(a,p.predict(f,'prediction',fitted))


def test_nonfinite_training_features_are_rejected():
    f=pd.DataFrame(np.ones((10,3)),columns=p.EXTRA)
    f['prediction']=0.;f['result']=1.
    f.loc[0,p.EXTRA[0]]=np.nan
    with pytest.raises(ValueError,match='nonfinite'):
        p.fit(f,'prediction',True)
