"""Test 50: a total-conditioned median map; see TOTAL_MEDIAN_MAP.md.

    python research/total_median_map.py --freeze GAMES_CSV   # freeze replay columns, OOS spreads and totals
    python research/total_median_map.py                      # fidelity check and scores (no network)

Arms: M production map (fixed_bands), T2 band x total half (primary), T3 band x total tercile
(descriptive). The primary score is the absolute error of the mapped spread; flat 1u ATS at -110 is
reported and never decides. Never writes data/, public/ or the ledgers. Development evidence only.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nfl_model as m  # noqa: E402
import fixed_bands as fb  # noqa: E402

INPUTS = ROOT/'research/total_median_map_inputs'
REPLAY, OOS, TOTALS = INPUTS/'replay.csv', INPUTS/'oos.csv', INPUTS/'totals.csv'
OUT = ROOT/'research/total_median_map_results'
PROTOCOL = ROOT/'research/TOTAL_MEDIAN_MAP.md'
PROTOCOL_COMMIT = 'ecb6168'
LEDGER_SRC = ROOT/'data/latest/fixed_band_ledger.csv'
SUMMARY_SRC = ROOT/'data/latest/fixed_band_summary.csv'
OOS_SRC = ROOT/'research/out_of_sample_results/predictions.csv'
MIN_CELL = 30
SEED, DRAWS, LEVEL = 20261103, 2000, .95
BASES = {'R 2023-25': ('R', 2023, 2025), 'O 2019-20': ('O', 2019, 2020), 'R 2026 (diagnostic)': ('R', 2026, 2026)}
DECIDING = ('R 2023-25', 'O 2019-20')
ARMS = ('M', 'T2', 'T3')
WIN = 1/1.1


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def guard(out):
    out = Path(out).resolve()
    if any(out == x or x in out.parents for x in (ROOT/'data', ROOT/'public')): raise ValueError('Protected output')
    return out


# --- inputs -----------------------------------------------------------------------------------------

def freeze(games_csv):
    INPUTS.mkdir(parents=True, exist_ok=True)
    r = pd.read_csv(LEDGER_SRC)[['game_id', 'season', 'week', 'model_spread', 'fixed_band_spread', 'spread_line', 'result']]
    o = pd.read_csv(OOS_SRC)
    o = o.assign(model_spread=m.implied_spread(o['production']))[['game_id', 'season', 'week', 'model_spread', 'spread_line', 'result']]
    g = pd.read_csv(games_csv)
    g = g[g.game_type == 'REG'][['game_id', 'total_line', 'spread_line', 'result']]
    ids = pd.concat([r.game_id, o.game_id]).drop_duplicates()
    t = g[g.game_id.isin(ids)][['game_id', 'total_line']]
    missing = sorted(set(ids)-set(t.dropna().game_id))
    if missing: raise ValueError(f'{len(missing)} games without a total, e.g. {missing[:3]}')
    agree = {}
    for name, f in (('replay', r), ('oos', o)):
        j = f.merge(g, on='game_id', suffixes=('', '_games'))
        agree[name] = {c: int((~np.isclose(j[c], j[c+'_games'], equal_nan=True)).sum()) for c in ('spread_line', 'result')}
    r.to_csv(REPLAY, index=False, float_format='%.10g'); o.to_csv(OOS, index=False, float_format='%.10g')
    t.sort_values('game_id').to_csv(TOTALS, index=False)
    pub = pd.read_csv(SUMMARY_SRC).query("season == 'All' and method == 'Fixed bands'").iloc[0]
    published = {'games': int(pub.games), 'W': int(pub.wins), 'L': int(pub.losses), 'P': int(pub.pushes), 'units': float(pub.units)}
    (INPUTS/'provenance.json').write_text(json.dumps({
        'published_replay_2023_on': published, 'fixed_band_summary_sha256': sha(SUMMARY_SRC),
        'games_csv_sha256': sha(games_csv), 'games_csv_source': 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
        'fixed_band_ledger_sha256': sha(LEDGER_SRC), 'oos_predictions_sha256': sha(OOS_SRC),
        'replay_sha256': sha(REPLAY), 'oos_sha256': sha(OOS), 'totals_sha256': sha(TOTALS),
        'rows_differing_from_games_csv': agree,
        'note': 'replay.csv is a frozen copy of data/latest/fixed_band_ledger.csv columns (bot-generated, changes each build); '
                'oos.csv maps the 2017-20 out-of-sample production probability through nfl_model.implied_spread; '
                'totals.csv is nflverse total_line (capture time unknown). Spreads and results are taken from the frozen inputs.'}, indent=2))


def load(kind):
    f = pd.read_csv(REPLAY if kind == 'R' else OOS).merge(pd.read_csv(TOTALS), on='game_id', how='left', validate='one_to_one')
    if f.total_line.isna().any(): raise ValueError('Missing totals')
    return f


# --- total-conditioned map --------------------------------------------------------------------------

def training(history, season):
    d = history.loc[history.season < season].copy()
    for c in ('model_spread', 'result', 'total_line'): d[c] = pd.to_numeric(d[c], errors='coerce')
    return d.loc[np.isfinite(d[['model_spread', 'result']]).all(axis=1) & d.model_spread.ne(0)]


def total_group(total, cuts):
    """Index of the total group: the number of cuts strictly below the total (a total equal to a cut is low)."""
    return np.searchsorted(np.asarray(cuts, float), np.asarray(total, float), side='left')


def fit_conditioned(history, season, groups):
    """Production's prior-season signed-MOV medians per band x total group; sparse cells fall back to production."""
    base = fb.fit(history, season)
    if base is None: return None
    d = training(history, season)
    if not np.isfinite(d.total_line).all(): raise ValueError('Training rows need totals')
    cuts = np.quantile(d.total_line.to_numpy(float), [k/groups for k in range(1, groups)]).tolist()
    band = np.digitize(d.model_spread.abs(), fb.CUTS); grp = total_group(d.total_line, cuts)
    signed = np.sign(d.model_spread.to_numpy())*d.result.to_numpy()
    mags, counts, fallback = np.zeros((4, groups)), np.zeros((4, groups), int), np.zeros((4, groups), bool)
    for k in range(4):
        for j in range(groups):
            sel = (band == k) & (grp == j); counts[k, j] = int(sel.sum())
            if counts[k, j] < MIN_CELL: mags[k, j] = base['magnitudes'][k]; fallback[k, j] = True
            else: mags[k, j] = float(np.median(signed[sel]))
    return dict(season=int(season), groups=groups, total_cuts=cuts, magnitudes=mags.tolist(), counts=counts.tolist(),
                fallback=fallback.tolist(), base_magnitudes=base['magnitudes'], training_games=len(d))


