"""Test 21: v1.11 QB projection (depth chart + questionable-starter blend) vs v1.10.

    python research/qb_depth_chart.py [CACHE_DIR]     # ~25 min warm

Four arms on the production families (point-margin families, production grid and
nested selection), scored on the same priced held-out games 2023-2025:
  v1.10            start-history QB rule; a Questionable starter counts as starting
  + blend only     start-history rule; a Questionable starter is a 50/50 blend with the next QB
  + depth only     timestamped depth chart (2025 on, >= 24h before kickoff); no blend
  v1.11            depth chart and blend (production)
QB_QUESTIONABLE_START = 1 reproduces v1.10's projection exactly, and depth=None
switches the chart off. The depth chart exists only from 2025, so it changes 2025
rows only; the blend changes rows in every season. Also reported: how often each
arm's projected passer is the team's actual starter (first dropback).
"""
import numpy as np
import pandas as pd

from _common import DHEAD, HEAD, OUTER, diff_row, cache_dir_from_argv, grid, load_inputs, log, m, outer, row, score

FAMS = tuple(m.FEATURE_FAMILIES)
ARMS = (('v1.10', False, 1.), ('+ blend only', False, .5), ('+ depth only', True, 1.), ('v1.11', True, .5))


def avail_for(inp, use_depth, q):
    a, old = inp['a'], m.QB_QUESTIONABLE_START
    m.QB_QUESTIONABLE_START = q
    try:
        return m.availability_table(inp['targets'], inp['qb'], a['snaps'], a['inj'], a['rost'],
                                    depth=a.get('depth') if use_depth else None)
    finally:
        m.QB_QUESTIONABLE_START = old


def pick_accuracy(av, qb):
    """Share of team-games whose single projected passer (no blend) started; by season."""
    st = qb[qb.starter.astype(bool)][['season', 'week', 'team', 'name']].rename(columns={'name': 'actual'})
    d = av.merge(st, on=['season', 'week', 'team'], how='inner')
    d = d[d.qb_expected.notna() & (d.qb_expected != m.NO_QB_LABEL)]
    first = d.qb_expected.str.split(' \\(Q\\) / ').str[0]
    d['hit'] = first == d.actual
    return d.groupby('season').hit.agg(['size', 'mean'])


def main():
    inp = load_inputs(cache_dir_from_argv())
    res, avs = {}, {}
    for name, use_depth, q in ARMS:
        avs[name] = avail_for(inp, use_depth, q)
        oof = grid(inp, avs[name], FAMS, name)
        o, picks = outer(oof, FAMS)
        res[name] = score(o); res[name]['frame'] = o
        log(f'{name}: picks {picks}')
    print('\n## Test 21: v1.11 QB projection, held-out ' + '-'.join(map(str, (OUTER[0], OUTER[-1]))) + '\n' + HEAD)
    for k, s in res.items(): print(row(k, s))
    print('\n' + DHEAD)
    for k in res:
        if k != 'v1.10': print(diff_row(f'{k} vs v1.10', res[k], res['v1.10']))
    base, new = res['v1.10'], res['v1.11']
    seasons = base['frame'].season.to_numpy()
    print('\n| Held-out season | Games | ROI difference | Log-loss gain |\n|---|---:|---:|---:|')
    for yr in OUTER:
        k = seasons == yr
        sub = lambda s: {'units_vec': s['units_vec'][k], 'll_vec': s['ll_vec'][k]}
        print(diff_row(str(yr), sub(new), sub(base)).replace(f'| {yr} |', f'| {yr} | {int(k.sum())} |'))
    # Games whose QB input changed at all.
    b, n = avs['v1.10'], avs['v1.11']
    key = ['season', 'week', 'team']
    j = b[key + ['qb_delta']].merge(n[key + ['qb_delta']], on=key, suffixes=('_b', '_n'))
    j = j[(j.qb_delta_b - j.qb_delta_n).abs() > 1e-9]
    chg = set(zip(j.season, j.week, j.team))
    f = base['frame']
    k = np.array([(y, w, h) in chg or (y, w, a) in chg for y, w, h, a in zip(f.season, f.week, f.home, f.away)])
    if k.any():
        sub = lambda s: {'units_vec': s['units_vec'][k], 'll_vec': s['ll_vec'][k]}
        print(diff_row(f'games with a changed QB input (n={int(k.sum())})', sub(new), sub(base)))
    print('\n| Arm | Season | Team-games | Projected passer started |\n|---|---|---:|---:|')
    for name in ('v1.10', '+ depth only'):
        acc = pick_accuracy(avs[name], inp['qb'])
        for yr, r in acc.iterrows():
            if yr >= 2023: print(f'| {name} | {yr} | {int(r["size"])} | {100 * r["mean"]:.1f}% |')
    log('done')


if __name__ == '__main__':
    main()
