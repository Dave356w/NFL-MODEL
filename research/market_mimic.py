"""Test 15: how much of the market can the model's own pregame stats reproduce, and how
does the market reweight last season against this season as the weeks pass?

    python research/market_mimic.py [CACHE_DIR]     # ~3 min warm

Rows: every ready, priced regular-season game 2021-2025. Market = no-vig closing
moneyline log-odds (spread-derived where a moneyline is missing).

A. Market mimic. OLS of the market log-odds on the frozen recipe's 23 pregame
   features (rates_core_avail_cs, h8), then adding decayed point margin, then
   splitting margin into last season and this season so far. R^2 is out of
   sample: each season is predicted from a fit on the other four.

B. What the market learns. By week group, standardized weights on three pregame
   summaries: the composite's walk-forward log-odds (frozen recipe), last season's
   average margin, and this season's average margin so far. Two targets: the
   market's log-odds (what the market uses) and the outcome (logistic, what
   actually predicted wins).

C. Market-trained composite. The same pregame features, refit before every week
   by weighted ridge regression on earlier games' closing-market log-odds instead
   of their outcomes (no lookahead: only earlier games' closing lines). The
   prediction is expit of the fitted market log-odds. The ridge (and whether to add
   decayed margin) is chosen per held-out season on earlier seasons' outcome log
   loss, and the model is scored like production on the priced 2023-25 games.
"""
import numpy as np
import pandas as pd
from scipy.special import logit

from _common import LAST, OUTER, _ll, availability, cache_dir_from_argv, load_inputs, log, m
from market_info import GROUPS, lagged_mov, logistic, score_row, with_market

FROZEN = {'family': 'rates_core_avail_cs', 'half_life': 8., 'ridge': .1}


def season_margins(sched):
    """Per (team, season, week): last season's average margin and this season's average so far."""
    s = sched[sched.result.notna()]
    rows = pd.concat([pd.DataFrame({'team': s.home_team, 'season': s.season, 'week': s.week, 'margin': s.result}),
                      pd.DataFrame({'team': s.away_team, 'season': s.season, 'week': s.week, 'margin': -s.result})])
    full = rows.groupby(['team', 'season']).margin.mean()
    out = {}
    for (team, yr), g in rows.groupby(['team', 'season']):
        for wk in range(1, 23):
            prev = g.margin[g.week < wk]
            out[(team, yr, wk)] = (float(full.get((team, yr - 1), 0.)), float(prev.mean()) if len(prev) else 0.)
    return out


def walk_forward_logit(f):
    valid = (f.season >= m.BACKTEST_FIRST_SEASON) & (f.season <= LAST) & f['home won'].isin([0., 1.]) & f.ready
    out = pd.Series(np.nan, index=f.index)
    for (yr, wk), test in f.loc[valid].groupby(['season', 'week'], sort=True):
        fit = m.fit_composite(f[m.before(f, int(yr), int(wk))], FROZEN, int(yr), int(wk))
        out.loc[test.index] = m.apply_fit(test, fit, contributions=True)[1]
    return out, valid


MIMIC_RIDGES = (.01, .1, 1., 10.)


def market_trained(f, names, valid):
    """Walk-forward weighted ridge of market log-odds on features; one column per (ridge, inputs)."""
    out = {}
    for (yr, wk), test in f.loc[valid].groupby(['season', 'week'], sort=True):
        t = f[m.before(f, int(yr), int(wk)) & f.ready & np.isfinite(f.mkt)]
        age = ((int(yr) - t.season.to_numpy()) * 19 + (int(wk) - t.week.to_numpy())) / (19 * m.FIT_HALF_LIFE_SEASONS)
        w = np.exp2(-age); w /= w.sum()
        for tag, cols in (('stats', names), ('stats+margin', names + ['mov'])):
            raw = t[cols].to_numpy(float); X = np.where(np.isfinite(raw), raw, 0.)
            mu = (w[:, None] * X).sum(0)
            sc = np.sqrt((w[:, None] * (X - mu) ** 2).sum(0)); sc = np.where(sc > 1e-8, sc, 1.); sc[0] = 1.
            Z = X / sc; y = t.mkt.to_numpy(float)
            xt = test[cols].to_numpy(float); Zt = np.where(np.isfinite(xt), xt, 0.) / sc
            for lam in MIMIC_RIDGES:
                pen = np.full(len(cols), lam); pen[0] *= .1
                b = np.linalg.solve(Z.T @ (w[:, None] * Z) + np.diag(pen), Z.T @ (w * y))
                out.setdefault(f'p__{tag}_r{lam:g}', pd.Series(np.nan, index=f.index)).loc[test.index] = 1 / (1 + np.exp(-(Zt @ b)))
    return pd.DataFrame(out)


def loso_r2(X, y, seasons):
    pred = np.empty_like(y)
    for s in np.unique(seasons):
        tr, te = seasons != s, seasons == s
        A = np.column_stack([np.ones(tr.sum()), X[tr]])
        b = np.linalg.lstsq(A, y[tr], rcond=None)[0]
        pred[te] = np.column_stack([np.ones(te.sum()), X[te]]) @ b
    return 1 - np.sum((y - pred) ** 2) / np.sum((y - y.mean()) ** 2)


def std(x):
    x = np.asarray(x, float); s = x.std()
    return (x - x.mean()) / (s if s > 0 else 1.)


