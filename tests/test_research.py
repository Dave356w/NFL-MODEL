"""Research helpers: the selection rule matches production and comparisons are same-game."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import _common as c  # noqa: E402
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
