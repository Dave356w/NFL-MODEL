import datetime as dt

import numpy as np
import pandas as pd

import grade_ledger as g


def rec(gid, wp, mkt, exp="e", rev="r1", week=5, hm=-150, am=130, sp=3.0):
    return {"experiment": exp, "revision": rev, "game_id": gid, "season": 2026, "week": week,
            "home": "H" + gid, "away": "A" + gid, "generated_utc": "2026-10-10T12:00:00+00:00",
            "kickoff_utc": "2026-10-11T17:00:00+00:00", "model_wp": wp, "market_wp": mkt,
            "homefield_wp": .55, "spread_line": sp, "home_moneyline": hm, "away_moneyline": am,
            "injury_report": {"home": "final", "away": "final"}}


RESULTS = pd.DataFrame({"game_id": ["a", "b", "c", "d"], "away_score": [10, 24, 17, np.nan],
                        "home_score": [20, 21, 17, np.nan], "result": [10, -3, 0, np.nan]})


def test_statuses_hits_and_scores():
    out = g.grade([rec("a", .7, .6), rec("b", .6, .4), rec("c", .5, .5), rec("d", .4, .45), rec("e", .6, None)], RESULTS)
    s = out.set_index("game_id")
    assert s.loc["a", "status"] == "graded" and s.loc["a", "model_hit"] == 1 and s.loc["a", "market_hit"] == 1
    assert s.loc["b", "model_hit"] == 0 and s.loc["b", "market_hit"] == 1
    assert s.loc["c", "status"] == "tie" and np.isnan(s.loc["c", "model_log_loss"])
    assert s.loc["d", "status"] == "pending" and s.loc["e", "status"] == "pending"
    assert np.isclose(s.loc["a", "model_log_loss"], -np.log(.7))
    assert np.isclose(s.loc["b", "market_brier"], .16)
    assert s.loc["a", "lead_hours"] == 29.0
    assert list(out.columns) == g.COLUMNS


def test_summary_scores_one_row_set():
    out = g.grade([rec("a", .7, .6), rec("b", .6, .4), rec("c", .5, .5), rec("d", .4, .45)], RESULTS)
    sm = g.summary(out)
    assert sm["scored"] == 2 and sm["pending"] == 1 and sm["ties"] == 1
    assert (sm["model_wins"], sm["model_losses"], sm["market_wins"], sm["market_losses"]) == (1, 1, 2, 0)
    d = (-np.log(.6) + np.log(.7)) + (-np.log(.6) + np.log(.4))
    assert np.isclose(sm["ll_gain"], d / 2)


def test_report_and_outputs(tmp_path):
    out = g.grade([rec("a", .7, .6), rec("b", .6, .4, rev="r0")], RESULTS)
    g.write_outputs(out, tmp_path, now=dt.datetime(2026, 10, 12, tzinfo=dt.timezone.utc))
    text = (tmp_path / "ledger_report.txt").read_text()
    assert "== r1:" in text and "== r0:" in text and "native forward observations only" in text
    assert pd.read_csv(tmp_path / "forward_ledger.csv").shape[0] == 2


def test_empty_ledger(tmp_path):
    out = g.grade([], RESULTS)
    assert out.empty and g.summary(out)["snapshots"] == 0
    g.write_outputs(out, tmp_path)
    assert "No snapshots" in (tmp_path / "ledger_report.txt").read_text()