def apply_conditioned(spread, total, rule):
    x = np.asarray(spread, float); t = np.asarray(total, float)
    if rule is None: return np.full(x.shape, np.nan)
    band = np.digitize(np.abs(np.nan_to_num(x)), fb.CUTS); grp = total_group(np.nan_to_num(t), rule['total_cuts'])
    return np.where(np.isfinite(x) & np.isfinite(t), np.sign(x)*np.asarray(rule['magnitudes'])[band, grp], np.nan)


def predictions(frame):
    out = frame.copy()
    for c in ARMS+('LINE',): out[c] = np.nan
    rules = {}
    for s in sorted(frame.season.unique()):
        k = (frame.season == s).to_numpy()
        base = fb.fit(frame, s); r2 = fit_conditioned(frame, s, 2); r3 = fit_conditioned(frame, s, 3)
        out.loc[k, 'M'] = fb.apply(frame.loc[k, 'model_spread'], base)
        out.loc[k, 'T2'] = apply_conditioned(frame.loc[k, 'model_spread'], frame.loc[k, 'total_line'], r2)
        out.loc[k, 'T3'] = apply_conditioned(frame.loc[k, 'model_spread'], frame.loc[k, 'total_line'], r3)
        out.loc[k, 'LINE'] = fb.apply(frame.loc[k, 'spread_line'], base)
        rules[int(s)] = {'M': base, 'T2': r2, 'T3': r3}
    return out, rules


