import datetime as dt

import numpy as np
import pandas as pd

import grade_ledger as g


def rec(gid, wp, mkt, exp="e", rev="r1", week=5, hm=-150, am=130, sp=3.0):
    return {"experiment": exp, "revision": rev, "game_id": gid, "season": 2026, "week": week,
            "home": "H" + gid, "away": "A" + gid, "generated_utc": "2026-10-10T12:00:00+00:00",
            "kickoff_utc": "2026-10-11T17:00:00+00:00", "model_wp": wp, "market_wp": mkt,
            "homefield_wp": .55, "spread_line": sp, "home_moneyline": hm, "away_moneyline": am,
            "injury_report": {"home": "final", "away": "final"}}


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


def test_flat_roi_at_saved_moneyline_with_same_row_baseline():
    # a: model home (-150) wins +0.667; b: model away (+130), away won -> +1.3; c: tie -> push 0;
    # e: no saved price -> no bet; d: pending -> no units yet.
    out = g.grade([rec("a", .7, .6), rec("b", .4, .6), rec("c", .6, .6), rec("d", .6, .6),
                   rec("e", .6, .6, hm=None, am=None)], RESULTS)
    s = out.set_index("game_id")
    assert s.loc["a", "bet_team"] == "Ha" and s.loc["a", "bet_result"] == "W" and np.isclose(s.loc["a", "units"], 2 / 3)
    assert s.loc["b", "bet_team"] == "Ab" and np.isclose(s.loc["b", "units"], 1.3) and s.loc["c", "bet_result"] == "P"
    assert np.isnan(s.loc["d", "units"]) and np.isnan(s.loc["e", "units"]) and s.loc["e", "bet_team"] == "He"
    r = g.summary(out)["roi"]
    assert (r["bets"], r["wins"], r["losses"], r["pushes"]) == (3, 2, 0, 1)
    assert np.isclose(r["units"], 2 / 3 + 1.3) and np.isclose(r["roi"], (2 / 3 + 1.3) / 3)
    assert np.isclose(r["fav_units"], 2 / 3 - 1 + 0)  # market favorite = home -150 on all three
    assert r["null_roi"] < 0  # market-correct null is negative by the hold
    bands = g.roi_bands(out).set_index("group")
    assert bands.loc["All games", "bets"] == 3 and bands.loc["−174 to −130", "bets"] == 2
    assert "HEADLINE flat 1u" in g.report_text(out)


def test_model_spread_and_ats_diagnostic():
    from scipy.special import ndtr
    even = float(ndtr(3 / g.m.MARKET_SIGMA))  # model spread equals the 3-point line: no side
    # a: model +6.5 vs 3 -> home; home won by 10 -> W.  b: model -3.1 -> away; home lost by 3 -> W.
    # c: model +3.1 -> home; tie, home 3 short of the line -> L.  d: pending -> no result.
    # e: line 10, home won by 10 -> push.  f: model equals the line -> no side.  g: no line -> no side.
    res = pd.concat([RESULTS, pd.DataFrame({"game_id": ["e", "f", "g"], "away_score": [10, 10, 10],
                                            "home_score": [20, 20, 20], "result": [10, 10, 10]})])
    out = g.grade([rec("a", .7, .6), rec("b", .4, .6), rec("c", .6, .6), rec("d", .6, .6),
                   rec("e", .9, .8, sp=10.0), rec("f", even, .6), rec("g", .6, None, sp=None)], res)
    s = out.set_index("game_id")
    assert np.isclose(s.loc["a", "model_spread"], g.m.MARKET_SIGMA * 0.5244005127080407)
    assert np.isclose(s.loc["a", "spread_gap"], s.loc["a", "model_spread"] - 3)
    assert (s.loc["a", "ats_side"], s.loc["a", "ats_result"]) == ("home", "W")
    assert (s.loc["b", "ats_side"], s.loc["b", "ats_result"]) == ("away", "W")
    assert (s.loc["c", "ats_side"], s.loc["c", "ats_result"]) == ("home", "L")
    assert s.loc["d", "ats_side"] == "home" and s.loc["d", "ats_result"] == ""
    assert s.loc["e", "ats_result"] == "P"
    assert s.loc["f", "ats_side"] == "" and s.loc["f", "ats_result"] == ""
    assert s.loc["g", "ats_side"] == "" and np.isnan(s.loc["g", "spread_gap"])
    a = g.ats_summary(out)
    assert (a["wins"], a["losses"], a["pushes"]) == (2, 1, 1)
    big = g.ats_summary(out, g.ATS_GAP_POINTS)  # a (+3.5), b (-6.1), e (+5.9) qualify; c (+0.1) does not
    assert (big["wins"], big["losses"], big["pushes"]) == (2, 0, 1) and big["lo"] < big["hi"]
    text = g.report_text(out)
    assert "Diagnostic, not the goal metric" in text and "|gap| >= 3 pts  2-0-1" in text
    # The headline still grades every priced, final game at the moneyline (a, b, c push, e, f, g),
    # including g, which has no spread and so no ATS side.
    assert g.summary(out)["roi"]["bets"] == 6


def test_no_ats_lines_before_any_decided_game():
    out = g.grade([rec("d", .6, .6)], RESULTS)
    assert out.loc[0, "ats_result"] == "" and "Diagnostic, not the goal metric" not in g.report_text(out)
