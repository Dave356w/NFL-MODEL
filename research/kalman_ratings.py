"""Test 40: a separate model on dynamic play-efficiency ratings, against production; see KALMAN_RATINGS.md.

    python research/kalman_ratings.py --build [CACHE_DIR]   # download nflverse play-by-play, freeze team-game observations
    python research/kalman_ratings.py                       # ratings, model, comparison (no network)

Never writes data/ or the ledger. Development evidence only.
"""
import argparse
import datetime as dt
import hashlib
import json
import sys
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import residual_trends as t  # noqa: E402
import feature_importance as fi  # noqa: E402
import model_updates as mu  # noqa: E402

INPUTS = ROOT/'research/kalman_ratings_inputs'
TEAM_GAMES = INPUTS/'team_games.csv'
OUT = ROOT/'research/kalman_ratings_results'
PROTOCOL_COMMIT = '0562c5e'
SEASONS = range(2013, 2027)
PBP_URL = 'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{y}.parquet'
PBP_COLS = ['game_id', 'season', 'week', 'season_type', 'posteam', 'defteam', 'home_team', 'away_team', 'play_type',
            'pass', 'rush', 'epa', 'down', 'ydstogo', 'yards_gained', 'touchdown', 'td_team', 'two_point_attempt', 'play_deleted']
METRICS = ('epa', 'sr')
PLAYS = ('pass', 'rush')
TUNE_SEASONS = (2013, 2014)
Q_GRID, RHO_GRID, P0_GRID = (.25, .5, 1., 2., 4.), (.4, .6, .8), (.5, 1., 2.)
PRIMARY = ('kalman_epa', 'kalman_sr', 'blend')
CONTEXT = ('kalman_epa_standalone',)
LEVEL = 1-.05/len(PRIMARY)
Z = float(norm.ppf(1-(1-LEVEL)/2))
MODEL_INPUTS = ['site', 'pass_edge', 'rush_edge', 'd__avail__qb_delta']


# --- build: freeze team-game observations ----------------------------------------------------------

def rule_success(down, togo, gain, td):
    """Rule-based success, no model: >= 40% of the distance on 1st down, 60% on 2nd, 100% on 3rd/4th,
    or an offensive touchdown. NaN when the down is missing."""
    down, togo, gain = (np.asarray(x, float) for x in (down, togo, gain))
    need = np.select([down == 1, down == 2, (down == 3) | (down == 4)], [.4*togo, .6*togo, togo], np.nan)
    s = np.where(np.isfinite(need), (gain >= need).astype(float), np.nan)
    return np.where(np.asarray(td, bool), 1., s)


def aggregate(p):
    """Team-game offensive observations from one season of play-by-play."""
    p = p[(p.season_type == 'REG') & p.play_type.isin(['pass', 'run'])].copy()
    if 'play_deleted' in p: p = p[pd.to_numeric(p.play_deleted, errors='coerce').fillna(0) != 1]
    p = p[pd.to_numeric(p.two_point_attempt, errors='coerce').fillna(0) != 1]
    for c in ('posteam', 'defteam', 'home_team', 'away_team', 'td_team'): p[c] = p[c].replace(m.TEAM_ALIASES)
    p['kind'] = np.where(pd.to_numeric(p['pass'], errors='coerce') == 1, 'pass',
                         np.where(pd.to_numeric(p['rush'], errors='coerce') == 1, 'rush', None))
    p = p[p.kind.notna() & p.epa.notna()]
    p['sr'] = rule_success(p.down, p.ydstogo, p.yards_gained, (p.touchdown == 1) & (p.td_team == p.posteam))
    p['epa2'] = p.epa**2
    rows = []
    for (gid, team, kind), g in p.groupby(['game_id', 'posteam', 'kind']):
        rows.append({'game_id': gid, 'season': int(g.season.iloc[0]), 'week': int(g.week.iloc[0]), 'team': team,
                     'opp': g.defteam.iloc[0], 'home': int(team == g.home_team.iloc[0]), 'kind': kind, 'n': len(g),
                     'epa_sum': float(g.epa.sum()), 'epa_sumsq': float(g.epa2.sum()),
                     'sr_n': int(g.sr.notna().sum()), 'sr_sum': float(np.nansum(g.sr))})
    return pd.DataFrame(rows)


