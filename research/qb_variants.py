"""Test 3: QB-term variants, each against production on the same games.

    python research/qb_variants.py [CACHE_DIR]     # ~30 min warm

  prior 75 / prior 300   QB_PRIOR_DROPBACKS (production 150): shrinkage of a QB's
                         net yards per dropback toward the league backup level
  half-life 4 / 16       QB_HALF_LIFE (production 8 team games): recency of QB history
  + backup-start flag    extra availability column qb_change = 1 when the projected
                         QB is not the usual starter (2 when no rostered QB has history)
Five variants are tried, so treat a single ~2 SE difference as possibly chance.
"""
import numpy as np

from _common import (FULL, DHEAD, HEAD, availability, cache_dir_from_argv, diff_row, grid, load_inputs, log,
                     m, outer, row, score)


def with_qb_change(avail):
    out = avail.copy()
    changed = out.qb_expected.notna() & (out.qb_expected != out.qb_usual)
    out['qb_change'] = np.where(out.qb_expected == m.NO_QB_LABEL, 2., changed.astype(float))
    return out


def main():
    inp = load_inputs(cache_dir_from_argv())
    base = availability(inp)
    res = {'production': score(outer(grid(inp, base, FULL, 'production'), FULL)[0])}
    for name, attr, val in (('prior 75', 'QB_PRIOR_DROPBACKS', 75.), ('prior 300', 'QB_PRIOR_DROPBACKS', 300.),
                            ('QB half-life 4', 'QB_HALF_LIFE', 4.), ('QB half-life 16', 'QB_HALF_LIFE', 16.)):
        old = getattr(m, attr); setattr(m, attr, val)
        try:
            res[name] = score(outer(grid(inp, availability(inp), FULL, name), FULL)[0])
        finally:
            setattr(m, attr, old)
    fams = ('rates_core_avail_cs_qbc', 'rates_core_adj_avail_cs_qbc')
    for fam, src in zip(fams, FULL):
        m.FAMILIES[fam] = m.RATES_CORE; m.AVAIL_FAMILIES[fam] = m.AVAIL_FAMILIES[src]
        m.AVAIL_FAMILY_COLS[fam] = m.AVAIL_COLS_CS + ('qb_change',)
    m.ALL_AVAIL_COLS = m.ALL_AVAIL_COLS + ('qb_change',)
    res['+ backup-start flag'] = score(outer(grid(inp, with_qb_change(base), fams, '+ backup-start flag'), fams)[0])
    print('\n## Test 3\n' + HEAD)
    for k, s in res.items(): print(row(k, s))
    print('\n' + DHEAD)
    for k in res:
        if k != 'production': print(diff_row(f'{k} vs production', res[k], res['production']))
    log('done')


if __name__ == '__main__':
    main()
