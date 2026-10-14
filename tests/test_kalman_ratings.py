import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import kalman_ratings as kr
import residual_trends as t


def test_rule_success():
    down = [1, 1, 2, 2, 3, 4, np.nan, 3]
    togo = [10, 10, 10, 10, 5, 1, 10, 8]
    gain = [4, 3, 6, 5, 5, 0, 20, -2]
    td = [False]*7+[True]
    s = kr.rule_success(down, togo, gain, td)
    assert s[:6].tolist() == [1., 0., 1., 0., 1., 0.]
    assert np.isnan(s[6]) and s[7] == 1.  # missing down; a touchdown always succeeds


def synthetic_obs(seed=0, weeks=40, noise=.02):
    """Four teams with fixed offense/defense strengths, round-robin each week."""
    rng = np.random.default_rng(seed)
    off = {'A': .10, 'B': 0., 'C': -.05, 'D': -.05}; dfn = {'A': -.05, 'B': .05, 'C': 0., 'D': 0.}
    rows = []
    for w in range(1, weeks+1):
        pairs = [('A', 'B'), ('C', 'D')] if w % 3 == 0 else [('A', 'C'), ('B', 'D')] if w % 3 == 1 else [('A', 'D'), ('B', 'C')]
        for i, (h, a) in enumerate(pairs if w % 2 else [(b, a) for a, b in pairs]):
            rows.append({'game_id': f'g{w}_{i}', 'season': 2013, 'week': w, 'home': h, 'away': a, 'n_home': 60, 'n_away': 60,
                         'y_home': .3+off[h]+dfn[a]+rng.normal(scale=noise), 'y_away': .3+off[a]+dfn[h]+rng.normal(scale=noise)})
    return pd.DataFrame(rows), off, dfn


def test_kalman_recovers_opponent_adjusted_strengths():
    obs, off, dfn = synthetic_obs()
    snap, ll = kr.kalman(obs, list('ABCD'), sigma2=.02**2*60, q=1e-6, rho=.6, p0=.01)
    last = snap[snap.game_id.str.startswith('g40_')]
    # Offense + opposing defense, relative to the league, matches the truth (identifiable sums).
    for r in last.itertuples():
        h, a = obs.set_index('game_id').loc[r.game_id, ['home', 'away']]
        assert abs((r.off_h+r.def_a)-(off[h]+dfn[a]-np.mean([off[x]+dfn[y] for x in off for y in dfn if x != y]))) < .03
    assert np.isfinite(ll) and ll > 0


def test_pregame_snapshot_ignores_its_own_week():
    obs, _, _ = synthetic_obs(weeks=10)
    a, _ = kr.kalman(obs, list('ABCD'), sigma2=.05, q=1e-5, rho=.6, p0=.01)
    shocked = obs.copy(); shocked.loc[shocked.week == 7, 'y_home'] += 5.  # change week 7 results only
    b, _ = kr.kalman(shocked, list('ABCD'), sigma2=.05, q=1e-5, rho=.6, p0=.01)
    wk = a.game_id.str.extract(r'g(\d+)_')[0].astype(int)
    cols = ['off_h', 'def_h', 'off_a', 'def_a']
    assert np.allclose(a.loc[wk <= 7, cols], b.loc[wk <= 7, cols])   # week 7's own snapshot is pregame
    assert not np.allclose(a.loc[wk == 8, cols], b.loc[wk == 8, cols])


def test_season_boundary_regresses_states():
    obs, _, _ = synthetic_obs(weeks=12)
    nxt = obs.assign(season=2014, game_id='n'+obs.game_id)
    cols = ['off_h', 'def_h', 'off_a', 'def_a']
    for rho, small in ((.01, True), (1., False)):
        snap, _ = kr.kalman(pd.concat([obs, nxt]), list('ABCD'), sigma2=.05, q=1e-6, rho=rho, p0=.01)
        end = snap[snap.game_id.str.startswith('g12_')][cols].abs().to_numpy().max()
        start = snap[snap.game_id.str.startswith('ng1_')][cols].abs().to_numpy().max()
        assert end > .02
        assert (start < .02*end) if small else (start > .5*end)  # rho near 0 resets the league; rho 1 carries over


def test_fit_reproduces_production_fit_composite():
    pack = pd.read_csv(t.OOS_PACK)
    names = list(t.m.feature_names(t.m.LEGACY_PRODUCT_RECIPE['family']))+list(t.m.PRODUCT_CONTEXT_NAMES)
    train = pack[t.m.before(pack, 2016, 5)]
    mine = kr.fit(train, names, 2016, 5)
    ref = t.m.fit_composite(train, t.m.LEGACY_PRODUCT_RECIPE, 2016, 5)
    assert np.allclose(mine['beta'], ref['beta'], atol=1e-6) and np.allclose(mine['scale'], ref['scale'])
    g = pack[(pack.season == 2016) & (pack.week == 5)]
    assert np.allclose(kr.predict(g, mine), t.m.apply_fit(g, ref), atol=1e-6)


def test_fit_rejects_future_rows_and_supports_no_offset():
    pack = pd.read_csv(t.OOS_PACK).assign(pass_edge=0., rush_edge=0.)
    with pytest.raises(ValueError, match='current/future'):
        kr.fit(pack[pack.season <= 2016], kr.MODEL_INPUTS, 2016, 5)
    f = kr.fit(pack[t.m.before(pack, 2016, 5)], kr.MODEL_INPUTS, 2016, 5, offset=False)
    assert len(f['beta']) == len(kr.MODEL_INPUTS)+1 and not f['offset']
