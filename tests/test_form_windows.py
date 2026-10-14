import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import form_windows as fw


@pytest.fixture(scope='module')
def small():
    box = pd.read_csv(fw.BOXES); sched = fw.schedule_frame(pd.read_csv(fw.SCHEDULE))
    keep = sched.season.isin([2013, 2014])
    return box[box.season.isin([2013, 2014])], sched[keep]


def test_decay_profiles_reproduce_production_lagged_features(small):
    box, sched = small
    mine = fw.profiles(box, sched, half_life=8.).set_index('game_id')
    ref = fw.m.lagged_features(box, sched, 8.).set_index('game_id')[fw.MAIN]
    j = ref.join(mine, rsuffix='_mine', how='inner')
    a, b = j[fw.MAIN].to_numpy(float), j[[c+'_mine' for c in fw.MAIN]].to_numpy(float)
    both = np.isfinite(a) & np.isfinite(b)
    assert len(j) == len(ref) and np.array_equal(np.isfinite(a), np.isfinite(b))
    assert np.allclose(a[both], b[both], rtol=0, atol=1e-12)


def test_window_weights_cover_exactly_the_last_n_games():
    h = pd.DataFrame({'season': [2013]*5+[2014]*2})
    assert fw.team_weights(h, 2014, n=3).tolist() == [0, 0, 0, 0, 1, 1, 1]
    assert fw.team_weights(h, 2014, n=10).tolist() == [1]*7      # fewer games than the window
    assert fw.team_weights(h.iloc[:0], 2014, n=2).tolist() == []
    w = fw.team_weights(h, 2014, half_life=8.)
    assert np.isclose(w[-1], 1.) and np.isclose(w[4], 2**(-2/8)*.5)  # decay plus the season-boundary halving


def test_windows_use_only_earlier_games(small):
    box, sched = small
    a = fw.profiles(box, sched, n=3)
    shocked = box.copy()
    wk = (shocked.season == 2014) & (shocked.week == 10)
    shocked.loc[wk, 'penalty_yards'] = shocked.loc[wk, 'penalty_yards']*3+50
    b = fw.profiles(shocked, sched, n=3)
    ids = sched[(sched.season == 2014) & (sched.week <= 10)].game_id
    later = sched[(sched.season == 2014) & (sched.week == 11)].game_id
    A, B = a.set_index('game_id'), b.set_index('game_id')
    assert np.allclose(A.loc[ids].to_numpy(float), B.loc[ids].to_numpy(float), equal_nan=True)
    assert not np.allclose(A.loc[later].to_numpy(float), B.loc[later].to_numpy(float), equal_nan=True)


def test_swap_replaces_main_columns_and_rejects_missing_games():
    prof = pd.DataFrame({'game_id': ['g1'], **{c: [1.] for c in fw.MAIN}})
    df = pd.DataFrame({'game_id': ['g1'], 'q': [.6], **{c: [0.] for c in fw.MAIN}})
    out = fw.swap(df, prof)
    assert (out[fw.MAIN] == 1.).all(axis=None) and out.q[0] == .6
    with pytest.raises(ValueError, match='without rebuilt'):
        fw.swap(pd.DataFrame({'game_id': ['g2'], 'q': [.5]}), prof)
