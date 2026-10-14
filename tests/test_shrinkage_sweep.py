import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import nfl_model as m

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research"))
import shrinkage_sweep as w  # noqa: E402


def test_protocol_values_match_production():
    w.check_values()
    names = w.arms()
    assert len(names) == 11 and names["production"] is None
    assert names["qb_prior=300"] == ("qb_prior", 300.) and names["fit_half_life=1"] == ("fit_half_life", 1.)
    assert all(v[1] != w.KNOBS[v[0]][1] for k, v in names.items() if v)  # no arm repeats production


def test_setting_restores_even_on_error():
    before = m.QB_PRIOR_DROPBACKS
    with pytest.raises(RuntimeError):
        with w.setting("QB_PRIOR_DROPBACKS", 999.):
            assert m.QB_PRIOR_DROPBACKS == 999.
            raise RuntimeError
    assert m.QB_PRIOR_DROPBACKS == before


def frame(n_weeks=6, seasons=(2021, 2022, 2023), seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        for wk in range(1, n_weeks + 1):
            for g in range(8):
                q = rng.uniform(.25, .75)
                rows.append({"game_id": f"{s}_{wk}_{g}", "season": s, "week": wk, "q": q,
                             "home won": float(rng.random() < q),
                             "home_moneyline": -150. if q > .5 else 130., "away_moneyline": 130. if q > .5 else -150.})
    t = pd.DataFrame(rows)
    y = t["home won"].to_numpy()
    for name in w.arms():
        t[name] = t.q
    t["qb_prior=300"] = np.clip(.8 * t.q + .2 * y, .01, .99)    # informative: better log loss
    t["pseudo_games=2"] = np.clip(.8 * t.q + .2 * (1 - y), .01, .99)  # anti-informative
    for name in w.arms():
        t[name + "|fp"] = m.favorite_penalized_wp(t[name].to_numpy(), t.q.to_numpy())
    t["market"] = t.q
    return t


def test_chosen_values_ties_go_to_production_and_best_wins():
    c = w.chosen_values(frame())
    assert c["qb_prior"]["chosen"] == "qb_prior=300"
    assert c["pseudo_games"]["chosen"] == "production"   # the worse arm loses
    assert c["retention"]["chosen"] == "production"      # exact tie with production


def test_annual_selection_uses_only_earlier_seasons():
    t = frame()
    t.loc[t.season == 2023, "qb_prior=300"] = .99  # a 2023-only change cannot affect the 2023 pick
    picks = w.annual_selected(t, (2022, 2023))
    assert [p["qb_prior"] for p in picks] == ["qb_prior=300", "qb_prior=300"]
    assert np.allclose(t.loc[t.season == 2023, "selected:qb_prior"], .99)
    t2 = frame()
    t2.loc[t2.season == 2021, "qb_prior=300"] = .5  # no information before 2022 → tie → production
    assert w.annual_selected(t2, (2022, 2022))[0]["qb_prior"] == "production"


def test_compare_pairs_and_roi_rows():
    t = frame()
    r = w.compare(t, ["production", "qb_prior=300", "pseudo_games=2"], .95)
    pairs = {p["arm"]: p for p in r["pairs"]}
    assert pairs["qb_prior=300"]["ll_gain"] > 0 and pairs["qb_prior=300"]["ll_gain_ci"][0] > 0
    assert pairs["pseudo_games=2"]["ll_gain"] < 0 and pairs["pseudo_games=2"]["ll_gain_ci"][1] < 0
    arms = [x["arm"] for x in r["results"]]
    assert arms[-1] == "market favorite" and r["bets"] == len(t)
    prod = next(x for x in r["results"] if x["arm"] == "production")
    fav = next(x for x in r["results"] if x["arm"] == "market favorite")
    assert prod["units"] == pytest.approx(fav["units"])  # production = q here, so same side as the favorite
    v = w.compare(t, ["production", "qb_prior=300"], .95, "|fp")
    assert v["results"][0]["log_loss"] == pytest.approx(prod["log_loss"])  # fp leaves p = q unchanged


def test_verdict_rules():
    assert w.verdict("production", None).startswith("keep production")
    assert w.verdict("qb_prior=300", {"ll_gain_ci": [.0001, .001]}).startswith("candidate")
    assert w.verdict("qb_prior=300", {"ll_gain_ci": [-.001, -.0001]}).startswith("keep production (arm worse")
    assert w.verdict("qb_prior=300", {"ll_gain_ci": [-.001, .001]}) == "unresolved, keep production"


def test_reproduce_rejects_drift(tmp_path, monkeypatch):
    ref = pd.DataFrame({"game_id": ["a", "b"], "production": [.6, .4]})
    ref.to_csv(tmp_path / "ref.csv", index=False)
    monkeypatch.setitem(w.REFERENCE, "confirm", (tmp_path / "ref.csv", "production"))
    ok = pd.DataFrame({"game_id": ["a", "b"], "prob": [.6, .4 + 1e-9]})
    assert w.reproduce("confirm", ok)["games"] == 2
    with pytest.raises(ValueError, match="reproduction failed"):
        w.reproduce("confirm", ok.assign(prob=[.6, .41]))
    with pytest.raises(ValueError, match="covers"):
        w.reproduce("confirm", ok.iloc[:1])
