#!/usr/bin/env python3
"""Addendum B of research/TOTALS_PACE.md: median bands (absolute or era-relative)
plus a residual model fitted on top of the band median.

Research only: reuses research/totals_pace.py and totals_median.py and writes
research/totals_pace_results/MEDIAN_RESIDUAL.txt. Nothing touches data/ or the pages.
"""
import numpy as np
import pandas as pd

import totals_pace as tp
import totals_median as tm

tp.LAST = 2026                       # 2026 to date is shown apart, never in the verdict
REL_EDGES = list(range(-8, 9, 2))
FIRST_TRAIN, EVAL, NOW = 2009, range(2017, 2026), 2026
RESID = ['dep', 'drift', 'dome', 'retract', 'short', 'bye', 'div', 'form', 'phase']


def bands(d, kind):
    x = d.total_line if kind == 'A' else d.total_line - d.league
    return np.searchsorted(tm.EDGES if kind == 'A' else REL_EDGES, np.asarray(x, float), side='right')


def season_medians(p, kind):
    """m for every game from priced games of earlier seasons only (2006 .. s-1)."""
    p = p.copy()
    p['band'] = bands(p, kind)
    nb = (len(tm.EDGES) if kind == 'A' else len(REL_EDGES)) + 1
    p['m'] = np.nan
    for s in sorted(p.season.unique()):
        hist = p[p.season < s]
        if hist.empty:
            continue
        d = (hist.total - hist.total_line).to_numpy()
        med = np.array([np.median(d[hist.band == k]) if (hist.band == k).any() else 0. for k in range(nb)])
        cur = p.season == s
        p.loc[cur, 'm'] = p.loc[cur, 'total_line'] + med[p.loc[cur, 'band'].to_numpy()]
    return p


def residual(p, seasons):
    p = p.dropna(subset=['m']).copy()
    p['dep'] = p['T'] - p.m
    p['drift'] = p.league - p.total_line
    parts, fits = [], {}
    for y in seasons:
        tr, te = p[p.season.between(FIRST_TRAIN, y - 1)], p[p.season == y].copy()
        X = np.column_stack([np.ones(len(tr)), tr[RESID].to_numpy(float)])
        beta = np.linalg.lstsq(X, (tr.total - tr.m).to_numpy(float), rcond=None)[0]
        res = tr.total - tr.m - X @ beta
        sig = {st: float(res[tr.stage == st].std()) for st in ('E', 'M')}
        te['T'] = te.m + np.column_stack([np.ones(len(te)), te[RESID].to_numpy(float)]) @ beta
        te['sigma'] = te.stage.map(sig)
        parts.append(te)
        fits[y] = dict(zip(['a', *RESID], np.round(beta, 3).tolist())) | {'sigma': {k: round(v, 2) for k, v in sig.items()}}
    return pd.concat(parts, ignore_index=True), fits


def main():
    g, s = tp.fetch()
    t = tp.team_games(g, s)
    f = tp.features(g, t, 16, 8, 64)                 # the registered grid choice
    p, _ = tp.walk_forward(f, 'T1', range(FIRST_TRAIN, NOW + 1))
    early = f[f.season < FIRST_TRAIN].assign(T=np.nan, sigma=np.nan)    # median history only
    p = pd.concat([early, p], ignore_index=True).dropna(subset=['total_line'])
    out = ['Addendum B: median bands with residual adjustments (research/totals_residual.py). ± 95% week-cluster bootstrap.',
           'Protocol: research/TOTALS_PACE.md, Addendum B (committed before this run). Schedule quotes, no capture time.', '']
    for kind, name in (('A', 'BA absolute bands + residual'), ('R', 'BR era-relative bands + residual')):
        pm = season_medians(p, kind)
        r, fits = residual(pm[pm.season >= FIRST_TRAIN], [*EVAL, NOW])
        out.append(f'===== {name}')
        for y in (2017, 2025, 2026):
            out.append(f'  fit for {y}: {fits[y]}')
        for label, seasons in (('2017–2025', EVAL), ('2026 to date (current-season diagnostic, not a verdict)', [NOW])):
            for st in ('M', 'E'):
                d = r[r.season.isin(list(seasons)) & (r.stage == st)]
                out.append(f'  {kind} stage {st}, {label}')
                tp.market_lines(d, out)
                if kind == 'R':
                    tm.m1(d, out)
                    out[-1] = out[-1].replace('M1 median sign', 'MR era-rel. median sign')
        out.append('')
        if kind == 'R':
            out.append('== BR stage M by season')
            for y in EVAL:
                out.append(f'  {y}')
                tp.market_lines(r[(r.season == y) & (r.stage == 'M')], out)
    text = '\n'.join(out) + '\n'
    (tp.OUT / 'MEDIAN_RESIDUAL.txt').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
