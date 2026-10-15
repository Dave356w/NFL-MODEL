"""Operating characteristics of the favorite-penalty forward verdict (current vs proposed rule).

    python research/forward_monitoring.py      # writes research/forward_monitoring_results/

Outcome-free with respect to the forward ledger: it uses only the historical per-game spread of the
penalty's log-loss gain (research/favorite_penalty_results/inputs.csv) and the season checkpoints.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nfl_model as m  # noqa: E402

INPUTS = ROOT/'research/favorite_penalty_results/inputs.csv'
OUT = ROOT/'research/forward_monitoring_results'
# Cumulative graded native v1.16 shadow games at each January checkpoint (13 week-5 rows + 193 in
# 2026 weeks 6-18, then 272 a season; ties about 0.5% are ignored).
LOOKS = {'Jan 2027': 206, 'Jan 2028': 478, 'Jan 2029': 750, 'Jan 2030': 1022, 'Jan 2031': 1294}
TRUE_GAINS = (-0.002, 0.0, 0.001, 0.0023, 0.004)
DELTA = 0.002          # the smallest gain the penalty was adopted for (2021-25 +0.0023, 2017-20 +0.0040)
MIN_N = 200
SEED = 20261015
REPS = 20000


def per_game_sd(path=INPUTS):
    """Per-game SD of v1.16 minus penalized log loss on the historical bases, inflated by the
    week-cluster design effect."""
    d = pd.read_csv(path)
    d = d[d['home won'].isin([0., 1.]) & d.q.notna() & d.model_wp.notna()].reset_index(drop=True)
    y = d['home won'].to_numpy(float); p = d.model_wp.to_numpy(float)
    fp = m.favorite_penalized_wp(p, d.q.to_numpy(float), m.FAVORITE_PENALTY)
    gain = -(y*np.log(p)+(1-y)*np.log(1-p))+(y*np.log(fp)+(1-y)*np.log(1-fp))
    d['gain'] = gain
    hist = d[d.basis.str.startswith(('2017-20', '2021-25'))]
    rows = {}
    for b, g in hist.groupby('basis'):
        n = len(g); sd = g.gain.std(ddof=1)
        c = g.groupby(g.season.astype(str)+'_'+g.week.astype(str)).gain.sum()
        cse = np.sqrt(len(c))*c.std(ddof=1)/n
        rows[b] = {'n': n, 'mean': float(g.gain.mean()), 'sd': float(sd), 'deff': float((cse/(sd/np.sqrt(n)))**2)}
    sd = float(hist.gain.std(ddof=1)); deff = max(1., max(r['deff'] for r in rows.values()))
    return {'bases': rows, 'sd': sd, 'deff': deff, 'sd_effective': sd*np.sqrt(deff)}


def verdict_current(est, se, n):
    """FAVORITE_PENALTY.md as written: from 200 games, falsified if the gain is not positive,
    supported if the 95% interval lies above zero."""
    if n < MIN_N: return 'none'
    if est - 1.96*se > 0: return 'supported'
    if est <= 0: return 'falsified'
    return 'unresolved'


def verdict_proposed(est, se, n, z=1.96, delta=DELTA):
    """Three-way: supported if the lower bound > 0; falsified if the upper bound < delta (the data
    exclude the gain the penalty was adopted for); otherwise unresolved."""
    if n < MIN_N: return 'none'
    if est - z*se > 0: return 'supported'
    if est + z*se < delta: return 'falsified'
    return 'unresolved'


def simulate(rule, gain, sd, looks=LOOKS, reps=REPS, seed=SEED, **kw):
    """Cumulative means at each look (Brownian increments); the first decisive verdict stands."""
    rng = np.random.default_rng(seed)
    ns = np.array(list(looks.values()))
    inc = np.diff(np.concatenate([[0], ns]))
    sums = np.cumsum(rng.normal(gain*inc, sd*np.sqrt(inc), size=(reps, len(ns))), axis=1)
    est = sums/ns; se = sd/np.sqrt(ns)
    first = np.full(reps, 'unresolved', dtype=object)
    done = np.zeros(reps, bool)
    by_look = {}
    for j, (name, n) in enumerate(looks.items()):
        v = np.array([rule(e, se[j], n, **kw) for e in est[:, j]], dtype=object)
        newly = ~done & np.isin(v, ['supported', 'falsified'])
        first[newly] = v[newly]; done |= newly
        by_look[name] = {'supported': float((first == 'supported').mean()), 'falsified': float((first == 'falsified').mean())}
    return by_look


def run(out=OUT):
    s = per_game_sd()
    sd = s['sd_effective']
    rules = {'current (FAVORITE_PENALTY.md)': (verdict_current, {}),
             'proposed z=1.96, delta=+0.002': (verdict_proposed, {'z': 1.96}),
             'proposed z=2.24, delta=+0.002': (verdict_proposed, {'z': 2.24})}
    rows = []
    for name, (rule, kw) in rules.items():
        for gtrue in TRUE_GAINS:
            res = simulate(rule, gtrue, sd, **kw)
            for look, r in res.items():
                rows.append({'rule': name, 'true_gain': gtrue, 'look': look, 'n': LOOKS[look], **r})
    t = pd.DataFrame(rows)
    out.mkdir(parents=True, exist_ok=True)
    t.to_csv(out/'operating_characteristics.csv', index=False, float_format='%.4f')
    (out/'results.json').write_text(json.dumps({'sd': s, 'looks': LOOKS, 'delta': DELTA, 'reps': REPS, 'seed': SEED}, indent=2)+'\n')
    return s, t


if __name__ == '__main__':
    s, t = run()
    print(json.dumps(s, indent=1))
    pd.set_option('display.width', 200)
    print(t.pivot_table(index=['rule', 'true_gain'], columns='look', values=['supported', 'falsified']).round(3).to_string())
