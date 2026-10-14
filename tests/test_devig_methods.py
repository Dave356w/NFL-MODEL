import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import nfl_model as m

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import devig_methods as d  # noqa: E402


def test_proportional_arm_is_production():
    hm, am = np.array([-110, -350, 280, -150, -1000]), np.array([-110, 280, -350, 130, 650])
    prod = m.market_ml_wp(pd.DataFrame({"home_moneyline": hm, "away_moneyline": am}))
    assert np.allclose(d.devig(hm, am, "P"), prod, atol=1e-14)


def test_known_values_at_asymmetric_juice():
    q = {arm: d.devig([-350], [280], arm)[0] for arm in d.ARMS}
    assert q["P"] == pytest.approx(.74719, abs=1e-5)
    assert q["A"] == pytest.approx(.75731, abs=1e-5)
    assert q["W"] == pytest.approx(.76275, abs=1e-5)
    assert q["P"] < q["A"] < q["W"]  # the methods move hold off the favorite in this order


@pytest.mark.parametrize("arm", d.ARMS)
def test_every_arm_is_a_proper_two_way_devig(arm):
    hm, am = np.array([-110, -350, -105, 100, -200]), np.array([-110, 280, -115, -100, 170])
    q, swapped = d.devig(hm, am, arm), d.devig(am, hm, arm)
    assert np.allclose(q + swapped, 1., atol=1e-10)  # complement and side swap
    assert q[0] == pytest.approx(.5) and q[3] == pytest.approx(.5)
    assert np.all((q > 0) & (q < 1))


@pytest.mark.parametrize("arm", d.ARMS)
def test_no_hold_leaves_fair_prices_alone(arm):
    # +300/-300 has no hold: implied 0.25 + 0.75 = 1
    assert d.devig([-300], [300], arm)[0] == pytest.approx(.75, abs=1e-12)


@pytest.mark.parametrize("arm", d.ARMS)
def test_invalid_prices_are_nan(arm):
    q = d.devig([np.nan, 50, -110, 0], [-110, -110, np.inf, -110], arm)
    assert np.isnan(q).all()


def test_arms_agree_on_the_favorite():
    rng = np.random.default_rng(0)
    fair = rng.uniform(.05, .95, 500); over = rng.uniform(1., 1.1, 500)
    to_ml = lambda dec: np.where(dec >= 2, (dec - 1) * 100, -100 / (dec - 1))
    hm, am = to_ml(1 / (over * fair)), to_ml(1 / (over * (1 - fair)))
    keep = (over * fair < 1) & (over * (1 - fair) < 1)
    sides = {arm: d.devig(hm[keep], am[keep], arm) >= .5 for arm in d.ARMS}
    assert (sides["P"] == sides["A"]).all() and (sides["P"] == sides["W"]).all()


def test_null_ev_matches_production_under_proportional():
    b = m.flat_bets(pd.DataFrame({"home_moneyline": [-350], "away_moneyline": [280], "model_wp": [.9]}))
    q = d.devig([-350], [280], "P")
    assert d.null_ev(q, np.array([-350.]))[0] == pytest.approx(b.null_ev.iloc[0], abs=1e-12)
    # additive/power leave less hold on the favorite: its null is less negative than proportional's
    assert d.null_ev(d.devig([-350], [280], "A"), np.array([-350.]))[0] > b.null_ev.iloc[0]


def fixture():
    return pd.DataFrame({"game_id": list("abcdef"), "season": [2010, 2010, 2010, 2020, 2020, 2020], "week": 1,
                         "home_team": "H", "away_team": "A",
                         "home_moneyline": [-350, 150, -110, -200, np.nan, -150],
                         "away_moneyline": [280, -170, -110, 170, -110, 130],
                         "result": [7, -3, 0, 3, 10, -14]})


def test_frame_excludes_ties_and_unpriced_games():
    g = d.frame(fixture())
    assert list(g.game_id) == ["a", "b", "d", "f"]  # c is a tie, e lacks a home price
    assert list(g.y) == [1., 0., 1., 0.]
    assert list(g.fav_home) == [True, False, True, True]


def test_paired_gain_and_selection_rules():
    p = d.paired([.001, -.001, .002, .0])
    assert p["n"] == 4 and p["mean"] == pytest.approx(.0005) and p["lo"] < p["mean"] < p["hi"]
    tie = {"arms": {"P": {"log_loss": .6}, "A": {"log_loss": .6}, "W": {"log_loss": .61}}}
    assert d.select(tie) == "P"
    assert d.select({"arms": {"P": {"log_loss": .6}, "A": {"log_loss": .59}, "W": {"log_loss": .595}}}) == "A"
    assert d.verdict("P", {"lo": .1, "hi": .2}).startswith("keep P")
    assert d.verdict("A", {"lo": .001, "hi": .002}).startswith("propose A")
    assert d.verdict("A", {"lo": -.002, "hi": -.001}).startswith("keep P")
    assert d.verdict("W", {"lo": -.001, "hi": .001}) == "unresolved, keep P"


def test_side_table_roi_is_method_independent_and_nulls_differ():
    g = d.frame(fixture())
    rows = d.side_table(g)
    fav = next(r for r in rows if r["band"] == "0.70–0.80" and r["side"] == "favorite")
    assert fav["n"] == 1 and fav["units"] == pytest.approx(100 / 350)  # a: -350 favorite won
    dog = next(r for r in rows if r["band"] == "0.70–0.80" and r["side"] == "underdog")
    assert dog["units"] == -1. and dog["null_A"] < dog["null_P"] < 0 < fav["null_A"] + 1


def test_calibration_recovers_identity_on_calibrated_draws():
    rng = np.random.default_rng(1)
    q = rng.uniform(.2, .8, 20000); y = (rng.random(20000) < q).astype(float)
    c = d.calibration(q, y)
    assert abs(c["intercept"]) < 3 * c["intercept_se"] + .01 and abs(c["slope"] - 1) < 3 * c["slope_se"] + .01
