"""Context feature semantics and chronological penalty selection."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import context_battle as c


def fixture():
    d = pd.DataFrame({'ho': [2., .8, -.7], 'ad': [1.5, -.9, -2.],
                      'ao': [-.2, -.4, .3], 'hd': [.3, .6, -.8]})
    d['product'] = d.ho*d.ad-d.ao*d.hd
    f = pd.DataFrame({'q': [.7, .5, .2], 'week': [1, 8, 17]})
    return d, f


def test_all_contexts_reverse_when_teams_swap():
    d, f = fixture()
    a, extras = c.context_features(d, f)
    swapped = d.rename(columns={'ho':'ao', 'ao':'ho', 'ad':'hd', 'hd':'ad'}).copy()
    swapped['product'] = -d['product']
    sf = f.copy(); sf['q'] = 1-f.q
    b, _ = c.context_features(swapped, sf)
    cols = sorted(set(sum(extras.values(), [])))
    assert np.allclose(a[cols], -b[cols])


def test_thresholds_and_single_extreme_have_distinct_support():
    d, f = fixture()
    a, _ = c.context_features(d, f)
    assert a.loc[0, 'h1_pp'] == pytest.approx(.5)
    assert a.loc[0, 'h2_pp'] == 0
    # Only defense is beyond 1 SD in row 2: both-extreme hinge is zero,
    # but the one-extreme construction captures the interaction.
    assert a.loc[2, 'h1_nn'] == 0
    assert a.loc[2, 'one_extreme'] > 0


def test_market_and_early_context_controls():
    d, f = fixture(); a, _ = c.context_features(d, f)
    assert a.loc[1, 'market_context'] == 0
    assert a.loc[0, 'early_context'] == d.loc[0, 'product']
    assert abs(a.loc[2, 'early_context']) < abs(d.loc[2, 'product'])
    assert a.loc[0, 'market_context'] == pytest.approx(d.loc[0, 'product']*.4)


def test_transform_does_not_use_labels_or_other_rows():
    d, f = fixture(); a, _ = c.context_features(d, f)
    f['home won'] = [1, 0, 1]
    d.loc[2, :] = 1000; f.loc[2, 'q'] = .99
    b, _ = c.context_features(d, f)
    assert np.allclose(a.iloc[:2], b.iloc[:2])


def test_penalty_selection_excludes_ties():
    prior = pd.DataFrame({'home won': [1., 0., .5]})
    for r in c.q.PENS:
        prior[f'hinge_1__r{r:g}'] = [.6, .4, .5]
    prior['hinge_1__r1'] = [.9, .1, .000001]
    assert c.select(prior, 'hinge_1') == 'hinge_1__r1'
