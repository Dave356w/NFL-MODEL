"""Test 28: margin as the fitting target (arm M), and a schedule-adjusted margin (arm A).

    python research/margin_target.py [CACHE_DIR]     # ~15 min warm

Plan and decision rule: research/README.md, Test 28 (committed before any result).
- M: same features, standardization, time-decay weights and site-penalty ratio as
  fit_composite, but weighted ridge least squares on the home point margin (ties
  included as 0); win probability Phi(mu / sigma), sigma = weighted RMS training residual.
  Ridge grid = production grid x 5 (logistic curvature p(1 - p) ~ 0.2).
- A: production logistic fit with d__margin replaced by d__margin_adj = r_home - r_away,
  ratings from a weighted ridge fit of earlier games' home margins on a home-site term
  plus r_home - r_away (the _adj family's league-week-slot decay, OFFSEASON_RETENTION,
  MAX_HISTORY_SEASONS; PRIOR_EQUIVALENT_GAMES of ridge on each rating).
- M + A: reported, not decisive.
Each held-out season's recipe is the minimum mean walk-forward log loss on earlier seasons.
"""
import numpy as np
import pandas as pd
from scipy.special import ndtr

from _common import (DHEAD, HEAD, LAST, OUTER, availability, cache_dir_from_argv, diff_row, load_inputs, log, m,
                     outer, row, score)

PROD = tuple(m.FEATURE_FAMILIES)                     # v1.12 families (raw margin)
ADJ = tuple(f + '_madj' for f in PROD)               # arm A: schedule-adjusted margin
LS_RIDGES = tuple(5. * r for r in m.RIDGE_GRID)      # arm M ridge grid
ADJ_FEATURE = 'd__margin_adj'
WEEK_GROUPS = ((1, 4, '1–4'), (5, 9, '5–9'), (10, 13, '10–13'), (14, 17, '14–17'), (18, 18, '18'))
BOOT = 4000
_base_names = m.feature_names


def feature_names(family):
    if family.endswith('_madj'):
        return [ADJ_FEATURE if n == m.MARGIN_FEATURE else n for n in _base_names(family[:-5])]
    return _base_names(family)


def adjusted_margins(sched, box, half_life):
    """{(team, season, week): rating} before each scheduled week, from earlier games in the
    box-score history (the games the raw margin uses). Home margin = h * site + r_home - r_away,
    weighted ridge, ridge PRIOR_EQUIVALENT_GAMES on each rating, none on h."""
    g = sched[sched.game_id.isin(set(box.game_id)) & sched.result.notna()]
    out = {}
    for (year, week), wk in sched.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week)
        h = g[m.before(g, year, week) & (g.season >= year - m.MAX_HISTORY_SEASONS)]
        teams = sorted(set(wk.home_team) | set(wk.away_team))
        if not len(h):
            out.update({(t, year, week): 0. for t in teams}); continue
        slot = (h.season.astype(int) * 100 + h.week.astype(int)).to_numpy()
        uniq = np.unique(slot); age = (len(uniq) - 1 - np.searchsorted(uniq, slot)).astype(float)
        w = np.exp2(-age / half_life) * np.power(m.OFFSEASON_RETENTION, year - h.season.to_numpy(float))
        allt = sorted(set(h.home_team) | set(h.away_team)); ix = {t: i for i, t in enumerate(allt)}
        n, T = len(h), len(allt)
        X = np.zeros((n, 1 + T)); X[:, 0] = h.site.to_numpy(float)
        X[np.arange(n), 1 + np.array([ix[t] for t in h.home_team])] = 1.
        X[np.arange(n), 1 + np.array([ix[t] for t in h.away_team])] = -1.
        A = X.T @ (w[:, None] * X); A[1:, 1:] += m.PRIOR_EQUIVALENT_GAMES * np.eye(T)
        beta = np.linalg.solve(A, X.T @ (w * h.result.to_numpy(float)))
        for t in teams: out[(t, year, week)] = float(beta[1 + ix[t]]) if t in ix else 0.
    return out


