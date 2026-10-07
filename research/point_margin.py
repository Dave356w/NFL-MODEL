"""Test 16: does a decayed point margin earn a place in the composite?

    python research/point_margin.py [CACHE_DIR]     # ~10 min warm

Tests 14-15 found that the market leans on point margin, which the box-score rates
leave out (red-zone finishing, special teams, return and defensive TDs, kicking).
Here each production family gains one input, d__mov: the home-minus-away decayed
average point margin from earlier games only, using the same weighting as the stat
profiles (team half-life h, OFFSEASON_RETENTION per season, MAX_HISTORY_SEASONS,
PRIOR_EQUIVALENT_GAMES pseudo-games at zero). Both variants run the production
grid; each held-out season's recipe is chosen on earlier seasons only; scored game
by game against production on the same 811 priced games.
"""
import numpy as np

from _common import (FULL, DHEAD, HEAD, LAST, availability, cache_dir_from_argv, diff_row, load_inputs, log, m,
                     outer, row, score)
from market_info import lagged_mov

MOV = tuple(f + '_mov' for f in FULL)
_base_names = m.feature_names


def feature_names(family):
    return _base_names(family[:-4]) + ['d__mov'] if family.endswith('_mov') else _base_names(family)


def main():
    m.feature_names = feature_names
    inp = load_inputs(cache_dir_from_argv())
    sched, avail = inp['sched'], availability(inp)
    feats = {}
    for h in m.TEAM_HALF_LIVES:
        f = m.lagged_features(inp['box'], sched, h, avail)
        mov = lagged_mov(sched, h)
        f['d__mov'] = [mov.get((a, y, w), np.nan) for a, y, w in zip(f.home, f.season, f.week)]
        f['d__mov'] -= [mov.get((a, y, w), np.nan) for a, y, w in zip(f.away, f.season, f.week)]
        feats[h] = f
    log('features built')
    m.FEATURE_FAMILIES = FULL + MOV
    oof = m.attach_moneylines(m.walk_forward_grid(feats, LAST), sched)
    prod, pp = outer(oof, FULL); var, pv = outer(oof, MOV)
    log(f'production picks {pp}'); log(f'margin picks {pv}')
    a, b = score(prod), score(var)
    print('\n### Test 16: decayed point margin\n' + HEAD)
    print(row('production', a)); print(row('+ decayed point margin', b))
    print('\n' + DHEAD); print(diff_row('+ margin vs production', b, a))
    print('\n| Weeks | Games | ROI difference | Log-loss gain |\n|---|---:|---:|---:|')
    wk = prod.week.to_numpy()
    for lo, hi, name in ((1, 4, '1–4'), (5, 9, '5–9'), (10, 13, '10–13'), (14, 17, '14–17'), (18, 18, '18')):
        k = (wk >= lo) & (wk <= hi)
        du = (b['units_vec'] - a['units_vec']).to_numpy()[k]; du = du[np.isfinite(du)]
        dl = (a['ll_vec'] - b['ll_vec'])[k]
        print(f'| {name} | {k.sum()} | {100 * du.mean():+.2f} pts ± {100 * du.std(ddof=1) / np.sqrt(len(du)):.2f} | '
              f'{dl.mean():+.4f} ± {dl.std(ddof=1) / np.sqrt(len(dl)):.4f} |')
    last = pv[max(pv)]; fam, rest = last.split('_h'); h, r = rest.split('_r')
    recipe = {'family': fam, 'half_life': float(h), 'ridge': float(r)}
    f = feats[recipe['half_life']]
    fit = m.fit_composite(f[m.before(f, LAST + 1, 1)], recipe, LAST + 1, 1)
    coef = dict(zip(fit['names'], fit['beta']))
    top = sorted(((abs(v), k, v) for k, v in coef.items() if k != 'site'), reverse=True)[:5]
    print(f'\nFit through {LAST} ({last}), coefficient per scaled unit: point margin {coef["d__mov"]:+.3f}; largest: '
          + ', '.join(f'{k.split("__")[-1]} {v:+.3f}' for _, k, v in top))
    log('done')


if __name__ == '__main__':
    main()
