"""Settlement and price-sensitive decisions; no historical ROI tuning."""
import json

import numpy as np
import pytest

from research import r003_spread_ev as ev


def quote(side="home", handicap=-3, american_odds=-110, **extra):
    return dict(side=side, handicap=handicap, american_odds=american_odds, **extra)


def test_integer_push_halfpoint_and_away_sign():
    p, s = [.25, .35, .40], [-7, 3, 7]
    home = ev.price_offer(p, s, **quote())
    away = ev.price_offer(p, s, **quote("away", 3))
    assert [home[k] for k in ["cover_probability", "push_probability", "loss_probability"]] == pytest.approx([.4, .35, .25])
    assert away["cover_probability"] == pytest.approx(home["loss_probability"])
    assert away["loss_probability"] == pytest.approx(home["cover_probability"])
    assert away["push_probability"] == pytest.approx(.35)
    half = ev.price_offer(p, s, **quote(handicap=-3.5))
    assert half["push_probability"] == 0 and half["loss_probability"] == pytest.approx(.6)
    plus = ev.price_offer(p, s, **quote("home", 3))
    assert plus["cover_probability"] == pytest.approx(.75)
    pickem = ev.price_offer([.3, .2, .5], [-1, 0, 1], **quote(handicap=0))
    assert pickem["push_probability"] == pytest.approx(.2)


def test_mean_gap_can_disagree_with_cover_ev():
    # Mean MOV is +4.4, above the home -3 threshold, yet home covers only 10%.
    p, s = [.90, .10], [-4, 80]
    assert np.dot(p, s) > 3
    result = ev.evaluate_offers(p, s, [quote(), quote("away", 3)])
    assert result["selected_offer"]["side"] == "away"
    assert result["selected_offer"]["cover_probability"] == pytest.approx(.9)


def test_lower_probability_can_have_higher_ev_and_prices_change_choice():
    p, s = [.45, .55], [-7, 7]
    result = ev.evaluate_offers(p, s, [quote(american_odds=-150), quote("away", 3, 150)])
    selected = result["selected_offer"]
    assert selected["side"] == "away" and selected["cover_probability"] == pytest.approx(.45)
    assert selected["expected_units"] == pytest.approx(.45 * 1.5 - .55)
    repriced = ev.evaluate_offers(p, s, [quote(american_odds=110), quote("away", 3, -150)])
    assert repriced["selected_offer"]["side"] == "home"


def test_push_mass_enters_unconditional_ev_and_settlement_oracle():
    p, s = np.array([.20, .40, .40]), np.array([-7, 3, 7])
    row = ev.price_offer(p, s, **quote())
    assert row["conditional_cover_probability"] == pytest.approx(2 / 3)
    assert row["expected_units"] == pytest.approx(.4 / 1.1 - .2)
    # Direct payoff by outcome is independent of the event-probability formula.
    payoff = np.array([-1., 0., 1 / 1.1])
    assert row["expected_units"] == pytest.approx(p @ payoff)


def test_nonpositive_ev_and_empty_offers_pass():
    result = ev.evaluate_offers([.5, .5], [-7, 7], [quote(), quote("away", 3)])
    assert result["action"] == "pass" and result["selected_offer"] is None
    assert result["pass_expected_units"] == 0
    assert ev.evaluate_offers([.5, .5], [-7, 7], [quote(american_odds=100)])["action"] == "pass"
    assert ev.evaluate_offers([1.], [3], [quote()])["action"] == "pass"
    assert ev.evaluate_offers([1.], [3], [])["action"] == "pass"


def test_commission_and_fixed_fee_can_remove_positive_edge():
    p, s = [.45, .55], [-7, 7]
    row = ev.price_offer(p, s, **quote(american_odds=100, commission=.1, stake_fee=.02))
    assert row["expected_units"] == pytest.approx(.55 * .9 - .45 - .02)
    assert ev.evaluate_offers(p, s, [quote(american_odds=100, stake_fee=.11)])["action"] == "pass"
    assert ev.price_offer([1.], [3], **quote(stake_fee=.01))["expected_units"] == pytest.approx(-.01)


def test_compare_actual_different_handicaps_and_equal_ev_order():
    p, s = [.3, .3, .4], [-7, 3, 7]
    result = ev.evaluate_offers(p, s, [quote(handicap=-3.5), quote("away", 3.5)])
    assert result["selected_offer"]["handicap"] == 3.5
    duplicate = ev.evaluate_offers(p, s, [quote(), quote()])
    assert duplicate["selected_offer_index"] == 0


