"""v1.18: the favorite penalty applied at the source, and the v1.16 shadow lock."""
import datetime as dt
import json
import numpy as np
import pandas as pd
import pytest
import nfl_model as m
from test_product_production import fixture

ASOF = dt.datetime(2023, 9, 9, tzinfo=dt.timezone.utc)


@pytest.fixture(autouse=True)
def legacy_v118_identity(monkeypatch):
    """These are frozen v1.18 contracts, independent of current production."""
    monkeypatch.setattr(m, 'SHADOW_LOCK', True)
    with m.revision_identity('boxscore-composite-v1.18',
                             dict(m.LEGACY_PRODUCT_RECIPE, favorite_penalty=m.FAVORITE_PENALTY)):
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
    fit18 = m.fit_composite(train, m.PRODUCT_RECIPE, 2023, 1)
    fit16 = m.fit_composite(train, m.LEGACY_PRODUCT_RECIPE, 2023, 1)
    assert fit18['beta'] == fit16['beta'] and fit18['scale'] == fit16['scale']      # the penalty never touches fitting
    raw = m.apply_fit(test, fit16)
    assert np.allclose(m.apply_fit(test, fit18, raw=True), raw, rtol=0, atol=1e-15)
    assert np.allclose(m.apply_fit(test, fit18), m.favorite_penalized_wp(raw, test.q), rtol=0, atol=1e-12)
    assert np.array_equal(m.apply_fit(test, fit18) > .5, raw > .5)                   # picks never change
    p, score, _ = m.apply_fit(test, fit18, True)
    assert np.allclose(m.expit(score), p)


def test_v118_and_v116_have_distinct_identities():
    assert m.recipe_key(m.PRODUCT_RECIPE).endswith('_fp0.2')
    assert m.recipe_key(m.SHADOW_RECIPE) == m.recipe_key(m.LEGACY_PRODUCT_RECIPE)
    sig18 = m.config_signature()[0]
    with m.revision_identity(m.SHADOW_REVISION, m.SHADOW_RECIPE):
        sig16 = m.config_signature()[0]
        assert m.REVISION == 'boxscore-composite-v1.16'
    assert sig16.startswith('9dad9b9a') and sig18 != sig16
    assert m.REVISION == 'boxscore-composite-v1.18' and m.PRODUCT_RECIPE['favorite_penalty'] == m.FAVORITE_PENALTY


def shadow_state(tmp_path, monkeypatch, season=2023):
    monkeypatch.setattr(m, 'STATE_DIR', str(tmp_path))
    with m.revision_identity(m.SHADOW_REVISION, m.SHADOW_RECIPE):
        sig, cfg = m.config_signature()
        (tmp_path/m.frozen_recipe_name(season)).write_text(json.dumps(
            {'revision': m.REVISION, 'season': season, 'recipe': m.SHADOW_RECIPE, 'config_signature': sig,
             'config': cfg, 'selection_max_season': season-1}))
    return sig


def test_shadow_locks_v116_beside_v118(tmp_path, monkeypatch):
    sig16 = shadow_state(tmp_path, monkeypatch)
    train, board = fixture(); fit = m.fit_composite(train, m.PRODUCT_RECIPE, 2023, 1)
    board = lockable(train, board, fit)
    rec18 = {'config_signature': m.config_signature()[0], 'recipe': m.PRODUCT_RECIPE, 'season': 2023}
    _, n18 = m.record_forward(board, fit, rec18, asof=ASOF)
    n16 = m.record_shadow(board, fit, None, 2023, asof=ASOF)
    assert n18 == n16 == 4
    rows = [json.loads(l) for l in (tmp_path/'forward_predictions.jsonl').read_text().splitlines()]
    v18 = {r['game_id']: r for r in rows if r['revision'] == 'boxscore-composite-v1.18'}
    v16 = {r['game_id']: r for r in rows if r['revision'] == 'boxscore-composite-v1.16'}
    assert all(r['experiment'].startswith(sig16) for r in v16.values())
    assert not any(r['experiment'].startswith(sig16) for r in v18.values())
    for g, r in v16.items():
        assert r['model_wp'] == pytest.approx(board.set_index('game_id').model_wp_v116[g])
        assert v18[g]['model_wp'] == pytest.approx(m.favorite_penalized_wp([r['model_wp']], [r['market_no_vig_wp']])[0])
        assert (v18[g]['model_wp'] > .5) == (r['model_wp'] > .5)
        assert 'favorite_penalty' not in r['recipe'] and v18[g]['recipe']['favorite_penalty'] == m.FAVORITE_PENALTY
    assert m.REVISION == 'boxscore-composite-v1.18'                                  # identity restored
    assert m.record_shadow(board, fit, None, 2023, asof=ASOF) == 0                     # first snapshot only


def test_shadow_off_or_without_raw_column_writes_nothing(tmp_path, monkeypatch):
    shadow_state(tmp_path, monkeypatch)
    train, board = fixture(); fit = m.fit_composite(train, m.PRODUCT_RECIPE, 2023, 1)
    board = lockable(train, board, fit)
    assert m.record_shadow(board.drop(columns='model_wp_v116'), fit, None, 2023, asof=ASOF) == 0
    monkeypatch.setattr(m, 'SHADOW_LOCK', False)
    assert m.record_shadow(board, fit, None, 2023, asof=ASOF) == 0
    assert not (tmp_path/'forward_predictions.jsonl').exists()


def test_shadow_refuses_a_tampered_raw_forecast(tmp_path, monkeypatch):
    shadow_state(tmp_path, monkeypatch)
    train, board = fixture(); fit = m.fit_composite(train, m.PRODUCT_RECIPE, 2023, 1)
    board = lockable(train, board, fit)
    with pytest.raises(ValueError, match='does not match'):
        m.record_shadow(board.assign(model_wp_v116=board.model_wp), fit, None, 2023, asof=ASOF)
    assert m.REVISION == 'boxscore-composite-v1.18'                                  # restored after an error


def test_model_range_bounds_follow_the_penalty():
    train, test = fixture()
    fit = m.fit_composite(train, m.PRODUCT_RECIPE, 2023, 1)
    se, lo, hi = m.offset_band(train, fit, test)
    p = m.apply_fit(test, fit)
    assert np.all(lo <= p+1e-12) and np.all(p <= hi+1e-12) and np.all(np.isfinite(se))
