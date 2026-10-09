"""Research helpers: the selection rule matches production and comparisons are same-game."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import _common as c  # noqa: E402
import availability_audit as aa  # noqa: E402
import qb_variants  # noqa: E402


def oof():
    rng = np.random.default_rng(3)
    rows = []
    for yr in (2021, 2022, 2023, 2024, 2025):
        for i in range(40):
            y = float(rng.random() < .55)
            rows.append({"game_id": f"{yr}_{i:02d}", "season": yr, "week": 1 + i % 17, "home won": y,
                         "home_moneyline": -150., "away_moneyline": 130.,
                         # 'good' tracks the outcome before 2023 only; 'flat' never does
                         "p__fam_h8_r0.1": (.8 if y else .2) if yr < 2023 else .6,
                         "p__fam_h8_r1": .55, "p__other_h8_r0.1": .9 if y else .1})
    return pd.DataFrame(rows)


def test_outer_selects_on_earlier_seasons_only_and_within_family():
    held, picks = c.outer(oof(), ("fam",))
    assert picks == {2023: "fam_h8_r0.1", 2024: "fam_h8_r0.1", 2025: "fam_h8_r0.1"}  # not 'other' (other family)
    assert set(held.season) == {2023, 2024, 2025} and (held.model_wp == .6).all()


def test_paired_difference_is_same_game():
    o = oof()
    a = c.score(c.outer(o, ("fam",))[0])
    b = c.score(c.outer(o, ("other",))[0])
    du, se, dl, sl = c.paired(a, b)
    assert np.isclose(du, a["roi"] - b["roi"]) and dl < 0  # 'other' is clairvoyant: better log loss


def test_backup_start_flag():
    av = pd.DataFrame({"qb_expected": ["A", "B", c.m.NO_QB_LABEL, None], "qb_usual": ["A", "C", "C", None]})
    assert qb_variants.with_qb_change(av).qb_change.tolist() == [0., 1., 2., 0.]


def test_practice_label():
    assert aa.practice_label("Questionable", "Did Not Participate In Practice") == "Q/DNP"
    assert aa.practice_label("Questionable", "Limited Participation in Practice") == "Q/Lim"
    assert aa.practice_label("Questionable", None) == "Q/-"
    assert aa.practice_label("Out", "Full Participation in Practice") == "Out"
    assert aa.practice_label(None, "Did Not Participate In Practice") == "practice/DNP"
    assert aa.calibrated_weight("Doubtful", {}) == 1. and aa.calibrated_weight("practice/Full", {}) == 0.


def test_profile_weights_match_lagged_features_decay():
    w = aa.profile_weights([2024, 2025, 2025], 2025, half_life=8.)
    assert np.allclose(w, [2 ** (-2 / 8) * c.m.OFFSEASON_RETENTION, 2 ** (-1 / 8), 1.])


def test_profile_measures_credit_returns_only():
    # Four equal-weight prior games, two unit slots per game. Columns: S starter (missed games 1-2
    # on a reserve list), B backup (filled in, never missed), C regular, A arrival (first game 3).
    P = np.array([[.5, 0, .5, 0], [0, .5, .5, 0], [0, .5, .5, 0], [.5, 0, 0, .5]])
    missed = np.zeros((4, 4), bool); missed[1:3, 0] = True
    on = np.ones((4, 4), bool); on[:3, 3] = False
    W = np.ones(4)
    # C out now: absent = C's decayed share; S back: credit = healthy .5 x missed weight 2/4.
    absent, ret = aa.profile_measures(P, W, np.array([0., 0., 1., 0.]), missed, on)
    assert np.isclose(absent, .375) and np.isclose(ret, .25)
    # Nobody missed anything: a backup or an arrival never earns return credit.
    assert aa.profile_measures(P, W, np.zeros(4), np.zeros((4, 4), bool), on)[1] == 0.
    # S out again: no credit, and his share still in the profile counts as absent.
    absent, ret = aa.profile_measures(P, W, np.array([1., 0., 0., 0.]), missed, on)
    assert np.isclose(absent, .25) and ret == 0.
    # A Questionable return earns credit in proportion to availability.
    assert np.isclose(aa.profile_measures(P, W, np.array([.25, 0., 0., 0.]), missed, on)[1], .75 * .25)


def test_same_week_reserve_or_gone():
    rost = pd.DataFrame({"season": 2025, "week": [1, 1, 1, 2, 2], "team": "KC",
                         "gsis_id": ["A", "B", "C", "A", "B"], "position": "WR",
                         "status": ["ACT", "ACT", "ACT", "RES", "ACT"],
                         "status_description_abbr": [None, None, None, "R01", None]})
    inj = pd.DataFrame(columns=["season", "week", "team", "gsis_id", "report_status"])
    r = aa.Roster(rost, inj)
    assert r.gone(2025, 2, "KC", "A")        # moved to IR in the game week
    assert r.gone(2025, 2, "KC", "C")        # gone from the game-week roster
    assert not r.gone(2025, 2, "KC", "B")    # still active
    assert not r.gone(2025, 1, "KC", "C")    # week 1 already uses its own roster
    assert not r.gone(2025, 3, "KC", "A")    # no roster rows that week: no claim
    out, ref = r.status(2025, 2, "KC")       # production's rule still reads week 1
    assert ref == {"A", "B", "C"} and out == {}
