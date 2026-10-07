"""Tests 12-14: the market as an input, the market's phases, and what it prices that the model lacks.

    python research/market_info.py [CACHE_DIR]     # ~8 min warm

Test 12. Market-aware composite: the box-score features fit only what the market
misses. 'offset' fixes the market's log-odds at coefficient 1 (a residual model);
'free' gives the market log-odds an unpenalized coefficient next to the features.
Market = no-vig closing moneyline (spread-derived where a moneyline is missing).
Each candidate (family x half-life x ridge x mode) is refit before every week as
in production, and each held-out season's recipe is chosen on earlier seasons
only (min log loss). Scored on the same 811 priced held-out games as production.

Test 13. Model vs market by week group on the production held-out rows: market log
loss, model log loss, paired gain, market confidence, and the in-sample blend
weights y ~ a*logit(market) + b*logit(model).

Test 14. What explains the model-market gap? Pregame covariates, one at a time:
does it move the gap (market prices it), and does it add to the outcome beyond the
model (the model misses it) or beyond the market (the market misses it)?
Diagnostics, in-sample on the held-out rows.
"""
import numpy as np
import pandas as pd
from scipy.special import expit, logit

from _common import FULL, LAST, OUTER, _ll, availability, cache_dir_from_argv, load_inputs, log, m, outer

MODES = ('offset', 'free')
GROUPS = ((1, 4, 'Weeks 1–4'), (5, 9, 'Weeks 5–9'), (10, 13, 'Weeks 10–13'), (14, 17, 'Weeks 14–17'), (18, 18, 'Week 18'))
MOV_HALF_LIFE = 8.


def with_market(f, sched):
    f = m.attach_moneylines(f, sched)
    q = m.market_ml_wp(f)
    q = np.where(np.isfinite(q), q, f.market_wp.to_numpy(float))
    return f.assign(q=q, mkt=logit(np.clip(q, 1e-4, 1 - 1e-4)))


def fit_market_aware(t, names, ridge, year, week, mode):
    t = t[t['home won'].isin([0., 1.]) & t.ready & np.isfinite(t.mkt)]
    raw = t[names].to_numpy(float); X = np.where(np.isfinite(raw), raw, 0.)
    age = ((year - t.season.to_numpy()) * 19 + (week - t.week.to_numpy())) / (19 * m.FIT_HALF_LIFE_SEASONS)
    w = np.exp2(-age); w /= w.sum()
    mu = (w[:, None] * X).sum(0)
    sc = np.sqrt((w[:, None] * (X - mu) ** 2).sum(0)); sc = np.where(sc > 1e-8, sc, 1.); sc[0] = 1.
    Z, off, y = X / sc, t.mkt.to_numpy(float), t['home won'].to_numpy(float)
    pen = np.full(len(names), float(ridge)); pen[0] *= .1
    if mode == 'free':
        Z = np.column_stack([Z, off]); off = np.zeros_like(off); pen = np.append(pen, 0.)

    def obj(b):
        eta = off + Z @ b
        return (np.sum(w * (np.logaddexp(0, eta) - y * eta)) + .5 * np.sum(pen * b * b),
                Z.T @ (w * (expit(eta) - y)) + pen * b)
    return m.checked_optimize(obj, Z.shape[1]), sc


def predict_market_aware(df, names, beta, sc, mode):
    x = df[names].to_numpy(float); Z = np.where(np.isfinite(x), x, 0.) / sc
    eta = Z @ beta[:len(names)] + (beta[-1] if mode == 'free' else 1.) * df.mkt.to_numpy(float)
    return expit(eta)


