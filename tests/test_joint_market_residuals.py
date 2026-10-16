import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research'))
import joint_market_residuals as j
import joint_market_residuals_report as report


def two_team_history():
    return pd.DataFrame(dict(game_id=['a', 'b', 'c'], season=[2024, 2024, 2025], week=[1, 2, 1],
                             gameday=['2024-09-01', '2024-09-08', '2025-09-01'],
                             home_team=['SF'] * 3, away_team=['SEA'] * 3,
                             home_score=[28., 21., 20.], away_score=[21., 24., 10.],
                             spread_line=[3., 3., 3.], total_line=[45., 45., 45.],
                             home_moneyline=[-150.] * 3, away_moneyline=[130.] * 3))


def test_histories_are_team_oriented_span_four_and_offseason_retained():
    f, audit = j.add_histories(two_team_history())
    assert f.loc[0, 'home_scored'] == 0
    assert f.loc[1, 'home_scored'] == pytest.approx(.4 * (28 - 24))
    assert f.loc[1, 'away_allowed'] == pytest.approx(f.loc[1, 'home_scored'])
    assert f.loc[1, 'home_total_residual'] == pytest.approx(.4 * (49 - 45))
    expected = .5 * (.6 * .4 * 4 + .4 * (21 - 24))
    assert f.loc[2, 'home_scored'] == pytest.approx(expected)
    assert audit.loc[audit.game_id == 'b', 'source_week'].eq(1).all()
    assert audit.loc[audit.game_id == 'c', 'source_season'].eq(2024).all()


def test_history_excludes_own_and_future_labels_and_fails_duplicate_team():
    a = two_team_history()
    original, _ = j.add_histories(a)
    a.loc[a.week == 2, ['home_score', 'away_score']] = 70
    changed, _ = j.add_histories(a)
    cols = list(j.MEAN_HISTORY + j.ABS_HISTORY + j.SQ_HISTORY)
    assert np.array_equal(original.loc[1, cols], changed.loc[1, cols])
    assert not np.array_equal(original.loc[2, cols], changed.loc[2, cols])
    with pytest.raises(ValueError, match='more than once'):
        j.add_histories(pd.concat([a, a.iloc[[0]].assign(game_id='duplicate')]))


def test_joint_is_normalized_and_all_derived_probabilities_are_coherent():
    p = j.smooth_joint(np.array([25., 21.]), np.array([81., 100., 12.]))
    assert p.sum() == pytest.approx(1)
    assert np.all(p >= 0)
    z = j.marginals(p)
    for pmf in z.values():
        assert pmf.sum() == pytest.approx(1)
    home, away = z['home'] @ j.SCORE_SUPPORT, z['away'] @ j.SCORE_SUPPORT
    assert z['margin'] @ j.MOV_SUPPORT == pytest.approx(home - away)
    assert z['total'] @ j.TOTAL_SUPPORT == pytest.approx(home + away)
    swapped = j.smooth_joint(np.array([21., 25.]), np.array([100., 81., 12.]))
    assert np.allclose(p.T, swapped)
    assert sum(j.event_probabilities(z['margin'], j.MOV_SUPPORT, 3)) == pytest.approx(1)
    assert j.event_probabilities(z['margin'], j.MOV_SUPPORT, 3)[1] > 0
    assert j.event_probabilities(z['margin'], j.MOV_SUPPORT, 3.5)[1] == 0


def test_covariance_is_positive_definite_even_for_adversarial_predictions():
    cov, clipped = j.stable_covariance(np.array([[-100., 10000., 900.], [81., 81., 0.]]))
    assert clipped.tolist() == [True, False]
    assert np.all(cov[:, 0] * cov[:, 1] > cov[:, 2] ** 2)
    with pytest.raises(ValueError):
        j.smooth_joint([24., 20.], [1., 1., 2.])


