"""The ablation must fit exactly one pressure signal and use prior sources only."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RESEARCH=Path(__file__).parents[1]/'research'
if str(RESEARCH) not in sys.path:sys.path.insert(0,str(RESEARCH))
import offensive_pressure_only as q


def history():
    return pd.DataFrame([dict(game_id=f'{season}_{week}',season=season,week=week,team=t,
                              times_pressured=n,opportunities=40)
                         for season,week in [(2023,1),(2024,1),(2024,2),(2024,3)]
                         for t,n in [('A',12),('B',4)]])


def target():
    return pd.DataFrame([dict(game_id='target',season=2024,week=3,home='A',away='B',result=0.)])


def test_offensive_profiles_need_no_defensive_columns_and_reverse_on_swap():
    g=history();f=target();a=q.profiles(f,g,2)
    assert q.EXTRA==['pressure_allowed_diff']
    assert not any(c in a for c in ['pressure_generated_diff','pressure_matchup','generated','def_opportunities'])
    assert a.pressure_allowed_diff.iloc[0]>0
    f['home']='B';f['away']='A'
    b=q.profiles(f,g,2)
    np.testing.assert_allclose(a[q.EXTRA],-b[q.EXTRA],atol=1e-12)


def test_recent_future_sources_and_target_label_cannot_change_feature():
    g=history();f=target();a=q.profiles(f,g,2)
    g.loc[~q.p.eligible(g,2024,3,2),'times_pressured']=999;f['result']=-100.
    b=q.profiles(f,g,2)
    np.testing.assert_array_equal(a[q.EXTRA],b[q.EXTRA])
    assert a.source_max_week.iloc[0]==1


def test_fit_uses_one_coefficient_and_ignores_defensive_inputs():
    f=pd.DataFrame({'pressure_allowed_diff':np.linspace(-2,2,100),'prediction':0.})
    f['result']=-3*f.pressure_allowed_diff
    f['pressure_generated_diff']=0.;f['pressure_matchup']=0.
    a=q.p.fit(f,'prediction',True,q.EXTRA)
    assert a['columns']==q.EXTRA and len(a['coef'])==2 and a['coef'][1]<0
    pred=q.p.predict(f,'prediction',a)
    f['pressure_generated_diff']=np.nan;f['pressure_matchup']=9999.
    b=q.p.fit(f,'prediction',True,q.EXTRA)
    np.testing.assert_array_equal(a['coef'],b['coef'])
    np.testing.assert_array_equal(pred,q.p.predict(f,'prediction',b))


def test_missing_team_and_invalid_opportunities_rejected():
    g=history();f=target()
    with pytest.raises(ValueError,match='No offensive pressure history'):
        q.profiles(f,g[g.team.eq('A')],2)
    g.loc[g.team.eq('A'),'opportunities']=0
    with pytest.raises(ValueError,match='Nonpositive'):q.profiles(f,g,2)
