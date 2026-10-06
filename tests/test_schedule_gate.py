from datetime import datetime, timedelta, timezone
from pathlib import Path

import schedule_gate as sg

NOW = datetime(2026, 10, 10, 15, 0, tzinfo=timezone.utc)  # Sat 11:00 ET


def game(gid, ko_et, result=""):
    return {"game_id": gid, "game_type": "REG", "gameday": ko_et[:10], "gametime": ko_et[11:16], "result": result}


def test_unrecorded_game_inside_30h_is_due_until_recorded():
    games = [game("g1", "2026-10-11T13:00")]  # Sun 1pm ET = 26h ahead
    assert sg.due_games(games, NOW, set()) == [("g1", "awaiting first ledger snapshot")]
    assert sg.due_games(games, NOW, {"g1"}) == []


def test_final_refresh_runs_even_when_recorded_and_not_inside_15_minutes():
    soon = NOW + timedelta(minutes=90)
    et = soon.astimezone(sg.ET).strftime("%Y-%m-%dT%H:%M")
    assert sg.due_games([game("g", et)], NOW, {"g"}) == [("g", "final pregame refresh")]
    late = (NOW + timedelta(minutes=10)).astimezone(sg.ET).strftime("%Y-%m-%dT%H:%M")
    assert sg.due_games([game("g", late)], NOW, set()) == []


def test_finished_far_and_postseason_games_are_not_due():
    games = [game("done", "2026-10-11T13:00", result="3"),
             game("far", "2026-10-13T20:15"),
             dict(game("post", "2026-10-11T13:00"), game_type="WC")]
    assert sg.due_games(games, NOW, set()) == []


def test_decision_paths():
    assert sg.decision("push", "", NOW)[0]
    assert sg.decision("schedule", sg.DAILY_CRON, NOW)[0]
    run, season, reason = sg.decision("schedule", "41 * * * *", NOW, games=[], recorded=set())
    assert not run and season == 2026
    assert sg.decision("schedule", "41 * * * *", NOW, games=[game("g1", "2026-10-11T13:00")], recorded=set())[0]


def test_lookup_failure_fails_open(monkeypatch):
    def boom(*a, **k):
        raise OSError("down")
    monkeypatch.setattr(sg, "fetch_games", boom)
    run, _, reason = sg.decision("schedule", "41 * * * *", NOW)
    assert run and "fail-open" in reason


def test_revision_is_read_from_the_model():
    import nfl_model
    assert sg.current_revision() == nfl_model.REVISION


def test_recorded_games_filters_by_revision(tmp_path):
    p = tmp_path / "l.jsonl"
    p.write_text('{"revision":"a","game_id":"x"}\n{"revision":"b","game_id":"y"}\n')
    assert sg.recorded_games("a", p) == {"x"}
    assert sg.recorded_games("a", tmp_path / "missing.jsonl") == set()


def test_build_workflow_carries_the_gate_crons():
    text = (Path(__file__).resolve().parents[1] / ".github/workflows/build.yml").read_text()
    assert f"cron: '{sg.DAILY_CRON}'" in text
    assert "group: site-build" in text and "cancel-in-progress: false" in text
    assert "python schedule_gate.py" in text and "python build_site.py" in text
    # the commit step must survive a failed render so a written snapshot is kept
    assert "if: ${{ !cancelled() }}" in text
