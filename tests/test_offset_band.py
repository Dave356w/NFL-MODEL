"""Reporting-only model-probability range on the board (never written to snapshots)."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import nfl_model as m


@pytest.fixture(autouse=True)
def legacy_v118_identity():
    """This conditional-offset band predates the two-stage market baseline."""
    with m.revision_identity('boxscore-composite-v1.18',
                             dict(m.LEGACY_PRODUCT_RECIPE, favorite_penalty=m.FAVORITE_PENALTY)):
        yield


def fixture(n=300, seed=3):
    rng = np.random.default_rng(seed)
    names = m.feature_names(m.PRODUCT_RECIPE['family'])+list(m.PRODUCT_CONTEXT_NAMES)
    f = pd.DataFrame(rng.normal(0, .3, (n, len(names))), columns=names)
    f['site'] = 1.; f['season'] = 2025; f['week'] = np.arange(n) % 18+1; f['ready'] = True
    f['q'] = rng.uniform(.25, .75, n); f['home won'] = (rng.random(n) < f.q).astype(float)
    return f


def test_band_brackets_the_forecast_and_widens_with_the_level():
    f = fixture(); fit = m.fit_composite(f, m.PRODUCT_RECIPE, 2026, 1); rows = f.iloc[:5]
    se, lo, hi = m.offset_band(f, fit, rows)
    p = m.apply_fit(rows, fit)
    assert np.all(se > 0) and np.all(lo < p) and np.all(p < hi)
    _, lo99, hi99 = m.offset_band(f, fit, rows, level=.99)
    assert np.all(lo99 < lo) and np.all(hi99 > hi)


def test_band_refuses_rows_the_fit_did_not_use_and_non_offset_fits():
    f = fixture(); fit = m.fit_composite(f, m.PRODUCT_RECIPE, 2026, 1)
    assert np.isnan(np.r_[m.offset_band(f.iloc[:-10], fit, f.iloc[:3])]).all()
    baseline = m.fit_composite(f, m.PRODUCT_RECIPE, 2026, 1, baseline=True)
    assert np.isnan(np.r_[m.offset_band(f, baseline, f.iloc[:3])]).all()
    missing = f.iloc[:2].assign(q=np.nan)
    assert np.isnan(m.offset_band(f, fit, missing)[1]).all()


def test_real_week_matches_an_independent_calculation():
    root = Path(__file__).resolve().parents[1]
    f = pd.read_csv(root/'research/shrinkage_results/frozen_training_features.csv.gz')
    train = f[m.before(f, 2026, 5)]
    fit = m.fit_composite(train, m.LEGACY_PRODUCT_RECIPE, 2026, 5)
    rows = f[f.game_id.isin(['2026_05_SF_SEA', '2026_05_BAL_ATL'])].sort_values('game_id')
    se, lo, hi = m.offset_band(train, fit, rows)
    # Values from a separate scratch implementation of the same penalized-Hessian formula.
    assert se == pytest.approx([.295, .918], abs=1e-3)
    assert lo[1] == pytest.approx(.773, abs=1e-3) and hi[1] == pytest.approx(.986, abs=1e-3)
