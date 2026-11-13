"""v1.19: v1.18 fitted on ten core terms, with the v1.16 shadow on its own fit."""
import numpy as np
import pandas as pd
import pytest
import nfl_model as m
from test_product_production import fixture


def test_identity_and_terms():
    assert m.REVISION == 'boxscore-composite-v1.24' and m.OUTPUT_NAME == 'nfl_boxscore_output_v1_24'
    assert m.PRODUCT_RECIPE == dict(m.V118_RECIPE, terms=list(m.CORE_TERMS))
    main, ctx = m.model_terms(m.PRODUCT_RECIPE)
    assert len(main)+len(ctx) == 10 and main[0] == 'site' and set(main+ctx) == set(m.CORE_TERMS)
    assert ctx == ['pass_product', 'pass_1sd_pn', 'pass_1sd_np']
    full_main, full_ctx = m.model_terms(m.V118_RECIPE)
    assert len(full_main)+len(full_ctx) == 29 and main == [n for n in full_main if n in m.CORE_TERMS]
    assert m.config_signature()[1]['production_recipe']['terms'] == list(m.CORE_TERMS)


def test_bad_term_lists_are_refused():
    with pytest.raises(ValueError, match='not in its family'):
        m.model_terms(dict(m.V118_RECIPE, terms=['site', 'd__no_such_term']))
    with pytest.raises(ValueError, match="keep 'site'"):
        m.model_terms(dict(m.V118_RECIPE, terms=['pass_product']))


def test_fit_uses_only_the_terms_and_equals_zeroed_v118():
    train, test = fixture()
    fit = m.fit_composite(train, m.PRODUCT_RECIPE, 2023, 1)
    assert fit['names'] == sum(m.model_terms(m.PRODUCT_RECIPE), [])
    dropped = [n for n in sum(m.model_terms(m.V118_RECIPE), []) if n not in m.CORE_TERMS]
    zeroed = m.fit_composite(train.assign(**{c: 0. for c in dropped}), m.V118_RECIPE, 2023, 1)
    z = dict(zip(zeroed['names'], zeroed['beta']))
    assert np.allclose(fit['beta'], [z[n] for n in fit['names']], rtol=0, atol=1e-10)
    assert all(abs(z[c]) < 1e-12 for c in dropped)
    # Dropped inputs cannot move a v1.19 forecast; a kept one does.
    p = m.apply_fit(test, fit)
    assert np.array_equal(p, m.apply_fit(test.assign(**{c: 1e4 for c in dropped}), fit))
    assert not np.allclose(p, m.apply_fit(test.assign(d__avail__qb_delta=test.d__avail__qb_delta+5.), fit))
    se, lo, hi = m.offset_band(train, fit, test)
    assert np.all(np.isfinite(se)) and np.all(lo <= p+1e-12) and np.all(p <= hi+1e-12)


def test_shadow_gets_its_own_v116_fit():
    train, test = fixture()
    fit19 = m.fit_composite(train, m.PRODUCT_RECIPE, 2023, 1)
    fit18 = m.fit_composite(train, m.V118_RECIPE, 2023, 1)
    s19 = m.shadow_fit(train, fit19, 2023, 1)
    assert s19['recipe'] == m.SHADOW_RECIPE and len(s19['names']) == 29
    assert m.shadow_fit(train, fit18, 2023, 1) is fit18                              # v1.18 path unchanged
    v116 = m.apply_fit(test, m.fit_composite(train, m.LEGACY_PRODUCT_RECIPE, 2023, 1))
    assert np.allclose(m.apply_fit(test, s19, raw=True), v116, rtol=0, atol=1e-15)
    assert not np.allclose(m.apply_fit(test, fit19, raw=True), v116)              # the production raw is not v1.16
    with pytest.raises(ValueError, match='term-restricted'):
        m.record_shadow(test.assign(model_wp_v116=.5), fit19, None, 2023)


def test_recipe_keys_never_collide():
    assert m.recipe_key(m.PRODUCT_RECIPE) != m.recipe_key(m.V118_RECIPE)
    other = dict(m.PRODUCT_RECIPE, terms=list(m.CORE_TERMS[:-1]))
    assert m.recipe_key(other) != m.recipe_key(m.PRODUCT_RECIPE)