def fit_margin(train, recipe, year, week):
    """fit_composite with weighted ridge least squares on the home margin."""
    t = train[train.result.notna() & train.ready].copy()
    if len(t) < m.MIN_TRAIN_GAMES: raise ValueError(f'Only {len(t)} labeled games')
    if not m.before(t, year, week).all(): raise ValueError('Training includes current/future week')
    names = m.feature_names(recipe['family'])
    raw = t[names].to_numpy(float); X = np.where(np.isfinite(raw), raw, 0.)
    age = ((year - t.season.to_numpy()) * 19 + (week - t.week.to_numpy())) / (19 * m.FIT_HALF_LIFE_SEASONS)
    w = np.exp2(-age); w /= w.sum()
    mu = np.sum(w[:, None] * X, axis=0)
    scale = np.sqrt(np.sum(w[:, None] * (X - mu) ** 2, axis=0))
    scale = np.where(scale > 1e-8, scale, 1.); scale[0] = 1.
    Z = X / scale; y = t.result.to_numpy(float)
    pen = np.full(len(names), float(recipe['ridge'])); pen[0] *= .1
    beta = np.linalg.solve(Z.T @ (w[:, None] * Z) + np.diag(pen), Z.T @ (w * y))
    sigma = float(np.sqrt(np.sum(w * (y - Z @ beta) ** 2)))
    return {'names': names, 'scale': scale, 'beta': beta, 'sigma': sigma}


def apply_margin(df, fit):
    x = df[fit['names']].to_numpy(float)
    mu = (np.where(np.isfinite(x), x, 0.) / fit['scale']) @ fit['beta']
    return ndtr(mu / fit['sigma']), mu


def margin_grid(feats, oof, families):
    """Walk-forward arm M on the same rows as walk_forward_grid; adds p__lsq_<key> and mu__lsq_<key>."""
    first = feats[m.TEAM_HALF_LIVES[0]]
    valid = ((first.season >= m.BACKTEST_FIRST_SEASON) & (first.season <= LAST)
             & first['home won'].isin([0., 1.]) & first.ready)
    cols = {}
    for fam in families:
        for h in m.TEAM_HALF_LIVES:
            f = feats[h]
            for r in LS_RIDGES:
                recipe = {'family': fam, 'half_life': h, 'ridge': r}; key = 'lsq_' + m.recipe_key(recipe)
                p = pd.Series(np.nan, index=f.index); mu = p.copy()
                for (year, week), test in f.loc[valid].groupby(['season', 'week'], sort=True):
                    fit = fit_margin(f[m.before(f, int(year), int(week))], recipe, int(year), int(week))
                    p.loc[test.index], mu.loc[test.index] = apply_margin(test, fit)
                cols['p__' + key] = p.loc[valid].to_numpy(); cols['mu__' + key] = mu.loc[valid].to_numpy()
        log(f'margin target {fam}: done')
    ids = first.loc[valid, 'game_id'].to_numpy()
    if not (ids == oof.game_id.to_numpy()).all(): raise ValueError('row order differs from walk_forward_grid')
    return oof.assign(**cols)


def boot_ci(d, level=.975, reps=BOOT):
    d = np.asarray(d, float); rng = np.random.default_rng(m.SEED)
    means = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(reps)])
    a = (1 - level) / 2
    return np.quantile(means, [a, 1 - a])


def extra(df):
    """Market favorite and market-correct null on the same priced rows as score()."""
    d = df.copy(); d['market_ml_wp'] = m.market_ml_wp(d)
    mb, kb = m.flat_bets(d, 'model_wp'), m.flat_bets(d, 'market_ml_wp')
    keep = mb.units.notna() & kb.units.notna()
    return m.roi_summary(mb[keep])['null_roi'], m.roi_summary(kb[keep])['roi']


DIRECTION_SIGN = {'site': 1, m.MARGIN_FEATURE: 1, ADJ_FEATURE: 1, 'd__avail__qb_delta': 1}


def expected_sign(name):
    if name in DIRECTION_SIGN: return DIRECTION_SIGN[name]
    if name.startswith('d__avail__'): return -1
    role, _, metric = name.split('__')[1:]
    hb = m.OFFENSE_HIGHER_BETTER.get(metric)
    if hb is None: return 0
    return (1 if hb else -1) * (1 if role == 'for' else -1)


def wrong_signs(names, beta):
    return [n for n, b in zip(names, beta) if expected_sign(n) and np.sign(b) != expected_sign(n)]