def test_flat_roi_at_saved_moneyline_with_same_row_baseline():
    # a: model home (-150) wins +0.667; b: model away (+130), away won -> +1.3; c: tie -> push 0;
    # e: no saved price -> no bet; d: pending -> no units yet.
    out = g.grade([rec("a", .7, .6), rec("b", .4, .6), rec("c", .6, .6), rec("d", .6, .6),
                   rec("e", .6, .6, hm=None, am=None)], RESULTS)
    s = out.set_index("game_id")
    assert s.loc["a", "bet_team"] == "Ha" and s.loc["a", "bet_result"] == "W" and np.isclose(s.loc["a", "units"], 2 / 3)
    assert s.loc["b", "bet_team"] == "Ab" and np.isclose(s.loc["b", "units"], 1.3) and s.loc["c", "bet_result"] == "P"
    assert np.isnan(s.loc["d", "units"]) and np.isnan(s.loc["e", "units"]) and s.loc["e", "bet_team"] == "He"
    r = g.summary(out)["roi"]
    assert (r["bets"], r["wins"], r["losses"], r["pushes"]) == (3, 2, 0, 1)
    assert np.isclose(r["units"], 2 / 3 + 1.3) and np.isclose(r["roi"], (2 / 3 + 1.3) / 3)
    assert np.isclose(r["fav_units"], 2 / 3 - 1 + 0)  # market favorite = home -150 on all three
    assert r["null_roi"] < 0  # market-correct null is negative by the hold
    bands = g.roi_bands(out).set_index("group")
    assert bands.loc["All games", "bets"] == 3 and bands.loc["−174 to −130", "bets"] == 2
    assert "HEADLINE flat 1u" in g.report_text(out)


def test_model_spread_and_ats_diagnostic():
    from scipy.special import ndtr
    even = float(ndtr(3 / g.m.MARKET_SIGMA))  # model spread equals the 3-point line: no side
    # a: model +6.5 vs 3 -> home; home won by 10 -> W.  b: model -3.1 -> away; home lost by 3 -> W.
    # c: model +3.1 -> home; tie, home 3 short of the line -> L.  d: pending -> no result.
    # e: line 10, home won by 10 -> push.  f: model equals the line -> no side.  g: no line -> no side.
    res = pd.concat([RESULTS, pd.DataFrame({"game_id": ["e", "f", "g"], "away_score": [10, 10, 10],
                                            "home_score": [20, 20, 20], "result": [10, 10, 10]})])
    out = g.grade([rec("a", .7, .6), rec("b", .4, .6), rec("c", .6, .6), rec("d", .6, .6),
                   rec("e", .9, .8, sp=10.0), rec("f", even, .6), rec("g", .6, None, sp=None)], res)
    s = out.set_index("game_id")
    assert np.isclose(s.loc["a", "model_spread"], g.m.MARKET_SIGMA * 0.5244005127080407)
    assert np.isclose(s.loc["a", "spread_gap"], s.loc["a", "model_spread"] - 3)
    assert (s.loc["a", "ats_side"], s.loc["a", "ats_result"]) == ("home", "W")
    assert (s.loc["b", "ats_side"], s.loc["b", "ats_result"]) == ("away", "W")
    assert (s.loc["c", "ats_side"], s.loc["c", "ats_result"]) == ("home", "L")
    assert s.loc["d", "ats_side"] == "home" and s.loc["d", "ats_result"] == ""
    assert s.loc["e", "ats_result"] == "P"
    assert s.loc["f", "ats_side"] == "" and s.loc["f", "ats_result"] == ""
    assert s.loc["g", "ats_side"] == "" and np.isnan(s.loc["g", "spread_gap"])
    a = g.ats_summary(out)
    assert (a["wins"], a["losses"], a["pushes"]) == (2, 1, 1)
    big = g.ats_summary(out, g.ATS_GAP_POINTS)  # a (+3.5), b (-6.1), e (+5.9) qualify; c (+0.1) does not
    assert (big["wins"], big["losses"], big["pushes"]) == (2, 0, 1) and big["lo"] < big["hi"]
    text = g.report_text(out)
    assert "Diagnostic, not the goal metric" in text and "|gap| >= 3 pts  2-0-1" in text
    # The headline still grades every priced, final game at the moneyline (a, b, c push, e, f, g),
    # including g, which has no spread and so no ATS side.
    assert g.summary(out)["roi"]["bets"] == 6


