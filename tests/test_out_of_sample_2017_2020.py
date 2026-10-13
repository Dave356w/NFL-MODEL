import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import out_of_sample_2017_2020 as o
from test_context_shrinkage import fixture


def mixed_fixture():
    """160 close and 60 lopsided training games, all before 2023 week 1."""
    f = fixture(); f.loc[:59, 'q'] = .8
    return f


def test_close_line_is_strict_and_symmetric():
    f = pd.DataFrame({'q': [.5, .59, .41, .6, .4, .75]})
    assert o.close(f).tolist() == [True, True, True, False, False, False]


def test_challenger_trains_only_on_close_games():
    f = mixed_fixture()
    prod, challenger = o.fit_arm(f, 2023, 1, 'production'), o.fit_arm(f, 2023, 1, 'close_fit')
    assert prod['training_games'] == 220 and challenger['training_games'] == 160
    assert prod['beta'] != challenger['beta']


def test_challenger_returns_market_outside_close_games():
    f = mixed_fixture(); fitted = o.fit_arm(f, 2023, 1, 'close_fit'); prod_fit = o.fit_arm(f, 2023, 1, 'production')
    test = f.iloc[:6].copy(); test['q'] = [.8, .5, .45, .62, .3, .55]
    inside = o.close(test)
    out = o.forecast(test, fitted, 'close_fit')
    assert np.array_equal(out[~inside], test.q.to_numpy()[~inside])
    assert np.array_equal(out[inside], o.m.apply_fit(test, fitted)[inside])
    prod = o.forecast(test, prod_fit, 'production')
    mixed = o.forecast(test, None, 'v116_close_only', prod)
    assert np.array_equal(mixed[inside], prod[inside]) and np.array_equal(mixed[~inside], test.q.to_numpy()[~inside])


def test_training_must_precede_the_scored_week():
    with pytest.raises(ValueError, match='current/future'): o.fit_arm(mixed_fixture(), 2022, 11, 'close_fit')


def test_preregistered_verdicts():
    assert o.verdict_q1({'interval': [.001, .05]}) == 'supported'
    assert o.verdict_q1({'interval': [-.05, -.001]}) == 'contradicted'
    assert o.verdict_q1({'interval': [-.01, .02]}) == 'unresolved'
    c, d = {'per_bet': .01, 'interval': [-.01, .03]}, {'mean': .002, 'interval': [-.001, .005]}
    assert o.verdict_q2(c, d) == 'favored, unresolved'
    assert o.verdict_q2({**c, 'interval': [.001, .03]}, {**d, 'interval': [.0001, .005]}) == 'supported'
    assert o.verdict_q2({**c, 'per_bet': 0.}, d) == 'not supported'
    assert o.verdict_q2(c, {**d, 'mean': -.001}) == 'not supported'


def test_protected_output_guard():
    with pytest.raises(ValueError, match='production outputs'): o.run(o.ROOT/'data'/'oos')


def test_committed_results_follow_the_protocol():
    out = o.OUT
    info = json.loads((out/'results.json').read_text())
    assert info['protocol'] == 'research/OUT_OF_SAMPLE_2017_2020.md' and info['all_training_cutoffs_prior']
    assert info['all_references_prior_week'] and info['confidence_level'] == .975
    assert set(info['verdicts']) == {'Q1', 'Q2'}
    held = pd.read_csv(out/'predictions.csv')
    assert held.season.between(2017, 2020).all()
    inside = o.close(held)
    assert np.allclose(held.close_fit[~inside], held.q[~inside], rtol=0, atol=1e-12)
    assert np.allclose(held.v116_close_only[inside], held.production[inside], rtol=0, atol=1e-12)
    audit = pd.read_csv(out/'fit_audit.csv')
    assert len(audit) == 2*len(held[['season', 'week']].drop_duplicates())


def pbp_game(rows, gid='2014_04_GB_CHI'):
    return pd.DataFrame([{'game_id': gid, 'play_id': pid, 'season_type': 'REG', 'qtr': qtr,
                          'game_seconds_remaining': left, 'total_home_score': h, 'total_away_score': a, 'sp': 1}
                         for pid, qtr, left, h, a in rows])


def one_game(home=7, away=38):
    return pd.DataFrame({'game_id': ['2014_04_GB_CHI'], 'home_team': ['CHI'], 'away_team': ['GB'],
                         'home_score': [home], 'away_score': [away], 'result': [home-away]})


def test_peak_repair_only_for_a_misstamped_clock():
    # Play 30 is stamped early in Q3, but its play ID and the scores place it after play 25.
    rows = [(10, 1, 3000, 7, 0), (20, 2, 2000, 7, 21), (25, 3, 1500, 7, 24), (30, 3, 1790, 7, 31), (40, 4, 800, 7, 38)]
    pbp, game = pbp_game(rows), one_game()
    with pytest.raises(ValueError, match='not monotone'): o.STRICT_PEAKS(pbp, game)
    o.PEAK_REPAIRS.clear()
    out = o.repaired_score_peaks(pbp, game).set_index('team')
    assert (out.loc['CHI', 'max_lead'], out.loc['CHI', 'max_deficit']) == (7., 31.)
    assert (out.loc['GB', 'max_lead'], out.loc['GB', 'max_deficit']) == (31., 7.)
    assert [r['game_id'] for r in o.PEAK_REPAIRS] == ['2014_04_GB_CHI']
    # A wrong official final, or a play-ID order that is not monotone either, is still rejected.
    with pytest.raises(ValueError, match='official score'): o.repaired_score_peaks(pbp, one_game(away=35))
    bad = pbp_game(rows[:3]+[(30, 3, 1790, 7, 20), (40, 4, 800, 7, 38)])
    with pytest.raises(ValueError, match='not monotone'): o.repaired_score_peaks(bad, game)
    # Clean games match production exactly and are not logged.
    clean = pbp_game([(10, 1, 3000, 7, 0), (20, 2, 2000, 7, 21), (40, 4, 800, 7, 38)])
    o.PEAK_REPAIRS.clear()
    pd.testing.assert_frame_equal(o.repaired_score_peaks(clean, game), o.STRICT_PEAKS(clean, game))
    assert o.PEAK_REPAIRS == []
