import numpy as np
import pandas as pd
import pytest
import nfl_model as m
from test_score_peaks import boxes_and_schedule


def test_compact_profiles_preserve_every_shared_value_and_skip_adjustment(monkeypatch):
    box, sched = boxes_and_schedule()
    full = m.lagged_features(box, sched, 8.)
    def fail(*args, **kwargs): raise AssertionError('Unused opponent adjustment ran')
    monkeypatch.setattr(m, 'opponent_adjust', fail)
    compact = m.lagged_features(box, sched, 8., profile_families=('rates_core',))
    pd.testing.assert_frame_equal(compact, full[compact.columns], check_exact=True)
    assert len(compact.columns) < len(full.columns)
    assert not any('rates_core_adj' in c for c in compact)
    assert all(c in compact for c in m.feature_names(m.PRODUCT_RECIPE['family']))
    with pytest.raises(ValueError, match='Unknown'):
        m.lagged_features(box, sched, 8., profile_families=('typo',))


def test_runtime_modes_keep_statistical_identity():
    sig = m.config_signature()[0]
    assert m.profile_half_lives('full') == m.TEAM_HALF_LIVES
    assert m.profile_half_lives('production') == (8., 16.)
    with pytest.raises(ValueError, match='NFL_PROFILE_MODE'):
        m.profile_half_lives('typo')
    assert m.config_signature()[0] == sig


def test_compact_cache_does_not_require_unused_h4(tmp_path, monkeypatch):
    f = pd.DataFrame({'season': [2022], 'game_id': ['g'], 'pass_product': [0.]})
    monkeypatch.setattr(m, 'CACHE_DIR', str(tmp_path))
    calls = []
    def walk(features, year):
        calls.append(year)
        assert set(features) == {8., 16.}
        return pd.DataFrame({'game_id': ['g']})
    monkeypatch.setattr(m, 'walk_forward_product', walk)
    features = {8.: f, 16.: f.copy()}
    assert m.cached_grid(features, 2023).game_id.tolist() == ['g']
    assert m.cached_grid(features, 2023).game_id.tolist() == ['g']
    assert len(calls) == 1
