"""Test 35: which de-vig method gives the best market anchor? See DEVIG_METHODS.md.

Arms (parameter-free): P proportional (production), A additive (= Shin for two outcomes),
W power. Selection on 2006-2016 by log loss; held-out 2017-2025 scored once against P.

The first run downloads nflverse schedules and freezes the needed columns in
devig_methods_results/schedule_pack.csv.gz; later runs read only the frozen pack.

    python research/devig_methods.py
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import logit, ndtri
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nfl_model as m  # noqa: E402

OUT = ROOT/'research/devig_methods_results'
PACK = OUT/'schedule_pack.csv.gz'
SELECTION, HELD_OUT = (2006, 2016), (2017, 2025)
ARMS = ('P', 'A', 'W')
NAMES = {'P': 'proportional (production)', 'A': 'additive (= Shin)', 'W': 'power'}
LEVEL = .975
BANDS = ((.5, .6, '0.50–0.60'), (.6, .7, '0.60–0.70'), (.7, .8, '0.70–0.80'), (.8, 1.01, '≥ 0.80'))
PACK_COLS = ['game_id', 'season', 'week', 'home_team', 'away_team', 'home_moneyline', 'away_moneyline', 'result']


def implied(ml):
    ml = np.asarray(ml, float)
    with np.errstate(divide='ignore', invalid='ignore'):
        return np.where(ml < 0, -ml/(-ml+100.), 100./(ml+100.))


def valid_prices(hm, am):
    hm, am = np.asarray(hm, float), np.asarray(am, float)
    return np.isfinite(hm) & np.isfinite(am) & (np.abs(hm) >= 100) & (np.abs(am) >= 100)


def power_k(a, b):
    """k with a^k + b^k = 1; k = 1 when there is no hold."""
    if np.isclose(a+b, 1., atol=1e-15): return 1.
    return brentq(lambda k: a**k+b**k-1, 1e-6, 50., xtol=1e-14)


def devig(hm, am, arm):
    """No-vig home probability under arm P, A or W; NaN where either price is invalid."""
    a, b = implied(hm), implied(am)
    ok = valid_prices(hm, am)
    out = np.full(a.shape, np.nan)
    if arm == 'P': out[ok] = a[ok]/(a[ok]+b[ok])
    elif arm == 'A': out[ok] = a[ok]-(a[ok]+b[ok]-1)/2
    elif arm == 'W': out[ok] = [x**power_k(x, y) for x, y in zip(a[ok], b[ok])]
    else: raise ValueError(f'unknown arm {arm}')
    return out


def null_ev(q_side, ml_side):
    """Market-correct expected profit of 1u on a side priced ml_side whose fair probability is q_side."""
    ml = np.asarray(ml_side, float)
    pay = np.where(ml > 0, ml/100., 100./-ml)
    return q_side*pay-(1-q_side)


def log_loss(q, y):
    q = np.clip(q, 1e-12, 1-1e-12)
    return -(y*np.log(q)+(1-y)*np.log(1-q))


def paired(diff, level=LEVEL):
    diff = np.asarray(diff, float); n = len(diff)
    mean = float(diff.mean()); se = float(diff.std(ddof=1)/np.sqrt(n)) if n > 1 else np.nan
    z = float(ndtri(.5+level/2))
    return {'n': n, 'mean': mean, 'se': se, 'lo': mean-z*se, 'hi': mean+z*se}


def calibration(q, y):
    """Logistic recalibration y ~ intercept + slope * logit(q). Slope > 1: q too timid."""
    x = logit(np.clip(q, 1e-9, 1-1e-9))
    def nll(t):
        z = t[0]+t[1]*x
        return float(np.sum(np.logaddexp(0, z)-y*z))
    r = minimize(nll, [0., 1.], method='BFGS')
    X = np.column_stack([np.ones_like(x), x]); w = 1/(1+np.exp(-(X @ r.x))); w = w*(1-w)
    cov = np.linalg.inv(X.T @ (X*w[:, None]))  # exact Fisher information at the optimum
    return {'intercept': float(r.x[0]), 'slope': float(r.x[1]),
            'intercept_se': float(np.sqrt(cov[0, 0])), 'slope_se': float(np.sqrt(cov[1, 1]))}


def frame(sched):
    """Included games with every arm's q, labels and favorite/underdog prices."""
    g = sched[valid_prices(sched.home_moneyline, sched.away_moneyline) & sched.result.notna()
              & (sched.result != 0)].copy()
    g['y'] = (g.result > 0).astype(float)
    for arm in ARMS: g[f'q_{arm}'] = devig(g.home_moneyline, g.away_moneyline, arm)
    g['fav_home'] = g.q_P >= .5
    g['fav_wp'] = np.maximum(g.q_P, 1-g.q_P)
    g['band'] = pd.cut(g.fav_wp, [b[0] for b in BANDS]+[BANDS[-1][1]], labels=[b[2] for b in BANDS], right=False)
    return g.reset_index(drop=True)