def test_continuous_policy_uses_saved_revision_and_exact_favorite_tie_rule():
    from scipy.special import ndtr
    # Same saved probability/line: legacy skip, new home favorite bet.
    even = float(ndtr(3 / g.m.MARKET_SIGMA))
    near = float(ndtr((3 + 1e-7) / g.m.MARKET_SIGMA))
    away = float(ndtr(-3 / g.m.MARKET_SIGMA))
    rows = [rec('a', even, .6, exp='legacy', rev='boxscore-composite-v1.18'),
            rec('b', .7, .6, exp='legacy', rev='boxscore-composite-v1.18'),
            rec('a', even, .6, exp='new', rev='boxscore-composite-v1.19'),
            rec('b', near, .6, rev='boxscore-composite-v1.19'),
            rec('c', away, .4, rev='boxscore-composite-v1.19', sp=-3.),
            rec('d', .5, .5, rev='boxscore-composite-v1.19', sp=0.)]
    out = g.grade(rows, RESULTS).set_index(['experiment','game_id'])
    assert tuple(out.loc[('legacy','a'), ['ats_side','ats_result']]) == ('','')
    assert tuple(out.loc[('new','a'), ['ats_side','ats_result']]) == ('home','W')
    assert tuple(out.loc[('e','b'), ['ats_side','ats_result']]) == ('home','L')
    assert tuple(out.loc[('e','c'), ['ats_side','ats_result']]) == ('away','L')
    assert tuple(out.loc[('e','d'), ['ats_side','ats_result']]) == ('','S')
    text = g.report_text(out.reset_index())
    assert 'Continuous ATS policy at the original first-snapshot spread' in text
    assert 'separate from the native production T-60 ATS locks' in text
    assert 'Older revisions retain their diagnostic grading' in text
    assert 'no-vig moneylines for v1.16-v1.19' in text
    assert 'fitted spread/total forecast offset is separate from this benchmark' in text


def test_no_ats_lines_before_any_decided_game():
    out = g.grade([rec("d", .6, .6)], RESULTS)
    assert out.loc[0, "ats_result"] == "" and "Diagnostic, not the goal metric" not in g.report_text(out)


CLOSE = pd.DataFrame({"game_id": ["a", "b", "d", "f"], "away_score": [10, 24, np.nan, 13],
                      "home_score": [20, 21, np.nan, 20], "result": [10, -3, np.nan, 7],
                      "close_home_moneyline": [-200, -200, -300, np.nan], "close_away_moneyline": [170, 170, 250, np.nan]})


def test_closing_line_value_sign_and_missing_closes():
    # Lock -150/+130 (home q .5798); close -200/+170 (home q .6429).
    out = g.grade([rec("a", .7, .6), rec("b", .3, .4), rec("d", .7, .6), rec("f", .7, .6)], CLOSE).set_index("game_id")
    assert np.isclose(out.loc["a", "close_q"], .6667 / (.6667 + 100 / 270), atol=1e-4)
    assert np.isclose(out.loc["a", "clv_pp"], 6.31, atol=.01)        # home pick, price moved toward it
    assert np.isclose(out.loc["b", "clv_pp"], -6.31, atol=.01)       # away pick, price moved away from it
    assert np.isnan(out.loc["d", "close_q"]) and np.isnan(out.loc["d", "close_home_moneyline"])  # pending: no close
    assert np.isnan(out.loc["f", "clv_pp"])                          # no closing quote
    s = g.clv_summary(out.reset_index())
    assert s["n"] == 2 and np.isclose(s["mean"], 0, atol=1e-9) and s["dog_n"] == 1 and np.isclose(s["dog_mean"], -6.31, atol=.01)


def h12(gid, wp, week, season=2026, rev=None, exp=None):
    r = rec(gid, wp, .6, rev=rev or g.H12_REVISION, exp=exp or g.H12_EXPERIMENT + str(season), week=week)
    return {**r, "season": season}


