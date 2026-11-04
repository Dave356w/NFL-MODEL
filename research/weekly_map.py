"""Test 59: weekly refits of the median ATS map, and a linear-trend map; see WEEKLY_MAP.md.

    python research/weekly_map.py

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
import feature_importance as fi  # noqa: E402
import slim_model as sm  # noqa: E402
import smooth_map as smap  # noqa: E402

OUT = ROOT/'research/weekly_map_results'
PROTOCOL_COMMIT = 'b0d78ca'
K = 3
Z_BAR = float(norm.ppf(1-.05/K/2))  # 2.39
ARMS = ('A annual', 'W weekly expanding', 'D weekly decayed', 'T linear trend')


def weighted_median(x, w):
    o = np.argsort(x, kind='mergesort'); x, w = np.asarray(x, float)[o], np.asarray(w, float)[o]
    c = np.cumsum(w); half = c[-1]/2; i = int(np.searchsorted(c, half-1e-12*c[-1]))
    if abs(c[i]-half) <= 1e-12*c[-1] and i+1 < len(x): return float((x[i]+x[i+1])/2)
    return float(x[i])


def eligible(h):
    return h[np.isfinite(h.model_spread) & np.isfinite(h.result) & h.model_spread.ne(0)].copy()


def numbers(tr, weights=None):
    """Band numbers from training rows, or None if production's minimums fail."""
    if tr.season.nunique() < 2 or len(tr) < 300: return None
    band = np.digitize(tr.model_spread.abs(), smap.CUTS)
    if np.bincount(band, minlength=4).min() < 30: return None
    s = (np.sign(tr.model_spread)*tr.result).to_numpy(float)
    w = np.ones(len(tr)) if weights is None else weights
    return [weighted_median(s[band == k], w[band == k]) for k in range(4)]


def trend_numbers(tr, year, base):
    if base is None: return None
    out = []
    band = np.digitize(tr.model_spread.abs(), smap.CUTS); s = np.sign(tr.model_spread)*tr.result
    for k in range(4):
        med = s[band == k].groupby(tr.season[band == k]).median()
        if len(med) < 3: return None
        x = med.index.to_numpy(float); slope = np.polyfit(x, med.to_numpy(float), 1)[0]
        out.append(base[k]+slope*(year-x.mean()))
    return out


def build(h, b):
    h = eligible(h); span = smap.BASES[b]['span']; maps = {}
    for y in range(span[0], span[1]+1):
        prior = h[h.season < y]; annual = numbers(prior)
        for w in sorted(h.loc[h.season == y, 'week'].unique()):
            tr = h[m_before(h, y, w)]
            age = ((y-tr.season.to_numpy())*19+(w-tr.week.to_numpy()))/19
            maps[(y, w)] = {'A annual': annual, 'W weekly expanding': numbers(tr),
                            'D weekly decayed': numbers(tr, np.exp2(-age)), 'T linear trend': trend_numbers(prior, y, annual)}
    return maps


def m_before(df, y, w):
    return (df.season < y) | ((df.season == y) & (df.week < w))


def apply_maps(s, maps):
    s = s.copy()
    for arm in ARMS:
        out = np.full(len(s), np.nan)
        for (y, w), g in s.groupby(['season', 'week']):
            mags = maps.get((int(y), int(w)), {}).get(arm)
            if mags is not None: out[g.index] = np.sign(g.model_spread)*np.asarray(mags)[np.digitize(g.model_spread.abs(), smap.CUTS)]
        s[arm] = out
    return s


def checks(maps, h, b, prod):
    span = smap.BASES[b]['span']; err = []
    rng = np.random.default_rng(1)
    for _ in range(200):
        x = rng.integers(-20, 30, rng.integers(1, 40)).astype(float)
        if weighted_median(x, np.ones(len(x))) != np.median(x): raise ValueError('weighted median != np.median')
    for y in range(span[0], span[1]+1):
        wk1 = min(w for (yy, w) in maps if yy == y)
        if maps[(y, wk1)]['W weekly expanding'] != maps[(y, wk1)]['A annual']: raise ValueError(f'W != A in week 1 of {y}')
        rule = fb.fit(h, y)
        if (rule is None) != (maps[(y, wk1)]['A annual'] is None) or (rule and rule['magnitudes'] != maps[(y, wk1)]['A annual']):
            raise ValueError(f'A does not reproduce fixed_bands.fit for {y}')
    return True


def contrasts(b, period, s):
    s = s[np.isfinite(s[list(ARMS)]).all(axis=1) & np.isfinite(s.spread_line) & np.isfinite(s.result)].reset_index(drop=True)
    sgn = np.sign(s.model_spread); sig = (sgn*s.result).to_numpy(float)
    line = s.spread_line.to_numpy(float); margin = (s.result-s.spread_line).to_numpy(float)
    rows, rets, sides = [], {}, {}
    for arm in ARMS:
        num = (sgn*s[arm]).to_numpy(float)
        sides[arm] = fb.pick(s[arm].to_numpy(float), line); rec, rets[arm] = sm.ats_record(sides[arm], margin)
        r = {'basis': b, 'period': period, 'arm': arm, 'n': len(s), 'mae': float(np.mean(np.abs(sig-num))), **rec}
        if arm != 'A annual':
            numA = (sgn*s['A annual']).to_numpy(float)
            mu, se = fi.cmean(np.abs(sig-num)-np.abs(sig-numA), s.season.astype(str)+'_'+s.week.astype(str))
            diff = rets[arm]-rets['A annual']; use = np.isfinite(diff)
            r.update({'mae_diff': mu, 'mae_se': se, 'mae_z': mu/se if se > 0 else np.nan,
                      'units_diff': float(diff[use].sum()), 'units_se': float(diff[use].std(ddof=1)*np.sqrt(use.sum())),
                      'flips': int((sides[arm] != sides['A annual']).sum())})
        rows.append(r)
    for name, side in (('always favorite', np.sign(line)), ('always home', np.ones(len(s)))):
        rec, _ = sm.ats_record(side, margin); rows.append({'basis': b, 'period': period, 'arm': name, 'n': len(s), **rec})
    return rows


