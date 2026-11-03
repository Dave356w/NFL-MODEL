import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import total_median_map as t


def history(seed=0, seasons=(2021, 2022, 2023), n=400, total=None, low_scale=1., high_scale=1.):
    """Synthetic rows: margins toward the pick scale with the band, optionally by total half."""
    rng = np.random.default_rng(seed); rows = []
    for s in seasons:
        ms = rng.choice([-1, 1], n)*rng.uniform(.5, 14, n)
        tot = np.full(n, total) if total is not None else rng.choice([38., 50.], n)
        scale = np.where(tot <= 44, low_scale, high_scale)
        res = np.round(ms*scale+rng.normal(0, 3, n))
        rows.append(pd.DataFrame({'game_id': [f'{s}_{i}' for i in range(n)], 'season': s, 'week': rng.integers(1, 19, n),
                                  'model_spread': ms, 'result': res, 'total_line': tot, 'spread_line': np.round(ms*2)/2}))
    return pd.concat(rows, ignore_index=True)


def test_constant_totals_reproduce_production_exactly():
    h = history(total=44.)
    base, r2 = t.fb.fit(h, 2023), t.fit_conditioned(h, 2023, 2)
    assert [row[0] for row in r2['magnitudes']] == base['magnitudes']        # every row sits in the low half
    assert all(f for row in r2['fallback'] for f in row[1:])                 # the empty high half falls back
    x = h[h.season == 2023]
    assert np.allclose(t.apply_conditioned(x.model_spread, x.total_line, r2), t.fb.apply(x.model_spread, base))


def test_total_dependent_margins_give_different_halves():
    h = history(low_scale=.5, high_scale=1.5)
    r2 = t.fit_conditioned(h, 2023, 2)
    mags = np.array(r2['magnitudes'])
    assert (mags[:, 0] < mags[:, 1]).all() and not np.array(r2['fallback']).any()
    assert r2['total_cuts'] == [pytest.approx(np.median(h[h.season < 2023].total_line))]


def test_fit_uses_only_earlier_seasons():
    h = history(low_scale=.5, high_scale=1.5)
    a = t.fit_conditioned(h, 2023, 2)
    h2 = h.copy(); k = h2.season == 2023
    h2.loc[k, 'result'] += 50; h2.loc[k, 'total_line'] += 20
    assert t.fit_conditioned(h2, 2023, 2) == a
    h3 = h.copy(); h3.loc[h3.season == 2022, 'result'] *= 2
    assert t.fit_conditioned(h3, 2023, 2)['magnitudes'] != a['magnitudes']


def test_split_rule_and_sparse_cell_fallback():
    assert t.total_group([40., 44., 44.5], [44.]).tolist() == [0, 0, 1]      # equal to the split counts as low
    assert t.total_group([40., 46., 52.], [43., 48.]).tolist() == [0, 1, 2]
    h = history(low_scale=.5, high_scale=1.5)
    big = (h.model_spread.abs() >= 10) & (h.total_line > 44) & (h.season < 2023)
    h = h.drop(h[big].index[5:])                                             # leave 5 rows in that cell
    r2 = t.fit_conditioned(h, 2023, 2); base = t.fb.fit(h, 2023)
    assert r2['fallback'][3][1] and r2['magnitudes'][3][1] == base['magnitudes'][3]
    assert not r2['fallback'][3][0]


def test_no_production_rule_means_no_conditioned_rule():
    h = history(seasons=(2022, 2023))                                         # one training season only
    assert t.fb.fit(h, 2023) is None and t.fit_conditioned(h, 2023, 2) is None
    assert np.isnan(t.apply_conditioned([3.], [44.], None)).all()


def test_baseline_predictions_pick_favorite_home_and_skip_pickem():
    line = np.array([3., -7., 0.])
    p = t.baseline_predictions(line)
    assert t.fb.pick(p['Always favorite'], line).tolist() == [1., -1., 0.]
    assert t.fb.pick(p['Always home'], line).tolist() == [1., 1., 1.]


def test_record_counts_pushes_in_roi_and_excludes_skips():
    r = t.record(np.array(['W', 'L', 'P', 'S']), np.array([1/1.1, -1., 0., 0.]))
    assert (r['W'], r['L'], r['P'], r['skips'], r['n']) == (1, 1, 1, 1, 3)
    assert r['roi'] == pytest.approx((1/1.1-1)/3) and r['cover'] == .5


def test_frozen_replay_reproduces_production_map():
    f = t.load('R'); pred, rules = t.predictions(f)
    ok = np.isfinite(pred.M)
    assert np.allclose(pred.M[ok], pred.fixed_band_spread[ok])
    assert rules[2026]['M']['magnitudes'] == [3., 4., 7., 14.]
    pub = __import__('json').loads((t.INPUTS/'provenance.json').read_text())['published_replay_2023_on']
    late = ok & (pred.season >= 2023)
    rec = t.record(*t.fb.grade(pred[late], pred.M[late].to_numpy(float)))
    assert (rec['n'], rec['W'], rec['L'], rec['P']) == (pub['games'], pub['W'], pub['L'], pub['P'])


def test_research_rejects_protected_outputs():
    for p in (t.ROOT/'data'/'x', t.ROOT/'public'):
        with pytest.raises(ValueError, match='Protected'): t.guard(p)
