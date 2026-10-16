import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import market_residual_models as r


def history():
    return pd.DataFrame({'game_id':['a','b','c'],'season':[2022]*3,'week':[1,2,3],
                         'home':['SF']*3,'away':['SEA']*3,'margin':[7.,10.,999.],
                         'margin_line':[3.,3.,0.],'total':[50.,48.,999.],'total_line':[45.]*3})


def test_residual_perspective_decay_and_shrinkage():
    f=history();h=r.residual_profile(f,2022,3,'SF',4,4);a=r.residual_profile(f,2022,3,'SEA',4,4)
    assert h[0]==pytest.approx(-a[0]) and h[1]==pytest.approx(a[1])
    w=np.array([2**(-1/4),1.]);assert h[0]==pytest.approx(w@np.array([4.,7.])/(w.sum()+4))
    assert h[5]==2 and h[3]<=2
    more=r.residual_profile(f,2022,3,'SF',4,12);assert abs(more[0])<abs(h[0])
    assert r.residual_profile(f,2022,3,'GB',4,4)[:4]==(0.,0.,0.,0.)


def test_own_future_outcomes_do_not_enter_history():
    f=history();a=r.residual_profile(f,2022,3,'SF',16,4)
    f.loc[f.week==3,['margin','total']]=-99999.
    assert a==r.residual_profile(f,2022,3,'SF',16,4)
    with pytest.raises(ValueError):r.residual_profile(f,2022,3,'SF',0,4)


def test_price_features_ignore_box_stats_and_outcomes():
    f=pd.DataFrame({'margin_line':[3.],'total_line':[45.5],'q':[.6],
                    'market_cover_q':[.51],'market_over_q':[.49],'margin':[10.],'total':[50.],
                    'arbitrary_box_stat':[999.]})
    a=r.price_features(f);b=r.price_features(f.assign(margin=-100,total=200,arbitrary_box_stat=-999))
    cols=list(dict.fromkeys(sum(r.PRICE_NAMES.values(),[])))
    assert np.array_equal(a[cols],b[cols])


def test_annual_selection_uses_only_earlier_outcomes():
    f=pd.DataFrame({'season':[2020,2021,2022],'margin':[0.,0.,0.],'total':[45.,45.,45.]})
    for target in r.t.TARGETS:
        for arm in ('market_relationships',*r.RULES):
            f[f'{target}__{arm}__mean']=f[target];f[f'{target}__{arm}__sd']=10.
    a,choices=r.select_forecasts(f)
    f.loc[f.season==2022,['margin','total']]=9999.
    b,altered=r.select_forecasts(f)
    assert [x for x in choices if x['season']==2022]==[x for x in altered if x['season']==2022]
    assert np.array_equal(a.loc[a.season==2022,'margin__selected__mean'],b.loc[b.season==2022,'margin__selected__mean'])


def test_protected_output():
    with pytest.raises(ValueError):r.run(r.ROOT/'data'/'research')
