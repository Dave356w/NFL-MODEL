"""v1.14.2 reporting: the model-vs-favorite disagreement contrast and pre-registered H5."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

import build_site as b
import grade_ledger as g
import nfl_model as m
import totals
import validate_data_files as v

NOW = dt.datetime(2026, 10, 10, 12, tzinfo=dt.timezone.utc)


def games():
    # a, b: model and market agree on home; c: model takes the away dog; d: pending.
    return pd.DataFrame({"game_id": list("abcd"), "season": 2026, "model_wp": [.7, .6, .45, .3],
                         "home_moneyline": [-200., -150., -150., 120.], "away_moneyline": [170., 130., 130., -140.],
                         "home won": [1., 0., 0., np.nan]})


def test_disagreement_rows_carry_the_whole_model_minus_favorite_difference():
    d = games()
    allg = m.roi_table(d, by="season").query("group == 'All games'").set_index("source")
    dis = m.disagreement_table(d, by="season").query("group == 'All games'").set_index("source")
    assert dis.loc["model", "bets"] == 1 and dis.loc["model", "wins"] == 1
    assert np.isclose(dis.loc["model", "units"], 1.3) and np.isclose(dis.loc["market favorite", "units"], -1)
    assert np.isclose(allg.loc["model", "units"] - allg.loc["market favorite", "units"],
                      dis.loc["model", "units"] - dis.loc["market favorite", "units"])
    agree = m.disagreement_table(d[d.game_id != "c"], by="season").query("group == 'All games'")
    assert (agree.bets == 0).all()


def rec(gid, wp, hm, am, ko="2026-10-11T17:00:00+00:00"):
    return {"experiment": "e", "revision": "r1", "game_id": gid, "season": 2026, "week": 5, "home": "H" + gid,
            "away": "A" + gid, "generated_utc": "2026-10-10T11:00:00+00:00", "kickoff_utc": ko, "model_wp": wp,
            "market_wp": .6, "homefield_wp": .55, "spread_line": 3., "home_moneyline": hm, "away_moneyline": am,
            "injury_report": {"home": "final", "away": "final"}}


SCHED = pd.DataFrame({"game_id": ["lo", "hi", "pk", "nt", "old"], "total_line": [40.5, 47.5, 38., np.nan, 39.],
                      "home_moneyline": [-200., -150., -110., -150., -150.],
                      "away_moneyline": [170., 130., -110., 130., 130.]})


def ledger(tmp_path):
    recs = [rec("lo", .7, -200, 170), rec("hi", .6, -150, 130), rec("pk", .6, -110, -110),
            rec("nt", .6, -150, 130), rec("old", .6, -150, 130, ko="2026-10-10T10:00:00+00:00")]
    (tmp_path / "forward_predictions.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    return recs


def test_totals_record_once_per_locked_future_game(tmp_path):
    ledger(tmp_path)
    assert totals.record(tmp_path, NOW, lambda: SCHED) == 3     # lo, hi, pk; nt has no total; old kicked off
    assert totals.record(tmp_path, NOW, lambda: SCHED) == 0     # never re-recorded
    path = tmp_path / "h5_totals.jsonl"
    assert v.validate_h5(path) == 3
    got = {r["game_id"]: r for r in totals.load(path)}
    assert got["lo"]["total_line"] == 40.5 and got["lo"]["away_moneyline"] == 170.
    assert totals.safe_record(tmp_path, NOW, lambda: 1 / 0) == 0  # a failure never raises


@pytest.mark.parametrize("bad", ["dup", "late", "total", "ml"])
def test_validate_h5_rejects_bad_rows(tmp_path, bad):
    ledger(tmp_path)
    totals.record(tmp_path, NOW, lambda: SCHED)
    path = tmp_path / "h5_totals.jsonl"
    rows = totals.load(path)
    if bad == "dup":
        rows.append(rows[0])
    elif bad == "late":
        rows[0]["captured_utc"] = "2026-10-12T00:00:00+00:00"
    elif bad == "total":
        rows[0]["total_line"] = None
    else:
        rows[0]["home_moneyline"] = -50
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with pytest.raises(ValueError):
        v.validate_h5(path)


def test_h5_bets_the_low_total_dog_only(tmp_path):
    ledger(tmp_path)
    totals.record(tmp_path, NOW, lambda: SCHED)
    h5 = totals.load(tmp_path / "h5_totals.jsonl")
    res = pd.DataFrame({"game_id": ["lo", "hi", "pk"], "result": [-3., -3., 7.]})
    d = g.h5_grades(h5, res)
    assert list(d.game_id) == ["lo", "pk"]                      # hi: total above the cut
    lo = d.set_index("game_id").loc["lo"]
    assert lo.bet_side == "away" and lo.bet_result == "W" and np.isclose(lo.units, 1.7) and lo.fav_units == -1
    assert np.isnan(d.set_index("game_id").loc["pk", "units"])  # pick'em: no underdog, no bet
    s = g.h5_summary(d)
    assert s["bets"] == 1 and s["recorded"] == 2 and g.h5_verdict(s).startswith("needs")
    tie = g.h5_grades(h5, pd.DataFrame({"game_id": ["lo"], "result": [0.]})).set_index("game_id")
    assert tie.loc["lo", "bet_result"] == "P" and tie.loc["lo", "units"] == 0


def test_h5_verdict_rule():
    base = {"bets": 300, "roi_se": .05, "null_roi": -.03}
    assert g.h5_verdict({**base, "roi": .08}).startswith("supported")   # .11 - 1.96 * .05 > 0
    assert g.h5_verdict({**base, "roi": .05}) == "unresolved"
    assert g.h5_verdict({**base, "roi": -.04}).startswith("falsified")
    assert g.h5_verdict({**base, "bets": 299, "roi": -.04}) == "unresolved"
    assert g.h5_verdict({**base, "bets": 9, "roi": .5}).startswith("needs")


def test_report_and_ledger_page_show_both(tmp_path):
    recs = ledger(tmp_path)
    totals.record(tmp_path, NOW, lambda: SCHED)
    res = pd.DataFrame({"game_id": ["lo", "hi", "pk"], "away_score": [10, 10, 10], "home_score": [7, 7, 17],
                        "result": [-3., -3., 7.]})
    led = g.grade([r for r in recs if r["game_id"] != "old"], res)
    text = g.report_text(led, NOW, g.h5_grades(totals.load(tmp_path / "h5_totals.jsonl"), res))
    assert "games where they pick different sides" in text and "n=0" in text
    assert "Pre-registered H5" in text and "2 qualifying games recorded, 1 graded" in text
    led_dis = g.grade([rec("x", .4, -200, 170)], pd.DataFrame({"game_id": ["x"], "away_score": [10],
                                                               "home_score": [7], "result": [-3.]}))
    assert "n=1, model +1.70u" in g.report_text(led_dis, NOW)
    graded = led[led.status == "graded"]
    assert "has not yet picked against" in b.disagreement_note(graded, "Locked picks")
    assert "in 1 game," in b.disagreement_note(led_dis, "Locked picks")
    assert b.disagreement_note(graded.iloc[:0], "Locked picks") == ""