def market_aware_grid(feats, sched):
    out = None
    for h in m.TEAM_HALF_LIVES:
        f = with_market(feats[h], sched)
        valid = (f.season >= m.BACKTEST_FIRST_SEASON) & (f.season <= LAST) & f['home won'].isin([0., 1.]) & f.ready
        if out is None: out = f.loc[valid, ['game_id', 'season', 'week', 'home won', 'q', 'mkt']].copy()
        for (year, week), test in f.loc[valid].groupby(['season', 'week'], sort=True):
            tr = f[m.before(f, int(year), int(week))]
            for fam in FULL:
                names = m.feature_names(fam)
                for r in m.RIDGE_GRID:
                    for mode in MODES:
                        beta, sc = fit_market_aware(tr, names, r, int(year), int(week), mode)
                        out.loc[test.index, f'p__{fam}_h{h:g}_r{r:g}_{mode}'] = predict_market_aware(test, names, beta, sc, mode)
        log(f'market-aware h{h:g} done')
    return out.reset_index(drop=True)


def nested(oof, cols):
    y = oof['home won'].to_numpy(float); parts, picks = [], {}
    for yr in OUTER:
        tr = (oof.season < yr).to_numpy()
        best = min(cols, key=lambda c: _ll(y[tr], oof[c].to_numpy()[tr]).mean())
        te = oof[oof.season == yr][['game_id']].copy(); te['p'] = oof.loc[oof.season == yr, best].to_numpy()
        parts.append(te); picks[yr] = best[3:]
    return pd.concat(parts), picks


def bets_summary(d, col):
    b = m.flat_bets(d, col); r = m.roi_summary(b)
    return b, r


def score_row(name, d, col):
    """Model-side flat ROI, same-row favorite, null, paired LL gain vs no-vig ML market."""
    b, r = bets_summary(d, col); fb, f = bets_summary(d, 'q')
    y = d['home won'].to_numpy(float); g = _ll(y, d.q.to_numpy()) - _ll(y, d[col].to_numpy())
    return (f"| {name} | {r['bets']} | {r['units']:+.2f} | {100 * r['roi']:+.1f}% ± {100 * r['roi_se']:.1f} | "
            f"{100 * f['roi']:+.1f}% | {100 * r['null_roi']:+.1f}% | {_ll(y, d[col].to_numpy()).mean():.4f} | "
            f"{g.mean():+.4f} ± {g.std(ddof=1) / np.sqrt(len(g)):.4f} |")


def value_row(name, d, col, edge=.02):
    """Bet the side the model prices at least `edge` above the no-vig market, at its moneyline."""
    p, q = d[col].to_numpy(float), d.q.to_numpy(float)
    pick = np.where(p - q >= edge, 1., np.where(q - p >= edge, 0., np.nan))
    sel = d[np.isfinite(pick)].copy(); sel['pick_wp'] = np.where(pick[np.isfinite(pick)] == 1., .99, .01)
    b, r = bets_summary(sel, 'pick_wp')
    if not r['bets']: return f'| {name} | 0 | – | – | – |'
    return (f"| {name} | {r['bets']} | {r['units']:+.2f} | {100 * r['roi']:+.1f}% ± {100 * r['roi_se']:.1f} | "
            f"{100 * r['null_roi']:+.1f}% |")


def logistic(X, y):
    """Unpenalized logistic fit with an intercept; returns coefficients, SEs, mean log loss."""
    A = np.column_stack([np.ones(len(y)), X])

    def obj(b):
        eta = A @ b
        return np.mean(np.logaddexp(0, eta) - y * eta), A.T @ (expit(eta) - y) / len(y)
    b = m.checked_optimize(obj, A.shape[1])
    p = expit(A @ b); H = A.T @ (A * (p * (1 - p))[:, None])
    return b, np.sqrt(np.diag(np.linalg.inv(H))), float(obj(b)[0])


