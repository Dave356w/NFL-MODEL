"""Test 1: does the availability layer earn its place? Test 2: absence-window length.

    python research/availability_ablation.py [CACHE_DIR]     # ~15 min warm

Test 1 variants (absence window 4): A no availability, B QB term only, C full layer
(production). Test 2: production families with AVAIL_WINDOW 8 and 16 vs 4.
Prints markdown tables; results recorded in research/README.md.
"""
from _common import (FULL, DHEAD, HEAD, availability, cache_dir_from_argv, diff_row, grid, load_inputs, log,
                     m, outer, row, score)

VARIANTS = {'A no availability': ('rates_core', 'rates_core_adj'),
            'B QB term only': ('rates_core_qb_cs', 'rates_core_adj_qb_cs'),
            'C full layer (production)': FULL}


def main():
    for fam, base in (('rates_core_qb_cs', 'rates_core'), ('rates_core_adj_qb_cs', 'rates_core_adj')):
        m.FAMILIES[fam] = m.RATES_CORE; m.AVAIL_FAMILIES[fam] = base; m.AVAIL_FAMILY_COLS[fam] = ('qb_delta',)
    inp = load_inputs(cache_dir_from_argv())
    m.AVAIL_WINDOW = 4
    oof4 = grid(inp, availability(inp), [f for v in VARIANTS.values() for f in v], 'window 4, all test-1 families')
    res = {k: score(outer(oof4, f)[0]) for k, f in VARIANTS.items()}
    print('\n## Test 1\n' + HEAD)
    for k, s in res.items(): print(row(k, s))
    c = res['C full layer (production)']
    print('\n' + DHEAD)
    print(diff_row('C full vs A none', c, res['A no availability']))
    print(diff_row('B QB only vs A none', res['B QB term only'], res['A no availability']))
    print(diff_row('C full vs B QB only', c, res['B QB term only']))
    wres = {4: c}
    for w in (8, 16):
        m.AVAIL_WINDOW = w
        wres[w] = score(outer(grid(inp, availability(inp), FULL, f'window {w}'), FULL)[0])
    m.AVAIL_WINDOW = 4
    print('\n## Test 2\n' + HEAD)
    for w, s in wres.items(): print(row(f'window {w}' + (' (production)' if w == 4 else ''), s))
    print('\n' + DHEAD)
    for w in (8, 16): print(diff_row(f'window {w} vs 4', wres[w], wres[4]))
    log('done')


if __name__ == '__main__':
    main()
