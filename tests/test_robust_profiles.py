import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import robust_profiles as rp


@pytest.fixture(scope='module')
def small():
    box = pd.read_csv(rp.fw.BOXES); sched = rp.fw.schedule_frame(pd.read_csv(rp.fw.SCHEDULE))
    keep = sched.season.isin([2013, 2014]) & sched.result.notna()
    return box[box.season.isin([2013, 2014])], sched[keep]


@pytest.fixture(scope='module')
def small_profiles(small):
    return rp.team_profiles(*small)


def test_weighted_median_rules():
    assert rp.weighted_median([3., 1., 2.], [1., 1., 1.]) == 2.
    assert rp.weighted_median([1., 2., 3., 4.], [1., 1., 1., 1.]) == 2.5      # exactly half: midpoint
    assert rp.weighted_median([1., 2., 3.], [1., 1., 5.]) == 3.               # weight moves the median
    assert rp.weighted_median([1., np.nan, 2., 9.], [1., 5., 0., 1.]) == 5.   # NaN and zero weight ignored
    assert np.isnan(rp.weighted_median([], []))
    # an outlier moves the mean, not the median
    x, w = np.array([4., 5., 6., 60.]), np.array([1., 1., 1., .9])
    assert rp.weighted_median(x, w) == 5. and np.average(x, weights=w) > 15


def test_median_and_winsor_equal_production_without_outliers():
    # identical per-game rates: median = ratio of sums, and nothing is clipped
    vals = np.array([[50., 10.], [100., 20.], [25., 5.]]); w = np.array([.5, .8, 1.])
    league = np.array([[40., 10.], [60., 10.]])
    full = np.zeros((3, len(rp.m.COUNTS))); full[:, rp.m.COUNTS.index('rush_yards')] = vals[:, 0]
    full[:, rp.m.COUNTS.index('rush_attempts')] = vals[:, 1]
    lg = np.zeros((2, len(rp.m.COUNTS))); lg[:, rp.m.COUNTS.index('rush_yards')] = league[:, 0]
    lg[:, rp.m.COUNTS.index('rush_attempts')] = league[:, 1]
    spec = {'rush_yards_per_attempt': rp.SPECS['rush_yards_per_attempt']}
    prod = rp.m.metric_profile(full, w, lg, spec)['rush_yards_per_attempt']
    assert rp.median_rate(vals, w, league, 'rush_yards', 'rush_attempts', 1.) == pytest.approx(prod)
    assert rp.winsor_rate(vals, w, league, 'rush_yards', 'rush_attempts', 1., 0., 99.) == pytest.approx(prod)
    # one outlier game: both robust arms sit below production
    out = vals.copy(); out[2] = [150., 5.]
    full[:, rp.m.COUNTS.index('rush_yards')] = out[:, 0]
    p2 = rp.m.metric_profile(full, w, lg, spec)['rush_yards_per_attempt']
    assert rp.median_rate(out, w, league, 'rush_yards', 'rush_attempts', 1.) < p2
    assert rp.winsor_rate(out, w, league, 'rush_yards', 'rush_attempts', 1., 0., 8.) < p2


def test_no_history_falls_back_to_league_and_peaks_shrink_to_zero():
    empty = np.zeros((0, 2)); league = np.array([[40., 10.], [60., 10.]])
    assert rp.median_rate(empty, np.zeros(0), league, 'rush_yards', 'rush_attempts', 1.) == pytest.approx(5.)
    w = np.array([1., 1.])
    assert rp.peak([10., 20.], w, 'P') == pytest.approx(30/6)
    assert rp.peak([10., 20.], w, 'A') == pytest.approx(2*15/6)
    assert rp.peak([10., 20.], w, 'B', 12., 14.) == pytest.approx(26/6)
    assert rp.peak([], np.zeros(0), 'A') == 0.


def test_cap_touches_only_long_gains():
    p = pd.DataFrame({'yards_gained': [45., 15., -7., 5., 30., 12.], 'pass_attempt': [1, 0, 0, 0, 0, 1],
                      'sack': [0, 0, 1, 0, 0, 0], 'rush_attempt': [0, 1, 0, 1, 0, 0]})
    c = rp.cap_plays(p)
    assert c.yards_gained.tolist() == [20., 10., -7., 5., 30., 12.]   # kickoff/punt rows (no flags) untouched
    assert p.yards_gained.tolist()[0] == 45.                          # input not mutated


def test_capped_boxes_replace_only_yardage_and_reject_missing_rows(small):
    box, _ = small
    capped = box[['game_id', 'team']].assign(net_pass_yards=box.net_pass_yards, rush_yards=box.rush_yards,
                                             net_pass_yards_capped=box.net_pass_yards-5, rush_yards_capped=box.rush_yards-3)
    out = rp.capped_boxes(box, capped)
    assert list(out['C'].columns) == list(box.columns)
    pd.testing.assert_frame_equal(out['Pc'].reset_index(drop=True), box.reset_index(drop=True), check_dtype=False)
    assert np.allclose(out['C'].rush_yards, box.rush_yards-3) and np.allclose(out['C'].net_yards, box.net_yards-8)
    assert np.allclose(out['C'].plays, box.plays) and np.allclose(out['C'].net_pass_yards, box.net_pass_yards-5)
    with pytest.raises(ValueError, match='Missing capped'):
        rp.capped_boxes(box, capped.iloc[1:])


