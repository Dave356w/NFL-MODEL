"""H11 exposed-game exclusion and the soft-versus-hard paired sign."""
import pandas as pd

from research import soft_band_ladder_score as h


def test_exposed_list_is_frozen_and_read_exactly(tmp_path):
    p = tmp_path / 'exposed.txt'
    p.write_text('2026_06_A_B\n\n2026_07_C_D\n')
    assert h.exposed_games(p) == {'2026_06_A_B', '2026_07_C_D'}
    assert len(h.exposed_games()) == 28


def rungs(soft, hard):
    return pd.DataFrame([dict(game_id=f'g{g}', y=y, kalshi=.5, band=hard(y), soft=soft(y))
                         for g in range(3) for y in (1., 0.)])


def test_paired_is_positive_when_soft_beats_hard_and_negative_otherwise():
    assert h.paired(rungs(lambda y: .8 if y else .2, lambda y: .6 if y else .4))['gain'] > 0
    assert h.paired(rungs(lambda y: .6 if y else .4, lambda y: .8 if y else .2))['gain'] < 0
    assert abs(h.paired(rungs(lambda y: .7, lambda y: .7))['gain']) < 1e-12
