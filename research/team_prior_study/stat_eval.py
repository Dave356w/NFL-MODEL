"""Stat-level predictive test of team / continuity / coach / QB shrinkage targets.

EXPLORATORY DEVELOPMENT EVIDENCE ONLY. Seasons 2015-2025 are already-exposed history; 2026 weeks 1-5
are a current-season diagnostic. No moneyline outcomes, no market, no ROI: this asks only whether the
pregame profile (production's h8 decayed box-score profile with 4 pseudo-games at some target) is a
better predictor of the team's realized stat in that game when the pseudo-games sit at a team-keyed
target instead of the league target.

Input: team_prior/profiles.csv.gz (built and validated by another agent; league variant is bit-identical
to nfl_model.metric_profile / lagged_features). Nothing in the repo is read or written.

Scores
  raw    weighted MSE of profile vs realized game value: weight = den__ (pass plays, rush attempts,
         plays, pass attempts) for ratio stats, 1 for per-game stats, peaks and margin.
  recal  same, after a walk-forward linear recalibration y ~ a + b*profile fitted (den-weighted) on
         seasons 2015..s-1 only and applied to season s. Removes level/scale differences (e.g. the
         peaks' 0 target) so the comparison is about how well the profile ranks/separates teams,
         which is closer to how a ridge regressor uses it.
Reference: league for rates and margin; for max_lead/max_deficit the team-type variants are compared
with league_level (same level, league-mean target), and league_level vs league is shown separately.
Uncertainty: team-season cluster bootstrap, 2,000 draws (one shared draw matrix for every comparison),
percentile 95% intervals on the MSE difference and on the % change. Sensitivity: team cluster (32).

Practical scale (pooled and per subset): MSE = noise + signal error, where noise is the within-team-
season game-to-game variance (den-weighted, n/(n-1) corrected) and signal error is the forecast's error
against the team's true season level. Between-team SD = SD of season-demeaned team-season means minus
their sampling variance. Reported: dMSE as a share of the league signal error and of the between-team
variance, and signal RMSE in between-team-SD units.

Persistence: season-level den-weighted means (ratio of sums), season-demeaned, correlated with the same
team's prior season (pairs s-1 -> s, s = 2016..2025), overall and split by season-level coach change
(opening coach != last coach of prior season) and QB change (season primary starter != prior season's).
Split-half (odd/even games) reliability with Spearman-Brown gives a disattenuated persistence.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from paths import ROOT, WORK, GAMES_CSV  # noqa: E402
OUT = WORK
PROF = OUT/'profiles.csv.gz'
SEED = 20261014
B = 2000
EVAL = list(range(2016, 2026))
TRAIN0 = 2015

MT = ['plays_per_game', 'net_pass_yards_per_pass_play', 'rush_yards_per_attempt', 'first_down_rate',
      'fumbles_lost_per_game', 'interception_pct', 'penalty_yards_per_game']
RATE = [f'{r}__rates_core__{m}' for r in ('for', 'allowed') for m in MT]
PEAKS = ['max_lead', 'max_deficit']
METRICS = RATE+PEAKS+['margin']
QB_METRICS = [f'for__rates_core__{m}' for m in ('net_pass_yards_per_pass_play', 'interception_pct', 'first_down_rate')]
TEAM_TYPE = ['team_window', 'team_prior', 'continuity', 'coach']
SHORT = {c: c.replace('__rates_core__', ':') for c in METRICS}
# nflverse lists the season-opening coach for every 2024-25 game; these interim spans are mislabeled
MISLABEL = [(2024, 'NYJ', 6), (2024, 'NO', 10), (2024, 'CHI', 14), (2025, 'TEN', 7), (2025, 'NYG', 11)]


def comparisons(metric):
    out = []
    ref_tt = 'league_level' if metric in PEAKS else 'league'
    for v in TEAM_TYPE:
        out.append((v, ref_tt))
        if metric in PEAKS: out.append((v, 'league'))
    if metric in QB_METRICS: out.append(('qb_offense', 'league'))
    if metric in PEAKS: out.append(('league_level', 'league'))
    out.append(('none', 'league'))
    return out


def load():
    d = pd.read_csv(PROF, low_memory=False)
    base = d[d.variant == 'league'].copy().sort_values(['season', 'week', 'game_id', 'team']).reset_index(drop=True)
    key = ['game_id', 'team']
    preds = {}
    for v, g in d.groupby('variant'):
        g = base[key].merge(g[key+METRICS], on=key, how='left', validate='one_to_one')
        assert len(g) == len(base) and not g[METRICS].isna().any().any()
        preds[v] = g[METRICS].to_numpy(float)
    for c in ('coach_change', 'qb_change'):
        base[c] = base[c].map({True: True, False: False, 'True': True, 'False': False})
    return base, preds


def recalibrate(f, y, w, season, groups=None, extra=None):
    """Walk-forward weighted LS y ~ a + b f [+ c extra]; fit on seasons TRAIN0..s-1, apply to s.
    groups: optional int array; a separate fit per group (e.g. week bucket). NaN outside EVAL/2026."""
    out = np.full(len(f), np.nan)
    if groups is None: groups = np.zeros(len(f), int)
    cols = [np.ones(len(f)), f]+([extra] if extra is not None else [])
    X = np.column_stack(cols)
    for s in EVAL+[2026]:
        for gv in np.unique(groups):
            tr = (season >= TRAIN0) & (season < s) & (groups == gv)
            te = (season == s) & (groups == gv)
            if not te.any(): continue
            sw = np.sqrt(w[tr])
            coef, *_ = np.linalg.lstsq(X[tr]*sw[:, None], y[tr]*sw, rcond=None)
            out[te] = X[te] @ coef
    return out


def main():
    base, preds = load()
    season = base.season.to_numpy(int); week = base.week.to_numpy(int)
    cc = base.coach_change.to_numpy(bool); qc = base.qb_change.to_numpy(bool)
    ev = np.isin(season, EVAL)
    mislabel = np.zeros(len(base), bool)
    for yr, tm, wk in MISLABEL:
        mislabel |= (season == yr) & (base.team.to_numpy() == tm) & (week >= wk)
    n_mis = int(mislabel.sum())

    # clusters over EVAL rows
    ts = (base.team+'_'+base.season.astype(str)).to_numpy()
    cl_ts = pd.factorize(np.where(ev, ts, 'x'))[0]
    tm_codes = pd.factorize(base.team)[0]
    rng = np.random.default_rng(SEED)
    ev_ts = np.unique(cl_ts[ev]); n_ts = cl_ts.max()+1
    C_ts = np.zeros((B, n_ts))
    C_ts[:, ev_ts] = rng.multinomial(len(ev_ts), np.full(len(ev_ts), 1/len(ev_ts)), size=B)
    n_tm = tm_codes.max()+1
    C_tm = rng.multinomial(n_tm, np.full(n_tm, 1/n_tm), size=B).astype(float)

    subsets = {
        'all': ev, 'wk1': ev & (week == 1), 'wk1-4': ev & (week <= 4), 'wk5-9': ev & (week >= 5) & (week <= 9),
        'wk10-18': ev & (week >= 10), 'both_unchanged': ev & ~cc & ~qc, 'coach_changed': ev & cc,
        'qb_changed': ev & qc, 'both_changed': ev & cc & qc, 'all_excl_coach_mislabel': ev & ~mislabel,
        'wk2-18': ev & (week >= 2),
    }
    diag2026 = season == 2026

    # ---------- practical scale: noise and between-team variance per metric
    Y = {mt: base[f'actual__{mt}'].to_numpy(float) for mt in METRICS}
    W = {mt: base[f'den__{mt}'].to_numpy(float) for mt in METRICS}
    noise_row, scale = {}, {}
    for mt in METRICS:
        y, w = Y[mt], W[mt]
        g = pd.DataFrame({'ts': ts, 'season': season, 'y': y, 'w': w, 'wy': w*y})
        agg = g.groupby('ts').agg(sw=('w', 'sum'), swy=('wy', 'sum'), n=('y', 'size'), season=('season', 'first'))
        agg['mean'] = agg.swy/agg.sw
        mu = g.ts.map(agg['mean']).to_numpy(); n = g.ts.map(agg['n']).to_numpy(float)
        ss = w*(y-mu)**2
        noise_row[mt] = ss*n/(n-1)
        agg['s2unit'] = pd.Series(ss, index=g.index).groupby(g.ts).sum()/(agg.n-1)
        agg['sampvar'] = agg.s2unit/agg.sw
        a = agg[agg.season.isin(EVAL)].copy()
        a['dm'] = a['mean']-a.groupby('season')['mean'].transform('mean')
        var_obs = float(a.dm.var(ddof=1)); samp = float(a.sampvar.mean())
        tau2 = var_obs-samp
        # per-game noise in "average game" units: s2unit / mean den per game
        mean_den = float(a.sw.sum()/a.n.sum())
        s2_game = float((a.s2unit*(a.n-1)).sum()/(a.n-1).sum())/mean_den
        scale[mt] = {'between_team_var_true': tau2, 'between_team_sd_true': float(np.sqrt(max(tau2, 0))),
                     'between_team_sd_observed': float(np.sqrt(var_obs)), 'mean_sampling_var_season': samp,
                     'game_noise_var_avg_game': s2_game, 'game_noise_sd_avg_game': float(np.sqrt(s2_game)),
                     'games_for_half_reliability': s2_game/tau2 if tau2 > 0 else np.inf}

    # ---------- scoring
    def boot_score(ev_v, ev_r, w, nz, mask):
        idx = cl_ts[mask]
        Sv = np.bincount(idx, w[mask]*ev_v[mask], minlength=n_ts)
        Sr = np.bincount(idx, w[mask]*ev_r[mask], minlength=n_ts)
        Sw = np.bincount(idx, w[mask], minlength=n_ts)
        Sn = np.bincount(idx, nz[mask], minlength=n_ts)
        mv, mr, sw = Sv.sum(), Sr.sum(), Sw.sum()
        bv, br, bw = C_ts @ Sv, C_ts @ Sr, C_ts @ Sw
        dd = (bv-br)/bw; pc = bv/br-1
        mse_v, mse_r = mv/sw, mr/sw
        sig2 = Sn.sum()/sw
        res = {'n_rows': int(mask.sum()), 'n_team_seasons': int(len(np.unique(idx))),
               'mse_ref': mse_r, 'mse_var': mse_v, 'd_mse': mse_v-mse_r,
               'd_mse_lo': float(np.percentile(dd, 2.5)), 'd_mse_hi': float(np.percentile(dd, 97.5)),
               'pct': 100*(mse_v/mse_r-1), 'pct_lo': 100*float(np.percentile(pc, 2.5)),
               'pct_hi': 100*float(np.percentile(pc, 97.5)), 'p_boot_better': float((dd < 0).mean()),
               'noise_var': sig2, 'signal_err_ref': mse_r-sig2, 'signal_err_var': mse_v-sig2}
        return res, (idx, w[mask]*ev_v[mask], w[mask]*ev_r[mask], w[mask])

    def team_ci(parts):
        idx, a, b, w = parts
        tmi = tm_codes[subsets['all']]
        Sv = np.bincount(tmi, a, minlength=n_tm); Sr = np.bincount(tmi, b, minlength=n_tm); Sw = np.bincount(tmi, w, minlength=n_tm)
        dd = (C_tm @ Sv-C_tm @ Sr)/(C_tm @ Sw)
        return float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))

    rows, by_season = [], []
    recal_cache = {}
    wkb = np.where(week <= 4, 0, np.where(week <= 9, 1, 2))
    for mt in METRICS:
        j = METRICS.index(mt)
        y, w, nz = Y[mt], W[mt], noise_row[mt]
        for mode in ('raw', 'recal', 'recal_wk', 'stack'):
            def pr(v, ref=None):
                f = preds[v][:, j]
                if mode == 'raw': return f
                if mode == 'stack' and ref is not None:
                    # y ~ a + b1 f_ref + b2 (f_v - f_ref): does the variant's shift carry information?
                    k = ('stack', v, ref, mt)
                    if k not in recal_cache:
                        fr = preds[ref][:, j]
                        recal_cache[k] = recalibrate(fr, y, w, season, extra=f-fr)
                    return recal_cache[k]
                mm = 'recal_wk' if mode == 'recal_wk' else 'recal'
                k = (mm, v, mt)
                if k not in recal_cache:
                    recal_cache[k] = recalibrate(f, y, w, season, groups=wkb if mm == 'recal_wk' else None)
                return recal_cache[k]
            for v, ref in comparisons(mt):
                e_v = (y-pr(v, ref))**2; e_r = (y-pr(ref))**2
                for sname, mask in subsets.items():
                    res, parts = boot_score(e_v, e_r, w, nz, mask)
                    seas = []
                    for s in EVAL:
                        ms = mask & (season == s)
                        if ms.sum() == 0: continue
                        dv = (w[ms]*e_v[ms]).sum()/w[ms].sum()-(w[ms]*e_r[ms]).sum()/w[ms].sum()
                        seas.append(dv)
                        if sname == 'all':
                            by_season.append({'metric': mt, 'variant': v, 'reference': ref, 'mode': mode, 'season': s,
                                              'n_rows': int(ms.sum()), 'd_mse': dv,
                                              'pct': 100*((w[ms]*e_v[ms]).sum()/(w[ms]*e_r[ms]).sum()-1)})
                    res['seasons_better'] = int(np.sum(np.array(seas) < 0)); res['seasons'] = len(seas)
                    if sname == 'all':
                        res['d_mse_lo_team'], res['d_mse_hi_team'] = team_ci(parts)
                    sc = scale[mt]
                    tau2 = sc['between_team_var_true']
                    res['d_mse_over_between_var'] = res['d_mse']/tau2
                    res['pct_signal_err'] = 100*res['d_mse']/res['signal_err_ref'] if res['signal_err_ref'] > 0 else np.nan
                    res['signal_rmse_ref_sd'] = np.sqrt(max(res['signal_err_ref'], 0))/np.sqrt(tau2)
                    res['signal_rmse_var_sd'] = np.sqrt(max(res['signal_err_var'], 0))/np.sqrt(tau2)
                    rows.append({'metric': mt, 'variant': v, 'reference': ref, 'mode': mode, 'subset': sname, **res})
                # 2026 diagnostic (no bootstrap)
                ms = diag2026
                if mode == 'raw' and ms.any():
                    by_season.append({'metric': mt, 'variant': v, 'reference': ref, 'mode': mode, 'season': 2026,
                                      'n_rows': int(ms.sum()),
                                      'd_mse': (w[ms]*e_v[ms]).sum()/w[ms].sum()-(w[ms]*e_r[ms]).sum()/w[ms].sum(),
                                      'pct': 100*((w[ms]*e_v[ms]).sum()/(w[ms]*e_r[ms]).sum()-1)})
    # ---------- full-sample (2016-2025) coefficients, descriptive: calibration slope per variant and
    # stacked b2 on (variant - reference), team-season cluster bootstrap via per-cluster cross products
    def cluster_wls(X, y, w, mask):
        idx = cl_ts[mask]; Xm, ym, wm = X[mask], y[mask], w[mask]
        p = X.shape[1]
        XtX = np.zeros((n_ts, p, p)); Xty = np.zeros((n_ts, p))
        for a in range(p):
            Xty[:, a] = np.bincount(idx, wm*Xm[:, a]*ym, minlength=n_ts)
            for b in range(p):
                XtX[:, a, b] = np.bincount(idx, wm*Xm[:, a]*Xm[:, b], minlength=n_ts)
        beta = np.linalg.solve(XtX.sum(0), Xty.sum(0))
        bA = np.einsum('bc,cij->bij', C_ts, XtX); bB = C_ts @ Xty
        bb = np.linalg.solve(bA, bB[..., None])[..., 0]
        return beta, np.percentile(bb, 2.5, axis=0), np.percentile(bb, 97.5, axis=0)
    coef_rows = []
    for mt in METRICS:
        j = METRICS.index(mt); y, w = Y[mt], W[mt]
        for v in ['league', 'league_level', 'team_window', 'team_prior', 'continuity', 'coach', 'qb_offense', 'none']:
            if v == 'qb_offense' and mt not in QB_METRICS: continue
            if v == 'league_level' and mt not in PEAKS: continue
            f = preds[v][:, j]
            beta, lo, hi = cluster_wls(np.column_stack([np.ones(len(f)), f]), y, w, ev)
            coef_rows.append({'metric': mt, 'kind': 'slope', 'variant': v, 'reference': '', 'coef': beta[1], 'lo': lo[1], 'hi': hi[1]})
        for v, ref in comparisons(mt):
            if v == 'league_level': continue
            fr = preds[ref][:, j]; f = preds[v][:, j]
            dv = f-fr
            if np.abs(dv[ev]).max() == 0: continue
            beta, lo, hi = cluster_wls(np.column_stack([np.ones(len(f)), fr, dv]), y, w, ev)
            coef_rows.append({'metric': mt, 'kind': 'stack_b2', 'variant': v, 'reference': ref, 'coef': beta[2], 'lo': lo[2], 'hi': hi[2],
                              'b1': beta[1], 'sd_shift': float(np.sqrt(np.average(dv[ev]**2, weights=w[ev])))})
    pd.DataFrame(coef_rows).to_csv(OUT/'stat_pred_coefs.csv', index=False, float_format='%.6g')

    long = pd.DataFrame(rows)
    long.to_csv(OUT/'stat_pred_long.csv', index=False, float_format='%.6g')
    pd.DataFrame(by_season).to_csv(OUT/'stat_pred_by_season.csv', index=False, float_format='%.6g')
    sc = pd.DataFrame(scale).T.rename_axis('metric').reset_index()
    sc.to_csv(OUT/'stat_pred_scale.csv', index=False, float_format='%.6g')

    # ---------- persistence
    first = base.sort_values(['season', 'week']).groupby(['team', 'season']).first()
    prim = first['prior_season_primary_qb_id']          # primary QB of season-1, keyed (team, season)
    season_coach_change = first['coach_change']
    pers_rows, rel_rows, pairs_all = [], [], []
    for mt in METRICS:
        y, w = Y[mt], W[mt]
        g = pd.DataFrame({'team': base.team, 'season': season, 'week': week, 'wy': w*y, 'w': w})
        g = g[(g.season >= 2015) & (g.season <= 2025)].sort_values(['team', 'season', 'week'])
        g['k'] = g.groupby(['team', 'season']).cumcount()
        tsm = g.groupby(['team', 'season']).agg(swy=('wy', 'sum'), sw=('w', 'sum'))
        tsm['m'] = tsm.swy/tsm.sw
        tsm['dm'] = tsm.m-tsm.groupby(level='season').m.transform('mean')
        # split-half reliability
        h = g.assign(half=g.k % 2).groupby(['team', 'season', 'half']).agg(swy=('wy', 'sum'), sw=('w', 'sum'))
        h['m'] = h.swy/h.sw
        hh = h.m.unstack('half')
        hh = hh[hh.index.get_level_values('season').isin(EVAL)]
        hh = hh.sub(hh.groupby(level='season').transform('mean'))
        r_half = float(np.corrcoef(hh[0], hh[1])[0, 1]); rel = 2*r_half/(1+r_half)
        rel_rows.append({'metric': mt, 'split_half_r': r_half, 'season_reliability_sb': rel})
        cur = tsm.dm.rename('cur').reset_index()
        prev = tsm.dm.rename('prev').reset_index(); prev['season'] += 1
        P = cur.merge(prev, on=['team', 'season'])
        P = P[P.season.isin(EVAL)].copy()
        P['coach_change'] = [bool(season_coach_change.loc[(t, s)]) for t, s in zip(P.team, P.season)]
        P['qb_change'] = [prim.loc[(t, s+1)] != prim.loc[(t, s)] for t, s in zip(P.team, P.season)]
        pairs_all.append(P.assign(metric=mt))
        splits = {'all': np.ones(len(P), bool), 'coach_same': ~P.coach_change.to_numpy(), 'coach_changed': P.coach_change.to_numpy(),
                  'qb_same': ~P.qb_change.to_numpy(), 'qb_changed': P.qb_change.to_numpy(),
                  'both_same': ~P.coach_change.to_numpy() & ~P.qb_change.to_numpy(),
                  'both_changed': P.coach_change.to_numpy() & P.qb_change.to_numpy()}
        for sn, msk in splits.items():
            x = P[msk]
            r = float(np.corrcoef(x.prev, x.cur)[0, 1]); n = len(x)
            z, se = np.arctanh(r), 1/np.sqrt(n-3)
            pers_rows.append({'metric': mt, 'split': sn, 'n_pairs': n, 'r': r, 'r_lo': float(np.tanh(z-1.96*se)),
                              'r_hi': float(np.tanh(z+1.96*se)), 'r_disattenuated': r/rel if rel > 0 else np.nan})
        # difference same - changed (Fisher z)
        for a_, b_ in (('coach_same', 'coach_changed'), ('qb_same', 'qb_changed'), ('both_same', 'both_changed')):
            ra = [p for p in pers_rows if p['metric'] == mt and p['split'] == a_][0]
            rb = [p for p in pers_rows if p['metric'] == mt and p['split'] == b_][0]
            dz = np.arctanh(ra['r'])-np.arctanh(rb['r']); se = np.sqrt(1/(ra['n_pairs']-3)+1/(rb['n_pairs']-3))
            pers_rows.append({'metric': mt, 'split': f'diff_{a_}_minus_{b_[:-8]}changed', 'n_pairs': ra['n_pairs']+rb['n_pairs'],
                              'r': ra['r']-rb['r'], 'r_lo': np.nan, 'r_hi': np.nan, 'r_disattenuated': np.nan,
                              'z_diff': dz/se})
    pers = pd.DataFrame(pers_rows)
    pers.to_csv(OUT/'persistence.csv', index=False, float_format='%.6g')
    reldf = pd.DataFrame(rel_rows); reldf.to_csv(OUT/'persistence_reliability.csv', index=False, float_format='%.6g')
    pa = pd.concat(pairs_all)
    split_counts = pa[pa.metric == METRICS[0]][['coach_change', 'qb_change']].value_counts().to_dict()

    meta = {'n_eval_rows': int(ev.sum()), 'n_team_seasons': int(len(ev_ts)), 'n_mislabel_rows': n_mis, 'B': B, 'seed': SEED,
            'subset_rows': {k: int(v.sum()) for k, v in subsets.items()},
            'persistence_pair_counts_(coach_change,qb_change)': {str(k): int(v) for k, v in split_counts.items()},
            'rows_2026_diag': int(diag2026.sum())}
    (OUT/'stat_pred_meta.json').write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == '__main__':
    main()
