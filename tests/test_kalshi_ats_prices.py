"""Kalshi NFL ATS quote retrieval and strict historical timestamp guards."""
import datetime as dt
import numpy as np
import pandas as pd
from research import kalshi_ats_prices as p
from research import ats_forward_shadow as sh


def snapshot(ts=1000,bid=".48",ask=".52"):
    return {"end_period_ts":ts,"yes_bid":{"close_dollars":bid},
            "yes_ask":{"close_dollars":ask}}


def test_candle_at_or_before_not_future_and_requires_two_sided_quote():
    cutoff=pd.Timestamp(1100, unit="s",tz="UTC")
    v=p.candle_quote([snapshot(1000),snapshot(1200)],cutoff)
    assert v["yes_ask"] == .52 and v["no_ask"] == .52 and v["age_seconds"] == 100
    assert p.candle_quote([snapshot(1200)],cutoff) is None
    assert p.candle_quote([snapshot(1000)],cutoff,max_staleness=90) is None
    assert p.candle_quote([snapshot(1000, ".52",".48")],cutoff) is None


def events(ticker="KXNFLSPREAD-26OCT18BALCLE"):
    return [{"event_ticker":ticker}]


def test_exact_halfpoint_quotes_and_no_ask_complement():
    row={"game_id":"2026_06_BAL_CLE","away":"BAL","home":"CLE",
         "spread_line":-3.5,"kickoff_utc":"2026-10-18T17:00:00+00:00"}
    ev=p.event_for_game(events(),row,p.kalshi.SPREAD_SERIES)
    assert ev == "KXNFLSPREAD-26OCT18BALCLE"
    m={"ticker":ev+"-BAL4","event_ticker":ev,"floor_strike":3.5}
    def fake_get(path):
        assert "/candlesticks?" in path
        return {"candlesticks":[{"end_period_ts":int(pd.Timestamp("2026-10-18T15:00:00+00:00").timestamp())-60,
                                  "yes_bid":{"close_dollars":".48"},
                                  "yes_ask":{"close_dollars":".53"}}]}
    v,status=p.line_quote(row,[(m,"historical")],"2026-10-18T15:00:00+00:00",fake_get)
    assert status=="quoted" and v["away_ask"]==.53
    assert v["home_ask"]==.52 and v["strike"]==3.5
    assert v["market_source"]=="historical"
    assert p.line_quote({**row,"spread_line":-3.},[(m,"historical")],
                        "2026-10-18T15:00:00+00:00",fake_get)[1]=="integer_or_nonhalfpoint_line"
    assert p.line_quote({**row,"spread_line":-4.5},[(m,"historical")],
                        "2026-10-18T15:00:00+00:00",fake_get)[1]=="missing_or_ambiguous_exact_strike"


def test_model_vs_fixed_graded_only_matched_kalshi_games():
    d=pd.DataFrame([{"game_id":"g1","original_side":"home","original_grade":"W",
                     "fixed_band_side":"away","fixed_band_grade":"L",
                     "cover_probability_side":"","cover_probability_grade":"S"},
                    {"game_id":"g2","original_side":"away","original_grade":"W",
                     "fixed_band_side":"away","fixed_band_grade":"W",
                     "cover_probability_side":"home","cover_probability_grade":"L"}])
    quotes=[{"game_id":"g1","status":"quoted","home_ask":.48,"away_ask":.54},
            {"game_id":"g2","status":"missing","home_ask":None,"away_ask":None}]
    x=p.joined_ats_results(d,quotes)
    assert len(x)==1 and x.iloc[0].game_id=="g1"
    assert np.isclose(x.iloc[0].original_kalshi_units,1/.48-1-.07*.52)
    assert np.isclose(x.iloc[0].fixed_band_kalshi_units,-1-.07*.46)
    assert x.iloc[0].cover_probability_kalshi_units==0


def test_live_shadow_uses_lock_time_quote_and_rejects_stale():
    raw={"game_id":"2026_07_BAL_CLE","away":"BAL","home":"CLE",
         "spread_line":-3.5,"generated_utc":"2026-10-17T11:00:00+00:00",
         "kickoff_utc":"2026-10-18T17:00:00+00:00"}
    snap={"game_id":raw["game_id"],"captured_utc":"2026-10-17T11:10:00+00:00",
          "spread_ladder":[{"team":"BAL","strike":3.5,"bid":.48,"ask":.53,
                            "ticker":"KXNFLSPREAD-26OCT18BALCLE-BAL4"}],
          "winner":{"home":{"ask":.3},"away":{"ask":.7}}}
    q=sh.kalshi_lock_quote(raw,[snap])
    assert q["home_ask"] == .52 and q["away_ask"] == .53
    assert q["winner_away_ask"] == .7
    assert sh.kalshi_lock_quote(raw,[{**snap,"captured_utc":"2026-10-17T12:00:00+00:00"}]) is None
    assert sh.kalshi_lock_quote({**raw,"spread_line":-3},[snap]) is None
    assert sh.kalshi_lock_quote(raw,[{**snap,"captured_utc":"2026-10-17T10:00:00+00:00"}]) is None


def test_historical_moneyline_only_observed_quotes_and_tie_half_settlement():
    games=pd.DataFrame([
        {"game_id":"g1","model_wp":.7,"home won":1.},
        {"game_id":"g2","model_wp":.3,"home won":.5},
        {"game_id":"g3","model_wp":.7,"home won":0.},
    ])
    quotes=[
        {"game_id":"g1","winner_home_ask":.60,"winner_away_ask":.42,
         "cutoff_utc":"2025-09-01T11:00:00+00:00","price_basis":"kalshi_candle"},
        {"game_id":"g2","winner_home_ask":.53,"winner_away_ask":.47,
         "cutoff_utc":"2025-09-01T11:00:00+00:00","price_basis":"kalshi_candle"},
        {"game_id":"g3","winner_home_ask":None,"winner_away_ask":None,
         "cutoff_utc":"2025-09-01T11:00:00+00:00","price_basis":"no_data"},
    ]
    graded=p.joined_kalshi_moneyline(games,quotes)
    assert len(graded)==2
    m=graded.set_index("game_id")
    assert m.loc["g1","kalshi_ml_side"]=="home"
    assert np.isclose(m.loc["g1","kalshi_ml_units"], 1/.60-1-.07*(1-.60))
    assert np.isclose(m.loc["g2","kalshi_ml_units"], .5/.47-1-.07*(1-.47))
