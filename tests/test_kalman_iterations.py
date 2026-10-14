import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import kalman_iterations as ki


def margin_obs(weeks=30, seed=0, noise=1.):
    rng = np.random.default_rng(seed)
    s = {'A': 6., 'B': 2., 'C': -3., 'D': -5.}
    rows = []
    for w in range(1, weeks+1):
        pairs = [('A', 'B'), ('C', 'D')] if w % 3 == 0 else [('A', 'C'), ('B', 'D')] if w % 3 == 1 else [('A', 'D'), ('B', 'C')]
        for i, (h, a) in enumerate(pairs if w % 2 else [(b, a) for a, b in pairs]):
            rows.append({'game_id': f'g{w}_{i}', 'season': 2013, 'week': w, 'home': h, 'away': a, 'y': 2.+s[h]-s[a]+rng.normal(scale=noise)})
    return pd.DataFrame(rows), s


def test_kalman1_recovers_strength_differences():
    obs, s = margin_obs()
    snap, ll = ki.kalman1(obs, list('ABCD'), sigma2=1., q=1e-4, rho=.6, p0=25.)
    last = snap[snap.game_id.str.startswith('g30_')].merge(obs, on='game_id')
    for r in last.itertuples():
        assert abs(r.edge-(s[r.home]-s[r.away])) < 1.
    assert np.isfinite(ll)


def test_kalman1_snapshot_is_pregame():
    obs, _ = margin_obs(weeks=8)
    a, _ = ki.kalman1(obs, list('ABCD'), sigma2=4., q=1e-3, rho=.6, p0=10.)
    shocked = obs.copy(); shocked.loc[shocked.week == 5, 'y'] += 30.
    b, _ = ki.kalman1(shocked, list('ABCD'), sigma2=4., q=1e-3, rho=.6, p0=10.)
    wk = a.game_id.str.extract(r'g(\d+)_')[0].astype(int)
    assert np.allclose(a.edge[wk <= 5], b.edge[wk <= 5])
    assert not np.allclose(a.edge[wk > 5], b.edge[wk > 5])  # later weeks see the change


def test_single_obs_kinds():
    g = pd.DataFrame({'game_id': ['x', 'y'], 'season': 2013, 'week': 1, 'home': ['A', 'B'], 'away': ['C', 'D'],
                      'result': [7., -3.], 'spread_line': [3., np.nan]})
    assert ki.single_obs(g, 'margin').y.tolist() == [7., -3.]
    ats = ki.single_obs(g, 'ats')
    assert ats.y.tolist() == [4.] and ats.game_id.tolist() == ['x']  # missing spread drops the game


def frames_for_selection(change_2019=False):
    """production is sharp in 2015-16 only; k5 is blunt in 2015 and sharp from 2016; k2 is always blunt."""
    sharp = {'production': lambda y: y <= 2016, 'k5_ridge1': lambda y: y >= 2016, 'k2_margin': lambda y: False}
    out = {}
    for arm, is_sharp in sharp.items():
        parts = []
        for season in range(2015, 2026):
            y = np.tile([1., 0.], 20)
            good = is_sharp(season) and not (change_2019 and season == 2019)
            p = np.where(y == 1, .7, .3) if good else np.where(y == 1, .55, .45)
            parts.append(pd.DataFrame({'game_id': [f'{season}_{i}' for i in range(40)], 'season': season, 'y': y, 'p': p}))
        out[arm] = pd.concat(parts, ignore_index=True)
    return out


def test_nested_selection_uses_only_earlier_seasons():
    choice = ki.select(frames_for_selection())
    assert choice[2017] == 'production'   # 2015-16: production sharp twice, k5 once
    assert choice[2019] == 'k5_ridge1'    # 2015-18: k5 sharp three times, production twice
    # A season's own results never affect its own choice.
    assert ki.select(frames_for_selection(change_2019=True))[2019] == choice[2019]


def test_selection_ties_go_to_production():
    f = frames_for_selection()
    same = {a: f['production'] for a in f}
    assert set(ki.select(same).values()) == {'production'}


def test_verdict_half_rule():
    def rows(gains, lo, bases):
        return pd.DataFrame({'basis': list(bases), 'context': 'all', 'll_gain_x1000': gains, 'lo_x1000': lo})
    two = ('2017-22', '2023-25'); three = ('2015-16', '2017-22', '2023-25')
    assert ki.verdict(rows([1., -1.], [0., -2.], two), two) == 'not better than production'
    assert ki.verdict(rows([1., 2.], [.1, -1.], two), two).startswith('better')
    assert ki.verdict(rows([1., 2.], [-.1, -1.], two), two) == 'unresolved'
    assert ki.verdict(rows([1., -1., 2.], [-1., -2., .5], three), three) == 'unresolved'
    assert ki.verdict(rows([-1., -1., 2.], [-2., -2., .5], three), three) == 'not better than production'
