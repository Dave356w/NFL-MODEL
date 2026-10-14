"""De-vig robustness: the no-vig market anchor (q) under varying holds and price asymmetry.

Every market baseline in the repo (market_ml_wp, flat_bets q and null_ev, the Kalshi ladder's
fav_wp, research price_probability) normalizes the two American-odds implied probabilities
proportionally: q = i_home / (i_home + i_away). These tests pin that anchor's properties from a
standard -110/-110 pair to asymmetric -350/+280 juice, and check that every copy agrees.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import kalshi as k
import nfl_model as m

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import margin_total_models as t  # noqa: E402

# (home ML, away ML, exact proportional no-vig home probability)
QUOTES = [
    (-110, -110, .5),
    (-105, -115, (105 / 205) / (105 / 205 + 115 / 215)),
    (-150, 130, (150 / 250) / (150 / 250 + 100 / 230)),
    (-350, 280, (350 / 450) / (350 / 450 + 100 / 380)),
    (280, -350, (100 / 380) / (350 / 450 + 100 / 380)),
    (-1000, 650, (1000 / 1100) / (1000 / 1100 + 100 / 750)),
]


def frame(quotes):
    return pd.DataFrame({"home_moneyline": [h for h, _, *_ in quotes], "away_moneyline": [a for _, a, *_ in quotes]})


def american(decimal):
    """Fair-rounded American odds for a decimal price (no cent rounding)."""
    return (decimal - 1) * 100 if decimal >= 2 else -100 / (decimal - 1)


def hold(h, a):
    return m.ml_implied(h) + m.ml_implied(a) - 1


def test_known_quotes_standard_and_asymmetric():
    q = m.market_ml_wp(frame(QUOTES))
    assert np.allclose(q, [x[2] for x in QUOTES], atol=1e-12)
    assert q[0] == .5                                   # -110/-110: exactly a coin flip
    assert q[3] == pytest.approx(.7471, abs=1e-4)       # -350/+280
    assert hold(-110, -110) == pytest.approx(.0476, abs=1e-4) and hold(-350, 280) == pytest.approx(.0409, abs=1e-4)


def test_complement_and_side_swap():
    """The two sides' anchors sum to one, and swapping home/away mirrors q exactly."""
    q = m.market_ml_wp(frame(QUOTES))
    swapped = m.market_ml_wp(frame([(a, h) for h, a, _ in QUOTES]))
    assert np.allclose(q + swapped, 1., atol=1e-12)
    assert np.all((q > 0) & (q < 1))


def test_sign_branch_is_continuous_at_even_money():
    """-100 and +100 are the same price; both branches of ml_implied must agree there."""
    assert m.ml_implied(-100) == m.ml_implied(100) == .5
    assert m.market_ml_wp(frame([(-100, 100), (100, -100), (100, 100)])).tolist() == [.5, .5, .5]
    eps = 1e-9
    assert m.ml_implied(-100 - eps) == pytest.approx(m.ml_implied(100 + eps), abs=1e-9)


@pytest.mark.parametrize("q_true", [.5, .55, .6524, .7472, .85, .88])
@pytest.mark.parametrize("overround", [1.0, 1.02, 1.0476, 1.08, 1.12])
def test_anchor_recovers_fair_price_at_any_proportional_hold(q_true, overround):
    """A book that scales both fair probabilities by the same overround leaves q unchanged:
    the anchor does not drift with the size of the vig."""
    hm, am = american(1 / (overround * q_true)), american(1 / (overround * (1 - q_true)))
    q = m.market_ml_wp(frame([(hm, am)]))[0]
    assert q == pytest.approx(q_true, abs=1e-12)
    assert hold(hm, am) == pytest.approx(overround - 1, abs=1e-12)


def test_anchor_stable_under_cent_rounded_quotes():
    """Real quotes round to whole cents. Widening the hold around the same fair -350/+280 anchor
    moves q by well under a point; the -110/-110 anchor does not move at all."""
    for h, a in [(-110, -110), (-105, -105), (-120, -120), (-125, -125)]:
        assert m.market_ml_wp(frame([(h, a)]))[0] == .5
    base = m.market_ml_wp(frame([(-350, 280)]))[0]
    ladder = [(-330, 290), (-340, 285), (-350, 280), (-360, 270), (-375, 265), (-400, 250)]
    qs = m.market_ml_wp(frame(ladder))
    holds = [hold(h, a) for h, a in ladder]
    assert min(holds) < .03 and max(holds) > .045        # the ladder spans narrow to wide juice
    assert np.all(np.abs(qs - base) < .015)              # observed max drift ~1.0 pt (-400/+250)


