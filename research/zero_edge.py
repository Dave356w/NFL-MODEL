"""Test 56: favorite, underdog or skip on zero-edge ATS games; see ZERO_EDGE.md.

    python research/zero_edge.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import fixed_bands as fb  # noqa: E402
import slim_model as sm  # noqa: E402
import smooth_map as smap  # noqa: E402

OUT = ROOT/'research/zero_edge_results'
PROTOCOL_COMMIT = '0f1d9d2'
K = 2
Z_BAR = float(norm.ppf(1-.05/K/2))  # 2.24
POLICIES = ('F favorite', 'D underdog', 'S skip')


def games():
    fr, repro, prod = smap.frames()
    out = {}
    for b, h in fr.items():
        smap.map_all(h, b)
        repro[f'map vs fixed_bands {b}'] = smap.check_m0(h, b, prod)
        s = h[h.season.between(*smap.BASES[b]['span']) & np.isfinite(h.spread_line) & np.isfinite(h.result)
              & np.isfinite(h['M0 production'])].reset_index(drop=True)
        out[b] = s
    return out, repro


def sides(s):
    line = s.spread_line.to_numpy(float); mapped = s['M0 production'].to_numpy(float)
    base = fb.pick(mapped, line)  # production: zero edge -> favorite, pick'em -> skip
    zero = (np.abs(mapped-line) <= fb.EPS) & (line != 0)
    fav = np.sign(line)
    return {'F favorite': base, 'D underdog': np.where(zero, -fav, base), 'S skip': np.where(zero, 0., base)}, zero


def season_rows(b, period, s):
    line = s.spread_line.to_numpy(float); margin = (s.result-s.spread_line).to_numpy(float)
    sd, zero = sides(s); rets = {}; rows = []
    for p in POLICIES:
        rec, rets[p] = sm.ats_record(sd[p], margin)
        zrec, _ = sm.ats_record(sd[p][zero], margin[zero]) if p != 'S skip' else ({}, None)
        rows.append({'basis': b, 'period': period, 'policy': p, **rec,
                     **({f'zero_{k}': v for k, v in zrec.items()} if zrec else {})})
    for name, side in (('always favorite', np.sign(line)), ('always home', np.ones(len(s)))):
        rec, _ = sm.ats_record(side, margin); rows.append({'basis': b, 'period': period, 'policy': name, **rec})
    base_bets = int((sd['F favorite'] != 0).sum())
    contrast = {'basis': b, 'period': period, 'games': len(s), 'zero_edge': int(zero.sum()),
                'zero_share_of_bets': float(zero.sum()/base_bets) if base_bets else np.nan}
    for p in ('D underdog', 'S skip'):
        diff = (rets[p]-rets['F favorite'])[zero]
        se = float(diff.std(ddof=1)*np.sqrt(len(diff))) if len(diff) > 1 else np.nan
        contrast[f'{p} - F'] = float(diff.sum()); contrast[f'{p} - F se'] = se
        contrast[f'{p} - F z'] = float(diff.sum()/se) if se and se > 0 else np.nan
    return rows, contrast


def breakdown(b, s):
    sd, zero = sides(s); z = s[zero].copy()
    margin = (z.result-z.spread_line).to_numpy(float)
    z['fav_ret'] = sm.ats_record(np.sign(z.spread_line.to_numpy(float)), margin)[1]
    z['line_group'] = np.select([z.spread_line.abs() == 3, z.spread_line.abs() == 7], ['3', '7'], 'other')
    z['band'] = np.array(smap.LABELS)[np.digitize(z.model_spread.abs(), smap.CUTS)]
    rows = []
    for col in ('line_group', 'band'):
        for k, g in z.groupby(col):
            r = g.fav_ret.to_numpy()
            rows.append({'basis': b, 'by': col, 'group': k, 'n': len(g), 'fav_W': int((r > 0).sum()),
                         'fav_L': int((r < 0).sum()), 'fav_P': int((r == 0).sum()), 'fav_units': float(r.sum())})
    return rows


def verdict(c, p):
    a = c[(c.basis == '2016-22') & (c.period == '2016-2022')].iloc[0]
    q = c[(c.basis == '2023-26') & (c.period == '2023-2026')].iloc[0]
    za, zq = a[f'{p} - F z'], q[f'{p} - F z']
    if za <= -Z_BAR or zq <= -Z_BAR: return 'worse than F'
    if (za >= Z_BAR and q[f'{p} - F'] > 0) or (zq >= Z_BAR and a[f'{p} - F'] > 0): return 'favored over F'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    fr, repro = games()
    rows, contrasts, bd = [], [], []
    for b, s in fr.items():
        span = smap.BASES[b]['span']
        r, c = season_rows(b, f'{span[0]}-{span[1]}', s); rows += r; contrasts.append(c)
        for y, g in s.groupby('season'):
            r, c = season_rows(b, str(int(y)), g.reset_index(drop=True)); rows += r; contrasts.append(c)
        bd += breakdown(b, s)
    rows, contrasts, bd = pd.DataFrame(rows), pd.DataFrame(contrasts), pd.DataFrame(bd)
    verdicts = {p: verdict(contrasts, p) for p in ('D underdog', 'S skip')}
    res = {'protocol': 'research/ZERO_EDGE.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'z_bar': Z_BAR, 'verdicts': verdicts}
    rows.to_csv(out/'records.csv', index=False, float_format='%.6g')
    contrasts.to_csv(out/'contrasts.csv', index=False, float_format='%.6g')
    bd.to_csv(out/'breakdown.csv', index=False, float_format='%.6g')
    (out/'results.json').write_text(json.dumps(res, indent=2, default=float))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/ZERO_EDGE.md', ROOT/'research/smooth_map.py', ROOT/'nfl_model.py',
        ROOT/'fixed_bands.py', smap.LEDGER)}, indent=2))
    report(res, rows, contrasts, bd, out)
    return res


def report(res, rows, contrasts, bd, out):
    L = ['# Test 56: favorite, underdog or skip on zero-edge ATS games', '',
         f'Protocol: [ZERO_EDGE.md](../ZERO_EDGE.md), committed (`{res["protocol_commit"]}`) before the policies were scored. '
         'Both bases are exposed; descriptive only. Flat 1u at -110; break-even 52.4%; pushes in the ROI denominator.', '',
         'Reproduction: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.', '',
         f'Verdicts (bar |z| >= {res["z_bar"]:.2f}): ' + ', '.join(f'{k}: {v}' for k, v in res['verdicts'].items()) + '.', '',
         '## Zero-edge games and contrasts against production (F)', '',
         '| Basis | Period | Games | Zero-edge | Share of bets | D − F | S − F |', '|---|---|---:|---:|---:|---:|---:|']
    for _, c in contrasts.iterrows():
        L.append(f'| {c.basis} | {c.period} | {c.games} | {c.zero_edge} | {100*c.zero_share_of_bets:.1f}% | '
                 f'{c["D underdog - F"]:+.1f} ± {c["D underdog - F se"]:.1f} | {c["S skip - F"]:+.1f} ± {c["S skip - F se"]:.1f} |')
    L += ['', '## Records', '', '| Basis | Period | Policy | Whole strategy W-L-P | Bets | Units | ROI ± SE | Cover | '
          'Zero-edge games W-L-P | Zero-edge units |', '|---|---|---|---|---:|---:|---:|---:|---|---:|']
    for _, r in rows.iterrows():
        zz = '' if pd.isna(r.get('zero_W')) else f'{int(r.zero_W)}-{int(r.zero_L)}-{int(r.zero_P)}'
        zu = '' if pd.isna(r.get('zero_units')) else f'{r.zero_units:+.1f}'
        L.append(f'| {r.basis} | {r.period} | {r.policy} | {r.W}-{r.L}-{r.P} | {r.bets} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {100*r.cover:.1f}% | {zz} | {zu} |')
    L += ['', '## Zero-edge favorite bets by line and band', '', '| Basis | By | Group | n | Favorite W-L-P | Units |',
          '|---|---|---|---:|---|---:|']
    for _, r in bd.iterrows():
        L.append(f'| {r.basis} | {r.by} | {r.group} | {r.n} | {r.fav_W}-{r.fav_L}-{r.fav_P} | {r.fav_units:+.1f} |')
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, default=float))