def test_crps_probability_and_moneyline_settlement():
    assert j.discrete_crps(np.array([0., 1., 0.]), np.arange(3), 1) == 0
    assert j.discrete_crps(np.array([0., 1., 0.]), np.arange(3), 2) == 1
    assert j.fair_moneyline([-150., 0.], [130., 130.])[0] == pytest.approx(.6 / (.6 + 100 / 230))
    assert np.isnan(j.fair_moneyline([-150., 0.], [130., 130.])[1])
    f = pd.DataFrame(dict(home_score=[24., 10., 21.], away_score=[17., 20., 21.],
                          home_moneyline=[-150.] * 3, away_moneyline=[130.] * 3,
                          q=[.58] * 3, p_home_non_tie=[.6, .4, .6],
                          spread_line=[3.] * 3, total_line=[45.] * 3,
                          cover_conditional=[.5] * 3, over_conditional=[.5] * 3))
    z = j.add_binary_and_bet_scores(f)
    assert z.model_units.tolist() == pytest.approx([2 / 3, 1.3, 0])
    assert np.isnan(z.win_ll.iloc[2])
    assert z.model_null.iloc[0] < 0


def test_empirical_mixture_normalizes_and_changes_score_pattern():
    train = two_team_history().iloc[:2].copy()
    p = j.smooth_joint([24., 21.], [81., 81., 0.])
    mixed, ess = j.empirical_joint(p, train, train.iloc[0], np.ones(2), ())
    assert mixed.sum() == pytest.approx(1)
    assert 1 <= ess <= 2
    assert mixed[28, 21] > p[28, 21]
    assert np.all(mixed > 0)


def test_production_paths_are_protected():
    for path in (j.ROOT / 'data', j.ROOT / 'data' / 'research', j.ROOT / 'public'):
        with pytest.raises(ValueError):
            j.guard_output(path)


def test_week_bootstrap_keeps_pairing_and_game_weighting():
    seasons = np.array([2023, 2023, 2023, 2024, 2024])
    weeks = np.array([1, 1, 2, 1, 2])
    values = np.column_stack([np.full(5, .125), np.arange(5.)])
    draws = report.week_bootstrap(values, seasons, weeks, reps=500)
    assert np.all(draws[:, 0] == .125)
    assert np.all((draws[:, 1] >= 0) & (draws[:, 1] <= 4))
    identical = report.week_bootstrap(values, seasons, weeks, reps=500)
    assert np.array_equal(draws, identical)
    with_nan = values.copy()
    with_nan[0, 0] = np.nan
    assert np.allclose(report.week_bootstrap(with_nan, seasons, weeks, reps=500)[:, 0], .125)


def test_end_to_end_own_week_mutation_cannot_change_forecast(tmp_path):
    rng = np.random.default_rng(7)
    rows = []
    for year in range(2013, 2018):
        for week in range(1, 3 if year == 2017 else 9):
            for game in range(8):
                rows.append(dict(game_id=f'{year}_{week}_{game}', season=year, week=week,
                                 gameday=f'{year}-09-01', home_team=f'H{game}', away_team=f'A{game}',
                                 home_score=int(rng.integers(7, 40)), away_score=int(rng.integers(7, 40)),
                                 spread_line=float(game - 3), total_line=45.,
                                 home_moneyline=-150., away_moneyline=130.))
    f = pd.DataFrame(rows)
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    first = j.fit_and_forecast(f, a, 2017)
    f.loc[(f.season == 2017) & (f.week == 2), ['home_score', 'away_score']] = [70, 0]
    second = j.fit_and_forecast(f, b, 2017)
    cols = ['p_home', 'p_tie', 'home_mean', 'away_mean', 'total_mean', 'margin_mean', 'total_width90']
    assert np.array_equal(first[cols], second[cols])
    audit = pd.read_csv(a / 'fit_audit.csv')
    assert all((r.training_max_season, r.training_max_week) < (r.season, r.week)
               for r in audit.itertuples())
    assert audit.loc[audit.season == 2017, 'covariance_fallback'].eq(False).all()
