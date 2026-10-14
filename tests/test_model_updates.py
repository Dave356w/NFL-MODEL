import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy.special import logit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import model_updates as mu


def imp():
    # Rows: inputs; columns: Test 38 importance on each basis (negative = better without it).
    return pd.DataFrame({'2015-16': [-1., -1., 1., -1.], '2017-22': [-1., 1., -1., -1.], '2023-25': [-1., -1., -1., 1.]},
                        index=['a', 'b', 'c', 'site'])


def test_prune_lobo_never_uses_the_evaluation_basis():
    t = imp()
    assert mu.prune_set('2015-16', t) == ['a', 'c']      # negative on 2017-22 and 2023-25
    assert mu.prune_set('2017-22', t) == ['a', 'b']      # negative on 2015-16 and 2023-25
    assert mu.prune_set('2023-25', t) == ['a', 'site']   # negative on 2015-16 and 2017-22
    assert mu.prune_set('native', t) == ['a']            # outside the three: negative on all three
    # Changing the evaluation basis's own column never changes its prune set.
    t2 = t.assign(**{'2015-16': -t['2015-16']})
    assert mu.prune_set('2015-16', t2) == mu.prune_set('2015-16', t)


def test_arm_specs_change_one_thing():
    base = mu.arm_spec('production', '2015-16', imp())
    assert base == (dict(mu.BASE), [], 1., mu.m.FIT_HALF_LIFE_SEASONS)
    r, z, k, hl = mu.arm_spec('ridge_0.3', '2015-16', imp())
    assert (r['ridge'], r['interaction_ridge'], z, k) == (.3, .3, [], 1.)
    assert mu.arm_spec('shrink_0.5', '2015-16', imp())[2] == .5
    assert mu.arm_spec('no_site', '2015-16', imp())[1] == ['site']
    assert mu.arm_spec('prune_8', '2015-16', imp())[1] == ['a']  # all-three negatives, site excluded
    assert mu.arm_spec('half_life_4', '2015-16', imp())[3] == 4.
    with pytest.raises(ValueError, match='Unknown arm'): mu.arm_spec('bigger', '2015-16', imp())


def test_fit_half_life_is_restored():
    before = mu.m.FIT_HALF_LIFE_SEASONS
    with pytest.raises(RuntimeError):
        with mu.fit_half_life(4.):
            assert mu.m.FIT_HALF_LIFE_SEASONS == 4.
            raise RuntimeError
    assert mu.m.FIT_HALF_LIFE_SEASONS == before


def test_shrink_halves_the_departure_and_keeps_its_side_of_the_market():
    q = np.array([.6, .4, .5]); p = np.array([.8, .55, .3])
    s = mu.shrink(p, q, .5)
    assert np.allclose(logit(s)-logit(q), .5*(logit(p)-logit(q)))
    assert ((s-q)*(p-q) > 0).all() and (np.abs(s-q) < np.abs(p-q)).all()
    assert np.array_equal(mu.shrink(p, q, 1.), p)


def rows(gains, lo):
    return pd.DataFrame({'basis': list(mu.BASES), 'context': 'all', 'll_gain_x1000': gains, 'lo_x1000': lo})


def test_verdict_rule():
    assert mu.verdict(rows([1., 2., .5], [-1., .1, -2.])) == 'supported for a forward shadow test'
    assert mu.verdict(rows([1., 2., .5], [-1., -.1, -2.])) == 'unresolved'
    assert mu.verdict(rows([1., 2., -.5], [.5, .5, -2.])) == 'unresolved'
    assert mu.verdict(rows([-1., 2., 0.], [-3., .5, -2.])) == 'not supported'
