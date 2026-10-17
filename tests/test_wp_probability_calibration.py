import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from research import wp_probability_calibration as c

ROOT=Path(__file__).resolve().parents[1]


def test_pooled_adjacent_violators_known_solution_and_endpoint_clipping():
    fit=c.IsotonicRegression().fit([.1,.2,.3,.4],[0.,1.,0.,1.],np.ones(4))
    np.testing.assert_allclose(fit.predict([.0,.1,.2,.25,.3,.4,.9]),[.005,.005,.5,.5,.5,.995,.995])
    with pytest.raises(ValueError):c.IsotonicRegression().fit([.1],[1.],[0.])


def test_bin_frequency_fixture_and_neutral_forecast():
    p=np.array([.52,.53,.56,.57,.62,.63,.67,.68,.72,.73,.77,.78,.85,.86])
    f=c.fit(p,np.tile([0.,1.],7))
    assert f['counts']==[2]*7 and f['rates']==[.5]*7
    assert c.predict([.5],f)[0][0]==.5


def test_inverse_favorite_penalty_matches_independent_archived_v116():
    d=c.get_data(c.OUT/'input.csv')
    archived=pd.read_csv(ROOT/'research/favorite_penalty_results/inputs.csv')
    archived=archived[archived.basis.str.startswith(('2021-25 rebuilt','2026 weeks 1-5'))]
    z=d.merge(archived[['game_id','model_wp','q']],on='game_id',suffixes=('_current','_reference'),validate='one_to_one')
    assert len(z)==1433
    np.testing.assert_allclose(z.v116,z.model_wp_reference,atol=1e-9,rtol=0)
    np.testing.assert_allclose(c.forward(d.v116,d.market),d.v118,atol=1e-12,rtol=0)


def test_years_are_immune_to_evaluation_or_future_labels():
    d=c.get_data(c.OUT/'input.csv');base,_,_=c.walk(d)
    for year in [2023,2024,2025,2026]:
        poison=d.copy();mask=poison.season>=year;poison.loc[mask,'y']=1-poison.loc[mask,'y']
        altered,_,_=c.walk(poison)
        np.testing.assert_array_equal(base.loc[base.season==year,c.METHODS],altered.loc[altered.season==year,c.METHODS])


def test_saved_probability_results_and_independent_proper_scores():
    r=json.loads((c.OUT/'results.json').read_text());d=pd.read_csv(c.OUT/'per_game.csv')
    assert r['primary']['v118']['n']==815 and r['diagnostic2026']['v118']['n']==78
    assert r['nomination_candidates']==[]
    for label,g in [('primary',d[d.season<=2025]),('diagnostic2026',d[d.season==2026])]:
        for method in c.METHODS:
            p=g[method]; y=g.y
            ll=-(y*np.log(p)+(1-y)*np.log(1-p)).mean()
            assert np.isclose(ll,r[label][method]['log_loss'],atol=1e-12)
            assert np.isclose(((p-y)**2).mean(),r[label][method]['brier'],atol=1e-12)


def test_monotone_maps_preserve_orientation_and_probability_bounds():
    _,_,objects=c.walk(c.get_data(c.OUT/'input.csv'))
    x=np.linspace(.001,.999,1001)
    for f in objects.values():
        _,p=c.predict(x,f);_,mirror=c.predict(1-x,f)
        assert np.all(np.diff(p)>=-1e-12)
        assert p.min()>=.005-1e-12 and p.max()<=.995+1e-12
        np.testing.assert_allclose(p+mirror,1,atol=1e-11)
