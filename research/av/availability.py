"""Projected participation at kickoff, with opportunity redistributed to available players.

Timing and membership follow v1.15 exactly (nfl_model.availability_table): the week's injury report;
the most recent roster BEFORE the game week for membership and roster-out codes (week 1: the week-1
roster); from week 2 the game week's own reserve list (GAME_WEEK_RESERVE); a window player absent from
the reference roster has left; the membership rule is skipped as a data gap when more than
MEMBERSHIP_MAX_SHARE of window snaps are off-roster. The QB is v1.15's projected starter
(`qb_expected`, which already applies the depth-chart and questionable-starter rules). Historical
dated personnel events are empty (as in every research run), so none apply.

Only the multipliers differ from v1.15's absence weights (Out/Doubtful 1, Questionable .25 of a snap
share): here participation multipliers m = Out 0, Doubtful .15, Questionable .65, available 1; roster-out
or departed 0. They are initial hypotheses, not calibrated probabilities.

Participation, per unit u of team t before (season y, week w):
  b_i   base share when active: mean snap share over the player's most recent BASE_GAMES games with
        snaps (any team, seasons y-1 and y, all before the game); 0 without such games.
  T_u   unit slots: mean summed unit share per game over the team's window (v1.15's '_cs' window:
        last AVAIL_WINDOW games, current season once it has CS_MIN_GAMES); league default if none.
  p_i   fill in descending b order with m_i b_i until T_u is reached (a returning starter takes his
        role back ahead of his stand-in), then give any shortfall to available members in proportion
        to their headroom m_i - p_i (expected share is capped at m_i x full time). Total opportunity is conserved at T_u.
"""
import numpy as np
import pandas as pd

from _common import m
from prepare_data import UNITS

MULT = {'Out': 0., 'Doubtful': .15, 'Questionable': .65}
BASE_GAMES = 4
STARTER_SHARE = .5
DEFAULT_SLOTS = {'QB': 1., 'OL': 5., 'RB': 1., 'WRTE': 3.4, 'DL': 3.3, 'LB': 2.7, 'DB': 4.9}


def unit_of(pos):
    return 'QB' if pos == 'QB' else m.POS_GROUP.get(pos)


def waterfill(base, mult, slots, cap=1.):
    """Projected shares: fill by descending base share with mult*base up to `slots`, then distribute any
    shortfall over available players by headroom m*cap - p (so no one's expected share exceeds his
    multiplier x full time). Returns (p, unfilled shortfall)."""
    base = np.asarray(base, float); mult = np.asarray(mult, float)
    p = np.zeros(len(base)); left = float(slots)
    for i in np.argsort(-base, kind='stable'):
        p[i] = min(mult[i] * base[i], max(left, 0.), cap); left -= p[i]
    for _ in range(20):
        if left <= 1e-9: break
        room = np.clip(mult * cap - p, 0, None)  # expected share never exceeds m x full time
        if room.sum() <= 1e-12: break
        add = np.minimum(room / room.sum() * left, room)
        p += add; left -= add.sum()
    return p, max(left, 0.)


