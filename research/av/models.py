"""Models B (pure rAV), C (v1.15 + rAV availability) and D (rAV roster prior + dynamic residual).

All fits follow production's walk-forward conventions: refit before every week on labeled games from
earlier weeks only (ties excluded), training weights halve every FIT_HALF_LIFE_SEASONS, features scaled
by their weighted RMS without centering and no intercept (a neutral site is exactly symmetric).

B   home margin = b_site site + sum_u b_u dAV_u, weighted ridge (lambda pseudo-games); win probability
    Phi(mu / sigma) with sigma the weighted residual RMS of the same earlier games.
C   production logistic composite (nfl_model.fit_composite) with feature names rewritten:
      C1  unit absence shares (*_out_cs) -> rAV unit losses (loss_u), QB efficiency term kept
      C2  both representations, the ridge grid regularizes
      C3  C1 with the QB efficiency term replaced by the QB rAV loss (does QB rAV substitute?)
D   mu_D = mu_roster + alpha_home - alpha_away, mu_roster = the B walk-forward margin actually available
    before each game (never an in-sample fit). Team state from completed games tau < t:
        alpha_k = sum lambda^a rho^(seasons) r_k,tau / (sum lambda^a rho^(seasons) + gamma)
    a = team games played since tau, rho = OFFSEASON_RETENTION per season boundary.
      D1  r = MOV - mu_roster (home residual; the away team gets exactly its negative)
      D2  opponent-adjusted: r = MOV - mu_roster + alpha_opp(pregame at tau)
    sigma from earlier games' D residuals, as in B.
"""
import numpy as np
import pandas as pd
from scipy.special import ndtr

from _common import m
from prepare_data import UNITS

B_RIDGE = (1., 10., 100., 1000.)
D_LAMBDA = (.85, .90, .92)
D_GAMMA = (1., 4., 12.)  # small / medium / strong, in team-game equivalents
NON_QB = tuple(u for u in UNITS if u != 'QB')
B_SPECS = {'B1': 'raw', 'B2': 'weak', 'B2rel': 'rel', 'B2min': 'min'}  # B2rel/B2min are ablations


def b_columns(kind, mode):
    return ['site'] + [f'd__av__{kind}_{u}_{mode}' for u in UNITS]


def fit_weights(t, year, week):
    age = ((year - t.season.to_numpy()) * 19 + (week - t.week.to_numpy())) / (19 * m.FIT_HALF_LIFE_SEASONS)
    w = np.exp2(-age); return w / w.sum()


def fit_margin(train, cols, lam, year, week):
    """Weighted ridge of home margin on `cols` using games strictly before (year, week)."""
    t = train[train['home won'].isin([0., 1.])]
    if not m.before(t, year, week).all(): raise ValueError('Training includes current/future week')
    if len(t) < m.MIN_TRAIN_GAMES: return None
    X = np.nan_to_num(t[cols].to_numpy(float)); y = t.result.to_numpy(float)
    w = fit_weights(t, year, week)
    scale = np.sqrt(np.sum(w[:, None] * X ** 2, axis=0)); scale = np.where(scale > 1e-8, scale, 1.); scale[0] = 1.
    Z = X / scale
    neff = 1. / np.sum(w * w)
    pen = np.full(len(cols), lam / neff); pen[0] *= .1
    beta = np.linalg.solve(Z.T @ (w[:, None] * Z) + np.diag(pen), Z.T @ (w * y))
    sigma = float(np.sqrt(np.sum(w * (y - Z @ beta) ** 2)))
    return {'cols': cols, 'scale': scale, 'beta': beta, 'sigma': sigma, 'n': len(t)}


def apply_margin(df, fit):
    return (np.nan_to_num(df[fit['cols']].to_numpy(float)) / fit['scale']) @ fit['beta']


def walk_forward_margin(f, cols, lam):
    """B walk-forward over every (season, week) of `f` with enough earlier games. Returns mu, sigma."""
    mu = pd.Series(np.nan, index=f.index); sg = pd.Series(np.nan, index=f.index)
    for (y, w), te in f.groupby(['season', 'week'], sort=True):
        fit = fit_margin(f[m.before(f, int(y), int(w))], cols, lam, int(y), int(w))
        if fit is None: continue
        mu.loc[te.index] = apply_margin(te, fit); sg.loc[te.index] = fit['sigma']
    return mu, sg


