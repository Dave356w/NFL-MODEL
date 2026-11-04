"""Test 53: price-dependent calibration of the no-vig moneyline; see MARKET_PRICE_CALIBRATION.md.

    python research/market_price_calibration.py

Market only. Reads Test 35's frozen schedule pack; no network access. Never writes data/ or the ledger.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit, ndtri

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'research'))
import devig_methods as dv  # noqa: E402

OUT = ROOT/'research/market_price_calibration_results'
PROTOCOL_COMMIT = 'baa1dbf'
FIRST_SCORED, SELECT, HELD = 2009, (2009, 2016), (2017, 2025)
EDGES = (.5, .6, .7, .8)
LABELS = ('0.50-0.60', '0.60-0.70', '0.70-0.80', '>= 0.80')
RIDGE = 10.
LEVEL = .975
ARMS = ('M0 raw', 'M1 linear', 'M2 price bands', 'M3 isotonic')


def frame():
    g = dv.frame(dv.load_pack())
    g['q'] = g.q_P
    g['f'] = np.maximum(g.q, 1-g.q)
    g['fav_home'] = g.q >= .5
    g['yf'] = np.where(g.fav_home, g.y, 1-g.y)
    g['k'] = np.digitize(g.f, EDGES[1:])
    g['cluster'] = g.season.astype(str)+'_'+g.week.astype(str)
    return g


def to_home(g, pf):
    return np.where(g.fav_home, pf, 1-pf)


# --- arms ----------------------------------------------------------------------------------------

def fit_m1(h):
    x, y = logit(np.clip(h.q, 1e-9, 1-1e-9)).to_numpy(), h.y.to_numpy()
    def nll(t):
        z = t[0]+t[1]*x
        return np.sum(np.logaddexp(0, z)-y*z), np.array([np.sum(expit(z)-y), np.sum((expit(z)-y)*x)])
    r = minimize(nll, [0., 1.], jac=True, method='BFGS')
    return {'a': float(r.x[0]), 'b': float(r.x[1])}


def apply_m1(g, p):
    return expit(p['a']+p['b']*logit(np.clip(g.q, 1e-9, 1-1e-9)))


def fit_m2(h):
    x, y, k = logit(h.f).to_numpy(), h.yf.to_numpy(), h.k.to_numpy()
    def nll(d):
        z = x+d[k]
        gr = np.bincount(k, weights=expit(z)-y, minlength=4)+RIDGE*d
        return np.sum(np.logaddexp(0, z)-y*z)+.5*RIDGE*np.sum(d*d), gr
    r = minimize(nll, np.zeros(4), jac=True, method='BFGS')
    return {'delta': r.x.tolist()}


def apply_m2(g, p):
    return to_home(g, expit(logit(g.f.to_numpy())+np.asarray(p['delta'])[g.k.to_numpy()]))


def pava(x, y):
    """Isotonic increasing fit; returns sorted unique x knots and fitted values."""
    o = np.argsort(x, kind='mergesort'); x, y = x[o], y[o]
    ux, inv = np.unique(x, return_inverse=True)
    s = np.bincount(inv, weights=y); n = np.bincount(inv).astype(float)
    vals, wts, cnt = [], [], []
    for si, ni in zip(s, n):
        vals.append(si/ni); wts.append(ni); cnt.append(1)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            w = wts[-2]+wts[-1]; v = (vals[-2]*wts[-2]+vals[-1]*wts[-1])/w; c = cnt[-2]+cnt[-1]
            vals[-2:] = [v]; wts[-2:] = [w]; cnt[-2:] = [c]
    fitted = np.repeat(vals, cnt)
    return ux, fitted


def fit_m3(h):
    ux, fv = pava(h.f.to_numpy(), h.yf.to_numpy())
    return {'x': ux.tolist(), 'y': fv.tolist()}


def apply_m3(g, p):
    x, y = np.asarray(p['x']), np.asarray(p['y'])
    i = np.clip(np.searchsorted(x, g.f.to_numpy(), side='right')-1, 0, len(x)-1)  # step: last knot at or below f
    return to_home(g, np.clip(y[i], .5, .995))


FITS = {'M1 linear': (fit_m1, apply_m1), 'M2 price bands': (fit_m2, apply_m2), 'M3 isotonic': (fit_m3, apply_m3)}


def forecasts(g):
    out = g.copy(); out['M0 raw'] = out.q; params = {}
    for arm in FITS: out[arm] = np.nan
    for y in range(FIRST_SCORED, int(g.season.max())+1):
        h = g[g.season < y]; k = g.season.eq(y)
        if not h.season.lt(y).all(): raise ValueError('lookahead')
        for arm, (fit, apply) in FITS.items():
            p = fit(h); params[(arm, y)] = p
            out.loc[k, arm] = apply(g[k], p)
    return out[out.season >= FIRST_SCORED].reset_index(drop=True), params


# --- scoring -------------------------------------------------------------------------------------

def gain(d, arm):
    """Log-loss gain of arm over M0 per game (positive = arm better), week-clustered SE."""
    x = dv.log_loss(d['M0 raw'].to_numpy(), d.y.to_numpy())-dv.log_loss(d[arm].to_numpy(), d.y.to_numpy())
    mu = float(x.mean()); r = pd.Series(x-mu).groupby(d.cluster.to_numpy()).sum()
    se = float(np.sqrt((r**2).sum())/len(x)); z = float(ndtri(.5+LEVEL/2))
    return {'n': len(x), 'gain': mu, 'se': se, 'lo': mu-z*se, 'hi': mu+z*se}


def band_table(g, span):
    d = g[g.season.between(*span)]; rows = []
    for k, lab in enumerate(LABELS):
        b = d[d.k == k]; n = len(b); w = b.yf.mean()
        rows.append({'period': f'{span[0]}-{span[1]}', 'band': lab, 'n': n, 'mean_f': float(b.f.mean()),
                     'fav_win': float(w), 'se': float(np.sqrt(w*(1-w)/n)), 'gap': float(w-b.f.mean())})
    return rows


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    g = frame()
    d, params = forecasts(g)
    sel_d, held_d = d[d.season.between(*SELECT)], d[d.season.between(*HELD)]
    sel_ll = {a: float(dv.log_loss(sel_d[a].to_numpy(), sel_d.y.to_numpy()).mean()) for a in ARMS}
    selected = min(ARMS, key=lambda a: (sel_ll[a], a != 'M0 raw'))
    held = {a: gain(held_d, a) for a in ARMS[1:]}
    sel_gain = {a: gain(sel_d, a) for a in ARMS[1:]}
    if selected == 'M0 raw': verdict = 'fail: M0 selected, keep q'
    else:
        r = held[selected]
        verdict = ('pass' if r['lo'] > 0 else 'fail: keep q' if r['hi'] < 0 else 'unresolved, keep q')
    by_band = [{'band': LABELS[k], 'arm': a, **gain(held_d[held_d.k == k], a)} for k in range(4) for a in ARMS[1:]]
    seasons = {int(y): gain(s, selected)['gain'] for y, s in held_d.groupby('season')} if selected != 'M0 raw' else {}
    bands = band_table(g, (2006, 2016))+band_table(g, HELD)
    show = {f'{a} {y}': (params[(a, y)] if a != 'M3 isotonic' else
                         {'knots': len(params[(a, y)]['x']), 'steps': sorted({round(v, 3) for v in params[(a, y)]['y']})})
            for a in FITS for y in (2017, 2025)}
    res = {'protocol': 'research/MARKET_PRICE_CALIBRATION.md', 'protocol_commit': PROTOCOL_COMMIT,
           'n_selection': len(sel_d), 'n_held_out': len(held_d), 'selection_log_loss': sel_ll, 'selected': selected,
           'selection_gain_vs_M0': sel_gain, 'held_out_gain_vs_M0': held, 'verdict': verdict,
           'held_out_selected_gain_by_season': seasons, 'parameters': show}
    (out/'results.json').write_text(json.dumps(res, indent=2))
    pd.DataFrame(bands).to_csv(out/'market_bands.csv', index=False, float_format='%.6g')
    pd.DataFrame(by_band).to_csv(out/'held_out_by_band.csv', index=False, float_format='%.6g')
    d[['game_id', 'season', 'week', 'y', *ARMS]].to_csv(out/'forecasts.csv.gz', index=False, float_format='%.6g')
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/MARKET_PRICE_CALIBRATION.md', ROOT/'research/devig_methods.py', dv.PACK)}, indent=2))
    report(res, bands, by_band, out)
    return res


def report(res, bands, by_band, out):
    f = lambda r: f'{1000*r["gain"]:+.2f} ± {1000*r["se"]:.2f} [{1000*r["lo"]:+.2f}, {1000*r["hi"]:+.2f}]'
    L = ['# Test 53: price-dependent calibration of the no-vig moneyline (market only)', '',
         f'Protocol: [MARKET_PRICE_CALIBRATION.md](../MARKET_PRICE_CALIBRATION.md), committed (`{res["protocol_commit"]}`) '
         'before any calibrated price was scored. Gains are log loss of M0 minus the arm, per game x1000 (positive = arm '
         'better), week-clustered SE, 97.5% interval.', '',
         f'Selection 2009-16 (n {res["n_selection"]}): selected **{res["selected"]}**. '
         f'Held-out 2017-25 (n {res["n_held_out"]}): **{res["verdict"]}**.', '',
         '| Arm | Log loss 2009-16 | Gain 2009-16 | Gain 2017-25 (held out) |', '|---|---:|---:|---:|']
    for a in ARMS:
        g1 = f(res['selection_gain_vs_M0'][a]) if a != 'M0 raw' else '-'
        g2 = f(res['held_out_gain_vs_M0'][a]) if a != 'M0 raw' else '-'
        L.append(f'| {a} | {res["selection_log_loss"][a]:.5f} | {g1} | {g2} |')
    L += ['', '## Market accuracy by favorite price band (descriptive)', '',
          '| Period | Band | n | Mean no-vig favorite WP | Favorite win rate ± SE | Realized − implied |',
          '|---|---|---:|---:|---:|---:|']
    for r in bands:
        L.append(f'| {r["period"]} | {r["band"]} | {r["n"]} | {r["mean_f"]:.3f} | {r["fav_win"]:.3f} ± {r["se"]:.3f} | {r["gap"]:+.3f} |')
    L += ['', '## Held-out gain by band (x1000)', '', '| Band | Arm | n | Gain |', '|---|---|---:|---:|']
    for r in by_band:
        L.append(f'| {r["band"]} | {r["arm"]} | {r["n"]} | {f(r)} |')
    L += ['', '## Fitted parameters', '']
    for k, v in res['parameters'].items():
        L.append(f'- {k}: ' + json.dumps({a: (round(b, 4) if isinstance(b, float) else
                                                [round(c, 4) for c in b] if isinstance(b, list) else b) for a, b in v.items()}))
    if res['held_out_selected_gain_by_season']:
        L += ['', 'Selected arm, held-out gain by season (x1000): ' +
              ', '.join(f'{y} {1000*v:+.2f}' for y, v in res['held_out_selected_gain_by_season'].items())]
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    r = run(); print(json.dumps({k: r[k] for k in ('selected', 'verdict', 'held_out_gain_vs_M0')}, indent=2))
