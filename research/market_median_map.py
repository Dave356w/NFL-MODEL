"""Test 51: a market-only median map, fitted on 2022-24 and tested on 2025-26; see MARKET_MEDIAN_MAP.md.

    python research/market_median_map.py --freeze GAMES_CSV   # freeze nflverse lines and the production references
    python research/market_median_map.py                      # fit once, score the test seasons (no network)

No model input enters arms A (spread bands) or B (spread x total half). The production map and the line
through production's model-fitted map are references only. Never writes data/, public/ or the ledgers.
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
import fixed_bands as fb  # noqa: E402

INPUTS = ROOT/'research/market_median_map_inputs'
GAMES, REFS, RULES = INPUTS/'games.csv', INPUTS/'production_refs.csv', INPUTS/'production_rules.json'
OUT = ROOT/'research/market_median_map_results'
PROTOCOL = ROOT/'research/MARKET_MEDIAN_MAP.md'
PROTOCOL_COMMIT = 'd4c316a'
FIT, TEST = (2022, 2024), (2025, 2026)
MIN_CELL = 30
SEED, DRAWS = 20261103, 2000


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def guard(out):
    out = Path(out).resolve()
    if any(out == x or x in out.parents for x in (ROOT/'data', ROOT/'public')): raise ValueError('Protected output')
    return out


def freeze(games_csv):
    INPUTS.mkdir(parents=True, exist_ok=True)
    g = pd.read_csv(games_csv)
    g = g[(g.game_type == 'REG') & g.season.between(FIT[0], TEST[1]) & g.result.notna()]
    g = g[['game_id', 'season', 'week', 'home_team', 'away_team', 'spread_line', 'total_line', 'result']]
    if g[['spread_line', 'total_line']].isna().any(axis=None): raise ValueError('Missing lines')
    g.to_csv(GAMES, index=False)
    led = ROOT/'data/latest/fixed_band_ledger.csv'; rules = ROOT/'data/latest/fixed_band_rules.json'
    r = pd.read_csv(led); r = r[r.season.between(*TEST)][['game_id', 'season', 'fixed_band_spread', 'spread_line', 'result']]
    r.to_csv(REFS, index=False); RULES.write_text(rules.read_text())
    (INPUTS/'provenance.json').write_text(json.dumps({
        'games_csv_sha256': sha(games_csv), 'games_csv_source': 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
        'fixed_band_ledger_sha256': sha(led), 'fixed_band_rules_sha256': sha(rules),
        'games_sha256': sha(GAMES), 'refs_sha256': sha(REFS), 'rules_sha256': sha(RULES),
        'games_by_season': {str(k): int(v) for k, v in g.season.value_counts().sort_index().items()}}, indent=2))


# --- the market-only map ----------------------------------------------------------------------------

def fit(train, by_total):
    """Median favorite margin per |spread| band (and total half); pick'em lines excluded; ties count zero."""
    d = train[pd.to_numeric(train.spread_line, errors='coerce').ne(0)].dropna(subset=['spread_line', 'result'])
    band = np.digitize(d.spread_line.abs(), fb.CUTS); fm = np.sign(d.spread_line.to_numpy())*d.result.to_numpy()
    counts = np.bincount(band, minlength=4)
    if counts.min() < MIN_CELL: raise ValueError(f'Band counts {counts.tolist()} below {MIN_CELL}')
    base = [float(np.median(fm[band == k])) for k in range(4)]
    rule = {'by_total': by_total, 'fit_seasons': sorted(int(s) for s in d.season.unique()), 'fit_games': int(len(d)),
            'band_counts': counts.tolist(), 'base_magnitudes': base}
    if not by_total: return {**rule, 'magnitudes': [[b] for b in base], 'total_cuts': []}
    split = float(np.median(d.total_line)); grp = np.searchsorted([split], d.total_line.to_numpy(float), side='left')
    mags, cnt, fall = [], [], []
    for k in range(4):
        row, crow, frow = [], [], []
        for j in range(2):
            sel = (band == k) & (grp == j); n = int(sel.sum()); crow.append(n)
            if n < MIN_CELL: row.append(base[k]); frow.append(True)
            else: row.append(float(np.median(fm[sel]))); frow.append(False)
        mags.append(row); cnt.append(crow); fall.append(frow)
    return {**rule, 'magnitudes': mags, 'total_cuts': [split], 'cell_counts': cnt, 'fallback': fall}


