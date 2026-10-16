"""Behavioral checks for the versioned R003-RF1 frequency extension."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research'))
import distribution_ablations as d
import joint_market_residuals as j
import r003_rare_frequency as rf


def joint():
    p = j.smooth_joint([18., 22.], [100., 90., 15.])
    return d.condition_support(p, d.football_support())[0]


def archive(count=300, observed=0):
    return pd.DataFrame(dict(game_id=[f'g{x}' for x in range(count)], season=2020,
                             week=1, mass0=.8, mass1=.18, mass2=.02,
                             rare_count=observed))


def test_probability_shape_support_swap_and_positive_legal_rarity():
    p = joint(); q = rf.transform(p, 2.)
    assert q.sum() == pytest.approx(1)
    assert np.array_equal(q > 0, p > 0)
    assert q[6, 1] > 0 and q[1, 6] > 0 and q[7, 1] == 0
    assert np.allclose(rf.transform(p.T, 2.), q.T, atol=1e-15)
    assert np.allclose(rf.transform(p, 0.), p, atol=1e-15)
    assert q[6, 1] / q[6, 3] == pytest.approx(p[6, 1] / p[6, 3] * np.exp(-2.))
    assert q[4, 4] / q[6, 3] == pytest.approx(p[4, 4] / p[6, 3] * np.exp(-4.))
    masses = rf.sufficient(p)
    assert masses.sum() == pytest.approx(1)
    assert rf.rare_counts(8)[4, 5] == 2


@pytest.mark.parametrize('theta', [-1, 8.01, np.nan, np.inf, True])
def test_invalid_penalties_fail(theta):
    with pytest.raises(ValueError):
        rf.transform(joint(), theta)


def test_objective_equals_full_joint_likelihood_and_gradient():
    p = joint(); theta = 1.2; q = rf.transform(p, theta)
    masses = np.array([rf.sufficient(p)] * 3)
    observed = np.array([0., 1., 2.]); weights = np.array([.2, .3, .5])
    pairs = [(20, 17), (4, 17), (4, 5)]
    changes = np.array([np.log(p[h, a] / q[h, a]) for h, a in pairs])
    loss, grad = rf.objective(theta, masses, observed, weights)
    assert loss == pytest.approx(weights @ changes + .5 * rf.RIDGE * theta**2)
    eps = 1e-5
    numeric = (rf.objective(theta+eps, masses, observed, weights)[0] -
               rf.objective(theta-eps, masses, observed, weights)[0]) / (2*eps)
    assert grad == pytest.approx(numeric, abs=1e-9)


def test_fitter_learns_suppression_but_not_when_rarity_is_underpredicted():
    theta, fit = rf.fit_penalty(archive(), 2020, 2)
    assert 0 < theta < rf.MAX_THETA and fit['boundary'] == 'interior'
    train = archive(); weights = np.ones(len(train)) / len(train)
    assert abs(rf.objective(theta, train[['mass0', 'mass1', 'mass2']].to_numpy(),
                            train.rare_count.to_numpy(), weights)[1]) < 1e-10
    assert rf.fit_penalty(archive(observed=1), 2020, 2)[0] == 0


def test_current_future_and_expired_labels_cannot_change_fit():
    past = archive()
    expected = rf.fit_penalty(past, 2020, 2)
    extra = archive(400, observed=2)
    for season, week in [(2020, 2), (2021, 1), (2014, 1)]:
        changed = extra.assign(season=season, week=week, game_id=extra.game_id+'extra')
        assert rf.fit_penalty(pd.concat([past, changed]), 2020, 2) == expected
    assert expected[1]['training_max_week'] == 1


def test_explicit_warmup_and_upper_bound(monkeypatch):
    theta, fit = rf.fit_penalty(archive(50), 2020, 2)
    assert theta == 0 and fit['warmup'] and fit['boundary'] == 'warmup'
    monkeypatch.setattr(rf, 'MAX_THETA', .01)
    theta, fit = rf.fit_penalty(archive(), 2020, 2)
    assert theta == .01 and fit['boundary'] == 'upper'


def test_duplicate_and_invalid_calibration_data_fail():
    x = archive(); x.loc[1, 'game_id'] = x.loc[0, 'game_id']
    with pytest.raises(ValueError, match='Duplicate'):
        rf.fit_penalty(x, 2020, 2)
    x = archive(); x.loc[0, 'mass1'] = -.1
    with pytest.raises(ValueError, match='sufficient'):
        rf.fit_penalty(x, 2020, 2)
    x = archive(); x.loc[0, 'rare_count'] = 3
    with pytest.raises(ValueError, match='sufficient'):
        rf.fit_penalty(x, 2020, 2)


def test_all_derived_markets_come_from_the_same_joint():
    q = rf.transform(joint(), 1.8); m = j.marginals(q)
    assert m['total'] @ j.TOTAL_SUPPORT == pytest.approx(m['home'] @ j.SCORE_SUPPORT + m['away'] @ j.SCORE_SUPPORT)
    assert m['margin'] @ j.MOV_SUPPORT == pytest.approx(m['home'] @ j.SCORE_SUPPORT - m['away'] @ j.SCORE_SUPPORT)
    for line in [0, 3, 3.5, 7, 7.5]:
        win, push, lose = j.event_probabilities(m['margin'], j.MOV_SUPPORT, line)
        assert win + push + lose == pytest.approx(1)
        assert win == pytest.approx(q[(j.HH-j.AA) > line].sum())


def test_original_experiment_output_cannot_be_overwritten():
    with pytest.raises(ValueError, match='protected'):
        rf.run(d.BASE)


def test_export_validation_rejects_probability_and_row_mismatches(tmp_path):
    p = joint(); m = j.marginals(p)
    g = pd.DataFrame([dict(arm=rf.ARM, game_id='game', p_home=p[j.HH > j.AA].sum(),
                           p_tie=np.trace(p), spread_line=3.,
                           cover_win=p[j.HH-j.AA > 3].sum(), cover_push=p[j.HH-j.AA == 3].sum())])
    audits = pd.DataFrame([dict(season=2020, week=2, training_max_season=2020, training_max_week=1)])
    path = tmp_path / 'marginals.npz'
    data = dict(game_ids=np.array(['game']), margin_support=j.MOV_SUPPORT,
                **{rf.ARM+'__'+k: v[None, :] for k, v in m.items()})
    np.savez(path, **data)
    assert all(rf.verify_exports(g, audits, path).values())
    wrong = dict(data); wrong[rf.ARM+'__margin'] = np.roll(data[rf.ARM+'__margin'], 5, axis=1)
    np.savez(path, **wrong)
    with pytest.raises(AssertionError, match='probabilities disagree'):
        rf.verify_exports(g, audits, path)
    np.savez(path, **data)
    with pytest.raises(AssertionError, match='populations'):
        rf.verify_exports(g.assign(game_id='other'), audits, path)
    with pytest.raises(AssertionError, match='future'):
        rf.verify_exports(g, audits.assign(training_max_week=2), path)
