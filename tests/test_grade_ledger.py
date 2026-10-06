import datetime as dt

import numpy as np
import pandas as pd

import grade_ledger as g


def rec(gid, wp, mkt, exp="e", rev="r1", week=5):
    return {"experiment": exp, "revision": rev, "game_id": gid, "season": 2026, "week": week,
            "home": "H" + gid, "away": "A" + gid, "generated_utc": "2026-10-10T12:00:00+00:00",
            "kickoff_utc": "2026-10-11T17:00:00+00:00", "model_wp": wp, "market_wp": mkt,
            "homefield_wp": .55, "spread_line": 3.0, "injury_report": {"home": "final", "away": "final"}}


RESULTS = pd.DataFrame({"game_id": ["a", "b", "c", "d"], "away_score": [10, 24, 17, np.nan],
                        "home_score": [20, 21, 17, np.nan], "result": [10, -3, 0, np.nan]})


def test_statuses_hits_and_scores():
    out = g.grade([rec("a", .7, .6), rec("b", .6, .4), rec("c", .5, .5), rec("d", .4, .45), rec("e", .6, None)], RESULTS)
    s = out.set_index("game_id")
    assert s.loc["a", "status"] == "graded" and s.loc["a", "model_hit"] == 1 and s.loc["a", "market_hit"] == 1
    assert s.loc["b", "model_hit"] == 0 and s.loc["b", "market_hit"] == 1
    assert s.loc["c", "status"] == "tie" and np.isnan(s.loc["c", "model_log_loss"])
    assert s.loc["d", "status"] == "pending" and s.loc["e", "status"] == "pending"
    assert np.isclose(s.loc["a", "model_log_loss"], -np.log(.7))
    assert np.isclose(s.loc["b", "market_brier"], .16)
    assert s.loc["a", "lead_hours"] == 29.0
    assert list(out.columns) == g.COLUMNS


def test_summary_scores_one_row_set():
    out = g.grade([rec("a", .7, .6), rec("b", .6, .4), rec("c", .5, .5), rec("d", .4, .45)], RESULTS)
    sm = g.summary(out)
    assert sm["scored"] == 2 and sm["pending"] == 1 and sm["ties"] == 1
    assert (sm["model_wins"], sm["model_losses"], sm["market_wins"], sm["market_losses"]) == (1, 1, 2, 0)
    d = (-np.log(.6) + np.log(.7)) + (-np.log(.6) + np.log(.4))
    assert np.isclose(sm["ll_gain"], d / 2)


def test_report_and_outputs(tmp_path):
    out = g.grade([rec("a", .7, .6), rec("b", .6, .4, rev="r0")], RESULTS)
    g.write_outputs(out, tmp_path, now=dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc))
    text = (tmp_path / "ledger_report.txt").read_text()
    assert "== r1:" in text and "== r0:" in text and "native forward observations only" in text
    assert pd.read_csv(tmp_path / "forward_ledger.csv").shape[0] == 2


def test_empty_ledger(tmp_path):
    out = g.grade([], RESULTS)
    assert out.empty and g.summary(out)["snapshots"] == 0
    g.write_outputs(out, tmp_path)
    assert "No snapshots" in (tmp_path / "ledger_report.txt").read_text()