def team_residual_states(f, mu, lam, gamma, opponent_adjust=False):
    """Pregame alpha for home and away of every row of `f` (sorted by season, week), from residuals of
    games in EARLIER weeks only. A week's games update the states after the whole week is predicted."""
    hist = {}  # team -> list of (season, residual)
    ah = np.zeros(len(f)); aa = np.zeros(len(f))
    rho = m.OFFSEASON_RETENTION

    def state(team, y):
        h = hist.get(team)
        if not h: return 0.
        s = np.array([x[0] for x in h], float); r = np.array([x[1] for x in h], float)
        a = np.arange(len(h) - 1, -1, -1, dtype=float)
        wt = lam ** a * rho ** (y - s)
        return float(np.dot(wt, r) / (wt.sum() + gamma))

    pos = {ix: i for i, ix in enumerate(f.index)}
    for (y, w), g in f.groupby(['season', 'week'], sort=True):
        y = int(y); upd = []
        for ix, r in g.iterrows():
            i = pos[ix]; ah[i] = state(r.home, y); aa[i] = state(r.away, y)
            if pd.notna(r.result) and pd.notna(mu.loc[ix]):
                res = float(r.result) - float(mu.loc[ix])
                if opponent_adjust: upd.append((r.home, res + aa[i])); upd.append((r.away, -res + ah[i]))
                else: upd.append((r.home, res)); upd.append((r.away, -res))
        for team, res in upd: hist.setdefault(team, []).append((y, res))
    return ah, aa


def walk_forward_sigma(f, mu):
    """sigma for each week from earlier weeks' residuals (production fit weights)."""
    sg = pd.Series(np.nan, index=f.index)
    ok = f.result.notna() & mu.notna() & f['home won'].isin([0., 1.])
    for (y, w), te in f.groupby(['season', 'week'], sort=True):
        tr = f[ok & m.before(f, int(y), int(w))]
        if len(tr) < m.MIN_TRAIN_GAMES: continue
        wt = fit_weights(tr, int(y), int(w))
        sg.loc[te.index] = float(np.sqrt(np.sum(wt * (tr.result - mu[tr.index]) ** 2)))
    return sg


def wp(mu, sigma):
    return pd.Series(ndtr(np.asarray(mu, float) / np.asarray(sigma, float)), index=mu.index)


# ---- Model C: feature-name rewrite of the production families (research process only) ----
C_VARIANTS = ('C1', 'C2', 'C3')
C_MODE = 'blend'
_orig_feature_names = m.feature_names


def c_feature_names(family):
    if '__' not in family: return _orig_feature_names(family)
    base, var = family.split('__')
    names = _orig_feature_names(base)
    unit_out = [f'd__avail__{g}_out_cs' for g in m.OFFENSE_GROUPS + m.DEFENSE_GROUPS]
    loss = [f'd__av__loss_{u}_{C_MODE}' for u in NON_QB]
    if var == 'C1': return [c for c in names if c not in unit_out] + loss
    if var == 'C2': return names + loss
    if var == 'C3':
        return [c for c in names if c not in unit_out and c != 'd__avail__qb_delta'] + loss + [f'd__av__loss_QB_{C_MODE}']
    raise ValueError(family)


def install_c():
    m.feature_names = c_feature_names


def attach_av(f, av):
    """Add d__av__* (home minus away) and per-side subgroup fields to a game frame."""
    cols = [c for c in av.columns if c not in ('season', 'week', 'team', 'ref_week', 'membership_gap', 'qb_matched')]
    a = av.set_index(['season', 'week', 'team'])[cols]
    h = a.reindex(pd.MultiIndex.from_arrays([f.season, f.week, f.home])).to_numpy(float)
    w = a.reindex(pd.MultiIndex.from_arrays([f.season, f.week, f.away])).to_numpy(float)
    out = f.copy()
    extra = {}
    for j, c in enumerate(cols):
        if c in ('starters_out', 'continuity'):
            extra[f'home_{c}'] = h[:, j]; extra[f'away_{c}'] = w[:, j]
        else:
            extra[f'd__av__{c}'] = h[:, j] - w[:, j]
    return pd.concat([out, pd.DataFrame(extra, index=out.index)], axis=1)
