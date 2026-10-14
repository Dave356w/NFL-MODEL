"""Test 41: fixed iterations of the Test 40 ratings model; see KALMAN_ITERATIONS.md.

    python research/kalman_iterations.py

Reads only committed files; no network access. Never writes data/ or the ledger. Development evidence only.
"""
import hashlib
import json
import sys
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
import kalman_ratings as kr  # noqa: E402

OUT = ROOT/'research/kalman_iterations_results'
PROTOCOL_COMMIT = 'cc9642a'
ARMS = {  # name: (inputs, ridge)
    'kalman_epa': (['site', 'pass_edge', 'rush_edge', 'd__avail__qb_delta'], .1),
    'k2_margin': (['site', 'pass_edge', 'rush_edge', 'd__avail__qb_delta', 'margin_edge'], .1),
    'k3_ats': (['site', 'pass_edge', 'rush_edge', 'd__avail__qb_delta', 'ats_edge'], .1),
    'k4_combined': (['site', 'eff_edge', 'd__avail__qb_delta'], .1),
    'k5_ridge1': (['site', 'pass_edge', 'rush_edge', 'd__avail__qb_delta'], 1.),
    'k6_compact': (['site', 'eff_edge', 'margin_edge', 'ats_edge', 'd__avail__qb_delta'], .1),
}
PRIMARY = ('k2_margin', 'k3_ats', 'k4_combined', 'k5_ridge1', 'k6_compact', 'selected')
LEVEL = 1-.05/len(PRIMARY)
Z = float(norm.ppf(1-(1-LEVEL)/2))
SELECT_FROM = ('production',)+tuple(ARMS)
SELECT_SEASONS = range(2017, 2026)
FIRST_SCORED = 2015


# --- one-state-per-team ratings (margin, margin beyond the spread) ----------------------------------

def games_table():
    """Completed regular-season games with final margin and closing spread, 2013-26, from the frozen packs."""
    a = pd.read_csv(t.OOS_PACK)[['game_id', 'season', 'week', 'home', 'away', 'result', 'spread_line']]
    b = pd.read_csv(t.T36_PACK)[['game_id', 'season', 'week', 'home', 'away', 'result', 'spread_line']]
    both = a.merge(b, on='game_id', suffixes=('', '_b'))
    for c in ('result', 'spread_line'):
        x, y = both[c].to_numpy(float), both[c+'_b'].to_numpy(float)
        if not np.allclose(np.nan_to_num(x, nan=-999), np.nan_to_num(y, nan=-999)): raise ValueError(f'Packs disagree on {c}')
    g = pd.concat([a[a.season <= 2020], b[b.season >= 2021]], ignore_index=True)
    g = g[g.result.notna()].copy()
    for c in ('home', 'away'): g[c] = g[c].replace(m.TEAM_ALIASES)
    return g.sort_values(['season', 'week', 'game_id']).reset_index(drop=True)


def single_obs(g, kind):
    o = g[['game_id', 'season', 'week', 'home', 'away']].copy()
    o['y'] = g.result if kind == 'margin' else g.result-g.spread_line
    return o[np.isfinite(o.y)]


def kalman1(obs, teams, sigma2, q, rho, p0, tune=kr.TUNE_SEASONS):
    """One state per team; observation y = s_H - s_A + home + e. Pregame snapshots (edge = s_H - s_A) and the
    predictive log-likelihood over the tuning seasons. Home effect from strictly earlier games (2013 week 1:
    its own week)."""
    ix = {tm: i for i, tm in enumerate(teams)}; k = len(teams)
    x = np.zeros(k); P = np.eye(k)*p0
    prior_y, snaps, loglik, season = [], [], 0., None
    for (yr, wk), g in obs.groupby(['season', 'week'], sort=True):
        if season is not None:
            if yr != season: x = rho*x; P = rho*rho*P+np.eye(k)*p0*(1-rho*rho)
            else: P = P+np.eye(k)*q
        season = yr
        for r in g.itertuples(index=False):
            snaps.append({'game_id': r.game_id, 'edge': x[ix[r.home]]-x[ix[r.away]]})
        home = float(np.mean(prior_y)) if prior_y else float(g.y.mean())
        for r in g.itertuples(index=False):
            h, a = ix[r.home], ix[r.away]
            y = r.y-home; pred = x[h]-x[a]
            Ph = P[:, h]-P[:, a]; S = Ph[h]-Ph[a]+sigma2
            if yr in tune: loglik += -.5*(np.log(2*np.pi*S)+(y-pred)**2/S)
            K = Ph/S; x = x+K*(y-pred); P = P-np.outer(K, Ph)
        prior_y += list(g.y.to_numpy())
    return pd.DataFrame(snaps), loglik