def apply(line, total, rule):
    line = np.asarray(line, float); total = np.asarray(total, float)
    band = np.digitize(np.abs(np.nan_to_num(line)), fb.CUTS)
    grp = np.searchsorted(rule['total_cuts'], np.nan_to_num(total), side='left') if rule['by_total'] else np.zeros(len(line), int)
    mag = np.asarray(rule['magnitudes'])[band, grp]
    return np.where(np.isfinite(line), np.sign(line)*mag, np.nan)


# --- scoring ----------------------------------------------------------------------------------------

def record(result, units):
    res = np.asarray(result); u = np.asarray(units, float); bet = np.isin(res, ['W', 'L', 'P']); ub = u[bet]
    w, l, p = int((res == 'W').sum()), int((res == 'L').sum()), int((res == 'P').sum())
    roi = float(ub.mean()) if len(ub) else np.nan; se = float(ub.std(ddof=1)/np.sqrt(len(ub))) if len(ub) > 1 else np.nan
    return {'W': w, 'L': l, 'P': p, 'skips': int((res == 'S').sum()), 'n': int(bet.sum()), 'units': float(ub.sum()),
            'roi': roi, 'roi_se': se, 'cover': w/(w+l) if w+l else np.nan,
            'ats_verdict': ('beats -110' if roi-2*se > 0 else 'loses to -110' if roi+2*se < 0 else 'unresolved') if len(ub) > 1 else '–'}


def cluster_boot(x, clusters, draws=DRAWS, seed=SEED):
    ids, inv = np.unique(clusters, return_inverse=True); G = len(ids)
    C = np.random.default_rng(seed).multinomial(G, np.full(G, 1/G), size=draws).astype(float)
    s, c = np.bincount(inv, x, G), np.bincount(inv, np.ones(len(x)), G)
    return (C @ s)/(C @ c)


def baselines(line):
    line = np.asarray(line, float)
    return {'Always favorite': 2*line, 'Always underdog': np.zeros(len(line)), 'Always home': line+1.}


def evaluate(d, rules):
    """All metrics on frame d (test rows). Returns a dict of results."""
    y = d.result.to_numpy(float); line = d.spread_line.to_numpy(float); cl = (d.season*100+d.week).to_numpy()
    preds = {k: apply(d.spread_line, d.total_line, r) for k, r in rules.items()}
    out = {'games': int(len(d)), 'mae_line': float(np.mean(np.abs(line-y))), 'point': {}, 'ats': {}}
    for k, p in preds.items():
        gain = np.abs(line-y)-np.abs(p-y); b = cluster_boot(gain, cl)
        out['point'][k] = {'mae': float(np.mean(np.abs(p-y))), 'gain': float(gain.mean()),
                           'ci95': [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]}
        lo, hi = out['point'][k]['ci95']
        out['point'][k]['verdict'] = 'beats the line' if lo > 0 else 'worse than the line' if hi < 0 else 'no detectable difference'
        for tie, fav in (('ties take favorite', True), ('ties skip', False)):
            out['ats'][f'{k}, {tie}'] = record(*fb.grade(d, p, favorite_on_tie=fav))
        side = fb.pick(p, line)
        out['ats'][f'{k}, ties take favorite']['dog_share'] = float(np.mean(side[side != 0] == -np.sign(line[side != 0])))
    for k, p in baselines(line).items(): out['ats'][k] = record(*fb.grade(d, p))
    return out, preds


