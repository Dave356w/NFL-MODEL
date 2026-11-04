"""Test 55: less noisy band numbers for the median ATS map; see SMOOTH_MAP.md.

    python research/smooth_map.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import beta, norm, trim_mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import fixed_bands as fb  # noqa: E402
import slim_model as sm  # noqa: E402
import market_implied as mi  # noqa: E402

OUT = ROOT/'research/smooth_map_results'
PROTOCOL_COMMIT = '42ee991'
LEDGER = ROOT/'data/latest/fixed_band_ledger.csv'
CUTS = [3., 7., 10.]
LABELS = ('<3', '3-7', '7-10', '10+')
ARMS = ('M0 production', 'M1 Harrell-Davis', 'M2 trimmed mean', 'M3 HD off key numbers')
K = 3
Z_BAR = float(norm.ppf(1-.05/K/2))  # 2.39
BOOT, SEED = 1000, 20261104
BASES = {'2016-22': dict(first_history=2014, span=(2016, 2022)), '2023-26': dict(first_history=2021, span=(2023, 2026))}


def harrell_davis(x):
    x = np.sort(np.asarray(x, float)); n = len(x); a = (n+1)/2
    w = np.diff(beta.cdf(np.arange(n+1)/n, a, a))
    return float(np.dot(w, x))


def off_key(v):
    return float(np.floor(v)+.5)  # nearest x.5 to v is floor(v)+0.5


STAT = {'M0 production': lambda s: float(np.median(s)),
        'M1 Harrell-Davis': harrell_davis,
        'M2 trimmed mean': lambda s: float(trim_mean(s, .2)),
        'M3 HD off key numbers': lambda s: off_key(harrell_davis(s))}


def training(h, season):
    d = h[h.season < season]
    d = d[np.isfinite(d.model_spread) & np.isfinite(d.result) & d.model_spread.ne(0)]
    if d.season.nunique() < 2 or len(d) < 300: return None
    band = np.digitize(d.model_spread.abs(), CUTS)
    if np.bincount(band, minlength=4).min() < 30: return None
    return band, (np.sign(d.model_spread)*d.result).to_numpy(float)


def fit(h, season, arm):
    t = training(h, season)
    if t is None: return None
    band, s = t
    return [STAT[arm](s[band == k]) for k in range(4)]


def apply(x, mags):
    x = np.asarray(x, float)
    return np.sign(x)*np.asarray(mags)[np.digitize(np.abs(x), CUTS)]


def frames():
    rep, _ = mi.forecasts(mi.season_parts(mi.scores()))
    repro = mi.reproduction(rep)
    prod = pd.read_csv(LEDGER, low_memory=False)
    cols = ['game_id', 'season', 'week', 'model_spread', 'result', 'spread_line']
    return {'2016-22': rep[rep.season.between(2014, 2022)][cols].reset_index(drop=True),
            '2023-26': prod[prod.season.between(2021, 2026)][cols].reset_index(drop=True)}, repro, prod


def map_all(h, b):
    span = BASES[b]['span']; maps = {}
    for arm in ARMS:
        out = np.full(len(h), np.nan)
        for y in range(span[0], span[1]+1):
            mags = fit(h, y, arm); k = h.season.eq(y).to_numpy()
            if mags is not None: out[k] = apply(h.loc[k, 'model_spread'], mags)
            maps[(arm, y)] = mags
        h[arm] = out
    return maps


def check_m0(h, b, prod):
    """M0 must reproduce fixed_bands.fit (and production's exported spreads on 2023-26)."""
    span = BASES[b]['span']; err = 0.
    for y in range(span[0], span[1]+1):
        rule = fb.fit(h, y)
        mine = fit(h, y, 'M0 production')
        if (rule is None) != (mine is None) or (rule and rule['magnitudes'] != mine):
            raise ValueError(f'M0 does not reproduce fixed_bands.fit for {y}')
    if b == '2023-26':
        j = h.merge(prod[['game_id', 'fixed_band_spread']], on='game_id')
        j = j[j.season >= 2023]
        err = float(np.nanmax(np.abs(j['M0 production']-j.fixed_band_spread)))
        if err > 0: raise ValueError(f'M0 does not reproduce exported fixed_band_spread ({err})')
    return err


def noise(h, b, maps):
    span = BASES[b]['span']; rng = np.random.default_rng(SEED); rows = []
    for arm in ARMS:
        seq = [maps[(arm, y)] for y in range(span[0], span[1]+1) if maps[(arm, y)] is not None]
        chg = np.abs(np.diff(np.asarray(seq), axis=0)).mean(axis=0) if len(seq) > 1 else [np.nan]*4
        sds, mae = [[] for _ in range(4)], [[] for _ in range(4)]
        for y in range(span[0], span[1]+1):
            t = training(h, y)
            if t is None: continue
            band, s = t
            for k in range(4):
                sk = s[band == k]
                sds[k].append(np.std([STAT[arm](rng.choice(sk, len(sk))) for _ in range(BOOT)]))
            nxt = h[h.season.eq(y) & np.isfinite(h.result) & np.isfinite(h.model_spread) & h.model_spread.ne(0)]
            nb = np.digitize(nxt.model_spread.abs(), CUTS); ns = (np.sign(nxt.model_spread)*nxt.result).to_numpy()
            for k in range(4):
                if (nb == k).any(): mae[k].append(np.abs(ns[nb == k]-maps[(arm, y)][k]).tolist())
        for k in range(4):
            rows.append({'basis': b, 'arm': arm, 'band': LABELS[k], 'mean_abs_change': float(chg[k]),
                         'boot_sd': float(np.mean(sds[k])), 'oos_mae': float(np.mean(sum(mae[k], []))),
                         'numbers': [None if maps[(arm, y)] is None else round(maps[(arm, y)][k], 2)
                                     for y in range(span[0], span[1]+1)]})
    return rows


def ats(h, b):
    span = BASES[b]['span']
    d = h[h.season.between(*span) & np.isfinite(h.spread_line) & np.isfinite(h.result)].copy()
    d = d[np.isfinite(d[list(ARMS)]).all(axis=1)].reset_index(drop=True)
    rows, contrasts = [], []
    for period, s in [(f'{span[0]}-{span[1]}', d)]+[(str(int(y)), g.reset_index(drop=True)) for y, g in d.groupby('season')]:
        line = s.spread_line.to_numpy(float); margin = (s.result-s.spread_line).to_numpy(float)
        ret, side = {}, {}
        for arm in ARMS:
            side[arm] = fb.pick(s[arm].to_numpy(float), line); rec, ret[arm] = sm.ats_record(side[arm], margin)
            zero = int((np.abs(s[arm].to_numpy(float)-line) <= fb.EPS).sum())
            rows.append({'basis': b, 'period': period, 'arm': arm, **rec, 'zero_edge': zero})
        for name, sd in (('always favorite', np.sign(line)), ('always home', np.ones(len(s)))):
            rec, _ = sm.ats_record(sd, margin); rows.append({'basis': b, 'period': period, 'arm': name, **rec})
        for arm in ARMS[1:]:
            diff = ret[arm]-ret['M0 production']; f = side[arm] != side['M0 production']
            se = float(diff.std(ddof=1)*np.sqrt(len(diff)))
            contrasts.append({'basis': b, 'period': period, 'arm': arm, 'n': len(s), 'flips': int(f.sum()),
                              'diff': float(diff.sum()), 'se': se, 'z': float(diff.sum()/se) if se > 0 else np.nan})
    return rows, contrasts


def verdict(c, arm):
    p = c[(c.arm == arm) & (c.basis == '2016-22') & (c.period == '2016-2022')].iloc[0]
    q = c[(c.arm == arm) & (c.basis == '2023-26') & (c.period == '2023-2026')].iloc[0]
    if (p.z <= -Z_BAR) or (q.z <= -Z_BAR): return 'worse'
    if p.z >= Z_BAR and q['diff'] > 0: return 'better'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    fr, repro, prod = frames()
    rows, contrasts, nz = [], [], []
    for b, h in fr.items():
        maps = map_all(h, b)
        repro[f'M0 vs fixed_bands {b}'] = check_m0(h, b, prod)
        nz += noise(h, b, maps)
        r, c = ats(h, b); rows += r; contrasts += c
    rows, contrasts, nz = pd.DataFrame(rows), pd.DataFrame(contrasts), pd.DataFrame(nz)
    verdicts = {arm: verdict(contrasts, arm) for arm in ARMS[1:]}
    res = {'protocol': 'research/SMOOTH_MAP.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'z_bar': Z_BAR, 'verdicts': verdicts}
    rows.to_csv(out/'ats.csv', index=False, float_format='%.6g')
    contrasts.to_csv(out/'arm_minus_production.csv', index=False, float_format='%.6g')
    nz.to_csv(out/'noise.csv', index=False, float_format='%.6g')
    (out/'results.json').write_text(json.dumps(res, indent=2, default=float))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/SMOOTH_MAP.md', ROOT/'research/market_implied.py', ROOT/'nfl_model.py',
        ROOT/'fixed_bands.py', LEDGER, mi.SCORES)}, indent=2))
    report(res, rows, contrasts, nz, out)
    return res


