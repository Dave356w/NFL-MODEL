"""The model's own synthetic regression suite (nfl_model.self_test)."""
import os

import nfl_model as m


def test_self_test_passes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # self_test writes selftest_board.html to the cwd
    box, sched = m.self_test()
    assert len(box) and len(sched)


def test_env_config_only_overrides_what_is_set(monkeypatch):
    saved = {k: getattr(m, k) for k in ("STATE_DIR", "CACHE_DIR", "SEASON", "CURRENT_WEEK")}
    try:
        m.apply_env_config({"NFL_STATE_DIR": "data", "NFL_WEEK": "5", "NFL_SEASON": ""})
        assert m.STATE_DIR == "data" and m.CURRENT_WEEK == 5 and m.SEASON == saved["SEASON"]
        assert str(m.state_dir()) == "data"
    finally:
        for k, v in saved.items():
            setattr(m, k, v)


def test_self_test_never_touches_configured_state_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(m, "STATE_DIR", str(tmp_path / "data"))
    m.self_test()
    assert not (tmp_path / "data").exists()
    assert m.STATE_DIR == str(tmp_path / "data")