def run(out=OUT):
    out = guard(out); out.mkdir(parents=True, exist_ok=True)
    g = pd.read_csv(GAMES)
    train, test = g[g.season.between(*FIT)], g[g.season.between(*TEST)].reset_index(drop=True)
    rules = {'A': fit(train, False), 'B': fit(train, True)}
    res = {'pooled 2025-26': evaluate(test, rules)[0]}
    for s in range(TEST[0], TEST[1]+1): res[str(s)] = evaluate(test[test.season == s].reset_index(drop=True), rules)[0]
    _, preds = evaluate(test, rules)
    # by band x total half (descriptive), arm A and B, production tie rule
    by = []
    band = np.digitize(test.spread_line.abs(), fb.CUTS); half = np.searchsorted(rules['B']['total_cuts'], test.total_line.to_numpy(float), side='left')
    for k in range(4):
        for j in range(2):
            sel = (band == k) & (half == j)
            if not sel.any(): continue
            row = {'band': fb.BANDS[k], 'total': ('low', 'high')[j], 'games': int(sel.sum())}
            for a in ('A', 'B'):
                r = record(*fb.grade(test[sel], preds[a][sel])); row[a] = f"{r['W']}-{r['L']}-{r['P']} {r['units']:+.1f}u"
            fav = record(*fb.grade(test[sel], 2*test.spread_line[sel].to_numpy(float))); row['favorite'] = f"{fav['W']}-{fav['L']}-{fav['P']}"
            by.append(row)
    # production references on the ledger's games
    refs = pd.read_csv(REFS).merge(test[['game_id', 'week', 'total_line']], on='game_id', how='inner')
    prules = {int(r['season']): r for r in json.loads(RULES.read_text())}
    refs['line_through_production'] = np.nan
    for s, r in prules.items():
        k = (refs.season == s).to_numpy()
        if k.any(): refs.loc[k, 'line_through_production'] = fb.apply(refs.loc[k, 'spread_line'], r)
    rp = {'Production median map (model input)': refs.fixed_band_spread.to_numpy(float),
          'Line through production map (ledger control)': refs.line_through_production.to_numpy(float),
          'A, market-only': apply(refs.spread_line, refs.total_line, rules['A']),
          'B, market-only': apply(refs.spread_line, refs.total_line, rules['B'])}
    graded = {k: fb.grade(refs, v) for k, v in rp.items()}
    ref = {'games': int(len(refs)), 'records': {k: record(*v) for k, v in graded.items()}, 'paired_vs_A': {}}
    cl = (refs.season*100+refs.week).to_numpy()
    for k in ('Production median map (model input)', 'Line through production map (ledger control)'):
        du = np.nan_to_num(graded[k][1])-np.nan_to_num(graded['A, market-only'][1]); b = cluster_boot(du, cl)
        ref['paired_vs_A'][k] = {'units': float(du.sum()), 'per_game': float(du.mean()), 'per_game_se': float(b.std(ddof=1)),
                                 'sides_differ': int((fb.pick(rp[k], refs.spread_line) != fb.pick(rp['A, market-only'], refs.spread_line)).sum())}
    info = {'protocol': 'research/MARKET_MEDIAN_MAP.md', 'protocol_commit': PROTOCOL_COMMIT, 'fit_seasons': list(FIT),
            'test_seasons': list(TEST), 'rules': rules, 'results': res, 'by_band_total': by, 'production_references': ref}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=True))
    test.assign(A=preds['A'], B=preds['B']).to_csv(out/'predictions.csv', index=False, float_format='%.6g')
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in
                                                   (Path(__file__), PROTOCOL, ROOT/'fixed_bands.py', GAMES, REFS, RULES)}, indent=2))
    write_report(info, out)
    return info