def team_season_var(obs):
    o = obs[obs.season.isin(kr.TUNE_SEASONS)]
    rows = pd.concat([o[['season', 'home', 'y']].rename(columns={'home': 'team'}),
                      o[['season', 'away', 'y']].rename(columns={'away': 'team'}).assign(y=lambda d: -d.y)])
    return float(rows.groupby(['season', 'team']).y.mean().var(ddof=1))


def rate_single(g, kind, teams):
    obs = single_obs(g, kind)
    tune = obs[obs.season.isin(kr.TUNE_SEASONS)]
    sigma2 = float((tune.y-tune.y.mean()).var(ddof=1)); v0 = team_season_var(obs)
    grid = []
    for qm in kr.Q_GRID:
        for rho in kr.RHO_GRID:
            for pm in kr.P0_GRID:
                grid.append({'q_mult': qm, 'rho': rho, 'p0_mult': pm,
                             'loglik': kalman1(tune, teams, sigma2, qm*1e-3*sigma2, rho, pm*v0)[1]})
    grid = pd.DataFrame(grid); b = grid.loc[grid.loglik.idxmax()]
    snap, _ = kalman1(obs, teams, sigma2, b.q_mult*1e-3*sigma2, b.rho, b.p0_mult*v0)
    return snap.rename(columns={'edge': f'{kind}_edge'}), {'q_mult': float(b.q_mult), 'rho': float(b.rho), 'p0_mult': float(b.p0_mult),
                                                          'sigma2': sigma2, 'team_season_var': v0, 'loglik': float(b.loglik)}


def combined_efficiency(tg):
    """One all-play EPA rating (pass and rush pooled), tuned like Test 40."""
    s = tg.groupby(['game_id', 'season', 'week', 'team', 'opp', 'home'], as_index=False)[['n', 'epa_sum', 'epa_sumsq', 'sr_n', 'sr_sum']].sum()
    s['kind'] = 'all'
    teams = sorted(set(tg.team) | set(tg.opp))
    obs = kr.observations(s, 'epa', 'all'); s2 = kr.play_variance(s, 'epa', 'all'); v0 = kr.season_mean_variance(s, 'epa', 'all')
    grid = []
    for qm in kr.Q_GRID:
        for rho in kr.RHO_GRID:
            for pm in kr.P0_GRID:
                grid.append({'q_mult': qm, 'rho': rho, 'p0_mult': pm,
                             'loglik': kr.kalman(obs[obs.season.isin(kr.TUNE_SEASONS)], teams, s2, qm*1e-3*s2/30, rho, pm*v0)[1]})
    grid = pd.DataFrame(grid); b = grid.loc[grid.loglik.idxmax()]
    snap, _ = kr.kalman(obs, teams, s2, b.q_mult*1e-3*s2/30, b.rho, b.p0_mult*v0)
    snap['eff_edge'] = (snap.off_h+snap.def_a)-(snap.off_a+snap.def_h)
    return snap[['game_id', 'eff_edge']], {'q_mult': float(b.q_mult), 'rho': float(b.rho), 'p0_mult': float(b.p0_mult), 'sigma2': s2,
                                           'season_mean_var': v0, 'loglik': float(b.loglik)}


