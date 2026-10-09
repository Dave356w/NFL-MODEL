"""Paired evaluation of the walk-forward variants on identical held-out games; writes REPORT tables.

    python research/av/evaluate.py          # reads output/heldout_predictions.csv, writes output/results.md

Every variant is scored on the same held-out games (2023-2025). Goal metric first: flat 1u moneyline
ROI on the model's side (graded at the nflverse schedule moneyline, which has no quote timestamp and is
NOT a pregame snapshot), with the market-correct null and the same-row market favorite. Then log loss,
Brier, calibration (intercept and slope of y on logit p), margin MAE/RMSE and the side of the market
spread. Paired differences against A (v1.15) carry week-clustered bootstrap intervals (resampling
(season, week) blocks, 2000 draws, seed nfl_model.SEED).

Subgroups were fixed in code before any held-out result was seen; none was chosen after:
  weeks 1-4 / 5-9 / 10-13 / 14-17 / 18; backup-QB games (either team's v1.15 projected starter differs
  from its usual starter); high-absence games (either team has >= 3 projected starters, base share
  >= .5, out at kickoff); roster continuity high/low (mean of both teams' share of last season's snaps
  held by current members, split at the 2021-22 team-week median: no held-out data).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from _common import m  # noqa: E402

OUT = HERE / 'output'
REPS = 2000


def ll_vec(y, p):
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def calibration(y, p):
    """(intercept, slope) of logistic y ~ a + b logit(p). Perfect calibration: (0, 1)."""
    x = logit(np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6))

    def f(t):
        e = t[0] + t[1] * x
        return np.sum(np.logaddexp(0, e) - y * e), np.array([np.sum(expit(e) - y), np.sum((expit(e) - y) * x)])
    r = minimize(f, np.array([0., 1.]), jac=True, method='BFGS')
    return float(r.x[0]), float(r.x[1])


def bets(d, col):
    x = d.assign(model_wp=d[col].to_numpy(), market_ml_wp=m.market_ml_wp(d))
    return m.flat_bets(x, 'model_wp'), m.flat_bets(x, 'market_ml_wp')


def ats(d, mu):
    """Side of the market spread the model margin takes: 1 win, 0 loss, NaN push/no edge."""
    edge = np.asarray(mu, float) - d.spread_line.to_numpy(float)
    cover = d.result.to_numpy(float) - d.spread_line.to_numpy(float)
    out = np.where((edge == 0) | (cover == 0) | ~np.isfinite(edge), np.nan, (np.sign(edge) == np.sign(cover)).astype(float))
    return out


def per_game(d, name):
    y = d['home won'].to_numpy(float)
    p = d[f'wp__{name}'].to_numpy(float)
    mb, kb = bets(d, f'wp__{name}')
    keep = (mb.units.notna() & kb.units.notna()).to_numpy()
    return {'ll': ll_vec(y, p), 'brier': (p - y) ** 2, 'units': np.where(keep, mb.units, np.nan),
            'fav_units': np.where(keep, kb.units, np.nan), 'null': np.where(keep, mb.null_ev, np.nan),
            'disagree': ((mb.side != kb.side).to_numpy() & keep), 'abs_err': np.abs(d[f'mu__{name}'] - d.result).to_numpy(),
            'sq_err': ((d[f'mu__{name}'] - d.result) ** 2).to_numpy(), 'ats': ats(d, d[f'mu__{name}'])}


def summary(d, g, name):
    y = d['home won'].to_numpy(float); u = g['units'][np.isfinite(g['units'])]
    a, b = calibration(y, d[f'wp__{name}'].to_numpy(float))
    dis = g['disagree']; du = g['units'][dis]; dk = g['fav_units'][dis]
    at = g['ats'][np.isfinite(g['ats'])]
    return {'variant': name, 'games': len(d), 'bets': len(u), 'units': u.sum(), 'roi': u.mean(),
            'roi_se': u.std(ddof=1) / np.sqrt(len(u)), 'fav_roi': np.nanmean(g['fav_units']), 'null': np.nanmean(g['null']),
            'll': g['ll'].mean(), 'brier': g['brier'].mean(), 'cal_a': a, 'cal_b': b,
            'mae': np.nanmean(g['abs_err']), 'rmse': np.sqrt(np.nanmean(g['sq_err'])),
            'ats_n': len(at), 'ats': at.mean() if len(at) else np.nan,
            'dis_n': int(dis.sum()), 'dis_units': du.sum(), 'dis_roi': du.mean() if len(du) else np.nan,
            'dis_fav_units': dk.sum()}


def cluster_boot(diff, clusters, seed=None):
    """Mean of `diff` (NaN dropped) and a 95% interval resampling whole clusters."""
    ok = np.isfinite(diff); diff, clusters = diff[ok], np.asarray(clusters)[ok]
    if not len(diff): return np.nan, np.nan, np.nan, np.nan
    keys, inv = np.unique(clusters, return_inverse=True)
    s = np.bincount(inv, weights=diff); n = np.bincount(inv).astype(float)
    rng = np.random.default_rng(m.SEED if seed is None else seed)
    draws = rng.integers(0, len(keys), size=(REPS, len(keys)))
    means = s[draws].sum(1) / n[draws].sum(1)
    return float(diff.mean()), float(means.std(ddof=1)), float(np.quantile(means, .025)), float(np.quantile(means, .975))


def paired(ga, gb, clusters, mask=None):
    """b minus a (positive = b better): ROI points, log-loss gain, Brier gain, each with cluster SE/CI."""
    k = np.ones(len(ga['ll']), bool) if mask is None else mask
    out = {}
    for key, sign in (('units', 1), ('ll', -1), ('brier', -1)):
        out[key] = cluster_boot(sign * (gb[key][k] - ga[key][k]), clusters[k])
    out['n'] = int(k.sum())
    return out


def subgroups(d, cont_threshold):
    wk = d.week.to_numpy()
    backup = ((d.home_qb_expected != d.home_qb_usual) | (d.away_qb_expected != d.away_qb_usual)).to_numpy()
    high_abs = (np.fmax(d.home_starters_out, d.away_starters_out) >= 3).to_numpy()
    cont = ((d.home_continuity + d.away_continuity) / 2).to_numpy()
    g = {f'weeks {lo}-{hi}' if lo != hi else f'week {lo}': (wk >= lo) & (wk <= hi)
         for lo, hi in ((1, 4), (5, 9), (10, 13), (14, 17), (18, 18))}
    g['backup-QB games'] = backup; g['starter-QB games'] = ~backup
    g['high absence (>=3 starters out)'] = high_abs; g['lower absence'] = ~high_abs
    g['high continuity'] = cont >= cont_threshold; g['low continuity'] = cont < cont_threshold
    return g


def fmt_pts(t):
    return f'{100 * t[0]:+.2f} ± {100 * t[1]:.2f} [{100 * t[2]:+.1f}, {100 * t[3]:+.1f}]'


def fmt_ll(t):
    return f'{t[0]:+.4f} ± {t[1]:.4f} [{t[2]:+.4f}, {t[3]:+.4f}]'


def main(variants=None):
    d = pd.read_csv(OUT / 'heldout_predictions.csv')
    sel = json.loads((OUT / 'selection.json').read_text())
    cc = json.loads((OUT / 'control_check.json').read_text())
    from walkforward import PRIMARY, VARIANTS
    names = list(variants or VARIANTS)
    av = pd.read_csv(OUT / 'av_team_week_features.csv.gz')
    thr = float(av[av.season.isin([2021, 2022])].continuity.median())
    clusters = (d.season * 100 + d.week).to_numpy()
    G = {n: per_game(d, n) for n in names}
    S = pd.DataFrame([summary(d, G[n], n) for n in names])
    mk = d.spread_line.to_numpy(float); res = d.result.to_numpy(float)
    L = []
    w = L.append
    w(f"Control check (v1.15 vs research Test 29): {'REPRODUCED' if cc['reproduced'] else 'NOT REPRODUCED'} "
      f"(bets {cc['bets']}, units {cc['units']:+.2f}, log loss {cc['ll']:.4f}; picks {sorted(set(cc['picks'].values()))})\n")
    if not cc['reproduced']:
        w('**The control did not reproduce: paired comparisons below are NOT accepted.**\n')
    w(f"Held-out {d.season.min()}–{d.season.max()}: {len(d)} games; same-row market favorite ROI "
      f"{100 * S.fav_roi.iloc[0]:+.1f}%; market-correct null {100 * S.null.iloc[0]:+.1f}%. Market spread "
      f"(nflverse close, no timestamp): margin MAE {np.mean(np.abs(mk - res)):.2f}, RMSE {np.sqrt(np.mean((mk - res) ** 2)):.2f}.\n")
    w('### Goal metric and scores (same games)\n')
    w('| Variant | Bets | Units | ROI ± SE | Log loss | Brier | Cal. intercept | Cal. slope | Margin MAE | RMSE | ATS side (n) |')
    w('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for r in S.itertuples():
        w(f'| {r.variant} | {r.bets} | {r.units:+.2f} | {100 * r.roi:+.1f}% ± {100 * r.roi_se:.1f} | {r.ll:.4f} | {r.brier:.4f} | '
          f'{r.cal_a:+.3f} | {r.cal_b:.3f} | {r.mae:.2f} | {r.rmse:.2f} | {100 * r.ats:.1f}% ({r.ats_n}) |')
    w('\n### Where the model and the market favorite differ\n')
    w('| Variant | Games | Model units | Model ROI | Favorite units, same games |\n|---|---:|---:|---:|---:|')
    for r in S.itertuples():
        w(f'| {r.variant} | {r.dis_n} | {r.dis_units:+.2f} | {100 * r.dis_roi:+.1f}% | {r.dis_fav_units:+.2f} |')
    w('\n### Paired differences vs A (v1.15), pooled and by season\n')
    w('Positive = the variant is better. Mean ± week-clustered bootstrap SE [95% interval].\n')
    w('| Variant | Season | Games | ROI difference (pts) | Log-loss gain | Brier gain |\n|---|---|---:|---:|---:|---:|')
    for n in names:
        if n == 'A': continue
        for lab, mask in [('pooled', None)] + [(str(y), (d.season == y).to_numpy()) for y in sorted(d.season.unique())]:
            p = paired(G['A'], G[n], clusters, mask)
            w(f"| {n} | {lab} | {p['n']} | {fmt_pts(p['units'])} | {fmt_ll(p['ll'])} | {fmt_ll(p['brier'])} |")
    w('\n### Per-season goal metric\n')
    w('| Variant | ' + ' | '.join(f'{y} ROI ± SE' for y in sorted(d.season.unique())) + ' | ' +
      ' | '.join(f'{y} LL' for y in sorted(d.season.unique())) + ' |')
    w('|---|' + '---:|' * (2 * d.season.nunique()))
    for n in names:
        cells, lls = [], []
        for y in sorted(d.season.unique()):
            k = (d.season == y).to_numpy(); u = G[n]['units'][k]; u = u[np.isfinite(u)]
            cells.append(f'{100 * u.mean():+.1f}% ± {100 * u.std(ddof=1) / np.sqrt(len(u)):.1f}'); lls.append(f"{G[n]['ll'][k].mean():.4f}")
        w(f'| {n} | ' + ' | '.join(cells) + ' | ' + ' | '.join(lls) + ' |')
    sg = subgroups(d, thr)
    w(f'\n### Pre-specified subgroups: primary variants vs A (continuity split at the 2021–22 median, {thr:.3f})\n')
    w('| Subgroup | Games | A ROI | A LL | ' + ' | '.join(f'{n} ΔROI / ΔLL' for n in PRIMARY if n != 'A') + ' |')
    w('|---|---:|---:|---:|' + '---:|' * (len(PRIMARY) - 1))
    for lab, k in sg.items():
        ua = G['A']['units'][k]; ua = ua[np.isfinite(ua)]
        cells = []
        for n in PRIMARY:
            if n == 'A' or n not in G: continue
            p = paired(G['A'], G[n], clusters, k)
            cells.append(f"{100 * p['units'][0]:+.1f} ± {100 * p['units'][1]:.1f} / {p['ll'][0]:+.4f} ± {p['ll'][1]:.4f}")
        w(f"| {lab} | {int(k.sum())} | {100 * ua.mean():+.1f}% | {G['A']['ll'][k].mean():.4f} | " + ' | '.join(cells) + ' |')
    w('\n### Recipes selected (each season on earlier seasons only, minimum walk-forward log loss)\n')
    w('| Variant | ' + ' | '.join(str(y) for y in sorted(d.season.unique())) + ' |\n|---|' + '---|' * d.season.nunique())
    for n in names: w(f'| {n} | ' + ' | '.join(f'`{sel[n][str(y)]}`' for y in sorted(d.season.unique())) + ' |')
    (OUT / 'results.md').write_text('\n'.join(L) + '\n')
    S.to_csv(OUT / 'summary.csv', index=False)
    print('\n'.join(L))


if __name__ == '__main__':
    main()
