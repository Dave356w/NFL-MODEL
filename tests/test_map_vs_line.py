import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research'))
import fixed_bands as fb  # noqa: E402
import map_vs_line as mvl  # noqa: E402

RULE = dict(cuts=[3., 7., 10.], magnitudes=[3., 5., 7., 13.])


def games(model, line, result):
    n = len(model)
    d = pd.DataFrame(dict(game_id=[f'g{i}' for i in range(n)], season=2020, week=1,
                          spread_line=line, result=result, model_spread=model))
    return mvl.frame(d, [RULE]*n, [RULE]*n)


def test_through_uses_each_rows_own_rule_and_missing_rule_is_nan():
    other = dict(RULE, magnitudes=[2., 4., 8., 14.])
    out = mvl.through([4., -4., 4.], [RULE, other, None])
    assert out[0] == 5. and out[1] == -4. and np.isnan(out[2])


def test_same_band_gives_identical_sides_and_zero_contrast():
    # Model 4.4 and line 4.5 share the 3-7 band: both map to 5 and take the favorite.
    d = games([4.4, -5.9], [4.5, -6.5], [10., 3.])
    rows, contrasts = mvl.summarize(d, 'test', 'x')
    c = next(k for k in contrasts if k['contrast'] == 'D model - D line-only')
    assert c['differ'] == 0 and c['units'] == 0.


def test_different_band_flips_the_side_and_is_counted():
    # Line 6.5 maps to 5 (underdog); model 7.5 maps to 7 (favorite). Home wins by 10: favorite covers.
    d = games([7.5, 4.4], [6.5, 4.5], [10., 10.])
    rows, contrasts = mvl.summarize(d, 'test', 'x')
    c = next(k for k in contrasts if k['contrast'] == 'D model - D line-only')
    assert c['differ'] == 1 and np.isclose(c['units'], 1/1.1 + 1.)
    assert c['first_arm_record_on_differing'] == '1-0-0'


def test_pickem_line_skips_line_only_but_not_the_model():
    d = games([4.], [0.], [7.])
    sides = {a: fb.pick(d[a].to_numpy(float), d.spread_line.to_numpy(float))[0] for a in ('D model', 'D line-only')}
    assert sides == {'D model': 1., 'D line-only': 0.}


def test_rows_without_a_rule_are_dropped_not_scored():
    d = pd.DataFrame(dict(game_id=['a'], season=2015, week=1, spread_line=[3.5], result=[7.], model_spread=[4.]))
    assert mvl.frame(d, [None], [RULE]).empty


def test_verdict_needs_sign_and_two_standard_errors():
    assert mvl.verdict(dict(units=50., z=2.1)) == 'supported'
    assert mvl.verdict(dict(units=-50., z=-2.1)) == 'contradicted'
    assert mvl.verdict(dict(units=43.7, z=1.39)) == 'unresolved'
