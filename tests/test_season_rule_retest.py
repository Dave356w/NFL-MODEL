"""Every-season gates keep bad/missing years and reject floating-point ties."""
import numpy as np
import pandas as pd
import pytest

from research import season_rule_retest as r
from research import verify_season_rule_retest as independent


def annual_fixture(probability=.6,win_margin=1.,candidate_margin=2.,unit_epsilon=0.):
    games=pd.DataFrame({'game_id':[str(y)for y in r.SEASONS],'season':r.SEASONS,
        'result':win_margin,'spread_line':3.5,'home won':1.})
    metadata=pd.DataFrame([
        dict(id='market:moneyline',anchor='moneyline',candidate='market',gamma=0.,is_control=True,own_anchor_control_id='market:moneyline'),
        dict(id='market:spread_total',anchor='spread_total',candidate='market',gamma=0.,is_control=True,own_anchor_control_id='market:spread_total'),
        dict(id='candidate',anchor='moneyline',candidate='single:site',gamma=.5,is_control=False,own_anchor_control_id='market:moneyline')])
    probabilities=np.tile([.5,.5,probability],(6,1))
    margins=np.tile([5.,5.,candidate_margin],(6,1))
    side,units=independent.settlement(margins,np.full((6,1),3.5),np.full((6,1),win_margin))
    units[:,2]+=unit_epsilon
    result,_,_=r.summarize(games,metadata,probabilities,
        {p:margins.copy()for p in r.PATHS},{p:side.copy()for p in r.PATHS},{p:units.copy()for p in r.PATHS})
    return result[result.variant_id.eq('candidate')].copy()


def test_valid_six_season_candidate_passes_both_independent_hurdles():
    annual=annual_fixture();gate=r.gates(annual)
    assert gate.all_seasons_probability_pass.all()
    assert gate.all_seasons_ats_pass.all()and gate.all_seasons_joint_pass.all()


@pytest.mark.parametrize('mutation',['drop_bad_year','replace_year_with_duplicate','retain_bad_year'])
def test_missing_duplicate_or_bad_season_cannot_pass(mutation):
    annual=annual_fixture()
    annual.loc[annual.season.eq(2021),['probability_pass','ats_pass']]=False
    if mutation=='drop_bad_year':annual=annual[annual.season.ne(2021)]
    elif mutation=='replace_year_with_duplicate':
        annual=annual[annual.season.ne(2021)]
        annual=pd.concat([annual,annual[annual.season.eq(2022)]],ignore_index=True)
    gate=r.gates(annual)
    assert not gate.all_seasons_probability_pass.any()
    assert not gate.all_seasons_ats_pass.any()and not gate.all_seasons_joint_pass.any()


def test_unavailable_early_median_years_do_not_shrink_the_six_year_gate():
    annual=annual_fixture()
    missing=annual.path.ne('raw')&annual.season.le(2022)
    annual.loc[missing,'full_coverage']=False
    annual.loc[missing,['units','roi','roi_gain_own','roi_gain_favorite']]=np.nan
    annual.loc[missing,'bets']=0;annual.loc[missing,'ats_pass']=False
    gates=r.gates(annual).set_index('path')
    assert gates.loc['raw','all_seasons_joint_pass']
    assert not gates.loc['own_median','all_seasons_joint_pass']
    assert gates.loc['own_median','covered_seasons']==4
    assert gates.loc['own_median','pass_2023_2026_components']


def test_tiny_positive_probability_gain_does_not_pass_a_rounding_tie():
    annual=annual_fixture(probability=.5+1e-14)
    assert (annual.log_loss_gain_ml>0).all()
    assert not annual.probability_pass.any()


def test_identical_positive_ats_records_and_numerical_dust_do_not_beat_favorite():
    annual=annual_fixture(win_margin=7.,candidate_margin=5.,unit_epsilon=1e-14)
    assert annual.ats_positive_roi.all()
    assert not annual.ats_beats_own.any()
    assert not annual.ats_beats_favorite.any()and not annual.ats_pass.any()


def test_independent_settlement_keeps_pushes_skips_and_away_favorite_distinct():
    side,units=independent.settlement(np.array([3.,-7.,0.,4.,2.,np.nan]),
        np.array([3.,-7.,0.,3.,3.,3.]),np.array([4.,-3.,0.,3.,1.,7.]))
    np.testing.assert_allclose(side,[1.,-1.,0.,1.,-1.,np.nan],equal_nan=True)
    np.testing.assert_allclose(units,[1/1.1,-1.,0.,0.,1/1.1,np.nan],equal_nan=True)
    selected=np.isfinite(side)&(side!=0)
    assert selected.sum()==4  # the push is staked; the skip and missing line are not


def test_independent_medians_require_prior_seasons_and_ignore_future_poison():
    margin=np.tile([1.,4.,8.,12.],80)
    games=pd.DataFrame({'season':np.repeat([2021,2022],160),'result':margin+2})
    expected=independent.median_prediction(games,margin,np.array([1.,4.,8.,12.]),2023)
    np.testing.assert_array_equal(expected,[3.,6.,10.,14.])
    poison=pd.DataFrame({'season':[2023]*320,'result':[-1000.]*320})
    result=independent.median_prediction(pd.concat([games,poison],ignore_index=True),np.r_[margin,margin],np.array([1.,4.,8.,12.]),2023)
    np.testing.assert_array_equal(result,expected)
    assert np.isnan(independent.median_prediction(games,margin,np.array([1.]),2022)).all()
