import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import peaks_to_ybc as p
import yards_before_contact as ybc
from test_product_production import fixture
from test_yards_before_contact import season_of_games


def test_replacement_is_exact_and_keeps_rush_efficiency():
    assert {a: len(n) for a, n in p.ARMS.items()} == {'production': 29, 'no_peaks': 27, 'peaks_to_ybc': 29}
    assert set(p.PRODUCTION)-set(p.NO_PEAKS) == set(p.m.PEAK_FEATURES)
    assert p.ARMS['peaks_to_ybc'] == p.NO_PEAKS+p.YBC
    assert set(ybc.RUSH) <= set(p.ARMS['peaks_to_ybc'])
    assert not set(p.m.PEAK_FEATURES) & set(p.ARMS['peaks_to_ybc'])
    assert p.LEVEL == .975


def inputs():
    train, board = fixture()
    train['game_id'] = ['train'+str(i) for i in range(len(train))]
    pack = pd.concat([train, board], ignore_index=True)
    pack['home_moneyline'] = -120.; pack['away_moneyline'] = 100.
    pack['q'] = p.m.market_ml_wp(pack)
    rng = np.random.default_rng(30)
    prof = pd.DataFrame({'game_id': pack.game_id, 'd_ybc_off': rng.normal(size=len(pack)),
                         'd_ybc_def': rng.normal(size=len(pack))})
    board = pack[pack.season == 2023].copy()
    return pack, board, prof


def test_replacement_ignores_removed_peaks_and_uses_ybc():
    pack, board, prof = inputs()
    a, audit, _ = p.frame(pack, board, prof, p.ARMS['peaks_to_ybc'])
    changed = pack.copy()
    changed[list(p.m.PEAK_FEATURES)] = 1e8
    b, _, _ = p.frame(changed, board.assign(**{n: -1e8 for n in p.m.PEAK_FEATURES}), prof, p.ARMS['peaks_to_ybc'])
    np.testing.assert_array_equal(a.p, b.p)
    shock = prof.copy(); shock.loc[shock.game_id.isin(board.game_id), 'd_ybc_off'] += 100
    c, _, _ = p.frame(pack, board, shock, p.ARMS['peaks_to_ybc'])
    assert not np.allclose(a.p, c.p)
    assert audit.training_max_season.max() == 2022


def test_production_fit_reproduces_independent_implementation():
    pack, board, prof = inputs()
    _, _, err = p.frame(pack, board, prof, p.PRODUCTION, verify_production=True)
    assert err < 1e-9


def test_missing_ybc_is_an_error_for_training_and_evaluation():
    pack, board, prof = inputs()
    with pytest.raises(ValueError, match='Missing evaluation'):
        p.frame(pack, board, prof[~prof.game_id.isin(board.game_id)], p.NO_PEAKS+p.YBC)
    prof.loc[prof.game_id == 'train0', 'd_ybc_off'] = np.nan
    with pytest.raises(ValueError, match='Missing training'):
        p.frame(pack, board, prof, p.NO_PEAKS+p.YBC)


def test_ybc_profiles_ignore_current_and_future_weeks():
    tg, games = season_of_games()
    tg = tg.rename(columns={'runs': 'carries', 'tfl': 'ybc'})
    a = ybc.profiles(tg, games, {'ybc': ('ybc', 'carries')}).set_index('game_id')
    shock = tg.copy(); shock.loc[shock.week >= 5, 'ybc'] += 10000
    b = ybc.profiles(shock, games, {'ybc': ('ybc', 'carries')}).set_index('game_id')
    early = games[games.week <= 5].game_id
    np.testing.assert_allclose(a.loc[early, p.YBC], b.loc[early, p.YBC], equal_nan=True)
    later = games[games.week == 6].game_id
    assert not np.allclose(a.loc[later, p.YBC], b.loc[later, p.YBC])


def test_development_screen_requires_both_comparators_and_bases():
    good = pd.DataFrame([{'arm': control, 'context': 'all', 'basis': basis,
                          'll_gain_x1000': 1., 'lo_x1000': .1}
                         for control in ('production', 'no_peaks') for basis in p.BASES])
    assert p.screen(good).startswith('Worth')
    good.loc[good.arm == 'no_peaks', 'lo_x1000'] = -.1
    assert p.screen(good).startswith('No nomination')


def test_reference_freeze_refuses_overwrite():
    with pytest.raises(ValueError, match='already frozen'):
        p.freeze_reference()
