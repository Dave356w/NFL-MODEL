"""H15 small-band filter, side orientation, de-vig, cutoff split and verdict gate."""
import numpy as np
import pandas as pd
import pytest

from research import h15_small_favorites as h
from research import soft_band_distributions as sb


@pytest.fixture(scope='module')
def fit():
    games = pd.read_csv(sb.INPUT)
    return sb.fit_prior(sb.clean(games)[lambda g: g.season < 2026], 2026)


def row(game, wp, result, home_ml=-120, away_ml=100, revision=h.REVISION, status='graded',
        generated='2026-11-01T12:00:00Z'):
    return dict(game_id=game, revision=revision, status=status, generated_utc=generated, model_wp=wp,
                result=result, home_moneyline=home_ml, away_moneyline=away_ml)


def test_filter_keeps_only_small_decided_v118_rows(fit):
    led = pd.DataFrame([row('a', .55, 3), row('b', .75, 3), row('c', .55, 0), row('d', .55, 3, revision='x'),
                        row('e', .55, 3, status='pending'), row('f', .55, 3, home_ml=np.nan)])
    d = h.rows(led, fit)
    assert list(d.game_id) == ['a']


def test_orientation_devig_and_units(fit):
    d = h.rows(pd.DataFrame([row('a', .45, -7, home_ml=-120, away_ml=100)]), fit)
    r = d.iloc[0]
    ih, ia = 120 / 220, 100 / 200
    assert r.side == 'away' and r.y == 1.
    assert np.isclose(r.q, ia / (ih + ia)) and np.isclose(r.model, .55)
    assert np.isclose(r.units, 1.) and r.fav_units == -1.  # away at +100 won; home was the market favorite
    assert .55 < r.soft < .65 and .55 < r.hard < .65


def test_first_snapshot_per_game_is_used(fit):
    led = pd.DataFrame([row('a', .55, 3, generated='2026-11-01T12:00:00Z'),
                        row('a', .45, 3, generated='2026-11-01T10:00:00Z')])
    assert h.rows(led, fit).iloc[0].side == 'away'


def test_verdict_gate():
    assert h.verdict(dict(n=149, excess=.2, se=.04)).startswith('interim')
    assert h.verdict(dict(n=150, excess=0., se=.04)) == 'falsified'
    assert h.verdict(dict(n=150, excess=.09, se=.04)).startswith('supported')
    assert h.verdict(dict(n=150, excess=.05, se=.04)) == 'unresolved'
    assert h.verdict(dict(n=40, excess=-.01, se=.08), final=True) == 'falsified'
