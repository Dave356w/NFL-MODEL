"""Test 58: market-centered ATS cover probability at actual spread prices; see SPREAD_PRICE_PROBABILITY.md.

    python research/spread_price_probability.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
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
import fixed_bands as fb  # noqa: E402
import feature_importance as fi  # noqa: E402
import smooth_map as smap  # noqa: E402

OUT = ROOT/'research/spread_price_probability_results'
ODDS = ROOT/'research/spread_price_inputs/spread_odds.csv'
PROTOCOL_COMMIT = 'd91b78a'
K = 2
Z_BAR = float(norm.ppf(1-.05/K/2))  # 2.24
ARMS = {'A raw disagreement': 'model_spread', 'B mapped disagreement': 'mapped'}


def payout(odds):
    o = np.asarray(odds, float)
    return np.where(o > 0, o/100., 100./-o)


def implied(odds):
    o = np.asarray(odds, float)
    return np.where(o < 0, -o/(-o+100.), 100./(o+100.))


def frames():
    fr, repro, prod = smap.frames()
    odds = pd.read_csv(ODDS)
    out = {}
    for b, h in fr.items():
        smap.map_all(h, b)
        repro[f'map vs fixed_bands {b}'] = smap.check_m0(h, b, prod)
        d = h.merge(odds[['game_id', 'spread_line', 'result', 'home_spread_odds', 'away_spread_odds']],
                    on='game_id', suffixes=('', '_odds'), validate='one_to_one')
        bad = (d.spread_line != d.spread_line_odds) | (d.result != d.result_odds)
        if bad.any(): raise ValueError(f'{b}: {int(bad.sum())} rows disagree with the frozen prices')
        a, c = implied(d.home_spread_odds), implied(d.away_spread_odds)
        d['q'] = a/(a+c)
        d['mapped'] = d['M0 production']
        d['margin'] = d.result-d.spread_line
        d['y'] = np.where(d.margin > 0, 1., np.where(d.margin < 0, 0., np.nan))
        d['cluster'] = d.season.astype(int).astype(str)+'_'+d.week.astype(int).astype(str)
        out[b] = d.sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
    return out, repro


def fit_beta(h, col):
    k = np.isfinite(h.y) & np.isfinite(h[col]) & np.isfinite(h.q)
    if h.loc[k, 'season'].nunique() < 2: return None
    z = ((h.loc[k, col]-h.loc[k, 'spread_line'])/10.).to_numpy(); off = logit(h.loc[k, 'q'].to_numpy()); y = h.loc[k, 'y'].to_numpy()
    beta = 0.
    for _ in range(50):
        p = expit(off+beta*z); g = np.sum((y-p)*z); H = np.sum(p*(1-p)*z*z)
        step = g/H; beta += step
        if abs(step) < 1e-12: break
    return float(beta)


def forecasts(d, b):
    span = smap.BASES[b]['span']; betas = {}
    for arm, col in ARMS.items():
        p = np.full(len(d), np.nan)
        for y in range(span[0], span[1]+1):
            beta = fit_beta(d[d.season < y], col); betas[(arm, y)] = beta
            k = d.season.eq(y).to_numpy() & np.isfinite(d[col]).to_numpy()
            if beta is not None:
                p[k] = expit(logit(d.q.to_numpy()[k])+beta*(d[col].to_numpy()[k]-d.spread_line.to_numpy()[k])/10.)
        d[arm] = p
    return betas


def ll_gain(s, arm):
    k = np.isfinite(s.y) & np.isfinite(s[arm])
    x = fi.ll(s.y[k], s.q[k])-fi.ll(s.y[k], s[arm][k])
    mu, se = fi.cmean(x, s.cluster[k])
    return {'n': int(k.sum()), 'gain_x1000': 1000*mu, 'se_x1000': 1000*se, 'z': mu/se if se > 0 else np.nan}


def grade(s, side):
    side = np.asarray(side, float); m = s.margin.to_numpy()
    pay = np.where(side > 0, payout(s.home_spread_odds), payout(s.away_spread_odds))
    qs = np.where(side > 0, s.q, 1-s.q)
    ret = np.where(side == 0, np.nan, np.where(side*m > 0, pay, np.where(side*m < 0, -1., 0.)))
    null = np.where(side == 0, np.nan, qs*pay-(1-qs))
    r = ret[np.isfinite(ret)]; n = len(r); w, l = int((r > 0).sum()), int((r < 0).sum())
    return {'W': w, 'L': l, 'P': n-w-l, 'bets': n, 'units': float(r.sum()), 'roi': float(r.mean()) if n else np.nan,
            'roi_se': float(r.std(ddof=1)/np.sqrt(n)) if n > 1 else np.nan, 'cover': w/(w+l) if w+l else np.nan,
            'null_roi': float(np.nanmean(null)) if n else np.nan}


def ev_side(s, p):
    p = np.asarray(p, float)
    eh = p*payout(s.home_spread_odds)-(1-p); ea = (1-p)*payout(s.away_spread_odds)-p
    return np.where(~np.isfinite(p), 0., np.where((eh > 0) & (eh >= ea), 1., np.where(ea > 0, -1., 0.)))


def season_rows(b, period, s):
    rows = [{'basis': b, 'period': period, 'arm': arm, 'kind': 'log loss', **ll_gain(s, arm)} for arm in ARMS]
    line = s.spread_line.to_numpy(float)
    sides = {arm: ev_side(s, s[arm]) for arm in ARMS}
    sides['production picks'] = np.where(np.isfinite(s.mapped), fb.pick(s.mapped.to_numpy(float), line), 0.)
    sides['always favorite'] = np.sign(line); sides['always home'] = np.ones(len(s))
    for name, side in sides.items():
        rows.append({'basis': b, 'period': period, 'arm': name, 'kind': 'ATS at actual prices', **grade(s, side)})
    return rows


def calibration(d, b):
    s = d[np.isfinite(d.y) & np.isfinite(d['A raw disagreement'])]
    dev = s['A raw disagreement']-s.q
    s = s.assign(decile=pd.qcut(dev, 10, labels=False, duplicates='drop'))
    return [{'basis': b, 'decile': int(k), 'n': len(g), 'mean_p_minus_q': float((g['A raw disagreement']-g.q).mean()),
             'mean_p': float(g['A raw disagreement'].mean()), 'mean_q': float(g.q.mean()), 'realized': float(g.y.mean())}
            for k, g in s.groupby('decile')]


def verdict(rows, betas, arm):
    r = rows[(rows.arm == arm) & (rows.kind == 'log loss')]
    a = r[(r.basis == '2016-22') & (r.period == '2016-2022')].iloc[0]; q = r[(r.basis == '2023-26') & (r.period == '2023-2026')].iloc[0]
    if a.z <= -Z_BAR or q.z <= -Z_BAR: return 'contradicted'
    bs = [v for (k, _), v in betas.items() if k == arm and v is not None]
    if ((a.z >= Z_BAR and q.gain_x1000 > 0) or (q.z >= Z_BAR and a.gain_x1000 > 0)) and all(v > 0 for v in bs): return 'supported'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    fr, repro = frames()
    rows, betas, cal = [], {}, []
    for b, d in fr.items():
        bt = forecasts(d, b); betas.update(bt)
        span = smap.BASES[b]['span']; s = d[d.season.between(*span)].reset_index(drop=True)
        rows += season_rows(b, f'{span[0]}-{span[1]}', s)
        for y, g in s.groupby('season'): rows += season_rows(b, str(int(y)), g.reset_index(drop=True))
        cal += calibration(s, b)
    rows, cal = pd.DataFrame(rows), pd.DataFrame(cal)
    verdicts = {arm: verdict(rows, betas, arm) for arm in ARMS}
    res = {'protocol': 'research/SPREAD_PRICE_PROBABILITY.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'z_bar': Z_BAR, 'verdicts': verdicts, 'betas': {f'{a} {y}': v for (a, y), v in betas.items()}}
    rows.to_csv(out/'results.csv', index=False, float_format='%.6g')
    cal.to_csv(out/'calibration.csv', index=False, float_format='%.6g')
    (out/'results.json').write_text(json.dumps(res, indent=2, default=float))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/SPREAD_PRICE_PROBABILITY.md', ROOT/'research/smooth_map.py', ROOT/'nfl_model.py',
        ROOT/'fixed_bands.py', ODDS, smap.LEDGER)}, indent=2))
    report(res, rows, cal, out)
    return res


def report(res, rows, cal, out):
    L = ['# Test 58: market-centered ATS cover probability at actual spread prices', '',
         f'Protocol: [SPREAD_PRICE_PROBABILITY.md](../SPREAD_PRICE_PROBABILITY.md), committed (`{res["protocol_commit"]}`) before any arm '
         'was scored. Diagnostic only.', '',
         'Reproduction: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.', '',
         f'Verdicts (bar |z| >= {res["z_bar"]:.2f}): ' + ', '.join(f'{k}: {v}' for k, v in res['verdicts'].items()) + '.', '',
         '## Cover log loss gain over the no-vig spread price (x1000, positive = arm better)', '',
         '| Basis | Period | Arm | n | Gain | z |', '|---|---|---|---:|---:|---:|']
    for _, r in rows[rows.kind == 'log loss'].iterrows():
        L.append(f'| {r.basis} | {r.period} | {r.arm} | {int(r.n)} | {r.gain_x1000:+.2f} ± {r.se_x1000:.2f} | {r.z:+.2f} |')
    L += ['', '## Fitted β (log-odds per 10 points of disagreement)', '', '| Arm, season | β |', '|---|---:|']
    for k, v in res['betas'].items():
        L.append(f'| {k} | {"—" if v is None else f"{v:+.3f}"} |')
    L += ['', '## ATS at actual prices', '', '| Basis | Period | Rule | W-L-P | Bets | Units | ROI ± SE | Cover | Market null ROI |',
          '|---|---|---|---|---:|---:|---:|---:|---:|']
    for _, r in rows[rows.kind == 'ATS at actual prices'].iterrows():
        L.append(f'| {r.basis} | {r.period} | {r.arm} | {int(r.W)}-{int(r.L)}-{int(r.P)} | {int(r.bets)} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {100*r.cover:.1f}% | {100*r.null_roi:+.1f}% |')
    L += ['', '## Calibration of arm A by decile of p − q', '', '| Basis | Decile | n | Mean p − q | Mean p | Realized home cover |',
          '|---|---:|---:|---:|---:|---:|']
    for _, r in cal.iterrows():
        L.append(f'| {r.basis} | {r.decile} | {r.n} | {100*r.mean_p_minus_q:+.2f} pts | {r.mean_p:.3f} | {r.realized:.3f} |')
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    print(json.dumps({k: v for k, v in run().items() if k in ('verdicts', 'reproduction_max_error')}, indent=2, default=float))
