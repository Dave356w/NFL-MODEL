"""H10 orientation, capture join, quote validity, scoring sign and verdict thresholds."""
import numpy as np
import pandas as pd

from research import band_ladder_score as h
from research import soft_band_distributions as sb


def point_mass(margin):
    p = np.zeros(len(sb.GRID))
    p[int(margin) + 100] = 1.
    return p


def test_over_orients_home_and_away_ladders():
    p = point_mass(5)  # home wins by 5
    assert h.over(p, True, 4.5) == 1. and h.over(p, True, 5.5) == 0.
    assert h.over(p, False, 1.5) == 0.  # away never wins
    q = point_mass(-8)  # away wins by 8
    assert h.over(q, False, 7.5) == 1. and h.over(q, False, 8.5) == 0.
    assert h.over(q, True, 0.5) == 0.


def test_capture_matches_ledger_join():
    caps = [{'captured_utc': '2026-10-25T10:00:00+00:00'}, {'captured_utc': '2026-10-25T12:00:00+00:00'}]
    assert h.capture(caps, '2026-10-25T11:00:00+00:00') == (caps[1], False)
    assert h.capture(caps, '2026-10-25T13:00:00+00:00') == (caps[1], True)
    assert h.capture([], '2026-10-25T13:00:00+00:00') == (None, False)


def test_valid_quote_rejects_empty_crossed_and_wide_books():
    assert h.valid_quote(.48, .49) and h.valid_quote(.40, .45)
    assert not h.valid_quote(0., .01)
    assert not h.valid_quote(.5, .4)
    assert not h.valid_quote(.40, .46)
    assert not h.valid_quote(.98, 1.)


def rungs(challenger, kalshi=.5, games=4):
    rows = []
    for g in range(games):
        for y in (1., 0.):
            rows.append(dict(game_id=f'g{g}', y=y, kalshi=kalshi, band=challenger(y)))
    return pd.DataFrame(rows)


def test_score_sign_and_game_weighting():
    better = h.score(rungs(lambda y: .8 if y else .2))
    assert better['games'] == 4 and better['rungs'] == 8 and better['gain'] > 0
    worse = h.score(rungs(lambda y: .2 if y else .8))
    assert worse['gain'] < 0
    same = h.score(rungs(lambda y: .5))
    assert abs(same['gain']) < 1e-12


def test_clip_bounds_a_zero_probability_miss():
    r = h.score(rungs(lambda y: 0. if y else 0.))
    assert np.isfinite(r['gain'])
    assert np.isclose(r['challenger_loss'], (-np.log(.005) - np.log(.995)) / 2)


def test_verdict_waits_for_100_games_then_applies_the_gate():
    assert h.verdict(dict(games=99, gain=.1, lo=.05)).startswith('interim')
    assert h.verdict(dict(games=100, gain=-.001, lo=-.01)).startswith('falsified')
    assert h.verdict(dict(games=100, gain=0., lo=-.01)).startswith('falsified')
    assert h.verdict(dict(games=100, gain=.01, lo=.001)).startswith('supported')
    assert h.verdict(dict(games=100, gain=.01, lo=-.001)) == 'unresolved'
