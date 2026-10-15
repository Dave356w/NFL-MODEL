"""Synthetic checks for research-only hypothetical original-spread alternate quotes."""
import numpy as np
import pandas as pd
import pytest

from research import original_spread_altline as alt


def games():
    return pd.DataFrame([
        dict(game_id="home_win", season=2024, week=1, result=6, spread_line=3,
             model_spread=4.2),
        dict(game_id="home_market_push", season=2024, week=1, result=3, spread_line=3,
             model_spread=4.2),
        dict(game_id="away_win", season=2024, week=2, result=-3, spread_line=3,
             model_spread=1.7),
        dict(game_id="same_half_line", season=2024, week=2, result=8, spread_line=3,
             model_spread=3.2),
        dict(game_id="unrealistic", season=2024, week=2, result=9, spread_line=3,
             model_spread=15),
    ])


def test_half_point_alt_pricing_and_graded_pushes():
    d = alt.evaluate(games()).set_index("game_id")
    assert len(d) == 4
    assert np.isclose(d.loc["home_win", "alt_line"], 4)
    assert np.isclose(d.loc["home_win", "point_shift"], 1)
    assert np.isclose(d.loc["home_win", "alt_implied"], .47 * 110 / 105)
    assert np.isclose(d.loc["home_win", "alt_units"], 1 / (.47 * 110 / 105) - 1)
    assert d.loc["home_market_push", "market_grade"] == "P"
    assert d.loc["home_market_push", "alt_grade"] == "L"
    assert d.loc["away_win", "alt_grade"] == "W"
    assert d.loc["away_win", "alt_line"] == 1.5
    assert d.loc["same_half_line", "alt_line"] == 3
    assert np.isclose(d.loc["same_half_line", "alt_units"],
                      d.loc["same_half_line", "market_units"])
    assert "unrealistic" not in d.index


def test_exact_spread_and_price_per_point_sensitivity():
    exact = alt.evaluate(games(), rounding="exact").set_index("game_id")
    assert np.isclose(exact.loc["home_win", "alt_line"], 4.2)
    assert exact.loc["home_market_push", "alt_grade"] == "L"
    two = alt.evaluate(games(), points_per_point=.02).set_index("game_id")
    four = alt.evaluate(games(), points_per_point=.04).set_index("game_id")
    assert four.loc["home_win", "alt_units"] > two.loc["home_win", "alt_units"]
    for x in (two, four):
        assert np.isclose(x.loc["same_half_line", "alt_win_profit"], 100 / 110)


def test_duplicate_ids_and_invalid_params_are_rejected():
    with pytest.raises(ValueError, match="duplicate game_id"):
        alt.evaluate(pd.concat([games(), games().iloc[:1]]))
    with pytest.raises(ValueError, match="points_per_point"):
        alt.evaluate(games(), points_per_point=0)
    with pytest.raises(ValueError, match="rounding"):
        alt.evaluate(games(), rounding="quarter")


def test_summaries_are_paired_and_grouped_by_game_week():
    d = alt.evaluate(games())
    s = alt.summary(d)
    assert s["bets"] == 4
    assert s["market"]["pushes"] == 1
    assert s["alt"]["wins"] + s["alt"]["losses"] + s["alt"]["pushes"] == 4
    assert s["paired"]["clusters"] == 2
    assert np.isclose(s["paired"]["delta_roi"],
                      (d.alt_units - d.market_units).mean())
    assert alt.summary(d.iloc[:0]) == {"bets": 0}