class Participation:
    """Per team-week projected shares from v1.15's injury/roster inputs and the player-game table."""

    def __init__(self, pg, inj, rost, avail15, qb, depth=None):
        self.pg = pg
        inj = m.injury_weights(inj)
        self.status = {k: g.groupby('gsis_id').report_status.agg(lambda s: next((x for x in ('Out', 'Doubtful', 'Questionable')
                                                                                   if (s == x).any()), None)).to_dict()
                       for k, g in inj.groupby(['season', 'week', 'team'])}
        rost = rost.assign(_out=m.roster_out_mask(rost), _unit=rost.position.map(unit_of))
        self.rost_out = {k: set(g.gsis_id[g._out]) for k, g in rost.groupby(['season', 'week', 'team'])}
        self.members = {k: dict(zip(g.gsis_id[~g._out], g._unit[~g._out])) for k, g in rost.groupby(['season', 'week', 'team'])}
        self.rweeks = {}
        for (s, w, t) in self.members: self.rweeks.setdefault((int(s), t), []).append(int(w))
        a = avail15.set_index(['season', 'week', 'team'])
        self.qb_expected, self.qb_usual = a.qb_expected.to_dict(), a.qb_usual.to_dict()
        names = {}
        for pid, nm in zip(qb.gsis_id, qb['name']): names.setdefault(pid, set()).add(nm)
        if depth is not None and len(depth):
            for pid, nm in zip(depth.gsis_id, depth.player_name): names.setdefault(pid, set()).add(nm)
        self.qb_names = names
        d = pg[(pg.share > 0) & pg.unit.notna()].sort_values(['season', 'week'])
        d = d.assign(_k=d.season * 100 + d.week)
        self.by_player = {p: (g._k.to_numpy(), g.share.to_numpy(), g.unit.to_numpy()) for p, g in d.groupby('gsis_id')}
        self.team_games = {t: g for t, g in pg[pg.unit.notna()].groupby('team')}
        prev = pg[pg.unit.notna()].groupby(['season', 'team', 'gsis_id']).share.sum()
        self.prev_season = {k: g.droplevel([0, 1]) for k, g in prev.groupby(level=[0, 1])}

    def ref_week(self, y, w, t):
        if w == 1: return 1 if (y, 1, t) in self.members else None
        prev = [k for k in self.rweeks.get((y, t), ()) if k < w]
        return max(prev) if prev else None

    def base_share(self, pid, y, w):
        h = self.by_player.get(pid)
        if h is None: return 0., None
        k = y * 100 + w
        i = np.searchsorted(h[0], k, side='left')
        lo = np.searchsorted(h[0], (y - 1) * 100, side='left')
        j = max(lo, i - BASE_GAMES)
        return (float(h[1][j:i].mean()), h[2][i - 1]) if i > j else (0., h[2][i - 1] if i > 0 else None)

    def window(self, y, w, t):
        g = self.team_games.get(t)
        if g is None: return None
        past = g[(g.season < y) | ((g.season == y) & (g.week < w))]
        games = past[['season', 'week', 'game_id']].drop_duplicates().sort_values(['season', 'week'])
        cur = games[games.season == y]
        ids = (cur if len(cur) >= m.CS_MIN_GAMES else games).tail(m.AVAIL_WINDOW).game_id
        return past[past.game_id.isin(ids)]

    def team_week(self, y, w, t):
        """Player rows for one team-week: unit, base b, multiplier m (projected) and flags."""
        rw = self.ref_week(y, w, t)
        ref = self.members.get((y, rw, t)) if rw is not None else None
        out = set(self.rost_out.get((y, rw, t), ())) if (rw is not None and w > 1) else set()
        if m.GAME_WEEK_RESERVE and w > 1: out |= self.rost_out.get((y, w, t), set())
        st = self.status.get((y, w, t), {})
        win = self.window(y, w, t)
        wsh = win.groupby('gsis_id').share.sum() if win is not None and len(win) else pd.Series(dtype=float)
        wunit = (win.sort_values('share').drop_duplicates('gsis_id', keep='last').set_index('gsis_id').unit
                 if win is not None and len(win) else pd.Series(dtype=object))
        gap = False
        if ref is not None and wsh.sum() > 0:
            gap = wsh[~wsh.index.isin(list(ref))].sum() / wsh.sum() > m.MEMBERSHIP_MAX_SHARE
        if gap: ref = None
        pool = {}
        if ref is not None:
            for pid, u in ref.items():
                if u is not None: pool[pid] = u
        for pid, u in wunit.items():
            pool.setdefault(pid, u)
        rows = []
        for pid, u in pool.items():
            b, _ = self.base_share(pid, y, w)
            departed = ref is not None and pid not in ref
            mult = 0. if (departed or pid in out) else MULT.get(st.get(pid), 1.)
            rows.append({'gsis_id': pid, 'unit': u, 'base': b, 'mult': mult, 'departed': departed,
                         'roster_out': pid in out, 'status': st.get(pid)})
        df = pd.DataFrame(rows, columns=['gsis_id', 'unit', 'base', 'mult', 'departed', 'roster_out', 'status'])
        slots = {}
        if win is not None and len(win):
            per = win.groupby(['game_id', 'unit']).share.sum().groupby('unit').mean()
            slots = per.to_dict()
        slots = {u: float(slots.get(u, DEFAULT_SLOTS[u])) for u in UNITS}
        slots['QB'] = 1.
        cont = np.nan
        ps = self.prev_season.get((y - 1, t))
        if ps is not None and ps.sum() > 0 and ref is not None:
            cont = float(ps[ps.index.isin(list(ref))].sum() / ps.sum())
        return df, slots, {'ref_week': rw, 'membership_gap': gap, 'continuity': cont}

    def qb_targets(self, y, w, t, pool_ids):
        """v1.15's projected starter as {gsis_id: share}; None when the name cannot be matched."""
        e = self.qb_expected.get((y, w, t))
        if e is None or not isinstance(e, str): return None
        if e == m.NO_QB_LABEL: return {}
        parts = e.split(' (Q) / ') if ' (Q) / ' in e else [e]
        wts = [m.QB_QUESTIONABLE_START, 1 - m.QB_QUESTIONABLE_START] if len(parts) == 2 else [1.]
        out = {}
        for nm, wt in zip(parts, wts):
            if nm == m.NO_QB_LABEL: continue
            hit = [p for p in pool_ids if nm in self.qb_names.get(p, ())]
            if len(hit) != 1: return None
            out[hit[0]] = out.get(hit[0], 0.) + wt
        return out