def write_report(info, out):
    def f(x, fmt='+.2f'): return '–' if x is None or not np.isfinite(x) else format(x, fmt).replace('-', '−')
    def rr(r): return (f"{r['W']}-{r['L']}-{r['P']}" + (f" ({r['skips']} skips)" if r['skips'] else '') +
                       f" | {f(r['units'], '+.1f')} | {f(100*r['roi'])}% ± {f(100*r['roi_se'], '.2f')} | {f(100*r['cover'], '.1f')}% | {r['ats_verdict']}")
    R = info['rules']
    L = ['# Test 51: a market-only median map, fitted on 2022–24 and tested on 2025–26', '',
         f"Protocol: [MARKET_MEDIAN_MAP.md](../MARKET_MEDIAN_MAP.md), pushed (`{info['protocol_commit']}`) before the map was fitted or "
         'scored. No model input. Production and the ledgers are unchanged. Exposed development (see the protocol).', '',
         '## Fitted map (2022–24, ' + f"{R['A']['fit_games']} games)", '',
         '| Band | Fit games | A | B low total | B high total |', '|---|---:|---:|---:|---:|']
    for k, name in enumerate(fb.BANDS):
        L.append(f"| {name} | {R['A']['band_counts'][k]} | {R['A']['magnitudes'][k][0]:g} | {R['B']['magnitudes'][k][0]:g}"
                 f"{'*' if R['B']['fallback'][k][0] else ''} (n={R['B']['cell_counts'][k][0]}) | {R['B']['magnitudes'][k][1]:g}"
                 f"{'*' if R['B']['fallback'][k][1] else ''} (n={R['B']['cell_counts'][k][1]}) |")
    L += ['', f"Total split: {R['B']['total_cuts'][0]:g} (equal counts as low). * = fallback to A.", '',
          '## Point forecast: absolute-error gain over the raw market line (points per game; positive = map better)', '',
          '| Test | Games | MAE line | A: MAE, gain [95%] | B: MAE, gain [95%] |', '|---|---:|---:|---|---|']
    for k, v in info['results'].items():
        a, b = v['point']['A'], v['point']['B']
        L.append(f"| {k} | {v['games']} | {v['mae_line']:.3f} | {a['mae']:.3f}, {f(a['gain'], '+.3f')} [{f(a['ci95'][0], '+.3f')}, {f(a['ci95'][1], '+.3f')}] | "
                 f"{b['mae']:.3f}, {f(b['gain'], '+.3f')} [{f(b['ci95'][0], '+.3f')}, {f(b['ci95'][1], '+.3f')}] |")
    p = info['results']['pooled 2025-26']['point']
    L += ['', f"Point verdict (pooled): A {p['A']['verdict']}; B {p['B']['verdict']}.", '',
          '## ATS at −110 (W-L-P | units | ROI ± SE | cover | verdict)', '']
    for k, v in info['results'].items():
        L += [f'**{k}** ({v["games"]} games)', '', '| Arm | Record |', '|---|---|']
        for a, r in v['ats'].items():
            extra = f" (underdog share {100*r['dog_share']:.0f}%)" if 'dog_share' in r else ''
            L.append(f'| {a}{extra} | {rr(r)} |')
        L.append('')
    pr = info['production_references']
    L += [f"## References on the ledger's {pr['games']} test games (production tie rule)", '', '| Arm | Record |', '|---|---|']
    for k, r in pr['records'].items(): L.append(f'| {k} | {rr(r)} |')
    for k, v in pr['paired_vs_A'].items():
        L.append(f"| {k} minus A | {f(v['units'], '+.1f')}u, {f(v['per_game'], '+.4f')} ± {f(v['per_game_se'], '.4f')} per game; sides differ on {v['sides_differ']} |")
    L += ['', '## By band and total half, pooled 2025–26 (descriptive; production tie rule)', '',
          '| Band | Total | Games | A | B | Always favorite |', '|---|---|---:|---|---|---|']
    for r in info['by_band_total']: L.append(f"| {r['band']} | {r['total']} | {r['games']} | {r['A']} | {r['B']} | {r['favorite']} |")
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--freeze', metavar='GAMES_CSV', help='freeze inputs from the nflverse games file')
    a = ap.parse_args()
    if a.freeze: freeze(a.freeze)
    else: run()
