"""Research ATS probabilities: chronology, key-number PMF, EV, shadow immutability."""
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from research import ats_cover_probability as c
from research import ats_forward_shadow as shadow


def mock_history():
    # Many independent weeks / two full previous seasons, deterministic margins.
    rows = []
    for season in (2021, 2022, 2023):
        for week in range(1, 17):
            for i in range(12):
                line = float([-7.5, -3.5, -2.5, 0, 2.5, 3.5, 7.5, 10][i % 8])
                margin = float(round(line + [-14, -7, -3, 0, 3, 7, 14, 10][(i+week) % 8]))
                spread = line + (-1 if i % 3 == 0 else 1.5)
                rows.append({"game_id": f"{season}_{week}_{i}", "season": season, "week": week,
                             "result": margin, "spread_line": line,
                             "model_spread": spread,
                             "fixed_band_spread": 5 if spread >= 0 else -5,
                             "basis": "synthetic"})
    return pd.DataFrame(rows)


def test_fit_uses_only_previous_seasons():
    d = mock_history()
    previous = d[d.season < 2023]
    model = c.fit_prior(previous, 2023)
    assert model["training_max_season"] == 2022
    assert model["n_training"] == 384
    assert model["target_season"] == 2023
    assert len(model["boosts"]) == 71
    assert model["boosts"][3] > 0 and model["boosts"][7] > 0
    with pytest.raises(ValueError, match="future"):
        c.fit_prior(d, 2023)
    preds, fits = c.evaluate(d)
    assert fits[0]["training_max_season"] == 2022
    assert len(preds) == 192
    # Poisoning 2023 labels never affects the 2023 predictions.
    poison = d.copy()
    poison.loc[poison.season == 2023, "result"] = 50
    changed, _ = c.evaluate(poison)
    for field in ("corrected_home_cover", "corrected_away_cover",
                  "corrected_push", "beta_prior", "market_home_cover"):
        np.testing.assert_allclose(preds[field], changed[field])


def test_pmf_preserves_key_numbers_and_pushes():
    fit = c.fit_prior(mock_history().query("season < 2023"), 2023)
    for line in (0., 3., -3., 7., -7., 3.5):
        market, corrected = c.distribution(line, 2.5, fit)
        assert np.isclose(market.sum(), 1.)
        assert np.isclose(corrected.sum(), 1.)
        hm, am, pu = c.event(market, line)
        assert np.isclose(hm + am + pu, 1.)
        assert np.isclose(hm / (hm + am), .5, atol=2e-7)
        if line == int(line):
            assert pu > 0
        else:
            assert pu == pytest.approx(0., abs=1e-10)


def test_grade_side_push_and_ev_accounting():
    assert c.grade(3, 3, "home") == ("P", 0.)
    assert c.grade(4, 3, "home") == ("W", 10/11)
    assert c.grade(2, 3, "away") == ("W", 10/11)
    assert c.grade(2, 3, "home") == ("L", -1.)
    assert c.grade(4, 3, "") == ("S", 0.)
    d, fits = c.evaluate(mock_history())
    assert d.groupby("game_id").size().max() == 1
    assert len(d) == 192 and len(fits) == 1
    assert np.allclose(d.market_home_cover / (d.market_home_cover+d.market_away_cover), .5, atol=1e-7)
    assert (d.cover_probability_grade == "S").any() or (
        (d.cover_probability_side != "") & (d[["home_ev_110", "away_ev_110"]].max(axis=1)>0)).all()
    result = c.report(d, fits)
    assert result["arms"]["fixed_band"]["games"] == 192
    assert result["nonpush_games"] <= 192
    assert "paired_fixed_vs_original_matched" in result
    assert "cover_log_loss" in result["paired_score_gains"]
    ll = result["paired_score_gains"]["cover_log_loss"]
    assert ll["n"] <= 192 and ll["clusters"] == 16
    assert np.isfinite(ll["gain"])
    assert ll["CI95_normal"][0] <= ll["gain"] <= ll["CI95_normal"][1]