def main():
    inp = load_inputs(cache_dir_from_argv())
    sched = inp['sched']
    f = m.lagged_features(inp['box'], sched, FROZEN['half_life'], availability(inp))
    comp, valid = walk_forward_logit(f)
    d = with_market(f.loc[valid].assign(comp=comp[valid]), sched)
    d = d[np.isfinite(d.mkt)].reset_index(drop=True)
    log(f'{len(d)} games')
    names = m.feature_names(FROZEN['family'])
    X = np.where(np.isfinite(d[names].to_numpy(float)), d[names].to_numpy(float), 0.)
    mov = lagged_mov(sched); sm = season_margins(sched)
    d['mov'] = [mov[(h, y, w)] - mov[(a, y, w)] for h, a, y, w in zip(d.home, d.away, d.season, d.week)]
    d['last'] = [sm[(h, y, w)][0] - sm[(a, y, w)][0] for h, a, y, w in zip(d.home, d.away, d.season, d.week)]
    d['now'] = [sm[(h, y, w)][1] - sm[(a, y, w)][1] for h, a, y, w in zip(d.home, d.away, d.season, d.week)]

    print('\n### Test 15A: how much of the market do pregame stats reproduce? (out-of-season R²)\n')
    print('| Weeks | Games | 23 model features | + decayed margin | + last-season & this-season margin | Composite log-odds alone |')
    print('|---|---:|---:|---:|---:|---:|')
    for lo, hi, name in GROUPS + ((1, 18, 'All'),):
        k = ((d.week >= lo) & (d.week <= hi)).to_numpy()
        y, s = d.mkt.to_numpy()[k], d.season.to_numpy()[k]
        a = loso_r2(X[k], y, s)
        b = loso_r2(np.column_stack([X[k], d.mov[k]]), y, s)
        c = loso_r2(np.column_stack([X[k], d.mov[k], d['last'][k], d.now[k]]), y, s)
        e = loso_r2(d.comp.to_numpy()[k, None], y, s)
        print(f'| {name} | {k.sum()} | {100 * a:.0f}% | {100 * b:.0f}% | {100 * c:.0f}% | {100 * e:.0f}% |')

    print('\n### Test 15B: what the market weights vs what predicted the outcome (per 1 SD, log-odds)\n')
    print('| Weeks | Target | Composite | Last-season margin | This-season margin so far |')
    print('|---|---|---:|---:|---:|')
    for lo, hi, name in GROUPS:
        k = ((d.week >= lo) & (d.week <= hi)).to_numpy()
        Z = np.column_stack([std(d.comp[k]), std(d['last'][k]), std(d.now[k])])  # week 1: 'now' is 0
        A = np.column_stack([np.ones(k.sum()), Z])
        bm = np.linalg.lstsq(A, d.mkt.to_numpy()[k], rcond=None)[0]
        res = d.mkt.to_numpy()[k] - A @ bm
        sem = np.sqrt(np.diag(np.linalg.inv(A.T @ A)) * res.var(ddof=4))
        bo, seo, _ = logistic(Z, d['home won'].to_numpy(float)[k])
        print(f'| {name} | market | {bm[1]:+.2f} ± {sem[1]:.2f} | {bm[2]:+.2f} ± {sem[2]:.2f} | {bm[3]:+.2f} ± {sem[3]:.2f} |')
        print(f'| {name} | outcome | {bo[1]:+.2f} ± {seo[1]:.2f} | {bo[2]:+.2f} ± {seo[2]:.2f} | {bo[3]:+.2f} ± {seo[3]:.2f} |')
    print('\n### Test 15C: composite trained on market prices instead of outcomes\n')
    f = f.assign(mov=[mov[(h, y, w)] - mov[(a, y, w)] for h, a, y, w in zip(f.home, f.away, f.season, f.week)])
    f = with_market(f, sched)
    preds = market_trained(f, names, valid)
    g = f.loc[valid, ['game_id', 'season', 'week', 'home won', 'home_moneyline', 'away_moneyline', 'q']].join(preds)
    g['frozen_wp'] = 1 / (1 + np.exp(-comp[valid]))
    y = g['home won'].to_numpy(float); cols = list(preds.columns); held = []
    for yr in OUTER:
        tr = (g.season < yr).to_numpy()
        best = min(cols, key=lambda c: _ll(y[tr], g[c].to_numpy()[tr]).mean())
        held.append(g[g.season == yr].assign(mimic=g.loc[g.season == yr, best])); log(f'{yr}: {best[3:]}')
    h = pd.concat(held)
    h = h[m.flat_bets(h, 'frozen_wp').units.notna() & m.flat_bets(h, 'q').units.notna()]
    print('| Model (held-out 2023–25) | Bets | Units | Model-side ROI ± SE | Same-row favorite | Market null | Log loss | LL gain vs ML market |')
    print('|---|---:|---:|---:|---:|---:|---:|---:|')
    print(score_row('Market alone (no-vig ML)', h.assign(mk=h.q), 'mk'))
    print(score_row('Frozen recipe, trained on outcomes', h, 'frozen_wp'))
    print(score_row('Same features, trained on market prices', h, 'mimic'))
    for c in ('p__stats_r1', 'p__stats+margin_r1'):
        print(score_row(f'Fixed {c[3:]} (no selection)', h, c))
    yy = h['home won'].to_numpy(float)
    dl = _ll(yy, h.frozen_wp.to_numpy()) - _ll(yy, h.mimic.to_numpy())
    du = (m.flat_bets(h, 'mimic').units - m.flat_bets(h, 'frozen_wp').units).to_numpy(float)
    print(f'\nMarket-trained minus outcome-trained, same games: LL gain {dl.mean():+.4f} ± {dl.std(ddof=1) / np.sqrt(len(dl)):.4f}, '
          f'ROI {100 * du.mean():+.2f} pts ± {100 * du.std(ddof=1) / np.sqrt(len(du)):.2f}; '
          f'picks differ on {int((h.mimic.gt(.5) != h.frozen_wp.gt(.5)).sum())} games.')
    log('done')


if __name__ == '__main__':
    main()
