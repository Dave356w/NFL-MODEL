"""Operating characteristics of the favorite-penalty forward verdict (as written vs the replacement).

    python research/forward_monitoring.py      # writes research/forward_monitoring_results/

Each simulated path resamples whole historical week blocks of the penalty's per-game log-loss gain
(2017-20 and 2021-25 in research/favorite_penalty_results/inputs.csv, recentred to the true gain),
so the gain keeps its skew and its week clustering. At each January checkpoint the verdict uses the
week-cluster SE estimated from the sampled weeks, as grade_ledger.fp_verdict does.

Three methods:
* unconditional: every week is resampled. Outcome-free with respect to the forward ledger.
* given week 5: the first week is fixed to the 13 graded native v1.16 week-5 rows, which are in the
  registered verdict sample and were seen before the addenda. It uses no later forward outcome.
* Gaussian, known SE: the method of the first 2026-10-15 addendum, kept for comparison.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import t as tdist

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nfl_model as m  # noqa: E402

INPUTS = ROOT/'research/favorite_penalty_results/inputs.csv'
OUT = ROOT/'research/forward_monitoring_results'
# (graded native v1.16 shadow games, season-week clusters) at each January checkpoint: 13 week-5 rows
# + 193 in 2026 weeks 6-18 (14 weeks), then 272 games over 18 weeks a season; ties (~0.5%) ignored.
LOOKS = {'Jan 2027': (206, 14), 'Jan 2028': (478, 32), 'Jan 2029': (750, 50), 'Jan 2030': (1022, 68),
         'Jan 2031': (1294, 86)}
TRUE_GAINS = (-0.002, 0.0, 0.001, 0.0023, 0.004)
DELTA = 0.002          # the smallest gain the penalty was adopted for (2021-25 +0.0023, 2017-20 +0.0040)
ALPHA = 0.025          # two-sided 97.5% bounds
MIN_N = 200
SEED = 20261015
REPS = 200000
CHUNK = 20000
METHODS = ('week-block bootstrap, estimated SE', 'week-block bootstrap given the 13 week-5 rows', 'Gaussian, known SE')


def _gains(d):
    y = d['home won'].to_numpy(float); p = d.model_wp.to_numpy(float)
    fp = m.favorite_penalized_wp(p, d.q.to_numpy(float), m.FAVORITE_PENALTY)
    return -(y*np.log(p)+(1-y)*np.log(1-p))+(y*np.log(fp)+(1-y)*np.log(1-fp))


def _graded(path):
    d = pd.read_csv(path)
    d = d[d['home won'].isin([0., 1.]) & d.q.notna() & d.model_wp.notna()].reset_index(drop=True)
    d['gain'] = _gains(d)
    d['week_key'] = d.season.astype(str)+'_'+d.week.astype(str)
    return d


def historical_gains(path=INPUTS):
    """Per-game v1.16 minus penalized log loss on the 2017-20 and 2021-25 bases."""
    d = _graded(path)
    return d[d.basis.str.startswith(('2017-20', '2021-25'))].reset_index(drop=True)


def week5_block(path=INPUTS):
    """(gain sum, games) of the graded native v1.16 week-5 rows: the first block of the verdict sample."""
    d = _graded(path)
    d = d[d.basis.str.startswith('native')]
    return float(d.gain.sum()), float(len(d))


def per_game_sd(path=INPUTS):
    """Per-game SD of the gain, its shape and the week-cluster design effect on each basis."""
    hist = historical_gains(path)
    rows = {}
    for b, g in hist.groupby('basis'):
        n = len(g); sd = g.gain.std(ddof=1)
        c = g.groupby('week_key').gain.sum()
        cse = np.sqrt(len(c))*c.std(ddof=1)/n
        rows[b] = {'n': n, 'mean': float(g.gain.mean()), 'sd': float(sd), 'deff': float((cse/(sd/np.sqrt(n)))**2)}
    sd = float(hist.gain.std(ddof=1)); deff = max(1., max(r['deff'] for r in rows.values()))
    weeks = hist.groupby('week_key').gain.agg(['sum', 'size'])
    top = hist.loc[hist.gain.idxmax()]
    return {'bases': rows, 'sd': sd, 'deff': deff, 'sd_effective': sd*np.sqrt(deff),
            'skew': float(hist.gain.skew()), 'excess_kurtosis': float(hist.gain.kurt()),
            'week_blocks': int(len(weeks)), 'games_per_week': float(weeks['size'].mean()),
            'max_game_gain': {'game_id': str(top.game_id), 'gain': float(top.gain)},
            'max_week_sum': float(weeks['sum'].max())}


def week_blocks(path=INPUTS):
    """Per-week sums and game counts of the gain, recentred so the per-game mean is 0."""
    hist = historical_gains(path)
    b = hist.assign(c=hist.gain-hist.gain.mean()).groupby('week_key').c.agg(['sum', 'size'])
    return b['sum'].to_numpy(float), b['size'].to_numpy(float)


def t_critical(clusters, alpha=ALPHA):
    """Two-sided t critical value with G - 1 degrees of freedom (G = season-week clusters)."""
    return tdist.ppf(1-alpha/2, np.asarray(clusters, float)-1)


def as_written(est, se, n, clusters):
    """FAVORITE_PENALTY.md as first written: from 200 games, falsified if the gain is not positive,
    supported if the 95% interval lies above zero. Returns (supported, falsified) boolean arrays."""
    ok = np.asarray(n) >= MIN_N
    sup = ok & (est-1.96*se > 0)
    return sup, ok & ~sup & (est <= 0)


def three_way(critical):
    """Supported if the lower bound > 0; falsified if the upper bound < DELTA (the data exclude the gain
    the penalty was adopted for); otherwise unresolved."""
    def rule(est, se, n, clusters):
        c = critical(clusters)
        ok = (np.asarray(n) >= MIN_N) & (np.asarray(clusters) >= 2) & np.isfinite(se)
        sup = ok & (est-c*se > 0)
        return sup, ok & ~sup & (est+c*se < DELTA)
    return rule


RULES = {'as written': as_written,
         'three-way, z 2.24 (first addendum)': three_way(lambda g: np.full(np.shape(g), 2.24)),
         'three-way, t(G-1) 97.5% (adopted)': three_way(t_critical)}


def verdict(rule, est, se, n, clusters):
    """One verdict as text: 'none' below 200 games, else supported / falsified / unresolved."""
    if n < MIN_N:
        return 'none'
    sup, fal = (bool(np.asarray(v).item()) for v in rule(np.float64(est), np.float64(se), n, clusters))
    return 'supported' if sup else 'falsified' if fal else 'unresolved'


def _first_counts(rule, est, se, n, looks):
    """Paths with a supported / falsified verdict by each look; the first decisive verdict stands."""
    first = np.zeros(est.shape[0], int)
    out = []
    for j, (_, g) in enumerate(looks.values()):
        sup, fal = rule(est[:, j], se[:, j], n[:, j], np.full(est.shape[0], g))
        new = first == 0
        first[new & sup] = 1; first[new & fal] = 2
        out.append(((first == 1).sum(), (first == 2).sum()))
    return np.array(out, float)


def _chunked(draw, rule, looks, reps, seed):
    counts = np.zeros((len(looks), 2))
    sizes = [CHUNK]*(reps//CHUNK)+([reps % CHUNK] if reps % CHUNK else [])
    for k, ss in zip(sizes, np.random.SeedSequence(seed).spawn(len(sizes))):
        counts += _first_counts(rule, *draw(np.random.default_rng(ss), k), looks)
    return {name: {'supported': c[0]/reps, 'falsified': c[1]/reps} for name, c in zip(looks, counts)}


def simulate(rule, gain, blocks, looks=LOOKS, reps=REPS, seed=SEED, fixed=None):
    """Resample whole historical weeks; the SE is the week-cluster SE of the sampled weeks. `fixed`,
    a (gain sum, games) pair, is an observed first week that every path shares (not recentred)."""
    s0, n0 = blocks
    weeks = np.array([g for _, g in looks.values()])

    def draw(rng, k):
        idx = rng.integers(0, len(s0), size=(k, weeks.max()-(fixed is not None)))
        s, n = s0[idx]+n0[idx]*gain, n0[idx]
        if fixed is not None:
            s = np.hstack([np.full((k, 1), fixed[0]), s]); n = np.hstack([np.full((k, 1), fixed[1]), n])
        cs, cs2, cn = np.cumsum(s, 1)[:, weeks-1], np.cumsum(s*s, 1)[:, weeks-1], np.cumsum(n, 1)[:, weeks-1]
        var = np.maximum(cs2-cs*cs/weeks, 0)/(weeks-1)
        return cs/cn, np.sqrt(weeks)*np.sqrt(var)/cn, cn
    return _chunked(draw, rule, looks, reps, seed)


def simulate_gaussian(rule, gain, sd, looks=LOOKS, reps=REPS, seed=SEED):
    """The first addendum's method: Brownian cumulative sums with the SE known (sd/sqrt(n))."""
    ns = np.array([n for n, _ in looks.values()])
    inc = np.diff(np.concatenate([[0], ns]))

    def draw(rng, k):
        est = np.cumsum(rng.normal(gain*inc, sd*np.sqrt(inc), size=(k, len(ns))), axis=1)/ns
        return est, np.broadcast_to(sd/np.sqrt(ns), est.shape), np.broadcast_to(ns, est.shape)
    return _chunked(draw, rule, looks, reps, seed)


