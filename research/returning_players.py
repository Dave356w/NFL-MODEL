"""Test 31: credit returning players.

    python research/returning_players.py [CACHE_DIR]     # ~12 min warm

Plan and decision rule: research/README.md, Tests 29-31 (committed before any result).
The unit columns (*_out_cs) count fresh absences only. Here, for each team-week and unit,
returning share = sum of s_p * (1 - u_p) over players p who
  * had no unit snaps for the team in the window games (the games _out_cs uses),
  * were listed Out/Doubtful on the team's injury report, or carried a reserve roster status,
    in at least one week of those window games,
with u_p production's unavailability for this game and s_p p's share of the unit's snaps over
his most recent (up to 4) games with snaps for the team before the window (this season and the
previous one). Each {g}_out_cs becomes {g}_out_cs - returning share. QBs are untouched.
"""
import numpy as np
import pandas as pd

from _common import LAST, availability, cache_dir_from_argv, load_inputs, log, m, outer, primary_row, \
    report_family, same_rows, score

LEVEL = 1 - .05 / 3
GROUPS = m.OFFENSE_GROUPS + m.DEFENSE_GROUPS
REGULAR = .10  # a returning share at or above this in some unit marks a returning regular
PRE_GAMES = 4


def returning_shares(targets, snaps, inj, rost):
    """DataFrame (season, week, team, <group>_ret) using only information production uses."""
    inj = m.injury_weights(inj)
    inj_map = {k: g.groupby('gsis_id').weight.max().to_dict() for k, g in inj.groupby(['season', 'week', 'team'])}
    inj_out = {k: set(g.gsis_id[g.weight >= 1.]) for k, g in inj.groupby(['season', 'week', 'team'])}
    rost = rost.assign(_out=m.roster_out_mask(rost))
    rost_out = {k: set(g.gsis_id[g._out]) for k, g in rost.groupby(['season', 'week', 'team'])}
    members = {k: set(g.gsis_id[~g._out]) for k, g in rost.groupby(['season', 'week', 'team'])}
    roster_weeks = {}
    for (rs, rw, rt) in members: roster_weeks.setdefault((int(rs), rt), []).append(int(rw))

    def ref_week_for(y, w, t):  # as availability_table: latest roster week before the game
        if w == 1: return 1 if (y, 1, t) in members else None
        prev = [wk for wk in roster_weeks.get((y, t), ()) if wk < w]
        return max(prev) if prev else None

    snaps = snaps.copy(); snaps['group'] = snaps.position.map(m.POS_GROUP)
    snaps = snaps[snaps.group.notna()].copy()
    snaps['snaps'] = np.where(snaps.group.isin(m.OFFENSE_GROUPS), snaps.offense_snaps, snaps.defense_snaps)
    by_team = {t: g for t, g in snaps.groupby('team')}
    rows = []
    for r in targets[['season', 'week', 'team']].drop_duplicates().itertuples(index=False):
        y, w, t = int(r.season), int(r.week), r.team
        rec = {'season': y, 'week': w, 'team': t, **{f'{g}_ret': 0. for g in GROUPS}}
        g = by_team.get(t)
        if g is None: rows.append(rec); continue
        past = g[m.before(g, y, w)]
        games = past[['season', 'week', 'game_id']].drop_duplicates().sort_values(['season', 'week'])
        h = past[past.game_id.isin(games.tail(m.AVAIL_WINDOW).game_id)]
        cur = games[games.season == y]
        hcs = past[past.game_id.isin(cur.tail(m.AVAIL_WINDOW).game_id)] if len(cur) >= m.CS_MIN_GAMES else h
        if not len(hcs): rows.append(rec); continue
        # This game's unavailability, exactly as availability_table builds it (no personnel events).
        ref_week = ref_week_for(y, w, t)
        out = dict(inj_map.get((y, w, t), {}))
        if ref_week is not None and w > 1:
            for pid in rost_out.get((y, ref_week, t), ()): out[pid] = 1.
        ref = members.get((y, ref_week, t)) if ref_week is not None else None
        if ref is not None and h.snaps.sum() > 0:
            per_all = h.groupby('gsis_id').snaps.sum()
            if float(per_all[~per_all.index.isin(ref)].sum() / per_all.sum()) > m.MEMBERSHIP_MAX_SHARE: ref = None

        def unavail(pid):
            return 1. if (ref is not None and pid not in ref) else out.get(pid, 0.)
        win_weeks = set(zip(hcs.season.astype(int), hcs.week.astype(int)))
        absent = set().union(*[inj_out.get((s, wk, t), set()) | rost_out.get((s, wk, t), set()) for s, wk in win_weeks])
        fs, fw = min(win_weeks)
        pre = past[(past.season >= y - 1) & m.before(past, fs, fw)]
        for grp in GROUPS:
            in_window = set(hcs.gsis_id[(hcs.group == grp) & (hcs.snaps > 0)])
            pg = pre[pre.group == grp]
            unit = pg.groupby('game_id').snaps.sum()
            share = 0.
            for pid, rows_p in pg[pg.snaps > 0].groupby('gsis_id'):
                if pid in in_window or pid not in absent: continue
                last = rows_p.sort_values(['season', 'week']).tail(PRE_GAMES).game_id
                tot = float(unit[last].sum())
                if tot > 0: share += float(rows_p[rows_p.game_id.isin(last)].snaps.sum()) / tot * (1. - unavail(pid))
            rec[f'{grp}_ret'] = share
        rows.append(rec)
    return pd.DataFrame(rows)