# --- scoring ----------------------------------------------------------------------------------------

def baseline_predictions(line):
    """Predictions that make fixed_bands.pick take the favorite (pick'em skips) and the home side."""
    line = np.asarray(line, float)
    return {'Always favorite': 2*line, 'Always home': line+1.}


def record(result, units):
    res = np.asarray(result); u = np.asarray(units, float)
    bet = np.isin(res, ['W', 'L', 'P']); ub = u[bet]
    w, l, p = int((res == 'W').sum()), int((res == 'L').sum()), int((res == 'P').sum())
    return {'W': w, 'L': l, 'P': p, 'skips': int((res == 'S').sum()), 'n': int(bet.sum()), 'units': float(ub.sum()),
            'roi': float(ub.mean()) if len(ub) else np.nan, 'roi_se': float(ub.std(ddof=1)/np.sqrt(len(ub))) if len(ub) > 1 else np.nan,
            'cover': w/(w+l) if w+l else np.nan}


def draws(clusters, n=DRAWS, seed=SEED):
    ids, inv = np.unique(clusters, return_inverse=True)
    rng = np.random.default_rng(seed)
    return rng.multinomial(len(ids), np.full(len(ids), 1/len(ids)), size=n).astype(float), inv, len(ids)


def boot_mean(x, inv, C, G):
    s = np.bincount(inv, x, G); c = np.bincount(inv, np.ones(len(x)), G)
    return (C @ s)/(C @ c)


def score(pred, label, rules):
    d = pred[np.isfinite(pred[list(ARMS)+['LINE']]).all(axis=1) & np.isfinite(pred.result)].reset_index(drop=True)
    y = d.result.to_numpy(float); C, inv, G = draws((d.season*100+d.week).to_numpy())
    lo, hi = 50*(1-LEVEL), 50*(1+LEVEL)
    ae = {a: np.abs(d[a].to_numpy(float)-y) for a in ARMS+('LINE',)}
    acc = {'basis': label, 'games': int(len(d)), 'mae': {a: float(v.mean()) for a, v in ae.items()}, 'abs_error_gain': {}}
    for a in ('T2', 'T3'):
        g = ae['M']-ae[a]; b = boot_mean(g, inv, C, G)
        acc['abs_error_gain'][a] = {'mean': float(g.mean()), 'ci95': [float(np.percentile(b, lo)), float(np.percentile(b, hi))]}
    picks = {**{a: d[a].to_numpy(float) for a in ARMS}, 'Line-only map': d.LINE.to_numpy(float), **baseline_predictions(d.spread_line)}
    graded = {k: fb.grade(d, v) for k, v in picks.items()}
    acc['ats'] = {k: record(*v) for k, v in graded.items()}
    sides = {a: fb.pick(d[a].to_numpy(float), d.spread_line.to_numpy(float)) for a in ARMS}
    acc['paired_vs_M'] = {}
    for a in ('T2', 'T3'):
        du = np.nan_to_num(graded[a][1])-np.nan_to_num(graded['M'][1]); b = boot_mean(du, inv, C, G)
        flip = sides[a] != sides['M']
        acc['paired_vs_M'][a] = {'units': float(du.sum()), 'per_game': float(du.mean()), 'per_game_se': float(b.std(ddof=1)),
                                 'flips': int(flip.sum()), 'arm_on_flips': record(graded[a][0][flip], graded[a][1][flip]),
                                 'M_on_flips': record(graded['M'][0][flip], graded['M'][1][flip])}
    # descriptive: by the T2 rule's total half
    half = np.zeros(len(d), int)
    for s in d.season.unique():
        k = (d.season == s).to_numpy(); half[k] = total_group(d.total_line[k], rules[int(s)]['T2']['total_cuts'])
    acc['by_total_half'] = {name: {'games': int((half == j).sum()), 'abs_error_gain_T2': float((ae['M']-ae['T2'])[half == j].mean()),
                                   'M': record(graded['M'][0][half == j], graded['M'][1][half == j]),
                                   'T2': record(graded['T2'][0][half == j], graded['T2'][1][half == j])}
                            for j, name in enumerate(('low', 'high'))}
    return acc, d


