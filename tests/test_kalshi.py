"""Kalshi capture and secondary grading, offline (a fake API stands in for the network)."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

import grade_ledger as g
import kalshi as k
import validate_data_files as v

NOW = dt.datetime(2026, 10, 8, 16, tzinfo=dt.timezone.utc)


def ledger_rec(gid="2026_05_TB_DAL", away="TB", home="DAL", ko="2026-10-09T00:15:00+00:00", wp=.645):
    return {"experiment": "e", "revision": "r1", "game_id": gid, "season": 2026, "week": 5, "home": home, "away": away,
            "generated_utc": "2026-10-08T06:38:38+00:00", "kickoff_utc": ko, "model_wp": wp, "market_wp": .754,
            "homefield_wp": .54, "spread_line": 8.5, "home_moneyline": -470, "away_moneyline": 360,
            "injury_report": {"home": "final", "away": "final"}}


def mk(ticker, bid, ask, strike=None):
    out = {"ticker": ticker, "yes_bid_dollars": f"{bid:.4f}", "yes_ask_dollars": f"{ask:.4f}"}
    if strike is not None:
        out["floor_strike"] = strike
    return out


API = {
    "/events?series_ticker=KXNFLGAME&status=open&limit=200":
        {"events": [{"event_ticker": "KXNFLGAME-26OCT08TBDAL"}, {"event_ticker": "KXNFLGAME-26OCT11PHIJAC"}], "cursor": ""},
    "/events?series_ticker=KXNFLSPREAD&status=open&limit=200":
        {"events": [{"event_ticker": "KXNFLSPREAD-26OCT08TBDAL"}], "cursor": ""},
    "/markets?event_ticker=KXNFLGAME-26OCT08TBDAL":
        {"markets": [mk("KXNFLGAME-26OCT08TBDAL-DAL", .79, .80), mk("KXNFLGAME-26OCT08TBDAL-TB", .20, .21)]},
    "/markets?event_ticker=KXNFLSPREAD-26OCT08TBDAL":
        {"markets": [mk("KXNFLSPREAD-26OCT08TBDAL-DAL4", .68, .69, 3.5), mk("KXNFLSPREAD-26OCT08TBDAL-DAL5", .65, .66, 4.5),
                     mk("KXNFLSPREAD-26OCT08TBDAL-DAL8", .52, .53, 7.5), mk("KXNFLSPREAD-26OCT08TBDAL-TB2", .14, .15, 1.5),
                     {"ticker": "KXNFLSPREAD-26OCT08TBDAL-DAL11", "floor_strike": 10.5, "yes_bid_dollars": "", "yes_ask_dollars": ""}]},
}


def fake_get(path):
    return API[path]


def test_parse_and_match_with_team_aliases():
    assert k.parse_event("KXNFLGAME-26OCT11PHIJAC")[1:] == (dt.date(2026, 10, 11), "PHIJAC")
    assert k.parse_event("KXNFLGAME-junk") is None
    evs = [{"event_ticker": "KXNFLGAME-26OCT11PHIJAC"}]
    assert k.match_event(evs, "PHI", "JAX", "2026-10-11T13:30:00+00:00") == "KXNFLGAME-26OCT11PHIJAC"
    assert k.match_event(evs, "JAX", "PHI", "2026-10-11T13:30:00+00:00") is None    # home/away order matters
    assert k.match_event(evs, "PHI", "JAX", "2026-10-18T13:30:00+00:00") is None    # a different week
    assert k.match_event(evs, "PHI", "JAX", "2026-10-12T00:20:00+00:00") == "KXNFLGAME-26OCT11PHIJAC"  # UTC next day


def test_quote_rejects_empty_or_crossed_books():
    assert k.quote(mk("t", .4, .41)) == {"ticker": "t", "bid": .4, "ask": .41}
    assert k.quote({"ticker": "t", "yes_bid": 40, "yes_ask": 42}) == {"ticker": "t", "bid": .4, "ask": .42}
    assert k.quote(mk("t", .5, .5)) is None and k.quote({"ticker": "t", "yes_bid_dollars": ""}) is None


def test_record_first_capture_only_and_never_after_kickoff(tmp_path):
    later = ledger_rec("2026_05_X_Y", "X", "Y", "2026-10-08T15:00:00+00:00")  # already kicked off: skipped
    (tmp_path / "forward_predictions.jsonl").write_text("\n".join(json.dumps(r) for r in (ledger_rec(), later)) + "\n")
    assert k.record(tmp_path, NOW, fake_get) == 1
    r = k.load(tmp_path / "kalshi_snapshots.jsonl")[0]
    assert r["winner"]["home"]["ask"] == .8 and r["winner_event"] == "KXNFLGAME-26OCT08TBDAL"
    assert [(x["team"], x["strike"]) for x in r["spread_ladder"]] == [("DAL", 3.5), ("DAL", 4.5), ("DAL", 7.5), ("TB", 1.5)]
    assert k.record(tmp_path, NOW, fake_get) == 0  # append-only: no second capture
    assert v.validate_kalshi(tmp_path / "kalshi_snapshots.jsonl") == 1


def test_safe_record_swallows_api_failures(tmp_path, capsys):
    (tmp_path / "forward_predictions.jsonl").write_text(json.dumps(ledger_rec()) + "\n")
    def boom(path):
        raise OSError("network down")
    assert k.safe_record(tmp_path, NOW, boom) == 0
    assert "kalshi: skipped" in capsys.readouterr().err and not (tmp_path / "kalshi_snapshots.jsonl").exists()


def test_validator_rejects_late_duplicate_and_bad_quotes(tmp_path):
    (tmp_path / "forward_predictions.jsonl").write_text(json.dumps(ledger_rec()) + "\n")
    k.record(tmp_path, NOW, fake_get)
    p = tmp_path / "kalshi_snapshots.jsonl"
    good = json.loads(p.read_text())
    for bad in ({**good, "captured_utc": "2026-10-09T01:00:00+00:00"},
                {**good, "winner": {"home": {"ticker": "t", "bid": .9, "ask": .8}}}):
        p.write_text(json.dumps(bad) + "\n")
        with pytest.raises(ValueError):
            v.validate_kalshi(p)
    p.write_text((json.dumps(good) + "\n") * 2)
    with pytest.raises(ValueError, match="duplicate"):
        v.validate_kalshi(p)


def graded(result, snaps_dir, wp=.645):
    rec = ledger_rec(wp=wp)
    res = pd.DataFrame({"game_id": [rec["game_id"]], "away_score": [0], "home_score": [result], "result": [result]})
    return g.grade([rec], res, k.load(snaps_dir / "kalshi_snapshots.jsonl")).iloc[0]


def test_kalshi_side_and_alt_rule_grading(tmp_path):
    (tmp_path / "forward_predictions.jsonl").write_text(json.dumps(ledger_rec()) + "\n")
    k.record(tmp_path, NOW, fake_get)
    win5 = graded(5, tmp_path)  # DAL by 5: model side (DAL) wins at .80; alt DAL >4.5 (model spread 4.58) wins at .66
    assert np.isclose(win5.kalshi_side_ask, .8) and np.isclose(win5.kalshi_units, 1 / .8 - 1 - .07 * .2)
    assert np.isclose(win5.kalshi_null, .795 / .8 - 1 - .07 * .2)  # normalized mid .795 for DAL
    assert win5.alt_rule and win5.alt_team == "DAL" and win5.alt_strike == 4.5 and np.isclose(win5.alt_ask, .66)
    assert win5.alt_result == "W" and np.isclose(win5.alt_units, 1 / .66 - 1 - .07 * .34)
    assert np.isclose(win5.alt_fav_units, win5.kalshi_fav_units)  # DAL is the Kalshi favorite too
    win4 = graded(4, tmp_path)  # DAL by 4: wins the game, misses the alt line
    assert win4.alt_result == "L" and np.isclose(win4.alt_units, -1 - .07 * .34) and win4.kalshi_units > 0
    tie = graded(0, tmp_path)   # Kalshi resolves a tie at $0.50 per side
    assert np.isclose(tie.kalshi_units, .5 / .8 - 1 - .07 * .2)
    pending = g.grade([ledger_rec()], pd.DataFrame(columns=["game_id", "away_score", "home_score", "result"]),
                      k.load(tmp_path / "kalshi_snapshots.jsonl")).iloc[0]
    assert np.isnan(pending.kalshi_units) and pending.alt_result == "" and np.isfinite(pending.kalshi_null)
    assert 9 < pending.kalshi_lag_hours < 10


def test_alt_rule_off_when_model_disagrees_or_is_larger(tmp_path):
    (tmp_path / "forward_predictions.jsonl").write_text(json.dumps(ledger_rec()) + "\n")
    k.record(tmp_path, NOW, fake_get)
    assert not graded(5, tmp_path, wp=.85).alt_rule   # model spread 12.8 > market 8.5
    assert not graded(5, tmp_path, wp=.40).alt_rule   # model favors TB
    small = graded(1, tmp_path, wp=.55)               # model spread 1.6: below every DAL strike -> game-winner market
    assert small.alt_rule and small.alt_strike == 0 and np.isclose(small.alt_ask, .8) and small.alt_result == "W"


def test_no_snapshots_leaves_columns_empty_and_report_quiet(tmp_path):
    rec = ledger_rec()
    res = pd.DataFrame({"game_id": [rec["game_id"]], "away_score": [0], "home_score": [5], "result": [5]})
    out = g.grade([rec], res)
    assert list(out.columns) == g.COLUMNS and out.kalshi_units.isna().all() and not out.alt_rule.any()
    assert "Kalshi" not in g.report_text(out)


def test_report_lines_once_graded(tmp_path):
    (tmp_path / "forward_predictions.jsonl").write_text(json.dumps(ledger_rec()) + "\n")
    k.record(tmp_path, NOW, fake_get)
    rec = ledger_rec()
    res = pd.DataFrame({"game_id": [rec["game_id"]], "away_score": [0], "home_score": [5], "result": [5]})
    text = g.report_text(g.grade([rec], res, k.load(tmp_path / "kalshi_snapshots.jsonl")))
    assert "Secondary: model's side at the Kalshi ask" in text and "Kalshi-correct null -2.0%" in text
    assert "alt-line rule at Kalshi prices: 1-0" in text


def toy_table(p_win=.75):
    """Reference table where the favorite's margin is uniform on -10..19 (no ties) at every fav_wp."""
    over, tie = {}, {}
    m = np.arange(-10, 20)
    for w in np.round(np.arange(.5, .98, .01), 2):
        tie[w] = 0.
        for s in np.arange(-30.5, 31, 1.):
            over[(w, s)] = float((m > s).mean())
    return over, tie


