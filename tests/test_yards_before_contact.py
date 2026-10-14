import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import nfl_model as m
import yards_before_contact as ybc


def test_ratio_matches_production_metric_profile():
    rng = np.random.default_rng(0)
    cols = list(m.COUNTS)
    h = pd.DataFrame(rng.uniform(1., 40., (9, len(cols))), columns=cols)
    league = pd.DataFrame(rng.uniform(1., 40., (60, len(cols))), columns=cols)
    w = rng.uniform(.1, 1., 9)
    want = m.metric_profile(h.to_numpy(float), w, league.to_numpy(float), {'r': ('rush_yards', 'rush_attempts', 1.)})['r']
    assert np.isclose(ybc.ratio(h, w, 'rush_yards', 'rush_attempts', league), want, rtol=0, atol=1e-12)


def test_ratio_without_team_history_is_league_average():
    league = pd.DataFrame({'tfl': [2., 4., 0.], 'runs': [20., 20., 20.]})
    empty = league.iloc[:0]
    assert np.isclose(ybc.ratio(empty, np.zeros(0), 'tfl', 'runs', league), 2./20.)
    assert np.isnan(ybc.ratio(empty, np.zeros(0), 'tfl', 'runs', league.iloc[:0]))


def test_aggregate_tfl_counts_designed_regular_season_runs_only():
    base = {'game_id': 'g1', 'season': 2015, 'week': 1, 'season_type': 'REG', 'posteam': 'STL', 'defteam': 'SEA',
            'qb_scramble': 0, 'two_point_attempt': 0, 'play_deleted': 0}
    plays = [dict(base, play_type='run', tackled_for_loss=1), dict(base, play_type='run', tackled_for_loss=0),
             dict(base, play_type='run', tackled_for_loss=np.nan),
             dict(base, play_type='run', tackled_for_loss=1, qb_scramble=1),         # scramble: excluded
             dict(base, play_type='run', tackled_for_loss=1, two_point_attempt=1),   # two-point try: excluded
             dict(base, play_type='run', tackled_for_loss=1, play_deleted=1),        # deleted: excluded
             dict(base, play_type='pass', tackled_for_loss=0),                       # pass: excluded
             dict(base, play_type='run', tackled_for_loss=1, season_type='POST'),    # postseason: excluded
             dict(base, play_type='run', tackled_for_loss=1, posteam='SEA', defteam='STL')]
    g = ybc.aggregate_tfl(pd.DataFrame(plays)).set_index('team')
    assert g.loc['LA', 'runs'] == 3 and g.loc['LA', 'tfl'] == 1 and g.loc['LA', 'opponent'] == 'SEA'  # alias applied
    assert g.loc['SEA', 'runs'] == 1 and g.loc['SEA', 'tfl'] == 1 and g.loc['SEA', 'opponent'] == 'LA'


def season_of_games(weeks=8, seed=1):
    rng = np.random.default_rng(seed)
    pairs = [[('A', 'B'), ('C', 'D')], [('A', 'C'), ('B', 'D')], [('A', 'D'), ('B', 'C')]]
    rows, games = [], []
    for w in range(1, weeks+1):
        for i, (h, a) in enumerate(pairs[w % 3]):
            gid = f'2020_{w:02d}_{a}_{h}'
            games.append({'game_id': gid, 'season': 2020, 'week': w, 'home': h, 'away': a})
            for team, opp in ((h, a), (a, h)):
                rows.append({'game_id': gid, 'season': 2020, 'week': w, 'team': team, 'opponent': opp,
                             'runs': int(rng.integers(15, 35)), 'tfl': int(rng.integers(0, 6))})
    return pd.DataFrame(rows), pd.DataFrame(games)


def test_profiles_use_only_earlier_games():
    tg, games = season_of_games()
    a = ybc.profiles(tg, games, ybc.TFL_SPECS).set_index('game_id')
    shocked = tg.copy(); shocked.loc[shocked.week == 5, 'tfl'] += 10
    b = ybc.profiles(shocked, games, ybc.TFL_SPECS).set_index('game_id')
    wk = games.set_index('game_id').week
    early, late = wk[wk <= 5].index, wk[wk > 5].index
    assert np.allclose(a.loc[early, ybc.TFL].to_numpy(), b.loc[early, ybc.TFL].to_numpy(), equal_nan=True)
    assert not np.allclose(a.loc[late, ybc.TFL].to_numpy(), b.loc[late, ybc.TFL].to_numpy())  # later weeks see it
    assert a.loc[wk[wk == 1].index, ybc.TFL].isna().all().all()  # no history, no league: missing (fit treats as 0)


def test_defense_profile_reads_opponents_offense():
    tg, games = season_of_games()
    shocked = tg.copy(); shocked.loc[(shocked.opponent == 'A') & (shocked.week < 4), 'tfl'] += 10  # A's defense stops more runs
    a = ybc.profiles(tg, games, ybc.TFL_SPECS).set_index('game_id')
    b = ybc.profiles(shocked, games, ybc.TFL_SPECS).set_index('game_id')
    g = games[(games.week == 4) & ((games.home == 'A') | (games.away == 'A'))].iloc[0]
    sign = 1. if g.home == 'A' else -1.
    moved = sign*(b.loc[g.game_id, 'd_tfl_def']-a.loc[g.game_id, 'd_tfl_def'])
    assert moved > 0
    # A game without A only feels the shift in the league pseudo-games, which is much smaller.
    other = games[(games.week == 4) & (games.home != 'A') & (games.away != 'A')].iloc[0]
    assert abs(b.loc[other.game_id, 'd_tfl_def']-a.loc[other.game_id, 'd_tfl_def']) < .1*moved


def test_arms_and_family_are_fixed():
    assert set(ybc.RUSH) <= set(ybc.PRODUCTION) and len(ybc.PRODUCTION) == 29
    assert ybc.ARMS['plus_ybc'] == ybc.PRODUCTION+['d_ybc_off', 'd_ybc_def']
    assert ybc.ARMS['plus_ybc_yac'] == ybc.PRODUCTION+ybc.SPLIT
    assert not set(ybc.RUSH) & set(ybc.ARMS['swap_rush']) and len(ybc.ARMS['swap_rush']) == 31
    assert ybc.ARMS['plus_tfl'] == ybc.PRODUCTION+ybc.TFL
    assert np.isclose(ybc.LEVEL, 1-.05/4)
    assert ybc.ARM_BASES['plus_tfl'] == ('2015-16', '2017-22', '2023-25') and ybc.ARM_BASES['plus_ybc'] == ('2021-22', '2023-25')
