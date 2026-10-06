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
         "away_qb_expected": "J.Daniels", "away_qb_usual": "B.Mayfield", "home_qb_expected": "D.Prescott",
         "home_qb_usual": "D.Prescott", "away_injury_report": "none", "home_injury_report": "none",
         "home__avail__qb_delta": .1, "away__avail__qb_delta": -.5, "home__avail__OL_out_cs": .1, "away__avail__OL_out_cs": 0.},
        {"game_id": "2026_05_KC_BUF", "season": 2026, "week": 5, "away": "KC", "home": "BUF",
         "gameday": "2026-10-04", "gametime": "16:25", "site": 1., "result": 7., "away_score": 20, "home_score": 27,
         "ready": True, "spread_line": 2.5, "market_wp": .58, "model_wp": .55, "homefield_wp": .54,
         "away_injury_report": "final", "home_injury_report": "final"}])
    board.to_csv(latest / "board.csv", index=False)
    pd.DataFrame([{"game_id": "2026_05_TB_DAL", "game": "TB@DAL", "feature": "site",
                   "home-minus-away input": 1, "log-odds contribution": .2, "direction": "home"}]).to_csv(latest / "contributions.csv", index=False)
    hist = pd.DataFrame({"season": 2024, "week": 1, "home won": (rng.random(300) < .55).astype(float),
                         "model_wp": rng.uniform(.2, .8, 300), "market_wp": rng.uniform(.2, .8, 300),
                         "homefield_wp": .55})
    m.calibration_bands(hist).to_csv(latest / "calibration_bands.csv", index=False)
    m.band_records(hist).to_csv(latest / "band_records.csv", index=False)
    old = m.BOOTSTRAP_REPS
    m.BOOTSTRAP_REPS = 50
    try:
        m.scorecard(hist).to_csv(latest / "outer_scorecard.csv", index=False)
        pd.concat([m.scorecard(hist).assign(season=2024)]).to_csv(latest / "outer_by_season.csv", index=False)
        m.scorecard(hist).to_csv(latest / "season_scorecard.csv", index=False)
    finally:
        m.BOOTSTRAP_REPS = old
    pd.DataFrame([{"family": "rates_core_avail_cs", "half_life": 8., "ridge": .1, "log loss": .638, "games": 1355, "selected": True}]).to_csv(latest / "recipe_selection.csv", index=False)
    pd.DataFrame([{"feature": "site", "label": "Home field", "coefficient per scaled unit": .2,
                   "training scale": 1., "training missing fraction": 0.}]).to_csv(latest / "weights.csv", index=False)
    pd.DataFrame().to_csv(latest / "market_blend.csv", index=False)
    (latest / "manifest.json").write_text(json.dumps({
        "revision": m.REVISION, "season": 2026, "week": 5, "generated_utc": "2026-10-07T14:00:00+00:00",
        "recipe": {"family": "rates_core_avail_cs", "half_life": 8., "ridge": .1},
        "market_blend_verdict": "Composite weight -0.1: no reliable evidence.", "limitations": ["a limitation"],
        "availability_audit": [{"source": "availability_roster_membership", "team_weeks": 10, "off_roster_snap_share": .066}]}))
    (latest / "board.html").write_text("<html>board</html>")
    if with_ledger:
        recs = [{"experiment": "e", "revision": m.REVISION, "game_id": "2026_05_KC_BUF", "season": 2026, "week": 5,
                 "home": "BUF", "away": "KC", "generated_utc": "2026-10-03T12:00:00+00:00",
                 "kickoff_utc": "2026-10-04T20:25:00+00:00", "model_wp": .55, "market_wp": .58,
                 "homefield_wp": .54, "spread_line": 2.5, "injury_report": {"home": "final", "away": "final"}}]
        res = pd.DataFrame({"game_id": ["2026_05_KC_BUF"], "away_score": [20], "home_score": [27], "result": [7]})
        g.write_outputs(g.grade(recs, res), root)
    return root


def render(tmp_path, **kw):
    data = make_data(tmp_path / "data", **kw)
    out = tmp_path / "public"
    files = b.render_all(out, data, now=NOW)
    return out, files


def test_all_pages_render_with_nav_and_no_nan(tmp_path):
    out, files = render(tmp_path)
    for name in ("index.html", "grades.html", "market-calibration.html", "model.html", "board.html", "ledger_report.txt", ".nojekyll"):
        assert name in files
    for name, _ in b.PAGES[:4]:
        html = (out / name).read_text()
        assert html.startswith("<!doctype html>") and "aria-current=\"page\"" in html
        assert all(f"href='{h}'" in html for h, _ in b.PAGES)
        text = re.sub(r"<[^>]+>", " ", html)
        assert not re.search(r"\bnan\b|\bNaN\b|\bNone\b", text), name


def test_index_flags_pending_reports_qb_change_and_market_gap(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "index.html").read_text()
    assert "Injury reports not final for 1 upcoming game." in html
    assert "Report pending" in html and "TB QB: J.Daniels" in html and "18 pts off market" in html
    assert "Model hit" in html and "Final 20–27" in html
    # upcoming game first
    assert html.index("Buccaneers") < html.index("Chiefs")


def test_ledger_tiles_match_report_numbers(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "grades.html").read_text()
    sm = g.summary(b.load_ledger(tmp_path / "data"))
    assert sm["scored"] == 1 and f"{sm['ll_gain']:+.3f}" in html and "1-0" in html
    assert "native forward" in (out / "ledger_report.txt").read_text()


def test_calibration_page_keeps_bases_separate(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "market-calibration.html").read_text()
    assert "Forward ledger" in html and "reconstructed (300 games)" in html
    assert html.count("<svg") == 2 and "no reliable evidence" in html


def test_empty_site_renders(tmp_path):
    out = tmp_path / "public"
    files = b.render_all(out, tmp_path / "nothing", now=NOW)
    assert "index.html" in files and "board.html" not in files
    assert "No model run has been published yet" in (out / "index.html").read_text()
    assert "No snapshots yet" in (out / "grades.html").read_text()


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
