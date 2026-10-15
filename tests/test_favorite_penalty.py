import datetime as dt
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit

import grade_ledger as g
import nfl_model as m
from test_grade_ledger import RESULTS, rec

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import favorite_penalty as fp

V116 = "boxscore-composite-v1.16"


def test_penalty_shrinks_only_favorite_bullish_departures():
    q = np.array([.7, .3, .7, .4, .45, .55, .5, .6, .6])
    p = np.array([.8, .2, .65, .45, .55, .45, .7, .6, np.nan])
    out = m.favorite_penalized_wp(p, q)
    assert out[0] == pytest.approx(expit(logit(.7)+.2*(logit(.8)-logit(.7))))      # home favorite, more bullish
    assert out[1] == pytest.approx(expit(logit(.3)+.2*(logit(.2)-logit(.3))))      # away favorite, more bullish
    assert np.allclose(out[2:8], p[2:8])     # cooler on the favorite, flips, pick'em market, equal: unchanged
    assert np.isnan(out[8])


def test_lambda_limits_and_missing_market():
    p, q = np.array([.8, .25]), np.array([.7, .35])
    assert np.allclose(m.favorite_penalized_wp(p, q, 1.), p)
    assert np.allclose(m.favorite_penalized_wp(p, q, 0.), q)
    assert np.allclose(m.favorite_penalized_wp(p, [np.nan, None]), p)


def test_picks_never_change():
    rng = np.random.default_rng(5)
    p, q = rng.uniform(.02, .98, 5000), rng.uniform(.02, .98, 5000)
    out = m.favorite_penalized_wp(p, q)
    assert np.array_equal(out > .5, p > .5) and np.array_equal(out < .5, p < .5)
    assert np.all(np.abs(out-.5) <= np.abs(p-.5)+1e-12)


def test_ledger_scores_penalty_for_v116_rows_only():
    out = g.grade([rec("a", .8, .7, rev=V116), rec("b", .6, .4, rev=V116), rec("a", .8, .7, rev="r1", exp="x")], RESULTS)
    v = out[out.revision == V116].set_index("game_id"); other = out[out.revision == "r1"]
    assert v.loc["a", "fp_wp"] == pytest.approx(m.favorite_penalized_wp([.8], [.7])[0])
    assert v.loc["a", "fp_log_loss"] == pytest.approx(-np.log(v.loc["a", "fp_wp"]))       # home won game a
    assert v.loc["b", "fp_wp"] == pytest.approx(.6)                                         # a flip is unchanged
    assert other.fp_wp.isna().all() and other.fp_log_loss.isna().all()
    assert ((v.fp_wp > .5) == (v.model_wp > .5)).all()
    sm = g.summary(out[out.revision == V116])
    assert sm["fp_n"] == 2 and sm["fp_changed"] == 1
    assert sm["fp_gain"] == pytest.approx((v.model_log_loss-v.fp_log_loss).mean())
    text = g.report_text(out)
    assert text.count("favorite-confidence penalty") == 1 and "no verdict before 200 graded games" in text  # FAVORITE_PENALTY.md addendum 2026-10-15


def _v116_season(week18_graded):
    """2027 v1.16 rows for weeks 17 and 18; week 18 has no result yet unless week18_graded."""
    recs = [{**rec(gid, .8, .7, rev=V116, week=wk), "season": 2027} for gid, wk in (("a", 17), ("b", 18))]
    res = pd.DataFrame({"game_id": ["a", "b"], "away_score": [10, 10], "home_score": [20, 20], "result": [10, 10]})
    return g.grade(recs, res if week18_graded else res.iloc[:1])


def test_penalty_line_is_a_checkpoint_only_once_week_18_is_graded():
    jan = dt.datetime(2028, 1, 4, tzinfo=dt.timezone.utc)
    pending = g.report_text(_v116_season(False), now=jan)                    # week 18 not yet played
    assert "interim reading, not a verdict" in pending and "January checkpoint verdict" not in pending
    done = g.report_text(_v116_season(True), now=jan + dt.timedelta(days=7))
    assert "January checkpoint verdict" in done and "interim reading" not in done
    october = g.report_text(_v116_season(True), now=dt.datetime(2028, 10, 15, tzinfo=dt.timezone.utc))
    assert "interim reading, not a verdict" in october and "week-cluster SE" in october


def test_research_scoring_checks_bets_and_gain():
    # a, c, d back the favorite more strongly than q (c is an away favorite); b is cooler, so unchanged.
    x = pd.DataFrame({'basis': 'b', 'game_id': list('abcd'), 'season': 2026, 'week': [1, 1, 2, 2],
                      'home won': [1., 0., 0., 1.], 'model_wp': [.9, .6, .4, .75], 'q': [.8, .65, .45, .7],
                      'home_moneyline': [-400, -185, 120, -233], 'away_moneyline': [300, 155, -140, 190]})
    won = fp.score(x)
    assert won['n'] == 4 and won['changed'] == 3 and won['bets_identical']
    assert won['units_model'] == pytest.approx(won['units_penalized'])
    assert won['gain'] < 0                     # every penalized favorite won: shrinking them costs log loss
    lost = fp.score(x.assign(**{'home won': [0., 0., 1., 0.]}))
    assert lost['gain'] > 0                    # every penalized favorite lost: shrinking them helps
