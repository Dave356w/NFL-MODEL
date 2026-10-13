"""Favorite-confidence penalty for v1.16 (reporting only); see FAVORITE_PENALTY.md.

`--freeze` copies the inputs (committed out-of-sample predictions, the bot's rebuilt
history and native ledger) into the results folder; the default run scores only the
frozen copies, so results reproduce after data/ is rebuilt. No production writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
import nfl_model as m

OUT = ROOT/'research/favorite_penalty_results'
REVISION = 'boxscore-composite-v1.16'
LEVEL, REPS, SEED = .95, 8000, 20261013
COLS = ['basis', 'game_id', 'season', 'week', 'home won', 'model_wp', 'q', 'home_moneyline', 'away_moneyline']
BASES = ['2017-20 out of sample (exposed)', '2021-25 rebuilt (exposed; lambda chosen here)',
         '2026 weeks 1-5 walk-forward (unseen)', 'native v1.16 ledger (unseen)']


def freeze(out=OUT):
    if m.REVISION != REVISION:  # from v1.18 the rebuilt history holds penalized forecasts
        raise ValueError('Inputs were frozen under v1.16; refreezing now would read v1.18 forecasts as v1.16')
    out.mkdir(parents=True, exist_ok=True)
    o = pd.read_csv(ROOT/'research/out_of_sample_results/predictions.csv').rename(columns={'production': 'model_wp'})
    o['basis'] = BASES[0]
    r = pd.read_csv(ROOT/'data/latest/retro_ledger.csv').rename(columns={'market_ml_wp': 'q'})
    r = r[r['home won'].notna()].copy()
    r['basis'] = np.where(r.season <= 2025, BASES[1], BASES[2])
    r = r[r.season >= 2021]
    f = pd.read_csv(ROOT/'data/forward_ledger.csv')
    f = f[(f.revision == REVISION) & f['home won'].notna()].sort_values('generated_utc').drop_duplicates(['experiment', 'game_id'])
    f = f.rename(columns={'market_wp': 'q'}).assign(basis=BASES[3])
    rows = pd.concat([x[COLS] for x in (o, r, f)], ignore_index=True)
    rows.to_csv(out/'inputs.csv', index=False)
    return rows


def cluster_interval(v, groups):
    a = pd.DataFrame({'v': v, 'g': groups}).groupby('g').v.agg(['sum', 'count'])
    if len(a) < 2: return [None, None]  # one week: no cluster interval
    i = np.random.default_rng(SEED).integers(0, len(a), (REPS, len(a)))
    d = a['sum'].to_numpy()[i].sum(1)/a['count'].to_numpy()[i].sum(1)
    return np.quantile(d, [(1-LEVEL)/2, (1+LEVEL)/2]).tolist()


def score(x):
    x = x[x['home won'].isin([0., 1.]) & np.isfinite(x.q) & np.isfinite(x.model_wp)].copy()
    y = x['home won'].to_numpy(float)
    x['fp'] = m.favorite_penalized_wp(x.model_wp, x.q)
    ll = lambda p: -(y*np.log(np.clip(p, 1e-12, 1)) + (1-y)*np.log(np.clip(1-p, 1e-12, 1)))
    lm, lf, lq = ll(x.model_wp.to_numpy()), ll(x.fp.to_numpy()), ll(x.q.to_numpy())
    gain = lm-lf; groups = (x.season.astype(str)+'_'+x.week.astype(str)).to_numpy()
    e = pd.Series(gain-gain.mean()).groupby(groups).sum().to_numpy(); G = len(e)
    se = float(np.sqrt((e*e).sum()*G/(G-1))/len(gain)) if G > 1 else None
    bets_m, bets_f = m.flat_bets(x, 'model_wp'), m.flat_bets(x.assign(fp_side=x.fp), 'fp_side')
    return {'n': int(len(x)), 'changed': int((~np.isclose(x.fp, x.model_wp)).sum()),
            'll_model': float(lm.mean()), 'll_penalized': float(lf.mean()), 'll_market': float(lq.mean()),
            'gain': float(gain.mean()), 'gain_cluster_se': se, 'gain_interval': cluster_interval(gain, groups),
            'bets_identical': bool((bets_m.side == bets_f.side).all()),
            'units_model': float(bets_m.units.sum()), 'units_penalized': float(bets_f.units.sum())}


def run(out=OUT):
    rows = pd.read_csv(out/'inputs.csv')
    res = {b: score(rows[rows.basis == b]) for b in BASES}
    check = all(res[b]['gain'] > 0 and res[b]['bets_identical'] for b in BASES[:2])
    nat = res[BASES[3]]
    if nat['n'] < 100: forward = f'no verdict ({nat["n"]} of 100 native games)'
    elif nat['n'] < 200: forward = 'reported, verdict at 200 native games'
    elif nat['gain'] <= 0: forward = 'falsified'
    else: forward = 'supported' if (nat['gain_interval'][0] or 0) > 0 else 'unresolved'
    info = {'protocol': 'research/FAVORITE_PENALTY.md', 'lambda': m.FAVORITE_PENALTY, 'revision': REVISION,
            'implementation_check': 'passed' if check else 'failed', 'forward': forward, 'results': res}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    src = [Path(__file__).resolve(), ROOT/'research/FAVORITE_PENALTY.md', ROOT/'nfl_model.py', out/'inputs.csv']
    (out/'provenance.json').write_text(json.dumps(
        {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in src}, indent=2)+'\n')
    lines = ['# Favorite-confidence penalty for v1.16: results', '',
             f"Protocol `research/FAVORITE_PENALTY.md`; lambda {m.FAVORITE_PENALTY:g}. Implementation check: "
             f"**{info['implementation_check']}**. Forward verdict: **{forward}**.", '',
             '| Basis | n | Changed | LL v1.16 | LL penalized | LL market | Gain vs v1.16 | 95% interval | Bets identical | Units |',
             '|---|---:|---:|---:|---:|---:|---:|---|---|---:|']
    for b in BASES:
        r = res[b]; lo, hi = r['gain_interval']
        iv = f"[{lo:+.5f}, {hi:+.5f}]" if lo is not None else 'one week: none'
        se = f" ± {r['gain_cluster_se']:.5f}" if r['gain_cluster_se'] is not None else ''
        lines.append(f"| {b} | {r['n']} | {r['changed']} | {r['ll_model']:.5f} | {r['ll_penalized']:.5f} | {r['ll_market']:.5f} | "
                     f"{r['gain']:+.5f}{se} | {iv} | {r['bets_identical']} | "
                     f"{r['units_model']:+.2f} |")
    lines += ['', 'Gain is v1.16 log loss minus penalized log loss (positive = penalty better), with week-cluster SE and '
              'bootstrap interval. Units are flat 1u on the model side over games with a winner (ties excluded), '
              'identical for both arms by construction.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))
    return info


if __name__ == '__main__':
    a = argparse.ArgumentParser(); a.add_argument('--freeze', action='store_true')
    if a.parse_args().freeze: freeze()
    run()
