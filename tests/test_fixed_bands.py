import json
from pathlib import Path
import numpy as np
import pandas as pd
import fixed_bands as f


def history():
    spread = np.tile([1., 4., 8., 12.], 80)
    return pd.DataFrame({'season': np.repeat([2021, 2022], 160),
                         'home won': 1., 'model_spread': spread,
                         'spread_line': spread + .5, 'result': spread + 2})


def test_legacy_training_excludes_target_and_future_seasons_and_ties():
    d = history()
    rule = f.fit_legacy(d, 2023)
    assert rule and rule['training_max_season'] == 2022
    poison = d.assign(season=2023, result=-100., **{'home won': 0.})
    tied = d.assign(result=0., **{'home won': .5})
    assert f.fit_legacy(pd.concat([d, poison, poison.assign(season=2024), tied]), 2023) == rule
    assert f.fit_legacy(d, 2022) is None
    assert f.fit_legacy(d.iloc[:20], 2023) is None


def test_signed_boundaries_missing_and_pickem():
    rule = dict(cuts=[3, 7, 10], magnitudes=[4, 5, 7, 13])
    x = f.apply([0., 2.99, 3., -7., 10., np.nan], rule)
    np.testing.assert_allclose(x, [0, 4, 5, -7, 13, np.nan], equal_nan=True)
    assert np.isnan(f.apply([1.], None)).all()


def test_grading_skip_before_push_tied_final_and_pending():
    d = pd.DataFrame({'spread_line': [3., 3., -3., 0., 3., np.nan],
                      'result': [3., 3., 0., 0., np.nan, 7.]})
    # The earlier rule skips a zero edge before push grading.
    r, u = f.grade(d, [3., 4., -2., 1., 4., 4.], favorite_on_tie=False)
    assert list(r) == ['S', 'P', 'W', 'P', '', '']
    np.testing.assert_allclose(u, [0, 0, 1/1.1, 0, np.nan, np.nan], equal_nan=True)
    # Production: the zero edge is a favorite bet, so the tied final is a push.
    r, u = f.grade(d, [3., 4., -2., 1., 4., 4.])
    assert list(r) == ['P', 'P', 'W', 'P', '', '']


def test_zero_edge_takes_the_market_favorite_and_pickem_still_skips():
    d = pd.DataFrame({'spread_line': [3., -7., 7., -3., 0., 0.],
                      'result': [10., -10., 0., 0., 5., 5.]})
    prediction = [3., -7., 7. + 1e-11, -3., 0., 1.]
    np.testing.assert_array_equal(f.pick(prediction, d.spread_line), [1., -1., 1., -1., 0., 1.])
    r, u = f.grade(d, prediction)
    assert list(r) == ['W', 'W', 'L', 'L', 'S', 'W']
    np.testing.assert_allclose(u, [1/1.1, 1/1.1, -1, -1, 0, 1/1.1])
    # Saved decisions under the earlier rule keep their skips, row by row.
    r, _ = f.grade(d, prediction, [False, True, False, True, True, True])
    assert list(r) == ['S', 'W', 'S', 'L', 'S', 'W']
    assert np.isnan(f.pick([np.nan], [3.])).all()


def test_summary_excludes_unavailable_and_skipped_stakes():
    d = pd.DataFrame({'season': [2023]*4, 'fixed_band_spread': [4., 3., 4., np.nan],
                      'spread_line': [3.]*4, 'result': [7., 7., 3., -7.],
                      'original_ats_result': ['W', 'L', 'P', 'L'],
                      'fixed_band_ats_result': ['W', 'S', 'P', '']})
    r = f.summary(d).query("season == 'All' and method == 'Fixed bands'").iloc[0]
    assert r.games == 3 and r.bets == 2 and r.skips == 1
    assert np.isclose(r.roi, (1/1.1)/2)