def test_shadow_first_lock_no_backfill_and_idempotence(tmp_path):
    now = dt.datetime(2026, 10, 17, 12, 0, tzinfo=dt.timezone.utc)
    data = tmp_path / "data"
    latest = data / "latest"
    latest.mkdir(parents=True)
    mock_history().to_csv(latest / "fixed_band_ledger.csv", index=False)
    rules = [{"season": 2026, "training_max_season": 2025,
              "cuts": [3., 7., 10.], "magnitudes": [3., 4., 7., 14.],
              "policy_version": shadow.POLICY_VERSION, "method": "median_signed_mov"}]
    (latest / "fixed_band_rules.json").write_text(json.dumps(rules))
    # Need prior observations up through 2025 to fit 2026.
    d = mock_history()
    d.loc[d.season == 2023, "season"] = 2025
    d.to_csv(latest / "fixed_band_ledger.csv", index=False)
    base = {"revision": shadow.REVISION, "game_id": "2026_07_AWAY_HOME",
            "season": 2026, "week": 7, "away": "AWAY", "home": "HOME",
            "model_wp": .59, "spread_line": 3.,
            "generated_utc": "2026-10-17T11:30:00+00:00",
            "kickoff_utc": "2026-10-17T20:00:00+00:00"}
    old = dict(base, game_id="2026_06_OLD_GAME",
               generated_utc="2026-10-15T23:00:00+00:00")
    later = dict(base, generated_utc="2026-10-17T11:40:00+00:00",
                 model_wp=.90)
    path = data / "forward_predictions.jsonl"
    path.write_text("\n".join(json.dumps(v) for v in (base, later, old)) + "\n")
    assert shadow.record(data, now) == 1
    snap = shadow.read_jsonl(data / shadow.STATE)
    assert len(snap) == 1
    r = snap[0]
    assert r["game_id"] == base["game_id"] and r["training_max_season"] == 2025
    assert r["research_only"] and r["quote_basis"] == "unverified_proxy_only"
    assert r["policy_version"] == shadow.POLICY_VERSION
    assert r["archived_utc"] == now.isoformat()
    assert r["selected_side"] == r["fixed_band_side"]
    assert r["skip_reason"] == ("zero_edge" if not r["selected_side"] else None)
    assert np.isclose(r["market_p_home_cover"]+r["market_p_away_cover"]+
                      r["market_p_push"], 1.)
    assert r["raw_spread"] < float(shadow.cp.SIGMA * shadow.ndtri(.9))
    assert r["fixed_band_side"] in ("home", "away", "")
    assert np.isclose(r["p_home_cover"]+r["p_away_cover"]+r["p_push"],1.)
    before = (data / shadow.STATE).read_bytes()
    assert shadow.record(data, now) == 0
    assert (data / shadow.STATE).read_bytes() == before
    # If the earliest snapshot predates launch, later generated copies cannot
    # be used to backfill a supposedly native shadow.
    past = dict(base, generated_utc="2026-10-15T23:30:00+00:00")
    path.write_text("\n".join(json.dumps(v) for v in (past, base)) + "\n")
    assert shadow.possible_locks(data, now) == []
    # A first lock earlier on adoption day is also excluded from the new policy.
    past = dict(base, generated_utc="2026-10-17T05:30:00+00:00")
    path.write_text("\n".join(json.dumps(v) for v in (past, base)) + "\n")
    assert shadow.possible_locks(data, now) == []


def test_shadow_rejects_superseded_mapping_identity():
    with pytest.raises(ValueError, match="median-MOV policy"):
        shadow.freeze({'season': 2026}, mock_history(),
                      {'training_max_season': 2025, 'cuts': [3, 7, 10],
                       'magnitudes': [4, 5, 7, 13]})