def verdict(acc):
    g = {b: acc[b]['abs_error_gain']['T2'] for b in DECIDING}
    if any(v['mean'] <= 0 for v in g.values()): return 'not supported'
    if any(v['ci95'][0] > 0 for v in g.values()): return 'supported for a forward shadow'
    return 'unresolved'


def run(out=OUT):
    out = guard(out); out.mkdir(parents=True, exist_ok=True)
    frames = {k: load(k) for k in ('R', 'O')}
    preds, rules = {}, {}
    for k, f in frames.items(): preds[k], rules[k] = predictions(f)
    # fidelity: production map on the replay
    r = preds['R']; ok = np.isfinite(r.M)
    fid = {'mapped_equal_published': bool(np.allclose(r.M[ok], r.fixed_band_spread[ok])), 'rows': int(ok.sum())}
    rep = record(*fb.grade(r[ok & (r.season >= 2023)], r.M[ok & (r.season >= 2023)].to_numpy(float)))
    fid['replay_2023_on'] = rep
    pub = json.loads((INPUTS/'provenance.json').read_text())['published_replay_2023_on']; fid['published'] = pub
    if not fid['mapped_equal_published'] or (rep['n'], rep['W'], rep['L'], rep['P']) != (pub['games'], pub['W'], pub['L'], pub['P']) \
            or not np.isclose(rep['units'], pub['units']):
        raise ValueError(f'Production map does not reproduce the published replay: {fid}')
    acc, frames_scored = {}, []
    for label, (kind, lo, hi) in BASES.items():
        p = preds[kind][preds[kind].season.between(lo, hi)]
        acc[label], d = score(p, label, rules[kind]); frames_scored.append(d.assign(basis=label))
    info = {'protocol': 'research/TOTAL_MEDIAN_MAP.md', 'protocol_commit': PROTOCOL_COMMIT, 'fidelity': fid,
            'verdict_T2': verdict(acc), 'bases': acc,
            'rules': {k: {str(s): v for s, v in rr.items()} for k, rr in rules.items()}}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=True, default=float))
    pd.concat(frames_scored).to_csv(out/'predictions.csv', index=False, float_format='%.6g')
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in
                                                   (Path(__file__), PROTOCOL, ROOT/'fixed_bands.py', REPLAY, OOS, TOTALS)}, indent=2))
    write_report(info, out)
    return info


