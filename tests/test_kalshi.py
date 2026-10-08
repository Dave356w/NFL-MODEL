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
