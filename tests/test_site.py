"""Page rendering from a synthetic data/ folder (no network, no model run)."""
import datetime as dt
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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
         "model_wp_lo": .52, "model_wp_hi": .67, "offset_se": .19,
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
                         market_ml_wp=m.market_ml_wp(retro),
                         home_score=np.where(roi_hist['home won'] == 1,20,17),
                         away_score=np.where(roi_hist['home won'] == 1,17,20))
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
# Public downloads: the board and recorded picks. Replayed ledgers and median-map rules stay in data/latest.
SPREAD_EXPORTS = {"fixed_band_board.csv"}
RESEARCH_EXPORTS = {"fixed_band_ledger.csv", "fixed_band_summary.csv", "fixed_band_rules.json"}

def test_all_published_timestamps_use_pacific_and_dst(tmp_path):
    # NFL schedule input is Eastern clock time. Presentation must be Pacific.
    october_game = {"gameday": "2026-10-18", "gametime": "20:15"}
    january_game = {"gameday": "2027-01-10", "gametime": "20:15"}
    assert b.kickoff_text(october_game) == "Sun 5:15 PM PDT"
    assert b.kickoff_text(january_game) == "Sun 5:15 PM PST"

    out, _ = render(tmp_path)
    index = (out / "index.html").read_text()
    grades = (out / "grades.html").read_text()
    assert "Thu 5:15 PM PDT" in index  # upcoming game
    assert "Moneyline locked" not in index
    for name in PUBLIC:
        html = (out / name).read_text()
        assert "2026-10-07 08:00 PDT" in html  # build timestamp
        assert not re.search(r"\b(?:EST|EDT|ET)\b", visible_text(html))



