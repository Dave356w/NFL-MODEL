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


def test_training_excludes_target_and_future_seasons_and_ties():
    d = history()
    rule = f.fit(d, 2023)
    assert rule and rule['training_max_season'] == 2022
    poison = d.assign(season=2023, result=-100., **{'home won': 0.})
    tied = d.assign(result=0., **{'home won': .5})
    assert f.fit(pd.concat([d, poison, poison.assign(season=2024), tied]), 2023) == rule
    assert f.fit(d, 2022) is None
    assert f.fit(d.iloc[:20], 2023) is None


def test_signed_boundaries_missing_and_pickem():
    rule = dict(cuts=[3, 7, 10], magnitudes=[4, 5, 7, 13])
    x = f.apply([0., 2.99, 3., -7., 10., np.nan], rule)
    np.testing.assert_allclose(x, [0, 4, 5, -7, 13, np.nan], equal_nan=True)
    assert np.isnan(f.apply([1.], None)).all()


def test_grading_skip_before_push_tied_final_and_pending():
    d = pd.DataFrame({'spread_line': [3., 3., -3., 0., 3., np.nan],
                      'result': [3., 3., 0., 0., np.nan, 7.]})
    r, u = f.grade(d, [3., 4., -2., 1., 4., 4.])
    assert list(r) == ['S', 'P', 'W', 'P', '', '']
    np.testing.assert_allclose(u, [0, 0, 1/1.1, 0, np.nan, np.nan], equal_nan=True)


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
    rule = f.fit(d, 2023)
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
    assert f.fit(d, 2023) is None


def test_strict_zero_edge_and_explicit_selection_denominator():
    d = pd.DataFrame({'spread_line': [3., 3., 3.],
                      'result': [4., 4., 4.]})
    result, units = f.grade(d, [3., 3. + 1e-11, 3. + 1e-8])
    assert list(result) == ['S', 'S', 'W']
    assert list(units[:2]) == [0., 0.]
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


def test_committed_annual_maps_are_frozen_regression_targets():
    # Source is the committed exposed-history ledger, not newly selected
    # outcomes. A change to any saved band would invalidate ATS comparisons.
    root = Path(__file__).resolve().parents[1]
    d = pd.read_csv(root / 'data/latest/fixed_band_ledger.csv', low_memory=False)
    archived = json.loads((root / 'data/latest/fixed_band_rules.json').read_text())
    assert [int(r['season']) for r in archived] == [2023, 2024, 2025, 2026]
    for stored in archived:
        current = f.fit(d, int(stored['season']))
        assert current is not None
        assert current['magnitudes'] == stored['magnitudes']
        assert current['cuts'] == stored['cuts']
        assert current['training_games'] == stored['training_games']
