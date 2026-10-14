import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logit, ndtr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import disjoint_features as df_


def test_feature_sets_are_disjoint_from_production():
    assert not set(df_.DISJOINT) & set(df_.PRODUCTION)
    assert 'site' in df_.PRODUCTION and 'd__avail__qb_delta' in df_.PRODUCTION
    assert df_.ARMS['production_plus_disjoint'] == df_.PRODUCTION+df_.DISJOINT


def frame():
    return pd.DataFrame({'q': [.7, .5, .3, .6], 'spread_line': [7., 0., -3., np.nan], 'total_line': [55., 45., 35., np.nan],
                         'div_game': [1, 0, 1, 0], 'home_rest': [13, 7, 4, 7], 'away_rest': [4, 7, 13, 6]})


def test_market_structure_definitions():
    d = df_.market_structure(frame())
    lq = logit(np.array([.7, .5, .3, .6]))
    assert np.isclose(d.ml_spread_gap[0], lq[0]-logit(ndtr(7/12.37)))
    assert np.isclose(d.ml_spread_gap[1], 0.)                # pick'em on both markets
    assert np.isnan(d.ml_spread_gap[3])                      # missing spread stays missing (fit treats as 0)
    assert np.allclose(d.total_x_market[:3], [1.*lq[0], 0., -1.*lq[2]])
    assert np.allclose(d.div_x_market, [lq[0], 0., lq[2], 0.])
    assert d.rest_diff.tolist() == [7., 0., -7., 1.]          # clipped to +/-7


def test_gap_sign_means_moneyline_more_bullish_than_spread():
    d = df_.market_structure(pd.DataFrame({'q': [.75, .55], 'spread_line': [3., 3.], 'total_line': 45., 'div_game': 0,
                                           'home_rest': 7, 'away_rest': 7}))
    assert d.ml_spread_gap[0] > 0 > d.ml_spread_gap[1]


def test_augment_merges_one_row_per_game():
    games = pd.DataFrame({'game_id': ['2017_01_A_B'], 'q': [.6], 'spread_line': [2.5]})
    edges = pd.DataFrame({'game_id': ['2017_01_A_B'], **{n: [.1] for n in df_.RATINGS}})
    ctx = pd.DataFrame({'game_id': ['2017_01_A_B'], 'div_game': [1], 'home_rest': [7], 'away_rest': [7]})
    a = df_.augment(games, edges, ctx)
    assert len(a) == 1 and all(c in a for c in df_.DISJOINT)
    assert a.rest_diff[0] == 0 and a.pass_edge[0] == .1