def report(res, rows, contrasts, nz, out):
    L = ['# Test 55: less noisy band numbers for the median ATS map', '',
         f'Protocol: [SMOOTH_MAP.md](../SMOOTH_MAP.md), committed (`{res["protocol_commit"]}`) before any arm was scored. '
         'Flat 1u at -110; break-even 52.4%; ROI SE has pushes in the denominator. Diagnostic only; both bases exposed.', '',
         'Reproduction: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.', '',
         f'## Arm minus production (units; bar |z| >= {res["z_bar"]:.2f})', '',
         '| Arm | 2016-22 | 2023-26 | Verdict |', '|---|---:|---:|---|']
    for arm in ARMS[1:]:
        c = contrasts[contrasts.arm == arm]
        cell = lambda b, p: (lambda r: f'{r["diff"]:+.1f} ± {r.se:.1f} (z {r.z:+.2f}, {r.flips} flips)')(
            c[(c.basis == b) & (c.period == p)].iloc[0])
        L.append(f'| {arm} | {cell("2016-22", "2016-2022")} | {cell("2023-26", "2023-2026")} | {res["verdicts"][arm]} |')
    L += ['', '## Noise and accuracy of the band numbers', '',
          '| Basis | Arm | Band | Numbers by season | Mean season-to-season change | Bootstrap SD | Out-of-sample MAE |',
          '|---|---|---|---|---:|---:|---:|']
    for _, r in nz.iterrows():
        L.append(f'| {r.basis} | {r.arm} | {r.band} | {r.numbers} | {r.mean_abs_change:.2f} | {r.boot_sd:.2f} | {r.oos_mae:.3f} |')
    L += ['', '## Records', '', '| Basis | Period | Arm | W-L-P | Skips | Units | ROI ± SE | Cover | Zero-edge |',
          '|---|---|---|---|---:|---:|---:|---:|---:|']
    for _, r in rows.iterrows():
        z = '' if pd.isna(r.get('zero_edge')) else int(r.zero_edge)
        L.append(f'| {r.basis} | {r.period} | {r.arm} | {r.W}-{r.L}-{r.P} | {r.skips} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {100*r.cover:.1f}% | {z} |')
    L += ['', '## Arm minus production by season', '', '| Basis | Period | Arm | Flips | Units diff |', '|---|---|---|---:|---:|']
    for _, c in contrasts.iterrows():
        L.append(f'| {c.basis} | {c.period} | {c.arm} | {c.flips} | {c["diff"]:+.1f} ± {c.se:.1f} |')
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, default=float))
