"""POST-HOC diagnostics, written after the primary results were seen (not part of any selection).

    python research/av/posthoc.py [CACHE_DIR]     # needs walkforward.py caches; ~2 min

1. What the dynamic team residual restores over its own rAV roster prior (D1/D2 vs the B2 base each
   held-out season's D recipe was built on), and what box-score team rates restore (C1 vs B2).
2. The primary D grid's selected shrinkage was its strongest value (gamma = 12) every season. Here
   gamma in {24, 48, 96} on the same selected bases, still chosen per season on earlier seasons only.
   Labelled post-hoc: the grid extension was chosen after seeing that edge.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from _common import OUTER, cache_dir_from_argv, m  # noqa: E402
import evaluate as ev  # noqa: E402
import models as md  # noqa: E402
from walkforward import select  # noqa: E402

OUT = HERE / 'output'


def main():
    cache = Path(cache_dir_from_argv())
    held = pd.read_csv(OUT / 'heldout_predictions.csv')
    oof = pd.read_parquet(cache / 'av' / 'oof_ac.parquet')[['game_id', 'season', 'home won']]
    bd = pd.read_parquet(cache / 'av' / 'bd_predictions.parquet')
    sched = pd.concat([m.load_schedule(y) for y in range(2019, 2026)])
    f = bd[['game_id']].merge(sched[['game_id', 'season', 'week', 'home_team', 'away_team', 'result', 'home won']]
                              .rename(columns={'home_team': 'home', 'away_team': 'away'}), on='game_id', how='left')
    f = f.sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
    bd = f[['game_id']].merge(bd, on='game_id', how='left')
    sel = json.loads((OUT / 'selection.json').read_text())
    clusters = (held.season * 100 + held.week).to_numpy()
    L = ['## Post-hoc diagnostics (after the primary results; not used for any selection)', '']
    # 1. restoration
    base = held[['game_id', 'season']].copy(); base['wp__D1 base'] = np.nan
    for yr in OUTER:
        k = sel['D1'][str(yr)].split('_l')[0][3:]  # D1_<base>_l.._g..
        te = base.season == yr
        base.loc[te, 'wp__D1 base'] = held.loc[te, 'game_id'].map(bd.set_index('game_id')['p__' + k]).to_numpy()
    h = held.assign(**{'wp__D1 base': base['wp__D1 base'].to_numpy()})
    h['mu__D1 base'] = h['mu__D1']  # margin columns are unused by the paired table
    g = {n: ev.per_game(h, n) for n in ('D1 base', 'D1', 'D2', 'B2', 'C1', 'A')}
    L += ['| Comparison (same 815 held-out games) | ROI difference (pts) | Log-loss gain |', '|---|---:|---:|']
    for a, b, lab in (('D1 base', 'D1', 'D1 vs its own B2 roster prior (residual restores)'),
                      ('D1 base', 'D2', 'D2 vs the same roster prior'),
                      ('B2', 'C1', 'C1 vs B2 (box-score team rates + v1.15 QB term restore)')):
        p = ev.paired(g[a], g[b], clusters)
        L.append(f"| {lab} | {ev.fmt_pts(p['units'])} | {ev.fmt_ll(p['ll'])} |")
    # 2. stronger shrinkage
    o = oof.merge(bd, on='game_id', how='left')
    cols = []
    for k in sorted({sel['D1'][str(y)].split('_l')[0][3:] for y in OUTER}):
        mu = bd['mu__' + k]
        for gam in (24., 48., 96.):
            ah, aa = md.team_residual_states(f, mu, .9, gam)
            mud = mu + ah - aa
            c = f'p__Dx_{k}_l0.9_g{gam:g}'
            p = md.wp(mud, md.walk_forward_sigma(f, mud))
            o[c] = o.game_id.map(pd.Series(p.to_numpy(), index=f.game_id)); cols.append(c)
    wpcol, picks = select(o, cols + [c for c in o if c.startswith('p__D1_')])
    h2 = held.assign(**{'wp__D1 wide gamma': held.game_id.map(pd.Series(wpcol.to_numpy(), index=o.game_id)).to_numpy(),
                        'mu__D1 wide gamma': held['mu__D1']})
    g2 = ev.per_game(h2, 'D1 wide gamma')
    p = ev.paired(g['A'], g2, clusters)
    u = g2['units'][np.isfinite(g2['units'])]
    L += ['', f"D1 with gamma ∈ {{1, 4, 12, 24, 48, 96}} (λ = .9 for the added values), selected per season on earlier seasons: "
          f"picks {picks}; held-out log loss {g2['ll'].mean():.4f}, ROI {100 * u.mean():+.1f}% ± {100 * u.std(ddof=1) / np.sqrt(len(u)):.1f}; "
          f"vs A: ROI {ev.fmt_pts(p['units'])}, log-loss gain {ev.fmt_ll(p['ll'])}."]
    (OUT / 'posthoc.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