def table(t, method):
    """Markdown rows (first look -> all five) for the documents, rounded from the CSV values."""
    first, last = list(LOOKS)[0], list(LOOKS)[-1]
    x = t[t.method == method].set_index(['rule', 'true_gain', 'look'])

    def cell(rule, gain, col):
        a, b = x.loc[(rule, gain, first), col], x.loc[(rule, gain, last), col]
        return f'{100*a:.1f}% → {100*b:.1f}%'
    rows = ['| Rule | False falsification (+0.0023) | False support (0) | Falsifies a true 0 | Supports a true +0.004 |',
            '|---|---:|---:|---:|---:|']
    for rule in RULES:
        rows.append(f'| {rule} | {cell(rule, .0023, "falsified")} | {cell(rule, 0., "supported")} | '
                    f'{cell(rule, 0., "falsified")} | {cell(rule, .004, "supported")} |')
    return '\n'.join(rows)


def run(out=OUT, reps=REPS):
    s = per_game_sd()
    blocks, w5 = week_blocks(), week5_block()
    rows = []
    for method in METHODS:
        for name, rule in RULES.items():
            for gtrue in TRUE_GAINS:
                if method == METHODS[2]:
                    res = simulate_gaussian(rule, gtrue, s['sd_effective'], reps=reps)
                else:
                    res = simulate(rule, gtrue, blocks, reps=reps, fixed=w5 if method == METHODS[1] else None)
                for look, r in res.items():
                    rows.append({'method': method, 'rule': name, 'true_gain': gtrue, 'look': look,
                                 'n': LOOKS[look][0], 'weeks': LOOKS[look][1], **r})
    t = pd.DataFrame(rows)
    out.mkdir(parents=True, exist_ok=True)
    t.to_csv(out/'operating_characteristics.csv', index=False, float_format='%.5f')
    (out/'tables.md').write_text('\n\n'.join(f'### {mth}\n\n{table(t, mth)}' for mth in METHODS)+'\n')
    crit = {k: round(float(t_critical(g)), 4) for k, (_, g) in LOOKS.items()}
    (out/'results.json').write_text(json.dumps({'sd': s, 'week5_block': {'gain_sum': w5[0], 'games': w5[1]},
                                                'looks': LOOKS, 't_critical': crit, 'delta': DELTA, 'alpha': ALPHA,
                                                'reps': reps, 'chunk': CHUNK, 'seed': SEED}, indent=2)+'\n')
    return s, t


if __name__ == '__main__':
    s, t = run()
    print(json.dumps(s, indent=1))
    print((OUT/'tables.md').read_text())
