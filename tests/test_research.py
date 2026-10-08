"""Research helpers: the selection rule matches production and comparisons are same-game."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.special import ndtr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import _common as c  # noqa: E402
import margin_target  # noqa: E402
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


def _margin_schedule(seed=5, seasons=(2021,), weeks=12):
    """Round-robin-ish schedule: 8 teams, true ratings, home edge 2, small noise."""
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(8)]
    rating = dict(zip(teams, np.linspace(-7, 7, 8)))
    rows = []
    for yr in seasons:
        for wk in range(1, weeks + 1):
            order = list(rng.permutation(teams))
            for i in range(0, 8, 2):
                h, a = order[i], order[i + 1]
                res = round(2 + rating[h] - rating[a] + rng.normal(0, 1))
                rows.append({"game_id": f"{yr}_{wk:02d}_{a}_{h}", "season": yr, "week": wk, "home_team": h,
                             "away_team": a, "result": float(res), "site": 1.})
    return pd.DataFrame(rows), rating


def test_adjusted_margin_recovers_schedule_adjusted_ratings():
    sched, rating = _margin_schedule()
    r = margin_target.adjusted_margins(sched, sched.rename(columns={"home_team": "team"}), 8.)
    est = {t: r[(t, 2021, 12)] for t in rating}
    assert np.corrcoef(list(est.values()), list(rating.values()))[0, 1] > .97
    assert all(r[(t, 2021, 1)] == 0. for t in rating)  # week 1 of the first season: no earlier games


def test_adjusted_margin_ignores_current_and_later_games():
    sched, _ = _margin_schedule()
    a = margin_target.adjusted_margins(sched, sched, 8.)
    later = sched.copy(); later.loc[later.week >= 6, "result"] += 40.
    b = margin_target.adjusted_margins(later, later, 8.)
    assert all(a[k] == b[k] for k in a if k[2] <= 6)
    assert any(a[k] != b[k] for k in a if k[2] == 7)  # a changed earlier game does move later ratings


def test_margin_fit_recovers_coefficients_and_probability():
    rng = np.random.default_rng(1)
    n = 400
    df = pd.DataFrame({"season": 2022, "week": rng.integers(1, 18, n), "ready": True, "site": 1.,
                       "x1": rng.normal(0, 1, n), "x2": rng.normal(0, 1, n)})
    df["result"] = 2 + 3 * df.x1 - 1 * df.x2 + rng.normal(0, 10, n)
    saved = c.m.feature_names
    try:
        c.m.feature_names = lambda fam: ["site", "x1", "x2"]
        fit = margin_target.fit_margin(df, {"family": "f", "half_life": 8., "ridge": 1e-6}, 2023, 1)
    finally:
        c.m.feature_names = saved
    coef = np.asarray(fit["beta"]) / fit["scale"]
    assert abs(coef[1] - 3) < 1.5 and abs(coef[2] + 1) < 1.5 and 8 < fit["sigma"] < 12
    p, mu = margin_target.apply_margin(df.head(3), fit)
    assert np.allclose(p, ndtr(mu / fit["sigma"]))
    future = df.assign(season=2023, week=2)
    with pytest.raises(ValueError):
        margin_target.fit_margin(pd.concat([df, future]), {"family": "f", "half_life": 8., "ridge": 1.}, 2023, 1)
