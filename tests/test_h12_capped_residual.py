"""H12 cap bands, no-lookahead signals, fade direction, grading and the verdict gate."""
import numpy as np
import pandas as pd

from research import h12_capped_residual as h


def test_cap_uses_the_band_median_number():
    assert h.cap(10, 2.5) == 3 and h.cap(-10, -2.5) == -3
    assert h.cap(10, 3) == 4 and h.cap(10, -6.5) == 4
    assert h.cap(10, 7) == 7 and h.cap(-20, 10) == -14
    assert h.cap(2, 13.5) == 2


def schedule(weeks, margin=0., line=0.):
    rows = []
    for w in range(1, weeks + 1):
        rows.append(dict(game_id=f'2013_{w:02d}_B_A', season=2013, week=w, game_type='REG',
                         home_team='A', away_team='B', result=margin, spread_line=line))
    return pd.DataFrame(rows)


def test_signal_uses_only_earlier_weeks_and_needs_n_games():
    g = schedule(4, margin=10., line=0.)  # home covers by 10 each week, capped at 3
    x = h.signals(g, 2)
    assert np.isnan(x[:2]).all()
    assert x[2] == 3 - (-3) and x[3] == 6
    g.loc[2, 'result'] = -50.  # the game's own outcome must not enter its signal
    assert h.signals(g, 2)[2] == 6


def test_fade_bets_against_the_better_recent_team_and_grades_pushes():
    g = schedule(4, margin=10., line=0.)
    g['season'] = 2013
    out = h.evaluate(g.assign(spread_line=.5), n=2)
    # x = 6 >= threshold: bet away; home covers by 9.5 each time, so the fade loses.
    assert out['rule']['bets'] == 2 and out['rule']['losses'] == 2
    assert np.allclose(h.returns(np.array([1., -1., 1.]), np.array([3., 3., 0.])), [1 / 1.1, -1., 0.])


def test_franchise_codes_continue_across_moves(tmp_path):
    seed = tmp_path / 'seed.csv'
    frozen = tmp_path / 'frozen.csv'
    pd.DataFrame([dict(game_id='2012_01_SD_STL', season=2012, week=1, game_type='REG',
                       home_team='STL', away_team='SD', result=3, spread_line=1)]).to_csv(seed, index=False)
    pd.DataFrame([dict(game_id='2017_01_LAC_LA', season=2017, week=1, game_type='REG',
                       home_team='LA', away_team='LAC', result=3, spread_line=1),
                  dict(game_id='2017_20_X_Y', season=2017, week=20, game_type='POST',
                       home_team='Y', away_team='X', result=3, spread_line=1)]).to_csv(frozen, index=False)
    g = h.load(seed, frozen)
    assert set(g.home_team) == {'LA'} and set(g.away_team) == {'LAC'} and len(g) == 2


def rec(bets, cover):
    return dict(bets=bets, cover=cover)


def test_verdict_gate():
    assert h.verdict(dict(rule=rec(149, .6), favorite=rec(149, .5))).startswith('inconclusive')
    assert h.verdict(dict(rule=rec(150, .53), favorite=rec(150, .50))).startswith('replicates')
    assert h.verdict(dict(rule=rec(150, .523), favorite=rec(150, .50))).startswith('falsified')
    assert h.verdict(dict(rule=rec(150, .55), favorite=rec(150, .56))).startswith('falsified')