def ladder_snap(asks):
    """DAL (home) favorite. asks: {(team, strike): ask}; strike 0 = game-winner market."""
    win = {("home" if t == "DAL" else "away"): {"ticker": f"W-{t}", "bid": a - .01, "ask": a}
           for (t, s), a in asks.items() if s == 0}
    lad = [{"team": t, "strike": s, "ticker": f"L-{t}{s}", "bid": a - .01, "ask": a}
           for (t, s), a in asks.items() if s]
    return {"home": "DAL", "away": "TB", "winner": win, "spread_ladder": lad}


def test_ladder_probability_both_sides_and_winner_market():
    t = toy_table()
    assert np.isclose(k.ladder_probability(t, .75, True, 4.5), 15 / 30)    # m > 4.5: 5..19
    assert np.isclose(k.ladder_probability(t, .75, False, 4.5), 6 / 30)    # m < -4.5: -10..-5
    assert np.isclose(k.ladder_probability(t, .75, True, 0), 19 / 30)      # m > 0, no ties
    assert np.isclose(k.ladder_probability(t, .999, True, 4.5), 15 / 30)   # clamped to the grid


def test_ladder_pick_takes_the_best_rung_after_fee_and_respects_limits():
    t = toy_table()
    # fair DAL>4.5 = .50; ask .44 -> edge .06 - fee .017 = .043 (bet); TB>4.5 fair .167 at .16 (no edge)
    s = ladder_snap({("DAL", 0): .64, ("TB", 0): .37, ("DAL", 4.5): .44, ("TB", 4.5): .16, ("DAL", 7.5): .40})
    p = k.ladder_pick(s, -300, 250, t)
    assert p["ticker"] == "L-DAL4.5" and p["side"] == "home" and np.isclose(p["edge"], .5 - .44 - .07 * .44 * .56)
    assert k.ladder_pick(s, -300, 250, t, min_edge=.05) is None                     # threshold is binding
    deep = ladder_snap({("DAL", 0): .64, ("TB", 0): .37, ("DAL", 18.5): .001})     # beyond the strike cap
    assert k.ladder_pick(deep, -300, 250, t) is None
    assert k.ladder_pick(s, None, 250, t) is None                                   # no moneyline, no bet