def stability(maps, b):
    rows = []
    for arm in ARMS:
        ch = []
        for y in sorted({y for y, _ in maps}):
            seq = [maps[(y, w)][arm] for w in sorted(w for yy, w in maps if yy == y) if maps[(y, w)][arm] is not None]
            if len(seq) > 1: ch.append(np.abs(np.diff(np.asarray(seq), axis=0)).mean(axis=0))
        m = np.mean(ch, axis=0) if ch else [np.nan]*4
        rows.append({'basis': b, 'arm': arm, **{f'weekly_change_{smap.LABELS[k]}': float(m[k]) for k in range(4)}})
    return rows


def verdict(c, arm):
    a = c[(c.basis == '2016-22') & (c.period == '2016-2022') & (c.arm == arm)].iloc[0]
    q = c[(c.basis == '2023-26') & (c.period == '2023-2026') & (c.arm == arm)].iloc[0]
    if a.mae_z >= Z_BAR or q.mae_z >= Z_BAR: return 'worse than A'
    if (a.mae_z <= -Z_BAR and q.mae_diff < 0) or (q.mae_z <= -Z_BAR and a.mae_diff < 0): return 'better than A'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    fr, repro, prod = smap.frames()
    rows, stab, nums = [], [], []
    for b, h in fr.items():
        maps = build(h, b); repro[f'checks {b}'] = checks(maps, h, b, prod)
        span = smap.BASES[b]['span']
        s = apply_maps(h[h.season.between(*span)].reset_index(drop=True), maps)
        rows += contrasts(b, f'{span[0]}-{span[1]}', s)
        for y, g in s.groupby('season'): rows += contrasts(b, str(int(y)), g.reset_index(drop=True))
        stab += stability(maps, b)
        nums += [{'basis': b, 'season': y, 'week': w, 'arm': arm, 'numbers': v[arm]} for (y, w), v in maps.items() for arm in ARMS]
    rows, stab = pd.DataFrame(rows), pd.DataFrame(stab)
    verdicts = {arm: verdict(rows, arm) for arm in ARMS[1:]}
    res = {'protocol': 'research/WEEKLY_MAP.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'z_bar': Z_BAR, 'verdicts': verdicts}
    rows.to_csv(out/'results.csv', index=False, float_format='%.6g')
    stab.to_csv(out/'stability.csv', index=False, float_format='%.6g')
    pd.DataFrame(nums).to_csv(out/'band_numbers.csv', index=False)
    (out/'results.json').write_text(json.dumps(res, indent=2, default=float))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/WEEKLY_MAP.md', ROOT/'research/smooth_map.py', ROOT/'nfl_model.py',
        ROOT/'fixed_bands.py', smap.LEDGER)}, indent=2))
    report(res, rows, stab, out)
    return res


def report(res, rows, stab, out):
    L = ['# Test 59: weekly refits of the median ATS map, and a linear-trend map', '',
         f'Protocol: [WEEKLY_MAP.md](../WEEKLY_MAP.md), committed (`{res["protocol_commit"]}`) before any arm was scored. '
         'Both bases exposed; diagnostic only. Flat 1u at -110; break-even 52.4%.', '',
         'Reproduction and checks: ' + ', '.join(f'{k} {v}' for k, v in res['reproduction_max_error'].items()) + '.', '',
         f'Verdicts (bar |z| >= {res["z_bar"]:.2f}): ' + ', '.join(f'{k}: {v}' for k, v in res['verdicts'].items()) + '.', '',
         '## Accuracy and ATS', '',
         '| Basis | Period | Arm | n | Mean abs error | Error vs A | z | W-L-P | Units | ROI ± SE | Units vs A | Flips |',
         '|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|']
    for _, r in rows.iterrows():
        mae = '' if pd.isna(r.get('mae')) else f'{r.mae:.3f}'
        md = '' if pd.isna(r.get('mae_diff')) else f'{r.mae_diff:+.3f} ± {r.mae_se:.3f}'
        z = '' if pd.isna(r.get('mae_z')) else f'{r.mae_z:+.2f}'
        ud = '' if pd.isna(r.get('units_diff')) else f'{r.units_diff:+.1f} ± {r.units_se:.1f}'
        fl = '' if pd.isna(r.get('flips')) else f'{int(r.flips)}'
        L.append(f'| {r.basis} | {r.period} | {r.arm} | {int(r.n)} | {mae} | {md} | {z} | {r.W}-{r.L}-{r.P} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {ud} | {fl} |')
    L += ['', '## Stability: mean absolute week-to-week change of band numbers within a season', '',
          '| Basis | Arm | <3 | 3-7 | 7-10 | 10+ |', '|---|---|---:|---:|---:|---:|']
    for _, r in stab.iterrows():
        L.append(f'| {r.basis} | {r.arm} | ' + ' | '.join(f'{r[f"weekly_change_{l}"]:.2f}' for l in smap.LABELS) + ' |')
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, default=float))
