"""H14 conditional cover, soft side tie rule, push exclusion, cutoff and verdict gate."""
import numpy as np
import pandas as pd
import pytest

from research import h14_soft_vs_hard_ats as h
from research import soft_band_distributions as sb


@pytest.fixture(scope='module')
def fit():
    games = pd.read_csv(sb.INPUT)
    return sb.fit_prior(sb.clean(games)[lambda g: g.season < 2026], 2026)


def test_conditional_excludes_push_mass():
    assert h.conditional(np.array([.45, .10, .45])) == .5
    assert np.isclose(h.conditional(np.array([.48, .10, .42])), .48 / .90)


def test_hard_and_soft_agree_at_an_anchor_and_differ_near_a_cutoff(fit):
    r = h.row('g', 8, 1.0, 1.5, 3., np.nan, fit)  # below the first anchor: one band only
    assert np.isclose(r['hard_p'], r['soft_p'])
    r = h.row('g', 8, 3.5, 3.5, 4., np.nan, fit)  # just past the 3 cutoff
    assert r['hard_p'] > .5 > r['soft_p'] and r['hard_side'] == 1. and r['soft_side'] == -1.


def test_push_is_unscored_and_outcome_orientation(fit):
    assert np.isnan(h.row('g', 8, 3.5, 3., 4., 3., fit)['y'])
    assert h.row('g', 8, 3.5, 3., 4., 7., fit)['y'] == 1.
    assert h.row('g', 8, 3.5, 3., 4., -7., fit)['y'] == 0.


def lock(lock_at, revision=h.REVISION, season=2026, recovered=False):
    return dict(revision=revision, season=season, week=8, game_id='2026_08_CAR_GB', lock_at_utc=lock_at,
                raw_spread=3.5, market_spread=3.5, fixed_band_spread=4., recovered_after_kickoff=recovered)


def test_forward_rows_apply_cutoff_revision_and_season(fit):
    rows = h.forward_rows([lock('2026-10-28T23:00:00Z'), lock('2026-10-29T23:15:00Z'),
                           lock('2026-10-29T23:15:00Z', revision='other'),
                           lock('2027-10-29T23:15:00Z', season=2027)], {'2026_08_CAR_GB': 7.}, fit)
    assert len(rows) == 1 and rows.y.iloc[0] == 1.
    s = h.score(rows)
    assert s['n'] == 1 and s['gain'] < 0  # home covered; hard leaned home, soft away
    p = h.paired(rows)
    assert p['n'] == 1 and p['hard']['wins'] == 1 and p['soft']['losses'] == 1


def test_verdict_gate():
    assert h.verdict(dict(n=99, gain=.1, se=.01)).startswith('interim')
    assert h.verdict(dict(n=99, gain=-.01, se=.01), season_over=True) == 'falsified'
    assert h.verdict(dict(n=100, gain=0., se=.01)) == 'falsified'
    assert h.verdict(dict(n=100, gain=.03, se=.01)).startswith('supported')
    assert h.verdict(dict(n=100, gain=.01, se=.01)) == 'unresolved'