def all_edges():
    tg = pd.read_csv(kr.TEAM_GAMES)
    edges, tuning = kr.tune_and_rate(tg)
    teams = sorted(set(tg.team) | set(tg.opp))
    g = games_table()
    if (set(g.home) | set(g.away)) - set(teams): raise ValueError('Team codes differ between packs and play-by-play')
    eff, tuning['eff_all'] = combined_efficiency(tg)
    mar, tuning['margin'] = rate_single(g, 'margin', teams)
    ats, tuning['ats'] = rate_single(g, 'ats', teams)
    e = edges['epa'].merge(eff, on='game_id', how='outer').merge(mar, on='game_id', how='outer').merge(ats, on='game_id', how='outer')
    tuning = {k: ({kk: vv for kk, vv in v.items() if kk != 'grid'} if isinstance(v, dict) else v) for k, v in tuning.items()}
    return e, tuning


# --- arms ------------------------------------------------------------------------------------------

def arm_frame(parts, edges, names, ridge):
    rows, coefs = [], []
    for pack, games in parts:
        pk, gm = pack.merge(edges, on='game_id', how='left'), games.merge(edges, on='game_id', how='left')
        for (y, w), g in gm.groupby(['season', 'week']):
            f = kr.fit(pk[m.before(pk, int(y), int(w))], names, int(y), int(w), ridge=ridge)
            rows.append(g.assign(p16=kr.predict(g, f)))
            coefs.append({'season': int(y), 'week': int(w), **dict(zip(names, map(float, f['beta'])))})
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    return t.prepare(d), pd.DataFrame(coefs)


def compare(prod, arm, basis, name):
    old = mu.Z; mu.Z = Z
    try: return mu.compare(prod, arm, basis, name)
    finally: mu.Z = old


def select(frames):
    """Nested selection: for season Y, the arm with the lowest pooled log loss over seasons 2015..Y-1."""
    pool = pd.concat([d[['game_id', 'season', 'y', 'p']].assign(arm=a) for a, d in frames.items()], ignore_index=True)
    pool = pool[pool.y.notna()]
    pool['ll'] = mu.ll(pool.y, pool.p)
    choice = {}
    for y in SELECT_SEASONS:
        h = pool[(pool.season >= FIRST_SCORED) & (pool.season < y)].groupby('arm').ll.mean()
        best = h.min()
        choice[y] = 'production' if np.isclose(h['production'], best, rtol=0, atol=1e-15) else h.idxmin()
    return choice


