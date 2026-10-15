"""Test 46 (research/ML_SPREAD_2006_12.md): disagreement definition, fits, rule and verdict."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import ml_spread_2006_12 as ms  # noqa: E402


def game(home_ml, away_ml, spread, result=3, gid='g'):
    return {'game_id': gid, 'season': 2010, 'week': 1, 'home_moneyline': home_ml, 'away_moneyline': away_ml,
            'spread_line': spread, 'result': result}


def test_disagreement_sign_follows_which_market_is_more_bullish_on_home():
    d = ms.disagreement(pd.DataFrame([game(-300, 250, 3.), game(-130, 110, 7.), game(-150, 130, -3.)]))
    assert d.dis[0] > 0                  # moneyline ~73% home vs spread +3 ~60%: moneyline more bullish on home
    assert d.dis[1] < 0                  # moneyline ~55% vs spread +7 ~72%: spread more bullish on home
    assert d.q_s[2] < .5 and d.dis[2] > 0  # positive spread = home favored; -3 means away favored


def test_priced_drops_unpriced_games_and_marks_ties():
    rows = [game(-150, 130, 3., 7, 'a'), game(np.nan, 130, 3., 7, 'b'), game(-150, 130, np.nan, 7, 'c'),
            game(-150, 130, 3., np.nan, 'd'), game(-150, 130, 3., 0, 'e')]
    d = ms.priced(pd.DataFrame(rows))
    assert list(d.game_id) == ['a', 'e'] and d.y[0] == 1. and np.isnan(d.y[1])


def test_free_slope_fit_recovers_a_known_negative_coefficient():
    rng = np.random.default_rng(1)
    n = 20000
    lq = rng.normal(0, .8, n); dis = rng.normal(0, .1, n)
    y = (rng.random(n) < expit(.1+1.0*lq-0.9*dis)).astype(float)
    d = pd.DataFrame({'q': expit(lq), 'dis': dis, 'y': y, 'cluster': rng.integers(0, 300, n)})
    r = ms.fit_free(d)
    assert abs(r['b']+0.9) < 3*r['se'] and abs(r['b_logit_q']-1.0) < 3*r['se_logit_q']
    null = d.assign(y=(rng.random(n) < expit(.1+1.0*lq)).astype(float))
    assert abs(ms.fit_free(null)['b']) < 3*ms.fit_free(null)['se']   # negative control: no dis effect


def test_verdict_rule_matches_the_protocol():
    assert ms.verdict(0.0, .5) == 'falsified for 2006-2012' and ms.verdict(.3, .5) == 'falsified for 2006-2012'
    assert ms.verdict(-1.1, .5) == 'replicated'
    assert ms.verdict(-.4, .5) == 'consistent sign, unresolved'


def test_rule_backs_the_side_the_spread_likes_more_and_grades_at_its_moneyline():
    d = ms.priced(pd.DataFrame([game(-300, 250, 3., -4, 'away_side'), game(-130, 110, 7., 10, 'home_side'),
                                game(-150, 130, 2.5, 10, 'small')]))
    x = ms.rule_bets(d).set_index('game_id')
    assert 'small' not in x.index                                    # |dis| below T: no bet
    assert x.loc['away_side', 'side'] == 'away' and np.isclose(x.loc['away_side', 'units'], 2.5)
    assert x.loc['home_side', 'side'] == 'home' and np.isclose(x.loc['home_side', 'units'], 100/130)
    assert (x.null_ev < 0).all()                                     # negative by the hold


def test_discovery_eras_reproduce_the_numbers_the_protocol_cites(tmp_path):
    import ml_spread_discovery_eras as de
    r = de.run(tmp_path/'eras.json')
    assert [round(r[e]['b'], 2) for e in de.ERAS] == [-0.86, -0.67, -0.94, -0.97]   # ML_SPREAD_2006_12.md
    assert r['2013-2026 (one block)']['n'] == 3472 and r['2013-2026 (one block)']['b'] < 0
