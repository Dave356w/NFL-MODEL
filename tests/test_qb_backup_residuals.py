import numpy as np
import pandas as pd
from research import qb_backup_residuals as q


def synthetic():
    rows=[]
    for year in (2021,2022,2023,2024,2025):
        for w,(h,a) in enumerate([(0,0),(1,0),(0,1),(1,1)],1):
            rows.append(dict(season=year,week=w,raw_margin=2.,result=2.+.4-3*(h-a),
                             home_replacement=float(h),away_replacement=float(a),backup_difference=float(h-a)))
    return pd.DataFrame(rows)


def test_oriented_penalty_and_no_double_counting():
    d=synthetic()
    np.testing.assert_allclose(q.ols(d),[.4,-3.])
    # Games with two replacements have zero relative-team adjustment.
    both=d[d.home_replacement.eq(1)&d.away_replacement.eq(1)]
    assert np.allclose(both.result-both.raw_margin,.4)
    ci=q.coefficient_ci(d)
    np.testing.assert_allclose(ci,[[.4,-3.],[.4,-3.]],atol=1e-10)


def test_future_outcomes_cannot_change_prior_season_fit():
    d=synthetic();p,f=q.walk_forward(d)
    contaminated=d.copy();contaminated.loc[contaminated.season>=2023,'result']+=10000
    cp,cf=q.walk_forward(contaminated)
    assert f[0]==cf[0]
    np.testing.assert_array_equal(p.loc[p.season.eq(2023),'adjusted_margin'],cp.loc[cp.season.eq(2023),'adjusted_margin'])
    assert (p.train_max_season<p.season).all()


def test_intercept_only_control_fits_its_own_intercept():
    d=synthetic()
    # Unequal flag prevalence makes the joint intercept differ from mean residual.
    d=pd.concat([d,d[d.home_replacement.eq(1)&d.away_replacement.eq(0)]],ignore_index=True)
    p,f=q.walk_forward(d)
    tr=d[d.season<2023]
    assert np.isclose(f[0]['intercept_only'],(tr.result-tr.raw_margin).mean())
    assert not np.isclose(f[0]['intercept'],f[0]['intercept_only'])


def test_incumbent_uses_prior_starts_and_reports_missing_roster():
    s=pd.DataFrame([dict(season=2022,week=w,result=1.,home_team='H',away_team='A',home_qb_id=p,away_qb_id='a')
                    for w,p in [(1,'starter'),(2,'starter'),(3,'backup'),(4,'backup')]])
    r=pd.DataFrame([dict(season=2022,week=2,team='H',gsis_id='starter',position='QB')])
    assert q.incumbent(s,r,'H',2022,3)=='starter'
    r2=r.iloc[:0]
    assert q.incumbent(s,r2,'H',2022,3)=='__unknown_roster__'
    assert q.incumbent(s,r,'H',2022,2) is None
