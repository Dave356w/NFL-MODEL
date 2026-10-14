import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import simplification as s
import nfl_model as m
from test_product_production import fixture


def test_fixed_arms_remove_only_the_promised_terms():
    assert {a: len(c) for a, c in s.ARMS.items()} == {'no_peaks': 2, 'no_peaks_site': 3, 'no_pass_tails': 4}
    assert s.ARMS['no_peaks_site'] == s.ARMS['no_peaks']+['site']
    assert 'pass_product' not in s.ARMS['no_pass_tails']
    assert set(s.ARMS['no_pass_tails']) == set(m.PRODUCT_CONTEXT_NAMES)-{'pass_product'}


@pytest.mark.parametrize('arm', s.ARMS)
def test_removed_terms_have_zero_weight_and_no_evaluation_effect(arm):
    train, test = fixture(); cols = s.ARMS[arm]
    zeroed = train.assign(**{c: 0. for c in cols})
    fit = m.fit_composite(zeroed, m.PRODUCT_RECIPE, 2023, 1)
    assert all(fit['beta'][fit['names'].index(c)] == 0. for c in cols)
    p = m.apply_fit(test.assign(**{c: 0. for c in cols}), fit)
    changed = test.assign(**{c: 10000. for c in cols})
    np.testing.assert_array_equal(p, m.apply_fit(changed, fit))
    assert train[cols].abs().sum().sum() > 0       # original input was not mutated
    with pytest.raises(ValueError, match='current/future'):
        m.fit_composite(pd.concat([zeroed, test]), m.PRODUCT_RECIPE, 2023, 1)


def test_comparison_rejects_different_coverage_before_scoring():
    p = pd.DataFrame({'game_id': ['a', 'b']})
    with pytest.raises(ValueError, match='coverage'):
        s.compare(p, p.iloc[:1], 'test', 'test')
    with pytest.raises(ValueError, match='Duplicate'):
        s.compare(pd.concat([p, p]), p, 'test', 'test')


def test_research_refuses_data_destination():
    with pytest.raises(ValueError, match='cannot write'):
        s.run(s.ROOT/'data/unsafe')