def phases(d):
    lines = ['| Weeks | Games | Market LL | Model LL | Gain vs market ± SE | Market confidence | Blend: market weight | Blend: model weight |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for lo, hi, name in GROUPS:
        g = d[(d.week >= lo) & (d.week <= hi)]
        y = g['home won'].to_numpy(float); lm, lp = _ll(y, g.q.to_numpy()), _ll(y, g.model_wp.to_numpy())
        b, se, _ = logistic(np.column_stack([logit(g.q), logit(np.clip(g.model_wp, 1e-4, 1 - 1e-4))]), y)
        lines.append(f"| {name} | {len(g)} | {lm.mean():.4f} | {lp.mean():.4f} | {(lm - lp).mean():+.4f} ± "
                     f"{(lm - lp).std(ddof=1) / np.sqrt(len(g)):.4f} | {np.abs(g.q - .5).mean():.3f} | "
                     f"{b[1]:+.2f} ± {se[1]:.2f} | {b[2]:+.2f} ± {se[2]:.2f} |")
    by = ['', '| Season | Weeks 1–13 gain | Weeks 14–18 gain |', '|---|---:|---:|']
    for yr, g in d.groupby('season'):
        y = g['home won'].to_numpy(float); gain = _ll(y, g.q.to_numpy()) - _ll(y, g.model_wp.to_numpy())
        late = (g.week >= 14).to_numpy()
        by.append(f'| {yr} | {gain[~late].mean():+.4f} (n={(~late).sum()}) | {gain[late].mean():+.4f} (n={late.sum()}) |')
    return '\n'.join(lines + by)


def lagged_mov(sched):
    """Decayed average point margin per team before each game (production profile weighting,
    MOV_HALF_LIFE team games, OFFSEASON_RETENTION per season, PRIOR_EQUIVALENT_GAMES at zero)."""
    s = sched[sched.result.notna()]
    rows = pd.concat([pd.DataFrame({'team': s.home_team, 'season': s.season, 'week': s.week, 'margin': s.result}),
                      pd.DataFrame({'team': s.away_team, 'season': s.season, 'week': s.week, 'margin': -s.result})])
    rows = rows.sort_values(['team', 'season', 'week'])
    out = {}
    for team, g in rows.groupby('team'):
        seasons, weeks, margins = g.season.to_numpy(), g.week.to_numpy(), g.margin.to_numpy(float)
        for (yr, wk) in sched.loc[(sched.home_team == team) | (sched.away_team == team), ['season', 'week']].itertuples(index=False):
            prior = (seasons < yr) | ((seasons == yr) & (weeks < wk))
            prior &= seasons >= yr - m.MAX_HISTORY_SEASONS
            n = int(prior.sum())
            if not n: out[(team, yr, wk)] = 0.; continue
            age = np.arange(n - 1, -1, -1, dtype=float)
            wt = np.exp2(-age / MOV_HALF_LIFE) * np.power(m.OFFSEASON_RETENTION, yr - seasons[prior])
            out[(team, yr, wk)] = float(np.dot(wt, margins[prior]) / (wt.sum() + m.PRIOR_EQUIVALENT_GAMES))
    return out


def covariates(d, sched):
    s = sched.set_index('game_id')
    g = s.loc[d.game_id]
    mov = lagged_mov(sched)
    outdoor = g.roof.isin(['outdoors', 'open']).to_numpy()
    cov = pd.DataFrame({
        'Decayed point margin, home − away': [mov[(h, y, w)] - mov[(a, y, w)] for h, a, y, w in
                                              zip(g.home_team, g.away_team, g.season, g.week)],
        'Rest days, home − away': (g.home_rest - g.away_rest).to_numpy(float),
        'Division game': g.div_game.to_numpy(float),
        'Wind (mph, outdoor; 0 indoors)': np.where(outdoor, pd.to_numeric(g.wind, errors='coerce').fillna(0.), 0.),
        'Week 18': (g.week == 18).to_numpy(float),
    }, index=d.index)
    return cov


def gap_table(d, cov):
    """Univariate diagnostics on held-out rows; each covariate standardized to 1 SD."""
    y = d['home won'].to_numpy(float)
    mk, md = logit(d.q.to_numpy()), logit(np.clip(d.model_wp.to_numpy(), 1e-4, 1 - 1e-4))
    gap = mk - md
    _, _, ll_md = logistic(md[:, None], y); _, _, ll_mk = logistic(mk[:, None], y)
    lines = ['| Covariate (per 1 SD) | Moves market − model gap (log-odds) | Adds beyond model: coef, LL gain | Adds beyond market: coef, LL gain |',
             '|---|---:|---:|---:|']
    for name, x in cov.items():
        x = x.to_numpy(float); sd = x.std() or 1.; z = (x - x.mean()) / sd
        A = np.column_stack([np.ones(len(z)), z]); bg = np.linalg.lstsq(A, gap, rcond=None)[0]
        res = gap - A @ bg; seg = np.sqrt(np.sum(res ** 2) / (len(z) - 2) / np.sum(z ** 2))
        b1, s1, l1 = logistic(np.column_stack([md, z]), y)
        b2, s2, l2 = logistic(np.column_stack([mk, z]), y)
        lines.append(f'| {name} | {bg[1]:+.3f} ± {seg:.3f} | {b1[2]:+.3f} ± {s1[2]:.3f}, {ll_md - l1:+.4f} | '
                     f'{b2[2]:+.3f} ± {s2[2]:.3f}, {ll_mk - l2:+.4f} |')
    A = np.column_stack([np.ones(len(gap)), (cov - cov.mean()) / cov.std().replace(0, 1)])
    bj = np.linalg.lstsq(A, gap, rcond=None)[0]; r2 = 1 - np.var(gap - A @ bj) / np.var(gap)
    return '\n'.join(lines) + f'\n\nAll five together explain {100 * r2:.0f}% of the variance of the gap (SD {gap.std():.3f} log-odds).'


def main():
    inp = load_inputs(cache_dir_from_argv())
    avail = availability(inp)
    feats = {h: m.lagged_features(inp['box'], inp['sched'], h, avail) for h in m.TEAM_HALF_LIVES}
    m.FEATURE_FAMILIES = FULL
    prod, picks = outer(m.attach_moneylines(m.walk_forward_grid(feats, LAST), inp['sched']), FULL)
    log(f'production picks: {picks}')
    d = with_market(prod, inp['sched'])
    d = d[m.flat_bets(d, 'model_wp').units.notna() & m.flat_bets(d, 'q').units.notna()].reset_index(drop=True)

    oof = market_aware_grid(feats, inp['sched'])
    head = ('| Model (held-out 2023–25) | Bets | Units | Model-side ROI ± SE | Same-row favorite | Market null | Log loss | LL gain vs ML market |\n'
            '|---|---:|---:|---:|---:|---:|---:|---:|')
    rows = [score_row('Market alone (no-vig ML)', d.assign(mk_wp=d.q), 'mk_wp'),
            score_row('Production composite', d, 'model_wp')]
    vrows = [value_row('Production composite', d, 'model_wp')]
    for label, cols in (('Market-aware, offset', [c for c in oof if c.endswith('_offset')]),
                        ('Market-aware, free market weight', [c for c in oof if c.endswith('_free')]),
                        ('Market-aware, either (nested)', [c for c in oof if c.startswith('p__')])):
        sel, pk = nested(oof, cols)
        log(f'{label} picks: {pk}')
        dd = d.merge(sel, on='game_id', how='left', validate='one_to_one')
        rows.append(score_row(label, dd, 'p')); vrows.append(value_row(label, dd, 'p'))
    print('\n### Test 12: market-aware composite\n')
    print(head); print('\n'.join(rows))
    print('\nValue rule (exploratory): bet the side priced ≥ 2 pts above the no-vig market.\n')
    print('| Model | Bets | Units | ROI ± SE | Market null |\n|---|---:|---:|---:|---:|'); print('\n'.join(vrows))
    free = [c for c in oof if c.endswith('_free')]
    print('\n### Test 13: phases\n')
    print(phases(d))
    print('\n### Test 14: what explains the model–market gap\n')
    print(gap_table(d, covariates(d, inp['sched'])))
    log(f'done ({len(free)} free-mode candidates)')


if __name__ == '__main__':
    main()
