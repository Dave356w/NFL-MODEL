import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import context_support_cap as c
from test_context_shrinkage import fixture


def hinges(**cols):
    f = pd.DataFrame({name: 0. for name in c.HINGES}, index=range(7))
    for name, values in cols.items(): f[name] = values
    return f


def test_cap_is_kth_largest_nonzero_magnitude():
    f = hinges(pass_1sd_pn=[0., 0., .2, -.9, .5, 2., -.1])
    assert c.support_caps(f, 1)['pass_1sd_pn'] == 2.
    assert c.support_caps(f, 2)['pass_1sd_pn'] == .9
    assert c.support_caps(f, 5)['pass_1sd_pn'] == .1
    # Fewer active training rows than K: no support, so the hinge is zeroed.
    assert c.support_caps(f, 6)['pass_1sd_pn'] == 0.
    assert c.support_caps(f, 1)['pass_1sd_pp'] == 0.


def test_invalid_support_inputs_rejected():
    f = hinges(pass_1sd_pn=[0., 1., 2., 0., 0., 0., 0.])
    for k in (0, -1, 1.5, True):
        with pytest.raises(ValueError, match='positive integer'): c.support_caps(f, k)
    f.loc[0, 'pass_1sd_nn'] = np.nan
    with pytest.raises(ValueError, match='Non-finite'): c.support_caps(f, 1)
    with pytest.raises(ValueError, match='Invalid support cap'): c.winsorize(f, {'pass_1sd_pn': -1.})
    with pytest.raises(ValueError, match='Invalid support cap'): c.winsorize(f, {'pass_product': 1.})


def test_winsorize_clips_only_beyond_support():
    f = hinges(pass_1sd_pn=[0., np.nan, .3, -.9, .5, 2., -.1])
    f['pass_product'] = 9.
    out = c.winsorize(f, {'pass_1sd_pn': .5})
    assert out.pass_1sd_pn.tolist()[2:] == [.3, -.5, .5, .5, -.1]
    assert out.pass_1sd_pn.iloc[0] == 0. and np.isnan(out.pass_1sd_pn.iloc[1])
    assert (out.pass_product == 9.).all() and f.pass_1sd_pn.iloc[5] == 2.
    pd.testing.assert_frame_equal(c.winsorize(f, {'pass_1sd_pn': 2.}), f)
    pd.testing.assert_frame_equal(c.winsorize(f, None), f)


def test_uncapped_and_nonbinding_arms_reproduce_production():
    f = fixture()
    prod = c.fit_arm(f, 2023, 1)
    ref = c.m.fit_composite(f, c.RECIPE, 2023, 1)
    assert np.array_equal(c.predict_arm(f, prod), c.m.apply_fit(f, ref))
    # Five active training rows at 1.0: the K=5 cap is 1.0 and changes nothing.
    k5 = c.fit_arm(f, 2023, 1, 5)
    assert k5['support_caps']['pass_1sd_pn'] == 1. and k5['support_active_rows']['pass_1sd_pn'] == 5
    assert np.array_equal(c.predict_arm(f, k5), c.predict_arm(f, prod)) and not c.capped(f, k5).any()
    # K=6 exceeds the active support: the hinge is zeroed in training and prediction.
    k6 = c.fit_arm(f, 2023, 1, 6)
    assert k6['support_caps']['pass_1sd_pn'] == 0. and k6['beta'][k6['names'].index('pass_1sd_pn')] == 0.
    assert c.capped(f, k6)[:5].all() and not c.capped(f, k6)[5:].any()
    assert not np.allclose(c.predict_arm(f, k6)[:5], c.predict_arm(f, prod)[:5])


def test_caps_use_only_prior_training_rows():
    f = fixture()
    with pytest.raises(ValueError, match='current/future'): c.fit_arm(f, 2022, 11, 5)
    k5, prod = c.fit_arm(f, 2023, 1, 5), c.fit_arm(f, 2023, 1)
    extreme = f.iloc[:1].assign(pass_1sd_pn=50.)
    at_cap = extreme.assign(pass_1sd_pn=k5['support_caps']['pass_1sd_pn'])
    assert c.capped(extreme, k5)[0] and not c.capped(at_cap, k5)[0]
    assert c.predict_arm(extreme, k5)[0] == c.predict_arm(at_cap, k5)[0]
    # Production extrapolates the same input linearly.
    assert c.predict_arm(extreme, prod)[0] != c.predict_arm(at_cap, prod)[0]


def test_flip_accounting_against_production():
    held = pd.DataFrame({'game_id': list('abcd'), 'season': 2023, 'week': [1, 1, 2, 2],
                         'home won': [1., 0., 1., .5], 'home_moneyline': [-150., -150., 120., -110.],
                         'away_moneyline': [130., 130., -140., -110.], 'q': [.58, .58, .44, .51],
                         'production': [.6, .6, .4, .6], 'cap_k5': [.6, .45, .4, .6],
                         'cap_k1': [.6, .6, .4, .6], 'cap_k10': [.6, .6, .55, .6]})
    for arm in c.ARMS: held[arm+'__capped'] = held[arm] != held.production
    pairs = {r['arm']: r for r in c.compare(held)['comparisons']}
    # cap_k5 moves game b to the away side at +130 and wins; production lost 1u there.
    assert pairs['cap_k5']['side_flips'] == 1 and pairs['cap_k5']['flip_units_delta'] == pytest.approx(2.3)
    assert pairs['cap_k10']['flip_units_delta'] == pytest.approx(2.2) and pairs['cap_k10']['capped_games'] == 1
    assert pairs['cap_k1']['side_flips'] == 0 and pairs['cap_k1']['ll_gain'] == 0.


def test_preregistered_verdict_rule():
    base = {'ll_gain': .001, 'flip_units_delta': 0., 'll_gain_ci': [-.001, .003]}
    assert c.verdict(base) == 'unresolved'
    assert c.verdict({**base, 'll_gain_ci': [.0001, .003]}).startswith('positive')
    assert c.verdict({**base, 'll_gain': 0.}) == 'not supported'
    assert c.verdict({**base, 'flip_units_delta': -.01}) == 'not supported'


def test_protected_output_guard():
    with pytest.raises(ValueError, match='production outputs'): c.run(c.ROOT/'data'/'support_cap')


def test_frozen_week5_refit_reproduces_archive_and_committed_replay():
    f = pd.read_csv(c.PACK)
    train = f[c.eligible(f) & c.m.before(f, 2026, 5)]
    snapshots = [json.loads(x) for x in c.SNAPSHOTS.read_text().splitlines()]
    r = next(x for x in snapshots if x['game_id'] == '2026_05_SF_SEA' and x['revision'] == c.REVISION)
    row = pd.DataFrame([{**r['model_inputs'], 'q': r['market_no_vig_wp']}])
    assert c.predict_arm(row, c.fit_arm(train, 2026, 5))[0] == pytest.approx(r['model_wp'], abs=1e-9)
    k5 = c.fit_arm(train, 2026, 5, 5)
    active = np.sort(np.abs(train.pass_1sd_pn[train.pass_1sd_pn != 0].to_numpy()))[::-1]
    assert k5['support_caps']['pass_1sd_pn'] == active[4] < abs(row.pass_1sd_pn.iloc[0])
    committed = pd.read_csv(c.ROOT/'research/support_cap_results/current_counterfactuals.csv').set_index('game_id')
    assert c.predict_arm(row, k5)[0] == pytest.approx(committed.loc['2026_05_SF_SEA', 'cap_k5'], abs=1e-9)
