"""Test 57: a vig-aware map for picking underdogs worth the points; see VIG_AWARE_MAP.md.

    python research/vig_aware_map.py

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

OUT = ROOT/'research/vig_aware_map_results'
PROTOCOL_COMMIT = '5d71016'
BREAK_EVEN = 1.1/2.1
K = 2
Z_BAR = float(norm.ppf(1-.05/K/2))  # 2.24
ARMS = ('P production', 'V vig-aware', 'U underdog-only')


def decide(h, s, threshold=BREAK_EVEN):
    """Home-signed side (+1 home, -1 away, 0 skip) for each row of s, from band margins of earlier seasons in h."""
    out = np.zeros(len(s))
    for y in sorted(s.season.unique()):
        t = smap.training(h, int(y))
        k = s.season.eq(y).to_numpy()
        if t is None: out[k] = np.nan; continue
        band_tr, S = t
        g = s[k]; x = g.model_spread.to_numpy(float); sgn = np.sign(x)
        ell = sgn*g.spread_line.to_numpy(float); band = np.digitize(np.abs(x), smap.CUTS)
        side = np.zeros(len(g))
        for i in range(len(g)):
            Sk = S[band_tr == band[i]]; win = (Sk > ell[i]).sum(); lose = (Sk < ell[i]).sum()
            if win+lose == 0: continue
            pm = win/(win+lose)
            if pm >= threshold: side[i] = sgn[i]
            elif 1-pm >= threshold: side[i] = -sgn[i]
        out[k] = side
    return out


def frames():
    fr, repro, prod = smap.frames()
    out = {}
    for b, h in fr.items():
        smap.map_all(h, b)
        repro[f'map vs fixed_bands {b}'] = smap.check_m0(h, b, prod)
        s = h[h.season.between(*smap.BASES[b]['span']) & np.isfinite(h.spread_line) & np.isfinite(h.result)
              & np.isfinite(h['M0 production'])].sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
        line = s.spread_line.to_numpy(float)
        v = decide(h, s); fav = np.sign(line)
        s['P production'] = fb.pick(s['M0 production'].to_numpy(float), line)
        s['V vig-aware'] = v
        s['U underdog-only'] = np.where((v == fav) | (line == 0), 0., v)
        s['V at 0.5'] = decide(h, s, .5)
        out[b] = s
    return out, repro


def drawdown(s, ret):
    w = pd.Series(np.nan_to_num(ret)).groupby([s.season.to_numpy(), s.week.to_numpy()]).sum()
    c = w.cumsum().to_numpy(); d = c-np.maximum.accumulate(np.r_[0, c])[1:]; cur = lon = 0
    for u in d < 0: cur = cur+1 if u else 0; lon = max(lon, cur)
    return float(-d.min()), int(lon)


def records(b, period, s):
    line = s.spread_line.to_numpy(float); margin = (s.result-s.spread_line).to_numpy(float); fav = np.sign(line)
    rows, rets = [], {}
    for arm in ARMS:
        side = s[arm].to_numpy(float); rec, rets[arm] = sm.ats_record(side, margin)
        mdd, lon = drawdown(s, rets[arm])
        bet = side != 0
        rows.append({'basis': b, 'period': period, 'arm': arm, **rec, 'max_drawdown': mdd, 'weeks_under_water': lon,
                     'dog_share': float(np.mean(side[bet] == -fav[bet])) if bet.any() else np.nan,
                     'bets_by_band': np.bincount(np.digitize(s.model_spread.abs()[bet], smap.CUTS), minlength=4).tolist()})
    for name, side in (('always favorite', fav), ('always home', np.ones(len(s))), ('always underdog', np.where(line != 0, -fav, 0.))):
        rec, _ = sm.ats_record(side, margin); rows.append({'basis': b, 'period': period, 'arm': name, **rec})
    contrast = {'basis': b, 'period': period, 'n': len(s)}
    for arm in ARMS[1:]:
        diff = rets[arm]-rets['P production']; se = float(diff.std(ddof=1)*np.sqrt(len(diff)))
        contrast[f'{arm} - P'] = float(diff.sum()); contrast[f'{arm} - P se'] = se
        contrast[f'{arm} - P z'] = float(diff.sum()/se) if se > 0 else np.nan
    u = s['U underdog-only'].to_numpy(float) != 0
    ru, _ = sm.ats_record(s['U underdog-only'].to_numpy(float)[u], margin[u])
    alld = line != 0; rd, _ = sm.ats_record(-fav[alld], margin[alld])
    contrast.update({'U_dog_cover': ru['cover'], 'U_dog_bets': ru['bets'], 'all_dog_cover': rd['cover'],
                     'check_V05_agrees_with_P': float(np.mean(s['V at 0.5'].to_numpy() == s['P production'].to_numpy()))})
    return rows, contrast


def verdict(c, arm):
    a = c[(c.basis == '2016-22') & (c.period == '2016-2022')].iloc[0]
    q = c[(c.basis == '2023-26') & (c.period == '2023-2026')].iloc[0]
    za, zq = a[f'{arm} - P z'], q[f'{arm} - P z']
    if za <= -Z_BAR or zq <= -Z_BAR: return 'worse than P'
    if (za >= Z_BAR and q[f'{arm} - P'] > 0) or (zq >= Z_BAR and a[f'{arm} - P'] > 0): return 'favored over P'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    fr, repro = frames()
    rows, contrasts = [], []
    for b, s in fr.items():
        span = smap.BASES[b]['span']
        r, c = records(b, f'{span[0]}-{span[1]}', s); rows += r; contrasts.append(c)
        for y, g in s.groupby('season'):
            r, c = records(b, str(int(y)), g.reset_index(drop=True)); rows += r; contrasts.append(c)
    rows, contrasts = pd.DataFrame(rows), pd.DataFrame(contrasts)
    verdicts = {arm: verdict(contrasts, arm) for arm in ARMS[1:]}
    res = {'protocol': 'research/VIG_AWARE_MAP.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'break_even': BREAK_EVEN, 'z_bar': Z_BAR, 'verdicts': verdicts}
    rows.to_csv(out/'records.csv', index=False, float_format='%.6g')
    contrasts.to_csv(out/'contrasts.csv', index=False, float_format='%.6g')
    (out/'results.json').write_text(json.dumps(res, indent=2, default=float))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/VIG_AWARE_MAP.md', ROOT/'research/smooth_map.py', ROOT/'nfl_model.py',
        ROOT/'fixed_bands.py', smap.LEDGER)}, indent=2))
    report(res, rows, contrasts, out)
    return res


def report(res, rows, contrasts, out):
    L = ['# Test 57: a vig-aware map for picking underdogs worth the points', '',
         f'Protocol: [VIG_AWARE_MAP.md](../VIG_AWARE_MAP.md), committed (`{res["protocol_commit"]}`) before any arm was computed. '
         'Both bases are exposed; descriptive only. Flat 1u at -110; break-even 52.4%; pushes in the ROI denominator.', '',
         'Reproduction: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.', '',
         f'Verdicts (bar |z| >= {res["z_bar"]:.2f}): ' + ', '.join(f'{k}: {v}' for k, v in res['verdicts'].items()) + '.', '',
         '## Contrasts against production and the underdog goal measure', '',
         '| Basis | Period | Games | V − P | U − P | U underdog bets | U cover | All underdogs cover | Check: V at 0.5 agrees with P |',
         '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for _, c in contrasts.iterrows():
        L.append(f'| {c.basis} | {c.period} | {c.n} | {c["V vig-aware - P"]:+.1f} ± {c["V vig-aware - P se"]:.1f} | '
                 f'{c["U underdog-only - P"]:+.1f} ± {c["U underdog-only - P se"]:.1f} | {int(c.U_dog_bets)} | '
                 f'{100*c.U_dog_cover:.1f}% | {100*c.all_dog_cover:.1f}% | {100*c.check_V05_agrees_with_P:.1f}% |')
    L += ['', '## Records', '', '| Basis | Period | Arm | W-L-P | Skips | Bets | Units | ROI ± SE | Cover | Underdog share | '
          'Max drawdown | Weeks under water | Bets by band (<3, 3-7, 7-10, 10+) |', '|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
    for _, r in rows.iterrows():
        ds = '' if pd.isna(r.get('dog_share')) else f'{100*r.dog_share:.0f}%'
        md = '' if pd.isna(r.get('max_drawdown')) else f'{r.max_drawdown:.1f}'
        wu = '' if pd.isna(r.get('weeks_under_water')) else f'{int(r.weeks_under_water)}'
        bb = '' if not isinstance(r.get('bets_by_band'), list) else str(r.bets_by_band)
        L.append(f'| {r.basis} | {r.period} | {r.arm} | {r.W}-{r.L}-{r.P} | {r.skips} | {r.bets} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {100*r.cover:.1f}% | {ds} | {md} | {wu} | {bb} |')
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    print(json.dumps(run(), indent=2, default=float))
