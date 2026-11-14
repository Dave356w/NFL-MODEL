"""Two independently fitted pressure regressors; explicitly no interaction."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

RESEARCH=Path(__file__).parents[1]/'research'
if str(RESEARCH) not in sys.path:sys.path.insert(0,str(RESEARCH))
import additive_pressure as q


def history():
    return pd.DataFrame([dict(game_id=f'{season}_{week}',season=season,week=week,team=t,
                              times_pressured=n,opportunities=40,generated=d,def_opportunities=40)
                         for season,week in [(2023,1),(2024,1),(2024,2),(2024,3)]
                         for t,n,d in [('A',12,4),('B',4,12)]])


def test_additive_profiles_keep_both_original_rates_and_remove_interaction():
    f=pd.DataFrame([dict(game_id='target',season=2024,week=3,home='A',away='B')]);g=history()
    a=q.profiles(f,g,2);original=q.p.profiles(f,g,2)
    assert 'pressure_matchup' not in a
    assert q.EXTRA==['pressure_allowed_diff','pressure_generated_diff']
    np.testing.assert_array_equal(a[q.EXTRA],original[q.EXTRA])
    assert a.pressure_allowed_diff.iloc[0]>0 and a.pressure_generated_diff.iloc[0]<0
    f['home']='B';f['away']='A';b=q.profiles(f,g,2)
    np.testing.assert_allclose(a[q.EXTRA],-b[q.EXTRA],atol=1e-12)


def test_separate_coefficients_learn_distinct_effects_without_interaction():
    rng=np.random.default_rng(123)
    f=pd.DataFrame(rng.normal(size=(300,2)),columns=q.EXTRA);f['prediction']=0.
    f['result']=-2*f.pressure_allowed_diff+3*f.pressure_generated_diff
    f['pressure_matchup']=9999.
    fitted=q.p.fit(f,'prediction',True,q.EXTRA)
    assert len(fitted['coef'])==3 and fitted['columns']==q.EXTRA
    assert fitted['coef'][1]<0 and fitted['coef'][2]>0
    pred=q.p.predict(f,'prediction',fitted)
    f['pressure_matchup']=np.nan
    np.testing.assert_array_equal(pred,q.p.predict(f,'prediction',fitted))
    f['pressure_generated_diff']+=1
    assert (q.p.predict(f,'prediction',fitted)>pred).all()


def test_both_pressure_profiles_ignore_recent_and_future_sources():
    f=pd.DataFrame([dict(game_id='target',season=2024,week=3,home='A',away='B',result=0.)]);g=history()
    a=q.profiles(f,g,2)
    g.loc[~q.p.eligible(g,2024,3,2),['times_pressured','generated']]=999
    f['result']=100.
    b=q.profiles(f,g,2)
    np.testing.assert_array_equal(a[q.EXTRA],b[q.EXTRA])
