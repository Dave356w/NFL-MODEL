import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import market_median_map as mm


def frame(seed=0, n=600, total=None, low_scale=1., high_scale=1.):
    rng = np.random.default_rng(seed)
    line = rng.choice([-1, 1], n)*rng.choice([1., 2.5, 3., 4.5, 6.5, 7., 8.5, 10., 13.5], n)
    tot = np.full(n, total) if total is not None else np.round(rng.uniform(36, 52, n)*2)/2
    scale = np.where(tot <= 44, low_scale, high_scale)
    res = np.round(line*scale+rng.normal(0, 4, n))
    return pd.DataFrame({'season': rng.choice([2022, 2023, 2024], n), 'week': rng.integers(1, 19, n),
                         'spread_line': line, 'total_line': tot, 'result': res})


def test_band_medians_signed_toward_favorite_and_pickem_excluded():
    d = pd.DataFrame({'season': 2022, 'week': 1, 'total_line': 44.,
                      'spread_line': [2.]*31+[-5.]*31+[8.]*31+[-12.]*31+[0.]*5,
                      'result': [3.]*31+[-1.]*31+[0.]*31+[-20.]*31+[30.]*5})
    r = mm.fit(d, False)
    assert r['base_magnitudes'] == [3., 1., 0., 20.] and r['fit_games'] == 124   # away favorite: -(-1) = +1; tie = 0
    assert mm.apply([3., -4.5, 0.], [44.]*3, r).tolist() == [1., -1., 0.]


def test_constant_totals_make_B_equal_A():
    d = frame(total=44.)
    a, b = mm.fit(d, False), mm.fit(d, True)
    assert [m[0] for m in b['magnitudes']] == a['base_magnitudes'] and all(f[1] for f in b['fallback'])
    assert np.allclose(mm.apply(d.spread_line, d.total_line, a), mm.apply(d.spread_line, d.total_line, b))


def test_total_dependent_margins_split_and_equal_split_counts_low():
    d = frame(low_scale=.6, high_scale=1.4)
    b = mm.fit(d, True); mags = np.array(b['magnitudes'])
    assert (mags[1:, 0] < mags[1:, 1]).all() and b['total_cuts'][0] == pytest.approx(44., abs=1.)
    assert np.searchsorted(b['total_cuts'], [44., 44.5], side='left').tolist() == [0, 1]


def test_sparse_cell_falls_back_and_thin_band_raises():
    d = frame(low_scale=.6, high_scale=1.4)
    big_high = (d.spread_line.abs() >= 10) & (d.total_line > mm.fit(d, True)['total_cuts'][0])
    d2 = d.drop(d[big_high].index[5:])
    b = mm.fit(d2, True)
    assert b['fallback'][3][1] and b['magnitudes'][3][1] == b['base_magnitudes'][3]
    with pytest.raises(ValueError, match='below'):
        mm.fit(d[d.spread_line.abs() < 10], False)


def test_selection_uses_production_pick_and_tie_rules():
    d = pd.DataFrame({'spread_line': [3., 3., 0.], 'result': [3., 7., 1.]})
    pred = np.array([3., 4., 0.])                     # zero edge, edge, pick'em zero
    res, _ = mm.fb.grade(d, pred)
    assert res.tolist() == ['P', 'W', 'S']             # zero edge takes the favorite (push at 3)
    res2, _ = mm.fb.grade(d, pred, favorite_on_tie=False)
    assert res2.tolist() == ['S', 'W', 'S']


def test_baselines_pick_the_named_side():
    line = np.array([3., -7., 0.])
    b = mm.baselines(line)
    assert mm.fb.pick(b['Always favorite'], line).tolist() == [1., -1., 0.]
    assert mm.fb.pick(b['Always underdog'], line).tolist() == [-1., 1., 0.]
    assert mm.fb.pick(b['Always home'], line).tolist() == [1., 1., 1.]


def test_record_verdicts_and_pushes_in_denominator():
    r = mm.record(np.array(['W']*600+['L']*400+['P']*50), np.array([1/1.1]*600+[-1.]*400+[0.]*50))
    assert r['n'] == 1050 and r['roi'] == pytest.approx((600/1.1-400)/1050) and r['ats_verdict'] == 'beats -110'
    r = mm.record(np.array(['W', 'L']*50), np.array([1/1.1, -1.]*50))
    assert r['ats_verdict'] == 'unresolved'


def test_frozen_inputs_fit_only_on_2022_24():
    g = pd.read_csv(mm.GAMES)
    train = g[g.season.between(*mm.FIT)]
    a = mm.fit(train, False)
    assert a['fit_seasons'] == [2022, 2023, 2024] and a['fit_games'] == int((train.spread_line != 0).sum())
    g2 = g.copy(); g2.loc[g2.season >= 2025, 'result'] += 40
    assert mm.fit(g2[g2.season.between(*mm.FIT)], False) == a


def test_research_rejects_protected_outputs():
    for p in (mm.ROOT/'data'/'x', mm.ROOT/'public'):
        with pytest.raises(ValueError, match='Protected'): mm.guard(p)
