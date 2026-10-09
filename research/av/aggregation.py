"""Team-week unit values from projected participation and pregame player rates.

For player i in unit u:  V_i = (rate_i - rep_u) x p_i   (replacement-relative)  or  rate_i x p_i (raw).
rate and rep are both rAV per full game and p is a share of team snaps, so V is rAV for this game.

  linear      unit value = sum_i V_i
  weak-link   OL: the 5 projected starters (largest p) ordered by value, best to worst, weighted
              5 x [.15, .15, .20, .25, .25] (the weakest starters weigh most); DB: the 4 base-defense
              starters, 4 x [.20, .20, .30, .30]. Starters count as full-time; everyone else linear.
              A missing starter slot is filled at replacement level (value 0).
  min         ablation: starters' mean replaced by N x the weakest starter's value.

Also per unit: the same value with everyone healthy and still on the team (`full_*`), so
`loss_u = rel_u - full_rel_u` is the AV-weighted absence net of replacement (the Model C input).
Counts for pre-specified subgroups: starters out (base share >= .5, multiplier <= .15, still on the team:
Out/Doubtful or a roster-out code; offseason and in-season departures are not counted) and
roster continuity (share of last season's unit snaps with this team held by current members).
"""
import numpy as np
import pandas as pd

from availability import STARTER_SHARE, waterfill
from prepare_data import UNITS

WEAK = {'OL': (5, (.15, .15, .20, .25, .25)), 'DB': (4, (.20, .20, .30, .30))}
MODES = ('prior', 'blend')


def weak_value(p, v, n, w):
    """Weighted lower-tail value of the n largest-share players; the rest enter linearly."""
    order = np.argsort(-p, kind='stable')
    st, rest = order[:n], order[n:]
    sv = np.sort(np.r_[v[st], np.zeros(max(0, n - len(st)))])[::-1]
    weak = float(n * np.dot(np.asarray(w), sv))
    lin_rest = float(np.dot(p[rest], v[rest])) if len(rest) else 0.
    return weak + lin_rest, float(n * sv.min()) + lin_rest


def unit_values(p, rate, rep, unit):
    v = rate - rep
    out = {'raw': float(np.dot(p, rate)), 'rel': float(np.dot(p, v))}
    if unit in WEAK:
        n, w = WEAK[unit]
        out['weak'], out['min'] = weak_value(p, v, n, w)
    else:
        out['weak'] = out['min'] = out['rel']
    return out


def team_week_features(part, est, y, w, t, audit=None):
    df, slots, info = part.team_week(y, w, t)
    rep = est.replacement(y)
    rec = {'season': y, 'week': w, 'team': t, **{k: info[k] for k in ('ref_week', 'membership_gap', 'continuity')}}
    starters_out = 0
    qb_matched = None
    for u in UNITS:
        g = df[df.unit == u].reset_index(drop=True)
        rates = {md: np.array([est.rate(pid, u, y, w, md)[0] for pid in g.gsis_id]) for md in MODES}
        base, mult = g.base.to_numpy(float), g.mult.to_numpy(float)
        full_mult = np.ones(len(g))
        if u == 'QB':
            tq = part.qb_targets(y, w, t, list(g.gsis_id))
            qb_matched = tq is not None
            if tq is not None:
                p = np.array([tq.get(pid, 0.) for pid in g.gsis_id])
            else:
                p, _ = waterfill(base, mult, 1.)
            pf, _ = waterfill(base, full_mult, 1.)
        else:
            p, _ = waterfill(base, mult, slots[u])
            pf, _ = waterfill(base, full_mult, slots[u])
        starters_out += int(((base >= STARTER_SHARE) & (mult <= .15) & ~g.departed.to_numpy(bool)).sum())
        for md in MODES:
            vals = unit_values(p, rates[md], rep[u], u) if len(g) else {'raw': 0., 'rel': 0., 'weak': 0., 'min': 0.}
            full = unit_values(pf, rates[md], rep[u], u) if len(g) else vals
            for k, v in vals.items(): rec[f'{k}_{u}_{md}'] = v
            rec[f'full_rel_{u}_{md}'] = full['rel']
            rec[f'loss_{u}_{md}'] = vals['rel'] - full['rel']
        rec[f'slots_{u}'] = slots[u]
        if audit is not None and len(g):
            audit.append(g.assign(season=y, week=w, team=t, proj_share=p, full_share=pf,
                                  rate_prior=rates['prior'], rate_blend=rates['blend'], rep=rep[u]))
    rec['starters_out'] = starters_out
    rec['qb_matched'] = qb_matched
    return rec


def build(part, est, targets, audit=None, log=None):
    rows = []
    keys = targets[['season', 'week', 'team']].drop_duplicates().sort_values(['season', 'week', 'team'])
    for i, r in enumerate(keys.itertuples(index=False)):
        rows.append(team_week_features(part, est, int(r.season), int(r.week), r.team, audit))
        if log and i % 500 == 0: log(f'  AV features {i}/{len(keys)}')
    return pd.DataFrame(rows)
