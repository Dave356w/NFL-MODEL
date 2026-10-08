"""Test 33: weight absences by player production, not snaps.

    python research/quality_availability.py [CACHE_DIR]     # ~25 min warm

Plan and decision rule: research/README.md, Tests 33-34 (committed before any result).
For WR/TE (targets), RB (carries + targets) and DL (sacks + QB hits), a player's weight in the
unit column {g}_out_cs becomes his share of the unit's production over the same window games,
instead of his share of the unit's snaps. OL, LB and DB keep snap weights. With snap weights the
reimplemented columns must reproduce production's exactly. Decided on held-out 2017-20; 2023-25
secondary (research/_bases.py).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from _bases import compare, data_ok, load_basis, window_gain
from _common import cache_dir_from_argv, log, m

GROUPS = m.OFFENSE_GROUPS + m.DEFENSE_GROUPS
PRODUCTION = {'WRTE': ('targets',), 'RB': ('carries', 'targets'), 'DL': ('def_sacks', 'def_qb_hits')}
LEVEL = .975
DIFF = .05


def load_player_production(years, cache):
    """Regular-season production per (gsis_id, game_id) for the PRODUCTION stats, cached per year span."""
    path = Path(cache) / f'player_production_{min(years)}_{max(years)}.csv'
    if path.exists(): return pd.read_csv(path)
    import nflreadpy as nfl
    cols = sorted({c for v in PRODUCTION.values() for c in v})
    ps = m.fetch_upstream(lambda: nfl.load_player_stats(list(years)).to_pandas(), f'player stats {min(years)}-{max(years)}')
    ps = ps[(ps.season_type == 'REG') & ps.player_id.notna() & ps.game_id.notna()]
    out = (ps.rename(columns={'player_id': 'gsis_id'})[['gsis_id', 'game_id', *cols]]
           .fillna({c: 0. for c in cols}).groupby(['gsis_id', 'game_id'], as_index=False)[cols].sum())
    out.to_csv(path, index=False)
    return out


def unit_columns(targets, snaps, inj, rost, production=None):
    """{g}_out_cs per (season, week, team) as availability_table builds them (no personnel events).
    production=None: snap weights. Otherwise a frame (gsis_id, game_id, stats): the PRODUCTION units use
    each player's share of the unit's production over the window games; a unit with zero window
    production keeps snap weights for that team-week (counted in 'fallbacks')."""
    inj = m.injury_weights(inj)
    inj_map = {k: g.groupby('gsis_id').weight.max().to_dict() for k, g in inj.groupby(['season', 'week', 'team'])}
    rost = rost.assign(_out=m.roster_out_mask(rost))
    rost_out = {k: set(g.gsis_id[g._out]) for k, g in rost.groupby(['season', 'week', 'team'])}
    members = {k: set(g.gsis_id[~g._out]) for k, g in rost.groupby(['season', 'week', 'team'])}
    roster_weeks = {}
    for (rs, rw, rt) in members: roster_weeks.setdefault((int(rs), rt), []).append(int(rw))

    def ref_week_for(y, w, t):
        if w == 1: return 1 if (y, 1, t) in members else None
        prev = [wk for wk in roster_weeks.get((y, t), ()) if wk < w]
        return max(prev) if prev else None

    snaps = snaps.copy(); snaps['group'] = snaps.position.map(m.POS_GROUP)
    snaps = snaps[snaps.group.notna()].copy()
    snaps['snaps'] = np.where(snaps.group.isin(m.OFFENSE_GROUPS), snaps.offense_snaps, snaps.defense_snaps)
    by_team = {t: g for t, g in snaps.groupby('team')}
    prod = None
    if production is not None:
        prod = {}
        for g, stats in PRODUCTION.items():
            v = production.set_index(['gsis_id', 'game_id'])[list(stats)].sum(axis=1)
            prod[g] = v[v != 0].to_dict()
    rows, fallbacks = [], {g: 0 for g in PRODUCTION}
    for r in targets[['season', 'week', 'team']].drop_duplicates(['season', 'week', 'team']).itertuples(index=False):
        y, w, t = int(r.season), int(r.week), r.team
        rec = {'season': y, 'week': w, 'team': t, **{f'{g}_out_cs': np.nan for g in GROUPS}}
        g_ = by_team.get(t)
        h = hcs = None
        if g_ is not None:
            past = g_[m.before(g_, y, w)]
            games = past[['season', 'week', 'game_id']].drop_duplicates().sort_values(['season', 'week'])
            h = past[past.game_id.isin(games.tail(m.AVAIL_WINDOW).game_id)]
            cur = games[games.season == y]
            hcs = past[past.game_id.isin(cur.tail(m.AVAIL_WINDOW).game_id)] if len(cur) >= m.CS_MIN_GAMES else h
        ref_week = ref_week_for(y, w, t)
        out = dict(inj_map.get((y, w, t), {}))
        if ref_week is not None and w > 1:
            for pid in rost_out.get((y, ref_week, t), ()): out[pid] = 1.
        ref = members.get((y, ref_week, t)) if ref_week is not None else None
        if ref is not None and h is not None and h.snaps.sum() > 0:
            per_all = h.groupby('gsis_id').snaps.sum()
            if float(per_all[~per_all.index.isin(ref)].sum() / per_all.sum()) > m.MEMBERSHIP_MAX_SHARE: ref = None

        def unavail(pid):
            return 1. if (ref is not None and pid not in ref) else out.get(pid, 0.)
        if hcs is not None:
            win = set(hcs.game_id)
            for grp in GROUPS:
                per = hcs[hcs.group == grp].groupby('gsis_id').snaps.sum()
                if prod is not None and grp in PRODUCTION and len(per):
                    pw = pd.Series({pid: sum(prod[grp].get((pid, gid), 0.) for gid in win) for pid in per.index})
                    if pw.sum() > 0: per = pw
                    else: fallbacks[grp] += 1
                tot = per.sum()
                if tot > 0: rec[f'{grp}_out_cs'] = float(sum(v * unavail(pid) for pid, v in per.items()) / tot)
        rows.append(rec)
    return pd.DataFrame(rows), fallbacks


def main():
    cache = cache_dir_from_argv()
    results = {}
    for kind in ('old', 'recent'):
        basis = load_basis(kind, cache)
        a = basis['a']
        snap_cols, _ = unit_columns(basis['targets'], a['snaps'], a['inj'], a['rost'])
        ref = basis['avail'].set_index(['season', 'week', 'team'])
        chk = snap_cols.set_index(['season', 'week', 'team']).loc[ref.index]
        for g in GROUPS:
            c = f'{g}_out_cs'
            if not np.allclose(chk[c].to_numpy(float), ref[c].to_numpy(float), equal_nan=True, rtol=0, atol=1e-12):
                raise ValueError(f'{kind}: snap-weighted {c} does not reproduce production')
        log(f'{kind}: snap weights reproduce all six production unit columns')
        production = load_player_production(basis['years'], cache)
        q, fb = unit_columns(basis['targets'], a['snaps'], a['inj'], a['rost'], production)
        qi = q.set_index(['season', 'week', 'team']).loc[ref.index]
        held = qi.index.get_level_values('season').isin(basis['outer'])
        print(f'\n{kind}: zero-production fallbacks to snap weights (team-weeks): {fb}')
        for g in PRODUCTION:
            c = f'{g}_out_cs'; dd = (qi[c] - ref[c]).abs()
            print(f'{kind} {g}: |production − snap weighting| > {DIFF:g} in {100 * float((dd[held] > DIFF).mean()):.1f}% '
                  f'of held-out team-weeks; mean {qi[c][held].mean():.3f} vs {ref[c][held].mean():.3f}')
        arm_avail = basis['avail'].copy().set_index(['season', 'week', 'team'])
        for g in PRODUCTION: arm_avail[f'{g}_out_cs'] = qi[f'{g}_out_cs']
        arm_avail = arm_avail.reset_index()
        arm = {h: m.lagged_features(basis['box'], basis['sched'], h, arm_avail) for h in m.TEAM_HALF_LIVES}
        if kind == 'old': print('\n### Test 33 result')
        results[kind] = compare('Test 33: production-weighted absences', basis, arm_feats=arm, level=LEVEL)
    old, rec = results['old'], results['recent']
    g517, n517 = window_gain(old, 5, 17)
    print(f'\n2017–20 weeks 5–17: LL gain {g517:+.4f} (n={n517}); 2023–25 gain {rec["d"].mean():+.4f}')
    if not data_ok(old): verdict = 'not run (data check failed)'
    elif old['hi'] < 0 or old['hi'] < .001 or g517 <= 0: verdict = 'dropped'
    elif old['lo'] > 0 and rec['d'].mean() > 0: verdict = 'supported'
    else: verdict = 'unresolved'
    print(f'**Test 33 verdict: {verdict}**')
    log('done')


if __name__ == '__main__':
    main()
