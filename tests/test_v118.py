"""v1.18: the favorite penalty applied at the source, and the v1.16 shadow lock.

v1.19 is production from 2026-11-03; these tests run under v1.18's own identity (V118_RECIPE)."""
import datetime as dt
import json
import numpy as np
import pandas as pd
import pytest
import nfl_model as m
from test_product_production import fixture

ASOF = dt.datetime(2023, 9, 9, tzinfo=dt.timezone.utc)
V118 = 'boxscore-composite-v1.18'


@pytest.fixture(autouse=True)
def as_v118():
    with m.revision_identity(V118, m.V118_RECIPE):
        yield


def lockable(train, board, fit):
    board = board.copy()
    board['result'] = np.nan; board['gameday'] = '2023-09-10'; board['gametime'] = '13:00'
    board['homefield_wp'] = .54; board['spread_line'] = 1.
    board['home_moneyline'] = [-300., -120., 150., -180.]; board['away_moneyline'] = [240., 100., -170., 155.]
    board['q'] = m.market_ml_wp(board); board['market_wp'] = board.q
    board['home_injury_report'] = 'final'; board['away_injury_report'] = 'final'
    for col in ('pass_ho', 'pass_ad', 'pass_ao', 'pass_hd'): board[col] = .7
    board['model_wp'] = m.apply_fit(board, fit); board['model_wp_v116'] = m.apply_fit(board, fit, raw=True)
    return board


def test_penalty_applies_at_the_source_without_changing_the_fit():
    train, test = fixture()
    fit18 = m.fit_composite(train, m.V118_RECIPE, 2023, 1)
    fit16 = m.fit_composite(train, m.LEGACY_PRODUCT_RECIPE, 2023, 1)
    assert fit18['beta'] == fit16['beta'] and fit18['scale'] == fit16['scale']      # the penalty never touches fitting
    raw = m.apply_fit(test, fit16)
    assert np.allclose(m.apply_fit(test, fit18, raw=True), raw, rtol=0, atol=1e-15)
    assert np.allclose(m.apply_fit(test, fit18), m.favorite_penalized_wp(raw, test.q), rtol=0, atol=1e-12)
    assert np.array_equal(m.apply_fit(test, fit18) > .5, raw > .5)                   # picks never change
    p, score, _ = m.apply_fit(test, fit18, True)
    assert np.allclose(m.expit(score), p)


def test_v119_is_production_and_keeps_v118_and_v116_identities():
    with m.revision_identity('boxscore-composite-v1.19', dict(m.V118_RECIPE, terms=list(m.CORE_TERMS))):
        sig19 = m.config_signature()[0]
        key19 = m.recipe_key(m.PRODUCT_RECIPE)
    assert not sig19.startswith(('73636f30', '9dad9b9a')) and key19.endswith('_t10_f8ff0b')
    assert key19.startswith(m.recipe_key(m.V118_RECIPE))


def test_model_range_bounds_follow_the_penalty():
    train, test = fixture()
    fit = m.fit_composite(train, m.V118_RECIPE, 2023, 1)
    se, lo, hi = m.offset_band(train, fit, test)
    p = m.apply_fit(test, fit)
    assert np.all(lo <= p+1e-12) and np.all(p <= hi+1e-12) and np.all(np.isfinite(se))
