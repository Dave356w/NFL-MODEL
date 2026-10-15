"""Stat-level predictive test of continuity-conditioned OFFSEASON_RETENTION (copy of eval_stat_prediction.py).

EXPLORATORY DEVELOPMENT EVIDENCE ONLY, AND POST HOC: the two arms were added after the earlier team-prior
variants had been scored on the same 2015-2025 seasons. 2026 weeks 1-5 are a current-season diagnostic.
No moneyline outcomes here: does the pregame h8 profile (production league pseudo-game target) predict the
team's realized stat in that game better when the season-boundary retention depends on regime continuity?

Inputs: team_prior/retention_profiles.csv.gz (league, retention_cont_75_25, retention_cont_50_25) and
team_prior/retention_controls_profiles.csv.gz (league, retention_flat_75, retention_flat_25), both built and
validated by agent_scratch/build_retention_variants.py (league rows identical to profiles.csv.gz).

Scoring is unchanged from eval_stat_prediction.py (raw, recal, recal_wk, stack; team-season cluster bootstrap
B=2000 with the same seed; team-cluster sensitivity; practical scale). Changes:
  * comparisons: each arm vs league (primary); each flat control vs league; arm vs its flat control
    (retention_cont_75_25 vs retention_flat_75, retention_cont_50_25 vs retention_flat_25).
    Every variant shares the league target, so peaks are compared with league (not league_level). Raw MSE on
    peaks mixes in a level effect (more retained weight = less shrinkage toward the 0 target); use recal for peaks.
  * extra subsets by boundary continuity: cur_changed (current boundary changed), cur_cont_older_changed
    (current continuous, an older boundary changed), all3_continuous (no boundary changed; cont_50_25 == league).
  * persistence section dropped (variant-independent; see persistence.csv).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from paths import ROOT, WORK, GAMES_CSV  # noqa: E402
OUT = WORK
PROF = OUT/'retention_profiles.csv.gz'
PROF_CTL = OUT/'retention_controls_profiles.csv.gz'
SEED = 20261014
B = 2000
EVAL = list(range(2016, 2026))
TRAIN0 = 2015

MT = ['plays_per_game', 'net_pass_yards_per_pass_play', 'rush_yards_per_attempt', 'first_down_rate',
      'fumbles_lost_per_game', 'interception_pct', 'penalty_yards_per_game']
RATE = [f'{r}__rates_core__{m}' for r in ('for', 'allowed') for m in MT]
PEAKS = ['max_lead', 'max_deficit']
METRICS = RATE+PEAKS+['margin']
ARMS = ['retention_cont_75_25', 'retention_cont_50_25']
CONTROLS = ['retention_flat_75', 'retention_flat_25']
PAIRS = [('retention_cont_75_25', 'retention_flat_75'), ('retention_cont_50_25', 'retention_flat_25')]
MISLABEL = [(2024, 'NYJ', 6), (2024, 'NO', 10), (2024, 'CHI', 14), (2025, 'TEN', 7), (2025, 'NYG', 11)]


def comparisons(metric):
    return [(v, 'league') for v in ARMS+CONTROLS]+PAIRS


def load():
    d = pd.read_csv(PROF, low_memory=False)
    c = pd.read_csv(PROF_CTL, low_memory=False)
    key = ['game_id', 'team']
    l1 = d[d.variant == 'league'].sort_values(key).reset_index(drop=True)
    l2 = c[c.variant == 'league'].sort_values(key).reset_index(drop=True)
    assert l1[key+METRICS].equals(l2[key+METRICS]), 'league rows differ between the two retention files'
    d = pd.concat([d, c[c.variant != 'league']], ignore_index=True)
    base = d[d.variant == 'league'].copy().sort_values(['season', 'week', 'game_id', 'team']).reset_index(drop=True)
    preds = {}
    for v, g in d.groupby('variant'):
        g = base[key].merge(g[key+METRICS], on=key, how='left', validate='one_to_one')
        assert len(g) == len(base) and not g[METRICS].isna().any().any()
        preds[v] = g[METRICS].to_numpy(float)
    for col in ('coach_change', 'qb_change', 'cont_boundary_cur', 'cont_boundary_m1', 'cont_boundary_m2'):
        base[col] = base[col].map({True: True, False: False, 'True': True, 'False': False})
    return base, preds


def recalibrate(f, y, w, season, groups=None, extra=None):
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
    c0 = base.cont_boundary_cur.to_numpy(bool); c1 = base.cont_boundary_m1.to_numpy(bool); c2 = base.cont_boundary_m2.to_numpy(bool)
    assert np.array_equal(c0, ~cc & ~qc)
    ev = np.isin(season, EVAL)
    mislabel = np.zeros(len(base), bool)
    for yr, tm, wk in MISLABEL:
        mislabel |= (season == yr) & (base.team.to_numpy() == tm) & (week >= wk)
    n_mis = int(mislabel.sum())

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
        'cur_changed': ev & ~c0, 'cur_cont_older_changed': ev & c0 & ~(c1 & c2), 'all3_continuous': ev & c0 & c1 & c2,
    }
    diag2026 = season == 2026

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
        mean_den = float(a.sw.sum()/a.n.sum())
        s2_game = float((a.s2unit*(a.n-1)).sum()/(a.n-1).sum())/mean_den
        scale[mt] = {'between_team_var_true': tau2, 'between_team_sd_true': float(np.sqrt(max(tau2, 0))),
                     'between_team_sd_observed': float(np.sqrt(var_obs)), 'mean_sampling_var_season': samp,
                     'game_noise_var_avg_game': s2_game, 'game_noise_sd_avg_game': float(np.sqrt(s2_game)),
                     'games_for_half_reliability': s2_game/tau2 if tau2 > 0 else np.inf}

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
                ms = diag2026
                if mode == 'raw' and ms.any():
                    by_season.append({'metric': mt, 'variant': v, 'reference': ref, 'mode': mode, 'season': 2026,
                                      'n_rows': int(ms.sum()),
                                      'd_mse': (w[ms]*e_v[ms]).sum()/w[ms].sum()-(w[ms]*e_r[ms]).sum()/w[ms].sum(),
                                      'pct': 100*((w[ms]*e_v[ms]).sum()/(w[ms]*e_r[ms]).sum()-1)})

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
        for v in ['league']+ARMS+CONTROLS:
            f = preds[v][:, j]
            beta, lo, hi = cluster_wls(np.column_stack([np.ones(len(f)), f]), y, w, ev)
            coef_rows.append({'metric': mt, 'kind': 'slope', 'variant': v, 'reference': '', 'coef': beta[1], 'lo': lo[1], 'hi': hi[1]})
        for v, ref in comparisons(mt):
            fr = preds[ref][:, j]; f = preds[v][:, j]
            dv = f-fr
            if np.abs(dv[ev]).max() == 0: continue
            beta, lo, hi = cluster_wls(np.column_stack([np.ones(len(f)), fr, dv]), y, w, ev)
            coef_rows.append({'metric': mt, 'kind': 'stack_b2', 'variant': v, 'reference': ref, 'coef': beta[2], 'lo': lo[2], 'hi': hi[2],
                              'b1': beta[1], 'sd_shift': float(np.sqrt(np.average(dv[ev]**2, weights=w[ev])))})
    pd.DataFrame(coef_rows).to_csv(OUT/'retention_stat_pred_coefs.csv', index=False, float_format='%.6g')

    long = pd.DataFrame(rows)
    long.to_csv(OUT/'retention_stat_pred_long.csv', index=False, float_format='%.6g')
    pd.DataFrame(by_season).to_csv(OUT/'retention_stat_pred_by_season.csv', index=False, float_format='%.6g')
    sc = pd.DataFrame(scale).T.rename_axis('metric').reset_index()
    sc.to_csv(OUT/'retention_stat_pred_scale.csv', index=False, float_format='%.6g')
    meta = {'n_eval_rows': int(ev.sum()), 'n_team_seasons': int(len(ev_ts)), 'n_mislabel_rows': n_mis, 'B': B, 'seed': SEED,
            'subset_rows': {k: int(v.sum()) for k, v in subsets.items()}, 'rows_2026_diag': int(diag2026.sum()),
            'post_hoc_note': 'arms added after the 7 earlier team-prior variants were scored on the same seasons'}
    (OUT/'retention_stat_pred_meta.json').write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


if __name__ == '__main__':
    main()