def visible_text(html):
    html = re.sub(r"<style>.*?</style>|<script>.*?</script>", "", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", html)


def test_three_public_pages_with_nav_and_no_nan(tmp_path):
    out, files = render(tmp_path)
    assert set(PUBLIC) | SPREAD_EXPORTS | {"ats_2026_results.csv", ".nojekyll"} == set(files)
    assert "model.html" not in files and "board.html" not in files
    for name in PUBLIC:
        html = (out / name).read_text()
        assert html.startswith("<!doctype html>") and "aria-current=\"page\"" in html
        assert all(f"href='{h}'" in html for h, _ in b.PAGES) and "model.html" not in html
        text = visible_text(html)
        assert not re.search(r"\bnan\b|\bNaN\b|\bNone\b", text), name


def test_retired_research_artifacts_are_removed_from_public_output(tmp_path):
    data=make_data(tmp_path/'data');out=tmp_path/'public';out.mkdir()
    retired=('ledger_report.txt','model.html','board.html',*RESEARCH_EXPORTS,'retro_ledger.csv','old_moneyline.csv')
    for name in retired:(out/name).write_text('OLD-RESEARCH')
    (out/'assets').mkdir()
    (out/'assets'/'reference.csv').write_text('asset\nretained\n')
    (out/'favicon.svg').write_text('<svg/>')
    b.render_all(out,data,now=NOW)
    assert all(not (out/name).exists() for name in retired)
    assert (data/'ledger_report.txt').exists()
    assert all((data/'latest'/name).exists() for name in RESEARCH_EXPORTS)
    assert (out/'assets'/'reference.csv').read_text() == 'asset\nretained\n'
    assert (out/'favicon.svg').read_text() == '<svg/>'
    html=(out/'index.html').read_text()
    assert 'ledger_report.txt' not in html and "id='main-content'" in html and "aria-label='Main navigation'" in html


@pytest.mark.parametrize('pages_only',[False,True])
def test_full_build_report_includes_its_new_archives(tmp_path,monkeypatch,pages_only):
    data=tmp_path/'data';data.mkdir();latest=data/'latest';latest.mkdir()
    monkeypatch.setattr(b,'DATA',data);monkeypatch.setattr(b,'LATEST',latest)
    monkeypatch.setattr(b,'run_model',lambda:tmp_path/'run')
    monkeypatch.setattr(b,'snapshot',lambda _: (2026,6))
    monkeypatch.setattr(b.kalshi,'safe_record',lambda *_:None)
    monkeypatch.setattr(b.matchup,'safe_record',lambda *_:None)
    monkeypatch.setattr(b.totals,'safe_record',lambda *_:None)
    monkeypatch.setattr(b.grade_ledger,'main',lambda *_:None)
    monkeypatch.setattr(b.version_report,'run',lambda *_:None)
    def render(_):
        (data/'ledger_report.txt').write_text('before capture')
        return []
    def capture(_):
        (data/'capture-marker').write_text('new archive')
        return 1
    monkeypatch.setattr(b,'render_all',render)
    monkeypatch.setattr(b.ats_forward_shadow,'record',capture)
    monkeypatch.setattr(b,'published_report',lambda path:(path/'capture-marker').read_text())
    assert b.main(['--pages-only'] if pages_only else [])==0
    assert (data/'ledger_report.txt').read_text()==('before capture' if pages_only else 'new archive')
    assert (data/'capture-marker').exists()!=pages_only


def test_public_pages_carry_no_analyst_units_or_model_internals(tmp_path):
    out, _ = render(tmp_path)
    for name in PUBLIC:
        text = visible_text((out / name).read_text())
        for banned in ("log loss", "Log loss", "no-vig q", "Excess", "excess pp", "Mkt null",
                       "rates_core", "recipe", "Brier", "coefficient", "Wilson", "research", "reconstructed",
                       "retrospective", "hindsight", "fitted weights", "MAE", "native", "favorite-confidence"):
            assert banned not in text, (name, banned)


def test_index_cards_flags_and_record(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "index.html").read_text()
    assert "Injury reports aren't final for 1 game yet" in html and "Report pending" in html
    assert "TB QB: J.Daniels" in html and "Market DAL −9.5" in html
    assert "Final 20–27" in html and "Moneyline result" not in html
    assert "pts off market" not in html and "Largest drivers" not in html
    assert html.index("Buccaneers") < html.index("Chiefs")  # upcoming game first
    assert "View ATS results" in html and "model win probability" not in html


def test_pooled_2026_v118_picks_no_double_count(tmp_path):
    data = make_data(tmp_path / "data")
    path = data / "latest" / "retro_ledger.csv"
    retro = pd.read_csv(path)
    prior = retro.iloc[:8].copy()
    prior["season"] = 2026
    prior["week"] = [1, 2, 3, 4, 5, 5, 3, 2]
    prior["game_id"] = ["prior_1", "prior_2", "prior_3", "prior_4",
                        "2026_05_KC_BUF", "2026_05_PENDING", "ignored_backtest", "unpriced"]
    prior["basis"] = ["current season walk-forward"] * 6 + ["backtest", "current season walk-forward"]
    prior["model_wp"] = .7
    prior["home won"] = [1., 0., .5, 1., 0., 1., 1., 1.]
    prior["home_moneyline"], prior["away_moneyline"] = -150., 130.
    prior["bet_result"] = ["W", "L", "P", "W", "L", "W", "W", "W"]
    prior["units"] = [2/3, -1., 0., 2/3, -1., 2/3, 2/3, float("nan")]
    pd.concat([retro, prior], ignore_index=True).to_csv(path, index=False)

    ledger_path = data / "forward_ledger.csv"
    ledger = pd.read_csv(ledger_path)
    pending = ledger.iloc[0].copy()
    pending["game_id"] = "2026_05_PENDING"
    pending["status"] = "pending"
    pending["bet_result"], pending["units"], pending["home won"] = "", float("nan"), float("nan")
    pd.concat([ledger, pending.to_frame().T], ignore_index=True).to_csv(ledger_path, index=False)

    latest = b.load_latest(data / "latest")
    saved = b.load_ledger(data)
    rows, n_replay, n_native, n_pending = b.pooled_2026_v118_rows(latest, saved)
    assert (n_replay, n_native, n_pending) == (4, 1, 1)
    assert len(rows) == len(set(rows.game_id)) == 5
    assert rows.loc[rows.game_id == "2026_05_KC_BUF", "_basis"].item() == "native"
    assert "2026_05_PENDING" not in set(rows.game_id)

    out = tmp_path / "public"
    b.render_all(out, data, now=NOW)
    page = (out / "grades.html").read_text()
    # Legacy moneyline research helpers still work, but are not published.
    research = b.pooled_2026_v118_header(latest, saved)
    assert "Season moneyline: 3-1-1 · +1.07u · ROI +21.5%" in research
    assert "4 historical replay · 1 recorded · 1 pending" in research
    assert "Moneyline" not in page and "Season moneyline:" not in page
    assert "ATS results" in page and "replay" not in page.lower()
    if (out / 'ats_2026_results.csv').exists():
        exported = pd.read_csv(out / 'ats_2026_results.csv')
        assert not exported.game_id.duplicated().any()

    # A later revision cannot silently inherit v1.18's pooled headline.
    latest["manifest"]["revision"] = "boxscore-composite-v1.19"
    assert b.pooled_2026_v118_rows(latest, saved) is None
    assert b.pooled_2026_v118_header(latest, saved) == ""


def test_index_before_any_graded_pick(tmp_path):
    data = make_data(tmp_path / "data", with_ledger=False)
    b.render_all(tmp_path / "public", data, now=NOW)
    html = (tmp_path / "public" / "index.html").read_text()
    assert "View ATS results" in html and "Recorded moneyline results" not in html


def test_results_page_keeps_unavailable_games_without_research_details(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "grades.html").read_text()
    assert 'ATS results' in html and 'Game-by-game ATS results' in html
    assert 'Unavailable' in html
    for research in ('Historical replay', 'Replayed', 'Per-season results', 'ledger_report.txt', 'BUF −135'):
        assert research not in html
    assert not (out / "ledger_report.txt").exists()
    assert "native forward" in (tmp_path / "data/ledger_report.txt").read_text()


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
    assert "ATS performance" in html and "How picks work" in html and "52.4%" in html
    assert "Moneyline" not in html and "Model confidence" not in html and "Historical replay" not in html


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
    proj.mkdir()
    pd.DataFrame({"game_id": ["old"], "model_wp": [.99]}).to_csv(proj / "2026_week04.csv", index=False)
    pd.DataFrame({"game_id": ["prior"], "model_wp": [.61]}).to_csv(run / "week4_board.csv", index=False)
    latest.mkdir()
    (latest / "stale.csv").write_text("x\n1\n")
    assert b.snapshot(run, latest, proj) == (2026, 5)
    names = {p.name for p in latest.iterdir()}
    assert {"board.csv", "board.html", "calibration_bands.csv", "manifest.json"} <= names and "stale.csv" not in names
    assert "market_blend.csv" not in names
    board = pd.read_csv(latest / "board.csv")
    assert "d__x" not in board.columns and "home__avail__qb_delta" in board.columns
    assert (proj / "2026_week05.csv").exists()
    assert pd.read_csv(proj / "2026_week04.csv").model_wp.iloc[0] == .61
    assert pd.read_csv(proj / "2026_week04.csv").game_id.iloc[0] == "prior"
    assert json.loads((latest / "manifest.json").read_text())["availability_audit"] == []


def test_rebuilt_history_stays_off_public_pages(tmp_path):
    out, _ = render(tmp_path)
    for page in PUBLIC:
        html = (out / page).read_text()
        assert "Historical replay" not in html and "Rebuilt history" not in html
        assert "Moneyline pick" not in html and "ML result" not in html


def test_factor_labels_are_plain():
    assert b.factor_label("site") == "Home field"
    assert b.factor_label(m.MARGIN_FEATURE) == "Point margin"
    assert b.factor_label("d__avail__qb_delta") == "Quarterback"
    assert b.factor_label("d__avail__OL_out_cs") == "Offensive line availability"
    assert b.factor_label("d__for__rates_core__first_down_rate") == "Sustaining drives"
    assert b.factor_label("d__allowed__rates_core__interception_pct") == "Interceptions forced"
    assert b.factor_label("pass_product") == "Passing matchup balance"


def test_passing_context_names_and_direction_are_independent():
    label, note = b.factor_description("pass_1sd_pn", -1.62, "SF", "SEA")
    assert label == "SF passing vs SEA defense"
    assert note == "Strong attack, strong defense"
    cells = "".join(b.factor_cells({"feature": "pass_1sd_pn", "home-minus-away input": -1.62,
                                  "log-odds contribution": 1.7}, "SF", "SEA", 1.7))
    assert "Toward SEA" in cells and "aria-label='Toward SEA'" in cells
    assert "SF passing vs SEA defense" in cells and "width:50.0%" in cells
    for suffix, words in b.PASS_CONTEXT_LABELS.items():
        label, note = b.factor_description("pass_1sd_"+suffix, .2, "SF", "SEA")
        assert label == "SEA passing vs SF defense" and note == words


def test_factor_cells_escape_names_and_handle_zero_or_missing_impact():
    c = {"feature": "pass_1sd_pn", "home-minus-away input": -1., "log-odds contribution": -.2}
    html = "".join(b.factor_cells(c, "SF<script>", "SEA", 1.))
    assert "<script>" not in html and "SF&lt;script&gt;" in html
    c["log-odds contribution"] = 0.
    assert "Neutral" in "".join(b.factor_cells(c, "SF", "SEA", 1.))
    c["log-odds contribution"] = np.nan
    assert b.factor_cells(c, "SF", "SEA", 1.) is None


def test_biggest_factors_use_readable_game_descriptions(tmp_path):
    data = tmp_path / "data"
    make_data(data)
    pd.DataFrame([{"game_id": "2026_05_TB_DAL", "feature": "pass_1sd_pn",
                   "home-minus-away input": -1.6, "log-odds contribution": 1.7}]).to_csv(
                       data / "latest" / "contributions.csv", index=False)
    out = tmp_path / "public"
    b.render_all(out, data=data, now=NOW)
    page = (out / "index.html").read_text()
    assert "TB passing vs DAL defense" not in page and "Model impact" not in page
    assert "1 SD context" not in page and "Pass matchup product" not in page


def test_injury_report_notes_on_the_card(tmp_path):
    out, _ = render(tmp_path)
    idx = (out / "index.html").read_text()
    assert "Injury report" in idx and "Baker Mayfield" in idx
    assert "not on a week-5 report yet" in idx and "Week 5 injury report is pending" in idx


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


def test_cards_keep_game_prices_without_price_cohort_research(tmp_path):
    out, _ = render(tmp_path)
    idx = (out / "index.html").read_text()
    assert 'DAL −485' not in idx and 'BUF −135' not in idx
    assert 'Market DAL −9.5' in idx and 'ATS pick' in idx
    assert 'At this price' not in idx and 'Same games for both' not in idx
    assert 'Model documentation' not in idx


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


def test_card_shows_fixed_band_as_model_spread(tmp_path, monkeypatch):
    monkeypatch.setattr(b.fixed_bands, 'fit', lambda history, year:
                        dict(cuts=[3, 7, 10], magnitudes=[4, 5, 7, 13]))
    out, _ = render(tmp_path)
    idx = (out / "index.html").read_text()
    assert "<span>Model DAL −5.0</span> · <span>Market DAL −9.5</span>" in idx
    assert "<td>Model spread</td><td class=n>+5.0</td><td class=n>−5.0</td>" in idx
    assert "Model DAL −3.1" not in idx
    assert "<td>Market spread</td><td class=n>+9.5</td><td class=n>−9.5</td>" in idx
    for page in ['grades.html', 'market-calibration.html']:
        text = (out / page).read_text()
        assert 'Per-season results' not in text and 'Historical replay' not in text
        assert '−110' in text


def test_missing_training_never_falls_back_to_old_spread(tmp_path):
    out, _ = render(tmp_path)
    idx = (out / 'index.html').read_text()
    assert '<span>Model —</span>' in idx
    assert 'Model DAL −3.1' not in idx


def test_ats_comparison_uses_common_selected_games():
    # Home win, away win, push; omit a model skip, market pick'em and pending game.
    d = pd.DataFrame({'fixed_band_spread': [7., -7., 7., 3., 3., 7.],
                      'spread_line': [3., -3., 3., 3., 0., 3.],
                      'result': [7., -7., 3., 10., 7., np.nan],
                      'fixed_band_ats_result': ['W', 'W', 'P', 'S', 'W', '']})
    html = b.ats_comparison_tiles(d)
    assert 'Compared games' in html and '>3<' in html
    assert html.count('2–0–1') == 2  # model and market favorite
    assert '1–1–1' in html  # home side
    assert '100.0% covered · +1.82u · ROI +60.6%' in html
    assert '50.0% covered · -0.09u · ROI −3.0%' in html
    assert 'pick’em' in html and 'Model skips' in html
    empty = b.ats_comparison_tiles(d.iloc[3:4])
    assert empty.count('No compared games yet') == 3
    assert 'nan' not in empty


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


def test_market_sides_margin_is_from_each_sides_view():
    df = pd.DataFrame({"home won": [1., 0.], "home_moneyline": [-150, -150], "away_moneyline": [130, 130],
                       "result": [7., -3.], "spread_line": [3., 3.]})
    s = b.market_sides(df)
    assert list(s[s.side == "home"].margin) == [7., -3.] and list(s[s.side == "away"].margin) == [-7., 3.]
    assert list(s[s.side == "home"].spread) == [3., 3.] and list(s[s.side == "away"].spread) == [-3., -3.]
    no_scores = b.market_sides(df.drop(columns=["result", "spread_line"]))
    assert no_scores.margin.isna().all()  # older inputs without scores still render


def test_calibration_page_shows_avg_margin(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "market-calibration.html").read_text()
    assert 'ATS performance' in html
    assert 'Avg margin' not in html and 'Model confidence' not in html


def test_model_confidence_rows_carry_avg_margin():
    hist = pd.DataFrame({"season": 2024, "week": 1, "home won": [1., 0., 1., 0.], "model_wp": [.7, .7, .3, .3],
                         "market_wp": [.6, .6, .6, .6], "result": [10., -4., 3., -7.], "spread_line": [3., 3., -2., -2.]})
    recs = m.band_records(hist)
    tot = recs[(recs.source == "model") & (recs.band == "All picks")].iloc[0]
    # picks: home (+10, -4), away (-3, +7); spreads from the pick's view: +3, +3, +2, +2
    assert np.isclose(tot["avg pick margin"], (10 - 4 - 3 + 7) / 4) and np.isclose(tot["avg pick spread"], 2.5)
    html = b.records_table(recs)
    assert "<th class=n>Avg margin</th>" in html and "+2.5" in html
    old = recs.drop(columns=["avg pick margin", "avg pick spread"])  # a band_records.csv written before v1.12.4
    assert "Avg margin" not in b.records_table(old)
    assert np.isnan(m.band_records(hist.drop(columns=["result", "spread_line"]))["avg pick margin"]).all()


def test_partial_parameter_uncertainty_stays_off_customer_cards(tmp_path):
    out, _ = render(tmp_path)
    html = (out / "index.html").read_text()
    assert "Model range" not in html and "fitted weights" not in html
    source = pd.read_csv(tmp_path / 'data/latest/board.csv')
    assert source.model_wp_lo.iloc[0] == .52 and source.model_wp_hi.iloc[0] == .67


def test_research_arms_stay_off_the_site_and_in_the_ledger_report(tmp_path):
    data = make_data(tmp_path / "data")
    latest = data / "latest"
    (latest / "version_report.md").write_text("# Production restoration and all competing-model results\nARM-MARKER\n")
    (latest / "regraded_ledger_report.md").write_text("REPLAY-MARKER\n")
    for name in ("version_native.csv", "version_archived.csv", "version_historical.csv"):
        pd.DataFrame([{"study": "s", "arm": "secret_arm", "bets": 3, "wins": 2, "losses": 1, "pushes": 0,
                       "units": 1., "roi": .3, "favorite_units": 0.}]).to_csv(latest / name, index=False)
    pd.DataFrame([{"original_revision": "old", "game_id": "x", "original_model_wp": .6, "model_wp": .6,
                   "bet_result": "W", "bet_units": 1.}]).to_csv(latest / "regraded_ledger.csv", index=False)
    # a shadow v1.16 lock beside the production pick must not reach the public ledger
    recs = [{"experiment": e, "revision": rev, "game_id": "2026_05_KC_BUF", "season": 2026, "week": 5,
             "home": "BUF", "away": "KC", "generated_utc": "2026-10-03T12:00:00+00:00",
             "kickoff_utc": "2026-10-04T20:25:00+00:00", "model_wp": wp, "market_wp": .58, "homefield_wp": .54,
             "spread_line": 2.5, "home_moneyline": -135, "away_moneyline": 115,
             "injury_report": {"home": "final", "away": "final"}}
            for e, rev, wp in (("e", m.REVISION, .55), ("shadow", m.SHADOW_REVISION, .45))]
    res = pd.DataFrame({"game_id": ["2026_05_KC_BUF"], "away_score": [20], "home_score": [27], "result": [7]})
    g.write_outputs(g.grade(recs, res), data)
    out = tmp_path / "public"
    files = b.render_all(out, data, now=NOW)
    assert set(files) <= {*PUBLIC, *SPREAD_EXPORTS, "ats_2026_results.csv", ".nojekyll"}
    pages = "".join((out / p).read_text() for p in PUBLIC)
    for marker in ("secret_arm", "competing", "replayed with", "ARM-MARKER", "REPLAY-MARKER", m.SHADOW_REVISION):
        assert marker not in pages
    grades = (out / "grades.html").read_text()
    assert grades.count("@ BUF</span>") <= 1          # at most one pick: production only
    assert not (out / "ledger_report.txt").exists()
    report = (data / "ledger_report.txt").read_text()
    assert "Appendix A" in report and "ARM-MARKER" in report and "Appendix B" in report and "REPLAY-MARKER" in report
    assert f"== {m.SHADOW_REVISION}" in report and f"== {m.REVISION}" in report
    assert 'Appendix C: current production sanity checks' in report
    assert 'Appendix D: win-probability calibration theory' in report
    b.render_all(out, data, now=NOW)
    assert (data / 'ledger_report.txt').read_text() == report


def test_current_season_replay_is_pooled_and_prior_seasons_stay_internal(tmp_path, monkeypatch):
    monkeypatch.setattr(b.fixed_bands, 'fit', lambda history, year:
                        dict(cuts=[3, 7, 10], magnitudes=[4, 5, 7, 13]))
    data = make_data(tmp_path / 'data')
    path = data / 'latest' / 'retro_ledger.csv'
    retro = pd.read_csv(path)
    retro.loc[retro.index[:3], 'season'] = 2026
    retro.loc[retro.index[:3], 'gameday'] = '2026-09-10'
    retro.loc[retro.index[:3], 'gametime'] = '13:00'
    retro.to_csv(path, index=False)
    out = tmp_path / 'public'
    b.render_all(out, data, now=NOW)
    latest = b.load_latest(data / 'latest')
    assert b.spread_record(latest, 2026) is not None
    public = pd.read_csv(out / 'ats_2026_results.csv')
    assert set(public.season) == {2026}
    assert 'ats_basis' not in public.columns
    assert 'Historical replay:' in (data / 'ledger_report.txt').read_text()
    assert not public.game_id.duplicated().any()
    stats = b.season_ats.summary(public)
    record = f"{stats['wins']}–{stats['losses']}–{stats['pushes']}"
    for page in PUBLIC:
        html = (out / page).read_text()
        assert record in html
        assert 'replayed' not in html and '<th>Source</th>' not in html
        for research in ('Per-season results', '<td>2024</td>'):
            assert research not in html, (page, research)
    grades = (out / 'grades.html').read_text()
    for game in public.game_id:
        assert grades.count(f"data-game-id='{game}'") == 1
    performance = (out / 'market-calibration.html').read_text()
    assert f"Pick {stats['bets']}" in performance
    assert (data / 'latest' / 'fixed_band_summary.csv').exists()


def test_previous_spread_removed_from_public_pages_and_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(b.fixed_bands, 'fit', lambda history, year:
                        dict(cuts=[3, 7, 10], magnitudes=[4, 5, 7, 13]))
    out, _ = render(tmp_path)
    for page in PUBLIC:
        text = (out / page).read_text()
        for label in ['Previous spread', 'Previous ATS', 'Avg previous', 'Original MAE', 'Original magnitude']:
            assert label not in text
    frame = pd.read_csv(out / 'fixed_band_board.csv')
    assert 'model_spread' in frame
    assert not any(c.startswith('original_ats_') for c in frame)
    assert 'fixed_band_spread' not in frame
    assert not any((out / name).exists() for name in RESEARCH_EXPORTS)
    # Internal history remains reproducible; only the public export is simplified.
    internal = pd.read_csv(tmp_path / 'data' / 'latest' / 'fixed_band_ledger.csv')
    assert 'original_ats_result' in internal and 'fixed_band_spread' in internal


def test_ats_card_pick_disagrees_with_moneyline_and_handles_skips():
    pick, edge = b.ats_card_pick(-5., -5.5, 'LV', 'BUF')
    assert pick == 'LV +5.5' and edge == .5
    # A matching line takes the market favorite; a saved legacy skip and a pick'em still skip.
    assert b.ats_card_pick(-5., -5., 'LV', 'BUF') == ('BUF −5.0', 0.)
    assert b.ats_card_pick(5., 5., 'LV', 'BUF') == ('LV −5.0', 0.)
    assert b.ats_card_pick(-5., -5., 'LV', 'BUF', False)[0] == 'No bet · zero projected edge'
    assert b.ats_card_pick(0., 0., 'LV', 'BUF')[0] == 'No bet · zero projected edge'
    assert b.ats_card_pick(float('nan'), -5.5, 'LV', 'BUF')[0] == 'Unavailable'
    assert b.ats_card_pick(7., 3., 'LV', 'BUF') == ('LV −3.0', 4.)


def test_cards_show_separate_picks_without_research_cohorts(tmp_path,monkeypatch):
    monkeypatch.setattr(b.fixed_bands, 'fit', lambda history, year:
                        dict(cuts=[3,7,10], magnitudes=[4,5,7,13]))
    out,_=render(tmp_path)
    text=(out/'index.html').read_text()
    assert "<span class='kind'>ATS pick</span>" in text
    assert "<span class='kind'>Moneyline</span>" not in text
    assert 'point difference' in text
    assert 'Historical reference' not in text and 'At this price' not in text
    assert 'model win probability' not in text and 'Recorded moneyline results' not in text


def completed_pool_fixture():
    game = dict(game_id='2026_06_SEA_DEN', season=2026, week=6, home='DEN', away='SEA',
                gameday='2026-10-15', gametime='20:15', result=3.,
                fixed_band_spread=30., spread_line=9.5)
    pooled = dict(game, ats_basis='Historical replay', ats_status='graded',
                  home_score=17., away_score=14.,
                  fixed_band_spread=-3., spread_line=-2.5,
                  fixed_band_ats_result='L', fixed_band_ats_units=-1.)
    latest = dict(manifest={'revision':m.REVISION}, ats_locks={}, pooled_ats=pd.DataFrame([pooled]))
    return latest, game


def test_completed_card_selection_uses_trusted_pool_before_live_postgame_prices():
    latest, game = completed_pool_fixture()
    state = b.ats_card_state(latest,game,NOW+dt.timedelta(days=20))
    assert (state['status'],state['selected_team'],state['result'],state['units']) == ('graded','SEA','L',-1.)
    assert (state['model_spread'],state['spread_line'],state['handicap']) == (-3.,-2.5,-2.5)
    assert state['pick'] == 'SEA −2.5'
    assert game['spread_line'] == 9.5 and game['fixed_band_spread'] == 30.


@pytest.mark.parametrize('kind',['pending_pool','missing_pool'])
def test_missing_or_pending_pool_never_backfills_an_unsaved_completed_card(kind):
    latest, game = completed_pool_fixture()
    if kind == 'pending_pool':
        latest['pooled_ats']['ats_status'] = 'pending'
    elif kind == 'missing_pool':
        latest['pooled_ats'] = pd.DataFrame()
    state = b.ats_card_state(latest,game,NOW+dt.timedelta(days=20))
    assert state['status'] == 'unavailable' and not state['selected_side']
    assert not state['result'] and not math.isfinite(state['units'])


@pytest.mark.parametrize('stale_result',[np.nan,-10.])
def test_completed_pool_outcomes_replace_missing_or_conflicting_board_scores(stale_result):
    latest, game = completed_pool_fixture()
    game.update(result=stale_result,home_score=10.,away_score=20.)
    state = b.ats_card_state(latest,game,NOW+dt.timedelta(days=20))
    assert state['status'] == 'graded' and state['result'] == 'L'
    assert state['display_row']['result'] == 3.
    assert state['display_row']['home_score'] == 17. and state['display_row']['away_score'] == 14.
    assert game['home_score'] == 10. and game['away_score'] == 20.


def test_saved_card_takes_priority_over_conflicting_completed_pool():
    latest, game = completed_pool_fixture()
    saved = dict(fixed_band_spread=7.,market_spread=7.,selected_side='home',
                 generated_utc='2026-10-15T20:00:00Z',lock_at_utc='2026-10-15T23:15:00Z')
    latest['ats_locks'][(m.REVISION,game['game_id'])] = saved
    state = b.ats_card_state(latest,game,NOW+dt.timedelta(days=20))
    assert state['saved'] is saved
    assert (state['model_spread'],state['spread_line'],state['selected_team']) == (7.,7.,'DEN')
    assert state['status'] == 'locked' and state['result'] == 'L'


def test_public_ats_roi_uncertainty_includes_pushes_and_is_unavailable_for_one_bet():
    frame = pd.DataFrame(dict(week=[6,6,6],ats_status=['graded']*3,
                              fixed_band_ats_result=['W','L','P'],
                              spread_line=[1.,1.,1.],fixed_band_spread=[2.,2.,2.],result=[2.,0.,1.]))
    # Returns 10/11, -1, 0 have sample-mean SE sqrt(331)/33.
    expected = f'± {100*math.sqrt(331)/33:.1f} pp SE'
    assert expected in b.record_tiles(frame,'Season')
    assert expected in b.weekly_table(frame)
    assert b.ats_comparison_tiles(frame).count(expected) == 3
    assert 'SE unavailable' in b.record_tiles(frame.iloc[:1],'One pick')
    assert 'nan' not in b.weekly_table(frame.iloc[:1]).lower()


def test_pick_badge_text_contrast_in_light_and_dark_themes():
    def luminance(rgb):
        linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in np.array(rgb)/255]
        return sum(a*v for a,v in zip((.2126,.7152,.0722),linear))
    for block in [b.CSS.split('@media')[0],b.CSS.split('html[data-theme="dark"]{',1)[1].split('}',1)[0]]:
        background = tuple(int(v) for v in re.search(r'--accent:([\d,]+)',block).group(1).split(','))
        foreground = re.search(r'--accent-on:#([0-9a-fA-F]{6})',block).group(1)
        foreground = tuple(int(foreground[i:i+2],16) for i in (0,2,4))
        light,dark = sorted([luminance(background),luminance(foreground)],reverse=True)
        assert (light+.05)/(dark+.05) >= 4.5
    assert 'color:var(--accent-on)' in b.CSS.split('.g-team.picked .nm::after{',1)[1].split('}',1)[0]


