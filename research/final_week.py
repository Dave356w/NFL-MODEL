"""Test 30: playoff-race inputs in the final week only.

    python research/final_week.py [CACHE_DIR]     # ~12 min warm

Plan and decision rule: research/README.md, Tests 29-31 (committed before any result).
v1.12 families plus three inputs: home minus away of Test 17's eliminated, clinched and
top-seed flags (research/season_context.py, earlier weeks' results only), each multiplied
by an indicator for the season's final regular-season week (17 in 2019-20, 18 from 2021),
so they are zero in every other week.
"""
import numpy as np

from _common import LAST, OUTER, availability, cache_dir_from_argv, load_inputs, log, m, null_and_favorite, outer, \
    primary_row, report_family, same_rows, score
from season_context import STATUS, team_status

LEVEL = 1 - .05 / 3
FW = tuple(f'd__fw_{s}' for s in STATUS)


def add_final_week(f, status, sched):
    """Home-minus-away status flags in each season's final regular-season week, 0 elsewhere."""
    last = sched.groupby('season').week.max()
    f = f.copy(); final = (f.week.to_numpy() == f.season.map(last).to_numpy())
    for s, col in zip(STATUS, FW):
        h = np.array([status.get((t, y, w), {}).get(s, 0.) for t, y, w in zip(f.home, f.season, f.week)])
        a = np.array([status.get((t, y, w), {}).get(s, 0.) for t, y, w in zip(f.away, f.season, f.week)])
        f[col] = np.where(final, h - a, 0.)
    return f


def final_week_rows(held, sched):
    last = sched.groupby('season').week.max()
    return (held.week.to_numpy() == held.season.map(last).to_numpy())


def main():
    inp = load_inputs(cache_dir_from_argv())
    sched = inp['sched']; status = team_status(sched)
    avail = availability(inp)
    prod = {h: m.lagged_features(inp['box'], sched, h, avail) for h in m.TEAM_HALF_LIVES}
    var = {h: add_final_week(f, status, sched) for h, f in prod.items()}
    f8 = var[8.]
    nz = {c: int((f8.loc[f8.season.between(OUTER[0], LAST), c] != 0).sum()) for c in FW}
    log(f'features built; held-out games with a nonzero final-week input: {nz}')
    fams = tuple(m.FEATURE_FAMILIES); names = m.feature_names
    held, picks, sc, oofs = {}, {}, {}, {}
    for name, feats, fn in (('production (v1.12)', prod, names),
                            ('Test 30: final-week status', var, lambda fam: names(fam) + list(FW))):
        m.feature_names = fn
        try: oofs[name] = m.attach_moneylines(m.walk_forward_grid(feats, LAST), sched)
        finally: m.feature_names = names
        held[name], picks[name] = outer(oofs[name], fams); sc[name] = score(held[name])
        log(f'{name} picks {picks[name]}')
    same_rows(*held.values())
    p, v = sc['production (v1.12)'], sc['Test 30: final-week status']
    print('\n### Test 30 result\n\n| Arm | LL gain vs production [98.33% CI] | ± SE | Verdict |\n|---|---:|---:|---|')
    primary_row('Test 30: final-week status', p['ll_vec'] - v['ll_vec'], LEVEL,
                lambda mean, lo, hi: 'supported' if lo > 0 else 'harmful' if hi < 0 else 'unresolved')
    report_family(held['production (v1.12)'], sc, LEVEL)
    fw = final_week_rows(held['production (v1.12)'], sched)
    d = p['ll_vec'] - v['ll_vec']
    print(f'\nFinal-week games (n={fw.sum()}): LL gain {d[fw].mean():+.4f} ± {d[fw].std(ddof=1) / np.sqrt(fw.sum()):.4f}; '
          f'weeks before the final week (n={(~fw).sum()}): {d[~fw].mean():+.4f} ± {d[~fw].std(ddof=1) / np.sqrt((~fw).sum()):.4f}')
    print('\n| Final-week rows | Bets | Units | ROI ± SE | Same-row favorite | Market null |\n|---|---:|---:|---:|---:|---:|')
    for name in held:
        hf = held[name][fw]; s = score(hf); null, fav = null_and_favorite(hf)
        print(f"| {name} | {s['bets']} | {s['units']:+.2f} | {100 * s['roi']:+.1f}% ± {100 * s['roi_se']:.1f} | "
              f"{100 * fav:+.1f}% | {100 * null:+.1f}% |")
    # Development only: 2021-22 final weeks with each arm's 2023 pick (selected on 2021-22).
    dev = []
    for name in held:
        o = oofs[name]; o = o[o.season.isin((2021, 2022))]
        o = o[final_week_rows(o, sched)].assign(model_wp=lambda x, c='p__' + picks[name][OUTER[0]]: x[c])
        dev.append(score(o.sort_values('game_id').reset_index(drop=True)))
    dd = dev[0]['ll_vec'] - dev[1]['ll_vec']
    print(f'\nDevelopment only, 2021–22 final weeks (n={len(dd)}, recipes selected on those seasons): '
          f'LL gain {dd.mean():+.4f} ± {dd.std(ddof=1) / np.sqrt(len(dd)):.4f}')
    log('done')


if __name__ == '__main__':
    main()