@pytest.mark.parametrize("kwargs", [
    {"side": "favorite"}, {"handicap": -3.25}, {"handicap": np.nan},
    {"american_odds": -99}, {"american_odds": 0}, {"american_odds": "-110"},
    {"american_odds": True}, {"commission": -1}, {"commission": 1},
    {"stake_fee": -.01}, {"stake_fee": np.inf},
])
def test_invalid_quotes_fail(kwargs):
    with pytest.raises(ValueError):
        ev.price_offer([.4, .6], [-7, 7], **(quote() | kwargs))


@pytest.mark.parametrize("p,s", [
    ([.4, .5], [-1, 1]), ([np.nan, .5], [-1, 1]), ([-.1, 1.1], [-1, 1]),
    ([.5, .5], [1, 1]), ([.5, .5], [1, -1]), ([1.], [1.5]),
    ([], []), ([1.], [0, 1]), ([[1.]], [0]),
])
def test_invalid_pmfs_fail(p, s):
    with pytest.raises(ValueError):
        ev.evaluate_offers(p, s, [quote()])


def test_float32_rounding_is_normalized_and_side_swap_is_symmetric():
    p, s = np.array([.1, .2, .7], np.float32), np.array([-7, 0, 7])
    a = ev.price_offer(p, s, **quote())
    b = ev.price_offer(p[::-1], -s[::-1], **quote("away", -3))
    assert a["expected_units"] == pytest.approx(b["expected_units"])
    assert sum(a[k] for k in ["cover_probability", "loss_probability", "push_probability"]) == pytest.approx(1)


def make_pack(tmp_path, ids=None):
    path = tmp_path / "marginals.npz"
    np.savez(path, game_ids=np.array(ids or ["fixture"]), margin_support=[-7, 3, 7],
             **{ev.ARM + "__margin": [[.25, .35, .4]]})
    return path


def test_request_and_cli_use_matching_game_and_supplied_quotes(tmp_path, capsys):
    path = make_pack(tmp_path)
    request = dict(game_id="fixture", offers=[quote(), quote("away", 3)])
    file = tmp_path / "request.json"
    file.write_text(json.dumps(request))
    before = path.read_bytes()
    ev.main([str(file), "--pmfs", str(path)])
    result = json.loads(capsys.readouterr().out)
    assert result["selected_offer"]["side"] == "home"
    assert result["game_id"] == "fixture" and result["arm"] == ev.ARM
    assert len(result["pmf_sha256"]) == 64 and path.read_bytes() == before
    with pytest.raises(ValueError, match="exactly once"):
        ev.evaluate_request(path, request | {"game_id": "wrong"})
    with pytest.raises(ValueError, match="outcomes"):
        ev.evaluate_request(path, request | {"actual_margin": 7})
    with pytest.raises(ValueError, match="unique"):
        ev.load_margin(make_pack(tmp_path, ["fixture", "fixture"]), "fixture")


def test_missing_and_malformed_prices_fail_instead_of_assuming_minus110(tmp_path):
    with pytest.raises(ValueError, match="american_odds"):
        ev.evaluate_offers([.4, .6], [-7, 7], [{"side": "home", "handicap": -3}])
    with pytest.raises(ValueError):
        ev.evaluate_offers([.4, .6], [-7, 7], [quote() | {"odds": -105}])
    request = tmp_path / "request.json"
    request.write_text(json.dumps(dict(game_id="fixture", offers=[quote()])))
    with pytest.raises(SystemExit) as exc:
        ev.main([str(request), "--pmfs", str(tmp_path / "missing.npz")])
    assert exc.value.code == 2


def test_misaligned_pack_and_non_r003_arm_fail(tmp_path):
    path = tmp_path / "pack.npz"
    np.savez(path, game_ids=["fixture", "other"], margin_support=[-7, 7],
             **{ev.ARM + "__margin": [[.4, .6]]})
    with pytest.raises(ValueError, match="align"):
        ev.load_margin(path, "fixture")
    np.savez(path, game_ids=["fixture"], margin_support=[-7, 7],
             smooth__R003_score_support__margin=[[.4, .6]])
    with pytest.raises(KeyError):
        ev.load_margin(path, "fixture")


def test_arbitrary_offer_handicap_is_evaluated_from_pmf_without_mean_or_labels():
    # At the market threshold 3, this PMF has 40% cover and 35% push. A quoted
    # home -2.5 has 75% cover and no push; reusing original cover fields is wrong.
    p, s = [.25, .35, .40], [-7, 3, 7]
    offers = [quote(handicap=-2.5, american_odds=-200, book="fixture", quote_id="q1")]
    result = ev.evaluate_offers(p, s, offers)
    row = result["offers"][0]
    assert row["cover_probability"] == pytest.approx(.75)
    assert row["push_probability"] == 0
    assert row["expected_units"] == pytest.approx(.75 * .5 - .25)
    assert row["quote"] == offers[0]
    assert offers == [quote(handicap=-2.5, american_odds=-200, book="fixture", quote_id="q1")]
