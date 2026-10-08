"""Page rendering from a synthetic data/ folder (no network, no model run)."""
import datetime as dt
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import build_site as b
import grade_ledger as g
import nfl_model as m

NOW = dt.datetime(2026, 10, 7, 15, tzinfo=dt.timezone.utc)  # Wednesday


def make_data(root, with_ledger=True):
    rng = np.random.default_rng(1)
    latest = root / "latest"
    latest.mkdir(parents=True)
    board = pd.DataFrame([
        {"game_id": "2026_05_TB_DAL", "season": 2026, "week": 5, "away": "TB", "home": "DAL",
         "gameday": "2026-10-08", "gametime": "20:15", "site": 1., "result": np.nan, "ready": True,
         "spread_line": 9.5, "market_wp": .78, "model_wp": .60, "homefield_wp": .54,
         "home_moneyline": -485, "away_moneyline": 370,
         "away_qb_expected": "J.Daniels", "away_qb_usual": "B.Mayfield", "home_qb_expected": "D.Prescott",
         "home_qb_usual": "D.Prescott", "away_injury_report": "none", "home_injury_report": "none",
         "home__avail__qb_delta": .1, "away__avail__qb_delta": -.5, "home__avail__OL_out_cs": .1, "away__avail__OL_out_cs": 0.},
        {"game_id": "2026_05_KC_BUF", "season": 2026, "week": 5, "away": "KC", "home": "BUF",
         "gameday": "2026-10-04", "gametime": "16:25", "site": 1., "result": 7., "home won": 1., "away_score": 20, "home_score": 27,
         "ready": True, "spread_line": 2.5, "market_wp": .58, "model_wp": .55, "homefield_wp": .54,
         "home_moneyline": -135, "away_moneyline": 115,
         "away_injury_report": "final", "home_injury_report": "final"}])
    board.to_csv(latest / "board.csv", index=False)
    pd.DataFrame([{"game_id": "2026_05_TB_DAL", "game": "TB@DAL", "feature": "site",
                   "home-minus-away input": 1, "log-odds contribution": .2, "direction": "home"}]).to_csv(latest / "contributions.csv", index=False)
    hist = pd.DataFrame({"season": 2024, "week": 1, "home won": (rng.random(300) < .55).astype(float),
                         "model_wp": rng.uniform(.2, .8, 300), "market_wp": rng.uniform(.2, .8, 300),
                         "homefield_wp": .55})
    m.calibration_bands(hist).to_csv(latest / "calibration_bands.csv", index=False)
    ml = pd.DataFrame({"home_moneyline": np.where(hist.market_wp > .5, -150, 130),
                       "away_moneyline": np.where(hist.market_wp > .5, 130, -150)})
    roi_hist = pd.concat([hist, ml], axis=1)
    m.roi_table(roi_hist).to_csv(latest / "roi_bands.csv", index=False)
    m.roi_table(roi_hist, by="season").to_csv(latest / "roi_by_season.csv", index=False)
    m.roi_table(roi_hist.iloc[:0]).to_csv(latest / "season_roi.csv", index=False)
    retro = roi_hist.assign(game_id=[f"g{i}" for i in range(len(roi_hist))], week=1, home="DAL", away="TB",
                            result=np.where(roi_hist["home won"] == 1, 3., -3.), spread_line=1.,
                            basis="backtest (recipe chosen on these seasons)")
    bets = m.flat_bets(retro)
    retro = retro.assign(bet_side=bets.side, bet_team=np.where(bets.side == "home", "DAL", "TB"), bet_price=bets.price,
                         bet_band=bets.band, bet_q=bets.q, bet_result=bets.result, units=bets.units, null_ev=bets.null_ev,
                         market_ml_wp=m.market_ml_wp(retro), home_score=20, away_score=17)
    retro.to_csv(latest / "retro_ledger.csv", index=False)
    m.roi_table(retro, by="season").to_csv(latest / "retro_roi_by_season.csv", index=False)
    m.roi_table(retro).to_csv(latest / "retro_roi_bands.csv", index=False)
    pd.DataFrame([{"key": "rates_core_avail_cs_h8_r0.1", "log loss": .638, "bets": 300, "units": -2., "roi": -.0067,
                   "roi_se": .022}]).to_csv(latest / "candidate_roi.csv", index=False)
    m.band_records(hist).to_csv(latest / "band_records.csv", index=False)
    old = m.BOOTSTRAP_REPS
    m.BOOTSTRAP_REPS = 50
    try:
        m.scorecard(hist).to_csv(latest / "outer_scorecard.csv", index=False)
        pd.concat([m.scorecard(hist).assign(season=2024)]).to_csv(latest / "outer_by_season.csv", index=False)
        m.scorecard(hist).to_csv(latest / "season_scorecard.csv", index=False)
    finally:
        m.BOOTSTRAP_REPS = old
    pd.DataFrame([{"family": "rates_core_avail_cs", "half_life": 8., "ridge": .1, "key": "rates_core_avail_cs_h8_r0.1",
                   "log loss": .638, "games": 1355, "selected": True}]).to_csv(latest / "recipe_selection.csv", index=False)
    pd.DataFrame([{"feature": "site", "label": "Home field", "coefficient per scaled unit": .2,
                   "training scale": 1., "training missing fraction": 0.}]).to_csv(latest / "weights.csv", index=False)
    pd.DataFrame().to_csv(latest / "market_blend.csv", index=False)
    (latest / "manifest.json").write_text(json.dumps({
        "revision": m.REVISION, "season": 2026, "week": 5, "generated_utc": "2026-10-07T14:00:00+00:00",
        "recipe": {"family": "rates_core_avail_cs", "half_life": 8., "ridge": .1},
        "market_blend_verdict": "Composite weight -0.1: no reliable evidence.", "limitations": ["a limitation"],
        "availability_audit": [{"source": "availability_roster_membership", "team_weeks": 10, "off_roster_snap_share": .066}]}))
    (latest / "board.html").write_text("<html>board</html>")
    pd.DataFrame([{"team": "TB", "gsis_id": "x", "player": "Baker Mayfield", "position": "QB", "unit": "QB",
                   "snap_share": .74, "prev_week": 4, "prev_status": "Out", "prev_injury": "Thumb",
                   "this_week": "not on a week-5 report yet", "counted": 0., "report_state": "none"}]
                 ).to_csv(latest / "report_notes.csv", index=False)
    if with_ledger:
        recs = [{"experiment": "e", "revision": m.REVISION, "game_id": "2026_05_KC_BUF", "season": 2026, "week": 5,
                 "home": "BUF", "away": "KC", "generated_utc": "2026-10-03T12:00:00+00:00",
                 "kickoff_utc": "2026-10-04T20:25:00+00:00", "model_wp": .55, "market_wp": .58,
                 "homefield_wp": .54, "spread_line": 2.5, "home_moneyline": -135, "away_moneyline": 115,
                 "injury_report": {"home": "final", "away": "final"}}]
        res = pd.DataFrame({"game_id": ["2026_05_KC_BUF"], "away_score": [20], "home_score": [27], "result": [7]})
        g.write_outputs(g.grade(recs, res), root)
    return root


