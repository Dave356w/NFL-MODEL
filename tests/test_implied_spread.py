import numpy as np
from scipy.special import ndtr

import nfl_model as m


def test_implied_spread_inverts_the_market_comparator():
    lines = np.array([-14., -3., 0., 2.5, 7.])
    assert np.allclose(m.implied_spread(ndtr(lines / m.MARKET_SIGMA)), lines)


def test_implied_spread_sign_clip_and_missing():
    out = m.implied_spread([.6, .4, 1., 0., np.nan, None])
    assert out[0] > 0 > out[1] and np.isclose(out[0], -out[1])  # positive = home favored
    assert np.isclose(out[2], -out[3]) and 30 < out[2] < 33     # clipped at .995, not infinite
    assert np.isnan(out[4]) and np.isnan(out[5])
