import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import feature_importance as fi
import residual_trends as t


@pytest.fixture(scope='module')
def pack():
    p = pd.read_csv(t.OOS_PACK)
    return p, p[(p.season == 2015) & p.week.isin([1, 2])]


def test_zeroed_input_gets_no_weight_and_leaves_the_rest_fitted(pack):
    p, games = pack
    base = fi.weekly(p, games)
    arm = fi.weekly(p, games, zero=['d__avail__qb_delta'])
    assert (arm['c__d__avail__qb_delta'] == 0).all()
    assert not np.allclose(base['c__d__avail__qb_delta'], 0)
    assert not np.allclose(arm.p16, base.p16)  # the refit without the input is a different model
    # Contributions are additive on the market log-odds (v1.16 before the penalty).
    q = pd.Series(t.m.market_ml_wp(games)).to_numpy()
    s = base[[c for c in base if c.startswith('c__')]].sum(axis=1).to_numpy()
    assert np.allclose(expit(logit(q)+s), base.p16, atol=1e-12)


def test_attribution_sign_follows_the_outcome():
    names = fi.FEATURES
    row = {f'c__{f}': 0. for f in names}
    d = pd.DataFrame([{**row, 'game_id': 'g', 'season': 2020, 'week': 5, 'home': 'H', 'away': 'A', 'q': .5, 'p': np.nan,
                       'total_line': 45., 'cluster': '2020_5', 'y': y} for y in (1., 0.)])
    d['c__d__avail__qb_delta'] = -.4  # pushes toward the away team
    d['c__pass_product'] = .2           # pushes toward the home team
    a = fi.attribute(d)
    home_won, away_won = a.iloc[0], a.iloc[1]
    assert home_won['eff__d__avail__qb_delta'] < 0 < home_won['eff__pass_product']
    assert away_won['eff__d__avail__qb_delta'] > 0 > away_won['eff__pass_product']
    assert np.isclose(home_won['grp__QB projection'], -.4) and home_won['eff__site'] == 0


def test_interaction_scan_matches_the_single_cell_test():
    rng = np.random.default_rng(3)
    n = 1500
    d = pd.DataFrame({c: rng.normal(size=n) for c in fi.INPUTS + ['market_logit']})
    p = expit(rng.normal(scale=.7, size=n))
    a, b = fi.INPUTS[0], fi.INPUTS[1]
    d['y'] = (rng.random(n) < expit(logit(p)+.6*d[a]*d[b])).astype(float)
    d['p'] = p; d['total_line'] = 45.; d['cluster'] = [f'w{i % 40}' for i in range(n)]
    s = fi.interaction_scan(d, 'x')
    row = s[(s.context == 'all') & (s.a == a) & (s.b == b)].iloc[0]
    prod = (d[a]-d[a].mean())*(d[b]-d[b].mean())
    ref = t.cell(d.assign(prod=prod), 'prod')
    assert np.isclose(row.z, ref['z']) and row.z > 4
    quiet = s[(s.context == 'all') & ~((s.a == a) & (s.b == b))]
    assert (quiet.z.abs() < 4).mean() > .99


def test_interaction_selection_and_verdicts():
    disc = pd.DataFrame({'context': 'all', 'a': list('abcd'), 'b': 'z', 'z': [3.5, -3.1, 2.9, 4.0]})
    c = fi.select_interactions(disc)
    assert c.a.tolist() == ['d', 'a', 'b']
    other = disc.assign(z=[1.0, 2.9, 0., -5.])
    out, bar = fi.test_interactions(c, other, 'confirm')
    v = dict(zip(out.a, out.verdict_confirm))
    assert np.isclose(bar, fi.norm.ppf(1-.05/3))
    assert v == {'d': 'reversed', 'a': 'direction holds', 'b': 'reversed'}  # b: -3.1 then +2.9 is the opposite direction
    out, _ = fi.test_interactions(c, disc.assign(z=[3., -3., 0., 3.]), 'replicate')
    assert set(out.verdict_replicate) == {'replicated'}


def test_reading_and_clustered_mean():
    assert fi.reading(2.) == 'helps' and fi.reading(-2.) == 'hurts' and fi.reading(1.99) == 'unresolved'
    assert fi.reading(np.nan) == 'n/a'
    mu, se = fi.cmean([1., 1., -1., -1.], ['a', 'a', 'b', 'b'])
    assert mu == 0 and np.isclose(se, np.sqrt(8)/4)