def score(g):
    out = {'n': len(g), 'arms': {}}
    for arm in ARMS:
        q = g[f'q_{arm}'].to_numpy(); y = g.y.to_numpy()
        out['arms'][arm] = {'log_loss': float(log_loss(q, y).mean()), 'brier': float(((q-y)**2).mean()),
                            'gain_vs_P': paired(log_loss(g.q_P.to_numpy(), y)-log_loss(q, y)),
                            'calibration': calibration(q, y)}
    return out


def select(selection_score):
    """Lowest selection log loss; exact ties go to P."""
    ll = {a: selection_score['arms'][a]['log_loss'] for a in ARMS}
    best = min(ll.values())
    return 'P' if ll['P'] == best else min(ll, key=ll.get)


def verdict(selected, gain):
    if selected == 'P': return 'keep P (P selected)'
    if gain['lo'] > 0: return f'propose {selected} to the owner (held-out gain excludes zero)'
    if gain['hi'] < 0: return f'keep P ({selected} worse on held-out, interval excludes zero)'
    return 'unresolved, keep P'


def side_table(g):
    """Per band: favorite and underdog flat 1u ROI (method-independent) and each arm's mean null."""
    rows = []
    for _, _, lab in BANDS:
        b = g[g.band == lab]
        for side in ('favorite', 'underdog'):
            home = b.fav_home if side == 'favorite' else ~b.fav_home
            ml = np.where(home, b.home_moneyline, b.away_moneyline)
            won = np.where(home, b.y, 1-b.y)
            pay = np.where(ml > 0, ml/100., 100./-ml)
            units = np.where(won == 1, pay, -1.)
            row = {'band': lab, 'side': side, 'n': len(b), 'units': float(units.sum()),
                   'roi': float(units.mean()) if len(b) else np.nan,
                   'roi_se': float(units.std(ddof=1)/np.sqrt(len(b))) if len(b) > 1 else np.nan}
            for arm in ARMS:
                qs = np.where(home, b[f'q_{arm}'], 1-b[f'q_{arm}'])
                row[f'null_{arm}'] = float(null_ev(qs, ml).mean()) if len(b) else np.nan
            rows.append(row)
    return rows


def band_gains(g):
    out = []
    for _, _, lab in BANDS:
        b = g[g.band == lab]; y = b.y.to_numpy(); lp = log_loss(b.q_P.to_numpy(), y)
        out.append({'band': lab, 'n': len(b),
                    **{arm: paired(lp-log_loss(b[f'q_{arm}'].to_numpy(), y)) for arm in ARMS if arm != 'P'}})
    return out


def season_gains(g):
    out = []
    for s, b in g.groupby('season'):
        y = b.y.to_numpy(); lp = log_loss(b.q_P.to_numpy(), y)
        out.append({'season': int(s), 'n': len(b),
                    **{arm: float((lp-log_loss(b[f'q_{arm}'].to_numpy(), y)).mean()) for arm in ARMS if arm != 'P'}})
    return out


def load_pack():
    if not PACK.exists():
        import nflreadpy as nfl
        s = nfl.load_schedules(list(range(SELECTION[0], HELD_OUT[1]+1))).to_pandas()
        s = m.normalize_teams(s[s.game_type == 'REG'].copy())
        OUT.mkdir(parents=True, exist_ok=True)
        s[PACK_COLS].sort_values('game_id').to_csv(PACK, index=False, compression={'method': 'gzip', 'mtime': 0})
    return pd.read_csv(PACK)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pct(x): return f'{100*x:+.1f}%'


