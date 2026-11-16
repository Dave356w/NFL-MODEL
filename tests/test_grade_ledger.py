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


CLOSE = pd.DataFrame({"game_id": ["a", "b", "d", "f"], "away_score": [10, 24, np.nan, 13],
                      "home_score": [20, 21, np.nan, 20], "result": [10, -3, np.nan, 7],
                      "close_home_moneyline": [-200, -200, -300, np.nan], "close_away_moneyline": [170, 170, 250, np.nan]})


def h12(gid, wp, week, season=2026, rev=None, exp=None):
    r = rec(gid, wp, .6, rev=rev or g.H12_REVISION, exp=exp or g.H12_EXPERIMENT + str(season), week=week)
    return {**r, "season": season}


H9_REV = "boxscore-composite-v1.18"


def _h9_games(n, weeks, win, pending=(), ties=(), prices=(-300, -150, 130, 200)):
    """n H9 games over `weeks` weeks from week 6; win(d, rng) gives home wins for the H9 rows d. Games
    listed in `pending` get no result; games in `ties` end level."""
    rng = np.random.default_rng(0)
    hm = rng.choice(list(prices), n)
    am = np.where(hm < 0, np.abs(hm) - 20, -(hm + 20))
    sp = rng.normal(0, 5, n).round(1)
    recs = [rec(f"g{i}", .6, .6, rev=H9_REV, week=6 + i % weeks, hm=float(hm[i]), am=float(am[i]), sp=float(sp[i]))
            for i in range(n)]
    d = g.h9_rows(g.grade(recs, pd.DataFrame({"game_id": [], "away_score": [], "home_score": [], "result": []})))
    w = win(d, rng)
    res = pd.DataFrame({"game_id": d.game_id, "away_score": np.where(w, 10, 20), "home_score": np.where(w, 20, 10),
                        "result": np.where(w, 10, -10)})
    res.loc[res.game_id.isin([f"g{i}" for i in ties]), ["away_score", "home_score", "result"]] = [17, 17, 0]
    return g.grade(recs, res[~res.game_id.isin([f"g{i}" for i in pending])])


def _coin(d, rng):
    return rng.random(len(d)) < .5


