import numpy as np
import pandas as pd
from research.qb_minus2_2026 import overlay,metric


def test_unknown_lineup_keeps_the_saved_decision_and_is_not_called_known():
    d=pd.DataFrame(dict(fixed_band_spread=[3.,3.,3.,3.],home_chart=[1.,0.,1.,np.nan],away_chart=[0.,1.,1.,0.],result=[-9.,8.,1.,99.]))
    original=d.copy(deep=True)
    adjusted,known=overlay(d,'chart')
    np.testing.assert_allclose(adjusted,[1.,5.,3.,3.])
    assert known.tolist()==[True,True,True,False]
    pd.testing.assert_frame_equal(d,original)
    # Counterfactual assignment must not use eventual game scores.
    changed=d.copy();changed.result=-changed.result
    same,k=overlay(changed,'chart')
    pd.testing.assert_series_equal(same,adjusted)
    pd.testing.assert_series_equal(k,known)


def test_margin_errors_use_actual_minus_projection_on_same_rows():
    d=pd.DataFrame({'result':[7.,-3.]})
    out=metric(d,pd.Series([5.,-4.]))
    assert out==dict(n=2,mean_home_residual=1.5,MAE=1.5,MSE=2.5)