def report(res):
    sel, ho = res['selection'], res['held_out']
    lines = ['# Test 35: de-vig method for the market anchor', '',
             'Protocol: [DEVIG_METHODS.md](../DEVIG_METHODS.md), pushed before any non-proportional q was scored. '
             'Basis: nflverse schedule moneylines (capture time unknown), regular season; selection 2006–2016, '
             'held-out 2017–2025 scored once. Not forward evidence.',
             f"Selected on 2006–2016: **{res['selected']} ({NAMES[res['selected']]})**. "
             f"**Verdict: {res['verdict']}.**", '',
             'Flat 1u ROI on the model side and the market-favorite baseline are identical under every arm (all '
             'three agree on the favorite); the arms differ only in q and what is computed from it.', '']
    for title, s in (('Held-out 2017–2025', ho), ('Selection 2006–2016 (selection data)', sel)):
        lines += [f'## {title}: {s["n"]} decided, priced games', '',
                  '| Arm | Log loss | Brier | LL gain vs P [97.5%] | Calib. intercept | Calib. slope |',
                  '|---|---:|---:|---:|---:|---:|']
        for arm in ARMS:
            a = s['arms'][arm]; gg = a['gain_vs_P']; c = a['calibration']
            gain = '—' if arm == 'P' else f"{gg['mean']:+.5f} ± {gg['se']:.5f} [{gg['lo']:+.5f}, {gg['hi']:+.5f}]"
            lines.append(f"| {arm} {NAMES[arm]} | {a['log_loss']:.5f} | {a['brier']:.5f} | {gain} | "
                         f"{c['intercept']:+.3f} ± {c['intercept_se']:.3f} | {c['slope']:.3f} ± {c['slope_se']:.3f} |")
        lines += ['', 'LL gain vs P by production favorite probability (± SE):', '',
                  '| Band | n | A | W |', '|---|---:|---:|---:|']
        for b in s['bands']:
            lines.append(f"| {b['band']} | {b['n']} | {b['A']['mean']:+.5f} ± {b['A']['se']:.5f} | "
                         f"{b['W']['mean']:+.5f} ± {b['W']['se']:.5f} |")
        lines += ['', 'Flat 1u ROI by side and band (same under every arm) vs each arm\'s mean market-correct null:', '',
                  '| Band | Side | n | Units | ROI ± SE | Null P | Null A | Null W |', '|---|---|---:|---:|---:|---:|---:|---:|']
        for r in s['sides']:
            lines.append(f"| {r['band']} | {r['side']} | {r['n']} | {r['units']:+.2f} | {pct(r['roi'])} ± {100*r['roi_se']:.1f} | "
                         f"{pct(r['null_P'])} | {pct(r['null_A'])} | {pct(r['null_W'])} |")
        lines += ['', '| Season | n | A gain | W gain |', '|---|---:|---:|---:|']
        for r in s['seasons']:
            lines.append(f"| {r['season']} | {r['n']} | {r['A']:+.5f} | {r['W']:+.5f} |")
        lines.append('')
    return '\n'.join(lines)


def run():
    g = frame(load_pack())
    res = {}
    for key, (lo, hi) in (('selection', SELECTION), ('held_out', HELD_OUT)):
        part = g[g.season.between(lo, hi)]
        res[key] = {**score(part), 'bands': band_gains(part), 'sides': side_table(part), 'seasons': season_gains(part)}
    res['selected'] = select(res['selection'])
    res['primary'] = res['held_out']['arms'][res['selected']]['gain_vs_P']
    res['verdict'] = verdict(res['selected'], res['primary'])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/'results.json').write_text(json.dumps(res, indent=1, default=float)+'\n')
    (OUT/'REPORT.md').write_text(report(res))
    (OUT/'provenance.json').write_text(json.dumps(
        {str(p.relative_to(ROOT)): sha(p) for p in (ROOT/'research/devig_methods.py', ROOT/'research/DEVIG_METHODS.md', PACK)},
        indent=1)+'\n')
    return res


if __name__ == '__main__':
    r = run()
    print(f"selected {r['selected']}; held-out gain {r['primary']['mean']:+.5f} "
          f"[{r['primary']['lo']:+.5f}, {r['primary']['hi']:+.5f}]; {r['verdict']}")
