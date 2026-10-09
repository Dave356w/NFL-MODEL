"""Test 29: v1.15 game week's own reserve list vs v1.14, held-out development comparison.

    python research/game_week_reserve.py [CACHE_DIR]     # ~25 min warm

The owner adopted v1.15 after research test 28 (participation and market diagnostics). This
reports its held-out effect; it was not a gate. Two arms on the production families, grid and
nested selection, scored on the same priced held-out games 2023-2025:
  v1.14   GAME_WEEK_RESERVE = False: only the roster before the game week is read
  v1.15   GAME_WEEK_RESERVE = True: roster-out rows on the game week's own roster also count out
Also: how many availability inputs change, and the timing check behind the rule (players newly
on a game-week out list who nevertheless took an offensive or defensive snap in that game).
"""
import numpy as np
import pandas as pd

from _common import DHEAD, HEAD, OUTER, cache_dir_from_argv, diff_row, grid, load_inputs, log, m, outer, row, score

FAMS = tuple(m.FEATURE_FAMILIES)
ARMS = (('v1.14', False), ('v1.15', True))


def avail_for(inp, on):
    a, old = inp['a'], m.GAME_WEEK_RESERVE
    m.GAME_WEEK_RESERVE = on
    try:
        return m.availability_table(inp['targets'], inp['qb'], a['snaps'], a['inj'], a['rost'], depth=a.get('depth'))
    finally:
        m.GAME_WEEK_RESERVE = old


def timing_check(rost, snaps):
    """Players newly on a game-week out list (weeks 2+; not out on the team's previous roster week),
    and how many of them took an offensive or defensive snap in that week's game."""
    r = rost.assign(_out=m.roster_out_mask(rost))
    out = set(zip(r.season[r._out], r.week[r._out], r.team[r._out], r.gsis_id[r._out]))
    prev = {}
    for (s, t), g in r.groupby(['season', 'team']):
        ws = sorted(int(w) for w in g.week.unique())
        for a, b in zip(ws[:-1], ws[1:]): prev[(int(s), b, t)] = a
    sn = snaps[(snaps.offense_snaps + snaps.defense_snaps) > 0]
    played = set(zip(sn.season, sn.week, sn.team, sn.gsis_id))
    games = set(zip(snaps.season, snaps.week, snaps.team))
    rows = [(int(s), int(w), t, p) for s, w, t, p, o in zip(r.season, r.week, r.team, r.gsis_id, r._out)
            if o and w > 1 and (s, w, t) in games and (s, prev.get((int(s), int(w), t)), t, p) not in out]
    d = pd.DataFrame(rows, columns=['season', 'week', 'team', 'gsis_id'])
    d['played'] = [k in played for k in zip(d.season, d.week, d.team, d.gsis_id)]
    return d


def main():
    inp = load_inputs(cache_dir_from_argv())
    tc = timing_check(inp['a']['rost'], inp['a']['snaps'])
    by = tc.groupby('season').played.agg(['size', 'sum'])
    print(f'\nTiming: {len(tc)} players newly on a game-week out list (weeks 2+, 2019–25); '
          f'{int(tc.played.sum())} took an offensive or defensive snap in that game ({tc.played.mean():.2%})\n'
          + by.rename(columns={'size': 'newly out', 'sum': 'played'}).to_string())
    res, avs = {}, {}
    for name, on in ARMS:
        avs[name] = avail_for(inp, on)
        oof = grid(inp, avs[name], FAMS, name)
        o, picks = outer(oof, FAMS)
        res[name] = score(o); res[name]['frame'] = o
        log(f'{name}: picks {picks}')
    f = res['v1.14']['frame'].copy(); f['market_ml_wp'] = m.market_ml_wp(f)
    null = m.flat_bets(f, 'model_wp').null_ev.mean()
    print('\n## Test 29: v1.15 game-week reserve list, held-out ' + '–'.join(map(str, (OUTER[0], OUTER[-1]))))
    print(f'Same-row market favorite ROI {100 * res["v1.14"]["fav_roi"]:+.1f}%; market-correct null {100 * null:+.1f}%\n' + HEAD)
    for k, s in res.items(): print(row(k, s))
    base, new = res['v1.14'], res['v1.15']
    print('\n' + DHEAD + '\n' + diff_row('v1.15 vs v1.14', new, base))
    seasons = base['frame'].season.to_numpy()
    print('\n| Held-out season | Games | ROI difference | Log-loss gain |\n|---|---:|---:|---:|')
    for yr in OUTER:
        k = seasons == yr
        sub = lambda s: {'units_vec': s['units_vec'][k], 'll_vec': s['ll_vec'][k]}
        print(diff_row(str(yr), sub(new), sub(base)).replace(f'| {yr} |', f'| {yr} | {int(k.sum())} |'))
    key = ['season', 'week', 'team']; cols = list(m.AVAIL_COLS_CS)
    j = avs['v1.14'][key + cols].merge(avs['v1.15'][key + cols], on=key, suffixes=('_b', '_n'))
    chg = np.zeros(len(j), bool)
    for c in cols: chg |= ~np.isclose(j[c + '_b'].fillna(-9), j[c + '_n'].fillna(-9))
    qchg = ~np.isclose(j.qb_delta_b.fillna(-9), j.qb_delta_n.fillna(-9))
    held = j[j.season.between(OUTER[0], OUTER[-1])]
    print(f'\nTeam-weeks with a changed availability input, held-out seasons: {int(chg[held.index].sum())} of {len(held)} '
          f'(QB term changed: {int(qchg[held.index].sum())})')
    cset = set(zip(j.season[chg], j.week[chg], j.team[chg]))
    fr = base['frame']
    k = np.array([(y, w, h) in cset or (y, w, a) in cset for y, w, h, a in zip(fr.season, fr.week, fr.home, fr.away)])
    if k.any():
        sub = lambda s: {'units_vec': s['units_vec'][k], 'll_vec': s['ll_vec'][k]}
        print(DHEAD + '\n' + diff_row(f'games with a changed input (n={int(k.sum())})', sub(new), sub(base)))
    flips = (np.sign(new['frame'].model_wp - .5) != np.sign(base['frame'].model_wp - .5)).sum()
    print(f'Picked side changed in {int(flips)} of {len(fr)} games')
    log('done')


if __name__ == '__main__':
    main()