def verdict(rows, bases):
    a = rows[rows.context == 'all'].set_index('basis').reindex(list(bases))
    if (a.ll_gain_x1000 <= 0).sum()*2 >= len(bases): return 'not better than production'
    if (a.ll_gain_x1000 > 0).all() and (a.lo_x1000 > 0).any(): return 'better than production: worth a forward shadow test'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    edges, tuning = all_edges()
    parts = {**fi.basis_parts(), '2026 wk1-5 (diagnostic)': mu.extra_parts()['2026 wk1-5 (diagnostic)']}
    prod = {b: mu.basis_frame(p, 'production', b) for b, p in parts.items()}
    repro = fi.reproduction({b: prod[b] for b in fi.BASES})
    frames, coefs = {}, {}
    for a, (names, ridge) in ARMS.items():
        for b, p in parts.items():
            frames[(b, a)], c = arm_frame(p, edges, names, ridge)
            coefs[(b, a)] = {n: float(c[n].mean()) for n in names}
    # Nested selection over all scored seasons (bases are concatenated only to look up earlier seasons).
    hist = {a: pd.concat([(prod[b] if a == 'production' else frames[(b, a)]) for b in fi.BASES], ignore_index=True) for a in SELECT_FROM}
    choice = select(hist)
    for b in ('2017-22', '2023-25'):
        sel = []
        for y, a in choice.items():
            src = prod[b] if a == 'production' else frames[(b, a)]
            sel.append(src[src.season == y])
        frames[(b, 'selected')] = pd.concat(sel, ignore_index=True)
    rows, mkt = [], []
    for (b, a), d in frames.items():
        rows += compare(prod[b], d, b, a)
        g, se = kr.vs_market(d); mkt.append({'basis': b, 'arm': a, 'll_gain_vs_market_x1000': g, 'se_x1000': se})
    for b, d in prod.items():
        g, se = kr.vs_market(d); mkt.append({'basis': b, 'arm': 'production', 'll_gain_vs_market_x1000': g, 'se_x1000': se})
    res = pd.DataFrame(rows); res.to_csv(out/'arms.csv', index=False, float_format='%.6g')
    mkt = pd.DataFrame(mkt); mkt.to_csv(out/'vs_market.csv', index=False, float_format='%.6g')
    edges.to_csv(out/'edges.csv.gz', index=False, float_format='%.6g')
    pd.concat([d[['game_id', 'p']].assign(basis=b, arm=a) for (b, a), d in frames.items()] +
              [d[['game_id', 'p']].assign(basis=b, arm='production') for b, d in prod.items()]).to_csv(
        out/'predictions.csv.gz', index=False, float_format='%.6g')
    verdicts = {a: verdict(res[res.arm == a], ('2017-22', '2023-25') if a == 'selected' else fi.BASES) for a in PRIMARY}
    verdicts['kalman_epa (Test 40, reference)'] = verdict(res[res.arm == 'kalman_epa'], fi.BASES)
    prod_roi = {b: m.roi_summary(m.flat_bets(d[d.bet].assign(model_wp=d.p[d.bet]))) for b, d in prod.items()}
    info = {'protocol': 'research/KALMAN_ITERATIONS.md', 'protocol_commit': PROTOCOL_COMMIT, 'level': LEVEL,
            'reproduction_max_error': repro, 'tuning': tuning, 'verdicts': verdicts, 'selected_by_season': {str(k): v for k, v in choice.items()},
            'coefficients_mean_per_sd': {f'{b}|{a}': v for (b, a), v in coefs.items()},
            'binary_games': {b: int(d.y.notna().sum()) for b, d in prod.items()},
            'production_roi': {b: {k: float(v) if isinstance(v, (int, float, np.integer, np.floating)) else v for k, v in s.items()}
                               for b, s in prod_roi.items()}}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=True))
    prov = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/'research/KALMAN_ITERATIONS.md', ROOT/'research/kalman_ratings.py',
                                                       ROOT/'nfl_model.py', kr.TEAM_GAMES, t.OOS_PACK, t.T36_PACK, t.OOS_PRED, t.HELDOUT,
                                                       t.RETRO, t.TOTALS)}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2))
    write_report(info, res, mkt, prod_roi, out)
    return info, res, mkt


