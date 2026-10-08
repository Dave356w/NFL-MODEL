"""Research helpers: the selection rule matches production and comparisons are same-game."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.special import ndtr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import _common as c  # noqa: E402
import final_week  # noqa: E402
import margin_target  # noqa: E402
import qb_variants  # noqa: E402
import returning_players  # noqa: E402
import stat_shrinkage  # noqa: E402


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


def _league(seed=7, teams=16, seasons=(2019, 2020, 2021, 2022), weeks=16):
    """Synthetic league: first-down rate tracks a fixed team strength; fumbles are pure noise."""
    rng = np.random.default_rng(seed)
    names = [f"T{i:02d}" for i in range(teams)]
    strength = dict(zip(names, np.linspace(-.06, .06, teams)))
    sched, box = [], []
    for yr in seasons:
        for wk in range(1, weeks + 1):
            order = list(rng.permutation(names))
            for i in range(0, teams, 2):
                h, a = order[i], order[i + 1]; gid = f"{yr}_{wk:02d}_{a}_{h}"
                res = float(round(2 + 100 * (strength[h] - strength[a]) + rng.normal(0, 10)))
                sched.append({"game_id": gid, "season": yr, "week": wk, "home_team": h, "away_team": a,
                              "gameday": f"{yr}-09-{wk:02d}", "gametime": "13:00", "site": 1., "result": res,
                              "home won": c.m.won(res), "spread_line": 0., "market WP": .5})
                for t, o in ((h, a), (a, h)):
                    plays = 64.; pp = 34.
                    box.append({"game_id": gid, "season": yr, "week": wk, "team": t, "opponent": o, "plays": plays,
                                "net_yards": 330., "net_pass_yards": 210., "rush_yards": 120., "pass_plays": pp,
                                "pass_attempts": pp - 2, "rush_attempts": plays - pp,
                                "first_downs": float(rng.binomial(int(plays), .3 + strength[t])),
                                "third_converted": 5., "third_attempts": 13.,
                                "fumbles_lost": float(rng.poisson(.8)), "interceptions": float(rng.poisson(.8)),
                                "sacks_taken": 2., "penalties": 6., "penalty_yards": 50.,
                                "top_seconds": 1800., "game_seconds": 3600.})
    return pd.DataFrame(sched), pd.DataFrame(box)


def test_reliability_k_small_for_stable_stats_large_for_noise():
    sched, box = _league()
    k, table, n = stat_shrinkage.reliability_k(box, sched)
    assert 7.5 < n < 8.5
    assert k[("for", "first_down_rate")] < 3        # strong team effect: little shrinkage
    assert k[("for", "fumbles_lost_per_game")] > 15  # pure noise: heavy shrinkage
    assert stat_shrinkage.k_from_r(-.2, 8.) == 64. and stat_shrinkage.k_from_r(.99, 8.) == 1.


def test_per_stat_k_of_four_reproduces_production_profiles():
    sched, box = _league(seasons=(2019, 2020), weeks=6, teams=8)
    prod = c.m.lagged_features(box, sched, 8.)
    keys = [(r, mt) for r in ("for", "allowed") for mt in c.m.RATES_CORE] + ["margin"]
    same, cols = stat_shrinkage.with_k(prod, box, sched, 8., {key: 4. for key in keys})
    assert len(cols) == 33 and "d__margin" in cols
    for col in cols:
        assert np.allclose(same[col], prod[col], equal_nan=True, rtol=0, atol=1e-9), col
    big, _ = stat_shrinkage.with_k(prod, box, sched, 8., {key: 64. for key in keys})
    col = "d__for__rates_core__first_down_rate"
    assert np.nanstd(big[col]) < .5 * np.nanstd(prod[col])  # more pseudo-games: profiles pulled together


def test_final_week_inputs_are_zero_outside_the_final_week():
    sched = pd.DataFrame({"season": [2021] * 3, "week": [16, 17, 18]})
    f = pd.DataFrame({"season": [2021] * 3, "week": [16, 17, 18], "home": ["A"] * 3, "away": ["B"] * 3})
    status = {("A", 2021, w): {"eliminated": 0., "clinched": 1., "top_seed": 1.} for w in (16, 17, 18)}
    status.update({("B", 2021, w): {"eliminated": 1., "clinched": 0., "top_seed": 0.} for w in (16, 17, 18)})
    out = final_week.add_final_week(f, status, sched)
    assert out["d__fw_clinched"].tolist() == [0., 0., 1.] and out["d__fw_eliminated"].tolist() == [0., 0., -1.]


def _returning_fixture(week9_status=None, p1_roster_week8="ACT"):
    """OL unit of five; P1 plays weeks 1-4 then is Out weeks 5-8; P2 is benched weeks 5-8 (no injury)."""
    snaps, inj, rost = [], [], []
    for wk in range(1, 9):
        players = ["P1", "P2", "P3", "P4", "P5"] if wk <= 4 else ["P3", "P4", "P5", "R1", "R2"]
        for pid in players:
            snaps.append({"season": 2021, "week": wk, "game_id": f"g{wk}", "team": "T", "gsis_id": pid,
                          "position": "T", "offense_snaps": 60., "defense_snaps": 0.})
        if wk >= 5: inj.append({"season": 2021, "week": wk, "team": "T", "gsis_id": "P1", "report_status": "Out"})
        for pid in ["P1", "P2", "P3", "P4", "P5", "R1", "R2"]:
            st = p1_roster_week8 if (pid == "P1" and wk == 8) else "ACT"
            rost.append({"season": 2021, "week": wk, "team": "T", "gsis_id": pid, "position": "T",
                         "status": st, "status_description_abbr": None})
    if week9_status:
        inj.append({"season": 2021, "week": 9, "team": "T", "gsis_id": "P1", "report_status": week9_status})
    targets = pd.DataFrame({"season": [2021], "week": [9], "team": ["T"]})
    ret = returning_players.returning_shares(targets, pd.DataFrame(snaps), pd.DataFrame(inj), pd.DataFrame(rost))
    return ret.set_index("team").loc["T"]


def test_returning_starter_is_credited_with_his_pre_absence_share():
    r = _returning_fixture()
    assert np.isclose(r.OL_ret, .2)                 # P1 only: 60 of 300 OL snaps; benched P2 earns nothing
    assert np.isclose(_returning_fixture("Questionable").OL_ret, .15)
    assert r.DL_ret == 0. and r.WRTE_ret == 0.


def test_returning_player_still_out_or_off_the_roster_earns_nothing():
    assert _returning_fixture("Out").OL_ret == 0.
    assert _returning_fixture(p1_roster_week8="RES").OL_ret == 0.  # prior-week roster still has him on reserve


def test_net_availability_subtracts_returning_share():
    avail = pd.DataFrame({"season": [2021], "week": [9], "team": ["T"], "OL_out_cs": [.3], "DL_out_cs": [np.nan],
                          **{f"{g}_out_cs": [0.] for g in ("WRTE", "RB", "LB", "DB")}})
    ret = pd.DataFrame({"season": [2021], "week": [9], "team": ["T"], "OL_ret": [.2],
                        **{f"{g}_ret": [0.] for g in ("WRTE", "RB", "DL", "LB", "DB")}})
    net = returning_players.net_availability(avail, ret)
    assert np.isclose(net.OL_out_cs[0], .1) and np.isnan(net.DL_out_cs[0]) and "OL_ret" not in net