def render(tmp_path, **kw):
    data = make_data(tmp_path / "data", **kw)
    out = tmp_path / "public"
    files = b.render_all(out, data, now=NOW)
    return out, files


PUBLIC = ("index.html", "grades.html", "market-calibration.html")


def visible_text(html):
    html = re.sub(r"<style>.*?</style>|<script>.*?</script>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def test_three_public_pages_with_nav_and_no_nan(tmp_path):
    out, files = render(tmp_path)
    assert set(PUBLIC) | {"ledger_report.txt", ".nojekyll"} == set(files)
    assert "model.html" not in files and "board.html" not in files
    for name in PUBLIC:
        html = (out / name).read_text()
        assert html.startswith("<!doctype html>") and "aria-current=\"page\"" in html
        assert all(f"href='{h}'" in html for h, _ in b.PAGES) and "model.html" not in html
        text = visible_text(html)
        assert not re.search(r"\bnan\b|\bNaN\b|\bNone\b", text), name


def test_public_pages_carry_no_analyst_units_or_model_internals(tmp_path):
    out, _ = render(tmp_path)
    for name in PUBLIC:
        text = visible_text((out / name).read_text())
        for banned in ("±", " SE", "log loss", "Log loss", "no-vig q", "Excess", "excess pp", "Mkt null",
                       "rates_core", "recipe", "Brier", "coefficient", "Wilson"):
            assert banned not in text, (name, banned)


def test_index_cards_flags_and_record(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "index.html").read_text()
    assert "Injury reports aren't final for 1 game yet" in html and "Report pending" in html
    assert "TB QB: J.Daniels" in html and "Pick DAL −485" in html
    assert "Final 20–27" in html and "Pick BUF · W" in html
    assert "pts off market" not in html and "Largest drivers" not in html
    assert html.index("Buccaneers") < html.index("Chiefs")  # upcoming game first
    # record box: forward ledger, KC@BUF picked BUF -135 and won
    assert "Model 1-0 (100.0%) · ROI +74.1%" in html and "always favorite 1-0" in html


def test_index_before_any_graded_pick(tmp_path):
    data = make_data(tmp_path / "data", with_ledger=False)
    b.render_all(tmp_path / "public", data, now=NOW)
    html = (tmp_path / "public" / "index.html").read_text()
    assert "No graded picks yet." in html


def test_ledger_tiles_are_comparable_controls(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "grades.html").read_text()
    for label in ("Graded", "Model", "Always favorite", "Always home"):
        assert f">{label}<" in html
    assert html.count("100.0% · ROI +74.1%") == 3  # BUF was model pick, favorite and home
    assert "2026 week 5" in html and "BUF −135" in html and "ledger_report.txt" in html
    assert "native forward" in (out / "ledger_report.txt").read_text()


def test_control_records_share_rows_and_push_ties():
    df = pd.DataFrame({"home won": [1., 0., .5, 1.], "model_wp": [.6, .6, .4, .7],
                       "home_moneyline": [-150, 120, -120, np.nan], "away_moneyline": [130, -140, 100, 100]})
    c = b.control_records(df)
    # last row has no home price: dropped for all three; the tie is a push everywhere
    assert {k: (v["bets"], v["wins"], v["losses"], v["pushes"]) for k, v in c.items()} == {
        "model": (3, 1, 1, 1), "favorite": (3, 2, 0, 1), "home": (3, 1, 1, 1)}
    assert np.isclose(c["model"]["units"], 100 / 150 - 1) and np.isclose(c["home"]["units"], 100 / 150 - 1)
    # a pick'em (no favorite) is dropped for every control, so all three stay on the same rows
    even = df.assign(home_moneyline=[-150, 120, -110, -110], away_moneyline=[130, -140, -110, -110])
    assert {v["bets"] for v in b.control_records(even).values()} == {2}
    assert b.control_records(df.iloc[:0]) is None


def test_market_sides_devig_and_bands():
    df = pd.DataFrame({"home won": [1., 0., .5], "home_moneyline": [-150, -150, -110], "away_moneyline": [130, 130, -110]})
    s = b.market_sides(df)
    assert len(s) == 4  # the tie is excluded, two sides per decided game
    home = s[s.side == "home"]
    q = (150 / 250) / (150 / 250 + 100 / 230)
    assert np.allclose(home.q, q) and list(home.won) == [1., 0.] and set(home.band) == {"−174 to −130"}
    assert np.allclose(s[s.side == "home"].q.to_numpy() + s[s.side == "away"].q.to_numpy(), 1.)


def test_calibration_page_grades_the_market_and_model_confidence(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "market-calibration.html").read_text()
    assert "Favorites won" in html and "Home teams won" in html and "Moneyline" in html
    assert "Model confidence" in html and "Locked picks." in html and "Past games" in html
    assert "<svg" not in html


def test_empty_site_renders(tmp_path):
    out = tmp_path / "public"
    files = b.render_all(out, tmp_path / "nothing", now=NOW)
    assert "index.html" in files and "board.html" not in files
    assert "No model run has been published yet" in (out / "index.html").read_text()
    assert "No picks locked yet" in (out / "grades.html").read_text()


def test_snapshot_copies_page_inputs(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "run_manifest.json").write_text(json.dumps({"revision": "r", "season": 2026, "week": 5,
                                                       "source_audit": [{"source": "schedule"}]}))
    pd.DataFrame({"game_id": ["g"], "home": ["H"], "away": ["A"], "model_wp": [.6], "d__x": [1.],
                  "home__avail__qb_delta": [.1]}).to_csv(run / "week5_board.csv", index=False)
    pd.DataFrame({"a": [1]}).to_csv(run / "calibration_bands.csv", index=False)
    pd.DataFrame().to_csv(run / "market_blend_diagnostic.csv", index=False)  # empty: must not be copied
    (run / "week5_board.html").write_text("<html></html>")
    latest, proj = tmp_path / "latest", tmp_path / "proj"
    latest.mkdir()
    (latest / "stale.csv").write_text("x\n1\n")
    assert b.snapshot(run, latest, proj) == (2026, 5)
    names = {p.name for p in latest.iterdir()}
    assert {"board.csv", "board.html", "calibration_bands.csv", "manifest.json"} <= names and "stale.csv" not in names
    assert "market_blend.csv" not in names
    board = pd.read_csv(latest / "board.csv")
    assert "d__x" not in board.columns and "home__avail__qb_delta" in board.columns
    assert (proj / "2026_week05.csv").exists()
    assert json.loads((latest / "manifest.json").read_text())["availability_audit"] == []


def test_rebuilt_history_is_graded_labelled_and_secondary(tmp_path):
    out, _ = render(tmp_path)
    retro = pd.read_csv(tmp_path / "data" / "latest" / "retro_ledger.csv")
    r = b.control_records(retro)["model"]
    grades = (out / "grades.html").read_text()
    assert "Rebuilt history" in grades and "Hindsight, not a track record:" in grades
    assert grades.index("Always home") < grades.index("Rebuilt history")  # forward record leads
    assert f"{b.wl_text(r)}" in grades and f"ROI {b.roi_short(r['roi'])}" in grades
    assert np.isclose(retro.units.sum(), m.roi_summary(m.flat_bets(retro))["units"])
    assert "Rebuilt history" not in (out / "index.html").read_text()


def test_factor_labels_are_plain():
    assert b.factor_label("site") == "Home field"
    assert b.factor_label(m.MARGIN_FEATURE) == "Point margin"
    assert b.factor_label("d__avail__qb_delta") == "Quarterback"
    assert b.factor_label("d__avail__OL_out_cs") == "Offensive line availability"
    assert b.factor_label("d__for__rates_core__first_down_rate") == m.feature_label("d__for__rates_core__first_down_rate")


def test_injury_report_notes_on_the_card(tmp_path):
    out, _ = render(tmp_path)
    idx = (out / "index.html").read_text()
    assert "Injury report" in idx and "Baker Mayfield" in idx
    assert "not on a week-5 report yet" in idx and "Week 5 report not out yet" in idx


def test_team_logos_from_espn_with_code_fallback(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "index.html").read_text()
    for code in ("tb", "dal", "kc", "buf"):
        assert f"/i/teamlogos/nfl/500/{code}.png" in html and f"/i/teamlogos/nfl/500-dark/{code}.png" in html
    assert "<span>TB</span>" in html  # the code stays under the logo if it fails to load
    # nflverse codes that ESPN spells differently
    assert "/nfl/500/lar.png" in b.logo_html("LA") and "/nfl/500/wsh.png" in b.logo_html("WAS")
    assert b.logo_html("XYZ") == "" and b.logo_html(None) == ""
    assert "teamlogos" not in (out / "grades.html").read_text()


def test_card_shows_price_band_for_market_and_model(tmp_path):
    out, _ = render(tmp_path)
    idx = (out / "index.html").read_text()
    # TB@DAL: pick DAL -485; no held-out or forward side was priced that short
    assert "At this price · DAL −485 is in the ≤ −250 range" in idx and "no games at this price yet" in idx
    # KC@BUF: pick BUF -135. Market: 300 held-out sides at -150 plus the graded forward BUF -135 side.
    # Model: held-out picks in the band plus the forward pick (BUF won).
    assert "At this price · BUF −135 is in the −174 to −130 range" in idx and "301 teams" in idx
    assert "Same games for both: 2024" in idx and "plus 1 locked pick this season" in idx


def test_band_windows_use_the_same_games_and_add_forward_picks():
    retro = pd.DataFrame({"season": [2022, 2024, 2024, 2024], "home won": [1., 1., 0., .5],
                          "home_moneyline": [-150, -150, -150, -110], "away_moneyline": [130, 130, 130, -110],
                          "model_wp": [.6, .6, .6, .5]})
    held = retro[retro.season == 2024].assign(market_wp=.5)
    latest = {"retro_ledger": retro, "roi_bands": m.roi_table(held),
              "roi_by_season": m.roi_table(held, by="season")}
    fwd = pd.DataFrame({"season": [2026], "home won": [1.], "home_moneyline": [-140.], "away_moneyline": [120.],
                        "model_wp": [.62]})
    mkt, mdl, years, n = b.band_windows(latest, fwd)
    assert years == [2024] and n == 1
    # 2022 is outside the held-out window; the tie is excluded; the forward game is added
    assert mkt["−174 to −130"][0] == 3 and np.isclose(mkt["−174 to −130"][1], 2 / 3)
    assert (mdl["−174 to −130"]["wins"], mdl["−174 to −130"]["losses"], mdl["−174 to −130"]["bets"]) == (2, 1, 3)
    html = b.price_band_html("BUF", -135, .55, mkt, mdl, years, n)
    assert "−174 to −130 range" in html and "3 teams · small sample" in html and "2-1" in html
    assert "won 66.7%" in html and "55.0%" in html and "3 picks · small sample" in html
    mkt0, mdl0, _, n0 = b.band_windows(latest, None)
    assert n0 == 0 and mkt0["−174 to −130"][0] == 2 and mdl0["−174 to −130"]["bets"] == 2


def test_price_band_flags_small_samples_only():
    big = {"−174 to −130": (231, .628, .576)}
    mdl = {"−174 to −130": {"wins": 103, "losses": 53, "bets": 156, "qsum": .579 * 156}}
    html = b.price_band_html("CHI", -148, .572, big, mdl, [2023, 2024, 2025], 0)
    assert "small sample" not in html and "won 62.8%" in html and "vs 57.6% implied · 231 teams" in html
    assert "won 66.0%" in html and "This game" in html and "2023–2025" in html


def test_card_shows_model_and_market_spread(tmp_path):
    out, _ = render(tmp_path)
    idx = (out / "index.html").read_text()
    # TB@DAL: board has no model_spread column (published before v1.12.1), so it is derived from
    # model_wp .60 -> DAL by 12.37 * Phi^-1(.6) = 3.13; the market line 9.5 favors DAL too.
    assert "<span>Model DAL −3.1</span> · <span>Market DAL −9.5</span>" in idx
    assert "<td>Model spread</td><td class=n>+3.1</td><td class=n>−3.1</td>" in idx
    assert "<td>Market spread</td><td class=n>+9.5</td><td class=n>−9.5</td>" in idx


def test_spread_text_sides_pickem_and_missing():
    assert b.spread_text(4.58, True) == "−4.6" and b.spread_text(4.58, False) == "+4.6"
    assert b.spread_text(-2.5, True) == "+2.5" and b.spread_text(.04, True) == "PK"
    assert b.spread_text(float("nan"), True) == "—"
    assert b.favorite_spread_text(-3.2, "GB", "CHI") == "CHI −3.2"
    assert b.favorite_spread_text(0., "GB", "CHI") == "PK" and b.favorite_spread_text(None, "GB", "CHI") == "—"
    # A board that carries model_spread uses it; an older board falls back to model_wp.
    assert b.model_spread({"model_spread": 7.25, "model_wp": .5}) == 7.25
    assert np.isclose(b.model_spread({"model_wp": .5}), 0.)


def test_snapshot_keeps_model_spread():
    assert "model_spread" in b.BOARD_COLS