def main():
    m.feature_names = feature_names
    inp = load_inputs(cache_dir_from_argv())
    sched, box, avail = inp['sched'], inp['box'], availability(inp)
    feats = {}
    for h in m.TEAM_HALF_LIVES:
        f = m.lagged_features(box, sched, h, avail)
        r = adjusted_margins(sched, box, h)
        f[ADJ_FEATURE] = [r.get((a, y, w), 0.) - r.get((b, y, w), 0.) for a, b, y, w in zip(f.home, f.away, f.season, f.week)]
        feats[h] = f
    log('features built')
    m.FEATURE_FAMILIES = PROD + ADJ
    oof = m.attach_moneylines(m.walk_forward_grid(feats, LAST), sched)
    oof = margin_grid(feats, oof, PROD + ADJ)
    arms = {'production (v1.12)': PROD, 'M: margin target': tuple('lsq_' + f for f in PROD),
            'A: schedule-adjusted margin': ADJ, 'M + A (not decisive)': tuple('lsq_' + f for f in ADJ)}
    held, picks, sc = {}, {}, {}
    for name, fams in arms.items():
        held[name], picks[name] = outer(oof, fams); sc[name] = score(held[name])
        log(f'{name} picks {picks[name]}')
    base = sc['production (v1.12)']
    print('\n### Test 28 result\n')
    print('| Arm | LL gain vs production [97.5% CI] | ± SE | Verdict |\n|---|---:|---:|---|')
    for name in list(arms)[1:]:
        d = base['ll_vec'] - sc[name]['ll_vec']; lo, hi = boot_ci(d)
        verdict = 'supported' if lo > 0 else 'harmful' if hi < 0 else 'unresolved'
        if name.startswith('M + A'): verdict = 'reported only'
        print(f'| {name} | {d.mean():+.4f} [{lo:+.4f}, {hi:+.4f}] | {d.std(ddof=1) / np.sqrt(len(d)):.4f} | {verdict} |')
    print('\n' + HEAD)
    for name in arms: print(row(name, sc[name]))
    null, fav = extra(held['production (v1.12)'])
    print(f'\nSame priced rows: market favorite {100 * fav:+.1f}%, market-correct null {100 * null:+.1f}%.')
    print('\n' + DHEAD)
    for name in list(arms)[1:]: print(diff_row(f'{name} vs production', sc[name], base))
    print('\n| Log-loss gain vs production | ' + ' | '.join(str(s) for s in OUTER) + ' | '
          + ' | '.join(f'wk {g[2]}' for g in WEEK_GROUPS) + ' |')
    print('|---|' + '---:|' * (len(OUTER) + len(WEEK_GROUPS)))
    seas = held['production (v1.12)'].season.to_numpy(); wk = held['production (v1.12)'].week.to_numpy()
    for name in list(arms)[1:]:
        d = base['ll_vec'] - sc[name]['ll_vec']; cells = []
        for k in [seas == s for s in OUTER] + [(wk >= lo) & (wk <= hi) for lo, hi, _ in WEEK_GROUPS]:
            cells.append(f'{d[k].mean():+.4f} ± {d[k].std(ddof=1) / np.sqrt(k.sum()):.4f} (n={k.sum()})')
        print(f'| {name} | ' + ' | '.join(cells) + ' |')
    # Margin RMSE: arm M's mu vs the market spread and production's implied spread.
    rows = []
    for yr, key in picks['M: margin target'].items():
        part = oof[oof.season == yr]
        rows.append(pd.DataFrame({'game_id': part.game_id, 'mu': part['mu__' + key], 'result': part.result,
                                  'spread_line': part.spread_line}))
    mm = pd.concat(rows).merge(held['production (v1.12)'][['game_id', 'model_wp']], on='game_id')
    ok = mm.spread_line.notna()
    rmse = lambda a: float(np.sqrt(np.mean((mm.result[ok] - a[ok]) ** 2)))
    print(f'\nHeld-out margin RMSE (n={int(ok.sum())}): arm M mu {rmse(mm.mu):.2f}, market spread '
          f'{rmse(mm.spread_line):.2f}, production implied spread {rmse(pd.Series(m.implied_spread(mm.model_wp), index=mm.index)):.2f}')
    # Coefficients against the direction map, fit through LAST, each arm's last pick.
    f_last = {}
    for name in ('production (v1.12)', 'M: margin target'):
        key = picks[name][max(OUTER)]; fam, rest = key.split('_h'); hl, rd = rest.split('_r')
        lsq = fam.startswith('lsq_'); fam = fam[4:] if lsq else fam
        recipe = {'family': fam, 'half_life': float(hl), 'ridge': float(rd)}
        f = feats[recipe['half_life']]; tr = f[m.before(f, LAST + 1, 1)]
        fit = fit_margin(tr, recipe, LAST + 1, 1) if lsq else m.fit_composite(tr, recipe, LAST + 1, 1)
        bad = wrong_signs(fit['names'], np.asarray(fit['beta']))
        n_dir = sum(1 for n in fit['names'] if expected_sign(n))
        f_last[name] = fit
        print(f'Fit through {LAST} ({key}): {len(bad)} of {n_dir} directed coefficients against the direction map'
              + (': ' + ', '.join(bad) if bad else ''))
    print(f"Arm M residual SD through {LAST}: {f_last['M: margin target']['sigma']:.2f} points")
    log('done')


if __name__ == '__main__':
    main()