def test_h1_h2_use_only_the_registered_sample():
    games = list("pqstuvwx")
    res = pd.DataFrame({"game_id": games, "away_score": [10, 10, 30, 10, 10, 10, 10, 10],
                        "home_score": [20] * 8, "result": [10, 10, -10, 10, 10, 10, 10, 10]})
    # q from the snapshot moneylines is .580: gaps .27, .22 and .28 qualify, .04 and .03 do not.
    rows = [h12("p", .85, 6), h12("q", .62, 9), h12("s", .80, 15), h12("t", .55, 18),
            h12("u", .90, 5),                                          # week 5: before the addendum
            h12("v", .90, 9, rev="boxscore-composite-v1.17"),          # another revision
            h12("w", .90, 9, exp="deadbeef:other_recipe:2026"),        # another configuration
            h12("x", .30, 3, season=2027)]                             # later seasons count
    out = g.grade(rows, res)
    assert sorted(g.h12_rows(out).game_id) == ["p", "q", "s", "t", "x"]
    s1 = g.h1_summary(out)
    assert s1["rows"] == 5 and s1["bets"] == 3 and np.isclose(s1["units"], 1 / 1.5 - 2)
    assert g.h1_verdict(s1) == "unresolved"
    assert g.h1_verdict({**s1, "bets": 0}) == "no qualifying graded rows"
    s2 = g.h2_summary(out)
    assert (s2["mid"]["n"], s2["late"]["n"], s2["late_14_17"]["n"], s2["week_18"]["n"]) == (2, 2, 1, 1)
    assert np.isclose(s2["diff"], s2["late"]["mean"] - s2["mid"]["mean"])
    assert (s2["mid"]["bets"], s2["late"]["bets"]) == (2, 2)              # secondary ROI on the same sample
    assert np.isclose(s2["late"]["roi"], (-1 + 1 / 1.5) / 2) and np.isclose(s2["late"]["fav_roi"], (-1 + 1 / 1.5) / 2)
    only_mid = g.h2_summary(g.grade(rows[:2], res))
    assert g.h2_verdict(only_mid) == "no late-season rows"
    text = g.report_text(out)
    assert "Pre-registered H1/H2" in text and "from 2026 week 6" in text and "H2 secondary, flat 1u ROI" in text
    assert "Pre-registered H1/H2" not in g.report_text(g.grade([rec("a", .7, .6)], RESULTS))


def test_h1_h2_wait_for_week_6_rows():
    out = g.grade([h12("u", .90, 5)], pd.DataFrame({"game_id": ["u"], "away_score": [10], "home_score": [20], "result": [10]}))
    s1, s2 = g.h1_summary(out), g.h2_summary(out)
    assert s1["rows"] == 0 and g.h1_verdict(s1) == "no qualifying graded rows" and g.h2_verdict(s2) == "no graded rows"
    assert "0 qualifying graded bets of 0 priced rows" in g.report_text(out)


def test_h6_grades_only_underdog_picks_in_the_registered_sample():
    res = pd.DataFrame({"game_id": list("abcdefgh"), "away_score": [24, 10, 10, 24, 24, 24, 24, np.nan],
                        "home_score": [21, 20, 20, 21, 21, 21, 21, np.nan], "result": [-3, 10, 10, -3, -3, -3, -3, np.nan]})
    pickem_market = {"home_moneyline": -110, "away_moneyline": -110}
    rows = [h12("a", .30, 7), h12("b", .45, 8),                    # the +130 underdog: one win, one loss
            h12("c", .70, 9),                                      # the -150 favorite: not H6
            h12("d", .30, 5),                                      # week 5: before the addendum
            h12("e", .30, 9, rev="boxscore-composite-v1.17"),      # another revision
            {**h12("f", .30, 9), **pickem_market},                 # market pick'em: no underdog
            h12("g", .50, 9),                                      # model pick'em: no bet
            h12("h", .30, 10)]                                     # pending
    out = g.grade(rows, res)
    s6 = g.h6_summary(out)
    assert s6["rows"] == 6 and s6["bets"] == 2 and np.isclose(s6["units"], 1.3 - 1)
    assert np.isclose(s6["fav_roi"], (-1 + 1 / 1.5) / 2)          # the -150 side of the same two games
    assert np.isclose(s6["null_roi"], (100 / 230) / (100 / 230 + 150 / 250) * 2.3 - 1)
    assert g.h6_verdict(s6) == "no verdict before 10 graded bets"
    text = g.report_text(out)
    assert "Pre-registered H1/H2/H6" in text and "H6, the model backs the market underdog" in text
    assert "H6" not in g.report_text(g.grade([rec("a", .3, .6)], RESULTS))