def net_availability(avail, ret):
    """Production availability with each {g}_out_cs reduced by the returning share."""
    a = avail.merge(ret, on=['season', 'week', 'team'], how='left', validate='one_to_one')
    for grp in GROUPS:
        a[f'{grp}_out_cs'] = a[f'{grp}_out_cs'] - a[f'{grp}_ret'].fillna(0.)
    return a.drop(columns=[f'{g}_ret' for g in GROUPS])


def main():
    inp = load_inputs(cache_dir_from_argv())
    sched, a = inp['sched'], inp['a']
    avail = availability(inp)
    ret = returning_shares(inp['targets'], a['snaps'], a['inj'], a['rost'])
    rc = [f'{g}_ret' for g in GROUPS]
    ret['max_ret'] = ret[rc].max(axis=1)
    log(f'returning shares: {(ret.max_ret > 0).mean():.1%} of team-weeks have any, '
        f'{(ret.max_ret >= REGULAR).mean():.1%} have a returning regular (share >= {REGULAR:g} in some unit)')
    print('Mean returning share by unit where nonzero: '
          + ', '.join(f'{g} {ret.loc[ret[c] > 0, c].mean():.3f} (n={int((ret[c] > 0).sum())})' for g, c in zip(GROUPS, rc)))
    prod = {h: m.lagged_features(inp['box'], sched, h, avail) for h in m.TEAM_HALF_LIVES}
    net = net_availability(avail, ret[['season', 'week', 'team', *rc]])
    var = {h: m.lagged_features(inp['box'], sched, h, net) for h in m.TEAM_HALF_LIVES}
    log('features built')
    fams = tuple(m.FEATURE_FAMILIES)
    held, picks, sc = {}, {}, {}
    for name, feats in (('production (v1.12)', prod), ('Test 31: returning credit', var)):
        oof = m.attach_moneylines(m.walk_forward_grid(feats, LAST), sched)
        held[name], picks[name] = outer(oof, fams); sc[name] = score(held[name])
        log(f'{name} picks {picks[name]}')
    same_rows(*held.values())
    hp = held['production (v1.12)']
    mr = ret.set_index(['season', 'week', 'team']).max_ret
    reg = np.array([max(mr.get((y, w, h), 0.), mr.get((y, w, aw), 0.)) >= REGULAR
                    for y, w, h, aw in zip(hp.season, hp.week, hp.home, hp.away)])
    d = sc['production (v1.12)']['ll_vec'] - sc['Test 31: returning credit']['ll_vec']
    sub = float(d[reg].mean()) if reg.any() else np.nan
    print('\n### Test 31 result\n\n| Arm | LL gain vs production [98.33% CI] | ± SE | Verdict |\n|---|---:|---:|---|')
    primary_row('Test 31: returning credit', d, LEVEL,
                lambda mean, lo, hi: 'dropped' if hi < 0 or not sub > 0 else 'supported' if lo > 0 else 'unresolved')
    print(f'\nHeld-out games with a returning regular (either team, share >= {REGULAR:g}): n={int(reg.sum())}, '
          f'LL gain {sub:+.4f} ± {d[reg].std(ddof=1) / np.sqrt(reg.sum()):.4f}; other games '
          f'{d[~reg].mean():+.4f} ± {d[~reg].std(ddof=1) / np.sqrt((~reg).sum()):.4f}')
    report_family(hp, sc, LEVEL)
    log('done')


if __name__ == '__main__':
    main()