def test_h3_ladder_grading_and_report(tmp_path):
    (tmp_path / "forward_predictions.jsonl").write_text(json.dumps(ledger_rec()) + "\n")
    k.record(tmp_path, NOW, fake_get)
    snaps = k.load(tmp_path / "kalshi_snapshots.jsonl")
    snaps[0]["spread_ladder"] = [{"team": "DAL", "strike": 9.5, "ticker": "X-DAL10", "bid": .20, "ask": .21},
                                 {"team": "TB", "strike": 1.5, "ticker": "X-TB2", "bid": .29, "ask": .30}]
    snaps[0]["winner"] = {"home": {"ticker": "W-DAL", "bid": .70, "ask": .71}, "away": {"ticker": "W-TB", "bid": .32, "ask": .33}}
    rec = ledger_rec()
    def run(result):
        res = pd.DataFrame({"game_id": [rec["game_id"]], "away_score": [0], "home_score": [result], "result": [result]})
        return g.grade([rec], res, snaps, toy_table())
    hit, miss = run(12).iloc[0], run(9).iloc[0]   # toy fair DAL>9.5 = 10/30 vs ask .21: the best rung
    assert hit.ladder_ticker == "X-DAL10" and hit.ladder_result == "W" and np.isclose(hit.ladder_units, 1 / .21 - 1 - .07 * .79)
    assert miss.ladder_result == "L" and np.isclose(miss.ladder_null, .205 / .21 - 1 - .07 * .79)
    assert "Pre-registered H3" in g.report_text(run(12))
    none = g.grade([rec], pd.DataFrame(columns=["game_id", "away_score", "home_score", "result"]), snaps, None)
    assert none.ladder_ticker.isna().all() and "H3" not in g.report_text(none)