def test_h6_decision_rules():
    base = {"null_roi": -.03, "roi_se": .15}
    assert g.h6_verdict({**base, "bets": 9, "roi": .9}) == "no verdict before 10 graded bets"
    assert g.h6_verdict({**base, "bets": 20, "roi": .27}).startswith("supported")
    assert g.h6_verdict({**base, "bets": 20, "roi": .26}) == "unresolved"
    assert g.h6_verdict({**base, "bets": 60, "roi": -.03}).startswith("falsified")
    assert g.h6_verdict({**base, "bets": 49, "roi": -.20}) == "unresolved"


def test_integer_closing_prices_with_a_pending_game():
    res = pd.DataFrame({"game_id": ["a", "d"], "away_score": [10, np.nan], "home_score": [20, np.nan],
                        "result": [10, np.nan], "close_home_moneyline": [-200, -300], "close_away_moneyline": [170, 250]})
    out = g.grade([rec("a", .7, .6), rec("d", .7, .6)], res).set_index("game_id")
    assert np.isclose(out.loc["a", "clv_pp"], 6.31, atol=.01) and np.isnan(out.loc["d", "close_home_moneyline"])


H9_REV = "boxscore-composite-v1.18"


def test_h9_sample_is_first_production_snapshot_per_game_from_week_6():
    recs = [rec("a", .6, .6, rev=H9_REV, week=6, hm=-300, am=250, sp=3.),
            rec("a", .6, .6, rev="boxscore-composite-v1.16", week=6, hm=-300, am=250, sp=3.),   # shadow, same game
            rec("b", .6, .6, rev=H9_REV, week=5, hm=-300, am=250, sp=3.),                      # before week 6
            rec("c", .6, .6, rev=H9_REV, week=6, hm=-300, am=250, sp=None),                    # no spread: excluded
            rec("d", .6, .6, rev="r1", week=6, hm=-300, am=250, sp=3.)]                        # not production
    d = g.h9_rows(g.grade(recs, RESULTS))
    assert list(d.game_id) == ["a"] and d.revision.iloc[0] == H9_REV
    assert d.h9_dis.iloc[0] > 0          # moneyline ~73% home vs spread +3 ~60%: moneyline more bullish on home


def test_h9_production_list_names_the_current_revision():
    # Append-only: a production REVISION missing here would drop its games once production moves on.
    assert g.m.REVISION in g.H9_PRODUCTION and g.H9_PRODUCTION[0] == H9_REV


def test_h9_sample_keeps_every_listed_production_revision(monkeypatch):
    recs = [rec("a", .6, .6, rev=H9_REV, week=6, hm=-300, am=250, sp=3.),
            rec("b", .6, .6, rev="boxscore-composite-v1.19", week=7, hm=-300, am=250, sp=3.),
            rec("c", .6, .6, rev="boxscore-composite-v1.20", week=8, hm=-300, am=250, sp=3.),
            rec("d", .6, .6, rev="boxscore-composite-v1.16", week=8, hm=-300, am=250, sp=3.)]    # shadow
    graded = g.grade(recs, RESULTS)
    monkeypatch.setattr(g.m, "REVISION", "boxscore-composite-v1.20")
    monkeypatch.setattr(g, "H9_PRODUCTION", (H9_REV, "boxscore-composite-v1.19", "boxscore-composite-v1.20"))
    assert sorted(g.h9_rows(graded).game_id) == ["a", "b", "c"]
    monkeypatch.setattr(g, "H9_PRODUCTION", (H9_REV,))                    # v1.19 not listed: its games drop
    assert sorted(g.h9_rows(graded).game_id) == ["a", "c"]


