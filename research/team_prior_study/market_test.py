"""Team-prior shrinkage targets: market-anchored walk-forward test (exploratory, exposed seasons).

Research only. Reads the profile file built by build_team_prior_profiles.py, the repo's
research schedule (closing moneylines) and imports nfl_model for its math helpers. Nothing in the
repo, data/, the frozen recipe or the ledger is touched.

Model per variant (SIMPLIFIED production; NOT exact production):
  logit P(home win) = logit(q) + sum_j beta_j * x_j / s_j
  q = proportional no-vig closing moneyline home probability (nfl_model.market_ml_wp), fixed coefficient 1
  x = site + home-minus-away differences of the 16 box-score profiles (production names and order:
      7 'for' + 7 'allowed' rates_core metrics without sack %, then max_lead, max_deficit)
  OMITTED vs production: availability units (d__avail__*), the QB projection inside qb_delta, the five
      h16 pass-context terms, and the v1.18 favorite penalty (reported separately; it never flips sides).
  s = training-weighted SD (no centering of x), ridge 0.1 on standardized betas, site 0.01,
  training-row decay 2^-(age/(19*2)) with age in 19-week season slots, refit before every week on
  strictly earlier labeled games (2015 onward; MIN 150), exactly the arithmetic of nfl_model.fit_composite.

Incremental test: simplified league + DELTA features (variant profile minus reference profile,
home-minus-away). Reference = league_level for the team-type variants and 'none' (identical to league on
rates; removes the peak-level artifact), league for league_level and qb_offense.
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

PROFILES = WORK / 'profiles.csv.gz'
SCHED = MAIN / 'research' / 'form_windows_inputs' / 'schedule.csv'
OUT = WORK
OOS = MAIN / 'research' / 'out_of_sample_results' / 'predictions.csv'
REPRO = MAIN / 'research' / 'production_adoption_results' / 'historical_reproduction.csv'

FAMILY = 'rates_core_avail_cs_peaks_nosacks'
FEATS = [n for n in m.feature_names(FAMILY) if not n.startswith('d__avail__')]
PROFILE_COLS = [n[3:] for n in FEATS if n != 'site']
assert len(PROFILE_COLS) == 16, PROFILE_COLS
VARIANTS = ['league', 'league_level', 'team_window', 'team_prior', 'continuity', 'coach', 'qb_offense', 'none']
ARMS = VARIANTS[1:]                                   # compared with the simplified league
DELTA_REF = {'league_level': 'league', 'qb_offense': 'league', 'team_window': 'league_level',
             'team_prior': 'league_level', 'continuity': 'league_level', 'coach': 'league_level',
             'none': 'league_level'}
RIDGE, SITE_MULT, FIT_HL, MIN_TRAIN = .1, .1, 2., 150
FIRST_TRAIN, EVAL = 2015, (2017, 2025)
ERAS = {'2017-20': (2017, 2020), '2021-22': (2021, 2022), '2023-25': (2023, 2025), 'All 2017-25': (2017, 2025)}
REPS, SEED = 2000, m.SEED
K_BONF = len(ARMS)                                     # 7 variant-vs-league comparisons
BONF_LEVEL = 1 - .05 / K_BONF
T0 = time.time()


def log(s):
    print(f'[{time.time() - T0:5.0f}s] {s}', flush=True)


# ---------------------------------------------------------------- data
def load():
    p = pd.read_csv(PROFILES, low_memory=False)
    p = p[p.season <= EVAL[1]]
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
        g = s.set_index('game_id').join(h[['team', 'neutral_site'] + PROFILE_COLS], how='inner')
        g = g.join(a[['team'] + PROFILE_COLS].add_prefix('a_'), how='inner')
        if not (g.team == g.home_team).all() or not (g.a_team == g.away_team).all():
            raise ValueError('home/away mismatch between profiles and schedule')
        if not ((g.neutral_site.astype(str) == 'True') == (g.site == 0)).all():
            raise ValueError('neutral-site mismatch')
        for c in PROFILE_COLS:
            g['d__' + c] = g[c] - g['a_' + c]
        games[v] = g[['season', 'week', 'home_team', 'away_team', 'home won', 'site', 'q', 'result',
                      'home_moneyline', 'away_moneyline'] + ['d__' + c for c in PROFILE_COLS]].reset_index()
        games[v] = games[v].sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
    ids = games['league'].game_id
    for v in VARIANTS:
        if not games[v].game_id.equals(ids):
            raise ValueError('variant game sets differ')
    return games


# ---------------------------------------------------------------- fit (fit_composite arithmetic)
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
                 'home_moneyline', 'away_moneyline']].copy()
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


# ---------------------------------------------------------------- scoring
def ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def boot(v, g, level=.95, reps=REPS, seed=SEED):
    """Week-cluster percentile bootstrap of the per-game mean (ratio of resampled sums)."""
    a = pd.DataFrame({'v': np.asarray(v, float), 'g': np.asarray(g)}).groupby('g').v.agg(['sum', 'count'])
    if len(a) < 2:
        return [np.nan, np.nan]
    i = np.random.default_rng(seed).integers(0, len(a), (reps, len(a)))
    d = a['sum'].to_numpy()[i].sum(1) / a['count'].to_numpy()[i].sum(1)
    return np.quantile(d, [(1 - level) / 2, (1 + level) / 2]).tolist()


def wk_groups(d):
    return (d.season.astype(str) + '_' + d.week.astype(str).str.zfill(2)).to_numpy()


def bets_for(d, cols):
    """Flat 1u bets for each column and the market favorite; common = graded, priced rows where every
    column and the market favorite place a bet (q = 0.5 pick'em rows and model p = 0.5 drop out for all)."""
    d = d.copy(); d['_q'] = m.market_ml_wp(d)
    b = {c: m.flat_bets(d, c) for c in cols}
    b['_fav'] = m.flat_bets(d, '_q')
    # Shared rows: replacement models, league and the favorite. A delta arm can sit within 5e-6 of
    # p = .5 (no bet) on a game the others bet; it is masked per model in main(), not for every model.
    common = np.logical_and.reduce([x.units.notna().to_numpy() for c, x in b.items() if '+delta_' not in c])
    return b, pd.Series(common, index=d.index)


def fmt_iv(iv, k=5):
    return f'[{iv[0]:+.{k}f}, {iv[1]:+.{k}f}]'


def main():
    games = load()
    n_all = len(games['league'])
    log(f'loaded {n_all} games 2015-2025; eval rows '
        f"{int((games['league'].season.between(*EVAL) & np.isfinite(games['league'].q)).sum())}")

    # ---- validation: my fit == nfl_model.fit_composite on the league variant (zero avail/context columns)
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

    # ---- walk-forward per variant
    coefs = []
    preds = {}
    for v in VARIANTS:
        preds[v] = walk_forward(games[v], FEATS, v, coefs)
        log(f'{v}: {len(preds[v])} forecasts')
    # ---- incremental DELTA models: simplified league + (variant - reference) differences
    for v in ARMS:
        base = games['league'].copy(); ref = games[DELTA_REF[v]]
        dnames = []
        for c in PROFILE_COLS:
            dd = games[v]['d__' + c].to_numpy() - ref['d__' + c].to_numpy()
            if np.nanmax(np.abs(dd)) > 1e-9:          # skip identically-zero deltas (qb_offense, league_level rates)
                base['delta__' + c] = dd; dnames.append('delta__' + c)
        preds['league+delta_' + v] = walk_forward(base, FEATS + dnames, 'league+delta_' + v, coefs)
        log(f'league+delta_{v}: {len(dnames)} delta features')

    # ---- assemble
    keys = ['game_id', 'season', 'week', 'home_team', 'away_team', 'home won', 'q', 'result', 'home_moneyline', 'away_moneyline']
    P = preds['league'][keys].copy()
    for k, d in preds.items():
        if not d.game_id.equals(P.game_id): raise ValueError('forecast rows differ')
        P['p__' + k] = d.p.to_numpy()
        if k.startswith('league+delta_'): P['dl__' + k] = d.delta_logit.to_numpy()
    P['p__league_fp'] = m.favorite_penalized_wp(P['p__league'], P.q)
    for v in ARMS: P['p__' + v + '_fp'] = m.favorite_penalized_wp(P['p__' + v], P.q)
    # full production v1.16 reconstructions (reference only, where they exist)
    oos = pd.read_csv(OOS)[['game_id', 'production']].rename(columns={'production': 'p__prod_v116'})
    rep = pd.read_csv(REPRO)[['game_id', 'production_probability']].rename(columns={'production_probability': 'p__prod_v116'})
    P = P.merge(pd.concat([oos, rep]).drop_duplicates('game_id'), on='game_id', how='left')
    P.to_csv(OUT / 'market_test_predictions.csv.gz', index=False)
    pd.DataFrame(coefs).to_csv(OUT / 'market_test_coefficients.csv.gz', index=False)
    log('saved predictions and coefficients')

    models = ['league'] + ARMS + ['league+delta_' + v for v in ARMS]
    eras = {**ERAS}
    rows, inc_rows, wk_rows, sens = [], [], [], []
    for era, (a, b) in eras.items():
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
            row = {'era': era, 'model': mdl, 'n_ll': len(Y), 'll_model': l.mean(), 'll_market': llq.mean(),
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
                    if DELTA_REF[mdl] == 'league_level':  # team-type: identity/team part vs the level reference
                        d2 = ll(y, Y['p__league_level'].to_numpy()) - l
                        row['ll_gain_vs_league_level'] = d2.mean()
                        row['ll_gain_vs_league_level_ci95'] = boot(d2, g)
            # flat ROI (goal metric), common rows for every model and the market favorite
            row.update(bets=r['bets'], wlp=f"{r['wins']}-{r['losses']}-{r['pushes']}", units=r['units'],
                       roi=r['roi'], roi_se=r['roi_se'], null_roi=r['null_roi'], null_units=float(mb.null_ev.sum()),
                       fav_units=fav_m['units'], fav_roi=fav_m['roi'], units_vs_fav=r['units'] - fav_m['units'],
                       underdog_picks=int((mb.q < .5).sum()))
            if mdl != 'league':
                du = (mb.units - mbl_m.units).to_numpy()
                flips = (mb.side != mbl_m.side).to_numpy()
                fv, fl_ = mb[flips], mbl_m[flips]
                row.update(units_vs_league=float(du.sum()), roi_diff_vs_league=float(du.mean()),
                           roi_diff_vs_league_ci95=boot(du, gg_m), roi_diff_vs_league_ci_bonf=boot(du, gg_m, BONF_LEVEL),
                           side_flips=int(flips.sum()),
                           flip_wlp_variant=f"{int((fv.result=='W').sum())}-{int((fv.result=='L').sum())}-{int((fv.result=='P').sum())}",
                           flip_units_variant=float(fv.units.sum()), flip_units_league=float(fl_.units.sum()),
                           flip_null_units_variant=float(fv.null_ev.sum()), flip_null_units_league=float(fl_.null_ev.sum()),
                           # flipped games sit near pick'em and, under proportional de-vig, both sides share one null EV
                           flip_binom_p_two_sided=(float(binomtest(int((fv.result == 'W').sum()), int(fv.result.isin(['W', 'L']).sum()), .5).pvalue)
                                                   if fv.result.isin(['W', 'L']).any() else np.nan))
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
        # incremental delta: size of the delta part of the forecast logit
        for v in ARMS:
            dl = E['dl__league+delta_' + v]
            inc_rows.append({'era': era, 'variant': v, 'delta_ref': DELTA_REF[v],
                             'sd_delta_logit': float(dl.std()), 'mean_abs_delta_logit_pp':
                             float(np.mean(np.abs(expit(logit(E['p__league+delta_' + v]))
                                                  - expit(logit(E['p__league+delta_' + v]) - dl))) * 100)})
        # week-of-season diagnostic (all eras pooled is the 'All' era)
        if era == 'All 2017-25':
            for wl, sel in [('wk1', Y.week == 1), ('wk2-8', Y.week.between(2, 8)), ('wk9+', Y.week >= 9)]:
                ss = sel.to_numpy()
                for v in ARMS + ['league+delta_' + v for v in ARMS]:
                    d = (ll_lg - ll(y, Y['p__' + v].to_numpy()))[ss]
                    wk_rows.append({'weeks': wl, 'model': v, 'n': int(ss.sum()), 'll_gain_vs_league': d.mean(),
                                    'ci95': boot(d, g[ss])})
            # coach sensitivity: drop games touching team-weeks flagged as mislabeled coaches (builder note)
            bad = [(2024, 'NYJ', 6), (2024, 'NO', 10), (2024, 'CHI', 14), (2025, 'TEN', 7), (2025, 'NYG', 11)]
            flag = np.zeros(len(Y), bool)
            for yr, tm, w0 in bad:
                flag |= ((Y.season == yr) & (Y.week >= w0) & ((Y.home_team == tm) | (Y.away_team == tm))).to_numpy()
            for v in ['coach', 'league+delta_coach']:
                d = (ll_lg - ll(y, Y['p__' + v].to_numpy()))[~flag]
                sens.append({'model': v, 'excluded_games': int(flag.sum()), 'n': int((~flag).sum()),
                             'll_gain_vs_league': d.mean(), 'ci95': boot(d, g[~flag])})

    R = pd.DataFrame(rows); I = pd.DataFrame(inc_rows); W = pd.DataFrame(wk_rows); SN = pd.DataFrame(sens)
    R.to_csv(OUT / 'market_test_summary.csv', index=False)
    I.to_csv(OUT / 'market_test_delta_logit_size.csv', index=False)
    W.to_csv(OUT / 'market_test_by_week_group.csv', index=False)

    # coefficient stability (delta models): per era, standardized beta mean, SD across weekly fits, share > 0
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
        # base-feature comparison: matching base coefficient in the same model
    CS = pd.DataFrame(cs)
    CS.to_csv(OUT / 'market_test_delta_coef_stability.csv', index=False)
    # base-model coefficient means by era (league vs variant arms), for context
    bc = []
    for mdl in VARIANTS:
        cm = C[C.model == mdl]
        for n in FEATS:
            for era, (a, b) in ERAS.items():
                x = cm.loc[cm.season.between(a, b), 'beta_std__' + n]
                bc.append({'model': mdl, 'feature': n, 'era': era, 'mean_beta_std': x.mean(), 'share_positive': (x > 0).mean()})
    pd.DataFrame(bc).to_csv(OUT / 'market_test_base_coefficients.csv', index=False)

    res = {'validation_vs_fit_composite': val, 'bonferroni_k': K_BONF, 'bonferroni_level': BONF_LEVEL,
           'bootstrap_reps': REPS, 'seed': SEED, 'features': FEATS, 'delta_reference': DELTA_REF,
           'coach_sensitivity': SN.to_dict('records'), 'runtime_s': time.time() - T0}
    (OUT / 'market_test_results.json').write_text(json.dumps(res, indent=1, default=float))
    log('done')


if __name__ == '__main__':
    main()
