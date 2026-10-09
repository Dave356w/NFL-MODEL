"""Test 28: player-availability signal audit. Uses no game outcomes.

    python research/availability_audit.py [CACHE_DIR] [OUT_DIR]     # ~10 min warm; OUT_DIR keeps the tables

A. Participation by status. For every regular (>= 25% of his unit's snaps, on average, in the
   games he played among the team's previous 4) the snaps he actually played in the listed game
   against that normal share, by report status x final practice status, with production's roster
   rule applied. A status's calibrated weight is its excess snap loss over unlisted regulars,
   scaled so Out = 1, estimated on 2019-22 and checked on 2023-25. Also: regulars production counts
   available who are on a reserve list in the GAME week's own roster, or gone from it (same-week
   moves: production reads only the roster before the game week), and regulars back from an absence.
B. Window vs profile. Production unit columns count absences over the last 4 games (this season
   once 2 exist). The box-score profile they adjust decays over every prior game. On the profile's
   own weights (half-life 8 team games, this season once 2 exist, else production's window):
     linger  absent players' decayed share minus production's column (absences older than 4 games)
     return  available players' healthy share x profile weight of the games they missed while
             listed Out/Doubtful or on a reserve list (no production counterpart)
   The 3-season versions (OFFSEASON_RETENTION, MAX_HISTORY_SEASONS) are reported for contrast.
     samewk  production's window share of players it counts available who are on a reserve list
             in the game week's own roster or gone from it (weeks 2+)
   v1.15 adopted the same-week reserve list; main() pins GAME_WEEK_RESERVE = False so this audit
   still reproduces v1.14 production.
C. Market pricing. OLS of the no-vig closing moneyline log-odds on the frozen recipe's 24 features
   plus each signal, converted to model log-odds with that recipe's unit coefficients (fit once on
   2021-25 games). A coefficient of 1 means the market moves as much as the model's own unit
   weights would; S_prod, production's unit columns on the same scale, is the yardstick.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logit

from _common import availability, cache_dir_from_argv, load_inputs, log, m

GROUPS = m.OFFENSE_GROUPS + m.DEFENSE_GROUPS
REGULAR = .25                 # normal share of unit snaps that makes a player a regular (part A)
FIT_SEASONS = (2019, 2022)    # part A weights are estimated here, checked on 2023-25
PROFILE_HALF_LIFE = 8.        # frozen 2026 recipe
FROZEN = {'family': 'rates_core_avail_cs_peaks_nosacks', 'half_life': PROFILE_HALF_LIFE, 'ridge': .1}
PS = {'Did ': 'DNP', 'Limi': 'Lim', 'Full': 'Full'}
ORDER = ['not listed', 'game-week reserve/gone', 'practice/Full', 'practice/Lim', 'practice/DNP', 'Q/Full', 'Q/Lim', 'Q/DNP', 'Q/-',
         'Doubtful', 'Out', 'roster out']


def practice_label(report_status, practice_status):
    """Status label from the final report: game status, and for Questionable or practice-only rows
    the last practice participation (DNP / Lim / Full, '-' if missing)."""
    ps = PS.get(str(practice_status or '').strip()[:4], '-')
    if report_status in ('Out', 'Doubtful'): return report_status
    if report_status == 'Questionable': return f'Q/{ps}'
    return f'practice/{ps}'


def calibrated_weight(label, weights):
    """Unit-snap weight of a status label; labels without an estimate count as available."""
    return weights.get(label, 1. if label in ('Out', 'Doubtful') else 0.)


def profile_measures(P, W, unavail, missed, on_team):
    """Profile-weighted unit measures for one team-game.

    P        (games x players) unit snap shares in the profile's prior games
    W        profile weight per game
    unavail  current unavailability per player, 0..1 (production's rule)
    missed   (games x players) bool: listed Out/Doubtful or on a reserve list that week
    on_team  (games x players) bool: on the team's roster that week, or played

    absent    = sum_i s_i u_i, s_i the decayed share of player i
    returning = sum_i (1 - u_i) h_i f_i: h_i his decayed share over games he was on the team and
                not missed, f_i the profile weight of the games he missed. A backup who never
                missed a game and an arrival not yet on the team earn no credit.
    """
    P, W = np.asarray(P, float), np.asarray(W, float)
    missed, on_team, unavail = np.asarray(missed, bool), np.asarray(on_team, bool), np.asarray(unavail, float)
    Ws = W.sum()
    if not len(W) or Ws <= 0: return np.nan, np.nan
    absent = float((W @ P / Ws) @ unavail)
    ok = on_team & ~missed
    den = W @ ok
    healthy = np.divide(W @ (P * ok), den, out=np.zeros(P.shape[1]), where=den > 0)
    returning = float(((1 - unavail) * healthy * (W @ missed) / Ws).sum())
    return absent, returning


def profile_weights(seasons, year, half_life=PROFILE_HALF_LIFE):
    """lagged_features' team-game decay: age in team games, OFFSEASON_RETENTION per season back."""
    seasons = np.asarray(seasons, float)
    age = np.arange(len(seasons) - 1, -1, -1, dtype=float)
    return np.exp2(-age / half_life) * np.power(m.OFFSEASON_RETENTION, year - seasons)


def load_injury_detail(years):
    """Final practice status per player-week (production's injury cache keeps report_status only)."""
    import nflreadpy as nfl
    parts = []
    for y in years:
        path = m.cache_dir() / f'avail_injdetail_{y}.csv'
        if path.exists(): parts.append(pd.read_csv(path)); continue
        inj = m.fetch_upstream(lambda: nfl.load_injuries(y).to_pandas(), f'injuries {y}')
        inj = m.normalize_teams(inj[inj.game_type == 'REG'].dropna(subset=['gsis_id']).copy())
        inj = inj[['season', 'week', 'team', 'gsis_id', 'report_status', 'practice_status']]
        inj = inj.drop_duplicates(['season', 'week', 'team', 'gsis_id'])
        inj.to_csv(path, index=False); parts.append(inj)
    d = pd.concat(parts, ignore_index=True)
    d['label'] = [practice_label(s if isinstance(s, str) else None, p) for s, p in zip(d.report_status, d.practice_status)]
    return d


def unit_snaps(snaps):
    s = snaps.copy(); s['group'] = s.position.map(m.POS_GROUP); s = s[s.group.notna()].copy()
    off = s.group.isin(m.OFFENSE_GROUPS)
    s['snaps'] = np.where(off, s.offense_snaps, s.defense_snaps)
    # Team snaps per game and side: the player with the most (usually the centre or a safety).
    s['team_snaps'] = s.groupby(['game_id', 'team', off.rename('off')]).snaps.transform('max')
    return s


class Roster:
    """Production's roster rule: the most recent roster week before the game (week 1: week 1)."""

    def __init__(self, rost, inj):
        rost = rost.assign(_out=m.roster_out_mask(rost))
        self.out = {k: set(g.gsis_id[g._out]) for k, g in rost.groupby(['season', 'week', 'team'])}
        self.members = {k: set(g.gsis_id[~g._out]) for k, g in rost.groupby(['season', 'week', 'team'])}
        self.listed = {k: set(g.gsis_id) for k, g in rost.groupby(['season', 'week', 'team'])}
        self.weeks = {}
        for (s, w, t) in self.members: self.weeks.setdefault((int(s), t), []).append(int(w))
        inj = m.injury_weights(inj)
        self.inj = {k: g.groupby('gsis_id').weight.max().to_dict() for k, g in inj.groupby(['season', 'week', 'team'])}
        self.hard = {k: set(g.gsis_id[g.weight >= 1.]) for k, g in inj.groupby(['season', 'week', 'team'])}

    def gone(self, y, w, t, pid):
        """On a reserve list in the game week's own roster, or absent from it (weeks 2+; False
        when the team has no roster rows that week)."""
        if w == 1 or (y, w, t) not in self.listed: return False
        return pid in self.out.get((y, w, t), ()) or pid not in self.listed[(y, w, t)]

    def ref_week(self, y, w, t):
        if w == 1: return 1 if (y, 1, t) in self.members else None
        prev = [x for x in self.weeks.get((y, t), ()) if x < w]
        return max(prev) if prev else None

    def status(self, y, w, t, weights=None):
        """(pid -> weight for listed or roster-out players, reference member set or None)."""
        rw = self.ref_week(y, w, t)
        out = dict(self.inj.get((y, w, t), {}) if weights is None else weights.get((y, w, t), {}))
        if rw is not None and w > 1:
            for pid in self.out.get((y, rw, t), ()): out[pid] = 1.
        return out, (self.members.get((y, rw, t)) if rw is not None else None)


# ---------------------------------------------------------------- A. participation

def participation(s, detail, roster):
    """One row per (target game, regular window player): normal share, share played, status label.
    The window is the team's previous 4 games across seasons (no this-season rule), and production's
    membership data-gap rule is not applied: this is a participation measurement, not a feature."""
    lab = detail.set_index(['season', 'week', 'team', 'gsis_id']).label
    s = s.assign(pct=s.snaps / s.team_snaps.where(s.team_snaps > 0))
    s = s.groupby(['season', 'week', 'game_id', 'team', 'gsis_id'], as_index=False).agg(pct=('pct', 'max'), snaps=('snaps', 'max'))
    rows = []
    for t, st in s.groupby('team'):
        games = st[['season', 'week', 'game_id']].drop_duplicates().sort_values(['season', 'week']).reset_index(drop=True)
        by = {g: d.set_index('gsis_id').pct for g, d in st.groupby('game_id')}
        for i in range(m.AVAIL_WINDOW, len(games)):
            tg = games.iloc[i]; win = games.game_id.iloc[i - m.AVAIL_WINDOW:i]
            per = st[st.game_id.isin(win)].groupby('gsis_id').agg(normal=('pct', 'mean'), wsnaps=('snaps', 'sum'))
            per = per[per.normal >= REGULAR]
            if not len(per): continue
            _, ref = roster.status(int(tg.season), int(tg.week), t)
            played = by[tg.game_id].reindex(per.index).fillna(0.).to_numpy()
            rows.append(per.assign(season=int(tg.season), week=int(tg.week), team=t, played=played,
                                   roster_out=[ref is not None and pid not in ref for pid in per.index]).reset_index())
    d = pd.concat(rows, ignore_index=True)
    key = pd.MultiIndex.from_arrays([d.season, d.week, d.team, d.gsis_id])
    d['label'] = lab.reindex(key).fillna('not listed').to_numpy()
    d.loc[d.roster_out & ~d.label.isin(['Out', 'Doubtful']), 'label'] = 'roster out'
    free = d.label.eq('not listed') | d.label.str.startswith('practice/')  # production weight 0
    gone = np.array([roster.gone(y, w, t, pid) for y, w, t, pid in zip(d.season, d.week, d.team, d.gsis_id)], bool)
    d.loc[free & gone, 'label'] = 'game-week reserve/gone'
    d['loss'] = 1 - d.played / d.normal
    return d


def return_participation(s, roster, detail):
    """Regulars back from an absence (listed Out/Doubtful or on a reserve list for the team's
    previous game, not listed now): snaps played in the first game back against their normal
    share (mean of their last 4 games played before the absence, within 17 team games)."""
    s = s.assign(pct=s.snaps / s.team_snaps.where(s.team_snaps > 0))
    s = s.groupby(['season', 'week', 'game_id', 'team', 'gsis_id'], as_index=False).pct.max()
    rows = []
    for t, st in s.groupby('team'):
        games = st[['season', 'week', 'game_id']].drop_duplicates().sort_values(['season', 'week']).reset_index(drop=True)
        gi = {g: i for i, g in enumerate(games.game_id)}
        P = st.assign(gi=st.game_id.map(gi)).pivot_table(index='gi', columns='gsis_id', values='pct', aggfunc='max', fill_value=0.)
        P = P.reindex(range(len(games)), fill_value=0.)
        for i in range(1, len(games)):
            y, w = int(games.season[i]), int(games.week[i]); py, pw = int(games.season[i - 1]), int(games.week[i - 1])
            if py != y: continue  # returns within a season only
            out, ref = roster.status(y, w, t)
            for pid in roster.hard.get((py, pw, t), set()) | roster.out.get((py, pw, t), set()):
                if pid not in P.columns or out.get(pid, 0.) > 0 or (ref is not None and pid not in ref): continue
                col = P[pid].to_numpy()
                k = 0
                while k < i and col[i - 1 - k] == 0: k += 1
                h = col[max(0, i - k - 17):i - k]; h = h[h > 0][-4:]
                if len(h) < 2 or h.mean() < REGULAR: continue
                rows.append({'season': y, 'week': w, 'team': t, 'gsis_id': pid, 'missed': k,
                             'normal': float(h.mean()), 'played': float(col[i]), 'gone': roster.gone(y, w, t, pid)})
    d = pd.DataFrame(rows)
    lab = detail.set_index(['season', 'week', 'team', 'gsis_id']).label
    d['this_week'] = lab.reindex(pd.MultiIndex.from_arrays([d.season, d.week, d.team, d.gsis_id])).fillna('no report row').to_numpy()
    d['loss'] = 1 - d.played / d.normal
    return d


def qb_same_week(prod, qb, roster):
    """Team-games (weeks 2+) whose projected QB is on a game-week reserve list or gone, with the
    passer who actually started. The projection is matched to a passer id by name within the team."""
    scol = 'starter' if 'starter' in qb else 'leader'
    st = qb[qb[scol].astype(bool)].drop_duplicates(['season', 'week', 'team']).set_index(['season', 'week', 'team'])['name']
    ids = qb.drop_duplicates(['team', 'name']).set_index(['team', 'name']).gsis_id
    rows = []
    for r in prod[(prod.week > 1) & prod.qb_expected.notna()].itertuples():
        name = str(r.qb_expected).split(' (Q)')[0]
        pid = ids.get((r.team, name))
        if pid is not None and roster.gone(int(r.season), int(r.week), r.team, pid):
            rows.append({'season': r.season, 'week': r.week, 'team': r.team, 'projected': r.qb_expected,
                         'started': st.get((r.season, r.week, r.team)), 'qb_source': r.qb_source})
    return pd.DataFrame(rows, columns=['season', 'week', 'team', 'projected', 'started', 'qb_source'])


def status_table(d):
    def one(x):
        mu = np.average(x.loss, weights=x.wsnaps)
        return pd.Series({'n': len(x), 'did not play': (x.played == 0).mean(), 'loss': mu,
                          'se': np.sqrt(np.average((x.loss - mu) ** 2, weights=x.wsnaps) / len(x))})
    t = d.groupby('label').apply(one).reindex(ORDER)
    b = t.loc['not listed', 'loss']
    t['weight'] = (t.loss - b) / (1 - b)
    return t


# ---------------------------------------------------------------- B. window vs profile

def unit_variants(snaps, roster, targets, cal_weights):
    """Per (season, week, team): production unit columns (replicated), the practice-calibrated
    columns, and profile 'absent'/'return' on this-season and 3-season profiles."""
    s = unit_snaps(snaps); s['share'] = s.snaps / s.groupby(['game_id', 'team', 'group']).snaps.transform('sum')
    rows = []
    for t, tg in targets.groupby('team'):
        st = s[s.team == t]
        games = st[['season', 'week', 'game_id']].drop_duplicates().sort_values(['season', 'week']).reset_index(drop=True)
        gi = {g: i for i, g in enumerate(games.game_id)}
        miss_sets = [roster.hard.get((int(r.season), int(r.week), t), set()) | roster.out.get((int(r.season), int(r.week), t), set())
                     for r in games.itertuples()]
        list_sets = [roster.listed.get((int(r.season), int(r.week), t), set()) for r in games.itertuples()]
        mats = {}
        for G in GROUPS:
            u = st[st.group == G]
            P = u.assign(gi=u.game_id.map(gi)).pivot_table(index='gi', columns='gsis_id', values='share', aggfunc='sum', fill_value=0.)
            P = P.reindex(range(len(games)), fill_value=0.)
            cols = list(P.columns)
            missed = np.array([[pid in ms for pid in cols] for ms in miss_sets], bool).reshape(len(games), len(cols))
            on = np.array([[pid in ls for pid in cols] for ls in list_sets], bool).reshape(len(games), len(cols)) | (P.to_numpy() > 0)
            mats[G] = (P, missed, on)
        for r in tg.itertuples(index=False):
            y, w = int(r.season), int(r.week)
            prior = games[(games.season < y) | ((games.season == y) & (games.week < w))]
            cur = prior[prior.season == y]
            win4 = prior.index[-m.AVAIL_WINDOW:]
            wcs = cur.index[-m.AVAIL_WINDOW:] if len(cur) >= m.CS_MIN_GAMES else win4
            out, ref = roster.status(y, w, t); outc, _ = roster.status(y, w, t, weights=cal_weights)
            if ref is not None and len(win4):  # production's membership data-gap rule
                per = st[st.game_id.isin(games.game_id[win4])].groupby('gsis_id').snaps.sum()
                if per.sum() > 0 and per[~per.index.isin(ref)].sum() / per.sum() > m.MEMBERSHIP_MAX_SHARE: ref = None
            def unavail(pid, o):
                return 1. if (ref is not None and pid not in ref) else o.get(pid, 0.)
            rec = {'season': y, 'week': w, 'team': t}
            hist = {'cs': cur.index if len(cur) >= m.CS_MIN_GAMES else wcs,
                    'all': prior.index[(prior.season >= y - m.MAX_HISTORY_SEASONS).to_numpy()]}
            for G in GROUPS:
                P, missed, on = mats[G]; Pn = P.to_numpy()
                uv = np.array([unavail(pid, out) for pid in P.columns])
                sw = st[(st.group == G) & st.game_id.isin(games.game_id[wcs])].groupby('gsis_id').snaps.sum()
                for name, o in (('prod', out), ('cal', outc)):
                    rec[f'{name}_{G}'] = float(sum(v * unavail(pid, o) for pid, v in sw.items()) / sw.sum()) if sw.sum() > 0 else np.nan
                rec[f'samewk_{G}'] = (float(sum(v * (1 - unavail(pid, out)) for pid, v in sw.items() if roster.gone(y, w, t, pid)) / sw.sum())
                                      if sw.sum() > 0 else np.nan)
                for k, idx in hist.items():
                    if not len(idx): rec[f'absent_{k}_{G}'] = rec[f'return_{k}_{G}'] = np.nan; continue
                    W = profile_weights(games.season.to_numpy()[idx], y)
                    rec[f'absent_{k}_{G}'], rec[f'return_{k}_{G}'] = profile_measures(Pn[idx], W, uv, missed[idx], on[idx])
            rows.append(rec)
    v = pd.DataFrame(rows)
    for k in ('cs', 'all'):
        for G in GROUPS: v[f'linger_{k}_{G}'] = v[f'absent_{k}_{G}'] - v[f'prod_{G}']
    return v


def variant_table(v):
    rows = []
    for G in GROUPS:
        p = v[f'prod_{G}']
        rows.append({'unit': G, 'production mean': p.mean(), 'calibrated mean': v[f'cal_{G}'].mean(),
                     'corr(prod, cal)': p.corr(v[f'cal_{G}']),
                     'linger mean (this season)': v[f'linger_cs_{G}'].mean(),
                     'linger >= 0.10': (v[f'linger_cs_{G}'] >= .1).mean(),
                     'return mean (this season)': v[f'return_cs_{G}'].mean(),
                     'return >= 0.10': (v[f'return_cs_{G}'] >= .1).mean(),
                     'same-week mean': v[f'samewk_{G}'].mean(), 'same-week >= 0.10': (v[f'samewk_{G}'] >= .1).mean(),
                     'linger mean (3 seasons)': v[f'linger_all_{G}'].mean(),
                     'return mean (3 seasons)': v[f'return_all_{G}'].mean()})
    return pd.DataFrame(rows).set_index('unit')


# ---------------------------------------------------------------- C. market pricing

def ols_cluster(X, y, groups):
    """OLS with standard errors clustered on `groups` (season-week). Columns constant within the
    rows (e.g. a feature that is zero in every week-1 game) are dropped and reported as NaN."""
    keep = np.asarray(X).std(0) > 1e-12
    Xk = np.column_stack([np.ones(len(y)), np.asarray(X)[:, keep]])
    XtX = np.linalg.inv(Xk.T @ Xk); bk = XtX @ Xk.T @ y; e = y - Xk @ bk
    meat = np.zeros((Xk.shape[1],) * 2)
    for g in np.unique(groups):
        sc = Xk[groups == g].T @ e[groups == g]; meat += np.outer(sc, sc)
    b = np.full(keep.size, np.nan); se = np.full(keep.size, np.nan)
    b[keep] = bk[1:]; se[keep] = np.sqrt(np.diag(XtX @ meat @ XtX))[1:]
    return b, se, 1 - e.var() / y.var()


WEEK_GROUPS = (('all weeks', 1, 18), ('weeks 1–4', 1, 4), ('weeks 5+', 5, 18))
FINE_WEEKS = (('weeks 1–2', 1, 2), ('weeks 3–4', 3, 4), ('weeks 5–9', 5, 9), ('weeks 10–13', 10, 13), ('weeks 14–18', 14, 18))


def market_pricing(f, v, coef, groups=WEEK_GROUPS, profiles=('cs', 'all')):
    """Add signals in model log-odds; return the regression table by week group."""
    vv = v.set_index(['season', 'week', 'team'])
    def d(col):
        h = vv[col].reindex(pd.MultiIndex.from_arrays([f.season, f.week, f.home])).to_numpy(float)
        a = vv[col].reindex(pd.MultiIndex.from_arrays([f.season, f.week, f.away])).to_numpy(float)
        return np.nan_to_num(h - a)
    f = f.copy()
    f['S_prod'] = sum(coef[G] * d(f'prod_{G}') for G in GROUPS)
    f['S_cal'] = sum(coef[G] * (d(f'cal_{G}') - d(f'prod_{G}')) for G in GROUPS)
    f['S_samewk'] = sum(coef[G] * d(f'samewk_{G}') for G in GROUPS)
    for k in ('cs', 'all'):
        f[f'S_linger_{k}'] = sum(coef[G] * d(f'linger_{k}_{G}') for G in GROUPS)
        f[f'S_return_{k}'] = sum(-coef[G] * d(f'return_{k}_{G}') for G in GROUPS)
    units = [f'd__avail__{G}_out_cs' for G in GROUPS]
    base = [n for n in m.feature_names(FROZEN['family']) if n not in units]
    out = []
    for label, lo, hi in groups:
        rows = f[f.week.between(lo, hi)]
        for k in profiles:
            sig = ['S_prod', 'S_cal', 'S_samewk', f'S_linger_{k}', f'S_return_{k}']
            X = np.nan_to_num(rows[base + sig].to_numpy(float))
            b, se, r2 = ols_cluster(X, rows.mkt.to_numpy(float), (rows.season * 100 + rows.week).to_numpy())
            r = {'rows': label, 'profile': {'cs': 'this season', 'all': '3 seasons'}[k], 'games': len(rows), 'R2': r2,
                 'dropped': [c for c, bb in zip(base + sig, b) if not np.isfinite(bb)]}
            for j, sname in enumerate(sig):
                r[sname.replace(f'_{k}', '')] = (b[len(base) + j], se[len(base) + j], float(rows[sname].std()))
            out.append(r)
    return out, f


def md(df, digits=3):
    df = df.round(digits)
    head = '| ' + ' | '.join([str(df.index.name or '')] + [str(c) for c in df.columns]) + ' |'
    sep = '|---|' + '---:|' * len(df.columns)
    return '\n'.join([head, sep] + ['| ' + ' | '.join([str(i)] + [str(x) for x in r]) + ' |' for i, r in zip(df.index, df.values)])


def main():
    m.GAME_WEEK_RESERVE = False  # Test 28 audits v1.14 production; v1.15 adopted its same-week finding
    inp = load_inputs(cache_dir_from_argv())
    a = inp['a']
    years = sorted(int(y) for y in inp['sched'].season.unique())
    detail = load_injury_detail(years)
    roster = Roster(a['rost'], a['inj'])
    log('roster and injury detail ready')

    # A
    d = participation(unit_snaps(a['snaps']), detail, roster)
    fit = d[d.season.between(*FIT_SEASONS)]
    t_fit, t_all, t_test = status_table(fit), status_table(d), status_table(d[d.season >= 2023])
    print('\n## A. Snap loss by status (regulars in the window; weight = excess loss over not listed, Out = 1)\n')
    print('| Status | Players | Did not play | Snap loss ± SE | Weight 2019–22 | Weight 2023–25 | Production |\n|---|---:|---:|---:|---:|---:|---:|')
    prod_w = {'Out': 1., 'Doubtful': 1., 'roster out': 1.}
    for k in ORDER:
        r = t_all.loc[k]
        pw = prod_w.get(k, m.STATUS_WEIGHT['Questionable'] if k.startswith('Q/') else 0.)
        print(f'| {k} | {int(r.n)} | {r["did not play"]:.1%} | {r.loss:.3f} ± {r.se:.3f} | {t_fit.loc[k, "weight"]:.2f} | '
              f'{t_test.loc[k, "weight"]:.2f} | {pw:.2f} |')
    q = d[d.label.str.startswith('Q/')]; b = t_all.loc['not listed', 'loss']
    print(f'\nAll Questionable pooled weight: {(np.average(q.loss, weights=q.wsnaps) - b) / (1 - b):.3f} (production 0.25)')
    cal = {k: float(t_fit.loc[k, 'weight']) for k in ('Q/Full', 'Q/Lim', 'Q/DNP', 'Q/-', 'practice/DNP')}
    te = d[(d.season >= 2023) & d.label.str.startswith('Q/')]
    bt = t_test.loc['not listed', 'loss']; yv = ((te.loss - bt) / (1 - bt)).clip(-1, 1)
    for name, pred in (('production 0.25', np.full(len(te), .25)), ('practice-calibrated (2019–22)', te.label.map(cal).to_numpy())):
        print(f'2023–25 Questionable regulars, snap-weighted MSE of realized excess loss, {name}: '
              f'{np.average((yv - pred) ** 2, weights=te.wsnaps):.4f}')
    by = d.groupby('season').apply(lambda x: status_table(x).weight).reindex(columns=['Q/Full', 'Q/Lim', 'Q/DNP', 'practice/DNP', 'Doubtful', 'roster out'])
    print('\nWeight by season\n' + by.round(2).to_string())
    rp = return_participation(unit_snaps(a['snaps']), roster, detail)
    rp['missed games'] = pd.cut(rp.missed, [0, 1, 3, 99], labels=['1', '2–3', '4+'])
    rp['report'] = np.where(rp.this_week.str.startswith('practice/') & ~rp.this_week.eq('practice/DNP'), 'practice Full/Lim',
                            rp.this_week)
    rp['game week'] = np.where(rp.gone, 'reserve/gone', 'on roster')
    print('\nFirst game back from an absence (production counts him available), snap loss vs normal share; '
          f'not listed baseline {b:.3f}\n\n| This week | Game-week roster | Games missed | Players | Did not play | Snap loss ± SE |'
          '\n|---|---|---|---:|---:|---:|')
    for (rep, gw, k), x in rp.groupby(['report', 'game week', 'missed games'], observed=True):
        mu = np.average(x.loss, weights=x.normal); se = np.sqrt(np.average((x.loss - mu) ** 2, weights=x.normal) / len(x))
        print(f'| {rep} | {gw} | {k} | {len(x)} | {(x.played == 0).mean():.1%} | {mu:.3f} ± {se:.3f} |')
    gw = d[(d.week >= 5) & (d.season >= 2022)]
    wprod = gw.label.map({'Out': 1., 'Doubtful': 1., 'roster out': 1.}).fillna(
        gw.label.str.startswith('Q/').astype(float) * m.STATUS_WEIGHT['Questionable'])
    print(f'\n2022–25 weeks 5+: same-week reserve/gone regulars carry '
          f'{(gw.wsnaps * gw.label.eq("game-week reserve/gone")).sum() / (gw.wsnaps * wprod).sum():.1%} '
          'of the window snaps production counts out')
    log('A done')

    # B
    det = detail.assign(w=[calibrated_weight(lbl, cal) for lbl in detail.label])
    cal_weights = {k: g.groupby('gsis_id').w.max().to_dict() for k, g in det.groupby(['season', 'week', 'team'])}
    targets = inp['targets'][['season', 'week', 'team']].drop_duplicates()
    v = unit_variants(a['snaps'], roster, targets[targets.season <= 2025], cal_weights)
    prod = availability(inp)
    j = v.merge(prod, on=['season', 'week', 'team'])
    gap = max(float(np.nanmax(np.abs(j[f'prod_{G}'] - j[f'{G}_out_cs']))) for G in GROUPS)
    print(f'\nReplication of production unit columns on {len(j)} team-weeks: max |difference| = {gap:.2e}')
    qs = qb_same_week(prod, inp['qb'], roster)
    print(f'\nProjected QB on a game-week reserve list or gone (weeks 2+): {len(qs)} team-games, by rule '
          f'{qs.qb_source.value_counts().to_dict()}; projected passer started {(qs.projected == qs.started).sum()}\n'
          + qs.sort_values(['season', 'week']).to_string(index=False))
    print('\n## B. Window vs profile, 2021–25 team-weeks (unit snap shares)\n')
    print(md(variant_table(v[v.season >= 2021])))
    v['wg'] = pd.cut(v.week, [0, 2, 4, 9, 13, 18], labels=['1–2', '3–4', '5–9', '10–13', '14–18'])
    cols = [f'{k}_{G}' for G in ('OL', 'WRTE', 'DB') for k in ('prod', 'linger_cs', 'return_cs')]
    print('\nBy week, mean\n' + md(v[v.season >= 2021].groupby('wg', observed=True)[cols].mean()))
    log('B done')

    # C
    f = m.lagged_features(inp['box'], inp['sched'], PROFILE_HALF_LIFE, prod)
    fit26 = m.fit_composite(f, FROZEN, 2026, 1)
    beta = dict(zip(fit26['names'], np.asarray(fit26['beta']) / np.asarray(fit26['scale'])))
    coef = {G: beta[f'd__avail__{G}_out_cs'] for G in GROUPS}
    print('\nUnit coefficients, log-odds per unit share (frozen recipe fit on games through 2025):',
          {G: round(c, 3) for G, c in coef.items()})
    f = m.attach_moneylines(f, inp['sched'])
    q = m.market_ml_wp(f); q = np.where(np.isfinite(q), q, f.market_wp.to_numpy(float))
    f = f.assign(mkt=logit(np.clip(q, 1e-4, 1 - 1e-4)))
    f = f[(f.season >= 2021) & (f.season <= 2025) & f.ready & np.isfinite(f.mkt)].reset_index(drop=True)
    res, f = market_pricing(f, v, coef)
    print('\n## C. Market log-odds per model log-odds of each signal (clustered by week; SD = signal SD)\n')
    print('| Rows | Profile | Games | Production units | Practice calibration | Same-week reserve | Lingering absence | Return credit |'
          '\n|---|---|---:|---:|---:|---:|---:|---:|')
    for r in res:
        cells = ' | '.join(f'{r[k][0]:+.2f} ± {r[k][1]:.2f} (SD {r[k][2]:.3f})' for k in ('S_prod', 'S_cal', 'S_samewk', 'S_linger', 'S_return'))
        print(f"| {r['rows']} | {r['profile']} | {r['games']} | {cells} |")
    for k in ('S_prod', 'S_cal', 'S_samewk', 'S_linger_cs', 'S_return_cs'):
        print(f'{k}: games with |signal| >= 0.10 log-odds: {(f[k].abs() >= .1).mean():.1%}')
    sig = ['S_prod', 'S_cal', 'S_samewk', 'S_linger_cs', 'S_return_cs', 'S_linger_all', 'S_return_all']
    print('\nSignal correlations\n' + f[sig].corr().round(2).to_string())
    if len(sys.argv) > 2:
        out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
        v.drop(columns='wg').to_parquet(out / 'unit_variants.parquet'); d.to_parquet(out / 'participation.parquet')
        f[['game_id', 'season', 'week', 'home', 'away', 'mkt'] + sig].to_parquet(out / 'market_signals.parquet')
    def table(res, title):
        print(f'\n{title}\n\n| Rows | Games | Production units | Practice calibration | Same-week reserve | Lingering absence | Return credit |'
              '\n|---|---:|---:|---:|---:|---:|---:|')
        for r in res:
            cells = ' | '.join(f'{r[k][0]:+.2f} ± {r[k][1]:.2f}' for k in ('S_prod', 'S_cal', 'S_samewk', 'S_linger', 'S_return'))
            print(f"| {r['rows']} | {r['games']} | {cells} |" + (f"  (constant, dropped: {', '.join(r['dropped'])})" if r['dropped'] else ''))
    table(market_pricing(f, v, coef, FINE_WEEKS, ('cs',))[0], 'By week, this-season profile')
    eq = {G: -float(np.mean(np.abs(list(coef.values())))) for G in GROUPS}
    table(market_pricing(f, v, eq, WEEK_GROUPS, ('cs',))[0],
          f'Robustness: every unit at the mean |coefficient| ({eq["OL"]:+.3f}), this-season profile')
    log('done')


if __name__ == '__main__':
    main()