def test_later_revision_gets_its_own_capture_and_grades_at_it(tmp_path):
    early = ledger_rec()
    late = {**ledger_rec(), "experiment": "e2", "revision": "r2", "generated_utc": "2026-10-08T23:36:00+00:00"}
    led = tmp_path / "forward_predictions.jsonl"
    led.write_text(json.dumps(early) + "\n")
    assert k.record(tmp_path, NOW, fake_get) == 1
    assert k.record(tmp_path, NOW, fake_get) == 0               # every locked row already has a capture after its lock
    led.write_text(json.dumps(early) + "\n" + json.dumps(late) + "\n")
    later = dt.datetime(2026, 10, 8, 23, 50, tzinfo=dt.timezone.utc)
    assert k.record(tmp_path, later, fake_get) == 1              # r2 locked after the 16:00 capture
    assert k.record(tmp_path, later, fake_get) == 0
    snaps_path = tmp_path / "kalshi_snapshots.jsonl"
    v.validate_kalshi(snaps_path)                                 # two captures of one game at different times are valid
    snaps = k.load(snaps_path)
    res = pd.DataFrame({"game_id": [early["game_id"]], "away_score": [0], "home_score": [5], "result": [5]})
    x = g.grade([early, late], res, snaps).set_index("revision")
    assert x.loc["r1", "kalshi_captured_utc"] == snaps[0]["captured_utc"] and 9 < x.loc["r1", "kalshi_lag_hours"] < 10
    assert x.loc["r2", "kalshi_captured_utc"] == snaps[1]["captured_utc"] and 0 <= x.loc["r2", "kalshi_lag_hours"] < .3
    # Kickoff passed: no more captures, and a snapshot locked after the last capture is flagged, not dropped.
    assert k.record(tmp_path, dt.datetime(2026, 10, 9, 1, tzinfo=dt.timezone.utc), fake_get) == 0
    stale = g.grade([late], res, snaps[:1]).iloc[0]
    assert stale.kalshi_lag_hours < 0 and np.isfinite(stale.kalshi_units)
    text = g.report_text(g.grade([early, late], res, snaps[:1]))
    assert "1 captured BEFORE lock" in text and "first capture at or after lock" in text
    assert "BEFORE lock" not in g.report_text(g.grade([early, late], res, snaps))