def test_coverage_is_enforced_inside_monotone_optimization():
    # Within each of four bands, half the outcomes favor either ATS side.
    # An unconstrained W-L maximizer chooses an exact-line skip in every
    # band (its squared-distance tie-break prefers the original points).
    # Coverage-first fitting must find a feasible monotone runner-up.
    d = history()
    d['spread_line'] = d.model_spread
    sign = np.where((np.arange(len(d)) // 4) % 2 == 0, 1., -1.)
    d['result'] = d.spread_line + 2 * sign
    d['home won'] = (d.result > 0).astype(float)
    rule = f.fit_legacy(d, 2023)
    assert rule is not None
    mapped = f.apply(d.model_spread, rule)
    assert (np.abs(mapped - d.spread_line) > f.EPS).mean() >= .90
    assert rule['magnitudes'] == sorted(rule['magnitudes'])
    assert rule['cuts'] == [3., 7., 10.]


def test_no_feasible_coverage_returns_no_map():
    d = history()
    # A signed zero can never move away from a pick'em market.
    d.loc[d.model_spread == 1, 'model_spread'] = 0.
    d['spread_line'] = 0.
    d['result'] = 3.
    assert f.fit_legacy(d, 2023) is None


def test_strict_zero_edge_and_explicit_selection_denominator():
    d = pd.DataFrame({'spread_line': [3., 3., 3.],
                      'result': [4., 4., 4.]})
    result, units = f.grade(d, [3., 3. + 1e-11, 3. + 1e-8], favorite_on_tie=False)
    assert list(result) == ['S', 'S', 'W']
    assert list(units[:2]) == [0., 0.]
    assert list(f.grade(d, [3., 3. + 1e-11, 3. + 1e-8])[0]) == ['W', 'W', 'W']
    row = pd.DataFrame({'season': [2026] * 3, 'fixed_band_spread': [3., 3., 4.],
                        'result': [4.] * 3, 'spread_line': [3.] * 3,
                        'original_ats_result': ['S', 'S', 'W'],
                        'fixed_band_ats_result': ['S', 'S', 'W']})
    stats = f.summary(row)
    fixed = stats.query("method == 'Fixed bands' and season == 'All'").iloc[0]
    assert fixed.opportunities == fixed.games == 3
    assert fixed.selected == fixed.bets == 1
    assert fixed.skips == 2
    assert fixed.selection_rate == 1 / 3


V118_LEDGER = 'tests/fixtures/v118_fixed_band_ledger.csv'  # frozen copy from 989d882; never regenerated


def frozen_v118():
    root = Path(__file__).resolve().parents[1]
    return pd.read_csv(root / V118_LEDGER)


def test_committed_annual_maps_are_frozen_regression_targets():
    # Source is a frozen copy of the v1.18 exposed-history ledger (bot builds cannot change it),
    # not newly selected outcomes. A change to any saved band would invalidate ATS comparisons.
    root = Path(__file__).resolve().parents[1]
    d = frozen_v118()
    archived = json.loads((root / 'tests/fixtures/legacy_fixed_band_rules.json').read_text())
    assert [int(r['season']) for r in archived] == [2023, 2024, 2025, 2026]
    for stored in archived:
        current = f.fit_legacy(d, int(stored['season']))
        assert current is not None
        assert current['magnitudes'] == stored['magnitudes']
        assert current['cuts'] == stored['cuts']
        assert current['training_games'] == stored['training_games']


def test_production_median_includes_ties_and_ignores_target_future_and_prices():
    d = history()
    rule = f.fit(d, 2023)
    assert rule['magnitudes'] == [3., 6., 10., 14.]
    assert rule['method'] == 'median_signed_mov'
    assert rule['policy_version'] == f.POLICY_VERSION
    assert rule['includes_tied_finals']
    assert rule['training_band_counts'] == [80]*4
    poison = d.assign(season=2023, result=-100.)
    assert f.fit(pd.concat([d, poison, poison.assign(season=2024)]), 2023) == rule
    tied = d.assign(result=0., **{'home won': .5})
    changed = f.fit(pd.concat([d, tied]), 2023)
    assert changed['training_games'] == 640
    assert changed['magnitudes'] == [1.5, 3., 5., 7.]
    assert f.fit(d.drop(columns=['home won', 'spread_line']), 2023) == rule
    assert f.fit(d, 2022) is None
    assert f.fit(d.iloc[:20], 2023) is None


def test_median_signed_losses_away_symmetry_half_points_and_negative_values():
    d = history()
    d['model_spread'] *= np.where((np.arange(len(d))//4) % 2, -1., 1.)
    for k, magnitude in enumerate([1, 4, 8, 12]):
        ix = np.flatnonzero(d.model_spread.abs() == magnitude)
        signed_margin = np.resize([-10., 0., 3., 10.], len(ix)) + 2*k
        d.loc[ix, 'result'] = np.sign(d.loc[ix, 'model_spread'])*signed_margin
    rule = f.fit(d, 2023)
    assert rule['magnitudes'] == [1.5, 3.5, 5.5, 7.5]
    np.testing.assert_allclose(f.apply([1., -4., 8., -12.], rule), [1.5, -3.5, 5.5, -7.5])
    d['result'] = -3*np.sign(d.model_spread)
    rule = f.fit(d, 2023)
    assert rule['magnitudes'] == [-3.]*4
    assert f.apply([1.], rule)[0] == -3


def test_median_insufficient_band_and_zero_direction_training_unavailable():
    d = history()
    assert f.fit(d[d.model_spread != 1], 2023) is None
    assert f.fit(d.assign(model_spread=0.), 2023) is None


def test_production_median_reproduces_tested_maps_and_895_game_replay():
    d = frozen_v118()  # v1.18 targets; the live v1.19 maps are checked below
    import nfl_model as m
    d['model_spread'] = m.implied_spread(d.model_wp)
    expected = {2023: [2., 3., 6.5, 14.5], 2024: [3., 3., 7., 14.],
                2025: [3., 4., 6.5, 14.], 2026: [3., 4., 7., 14.]}
    scored = []
    for year, values in expected.items():
        rule = f.fit(d, year)
        assert rule['magnitudes'] == values
        assert rule['training_max_season'] < year
        if year == 2026:
            assert rule['training_games'] == 1359
        g = d[d.season == year]
        mapped = f.apply(g.model_spread, rule)
        scored.extend(zip(*f.grade(g, mapped), *f.grade(g, mapped, favorite_on_tie=False)))
    # This fixture snapshot stops at W5; later bot-updated snapshots may add rows.
    if len(scored) == 895:
        legacy = [r[2] for r in scored]
        assert [legacy.count(k) for k in ('W', 'L', 'P', 'S')] == [412, 349, 13, 121]
        assert np.isclose(sum(r[3] for r in scored), 25.545454545454547)
        # Production: the 121 former skips become favorite bets (61-48-12).
        grades = [r[0] for r in scored]
        assert [grades.count(k) for k in ('W', 'L', 'P', 'S')] == [473, 397, 25, 0]
        assert np.isclose(sum(r[1] for r in scored), 33.)


# Median maps the committed live ledger must reproduce, keyed by the revision that produced it.
# Add a new entry when a REVISION regenerates the replay; never edit a recorded one (pin it to a
# frozen fixture as v1.18 is above).
LIVE_MAPS = {
    'boxscore-composite-v1.19': {2023: [2., 3., 8., 14.], 2024: [2., 3., 7., 14.],
                                 2025: [3., 5., 7., 14.], 2026: [3., 4., 7., 14.]},
}
# v1.20 changes only sourced upcoming-game availability; its historical fit is v1.19's.
LIVE_MAPS['boxscore-composite-v1.20'] = LIVE_MAPS['boxscore-composite-v1.19']
LIVE_MAPS['boxscore-composite-v1.21'] = LIVE_MAPS['boxscore-composite-v1.19']
LIVE_MAPS['boxscore-composite-v1.22'] = LIVE_MAPS['boxscore-composite-v1.19']


def test_live_median_maps_match_the_recorded_targets_for_their_revision():
    root = Path(__file__).resolve().parents[1]
    revision = json.loads((root / 'data/latest/manifest.json').read_text())['revision']
    import nfl_model as m
    assert revision in ('boxscore-composite-v1.19', 'boxscore-composite-v1.20', 'boxscore-composite-v1.21', 'boxscore-composite-v1.22', m.REVISION)  # bot snapshot may precede code adoption
    assert revision in LIVE_MAPS, f'record the median-map targets for {revision} in LIVE_MAPS'
    d = pd.read_csv(root / 'data/latest/retro_ledger.csv')
    d['model_spread'] = m.implied_spread(d.model_wp)
    exported = json.loads((root / 'data/latest/fixed_band_rules.json').read_text())
    for year, values in LIVE_MAPS[revision].items():
        rule = f.fit(d, year)
        assert rule['magnitudes'] == values
        assert rule['training_max_season'] < year
    # The frozen annual targets above do not describe policy-v2 weekly exports.
    for saved in exported:
        year = saved['season']
        rule = f.fit_weekly(d, year, saved['week']) if 'week' in saved else f.fit(d, year)
        assert f.trained_before(rule, year, saved.get('week', 1))
        assert saved == rule
    assert f.fit(d, 2026)['training_games'] == 1359


def test_live_targets_reject_a_changed_map():
    # Negative fixture: the same comparison fails when one band moves.
    d = frozen_v118()
    import nfl_model as m
    d['model_spread'] = m.implied_spread(d.model_wp)
    assert f.fit(d, 2023)['magnitudes'] != LIVE_MAPS['boxscore-composite-v1.19'][2023]


# --- Map policy v2: weekly refit, one-season half-life (owner decision 2026-11-04) ---------------

def weekly_history():
    """Three seasons, 16 weeks, 4 bands x 5 games a week; margins 2 above the spread."""
    rows = []
    for season in (2021, 2022, 2023):
        for week in range(1, 17):
            for x in (1., 4., 8., 12.):
                rows += [dict(season=season, week=week, model_spread=x, result=x + 2, spread_line=x)] * 5
    return pd.DataFrame(rows)


def test_weighted_median_equals_numpy_median_with_equal_weights():
    rng = np.random.default_rng(7)
    for _ in range(300):
        x = rng.integers(-21, 28, rng.integers(1, 40)).astype(float)
        assert f.weighted_median(x, np.ones(len(x))) == np.median(x)
    assert f.weighted_median([0., 10.], [1., 3.]) == 10.  # heavier value wins


def test_weekly_rule_uses_only_games_before_its_week():
    d = weekly_history()
    rule = f.fit_weekly(d, 2023, 9)
    assert rule['magnitudes'] == [3., 6., 10., 14.]
    assert (rule['season'], rule['week'], rule['training_max_season'], rule['training_max_week']) == (2023, 9, 2023, 8)
    assert rule['method'] == f.MAP_METHOD and rule['policy_version'] == f.MAP_POLICY_VERSION
    # Negative: the forecast week itself and every later game cannot move the rule.
    poison = d[(d.season == 2023) & (d.week >= 9)].assign(result=-100.)
    later = d.assign(season=2024, result=-100.)
    clean = d[(d.season < 2023) | (d.week < 9)]
    assert f.fit_weekly(pd.concat([clean, poison, later]), 2023, 9) == rule
    # Positive: earlier weeks of the same season do move it once they carry most of the weight
    # (by week 16 this season's 15 weeks outweigh the two older seasons).
    moved = d.copy()
    moved.loc[(moved.season == 2023) & (moved.week < 16), 'result'] = -100.
    assert f.fit_weekly(moved, 2023, 16)['magnitudes'] == [-100.] * 4
    assert f.fit_weekly(d, 2023, 16)['magnitudes'] == [3., 6., 10., 14.]


def test_weekly_rule_weights_recent_games_more():
    d = weekly_history()
    old = d.season < 2023
    d.loc[old, 'result'] = d.loc[old, 'model_spread']        # older seasons: margin = spread
    d.loc[~old, 'result'] = d.loc[~old, 'model_spread'] + 6  # this season: 6 points more
    # 2023 weeks 1-15 carry most of the weight (one-season half-life), so the median follows them.
    assert f.fit_weekly(d, 2023, 16)['magnitudes'] == [7., 10., 14., 18.]
    # With equal weights the larger older sample would hold the median at the spread.
    assert f.fit(d[d.season < 2023].assign(season=d.season[d.season < 2023]), 2023)['magnitudes'] == [1., 4., 8., 12.]


def test_weekly_rule_needs_two_complete_earlier_seasons_and_band_counts():
    d = weekly_history()
    assert f.fit_weekly(d, 2022, 10) is None          # only 2021 is complete
    assert f.fit_weekly(d, 2023, 1) is not None       # 2021 and 2022 complete
    assert f.fit_weekly(d[d.model_spread != 12.], 2023, 5) is None


def test_trained_before_and_rule_for_match_the_week():
    rule = f.fit_weekly(weekly_history(), 2023, 9)
    assert f.trained_before(rule, 2023, 9)
    assert not f.trained_before(rule, 2023, 10) and not f.trained_before(rule, 2024, 9)
    assert not f.trained_before(dict(rule, training_max_week=9), 2023, 9)
    annual = dict(season=2023, training_max_season=2022, cuts=[3., 7., 10.], magnitudes=[3., 4., 7., 14.])
    assert f.rule_for([annual, rule], 2023, 9) is rule
    assert f.rule_for([annual, rule], 2023, 10) is annual
    assert f.rule_for([annual, rule], 2023, 9, weekly=False) is annual
    assert f.rule_for([annual], 2023, 9, weekly=True) is None


def test_prepare_maps_each_week_with_its_own_rule_and_declares_the_policy():
    d = weekly_history()
    d.loc[(d.season == 2023) & (d.week >= 5), 'result'] = -20.
    for c, v in dict(game_id=[f'g{i}' for i in range(len(d))], home='H', away='A', model_wp=.6).items():
        d[c] = v
    latest = {'retro_ledger': d.copy()}
    f.prepare(latest)
    led = latest['fixed_band_ledger']
    for (season, week), g in led[led.season == 2023].groupby(['season', 'week']):
        rule = f.fit_weekly(d, season, week)
        np.testing.assert_array_equal(g.fixed_band_spread, f.apply(g.model_spread, rule))
    assert (led.map_policy_version == f.MAP_POLICY_VERSION).all()
    assert led.loc[led.season < 2023, 'fixed_band_spread'].isna().all()
    assert {(r['season'], r['week']) for r in latest['fixed_band_rules']} == {(2023, w) for w in range(1, 17)}


def test_live_export_matches_the_map_policy_it_declares():
    root = Path(__file__).resolve().parents[1]
    led = pd.read_csv(root / 'data/latest/fixed_band_ledger.csv', low_memory=False)
    if led.get('map_policy_version', pd.Series(dtype=object)).dropna().eq(f.MAP_POLICY_VERSION).all() and 'map_policy_version' in led:
        import nfl_model as m
        h = pd.read_csv(root / 'data/latest/retro_ledger.csv')
        h['model_spread'] = m.implied_spread(h.model_wp)
        for (season, week), g in led.groupby(['season', 'week']):
            rule = f.fit_weekly(h, int(season), int(week))
            np.testing.assert_array_equal(g.fixed_band_spread.to_numpy(float), f.apply(g.model_spread, rule))


def test_spread_prices_attach_by_game_and_never_enter_the_fit():
    import nfl_model as m
    sched = pd.DataFrame({'game_id': ['a', 'b'], 'home_spread_odds': [-115., 100.], 'away_spread_odds': [-105., -120.]})
    out = m.attach_spread_prices(pd.DataFrame({'game_id': ['b', 'c'], 'x': [1, 2]}), sched)
    assert out.home_spread_odds.tolist()[0] == 100. and np.isnan(out.home_spread_odds.tolist()[1])
    assert m.attach_spread_prices(pd.DataFrame({'game_id': ['a']}), pd.DataFrame({'game_id': ['a']})).home_spread_odds.isna().all()
    main, ctx = m.model_terms(m.PRODUCT_RECIPE)
    assert not set(m.SPREAD_PRICE_COLS) & set(main + ctx)