def test_shadow_summary_never_pools_policy_versions():
    d = pd.DataFrame({'season': [2026, 2026], 'result': [1., 1.],
        'policy_version': ['old-fixed-band', shadow.POLICY_VERSION],
        **{arm+'_result': ['W', 'L'] for arm in ('raw', 'fixed_band', 'cover_probability')},
        **{arm+'_units_proxy_minus110': [10/11, -1.]
           for arm in ('raw', 'fixed_band', 'cover_probability')}})
    s = shadow.summary(d)
    all_rows = s.query("season == 'All' and policy == 'fixed_band'")
    assert set(all_rows.policy_version) == {'old-fixed-band', shadow.POLICY_VERSION}
    assert list(all_rows.opportunities) == [1, 1]


def test_shadow_no_record_after_kickoff(tmp_path):
    data = tmp_path
    r = {"revision": shadow.REVISION, "game_id": "g", "generated_utc":
         "2026-10-17T11:30:00+00:00", "kickoff_utc": "2026-10-17T11:45:00+00:00",
         "model_wp": .55, "spread_line": 3}
    (data / "forward_predictions.jsonl").write_text(json.dumps(r)+"\n")
    assert shadow.possible_locks(data, dt.datetime.fromisoformat("2026-10-17T12:00:00+00:00")) == []
    assert shadow.record(data, dt.datetime.fromisoformat("2026-10-17T12:00:00+00:00")) == 0


def test_native_shadow_three_way_scores_include_skips_and_pushes(tmp_path):
    data = tmp_path
    base = {
        "revision": shadow.REVISION, "season": 2026, "week": 8,
        "market_spread": 3., "p_home_cover": .6, "p_away_cover": .3, "p_push": .1,
        "market_p_home_cover": .475, "market_p_away_cover": .475, "market_p_push": .05,
        "generated_utc": "2026-10-16T15:00:00+00:00"}
    sides = ["home", "", "away"]
    rows = [dict(base, game_id=f"2026_08_{k}", raw_side="home",
                 fixed_band_side=side, probability_side="away")
            for k, side in enumerate(sides)]
    (data / shadow.STATE).write_text("".join(json.dumps(r)+"\n" for r in rows))
    pd.DataFrame({
        "revision": [shadow.REVISION]*3,
        "game_id": [r["game_id"] for r in rows],
        "generated_utc": [r["generated_utc"] for r in rows],
        "status": ["final"]*3,
        "result": [5., 2., 3.]
    }).to_csv(data / "forward_ledger.csv", index=False)
    graded = shadow.graded_view(data)
    assert list(graded.fixed_band_result) == ["W", "S", "P"]
    np.testing.assert_allclose(graded.model_ats_3way_log_loss,
                               -np.log([.6, .3, .1]))
    np.testing.assert_allclose(graded.market_ats_3way_log_loss,
                               -np.log([.475, .475, .05]))
    assert graded.model_ats_3way_brier.notna().all()
    records = shadow.summary(graded)
    fixed = records.query("policy == 'fixed_band' and season == 'All'").iloc[0]
    assert fixed.opportunities == 3 and fixed.selections == 2 and fixed.skips == 1
    assert fixed.wins == 1 and fixed.pushes == 1 and fixed.losses == 0
    assert fixed.selection_rate == 2/3
    assert np.isclose(fixed.model_3way_ll, -np.log([.6, .3, .1]).mean())


def test_legacy_shadow_missing_market_control_is_not_backfilled(tmp_path):
    data = tmp_path
    r = {"revision": shadow.REVISION, "game_id": "2026_08_legacy",
         "season": 2026, "market_spread": 3., "generated_utc": "2026-10-16T15:00:00+00:00",
         "fixed_band_side": "home", "raw_side": "home", "probability_side": "home",
         "p_home_cover": .5, "p_away_cover": .5, "p_push": 0.}
    (data / shadow.STATE).write_text(json.dumps(r)+"\n")
    pd.DataFrame([{"revision": shadow.REVISION, "game_id": r["game_id"],
                   "generated_utc": r["generated_utc"], "status": "final",
                   "result": 4.}]).to_csv(data / "forward_ledger.csv", index=False)
    d = shadow.graded_view(data)
    assert "model_ats_3way_log_loss" in d
    assert "market_ats_3way_log_loss" not in d
    assert np.isfinite(shadow.summary(d).iloc[0].model_3way_ll)
