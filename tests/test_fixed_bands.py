import numpy as np
import pandas as pd
import fixed_bands as f


def history():
    spread = np.tile([1., 4., 8., 12.], 80)
    return pd.DataFrame({'season': np.repeat([2021, 2022], 160),
                         'home won': 1., 'model_spread': spread,
                         'spread_line': spread + .5, 'result': spread + 2})


def test_training_excludes_target_and_future_seasons_and_ties():
    d = history()
    rule = f.fit(d, 2023)
    assert rule and rule['training_max_season'] == 2022
    poison = d.assign(season=2023, result=-100., **{'home won': 0.})
    tied = d.assign(result=0., **{'home won': .5})
    assert f.fit(pd.concat([d, poison, poison.assign(season=2024), tied]), 2023) == rule
    assert f.fit(d, 2022) is None
    assert f.fit(d.iloc[:20], 2023) is None


def test_signed_boundaries_missing_and_pickem():
    rule = dict(cuts=[3, 7, 10], magnitudes=[4, 5, 7, 13])
    x = f.apply([0., 2.99, 3., -7., 10., np.nan], rule)
    np.testing.assert_allclose(x, [0, 4, 5, -7, 13, np.nan], equal_nan=True)
    assert np.isnan(f.apply([1.], None)).all()


def test_grading_skip_before_push_tied_final_and_pending():
    d = pd.DataFrame({'spread_line': [3., 3., -3., 0., 3., np.nan],
                      'result': [3., 3., 0., 0., np.nan, 7.]})
    r, u = f.grade(d, [3., 4., -2., 1., 4., 4.])
    assert list(r) == ['S', 'P', 'W', 'P', '', '']
    np.testing.assert_allclose(u, [0, 0, 1/1.1, 0, np.nan, np.nan], equal_nan=True)


def test_summary_excludes_unavailable_and_skipped_stakes():
    d = pd.DataFrame({'season': [2023]*4, 'fixed_band_spread': [4., 3., 4., np.nan],
                      'spread_line': [3.]*4, 'result': [7., 7., 3., -7.],
                      'original_ats_result': ['W', 'L', 'P', 'L'],
                      'fixed_band_ats_result': ['W', 'S', 'P', '']})
    r = f.summary(d).query("season == 'All' and method == 'Fixed bands'").iloc[0]
    assert r.games == 3 and r.bets == 2 and r.skips == 1
    assert np.isclose(r.roi, (1/1.1)/2)
