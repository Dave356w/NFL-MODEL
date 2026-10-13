import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import margin_likelihood as ml
from test_context_shrinkage import fixture

FLAT = np.ones(ml.SUPPORT.max()+1)


def test_pmf_normalizes_and_win_probability_is_monotone_and_symmetric():
    w = FLAT.copy(); w[3] = w[7] = 2.
    pr = ml.pmf(np.array([-4., 0., 6.]), 13., w)
    assert np.allclose(pr.sum(1), 1.)
    p = ml.win_prob(np.linspace(-20, 20, 41), 13., w)
    assert np.all(np.diff(p) > 0)
    assert ml.win_prob(np.array([0.]), 13., w)[0] == pytest.approx(.5)


def test_key_multipliers_move_mass_onto_key_numbers():
    flat, keyed = FLAT.copy(), FLAT.copy(); keyed[3] = 3.
    p_flat, p_key = ml.pmf(np.array([2.]), 13., flat)[0], ml.pmf(np.array([2.]), 13., keyed)[0]
    at3 = ml.SUPPORT == 3
    assert p_key[at3][0] > 2.5*p_flat[at3][0]
    assert p_key[ml.SUPPORT == 4][0] < p_flat[ml.SUPPORT == 4][0]


def test_market_location_reproduces_q():
    w = FLAT.copy(); w[3] = 2.5; w[0] = .1
    q = np.array([.2, .5, .63, .9])
    assert np.allclose(ml.win_prob(ml.market_location(q, 13., w), 13., w), q, atol=1e-8)


def test_key_weights_detect_excess_and_deficit():
    rows = pd.DataFrame({'spread_line': 0., 'result': [3]*60+[-3]*60+list(range(-20, 21))*4})
    w = ml.key_weights(rows, 13.)
    assert w[3] > 1.5 and w[3] > w[4]
    none = pd.DataFrame({'spread_line': 0., 'result': [1, -1, 2, -2, 5, -5, 9, -9]*30})
    assert ml.key_weights(none, 13.)[3] < 1.


def test_shape_and_fit_use_only_earlier_data():
    f = fixture(); f['result'] = np.where(f['home won'] == 1, 3, -3); f['spread_line'] = 0.
    with pytest.raises(ValueError): ml.season_shape(f, 2022)       # all rows are 2022: none strictly earlier
    sigma, w = ml.season_shape(f, 2023)
    assert sigma == pytest.approx(3.) and np.isfinite(w).all()
    with pytest.raises(ValueError): ml.fit_margin(f, 2022, 5, 13., FLAT)


def margin_fixture(signal):
    f = fixture(); rng = np.random.default_rng(3)
    x = f[ml.FEATURES[1]].to_numpy()
    margin = np.round(signal*40*x+rng.normal(0, 13, len(f))).astype(int)
    margin[margin == 0] = 1
    f['result'] = margin; f['home won'] = (margin > 0).astype(float); f['spread_line'] = 0.; f['q'] = .5
    return f


def test_no_signal_keeps_market_and_signal_is_learned():
    flat = margin_fixture(0.)
    fitted = ml.fit_margin(flat, 2023, 1, 13., FLAT)
    assert np.max(np.abs(fitted['beta'])) < .2
    zero = dict(fitted, beta=[0.]*len(fitted['beta']))
    assert np.allclose(ml.apply_margin(flat.iloc[:5], zero, FLAT), .5)
    strong = ml.fit_margin(margin_fixture(1.), 2023, 1, 13., FLAT)
    assert strong['beta'][1] > .2 and strong['beta'][1] > abs(fitted['beta'][1])


def test_verdict_follows_the_preregistered_rules():
    st = lambda l, lo, u: {'L_ll_gain_vs_v116': {'mean': l, 'interval': [lo, 1.]}, 'U_units_vs_favorite_change': {'units': u}}
    assert ml.verdict(st(.001, .0001, 0.)) == 'supported'
    assert ml.verdict(st(.001, -.001, 2.)) == 'favored, unresolved'
    assert ml.verdict(st(0., .0, 5.)) == 'falsified'
    assert ml.verdict(st(.002, .001, -.01)) == 'falsified'