def write_report(info, res, mkt, prod_roi, out):
    B = list(fi.BASES); D = '2026 wk1-5 (diagnostic)'; allr = res[res.context == 'all']
    names = ('kalman_epa',)+PRIMARY
    L = ['# Test 41: iterations of the Test 40 ratings model', '',
         f"Protocol: [KALMAN_ITERATIONS.md](../KALMAN_ITERATIONS.md), pushed (`{PROTOCOL_COMMIT}`) before any iteration was built or "
         'scored. Production v1.18 and the ledger are unchanged. Development evidence only.', '',
         'Production reproduces its published forecasts: ' + ', '.join(f'{k} {v:.1e}' for k, v in info['reproduction_max_error'].items()) + '.', '',
         '**Tuning (2013-14 only):** ' + '; '.join(f"{k}: q x{v['q_mult']:g}, rho {v['rho']:g}, P0 x{v['p0_mult']:g}"
                                                 for k, v in info['tuning'].items() if isinstance(v, dict) and 'q_mult' in v)
         + '; pass/rush EPA and success-rate settings as in Test 40.', '',
         '## Verdicts (log-loss gain over production decides)', '']
    for a, v in info['verdicts'].items(): L.append(f"- **{a}**: {v}")
    L += ['', f"Nested selection chose, by season: " + ', '.join(f'{y} {a}' for y, a in info['selected_by_season'].items()) + '.', '',
          f"Rule: better if the gain is positive on every basis scored and its {100*LEVEL:.2f}% interval excludes zero on at least one; "
          'not better if <= 0 on at least half; otherwise unresolved.', '',
          '## Log-loss gain over production (x1000 per game; [99.17% interval])', '',
          '| Arm | ' + ' | '.join(B) + ' | 2026 wk1-5 (diag.) |', '|---|' + '---:|'*(len(B)+1)]
    for a in names:
        r = allr[allr.arm == a].set_index('basis')
        cells = [f"{r.loc[b, 'll_gain_x1000']:+.2f} [{r.loc[b, 'lo_x1000']:+.2f}, {r.loc[b, 'hi_x1000']:+.2f}]" if b in r.index else '-' for b in B]
        L.append(f"| {a} | " + ' | '.join(cells) + f" | {r.loc[D, 'll_gain_x1000']:+.2f} |" if D in r.index else f"| {a} | " + ' | '.join(cells) + ' | - |')
    L += ['', '## Log-loss gain over the market (x1000 per game ± SE)', '', '| Model | ' + ' | '.join(B) + ' | 2026 wk1-5 |', '|---|' + '---:|'*(len(B)+1)]
    for a in ('production',)+names:
        r = mkt[mkt.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join((f"{r.loc[b, 'll_gain_vs_market_x1000']:+.2f} ± {r.loc[b, 'se_x1000']:.2f}" if b in r.index else '-') for b in B+[D]) + ' |')
    L += ['', '## Flat 1u ROI (goal metric; reported, not used for the verdict)', '',
          '| Model | ' + ' | '.join(B) + ' |', '|---|' + '---:|'*len(B),
          '| production | ' + ' | '.join(f"{100*prod_roi[b]['roi']:+.2f}% ± {100*prod_roi[b]['roi_se']:.2f} ({prod_roi[b]['units']:+.1f}u)" for b in B) + ' |']
    for a in names:
        r = allr[allr.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join((f"{100*r.loc[b, 'roi']:+.2f}% ± {100*r.loc[b, 'roi_se']:.2f}; {r.loc[b, 'units_vs_prod']:+.1f}u vs prod, "
                                           f"{int(r.loc[b, 'side_flips'])} flips") if b in r.index else '-' for b in B) + ' |')
    r0 = allr[allr.arm == 'kalman_epa'].set_index('basis')
    L += ['', 'Same-row market favorite and market-correct null: ' + '; '.join(
        f"{b} favorite {r0.loc[b, 'fav_units']:+.1f}u, null {100*r0.loc[b, 'null']:+.2f}%" for b in B) + '.', '',
          '## By total band (log-loss gain over production x1000; units vs production)', '',
          '| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |', '|---|---|---:|---:|---:|']
    for a in PRIMARY:
        for b in B:
            r = res[(res.arm == a) & (res.basis == b)].set_index('context')
            if not len(r): continue
            L.append(f"| {a} | {b} | " + ' | '.join(f"{r.loc[c, 'll_gain_x1000']:+.2f} ({r.loc[c, 'units_vs_prod']:+.1f}u)"
                                                    for c in ('total_low', 'total_mid', 'total_high')) + ' |')
    L += ['', '## Mean fitted coefficient per SD (weekly fits)', '', '| Arm | Basis | Coefficients |', '|---|---|---|']
    for key, v in info['coefficients_mean_per_sd'].items():
        b, a = key.split('|')
        if b in B: L.append(f"| {a} | {b} | " + ', '.join(f"{n.replace('d__avail__', '')} {x:+.3f}" for n, x in v.items()) + ' |')
    L += ['', '## Limits', '',
          'Exposed history; six arms and a selection arm on the same bases (Bonferroni over 6). The ATS rating uses closing spreads of past '
          'games only. EPA comes from nflverse\'s expected-points model (Test 7 caveat). A "better" verdict would justify only a forward '
          'shadow test. Tables: `arms.csv`, `vs_market.csv`, `edges.csv.gz`, `predictions.csv.gz`.', '',
          'Run: `python research/kalman_iterations.py`.']
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    run()
