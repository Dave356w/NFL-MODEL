"""Exploratory (not pre-registered): is the coefficient logic of fit_composite well tuned?

    python research/coefficient_diagnostics.py [CACHE_DIR]     # ~8 min warm

Production features and the walk-forward 2021-25 exactly as walk_forward_grid, with a
reimplemented fit that exposes the settings production fixes: the ridge value, the decay of
older training games (FIT_HALF_LIFE_SEASONS), sign constraints from the direction map, and the
site-penalty ratio. Grids are compared with nested selection (each held-out season's recipe
chosen on earlier seasons only). Also: coefficients fit with lookahead on the season being
predicted (a ceiling that flatters the model), and coefficient stability over 2023-25 refits.
Post-hoc on seasons used by earlier tests: hypotheses only. See research/README.md.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit

from _common import LAST, OUTER, availability, boot_ci, cache_dir_from_argv, load_inputs, log, m
from margin_target import expected_sign

FAM_ADJ, FAM_RAW = 'rates_core_adj_avail_cs_margin', 'rates_core_avail_cs_margin'


def fit(train, family, ridge, year, week, fit_hl=None, signs=False, site_pen=.1):
    """fit_composite with its fixed settings exposed (defaults reproduce production)."""
    fit_hl = m.FIT_HALF_LIFE_SEASONS if fit_hl is None else fit_hl
    t = train[train['home won'].isin([0., 1.]) & train.ready]
    names = m.feature_names(family)
    raw = t[names].to_numpy(float); X = np.where(np.isfinite(raw), raw, 0.)
    age = ((year - t.season.to_numpy()) * 19 + (week - t.week.to_numpy())) / (19 * fit_hl)
    w = np.exp2(-age); w /= w.sum()
    mu = np.sum(w[:, None] * X, axis=0)
    scale = np.sqrt(np.sum(w[:, None] * (X - mu) ** 2, axis=0)); scale = np.where(scale > 1e-8, scale, 1.); scale[0] = 1.
    Z = X / scale; y = t['home won'].to_numpy(float)
    pen = np.full(len(names), float(ridge)); pen[0] *= site_pen

    def obj(b):
        eta = Z @ b
        return (np.sum(w * (np.logaddexp(0, eta) - y * eta)) + .5 * np.sum(pen * b * b),
                Z.T @ (w * (expit(eta) - y)) + pen * b)
    bounds = ([(0, None) if expected_sign(n) > 0 else (None, 0) if expected_sign(n) < 0 else (None, None) for n in names]
              if signs else None)
    o = minimize(obj, np.zeros(len(names)), jac=True, method='L-BFGS-B', bounds=bounds,
                 options={'maxiter': 3000, 'gtol': 1e-9, 'ftol': 1e-13})
    return {'names': names, 'scale': scale, 'beta': o.x}


def apply(df, f):
    x = df[f['names']].to_numpy(float)
    return expit((np.where(np.isfinite(x), x, 0.) / f['scale']) @ f['beta'])


def main():
    inp = load_inputs(cache_dir_from_argv())
    sched, avail = inp['sched'], availability(inp)
    feats = {h: m.lagged_features(inp['box'], sched, h, avail) for h in m.TEAM_HALF_LIVES}
    log('features built')
    oof = m.walk_forward_grid(feats, LAST)
    first = feats[m.TEAM_HALF_LIVES[0]]
    valid = ((first.season >= m.BACKTEST_FIRST_SEASON) & (first.season <= LAST)
             & first['home won'].isin([0., 1.]) & first.ready)
    base = first.loc[valid, ['game_id', 'season', 'week', 'home won']].reset_index(drop=True)
    if not (oof.game_id.to_numpy() == base.game_id.to_numpy()).all(): raise ValueError('row order')
    y = base['home won'].to_numpy(float); seas = base.season.to_numpy(); held = seas >= OUTER[0]

    def walk(h, family, ridge, **kw):
        f = feats[h]; p = pd.Series(np.nan, index=f.index)
        for (yr, wk), te in f.loc[valid].groupby(['season', 'week'], sort=True):
            p.loc[te.index] = apply(te, fit(f[m.before(f, int(yr), int(wk))], family, ridge, int(yr), int(wk), **kw))
        return p.loc[valid].to_numpy()

    p0 = walk(16., FAM_ADJ, .1)
    log(f"reimplemented fit vs production (adj h16 r0.1): max |diff| "
        f"{np.max(np.abs(p0 - oof['p__rates_core_adj_avail_cs_margin_h16_r0.1'].to_numpy())):.1e}")
    rows, preds = [], {}
    for fam, fl in ((FAM_ADJ, 'adj'), (FAM_RAW, 'raw')):
        for h in (8., 16.):
            arms = ([('ridge', r, {}) for r in (.02, .03, .05, .1, .2, .3, .5, 1.)]
                    + [('fit half-life', .1, {'fit_hl': hl}) for hl in (.5, 1., 4., np.inf)]
                    + [('sign-constrained', r, {'signs': True}) for r in (.01, .03, .1, .3, 1.)]
                    + [('site penalty', .1, {'site_pen': sp}) for sp in (0., 1.)])
            for label, r, kw in arms:
                p = walk(h, fam, r, **kw); l = m.ll(y, p)
                key = f'{label} {fl} h{h:g} r{r:g} ' + ' '.join(f'{k}={v:g}' for k, v in kw.items())
                preds[key] = p
                rows.append({'arm': label, 'family': fl, 'h': h, 'ridge': r, **kw,
                             'LL 2021-22': l[seas <= 2022].mean(), 'LL 2023-25': l[held].mean(),
                             **{str(s): l[seas == s].mean() for s in range(m.BACKTEST_FIRST_SEASON, LAST + 1)}})
    log('sweeps done')
    pd.set_option('display.width', 250)
    print('\nWalk-forward log loss by setting (production: ridge 0.1, fit half-life 2, no sign constraints, site penalty 0.1)')
    print(pd.DataFrame(rows).round(5).to_string(index=False))

    prod = {k[3:]: oof[k].to_numpy() for k in oof.columns if k.startswith('p__')}

    def nested(cands):
        out = np.full(len(base), np.nan); picks = {}
        for yr in OUTER:
            tr = seas < yr
            best = min(cands, key=lambda k: m.ll(y[tr], cands[k][tr]).mean()); picks[yr] = best
            out[seas == yr] = cands[best][seas == yr]
        return out, picks
    pp, pk = nested(prod)
    print(f'\nNested selection, held-out {OUTER[0]}-{OUTER[-1]} (n={held.sum()}). Production picks {pk}, LL {m.ll(y[held], pp[held]).mean():.4f}')
    print('| Production grid plus | Picks | LL gain vs production [95% CI] |\n|---|---|---:|')
    for label in ('ridge', 'fit half-life', 'sign-constrained', 'site penalty'):
        pv, pkv = nested({**prod, **{k: v for k, v in preds.items() if k.startswith(label)}})
        g = (m.ll(y, pp) - m.ll(y, pv))[held]; lo, hi = boot_ci(g, .95)
        print(f'| {label} | {pkv} | {g.mean():+.4f} [{lo:+.4f}, {hi:+.4f}] |')

    print('\nLookahead ceiling (production recipe adj h16 r0.1), held-out season log loss:')
    print('| Season | Walk-forward | Fit including the season (2-season decay) | Fit on the season alone | Market spread |\n|---|---:|---:|---:|---:|')
    f = feats[16.]
    for yr in OUTER:
        te = f[(f.season == yr) & f['home won'].isin([0., 1.]) & f.ready]; yy = te['home won'].to_numpy(float)
        thru = fit(f[(f.season <= yr) & f['home won'].isin([0., 1.]) & f.ready], FAM_ADJ, .1, yr + 1, 1)
        alone = fit(te, FAM_ADJ, .1, yr + 1, 1, fit_hl=np.inf)
        print(f'| {yr} | {m.ll(y[seas == yr], p0[seas == yr]).mean():.4f} | {m.ll(yy, apply(te, thru)).mean():.4f} | '
              f'{m.ll(yy, apply(te, alone)).mean():.4f} | {m.ll(yy, te.market_wp.to_numpy(float)).mean():.4f} |')

    betas = []
    for (yr, wk), te in f.loc[valid & (f.season >= OUTER[0])].groupby(['season', 'week'], sort=True):
        betas.append(fit(f[m.before(f, int(yr), int(wk))], FAM_ADJ, .1, int(yr), int(wk))['beta'])
    B = np.array(betas); names = m.feature_names(FAM_ADJ)
    st = pd.DataFrame({'feature': names, 'expected sign': [expected_sign(n) for n in names], 'mean': B.mean(0),
                       'SD across weeks': B.std(0), 'share of fits with the minority sign':
                       [(np.sign(B[:, i]) != np.sign(B[:, i].mean())).mean() for i in range(len(names))]})
    print(f'\nCoefficient stability, production recipe, {len(B)} weekly refits {OUTER[0]}-{OUTER[-1]} (per scaled unit):')
    print(st.round(3).to_string(index=False))
    log('done')


if __name__ == '__main__':
    main()