def build(cache):
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True); INPUTS.mkdir(parents=True, exist_ok=True)
    parts, prov = [], {'source': PBP_URL, 'built_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'files': {}}
    for y in SEASONS:
        f = cache/f'play_by_play_{y}.parquet'
        if not f.exists():
            import urllib.request
            urllib.request.urlretrieve(PBP_URL.format(y=y), f)
        prov['files'][f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
        p = pd.read_parquet(f, columns=PBP_COLS)
        a = aggregate(p); parts.append(a)
        print(f'  {y}: {p.shape[0]} plays -> {len(a)} team-game-kind rows')
    tg = pd.concat(parts, ignore_index=True).sort_values(['season', 'week', 'game_id', 'team', 'kind'])
    tg.to_csv(TEAM_GAMES, index=False, float_format='%.6f')
    prov.update(team_games_sha256=hashlib.sha256(TEAM_GAMES.read_bytes()).hexdigest(), rows=len(tg),
                last_game=str(tg.game_id.iloc[-1]),
                note='Raw play-by-play is not committed. Plays: REG, play_type pass/run, not deleted, not two-point, epa present.')
    (INPUTS/'provenance.json').write_text(json.dumps(prov, indent=2))
    return tg


# --- Kalman ratings --------------------------------------------------------------------------------

def observations(tg, metric, kind):
    """One row per game: raw per-play means and play counts for the home and away offenses."""
    d = tg[tg.kind == kind].copy()
    if metric == 'epa': d['y'], d['n_obs'] = d.epa_sum/d.n, d.n
    else: d['y'], d['n_obs'] = d.sr_sum/d.sr_n.replace(0, np.nan), d.sr_n
    h = d[d.home == 1][['game_id', 'season', 'week', 'team', 'opp', 'y', 'n_obs']].rename(
        columns={'team': 'home', 'opp': 'away', 'y': 'y_home', 'n_obs': 'n_home'})
    a = d[d.home == 0][['game_id', 'y', 'n_obs']].rename(columns={'y': 'y_away', 'n_obs': 'n_away'})
    o = h.merge(a, on='game_id', how='inner')
    return o[np.isfinite(o.y_home) & np.isfinite(o.y_away) & (o.n_home > 0) & (o.n_away > 0)].sort_values(['season', 'week', 'game_id'])


def play_variance(tg, metric, kind):
    d = tg[(tg.kind == kind) & tg.season.isin(TUNE_SEASONS)]
    if metric == 'epa':
        n = d.n.sum(); mean = d.epa_sum.sum()/n
        return float(d.epa_sumsq.sum()/n-mean**2)
    p = d.sr_sum.sum()/d.sr_n.sum()
    return float(p*(1-p))


def season_mean_variance(tg, metric, kind):
    d = tg[(tg.kind == kind) & tg.season.isin(TUNE_SEASONS)]
    num, den = ('epa_sum', 'n') if metric == 'epa' else ('sr_sum', 'sr_n')
    s = d.groupby(['season', 'team'])[[num, den]].sum()
    return float((s[num]/s[den]).var(ddof=1))


def kalman(obs, teams, sigma2, q, rho, p0, tune=TUNE_SEASONS):
    """Full-covariance filter over offense/defense states per team. Returns the pregame snapshot per game
    (taken before any game of its week is filtered) and the predictive log-likelihood of the
    observations in the tuning seasons. League mean and home effect use strictly earlier games
    (2013 week 1, which has none, uses its own week)."""
    ix = {tm: i for i, tm in enumerate(teams)}; k = 2*len(teams)
    x = np.zeros(k); P = np.eye(k)*p0
    sum_y = sum_n = 0.; home_diffs = []
    snaps, loglik, season = [], 0., None
    for (yr, wk), g in obs.groupby(['season', 'week'], sort=True):
        if season is not None:
            if yr != season:
                x = rho*x; P = rho*rho*P+np.eye(k)*p0*(1-rho*rho)
            else:
                P = P+np.eye(k)*q
        season = yr
        for r in g.itertuples(index=False):
            h, a = ix[r.home], ix[r.away]
            snaps.append({'game_id': r.game_id, 'off_h': x[2*h], 'def_h': x[2*h+1], 'off_a': x[2*a], 'def_a': x[2*a+1]})
        if sum_n > 0: mean, home = sum_y/sum_n, (np.mean(home_diffs) if home_diffs else 0.)
        else:
            mean = float((g.y_home*g.n_home+g.y_away*g.n_away).sum()/(g.n_home+g.n_away).sum())
            home = float(((g.y_home-g.y_away)/2).mean())
        for r in g.itertuples(index=False):
            h, a = ix[r.home], ix[r.away]
            for off, dfn, y, n in ((2*h, 2*a+1, r.y_home-mean-home, r.n_home), (2*a, 2*h+1, r.y_away-mean+home, r.n_away)):
                pred = x[off]+x[dfn]
                Ph = P[:, off]+P[:, dfn]
                S = Ph[off]+Ph[dfn]+sigma2/n
                if yr in tune: loglik += -.5*(np.log(2*np.pi*S)+(y-pred)**2/S)
                K = Ph/S
                x = x+K*(y-pred)
                P = P-np.outer(K, Ph)
        sum_y += float((g.y_home*g.n_home+g.y_away*g.n_away).sum()); sum_n += float((g.n_home+g.n_away).sum())
        home_diffs += list(((g.y_home-g.y_away)/2).to_numpy())
    return pd.DataFrame(snaps), loglik


def tune_and_rate(tg):
    """Per metric: choose (q, rho, P0) by 2013-14 predictive likelihood (pass + rush), then rate all seasons."""
    teams = sorted(set(tg.team) | set(tg.opp))
    edges, tuning = {}, {}
    for metric in METRICS:
        obs = {k: observations(tg, metric, k) for k in PLAYS}
        s2 = {k: play_variance(tg, metric, k) for k in PLAYS}
        v0 = {k: season_mean_variance(tg, metric, k) for k in PLAYS}
        grid = []
        for qm in Q_GRID:
            for rho in RHO_GRID:
                for pm in P0_GRID:
                    ll = sum(kalman(obs[k][obs[k].season.isin(TUNE_SEASONS)], teams, s2[k], qm*1e-3*s2[k]/30, rho, pm*v0[k])[1]
                             for k in PLAYS)
                    grid.append({'q_mult': qm, 'rho': rho, 'p0_mult': pm, 'loglik': ll})
        grid = pd.DataFrame(grid); best = grid.loc[grid.loglik.idxmax()]
        tuning[metric] = {'chosen': {k: float(best[k]) for k in ('q_mult', 'rho', 'p0_mult')}, 'loglik': float(best.loglik),
                          'sigma2': s2, 'season_mean_var': v0, 'grid': json.loads(grid.to_json(orient='records'))}
        e = None
        for k in PLAYS:
            snap, _ = kalman(obs[k], teams, s2[k], best.q_mult*1e-3*s2[k]/30, best.rho, best.p0_mult*v0[k])
            snap[f'{k}_edge'] = (snap.off_h+snap.def_a)-(snap.off_a+snap.def_h)
            e = snap[['game_id', f'{k}_edge']] if e is None else e.merge(snap[['game_id', f'{k}_edge']], on='game_id')
        edges[metric] = e
    return edges, tuning


# --- model -----------------------------------------------------------------------------------------

def eligible(f):
    """Production's training rows (fit_composite with the market offset)."""
    return (f['home won'].isin([0., 1.]) & f.ready.astype(bool) & np.isfinite(f.q)
            & np.isfinite(f[list(m.PRODUCT_CONTEXT_NAMES)]).all(axis=1))


def fit(train, names, year, week, ridge=.1, offset=True):
    """fit_composite's objective for an arbitrary input list: weekly decayed weighted mean log loss,
    SD-scaled inputs (site unscaled), ridge with site at 0.1x, market log-odds offset; without the
    offset an unpenalized intercept is added."""
    tr = train[eligible(train)]
    if len(tr) < m.MIN_TRAIN_GAMES: raise ValueError('Too few training games')
    if not m.before(tr, year, week).all(): raise ValueError('Training includes current/future week')
    X = np.where(np.isfinite(tr[names].to_numpy(float)), tr[names].to_numpy(float), 0.)
    age = ((year-tr.season.to_numpy())*19+(week-tr.week.to_numpy()))/(19*m.FIT_HALF_LIFE_SEASONS)
    w = np.exp2(-age); w /= w.sum()
    mu_ = (w[:, None]*X).sum(axis=0); scale = np.sqrt((w[:, None]*(X-mu_)**2).sum(axis=0))
    scale = np.where(scale > 1e-8, scale, 1.)
    if 'site' in names: scale[names.index('site')] = 1.
    pen = np.full(len(names), ridge)
    if 'site' in names: pen[names.index('site')] *= .1
    Zm = X/scale
    if not offset: Zm = np.column_stack([np.ones(len(Zm)), Zm]); pen = np.concatenate([[0.], pen])
    y = tr['home won'].to_numpy(float)
    base = logit(np.clip(tr.q.to_numpy(), 1e-5, 1-1e-5)) if offset else np.zeros(len(tr))
    def obj(b):
        eta = base+Zm@b
        return (np.sum(w*(np.logaddexp(0, eta)-y*eta))+.5*np.sum(pen*b*b), Zm.T@(w*(expit(eta)-y))+pen*b)
    beta = m.checked_optimize(obj, Zm.shape[1])
    return {'names': names, 'scale': scale, 'beta': beta, 'offset': offset}


def predict(df, f):
    X = df[f['names']].to_numpy(float); X = np.where(np.isfinite(X), X, 0.)/f['scale']
    if f['offset']: return expit(logit(np.clip(df.q.to_numpy(float), 1e-5, 1-1e-5))+X@f['beta'])
    return expit(f['beta'][0]+X@f['beta'][1:])


def novel_frame(parts, edges, offset=True):
    rows, coefs = [], []
    for pack, games in parts:
        pk, gm = pack.merge(edges, on='game_id', how='left'), games.merge(edges, on='game_id', how='left')
        for (y, w), g in gm.groupby(['season', 'week']):
            f = fit(pk[m.before(pk, int(y), int(w))], MODEL_INPUTS, int(y), int(w), offset=offset)
            rows.append(g.assign(p16=predict(g, f)))
            coefs.append({'season': int(y), 'week': int(w), **{n: float(b) for n, b in zip(MODEL_INPUTS, f['beta'][-len(MODEL_INPUTS):])}})
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    d = t.prepare(d)
    if not offset: d['p'] = d.p16  # the favorite penalty is defined relative to the market; not applied here
    return d, pd.DataFrame(coefs)


def blend_frame(prod, nov):
    j = prod.merge(nov[['game_id', 'p16']].rename(columns={'p16': 'p16_k'}), on='game_id', validate='one_to_one')
    lq = logit(j.q)
    j['p16'] = expit(lq+.5*(logit(j.p16)-lq)+.5*(logit(j.p16_k)-lq))
    return t.prepare(j.drop(columns=['p', 'p16_k', 'units', 'side', 'null_ev', 'fav_units', 'bet', 'y', 'departure',
                                     'departure16', 'market_logit', 'cluster']))


def vs_market(d):
    b = d[d.y.notna()]
    g = mu.ll(b.y, b.q)-mu.ll(b.y, b.p)
    mean, se = fi.cmean(g, b.cluster)
    return 1000*mean, 1000*se


def verdict(rows):
    a = rows[rows.context == 'all'].set_index('basis').reindex(list(fi.BASES))
    if (a.ll_gain_x1000 <= 0).sum() >= 2: return 'not better than production'
    if (a.ll_gain_x1000 > 0).all() and (a.lo_x1000 > 0).any(): return 'better than production: worth a forward shadow test'
    return 'unresolved'


def compare(prod, arm, basis, name):
    old = mu.Z; mu.Z = Z
    try: return mu.compare(prod, arm, basis, name)
    finally: mu.Z = old


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    tg = pd.read_csv(TEAM_GAMES)
    edges, tuning = tune_and_rate(tg)
    parts = {**fi.basis_parts(), '2026 wk1-5 (diagnostic)': mu.extra_parts()['2026 wk1-5 (diagnostic)']}
    prod = {b: mu.basis_frame(p, 'production', b) for b, p in parts.items()}
    repro = fi.reproduction({b: prod[b] for b in fi.BASES})
    arms, coefs, rows, mkt, corr = {}, {}, [], [], {}
    for b, p in parts.items():
        arms[(b, 'kalman_epa')], coefs[b] = novel_frame(p, edges['epa'])
        arms[(b, 'kalman_sr')], _ = novel_frame(p, edges['sr'])
        arms[(b, 'blend')] = blend_frame(prod[b], arms[(b, 'kalman_epa')])
        arms[(b, 'kalman_epa_standalone')], _ = novel_frame(p, edges['epa'], offset=False)
        j = prod[b][['game_id', 'departure16']].merge(arms[(b, 'kalman_epa')][['game_id', 'departure16']], on='game_id', suffixes=('_p', '_k'))
        corr[b] = float(np.corrcoef(j.departure16_p, j.departure16_k)[0, 1])
        for name in PRIMARY+CONTEXT:
            rows += compare(prod[b], arms[(b, name)], b, name)
            g, se = vs_market(arms[(b, name)]); mkt.append({'basis': b, 'arm': name, 'll_gain_vs_market_x1000': g, 'se_x1000': se})
        g, se = vs_market(prod[b]); mkt.append({'basis': b, 'arm': 'production', 'll_gain_vs_market_x1000': g, 'se_x1000': se})
    res = pd.DataFrame(rows); res.to_csv(out/'arms.csv', index=False, float_format='%.6g')
    mkt = pd.DataFrame(mkt); mkt.to_csv(out/'vs_market.csv', index=False, float_format='%.6g')
    pd.concat([e.assign(metric=k) for k, e in edges.items()]).to_csv(out/'edges.csv.gz', index=False, float_format='%.6g')
    pd.concat([a[['game_id', 'p']].assign(basis=b, arm=n) for (b, n), a in arms.items()] +
              [d[['game_id', 'p']].assign(basis=b, arm='production') for b, d in prod.items()]).to_csv(
        out/'predictions.csv.gz', index=False, float_format='%.6g')
    cstats = {b: {n: {'mean_beta_per_sd': float(c[n].mean()), 'share_positive': float((c[n] > 0).mean())} for n in MODEL_INPUTS}
              for b, c in coefs.items()}
    prod_roi = {b: m.roi_summary(m.flat_bets(d[d.bet].assign(model_wp=d.p[d.bet]))) for b, d in prod.items()}
    info = {'protocol': 'research/KALMAN_RATINGS.md', 'protocol_commit': PROTOCOL_COMMIT, 'level': LEVEL,
            'reproduction_max_error': repro, 'tuning': {k: {kk: vv for kk, vv in v.items() if kk != 'grid'} for k, v in tuning.items()},
            'verdicts': {a: verdict(res[res.arm == a]) for a in PRIMARY}, 'departure_corr_prod_vs_kalman_epa': corr,
            'coefficients': cstats, 'binary_games': {b: int(d.y.notna().sum()) for b, d in prod.items()},
            'production_roi': {b: {k: float(v) if isinstance(v, (int, float, np.integer, np.floating)) else v for k, v in s.items()}
                               for b, s in prod_roi.items()}}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=True))
    (out/'tuning_grid.json').write_text(json.dumps({k: v['grid'] for k, v in tuning.items()}, indent=1))
    prov = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/'research/KALMAN_RATINGS.md', ROOT/'nfl_model.py', TEAM_GAMES,
                                                       ROOT/'research/model_updates.py', ROOT/'research/feature_importance.py',
                                                       t.OOS_PACK, t.T36_PACK, t.OOS_PRED, t.HELDOUT, t.RETRO, t.TOTALS)}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2))
    write_report(info, res, mkt, prod_roi, out)
    return info, res, mkt


