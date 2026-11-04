"""Test 54: raw spread inside the 3-7 band, median map elsewhere; see HYBRID_BAND.md.

    python research/hybrid_band.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import fixed_bands as fb  # noqa: E402
import slim_model as sm  # noqa: E402
import market_implied as mi  # noqa: E402

OUT = ROOT/'research/hybrid_band_results'
PROTOCOL_COMMIT = '7b39c4e'
LEDGER = ROOT/'data/latest/fixed_band_ledger.csv'
TEST, DISCOVERY = (2016, 2022), (2023, 2026)
CUTS = [3., 7., 10.]
ARMS = ('M map', 'R raw', 'H hybrid')


def in_band(x):
    return np.digitize(np.abs(np.asarray(x, float)), CUTS) == 1


def predictions(d, mapped):
    x = d.model_spread.to_numpy(float); m = d[mapped].to_numpy(float)
    return {'M map': m, 'R raw': x, 'H hybrid': np.where(in_band(x), x, m)}


def graded(d, mapped):
    d = d[np.isfinite(d.spread_line) & np.isfinite(d.result) & np.isfinite(d[mapped]) & np.isfinite(d.model_spread)]
    return d.reset_index(drop=True)


def summarize(d, mapped, basis, label):
    line = d.spread_line.to_numpy(float); margin = (d.result-d.spread_line).to_numpy(float)
    preds = predictions(d, mapped); band = in_band(d.model_spread)
    out, rets, sides = [], {}, {}
    for arm in ARMS:
        side = fb.pick(preds[arm], line); rec, ret = sm.ats_record(side, margin)
        rets[arm], sides[arm] = ret, side
        rb, _ = sm.ats_record(side[band], margin[band]); ro, _ = sm.ats_record(side[~band], margin[~band])
        out.append({'basis': basis, 'period': label, 'arm': arm, **rec,
                    'band_record': f"{rb['W']}-{rb['L']}-{rb['P']}", 'band_units': rb['units'],
                    'outside_record': f"{ro['W']}-{ro['L']}-{ro['P']}", 'outside_units': ro['units']})
    for name, side in (('always favorite', np.sign(line)), ('always home', np.ones(len(d)))):
        rec, _ = sm.ats_record(side, margin); out.append({'basis': basis, 'period': label, 'arm': name, **rec})
    diff = rets['H hybrid']-rets['M map']
    flips = sides['H hybrid'] != sides['M map']
    zero = band & (np.abs(d[mapped].to_numpy(float)-line) <= fb.EPS)
    contrast = {'basis': basis, 'period': label, 'n': len(d), 'in_band': int(band.sum()), 'flips': int(flips.sum()),
                'h_minus_m': float(diff.sum()), 'se': float(diff.std(ddof=1)*np.sqrt(len(diff))),
                'h_flip_record': f"{int((rets['H hybrid'][flips] > 0).sum())}-{int((rets['H hybrid'][flips] < 0).sum())}-"
                                 f"{int((rets['H hybrid'][flips] == 0).sum())}",
                'zero_edge_in_band_map': int(zero.sum())}
    contrast['z'] = contrast['h_minus_m']/contrast['se'] if contrast['se'] > 0 else np.nan
    return out, contrast


def verdict(c):
    if c['h_minus_m'] > 0 and c['z'] >= 2: return 'supported'
    if c['h_minus_m'] < 0 and c['z'] <= -2: return 'contradicted'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    rep, _ = mi.forecasts(mi.season_parts(mi.scores()))
    repro = mi.reproduction(rep)
    test = graded(rep[rep.season.between(*TEST)], 'mapped_spread')
    prod = pd.read_csv(LEDGER, low_memory=False)
    disc = graded(prod[prod.season.between(*DISCOVERY)], 'fixed_band_spread')
    rows, contrasts = [], []
    for basis, d, col, span in (('test', test, 'mapped_spread', TEST), ('discovery', disc, 'fixed_band_spread', DISCOVERY)):
        r, c = summarize(d, col, basis, f'{span[0]}-{span[1]}'); rows += r; contrasts.append(c)
        for y, s in d.groupby('season'):
            r, c = summarize(s.reset_index(drop=True), col, basis, str(int(y))); rows += r; contrasts.append(c)
    rows, contrasts = pd.DataFrame(rows), pd.DataFrame(contrasts)
    primary = contrasts[(contrasts.basis == 'test') & (contrasts.period == f'{TEST[0]}-{TEST[1]}')].iloc[0].to_dict()
    res = {'protocol': 'research/HYBRID_BAND.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'primary': primary, 'verdict': verdict(primary)}
    rows.to_csv(out/'ats.csv', index=False, float_format='%.6g')
    contrasts.to_csv(out/'hybrid_minus_map.csv', index=False, float_format='%.6g')
    (out/'results.json').write_text(json.dumps(res, indent=2, default=float))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/HYBRID_BAND.md', ROOT/'research/market_implied.py', ROOT/'nfl_model.py',
        ROOT/'fixed_bands.py', LEDGER, mi.SCORES)}, indent=2))
    report(res, rows, contrasts, out)
    return res


def report(res, rows, contrasts, out):
    p = res['primary']
    L = ['# Test 54: raw spread inside the 3-7 band, median map elsewhere', '',
         f'Protocol: [HYBRID_BAND.md](../HYBRID_BAND.md), committed (`{res["protocol_commit"]}`) before the hybrid was scored. '
         'Flat 1u at -110; break-even cover 52.4%; ROI SE has pushes in the denominator. Diagnostic only.', '',
         'Reproduction of v1.19: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.', '',
         f'**Primary (test 2016-22): H - M = {p["h_minus_m"]:+.1f}u ± {p["se"]:.1f} (z {p["z"]:+.2f}, n {p["n"]}, '
         f'{p["flips"]} flips) -> {res["verdict"]}.**', '',
         '## Hybrid minus map', '', '| Basis | Period | Games | In band | Flips | H flip record | H − M units | z | Zero-edge in band (map) |',
         '|---|---|---:|---:|---:|---|---:|---:|---:|']
    for _, c in contrasts.iterrows():
        L.append(f'| {c.basis} | {c.period} | {c.n} | {c.in_band} | {c.flips} | {c.h_flip_record} | '
                 f'{c.h_minus_m:+.1f} ± {c.se:.1f} | {c.z:+.2f} | {c.zero_edge_in_band_map} |')
    L += ['', '## Records', '', '| Basis | Period | Arm | W-L-P | Skips | Units | ROI ± SE | Cover | In band | Outside band |',
          '|---|---|---|---|---:|---:|---:|---:|---|---|']
    for _, r in rows.iterrows():
        ib = '' if pd.isna(r.get('band_record')) else f'{r.band_record} ({r.band_units:+.1f})'
        ob = '' if pd.isna(r.get('outside_record')) else f'{r.outside_record} ({r.outside_units:+.1f})'
        L.append(f'| {r.basis} | {r.period} | {r.arm} | {r.W}-{r.L}-{r.P} | {r.skips} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {100*r.cover:.1f}% | {ib} | {ob} |')
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    r = run(); print(json.dumps({'primary': r['primary'], 'verdict': r['verdict']}, indent=2, default=float))
