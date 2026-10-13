"""Selection-adjusted benchmark: arm discovery, paired units, and the two best-arm nulls."""
import json
import numpy as np
import pandas as pd
import pytest
from scipy.special import expit, logit
from research import selection_benchmark as s


def test_units_are_paired_against_the_same_row_favorite():
    q = np.array([.58, .58]); y = np.array([0., 1.])
    p = np.array([[.40, .70], [.40, .70]])  # first arm takes the +130 underdog, second the -150 favorite
    du, dl = s.differentials(y, q, p, s.payouts([-150, -150]), s.payouts([130, 130]))
    assert du[:, 0] == pytest.approx([1.3+1, -1-100/150])
    assert du[:, 1] == pytest.approx([0, 0])
    assert dl[0, 0] > 0 > dl[1, 0]


def study(rows, **arms):
    return pd.DataFrame({'game_id': [f'g{i}' for i in range(len(rows['q']))], **rows, **arms})


def test_market_copies_reproductions_and_non_forecasts_are_dropped(tmp_path):
    rng = np.random.default_rng(1); n = 80
    q = rng.uniform(.3, .7, n)
    rows = {'season': [2023]*n, 'week': np.arange(n) % 18+1, 'home won': (rng.random(n) < q).astype(float),
            'home_moneyline': [-120]*n, 'away_moneyline': [100]*n, 'q': q}
    x, y, z = rng.uniform(.2, .8, (3, n))
    study(rows, x=x, copy_q=q, market=x[::-1], x_p05=y, bad=x+1, few=np.r_[[.6]*n]).to_csv(tmp_path/'a.csv', index=False)
    study(rows, x=x+1e-12, y=y).to_csv(tmp_path/'b.csv', index=False)
    study({**rows, 'season': [2022]+[2023]*(n-1)}, z=z).to_csv(tmp_path/'c.csv', index=False)
    base, arms = s.load_arms(tmp_path, {'a': 'a.csv', 'b': 'b.csv', 'c': 'c.csv'})
    assert list(arms.columns) == ['a:x', 'b:y']  # b:x reproduces a:x; c:z lacks a game in the window
    assert len(base) == n and arms.index.equals(base.index)


def market(seed, n=400):
    rng = np.random.default_rng(seed)
    q = rng.uniform(.3, .7, n); vig = 1.045  # proportional hold: both sides share the same expectation
    weeks = np.repeat(np.arange(n//20), 20).astype(str)
    return rng, q, (rng.random(n) < q).astype(float), 1/(vig*q)-1, 1/(vig*(1-q))-1, weeks


def test_planted_oracle_is_detected():
    rng, q, y, ph, pa, weeks = market(7)
    noise = expit(logit(q)[:, None]+rng.normal(0, .3, (len(q), 10)))
    p = np.column_stack([np.where(y == 1, .9, .1), noise])
    names = ['oracle']+[f'n{i}' for i in range(10)]
    info, units, _ = s.benchmark(y, q, p, ph, pa, weeks, names, named={'oracle': 'oracle'}, draws=400, boot=400)
    assert info['units_vs_favorite']['best_arm'] == 'oracle' and units[0] > 100
    assert info['units_vs_favorite']['market_null_p'] < .01 and info['units_vs_favorite']['reality_check_p'] < .01
    assert info['log_loss_gain']['market_null_p'] < .01


def test_search_luck_is_not_called_skill():
    rng, q, y, ph, pa, weeks = market(11)
    p = expit(logit(q)[:, None]+rng.normal(0, .3, (len(q), 30)))
    names = [f'n{i}' for i in range(30)]
    info, units, _ = s.benchmark(y, q, p, ph, pa, weeks, names, named={'a': 'n0', 'b': 'n1'}, draws=400, boot=400)
    u = info['units_vs_favorite']
    assert u['null_best_median_units'] > 0  # the best of many market-correct arms looks profitable
    assert u['market_null_p'] > .05 and u['reality_check_p'] > .05
    for arm in info['named'].values():
        assert arm['market_null_p_against_best_arm'] >= arm['unadjusted_market_null_p']


def test_named_arm_lost_to_deduplication_is_an_error():
    _, q, y, ph, pa, weeks = market(3, 40)
    with pytest.raises(ValueError, match='Named arms'):
        s.benchmark(y, q, np.c_[q+.01], ph, pa, weeks, ['other'], named={'v1.16': 'gone'}, draws=5, boot=5)


@pytest.mark.parametrize('target', ['data', 'public', 'data/latest'])
def test_research_cannot_write_production_outputs(target):
    with pytest.raises(ValueError, match='production outputs'):
        s.run(s.ROOT/target, draws=1, boot=1)


def test_committed_results_agree_with_the_committed_arms():
    info = json.loads((s.OUT/'results.json').read_text())
    arms = pd.read_csv(s.OUT/'arms.csv')
    assert info['arms'] == len(arms) and arms.arm.is_unique
    best = arms.loc[arms.units_vs_favorite.idxmax()]
    assert info['units_vs_favorite']['best_arm'] == best.arm
    assert info['units_vs_favorite']['best_units'] == pytest.approx(best.units_vs_favorite)
    for k, arm in s.NAMED.items():
        row = arms.set_index('arm').loc[arm]
        assert info['named'][k]['units_vs_favorite'] == pytest.approx(row.units_vs_favorite)
        assert info['named'][k]['ll_gain'] == pytest.approx(row.ll_gain)
    assert 'not forward evidence' in info['basis']
