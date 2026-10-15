"""Lock vs close basis on native forward rows (outcome-free diagnostic).

    python research/lock_close_basis.py      # reads data/forward_ledger.csv, writes research/lock_close_results/

Forward snapshots lock a median ~22 h before kickoff at the snapshot moneyline; historical tests use
nflverse's moneyline after the game (its close). This measures, on rows whose close is known, how far
the no-vig probability moved between lock and close, how the model's departure from the market
differs under each anchor, and how often a close-anchored forecast would pick a different side.
It never reads outcomes for the measurement and never writes data/.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nfl_model as m  # noqa: E402

LEDGER = ROOT/'data/forward_ledger.csv'
OUT = ROOT/'research/lock_close_results'


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1-1e-6)
    return np.log(p/(1-p))


def basis(led):
    """One row per snapshot with a known close: lock q, close q, the departure under each anchor and
    the close-anchored probability p_close = expit(logit p - logit q_lock + logit q_close)."""
    d = led.copy()
    d['q_lock'] = m.market_ml_wp(d)
    d['q_close'] = pd.to_numeric(d.close_q, errors='coerce')
    d = d[np.isfinite(d.q_lock) & np.isfinite(d.q_close) & d.model_wp.notna()].copy()
    p = d.model_wp.astype(float).to_numpy()
    d['move_pp'] = 100*(d.q_close-d.q_lock)
    d['dep_lock'] = logit(p)-logit(d.q_lock)
    d['dep_close'] = logit(p)-logit(d.q_close)
    d['p_close'] = 1/(1+np.exp(-(d.dep_lock+logit(d.q_close))))
    d['fav_changed'] = (d.q_lock > .5) != (d.q_close > .5)
    d['side_changed'] = (p > .5) != (d.p_close > .5)
    return d


def summarize(d):
    out = {}
    for rev, g in d.groupby('revision'):
        out[rev] = {'rows': int(len(g)), 'mean_abs_move_pp': float(g.move_pp.abs().mean()),
                    'max_abs_move_pp': float(g.move_pp.abs().max()),
                    'mean_abs_dep_lock': float(g.dep_lock.abs().mean()), 'mean_abs_dep_close': float(g.dep_close.abs().mean()),
                    'corr_dep_lock_close': float(np.corrcoef(g.dep_lock, g.dep_close)[0, 1]) if len(g) > 2 else None,
                    'favorite_changed': int(g.fav_changed.sum()), 'close_anchored_side_changes': int(g.side_changed.sum())}
    return out


def run(out=OUT):
    d = basis(pd.read_csv(LEDGER))
    s = summarize(d)
    out.mkdir(parents=True, exist_ok=True)
    (out/'results.json').write_text(json.dumps(s, indent=2)+'\n')
    d[['revision', 'game_id', 'lead_hours', 'model_wp', 'q_lock', 'q_close', 'move_pp', 'dep_lock', 'dep_close',
       'p_close', 'fav_changed', 'side_changed']].to_csv(out/'rows.csv', index=False, float_format='%.6g')
    return d, s


if __name__ == '__main__':
    _, s = run()
    print(json.dumps(s, indent=2))
