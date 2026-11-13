import numpy as np
import pandas as pd
import pytest
from research import qb_minus2_grade as q


def frame():
    return pd.DataFrame(dict(fixed_band_spread=[4.,4.,4.,4.],spread_line=[3.,3.,3.,3.],result=[4.,2.,3.,5.]))


def test_home_away_sign_and_double_backup_cancel():
    d=frame();before=d.copy(deep=True)
    out=q.apply_penalty(d,[1,0,1,0],[0,1,1,0])
    np.testing.assert_array_equal(out,[2.,6.,4.,4.])
    pd.testing.assert_frame_equal(d,before)
    unknown=q.apply_penalty(d,[np.nan,0,0,0],0)
    assert np.isnan(unknown.iloc[0])
    with pytest.raises(ValueError):q.apply_penalty(d,[.5,0,0,0],0)
    with pytest.raises(ValueError):q.apply_penalty(d,[np.inf,0,0,0],0)


def test_zero_edge_takes_favorite_but_pickem_skips():
    d=pd.DataFrame(dict(spread_line=[3.,-3.,0.],result=[4.,-4.,0.]))
    g=q.grade(d,[3.,-3.,0.])
    assert g.selected_side.tolist()==['home','away','skip']
    assert g.grade.tolist()==['W','W','S']
    assert q.summary(g)['WLP']=='2-0-0'
    assert q.summary(g)['skips']==1


def test_common_minus110_paired_results_and_pushes():
    d=frame();original=q.grade(d,d.fixed_band_spread)
    adjusted=q.grade(d,q.apply_penalty(d,1,0))
    assert original.grade.tolist()==['W','L','P','W']
    assert adjusted.grade.tolist()==['L','W','P','L']
    s=q.paired_summary(original,adjusted)
    assert s['n']==4 and s['priced_n']==4 and s['flips']==4
    assert s['units_gain']==pytest.approx(-1.-1/1.1)
    assert q.summary(original)['roi']==pytest.approx((2/1.1-1)/4)


def test_flipped_side_uses_its_own_price_and_never_original_price():
    d=frame().iloc[:2].copy();d['ats_home_odds']=[-120.,np.nan];d['ats_away_odds']=[105.,np.nan]
    d['ats_price']=[-120.,-120.]  # original home-side price must not leak into an away selection
    g=q.grade(d,[2.,2.],price_mode='side_specific')
    assert g.selected_side.tolist()==['away','away']
    assert g.grade.tolist()==['L','W']
    assert g.price.iloc[0]==105.
    assert g.units.iloc[0]==-1.
    assert np.isnan(g.units.iloc[1])
    assert g.price_basis.iloc[1]=='unavailable_side_price'
    # Missing prices are excluded for losses too, avoiding asymmetric return selection.
    d.loc[d.index[0],'ats_away_odds']=np.nan
    assert np.isnan(q.grade(d,[2.,2.],price_mode='side_specific').units.iloc[0])


def test_pending_and_unknown_projections_do_not_become_losses_or_bets():
    d=pd.DataFrame(dict(spread_line=[3.,3.],result=[np.nan,5.]))
    g=q.grade(d,[4.,np.nan])
    assert g.grade.tolist()==['','']
    assert q.summary(g)['n']==0
    assert q.summary(g)['units'] is None
    assert q.paired_summary(g,g)['n']==0