def test_production_arm_reproduces_production_profiles(small, small_profiles):
    box, sched = small
    ref = rp.fw.profiles(box, sched, half_life=8.).set_index('game_id')
    mine = rp.home_minus_away(small_profiles, sched).set_index('game_id').loc[ref.index, ref.columns]
    a, b = ref.to_numpy(float), mine.to_numpy(float)
    assert np.array_equal(np.isfinite(a), np.isfinite(b))
    assert np.nanmax(np.abs(a-b)) < 1e-12


def test_profiles_use_only_earlier_games(small, small_profiles):
    box, sched = small
    shocked = box.copy()
    wk = (shocked.season == 2014) & (shocked.week == 10)
    for c in ('rush_yards', 'penalty_yards'): shocked.loc[wk, c] = shocked.loc[wk, c]*3+50
    shocked.loc[wk, 'net_yards'] = shocked.loc[wk, 'net_pass_yards']+shocked.loc[wk, 'rush_yards']
    b = rp.team_profiles(shocked, sched)
    cols = [c for c in small_profiles if c[:2] in ('P|', 'A|', 'B|')]
    A, B = small_profiles.set_index(['season', 'week', 'game_id', 'team']), b.set_index(['season', 'week', 'game_id', 'team'])
    upto = A.index.get_level_values('season').isin([2013]) | (A.index.get_level_values('week') <= 10)
    assert np.allclose(A.loc[upto, cols].to_numpy(float), B.loc[upto, cols].to_numpy(float), equal_nan=True)
    later = (A.index.get_level_values('season') == 2014) & (A.index.get_level_values('week') == 11)
    for arm in ('P', 'A', 'B'):
        c = [f'{arm}|for:rush_yards_per_attempt', f'{arm}|for:penalty_yards_per_game']
        assert not np.allclose(A.loc[later, c].to_numpy(float), B.loc[later, c].to_numpy(float))


def test_targets_are_the_game_itself_and_allowed_is_the_opponent(small, small_profiles):
    box, _ = small
    r = small_profiles.dropna(subset=['y|for:plays_per_game']).iloc[50]
    own = box[(box.game_id == r.game_id) & (box.team == r.team)].iloc[0]
    opp = box[(box.game_id == r.game_id) & (box.team != r.team)].iloc[0]
    assert r['y|for:plays_per_game'] == own.plays and r['y|allowed:plays_per_game'] == opp.plays
    assert r['w|for:rush_yards_per_attempt'] == own.rush_attempts
    assert r['y|for:rush_yards_per_attempt'] == pytest.approx(own.rush_yards/own.rush_attempts)


def test_recalibration_is_walk_forward():
    rng = np.random.default_rng(0); n = 300
    season = np.repeat([2014, 2015, 2016], 100); f = rng.normal(size=n); y = 2*f+rng.normal(size=n); w = np.ones(n)
    a = rp.recalibrate(f, y, w, season)
    assert np.isnan(a[season == 2014]).all() and np.isfinite(a[season > 2014]).all()
    y2 = y.copy(); y2[season == 2016] += 100.                         # a season's own targets never fit it
    b = rp.recalibrate(f, y2, w, season)
    assert np.allclose(a[season <= 2016], b[season <= 2016], equal_nan=True)
    y3 = y.copy(); y3[season == 2015] += 100.
    assert not np.allclose(a[season == 2016], rp.recalibrate(f, y3, w, season)[season == 2016])


def test_thresholds_come_from_history_and_clip_both_tails():
    hist = pd.DataFrame({c: np.arange(1., 101.) for c in rp.m.COUNTS})
    hist['plays'] = np.arange(1., 101.); hist['max_lead'] = np.arange(100.); hist['max_deficit'] = np.arange(100.)
    t = rp.thresholds(hist)
    assert t['plays_per_game'] == pytest.approx((np.quantile(np.arange(1., 101.), .025), np.quantile(np.arange(1., 101.), .975)))
    assert t['first_down_rate'] == pytest.approx((1., 1.))            # identical rates: degenerate band


def test_identical_arm_scores_zero_and_verdict_rules():
    primary = pd.DataFrame([{'score': 'recal', 'arm': 'A', 'group': g, 'mean_pct_change': v, 'ci9833_hi': hi}
                            for g, v, hi in [('2015-16', -1., 0), ('2017-22', -1., 0), ('2023-25', -1., 0), ('2015-25', -1., -.1)]])
    assert rp.verdict(primary, 'A') == 'advance to stage 2'
    primary.loc[primary.group == '2015-25', 'ci9833_hi'] = .1
    assert rp.verdict(primary, 'A') == 'unresolved'
    primary.loc[primary.group.isin(['2015-16', '2023-25']), 'mean_pct_change'] = 0.
    assert rp.verdict(primary, 'A') == 'stop'


def test_summary_of_identical_arms_is_zero(small_profiles):
    d = rp.frame(small_profiles.assign(**{f'C|{f}': small_profiles[f'P|{f}'] for f in rp.APPLIED['C']}))
    d['season'] = d.season.replace({2013: 2014, 2014: 2015})            # one scored basis in the small fixture
    d['stratum'] = np.where(d.season == 2015, '2015-16', 'warm-up')
    S = rp.score(d)
    primary, _ = rp.summarize(d, S, C=rp.draw_matrix(d.stratum.to_numpy(), d.cluster.to_numpy(), draws=50))
    c = primary[(primary.arm == 'C') & (primary.group == '2015-16')]
    assert np.allclose(c.mean_pct_change, 0.) and np.allclose(c[['ci9833_lo', 'ci9833_hi']], 0.)


def test_research_rejects_protected_outputs():
    for p in (rp.ROOT/'data'/'x', rp.ROOT/'public'):
        with pytest.raises(ValueError, match='Protected'): rp.guard(p)