def test_monotone_in_each_price():
    favs = m.market_ml_wp(frame([(h, 200) for h in (-110, -150, -200, -350, -600)]))
    dogs = m.market_ml_wp(frame([(-250, a) for a in (110, 150, 200, 280, 400)]))
    assert np.all(np.diff(favs) > 0) and np.all(np.diff(dogs) > 0)  # longer dog → stronger home anchor


def test_market_null_is_minus_the_hold_on_either_side():
    """Proportional de-vig makes the market-correct null EV of a 1u bet equal 1/overround - 1
    on BOTH sides: negative by the hold, zero only without vig, independent of price asymmetry."""
    for q_true in (.5, .7472, .9):
        for overround in (1.0, 1.0476, 1.10):
            hm, am = american(1 / (overround * q_true)), american(1 / (overround * (1 - q_true)))
            d = frame([(hm, am), (hm, am)]).assign(model_wp=[.9, .1])  # back home, then away
            b = m.flat_bets(d)
            assert list(b.side) == ["home", "away"]
            assert np.allclose(b.null_ev, 1 / overround - 1, atol=1e-12)
            assert b.q.sum() == pytest.approx(1., abs=1e-12)


def test_null_ev_on_listed_quotes_is_negative_and_side_neutral():
    for h, a, _ in QUOTES:
        b = m.flat_bets(frame([(h, a), (h, a)]).assign(model_wp=[.9, .1]))
        assert b.null_ev.iloc[0] == pytest.approx(b.null_ev.iloc[1], abs=1e-12)
        assert b.null_ev.iloc[0] == pytest.approx(1 / (1 + hold(h, a)) - 1, abs=1e-12)
        assert b.null_ev.iloc[0] < 0


def test_every_copy_of_the_devig_agrees():
    """flat_bets q, market_ml_wp, the Kalshi ladder's ml_implied and research price_probability
    are separate implementations; they must give the same anchor on the same quotes."""
    d = frame(QUOTES)
    q = m.market_ml_wp(d)
    fb = m.flat_bets(d.assign(model_wp=np.where(q >= .5, .99, .01)))
    assert np.allclose(np.where(fb.side == "home", fb.q, 1 - fb.q), q, atol=1e-12)
    assert np.allclose(t.price_probability(d.home_moneyline, d.away_moneyline), q, atol=1e-12)
    for (h, a, _), qi in zip(QUOTES, q):
        assert k.ml_implied(h) == m.ml_implied(h) and k.ml_implied(a) == m.ml_implied(a)
        ih, ia = k.ml_implied(h), k.ml_implied(a)
        assert ih / (ih + ia) == pytest.approx(qi, abs=1e-12)


def test_invalid_prices_give_no_anchor():
    """Missing, non-numeric or sub-100 American odds give NaN, never a fabricated 50%."""
    bad = pd.DataFrame({"home_moneyline": [np.nan, None, "x", 0, 50, -99, -110],
                        "away_moneyline": [-110, -110, -110, -110, -110, -110, np.nan]})
    assert np.isnan(m.market_ml_wp(bad)).all()
    b = m.flat_bets(bad.assign(model_wp=.9))
    assert b.q.isna().all() and b.null_ev.isna().all()
    assert np.isnan(t.price_probability(pd.to_numeric(bad.home_moneyline, errors="coerce"), bad.away_moneyline)).all()


@pytest.mark.xfail(strict=True, reason="flat_bets validates only the backed side's price; an invalid "
                   "opposite price (0, 50, inf) still yields a q. Data validation keeps these out of the ledger.")
def test_flat_bets_requires_both_prices_valid():
    bad = frame([(-110, 0), (-110, 50), (-110, np.inf)]).assign(model_wp=.9)
    assert m.flat_bets(bad).q.isna().all()