def _h9_games(n, weeks, win, pending=(), ties=(), prices=(-300, -150, 130, 200)):
    """n H9 games over `weeks` weeks from week 6; win(d, rng) gives home wins for the H9 rows d. Games
    listed in `pending` get no result; games in `ties` end level."""
    rng = np.random.default_rng(0)
    hm = rng.choice(list(prices), n)
    am = np.where(hm < 0, np.abs(hm) - 20, -(hm + 20))
    sp = rng.normal(0, 5, n).round(1)
    recs = [rec(f"g{i}", .6, .6, rev=H9_REV, week=6 + i % weeks, hm=float(hm[i]), am=float(am[i]), sp=float(sp[i]))
            for i in range(n)]
    d = g.h9_rows(g.grade(recs, pd.DataFrame({"game_id": [], "away_score": [], "home_score": [], "result": []})))
    w = win(d, rng)
    res = pd.DataFrame({"game_id": d.game_id, "away_score": np.where(w, 10, 20), "home_score": np.where(w, 20, 10),
                        "result": np.where(w, 10, -10)})
    res.loc[res.game_id.isin([f"g{i}" for i in ties]), ["away_score", "home_score", "result"]] = [17, 17, 0]
    return g.grade(recs, res[~res.game_id.isin([f"g{i}" for i in pending])])


def _coin(d, rng):
    return rng.random(len(d)) < .5


def test_h9_interim_b_waits_for_ten_weeks_and_says_when_not_estimable():
    two_weeks = _h9_games(40, 2, _coin)
    s = g.h9_summary(two_weeks)
    assert s["n"] == 40 and s["weeks"] == 2 and np.isnan(s["b"]) and np.isnan(s["se"])
    assert "b needs 30 graded games over 10 weeks" in g.report_text(two_weeks)
    separated = _h9_games(40, 12, lambda d, rng: d.h_q.to_numpy() > .5)   # the favorite always wins: singular
    s = g.h9_summary(separated)
    assert s["weeks"] == 12 and np.isnan(s["b"])
    assert "b not estimable" in g.report_text(separated)


def test_h9_fit_that_never_converges_is_not_reported_as_an_estimate():
    sep = _h9_games(60, 12, lambda d, rng: d.h9_dis.to_numpy() < 0,       # separation on dis: b runs off
                    prices=(-300, -200, -150, -120, 110, 130, 170, 200, 250))
    binary = g.h9_rows(sep)[lambda x: x.status == "graded"]
    b, se = g._h9_fit(binary)                                             # Newton never settles; no exception
    assert np.isnan(b) and np.isnan(se)
    assert np.isnan(g.h9_summary(sep)["b"]) and "b not estimable" in g.report_text(sep)


def test_h9_week_gate_counts_only_weeks_with_binary_results():
    # 45 games over weeks 6-14 graded; week 15 holds three pending games and a tie: still 9 weeks.
    nine = _h9_games(49, 10, _coin, pending=(9, 19, 29), ties=(39,))
    s = g.h9_summary(nine)
    assert s["n"] == 45 and s["weeks"] == 9 and np.isnan(s["b"])
    assert "b needs 30 graded games over 10 weeks" in g.report_text(nine)
    ten = _h9_games(49, 10, _coin, pending=(9, 19, 29))                    # the week-15 game is decided
    s = g.h9_summary(ten)
    assert s["n"] == 46 and s["weeks"] == 10 and np.isfinite(s["b"]) and np.isfinite(s["se"])


def test_h9_rule_backs_the_spread_side_and_skips_small_disagreements():
    res = pd.DataFrame({"game_id": ["a", "b", "s"], "away_score": [20, 10, 10], "home_score": [10, 20, 20],
                        "result": [-10, 10, 10]})
    recs = [rec("a", .6, .6, rev=H9_REV, week=6, hm=-300, am=250, sp=3.),    # dis > 0 -> away +250, away won
            rec("b", .6, .6, rev=H9_REV, week=6, hm=-130, am=110, sp=7.),    # dis < 0 -> home -130, home won
            rec("s", .6, .6, rev=H9_REV, week=6, hm=-150, am=130, sp=2.5)]   # |dis| < T: no bet
    r = g.h9_summary(g.grade(recs, res))["rule"]
    assert r["bets"] == 2 and r["wins"] == 2 and np.isclose(r["units"], 2.5 + 100 / 130)
    assert r["null_roi"] < 0