def _f(x, fmt='+.2f'):
    return 'n/a' if x is None or not np.isfinite(x) else format(x, fmt)


def write_report(info, res, mkt, prod_roi, out):
    B = list(fi.BASES); allr = res[res.context == 'all']
    L = ['# Test 40: a separate model on dynamic play-efficiency ratings, against production', '',
         f"Protocol: [KALMAN_RATINGS.md](../KALMAN_RATINGS.md), pushed (`{PROTOCOL_COMMIT}`) before any rating, feature or forecast "
         'was computed. Production v1.18 and the ledger are unchanged. Development evidence only.', '',
         'Production reproduces its published forecasts: ' + ', '.join(f'{k} {v:.1e}' for k, v in info['reproduction_max_error'].items()) + '.', '',
         '**Model.** `logit p = logit q + b*[pass_edge, rush_edge, qb_delta, site]`, where the edges come from a full-covariance Kalman '
         'filter over every team\'s pass/rush offense and defense (per-play efficiency, opponent-adjusted, drifting weekly, regressed '
         'between seasons). Fit, decay, ridge and the favorite penalty are production\'s.', '',
         '**Tuning (2013-14 observation likelihood only):** ' + '; '.join(
             f"{k.upper()}: q x{v['chosen']['q_mult']:g}, rho {v['chosen']['rho']:g}, P0 x{v['chosen']['p0_mult']:g}" for k, v in info['tuning'].items()) + '.', '',
         '## Verdicts (log-loss gain over production decides)', '']
    for a in PRIMARY: L.append(f"- **{a}**: {info['verdicts'][a]}")
    L += ['', f"Rule: better if the gain is positive on all three bases and its {100*LEVEL:.2f}% interval excludes zero on at least one; "
          'not better if <= 0 on two or more; otherwise unresolved.', '',
          '## Log-loss gain over production (x1000 per game; [98.33% interval])', '',
          '| Arm | ' + ' | '.join(B) + ' | 2026 wk1-5 (diag.) |', '|---|' + '---:|'*(len(B)+1)]
    for a in PRIMARY+CONTEXT:
        r = allr[allr.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join(f"{r.loc[b, 'll_gain_x1000']:+.2f} [{r.loc[b, 'lo_x1000']:+.2f}, {r.loc[b, 'hi_x1000']:+.2f}]" for b in B)
                 + f" | {r.loc['2026 wk1-5 (diagnostic)', 'll_gain_x1000']:+.2f} |")
    L += ['', '## Log-loss gain over the market (x1000 per game ± SE)', '', '| Model | ' + ' | '.join(B) + ' | 2026 wk1-5 |', '|---|' + '---:|'*(len(B)+1)]
    for a in ('production',)+PRIMARY+CONTEXT:
        r = mkt[mkt.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join(f"{r.loc[b, 'll_gain_vs_market_x1000']:+.2f} ± {r.loc[b, 'se_x1000']:.2f}" for b in B+['2026 wk1-5 (diagnostic)']) + ' |')
    L += ['', '## Flat 1u ROI (goal metric; reported, not used for the verdict)', '',
          '| Model | ' + ' | '.join(B) + ' |', '|---|' + '---:|'*len(B),
          '| production | ' + ' | '.join(f"{100*prod_roi[b]['roi']:+.2f}% ± {100*prod_roi[b]['roi_se']:.2f} ({prod_roi[b]['units']:+.1f}u)" for b in B) + ' |']
    for a in PRIMARY+CONTEXT:
        r = allr[allr.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join(f"{100*r.loc[b, 'roi']:+.2f}% ± {100*r.loc[b, 'roi_se']:.2f}; {r.loc[b, 'units_vs_prod']:+.1f}u vs prod, "
                                          f"{int(r.loc[b, 'side_flips'])} flips" for b in B) + ' |')
    r0 = allr[allr.arm == PRIMARY[0]].set_index('basis')
    L += ['', 'Same-row market favorite and market-correct null: ' + '; '.join(
        f"{b} favorite {r0.loc[b, 'fav_units']:+.1f}u, null {100*r0.loc[b, 'null']:+.2f}%" for b in B) + '.', '',
          '## By total band (log-loss gain over production x1000; units vs production)', '',
          '| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |', '|---|---|---:|---:|---:|']
    for a in PRIMARY:
        for b in B:
            r = res[(res.arm == a) & (res.basis == b)].set_index('context')
            L.append(f"| {a} | {b} | " + ' | '.join(f"{r.loc[c, 'll_gain_x1000']:+.2f} ({r.loc[c, 'units_vs_prod']:+.1f}u)"
                                                    for c in ('total_low', 'total_mid', 'total_high')) + ' |')
    L += ['', '## What the ratings model learns', '',
          'Mean fitted coefficient per SD of each input over the weekly fits (share of fits with a positive sign):', '',
          '| Input | ' + ' | '.join(B) + ' |', '|---|' + '---:|'*len(B)]
    for n in MODEL_INPUTS:
        L.append(f"| {n} | " + ' | '.join(f"{info['coefficients'][b][n]['mean_beta_per_sd']:+.3f} ({info['coefficients'][b][n]['share_positive']:.0%})" for b in B) + ' |')
    L += ['', 'Correlation of production\'s and kalman_epa\'s departures from the market, game by game: '
          + ', '.join(f'{b} {v:+.2f}' for b, v in info['departure_corr_prod_vs_kalman_epa'].items()) + '.', '',
          '## Limits', '',
          'Exposed history: the bases have been scored in many earlier tests, though no ratings model had been. EPA comes from '
          'nflverse\'s expected-points model, fit on earlier seasons (Test 7 caveat); the success-rate arm has no such issue. A '
          '"better" verdict would justify only a forward shadow test; adoption is a new REVISION and the owner\'s decision. Tables: '
          '`arms.csv`, `vs_market.csv`, `edges.csv.gz`, `predictions.csv.gz`, `tuning_grid.json`.', '',
          'Run: `python research/kalman_ratings.py --build` (network), then `python research/kalman_ratings.py`.']
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--build', nargs='?', const='', default=None, metavar='CACHE_DIR', help='download and freeze team-game observations')
    a = ap.parse_args()
    if a.build is not None: build(a.build or tempfile.mkdtemp(prefix='pbp_'))
    else: run()