def write_report(info, out):
    def f(x, fmt='+.3f'): return '–' if x is None or not np.isfinite(x) else format(x, fmt).replace('-', '−')
    def rr(r): return (f"{r['W']}-{r['L']}-{r['P']}" + (f" ({r['skips']} skips)" if r['skips'] else '')
                       + f" | {f(r['units'], '+.1f')}u | {f(100*r['roi'], '+.2f')}% ± {f(100*r['roi_se'], '.2f')} | {f(100*r['cover'], '.1f')}%")
    B = info['bases']
    L = ['# Test 50: a total-conditioned median map', '',
         f"Protocol: [TOTAL_MEDIAN_MAP.md](../TOTAL_MEDIAN_MAP.md), pushed (`{info['protocol_commit']}`) before any total-conditioned "
         'magnitude was fitted or scored. Production v1.18, the median map, the lock policy and the ledgers are unchanged. '
         'Development evidence on exposed seasons.', '',
         f"Fidelity: the production map reproduces the published `fixed_band_spread` on {info['fidelity']['rows']} replay rows and the "
         f"published 2023-on replay record {rr(info['fidelity']['replay_2023_on'])} ({info['fidelity']['replay_2023_on']['n']} games).", '',
         f"**Verdict (T2): {info['verdict_T2']}.**", '',
         '## Primary: absolute-error gain of the mapped spread (production minus arm, points per game; positive = arm better)', '',
         '| Basis | Games | MAE production | MAE T2 | T2 gain [95%] | MAE T3 | T3 gain [95%] (descriptive) | MAE line-only map |',
         '|---|---:|---:|---:|---|---:|---|---:|']
    for b, a in B.items():
        g2, g3 = a['abs_error_gain']['T2'], a['abs_error_gain']['T3']
        L.append(f"| {b} | {a['games']} | {a['mae']['M']:.3f} | {a['mae']['T2']:.3f} | {f(g2['mean'])} [{f(g2['ci95'][0])}, {f(g2['ci95'][1])}] | "
                 f"{a['mae']['T3']:.3f} | {f(g3['mean'])} [{f(g3['ci95'][0])}, {f(g3['ci95'][1])}] | {a['mae']['LINE']:.3f} |")
    L += ['', '## Goal metric, reported only: flat 1u ATS at −110 (W-L-P | units | ROI ± SE | cover)', '']
    for b, a in B.items():
        L += [f'**{b}**', '', '| Arm | Record |', '|---|---|']
        for k in ('M', 'T2', 'T3', 'Line-only map', 'Always favorite', 'Always home'):
            L.append(f"| {dict(M='Production map', T2='T2 (primary)', T3='T3 (descriptive)').get(k, k)} | {rr(a['ats'][k])} |")
        for k in ('T2', 'T3'):
            p = a['paired_vs_M'][k]
            L.append(f"| {k} minus production | {f(p['units'], '+.1f')}u, {f(p['per_game'], '+.4f')} ± {f(p['per_game_se'], '.4f')} per game; "
                     f"{p['flips']} flips: {k} {p['arm_on_flips']['W']}-{p['arm_on_flips']['L']}-{p['arm_on_flips']['P']}, production "
                     f"{p['M_on_flips']['W']}-{p['M_on_flips']['L']}-{p['M_on_flips']['P']} |")
        L.append('')
    L += ['## By the T2 rule\'s total half (descriptive)', '', '| Basis | Half | Games | T2 abs-error gain | Production ATS | T2 ATS |', '|---|---|---:|---:|---|---|']
    for b, a in B.items():
        for h, v in a['by_total_half'].items():
            L.append(f"| {b} | {h} | {v['games']} | {f(v['abs_error_gain_T2'])} | {rr(v['M'])} | {rr(v['T2'])} |")
    L += ['', '## Fitted magnitudes (bands <3, 3–<7, 7–<10, 10+; low / high total; * = fallback to production)', '',
          '| Basis | Season | Split total | Production | T2 low | T2 high |', '|---|---:|---:|---|---|---|']
    for k, rr_ in info['rules'].items():
        for s, v in rr_.items():
            t2 = v['T2']
            if t2 is None: continue
            cell = lambda j: ' / '.join(f"{t2['magnitudes'][i][j]:g}{'*' if t2['fallback'][i][j] else ''}" for i in range(4))
            L.append(f"| {k} | {s} | {t2['total_cuts'][0]:g} | {' / '.join(f'{x:g}' for x in v['M']['magnitudes'])} | {cell(0)} | {cell(1)} |")
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--freeze', metavar='GAMES_CSV', help='freeze inputs from the nflverse games file')
    a = ap.parse_args()
    if a.freeze: freeze(a.freeze)
    else: run()
