import numpy as np
import pandas as pd
from research import qb_first_start_fade as f
from test_qb_backup_residuals import synthetic


def history():
    return pd.DataFrame([dict(team='T',season=2023,week=w,actual_id=p)
                         for w,p in [(1,'a'),(2,'a'),(3,'b'),(4,'b'),(6,'a'),(7,'b')]])


def test_stint_count_uses_prior_actual_games_with_byes_and_resets():
    h=history()
    assert f.prior_stint_start(h,'T',2023,3,'b')==1
    assert f.prior_stint_start(h,'T',2023,4,'b')==2
    assert f.prior_stint_start(h,'T',2023,6,'b')==3  # bye in week 5
    assert f.prior_stint_start(h,'T',2023,7,'b')==1  # another QB started week 6
    assert f.prior_stint_start(h,'T',2024,1,'b')==1
    assert np.isnan(f.prior_stint_start(h.assign(actual_id=None),'T',2023,3,'b'))


def test_fixed_fade_and_no_double_team_effect():
    d=pd.DataFrame([dict(season=2023,week=w,home='T',away='X',home_projected_id='b',away_projected_id='x',
                         home_replacement=1.,away_replacement=0.) for w in [3,4,6]])
    out=f.with_exposures(d,history())
    np.testing.assert_allclose(out.home_fade,[1.,2**-.5,.5])
    assert out.away_fade.eq(0).all()
    assert out.fade_difference.eq(out.home_fade).all()


def test_future_test_outcomes_do_not_change_earlier_fade_fit():
    d=synthetic();d['home_fade']=d.home_replacement;d['away_fade']=d.away_replacement
    d['fade_difference']=d.home_fade-d.away_fade
    p,folds=f.walk_forward(d)
    changed=d.copy();changed.loc[changed.season>=2023,'result']+=5000
    later,lf=f.walk_forward(changed)
    assert folds[0]==lf[0]
    np.testing.assert_array_equal(p.loc[p.season.eq(2023),'fade_margin'],later.loc[later.season.eq(2023),'fade_margin'])
    assert (p.train_max_season<p.season).all()
