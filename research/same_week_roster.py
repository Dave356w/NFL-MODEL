"""Test 5 (upper bound): what would same-week roster information be worth?

    python research/same_week_roster.py [CACHE_DIR]     # ~10 min warm

Production uses only the most recent roster BEFORE the game week (same-week
status has unknown timing). This variant uses the game week's own roster as the
reference and counts game-day inactives (INA) as out, i.e. it pretends the final
pregame roster (inactives are announced ~90 min before kickoff) was known at
forecast time. Historical same-week rows may include moves made after kickoff,
so this is an UPPER BOUND on what a T-60 snapshot could gain, not a usable model.
If the bound is small, live same-week rosters are not worth a new revision.
"""
from _common import (FULL, DHEAD, HEAD, availability, cache_dir_from_argv, diff_row, grid, load_inputs, log,
                     m, outer, row, score)


def same_week_table(inp):
    """Availability with the game week's own roster as reference and INA counted out.
    Weeks >= 2: week w's roster is relabelled w-1, so 'the latest roster before week w'
    is week w itself (availability_table keys roster weeks as ints). Week 1 already
    uses the week-1 roster in production; it is built from the unshifted roster."""
    a, t = inp['a'], inp['targets']
    shifted = a['rost'].assign(week=a['rost'].week - 1)
    later = m.availability_table(t[t.week >= 2], inp['qb'], a['snaps'], a['inj'], shifted[shifted.week >= 1])
    first = m.availability_table(t[t.week == 1], inp['qb'], a['snaps'], a['inj'], a['rost'])
    return m.pd.concat([first, later], ignore_index=True)


def main():
    inp = load_inputs(cache_dir_from_argv())
    res = {'production (prior-week roster)': score(outer(grid(inp, availability(inp), FULL, 'production'), FULL)[0])}
    old = m.ROSTER_OUT
    m.ROSTER_OUT = old + ('INA',)
    try:
        av = same_week_table(inp)
        res['same-week roster + inactives (upper bound)'] = score(outer(grid(inp, av, FULL, 'same-week'), FULL)[0])
    finally:
        m.ROSTER_OUT = old
    print('\n## Test 5\n' + HEAD)
    for k, s in res.items(): print(row(k, s))
    print('\n' + DHEAD)
    print(diff_row('same-week + INA vs production', res['same-week roster + inactives (upper bound)'],
                   res['production (prior-week roster)']))
    log('done')


if __name__ == '__main__':
    main()
