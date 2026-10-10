import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import context_shrinkage as s


def test_support_counts_and_concentration():
    x=np.array([[1.,1.,0.],[1.,1.,0.],[1.,10.,0.],[0.,0.,0.]])
    w=np.ones(4)/4
    assert np.allclose(s.effective_support(x,w,'active'),[3.,3.,0.])
    info=s.effective_support(x,w,'information')
    assert info[0]==3 and 1 < info[1] < 1.1 and info[2]==0
    assert np.allclose(info,s.effective_support(x*7,w,'information'))
    assert np.allclose(info,s.effective_support(-x,w,'information'))


def test_decay_and_invalid_inputs():
    x=np.ones((3,1)); w=np.array([1.,.5,.25])
    assert s.effective_support(x,w,'active')[0]==pytest.approx(w.sum()**2/(w*w).sum())
    with pytest.raises(ValueError):s.effective_support(x,[-1,1,1],'active')
    with pytest.raises(ValueError):s.effective_support(x,w,'unknown')
    with pytest.raises(ValueError):s.effective_support(x*np.nan,w,'active')


def fixture():
    rng=np.random.default_rng(7); n=220
    names=s.m.feature_names(s.q.BASE_FAMILY)+s.CONTEXTS
    f=pd.DataFrame(rng.normal(0,.2,(n,len(names))),columns=names)
    f['site']=1.;f['season']=2022;f['week']=np.tile(np.arange(1,12),20)
    f['ready']=True;f['q']=.5;f['home won']=rng.integers(0,2,n).astype(float)
    for col in s.CONTEXTS[1:]:f[col]=0.
    f.loc[:4,'pass_1sd_pn']=1.;f.loc[:4,'home won']=0.
    return f


def test_zero_strength_reproduces_production_and_penalties():
    f=fixture();a=s.fit(f,2023,1);b=s.m.fit_composite(f,s.m.LEGACY_PRODUCT_RECIPE,2023,1)
    assert np.allclose(s.predict(f,a),s.m.apply_fit(f,b),atol=1e-10,rtol=0)
    shr=s.fit(f,2023,1,'active',30.)
    assert shr['penalty_multiplier']['pass_product']==1.
    assert shr['penalty_multiplier']['pass_1sd_pn']>6.
    i=a['names'].index('pass_1sd_pn')
    assert abs(shr['beta'][i])<abs(a['beta'][i])
    # All-zero contexts stay zero and predictions remain finite.
    j=a['names'].index('pass_1sd_pp')
    assert shr['beta'][j]==0 and np.isfinite(s.predict(f,shr)).all()


def test_prior_week_and_strength_guards():
    f=fixture()
    with pytest.raises(ValueError,match='current/future'):s.fit(f,2022,11)
    with pytest.raises(ValueError,match='strength'):s.fit(f,2023,1,strength=-1)
    with pytest.raises(ValueError,match='Insufficient'):s.fit(f.iloc[:10],2023,1)


def test_protected_output_guard(tmp_path):
    with pytest.raises(ValueError,match='production outputs'):
        s.run(tmp_path,s.ROOT/'data'/'shrinkage')


def test_frozen_real_week_refit_reproduces_archive():
    import json
    root=s.ROOT/'research'/'shrinkage_results'
    f=pd.read_csv(root/'frozen_training_features.csv.gz')
    earlier=f[s.m.before(f,2026,5)]
    fitted=s.fit(earlier,2026,5)
    snapshots=[json.loads(x) for x in (root/'archived_current_inputs.jsonl').read_text().splitlines()]
    r=next(x for x in snapshots if x['game_id']=='2026_05_SF_SEA')
    row=pd.DataFrame([{**r['model_inputs'],'q':r['market_no_vig_wp']}])
    assert s.predict(row,fitted)[0]==pytest.approx(r['model_wp'],abs=1e-9)
    assert fitted['support']['pass_1sd_pn']==pytest.approx(43.14426871130312)
