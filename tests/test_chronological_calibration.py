import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import chronological_calibration as c


def fixture():
    rng=np.random.default_rng(8);n=200
    q=rng.uniform(.45,.75,n);p=np.clip(q+rng.normal(0,.04,n),.01,.99)
    return pd.DataFrame({'season':[2022]*n,'market':q,'production':p,'home won':rng.binomial(1,p).astype(float)})


def test_calibration_cutoff_and_close_application():
    f=fixture();fit=c.fit_calibration(f,2023,True);pred=c.apply_calibration(f,fit)
    close=np.maximum(f.market,1-f.market)<.6
    assert np.array_equal(pred[~close],f.loc[~close,'production'])
    assert ((pred>0)&(pred<1)).all()
    assert fit['training_games']==int(close.sum()) and fit['max_source_season']==2022
    with pytest.raises(ValueError,match='evaluation season'):c.fit_calibration(f,2022)
    with pytest.raises(ValueError,match='Insufficient'):c.fit_calibration(f.iloc[:10],2023)


def test_scale_selection_and_tie_rule():
    f=fixture();a=c.select_scale(f,2023);assert a['chosen_scale'] in c.SCALES
    f['production']=f.market
    assert c.select_scale(f,2023)['chosen_scale']==1.
    with pytest.raises(ValueError,match='evaluation season'):c.select_scale(f,2022)


def test_no_change_at_original_calibration():
    f=fixture();fit={'intercept':0.,'correction_scale':1.,'close_only':False}
    assert np.allclose(c.apply_calibration(f,fit),f.production,atol=1e-15)