def test_h9_decision_rules():
    assert g.h9_verdict({"n": 299, "b": -5., "se": 1.}).startswith("no verdict")
    assert g.h9_verdict({"n": 300, "b": -2.1, "se": 1.}).startswith("supported")
    assert g.h9_verdict({"n": 599, "b": .3, "se": 1.}) == "unresolved"
    assert g.h9_verdict({"n": 600, "b": 0., "se": 1.}).startswith("falsified")
    assert g.h9_rule_verdict({"bets": 99, "roi": .5, "null_roi": -.04, "roi_se": .1}).startswith("no verdict")
    assert g.h9_rule_verdict({"bets": 100, "roi": -.05, "null_roi": -.04, "roi_se": .1}).startswith("falsified")
    assert g.h9_rule_verdict({"bets": 100, "roi": .17, "null_roi": -.04, "roi_se": .1}).startswith("supported")


def test_h9_fit_recovers_a_negative_slope_and_appears_in_the_report(tmp_path):
    rng = np.random.default_rng(3)
    n = 4000
    hm = rng.choice([-300, -200, -150, -120, 110, 130, 180], n)
    am = np.where(hm < 0, np.abs(hm) - 20, -(hm + 20))
    sp = rng.normal(0, 6, n).round(1)
    recs = [rec(f"g{i}", .6, .6, rev=H9_REV, week=6 + i % 12, hm=float(hm[i]), am=float(am[i]), sp=float(sp[i]))
            for i in range(n)]
    graded = g.grade(recs, pd.DataFrame({"game_id": [], "away_score": [], "home_score": [], "result": []}))
    d = g.h9_rows(graded)
    z = np.log(d.h_q / (1 - d.h_q)) - 1.5 * d.h9_dis
    win = rng.random(len(d)) < 1 / (1 + np.exp(-z))
    res = pd.DataFrame({"game_id": d.game_id, "away_score": np.where(win, 10, 20), "home_score": np.where(win, 20, 10),
                        "result": np.where(win, 10, -10)})
    out = g.grade(recs, res)
    s = g.h9_summary(out)
    assert s["n"] == len(d) and s["b"] < 0 and abs(s["b"] + 1.5) < 3 * s["se"]
    g.write_outputs(out, tmp_path, now=dt.datetime(2027, 1, 12, tzinfo=dt.timezone.utc))
    assert "== Pre-registered H9" in (tmp_path / "ledger_report.txt").read_text()


def test_penalty_verdict_is_three_way_with_cluster_se():
    assert np.isclose(g.fp_critical(14), 2.5326, atol=1e-4) and np.isclose(g.fp_critical(86), 2.2818, atol=1e-4)
    assert g.fp_verdict(.01, .001, 199, 14).startswith("no verdict")
    assert g.fp_verdict(.006, .002, 200, 14).startswith("supported")       # lower bound .006 - 2.53*.002 > 0
    assert g.fp_verdict(-.004, .002, 200, 14).startswith("falsified")      # upper bound .0011 < .002
    assert g.fp_verdict(-.001, .002, 200, 14) == "unresolved"              # upper bound .0041 >= .002: not excluded
    assert g.fp_verdict(.0048, .002, 1300, 86).startswith("supported")     # t(85) 2.28: lower bound > 0
    assert g.fp_verdict(.0048, .002, 210, 14) == "unresolved"              # t(13) 2.53: few weeks, wider bounds
    assert g.fp_verdict(.0, float("nan"), 500, 30).startswith("no verdict")
    assert g.fp_verdict(.01, .001, 500, 1).startswith("no verdict")
    se = g._cluster_se([1., 1., -1., -1.], ["w1", "w1", "w2", "w2"])
    assert np.isclose(se, np.sqrt(2) * np.std([2., -2.], ddof=1) / 4)
