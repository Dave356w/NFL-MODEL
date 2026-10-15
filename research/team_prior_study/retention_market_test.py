"""Continuity-conditioned OFFSEASON_RETENTION: market-anchored walk-forward test (copy of team_prior_market_test.py).

EXPLORATORY, EXPOSED SEASONS, POST HOC: the two arms (retention_cont_75_25, retention_cont_50_25) were added
after the 7 earlier team-prior variants had been scored on these same 2017-2025 games. Nothing in the repo,
data/, the frozen recipe or the ledger is touched.

Model per variant (SIMPLIFIED production; NOT exact production), unchanged from team_prior_market_test.py:
  logit P(home win) = logit(q) + sum_j beta_j * x_j / s_j, q = proportional no-vig closing moneyline
  probability, x = site + 16 d__ profile differences; no availability, QB projection, pass contexts or
  favorite penalty (the penalty is reported separately). Ridge 0.1 (site x0.1), decay half-life 2 seasons
  in 19-week slots, weekly refit on strictly earlier labeled games from 2015, exactly fit_composite's arithmetic.
Variants: league (production profiles), the two arms, and two flat-retention controls
(retention_flat_75, retention_flat_25) that separate 'continuity matters' from 'a different retention level'.
Every variant uses the production league pseudo-game target, so the incremental DELTA reference is league.
Bonferroni family: 9 = the 7 earlier variant-vs-league comparisons + these 2 arms (controls are diagnostics).
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import binomtest

from paths import ROOT, WORK, GAMES_CSV  # noqa: E402
MAIN = ROOT
sys.path.insert(0, str(MAIN))
import nfl_model as m  # noqa: E402

PROFILES = [WORK / 'retention_profiles.csv.gz', WORK / 'retention_controls_profiles.csv.gz']
SCHED = MAIN / 'research' / 'form_windows_inputs' / 'schedule.csv'
OUT = WORK
PRIOR_PRED = OUT / 'market_test_predictions.csv.gz'
OOS = MAIN / 'research' / 'out_of_sample_results' / 'predictions.csv'
REPRO = MAIN / 'research' / 'production_adoption_results' / 'historical_reproduction.csv'

FAMILY = 'rates_core_avail_cs_peaks_nosacks'
FEATS = [n for n in m.feature_names(FAMILY) if not n.startswith('d__avail__')]
PROFILE_COLS = [n[3:] for n in FEATS if n != 'site']
assert len(PROFILE_COLS) == 16, PROFILE_COLS
PRIMARY = ['retention_cont_75_25', 'retention_cont_50_25']
CONTROLS = ['retention_flat_75', 'retention_flat_25']
VARIANTS = ['league'] + PRIMARY + CONTROLS
ARMS = VARIANTS[1:]
PAIRS = {'retention_cont_75_25': 'retention_flat_75', 'retention_cont_50_25': 'retention_flat_25'}
DELTA_REF = {v: 'league' for v in ARMS}
RIDGE, SITE_MULT, FIT_HL, MIN_TRAIN = .1, .1, 2., 150
FIRST_TRAIN, EVAL = 2015, (2017, 2025)
ERAS = {'2017-20': (2017, 2020), '2021-22': (2021, 2022), '2023-25': (2023, 2025), 'All 2017-25': (2017, 2025)}
REPS, SEED = 2000, m.SEED
K_BONF = 9
BONF_LEVEL = 1 - .05 / K_BONF
T0 = time.time()


def log(s):
    print(f'[{time.time() - T0:5.0f}s] {s}', flush=True)


def load():
    p = pd.concat([pd.read_csv(f, low_memory=False) for f in PROFILES], ignore_index=True)
    p = p[p.season <= EVAL[1]].drop_duplicates(['game_id', 'team', 'variant'])
    s = pd.read_csv(SCHED)
    s = m.normalize_teams(s[(s.season >= FIRST_TRAIN) & (s.season <= EVAL[1])].copy())
    s['home won'] = s.result.map(m.won)
    s['site'] = np.where(s.location.astype(str).str.lower() == 'neutral', 0., 1.)
    s['q'] = m.market_ml_wp(s)
    games = {}
    for v in VARIANTS:
        pv = p[p.variant == v]
        h = pv[pv.is_home.astype(str) == 'True'].set_index('game_id')
        a = pv[pv.is_home.astype(str) == 'False'].set_index('game_id')
        g = s.set_index('game_id').join(h[['team', 'neutral_site', 'cont_boundary_cur', 'cont_boundary_m1', 'cont_boundary_m2'] + PROFILE_COLS], how='inner')
        g = g.join(a[['team', 'cont_boundary_cur', 'cont_boundary_m1', 'cont_boundary_m2'] + PROFILE_COLS].add_prefix('a_'), how='inner')
        if not (g.team == g.home_team).all() or not (g.a_team == g.away_team).all():
            raise ValueError('home/away mismatch between profiles and schedule')
        if not ((g.neutral_site.astype(str) == 'True') == (g.site == 0)).all():
            raise ValueError('neutral-site mismatch')
        for c in PROFILE_COLS:
            g['d__' + c] = g[c] - g['a_' + c]
        tb = lambda x: x.astype(str) == 'True'  # noqa: E731
        g['cur_both_continuous'] = tb(g.cont_boundary_cur) & tb(g.a_cont_boundary_cur)
        g['all_boundaries_continuous'] = (tb(g.cont_boundary_cur) & tb(g.cont_boundary_m1) & tb(g.cont_boundary_m2) &
                                          tb(g.a_cont_boundary_cur) & tb(g.a_cont_boundary_m1) & tb(g.a_cont_boundary_m2))
        games[v] = g[['season', 'week', 'home_team', 'away_team', 'home won', 'site', 'q', 'result',
                      'home_moneyline', 'away_moneyline', 'cur_both_continuous', 'all_boundaries_continuous']
                     + ['d__' + c for c in PROFILE_COLS]].reset_index()
        games[v] = games[v].sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
    ids = games['league'].game_id
    for v in VARIANTS:
        if not games[v].game_id.equals(ids):
            raise ValueError('variant game sets differ')
    return games


def fit(t, names, year, week):
    if not m.before(t, year, week).all():
        raise ValueError('training includes current/future week')
    raw = t[names].to_numpy(float)
    X = np.where(np.isfinite(raw), raw, 0.)
    age = ((year - t.season.to_numpy()) * 19 + (week - t.week.to_numpy())) / (19 * FIT_HL)
    w = np.exp2(-age); w /= w.sum()
    mu = np.sum(w[:, None] * X, axis=0)
    scale = np.sqrt(np.sum(w[:, None] * (X - mu) ** 2, axis=0))
    scale = np.where(scale > 1e-8, scale, 1.); scale[0] = 1.
    Z = X / scale
    y = t['home won'].to_numpy(float)
    pen = np.full(len(names), RIDGE); pen[0] *= SITE_MULT
    base = logit(np.clip(t.q.to_numpy(), 1e-5, 1 - 1e-5))

    def obj(beta):
        eta = base + Z @ beta
        return (np.sum(w * (np.logaddexp(0, eta) - y * eta)) + .5 * np.sum(pen * beta * beta),
                Z.T @ (w * (expit(eta) - y)) + pen * beta)
    beta = m.checked_optimize(obj, len(names))
    return {'names': names, 'scale': scale, 'beta': beta, 'n': len(t), 'neff': float(1 / np.sum(w * w))}


def predict(df, f, parts=False):
    x = df[f['names']].to_numpy(float)
    z = np.where(np.isfinite(x), x, 0.) / f['scale']
    contrib = z * f['beta']
    p = expit(logit(np.clip(df.q.to_numpy(float), 1e-5, 1 - 1e-5)) + contrib.sum(1))
    return (p, contrib) if parts else p


def walk_forward(frame, names, label, coefs):
    out = frame[['game_id', 'season', 'week', 'home_team', 'away_team', 'home won', 'q', 'result',
                 'home_moneyline', 'away_moneyline', 'cur_both_continuous', 'all_boundaries_continuous']].copy()
    out['p'] = np.nan
    dcols = [n for n in names if n.startswith('delta__')]
    out['delta_logit'] = np.nan
    lab = frame['home won'].isin([0., 1.]) & np.isfinite(frame.q)
    ev = frame.season.between(*EVAL) & np.isfinite(frame.q)
    for (yr, wk), te in frame[ev].groupby(['season', 'week'], sort=True):
        tr = frame[lab & m.before(frame, yr, wk) & (frame.season >= FIRST_TRAIN)]
        if len(tr) < MIN_TRAIN:
            raise ValueError(f'{label}: {len(tr)} training games at {yr} wk{wk}')
        f = fit(tr, names, int(yr), int(wk))
        p, c = predict(te, f, True)
        out.loc[te.index, 'p'] = p
        if dcols:
            ix = [names.index(d) for d in dcols]
            out.loc[te.index, 'delta_logit'] = c[:, ix].sum(1)
        coefs.append({'model': label, 'season': int(yr), 'week': int(wk), 'train_games': f['n'],
                      'effective_train_games': f['neff'],
                      **{f'beta_std__{n}': b for n, b in zip(names, f['beta'])},
                      **{f'scale__{n}': s for n, s in zip(names, f['scale'])}})
    return out[ev].reset_index(drop=True)


def ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def boot(v, g, level=.95, reps=REPS, seed=SEED):
    a = pd.DataFrame({'v': np.asarray(v, float), 'g': np.asarray(g)}).groupby('g').v.agg(['sum', 'count'])
    if len(a) < 2:
        return [np.nan, np.nan]
    i = np.random.default_rng(seed).integers(0, len(a), (reps, len(a)))
    d = a['sum'].to_numpy()[i].sum(1) / a['count'].to_numpy()[i].sum(1)
    return np.quantile(d, [(1 - level) / 2, (1 + level) / 2]).tolist()


def wk_groups(d):
    return (d.season.astype(str) + '_' + d.week.astype(str).str.zfill(2)).to_numpy()


def bets_for(d, cols):
    d = d.copy(); d['_q'] = m.market_ml_wp(d)
    b = {c: m.flat_bets(d, c) for c in cols}
    b['_fav'] = m.flat_bets(d, '_q')
    # Shared rows: replacement models, league and the favorite. A delta arm can sit within 5e-6 of
    # p = .5 (no bet) on a game the others bet; it is masked per model in main(), not for every model.
    common = np.logical_and.reduce([x.units.notna().to_numpy() for c, x in b.items() if '+delta_' not in c])
    return b, pd.Series(common, index=d.index)


def flip_stats(mb, rb):
    du = (mb.units - rb.units).to_numpy()
    flips = (mb.side != rb.side).to_numpy()
    fv, fr = mb[flips], rb[flips]
    return du, flips, {
        'side_flips': int(flips.sum()),
        'flip_wlp_variant': f"{int((fv.result=='W').sum())}-{int((fv.result=='L').sum())}-{int((fv.result=='P').sum())}",
        'flip_units_variant': float(fv.units.sum()), 'flip_units_ref': float(fr.units.sum()),
        'flip_null_units_variant': float(fv.null_ev.sum()), 'flip_null_units_ref': float(fr.null_ev.sum()),
        'flip_binom_p_two_sided': (float(binomtest(int((fv.result == 'W').sum()), int(fv.result.isin(['W', 'L']).sum()), .5).pvalue)
                                   if fv.result.isin(['W', 'L']).any() else np.nan)}


def main():
    games = load()
    log(f"loaded {len(games['league'])} games 2015-2025; eval rows "
        f"{int((games['league'].season.between(*EVAL) & np.isfinite(games['league'].q)).sum())}")

    # ---- validation 1: my fit == nfl_model.fit_composite on the league variant (zero avail/context columns)
    lg = games['league'].copy(); lg['ready'] = True
    for c in m.feature_names(FAMILY):
        if c.startswith('d__avail__'): lg[c] = 0.
    for c in m.PRODUCT_CONTEXT_NAMES: lg[c] = 0.
    val = []
    for yr, wk in [(2017, 1), (2019, 9), (2021, 14), (2023, 1), (2025, 18)]:
        tr = lg[m.before(lg, yr, wk) & np.isfinite(lg.q)]
        te = lg[(lg.season == yr) & (lg.week == wk) & np.isfinite(lg.q)]
        fc = m.fit_composite(tr, m.LEGACY_PRODUCT_RECIPE, yr, wk)
        pc = m.apply_fit(te, fc, raw=True)
        mine = predict(te, fit(tr[tr['home won'].isin([0., 1.])], FEATS, yr, wk))
        val.append({'season': yr, 'week': wk, 'games': len(te), 'max_abs_prob_diff': float(np.max(np.abs(pc - mine))),
                    'training_games_fit_composite': fc['training_games']})
    log(f'validation vs fit_composite: {val}')
    if max(v['max_abs_prob_diff'] for v in val) > 1e-6:
        raise ValueError('simplified fit does not reproduce fit_composite arithmetic')

    coefs, preds = [], {}
    for v in VARIANTS:
        preds[v] = walk_forward(games[v], FEATS, v, coefs)
        log(f'{v}: {len(preds[v])} forecasts')
    # ---- validation 2: simplified league forecasts == the earlier run's p__league
    prior = pd.read_csv(PRIOR_PRED)[['game_id', 'p__league']]
    jj = preds['league'][['game_id', 'p']].merge(prior, on='game_id', how='outer', indicator=True)
    val2 = {'rows_unmatched': int((jj._merge != 'both').sum()), 'max_abs_diff_p_league': float(np.nanmax(np.abs(jj.p - jj.p__league)))}
    log(f'validation vs earlier market_test p__league: {val2}')
    if val2['rows_unmatched'] or val2['max_abs_diff_p_league'] > 1e-12:
        raise ValueError('simplified league forecasts differ from the earlier run')
    for v in ARMS:
        base = games['league'].copy(); ref = games[DELTA_REF[v]]
        dnames = []
        for c in PROFILE_COLS:
            dd = games[v]['d__' + c].to_numpy() - ref['d__' + c].to_numpy()
            if np.nanmax(np.abs(dd)) > 1e-9:
                base['delta__' + c] = dd; dnames.append('delta__' + c)
        preds['league+delta_' + v] = walk_forward(base, FEATS + dnames, 'league+delta_' + v, coefs)
        log(f'league+delta_{v}: {len(dnames)} delta features')

    keys = ['game_id', 'season', 'week', 'home_team', 'away_team', 'home won', 'q', 'result', 'home_moneyline', 'away_moneyline',
            'cur_both_continuous', 'all_boundaries_continuous']
    P = preds['league'][keys].copy()
    for k, d in preds.items():
        if not d.game_id.equals(P.game_id): raise ValueError('forecast rows differ')
        P['p__' + k] = d.p.to_numpy()
        if k.startswith('league+delta_'): P['dl__' + k] = d.delta_logit.to_numpy()
    P['p__league_fp'] = m.favorite_penalized_wp(P['p__league'], P.q)
    for v in ARMS: P['p__' + v + '_fp'] = m.favorite_penalized_wp(P['p__' + v], P.q)
    oos = pd.read_csv(OOS)[['game_id', 'production']].rename(columns={'production': 'p__prod_v116'})
    rep = pd.read_csv(REPRO)[['game_id', 'production_probability']].rename(columns={'production_probability': 'p__prod_v116'})
    P = P.merge(pd.concat([oos, rep]).drop_duplicates('game_id'), on='game_id', how='left')
    P.to_csv(OUT / 'retention_market_test_predictions.csv.gz', index=False)
    pd.DataFrame(coefs).to_csv(OUT / 'retention_market_test_coefficients.csv.gz', index=False)
    log('saved predictions and coefficients')

    models = ['league'] + ARMS + ['league+delta_' + v for v in ARMS]
    rows, inc_rows, wk_rows, sens, split_rows, pair_rows = [], [], [], [], [], []
    for era, (a, b) in ERAS.items():
        E = P[P.season.between(a, b)].copy()
        Y = E[E['home won'].isin([0., 1.])].copy()
        y = Y['home won'].to_numpy(float); g = wk_groups(Y)
        llq = ll(y, Y.q.to_numpy())
        ll_lg = ll(y, Y['p__league'].to_numpy())
        bets, common = bets_for(E, ['p__' + k for k in models])
        mbl = bets['p__league'][common]; fav = m.roi_summary(bets['_fav'][common])
        gg = wk_groups(E[common])
        for mdl in models:
            col = 'p__' + mdl
            l = ll(y, Y[col].to_numpy())
            sel = common & bets[col].units.notna()
            mb = bets[col][sel]; r = m.roi_summary(mb)
            mbl_m = bets['p__league'][sel]; fav_m = m.roi_summary(bets['_fav'][sel]); gg_m = wk_groups(E[sel])
            row = {'era': era, 'model': mdl, 'role': 'primary' if mdl in PRIMARY else 'control' if mdl in CONTROLS else
                   'reference' if mdl == 'league' else 'delta', 'n_ll': len(Y), 'll_model': l.mean(), 'll_market': llq.mean(),
                   'll_gain_vs_market': (llq - l).mean()}
            row['ll_gain_vs_market_ci95'] = boot(llq - l, g)
            if mdl != 'league':
                d = ll_lg - l
                row.update(ll_gain_vs_league=d.mean(), ll_gain_vs_league_ci95=boot(d, g),
                           ll_gain_vs_league_ci_bonf=boot(d, g, BONF_LEVEL))
                if mdl in ARMS:
                    lf, lfl = ll(y, Y[col + '_fp'].to_numpy()), ll(y, Y['p__league_fp'].to_numpy())
                    row['fp_ll_gain_vs_league'] = (lfl - lf).mean()
                    row['fp_ll_gain_vs_league_ci95'] = boot(lfl - lf, g)
            row.update(bets=r['bets'], wlp=f"{r['wins']}-{r['losses']}-{r['pushes']}", units=r['units'],
                       roi=r['roi'], roi_se=r['roi_se'], null_roi=r['null_roi'], null_units=float(mb.null_ev.sum()),
                       fav_units=fav_m['units'], fav_roi=fav_m['roi'], units_vs_fav=r['units'] - fav_m['units'],
                       underdog_picks=int((mb.q < .5).sum()))
            if mdl != 'league':
                du, flips, fs = flip_stats(mb, mbl_m)
                row.update(units_vs_league=float(du.sum()), roi_diff_vs_league=float(du.mean()),
                           roi_diff_vs_league_ci95=boot(du, gg_m), roi_diff_vs_league_ci_bonf=boot(du, gg_m, BONF_LEVEL),
                           **{k.replace('_ref', '_league'): v for k, v in fs.items()})
            mp = Y['p__prod_v116'].notna()
            if mp.any() and mdl == 'league':
                lp = ll(y[mp.to_numpy()], Y.loc[mp, 'p__prod_v116'].to_numpy())
                row['prod_v116_matched_n'] = int(mp.sum())
                row['prod_v116_ll_gain_vs_market'] = float((llq[mp.to_numpy()] - lp).mean())
                row['simplified_league_ll_gain_vs_market_matched'] = float((llq[mp.to_numpy()] - l[mp.to_numpy()]).mean())
                Em = E[E['p__prod_v116'].notna()]
                bm, cm = bets_for(Em, ['p__prod_v116', 'p__league'])
                rp, rs = m.roi_summary(bm['p__prod_v116'][cm]), m.roi_summary(bm['p__league'][cm])
                row.update(prod_v116_units=rp['units'], prod_v116_bets=rp['bets'], prod_v116_roi=rp['roi'],
                           prod_v116_roi_se=rp['roi_se'], simplified_league_units_matched=rs['units'],
                           fav_units_matched=m.roi_summary(bm['_fav'][cm])['units'])
            rows.append(row)
        # arm vs its flat control (does conditioning on continuity beat the same retention level everywhere?)
        for v, c in PAIRS.items():
            lc = ll(y, Y['p__' + c].to_numpy()); lv = ll(y, Y['p__' + v].to_numpy())
            du, flips, fs = flip_stats(bets['p__' + v][common], bets['p__' + c][common])
            pair_rows.append({'era': era, 'arm': v, 'control': c, 'n_ll': len(Y), 'll_gain_vs_control': (lc - lv).mean(),
                              'll_gain_vs_control_ci95': boot(lc - lv, g), 'units_arm': float(bets['p__' + v][common].units.sum()),
                              'units_control': float(bets['p__' + c][common].units.sum()), 'units_vs_control': float(du.sum()),
                              'roi_diff_vs_control': float(du.mean()), 'roi_diff_vs_control_ci95': boot(du, gg),
                              'bets': int(common.sum()), **fs})
        for v in ARMS:
            dl = E['dl__league+delta_' + v]
            inc_rows.append({'era': era, 'variant': v, 'delta_ref': DELTA_REF[v],
                             'sd_delta_logit': float(dl.std()), 'mean_abs_delta_logit_pp':
                             float(np.mean(np.abs(expit(logit(E['p__league+delta_' + v]))
                                                  - expit(logit(E['p__league+delta_' + v]) - dl))) * 100)})
        if era == 'All 2017-25':
            for wl, sel in [('wk1', Y.week == 1), ('wk2-8', Y.week.between(2, 8)), ('wk9+', Y.week >= 9)]:
                ss = sel.to_numpy()
                for v in ARMS + ['league+delta_' + v for v in ARMS]:
                    d = (ll_lg - ll(y, Y['p__' + v].to_numpy()))[ss]
                    wk_rows.append({'weeks': wl, 'model': v, 'n': int(ss.sum()), 'll_gain_vs_league': d.mean(),
                                    'ci95': boot(d, g[ss])})
            # continuity split (game level): both teams' current boundary continuous vs at least one changed;
            # and all six boundary flags continuous (where retention_cont_50_25 == league exactly)
            Ec = E[common.to_numpy()]
            splits = {'cur_both_continuous': Y.cur_both_continuous.to_numpy(bool),
                      'cur_any_changed': ~Y.cur_both_continuous.to_numpy(bool),
                      'all_boundaries_continuous': Y.all_boundaries_continuous.to_numpy(bool),
                      'any_boundary_changed': ~Y.all_boundaries_continuous.to_numpy(bool)}
            bsplits = {'cur_both_continuous': Ec.cur_both_continuous.to_numpy(bool),
                       'cur_any_changed': ~Ec.cur_both_continuous.to_numpy(bool),
                       'all_boundaries_continuous': Ec.all_boundaries_continuous.to_numpy(bool),
                       'any_boundary_changed': ~Ec.all_boundaries_continuous.to_numpy(bool)}
            for sn, ss in splits.items():
                bs = bsplits[sn]
                fsub = m.roi_summary(bets['_fav'][common][bs]); lsub = m.roi_summary(mbl[bs])
                for v in ARMS + ['league+delta_' + v for v in PRIMARY]:
                    d = (ll_lg - ll(y, Y['p__' + v].to_numpy()))[ss]
                    mb = bets['p__' + v][common][bs]; r = m.roi_summary(mb)
                    du, flips, fs = flip_stats(mb, mbl[bs])
                    split_rows.append({'split': sn, 'model': v, 'n_ll': int(ss.sum()), 'll_gain_vs_league': d.mean(),
                                       'll_gain_vs_league_ci95': boot(d, g[ss]), 'bets': r['bets'], 'units': r['units'],
                                       'roi': r['roi'], 'roi_se': r['roi_se'], 'null_roi': r['null_roi'],
                                       'league_units': lsub['units'], 'fav_units': fsub['units'], 'fav_roi': fsub['roi'],
                                       'units_vs_league': float(du.sum()), 'roi_diff_vs_league_ci95': boot(du, gg[bs]),
                                       **{k.replace('_ref', '_league'): v_ for k, v_ in fs.items()}})
            bad = [(2024, 'NYJ', 6), (2024, 'NO', 10), (2024, 'CHI', 14), (2025, 'TEN', 7), (2025, 'NYG', 11)]
            flag = np.zeros(len(Y), bool)
            for yr, tm, w0 in bad:
                flag |= ((Y.season == yr) & (Y.week >= w0) & ((Y.home_team == tm) | (Y.away_team == tm))).to_numpy()
            for v in PRIMARY + ['league+delta_' + v for v in PRIMARY]:
                d = (ll_lg - ll(y, Y['p__' + v].to_numpy()))[~flag]
                sens.append({'model': v, 'excluded_games': int(flag.sum()), 'n': int((~flag).sum()),
                             'll_gain_vs_league': d.mean(), 'ci95': boot(d, g[~flag])})

    R = pd.DataFrame(rows)
    R.to_csv(OUT / 'retention_market_test_summary.csv', index=False)
    pd.DataFrame(inc_rows).to_csv(OUT / 'retention_market_test_delta_logit_size.csv', index=False)
    pd.DataFrame(wk_rows).to_csv(OUT / 'retention_market_test_by_week_group.csv', index=False)
    pd.DataFrame(split_rows).to_csv(OUT / 'retention_market_test_by_continuity.csv', index=False)
    pd.DataFrame(pair_rows).to_csv(OUT / 'retention_market_test_vs_control.csv', index=False)

    C = pd.DataFrame(coefs)
    cs = []
    for v in ARMS:
        cm = C[C.model == 'league+delta_' + v]
        for c in [c for c in cm.columns if c.startswith('beta_std__delta__') and cm[c].notna().any()]:
            for era, (a, b) in ERAS.items():
                x = cm.loc[cm.season.between(a, b), c]
                cs.append({'variant': v, 'feature': c.replace('beta_std__delta__', ''), 'era': era,
                           'mean_beta_std': x.mean(), 'sd_beta_std': x.std(), 'share_positive': (x > 0).mean(),
                           'last_fit_beta_std': x.iloc[-1]})
    pd.DataFrame(cs).to_csv(OUT / 'retention_market_test_delta_coef_stability.csv', index=False)
    bc = []
    for mdl in VARIANTS:
        cm = C[C.model == mdl]
        for n in FEATS:
            for era, (a, b) in ERAS.items():
                x = cm.loc[cm.season.between(a, b), 'beta_std__' + n]
                bc.append({'model': mdl, 'feature': n, 'era': era, 'mean_beta_std': x.mean(), 'share_positive': (x > 0).mean()})
    pd.DataFrame(bc).to_csv(OUT / 'retention_market_test_base_coefficients.csv', index=False)

    res = {'validation_vs_fit_composite': val, 'validation_vs_earlier_p_league': val2, 'bonferroni_k': K_BONF,
           'bonferroni_level': BONF_LEVEL, 'bootstrap_reps': REPS, 'seed': SEED, 'features': FEATS, 'delta_reference': DELTA_REF,
           'coach_sensitivity': pd.DataFrame(sens).to_dict('records'), 'runtime_s': time.time() - T0,
           'post_hoc_note': 'arms added after the 7 earlier team-prior variants were scored on the same games'}
    (OUT / 'retention_market_test_results.json').write_text(json.dumps(res, indent=1, default=float))
    log('done')


if __name__ == '__main__':
    main()