def test_public_ats_keeps_all_season_sources_and_missing_locks():
    pooled = pd.DataFrame({
        'game_id': ['lock', 'legacy', 'backfill', 'replay', 'snapshot', 'early_missing', 'late_missing'],
        'ats_basis': ['60-minute lock', 'Recorded pregame', 'Backfilled recorded skip', 'Historical replay',
                      'Replayed pregame forecast', 'Awaiting ATS lock', 'Awaiting ATS lock'],
        'kickoff_utc': ['2026-10-25T17:00:00+00:00', '2026-10-18T17:00:00+00:00', '2026-10-18T17:00:00+00:00',
                        None, '2026-10-18T17:00:00+00:00', '2026-10-18T17:00:00+00:00', '2026-10-25T17:00:00+00:00']})
    kept = set(b.public_ats({'pooled_ats': pooled}).game_id)
    # Missing locks remain visible without a graded pick; no source is dropped.
    assert kept == set(pooled.game_id)
    assert b.public_ats({'pooled_ats': pd.DataFrame()}).empty and b.public_ats(None).empty


def test_units_chart_runs_in_kickoff_order_and_needs_two_picks():
    frame = pd.DataFrame({'game_id': ['b', 'a'], 'week': [6, 6], 'home': ['IND', 'NE'], 'away': ['TEN', 'NYJ'],
                          'kickoff_utc': ['2026-10-18T20:00:00+00:00', '2026-10-18T17:00:00+00:00'],
                          'fixed_band_ats_result': ['L', 'W'], 'fixed_band_ats_units': [-1., 1 / 1.1],
                          'fixed_band_ats_team': ['IND', 'NYJ'], 'fixed_band_ats_side': ['home', 'away'],
                          'spread_line': [7., 7.5]})
    html = b.units_chart(frame)
    assert html.index('NYJ @ NE') < html.index('TEN @ IND')    # earlier kickoff first
    assert 'running +0.91u' in html and 'running −0.09u' in html and '<svg' in html
    assert b.units_chart(frame.iloc[:1]) == '' and b.units_chart(pd.DataFrame()) == ''


def test_units_chart_orders_early_replay_before_later_recorded_games():
    frame = pd.DataFrame([
        dict(game_id='recorded',week=6,home='IND',away='TEN',kickoff_utc='2026-10-18T17:00:00Z',
             fixed_band_ats_result='L',fixed_band_ats_units=-1.),
        dict(game_id='a_replay',week=1,home='NE',away='NYJ',gameday='2026-09-14',
             fixed_band_ats_result='L',fixed_band_ats_units=-1.),
        dict(game_id='z_replay',week=1,home='LAC',away='ARI',gameday='2026-09-13',
             fixed_band_ats_result='W',fixed_band_ats_units=1/1.1)])
    html=b.units_chart(frame)
    assert html.index('ARI @ LAC') < html.index('NYJ @ NE') < html.index('TEN @ IND')
    assert 'running −1.09u' in html and 'Pick 3' in html
