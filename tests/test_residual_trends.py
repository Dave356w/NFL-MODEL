import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import residual_trends as t


def frame(n=2400, effect=0., seed=0, weeks=60):
    """Synthetic games: the model's probability omits `effect`*x; outcomes include it."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n); base = rng.normal(scale=.8, size=n)
    p = expit(base); y = (rng.random(n) < expit(base+effect*x)).astype(float)
    return pd.DataFrame({'x': x, 'p': p, 'y': y, 'season': 2020, 'week': np.arange(n) % weeks + 1,
                         'cluster': [f'2020_{w}' for w in np.arange(n) % weeks + 1]})


def test_cell_detects_an_omitted_input_and_its_sign():
    up = t.cell(frame(effect=.5), 'x')
    down = t.cell(frame(effect=-.5, seed=1), 'x')
    assert up['z'] > 4 and up['effect_per_sd'] > .25
    assert down['z'] < -4 and down['effect_per_sd'] < -.25


def test_cell_is_quiet_when_the_model_is_right():
    zs = [t.cell(frame(effect=0., seed=s), 'x')['z'] for s in range(20)]
    assert np.mean(np.abs(zs) < 2.5) >= .9
    assert abs(np.mean(zs)) < .8


def test_cell_skips_constant_inputs_ties_and_tiny_samples():
    f = frame(n=200)
    f['zero'] = 0.
    assert np.isnan(t.cell(f, 'zero')['z'])
    f.loc[:, 'y'] = np.where(np.arange(len(f)) < 195, np.nan, f.y)  # ties are NaN: only 5 binary rows
    assert t.cell(f, 'x')['n'] == 5 and np.isnan(t.cell(f, 'x')['z'])


def test_context_bands_are_exclusive_and_cover_half_points():
    tot = [40.5, 41., 41.5, 47., 47.5, np.nan]
    assert t.context_mask(tot, 'total_low').tolist() == [True, True, False, False, False, False]
    assert t.context_mask(tot, 'total_mid').tolist() == [False, False, True, True, False, False]
    assert t.context_mask(tot, 'total_high').tolist() == [False, False, False, False, True, False]
    assert t.context_mask(tot, 'all').all()
    with pytest.raises(ValueError, match='Unknown context'): t.context_mask(tot, 'week18')


def grid(zs):
    return pd.DataFrame({'context': 'all', 'input': [f'x{i}' for i in range(len(zs))], 'n': 100,
                         'z': zs, 'effect_per_sd': np.sign(zs)*.1, 'S': zs})


def test_selection_threshold_rank_and_cap():
    zs = [2.0, -3.0, 1.99, -2.5] + [2.1+i/100 for i in range(12)]
    c = t.select(grid(zs))
    assert len(c) == t.MAX_K
    assert c.z.iloc[0] == -3.0 and 1.99 not in c.z.tolist()
    assert t.select(grid([1.5, -1.9])).empty


def test_confirmation_is_directional_and_bonferroni():
    cands = t.select(grid([3.0, -2.5, 2.2, -2.1]))
    conf = grid([3.0, -2.5, 2.2, -2.1]).assign(z=[2.3, -0.4, -1.0, np.nan])
    out, bar = t.confirm(cands, conf)
    assert np.isclose(bar, norm.ppf(1-.05/4))
    v = dict(zip(out.input, out.verdict))
    assert v == {'x0': 'confirmed', 'x1': 'direction holds', 'x2': 'not replicated', 'x3': 'not replicated'}
    fwd = t.forward_set(out)
    assert fwd.input.tolist() == ['x0', 'x1']  # positive directional z only, ranked


def test_forward_set_is_capped():
    cands = t.select(grid([2.5+i/10 for i in range(8)]))
    out, _ = t.confirm(cands, grid([2.5+i/10 for i in range(8)]).assign(z=np.linspace(.1, 1., 8)))
    assert len(t.forward_set(out)) == t.MAX_FORWARD


def slope_frame(n=3000, b=1., seed=0):
    rng = np.random.default_rng(seed)
    q = expit(rng.normal(scale=.8, size=n)); d = rng.normal(scale=.4, size=n)
    y = (rng.random(n) < expit(logit(q)+b*d)).astype(float)
    return pd.DataFrame({'q': q, 'departure16': d, 'y': y, 'cluster': [f'w{i % 50}' for i in range(n)]})


def test_departure_slope_recovers_informative_and_empty_departures():
    b1, se1, _ = t.departure_slope(slope_frame(b=1.))
    b0, se0, _ = t.departure_slope(slope_frame(b=0., seed=1))
    assert abs(b1-1) < 3*se1 and b1 > 2*se1
    assert abs(b0) < 3*se0


def test_h7_verdict_rules():
    hi, lo = slope_frame(b=1.), slope_frame(b=0., seed=2)
    f = pd.concat([hi.assign(total_line=50.), lo.assign(total_line=38.)], ignore_index=True)
    assert t.h7(f)['verdict'].startswith('supported')
    small = pd.concat([hi.head(20).assign(total_line=50.), lo.head(80).assign(total_line=38.)], ignore_index=True)
    assert t.h7(small)['verdict'].startswith('no verdict')
    rev = pd.concat([lo.assign(total_line=50.), hi.assign(total_line=38.)], ignore_index=True)
    assert t.h7(rev)['verdict'].startswith('falsified')


def test_forward_verdict_rules():
    assert t.forward_verdict(3.0, 29, 4).startswith('no verdict')
    assert t.forward_verdict(norm.ppf(1-.05/4)+.01, 30, 4) == 'supported'
    assert t.forward_verdict(-.1, 99, 4) == 'unresolved'
    assert t.forward_verdict(-.1, 100, 4) == 'falsified'
    assert t.forward_verdict(np.nan, 200, 4).startswith('no verdict')


def snapshot(gid, rev, sig, week, when, wp=.6, inputs=None):
    return {'experiment': f'{sig}:recipe:2026', 'revision': rev, 'game_id': gid, 'season': 2026, 'week': week,
            'generated_utc': when, 'model_wp': wp, 'home_moneyline': -150., 'away_moneyline': 130.,
            'model_inputs': inputs or {'d__avail__qb_delta': .1}}


def test_forward_frame_filters_sample_and_takes_lock_total(tmp_path):
    rev, sig = t.FORWARD['H8']
    rows = [snapshot('2026_05_A_B', rev, sig, 5, '2026-10-09T00:00:00+00:00'),  # before the sample
            snapshot('2026_06_C_D', rev, sig, 6, '2026-10-15T00:00:00+00:00'),
            snapshot('2026_06_C_D', rev, sig, 6, '2026-10-16T00:00:00+00:00', wp=.9),  # later snapshot ignored
            snapshot('2026_06_E_F', rev, 'deadbeef', 6, '2026-10-15T00:00:00+00:00'),  # other configuration
            snapshot('2026_06_G_H', 'boxscore-composite-v1.16', sig, 6, '2026-10-15T00:00:00+00:00'),
            snapshot('2026_07_I_J', rev, sig, 7, '2026-10-22T00:00:00+00:00')]
    led = tmp_path/'ledger.jsonl'; led.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    view = tmp_path/'view.csv'
    pd.DataFrame({'experiment': f'{sig}:recipe:2026', 'game_id': ['2026_06_C_D', '2026_07_I_J'],
                  'home won': [1., np.nan]}).to_csv(view, index=False)
    h5 = tmp_path/'h5.jsonl'; h5.write_text(json.dumps({'game_id': '2026_06_C_D', 'total_line': 40.5})+'\n')
    f = t.forward_frame(rev, sig, led, view, h5)
    assert f.game_id.tolist() == ['2026_06_C_D', '2026_07_I_J']
    assert f.set_index('game_id').loc['2026_06_C_D', 'p_snap'] == .6
    assert f.set_index('game_id').loc['2026_06_C_D', 'total_line'] == 40.5
    d = t.forward_prepare(f, penalized=True)
    assert d.p.tolist() == [.6, .6] and int(d.y.notna().sum()) == 1
    assert t.forward_frame(rev, 'nothing', led, view, h5).empty


def test_wrong_pick_view_signs_toward_the_models_side():
    d = pd.DataFrame({'x': [1., -1., 2., -2.], 'side': ['home', 'away', 'away', 'home'], 'total_line': 45.,
                      'bet': True, 'p': [.6, .4, .3, .7], 'y': [1., 1., 0., 0.],
                      'units': [.5, -1., 1.4, -1.], 'fav_units': [.5, -1., -1., -1.]})
    v = {r['third']: r for r in t.wrong_pick_view(d, 'all', 'x', [-1.5, 1.5])}
    # Signed toward the pick: +1, +1, -2, -2 -> two 'middle', two 'low'.
    assert v['middle']['bets'] == 2 and v['low']['bets'] == 2 and v['high']['bets'] == 0
    assert np.isclose(v['middle']['wins_minus_expected'], (1-.6)+(0-.6))
    assert np.isclose(v['low']['wins_minus_expected'], (1-.7)+(0-.7))
