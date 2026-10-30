#!/usr/bin/env python3
"""Addendum A of research/TOTALS_PACE.md: shrink the totals model toward the
market-context median final total of its posted O/U band.

Research only: reuses research/totals_pace.py and writes
research/totals_pace_results/MEDIAN_SHRINK.txt. Nothing touches data/ or the pages.
"""
import numpy as np
import pandas as pd

import totals_pace as tp

tp.LAST = 2026                       # 2026 to date is shown apart, never in the verdict
EDGES = [36, 38, 40, 42, 44, 46, 48, 50, 52, 54]
OOF_FIRST, EVAL, NOW = 2009, range(2017, 2026), 2026


def band(line):
    return np.searchsorted(EDGES, np.asarray(line, float), side='right')


def medians(hist):
    """Median (final - line) per band from earlier priced games; bands without games give 0."""
    b = band(hist.total_line)
    d = (hist.total - hist.total_line).to_numpy()
    return np.array([np.median(d[b == k]) if (b == k).any() else 0. for k in range(len(EDGES) + 1)])


def shrink(p, seasons):
    """S1 for each season: T_s = m + w (T - m), with m, w and sigma from earlier seasons only."""
    p = p.dropna(subset=['total_line']).copy()
    parts, info = [], {}
    for y in seasons:
        tr, te = p[p.season < y].copy(), p[p.season == y].copy()
        med = medians(tr)
        for x in (tr, te):
            x['m'] = x.total_line + med[band(x.total_line)]
        u, v = (tr['T'] - tr.m).to_numpy(), (tr.total - tr.m).to_numpy()
        w = float(np.clip(u @ v / (u @ u), 0, 1))
        tr['Ts'] = tr.m + w * (tr['T'] - tr.m)
        sig = {st: float((tr.total - tr.Ts)[tr.stage == st].std()) for st in ('E', 'M')}
        te['T_model'], te['T'] = te['T'], te.m + w * (te['T'] - te.m)
        te['sigma'] = te.stage.map(sig)
        parts.append(te)
        info[y] = {'w': round(w, 3), 'median (final − line) by band': med.round(1).tolist(),
                   'sigma': {k: round(s, 2) for k, s in sig.items()}}
    return pd.concat(parts, ignore_index=True), info


def m1(d, out):
    """M1: bet the sign of (m - line); zero skips."""
    d = tp.market(d.dropna(subset=['over_odds', 'under_odds']))
    gap = d.m - d.total_line
    d = d[gap != 0].copy()
    over = (d.m > d.total_line).to_numpy()
    odds = np.where(over, d.over_odds, d.under_odds)
    pfair = np.where(over, d.q, 1 - d.q)
    win = np.where(over, d.total > d.total_line, d.total < d.total_line)
    d['pnl'] = np.where(d.push, 0., np.where(win, tp.decimal(odds) - 1, -1.))
    null = float(np.mean(pfair * (tp.decimal(odds) - 1) - (1 - pfair)))
    if len(d) == 0:
        out.append('    M1 median sign: no bets')
        return
    e, lo, hi = tp.boot(d, lambda x: 100 * float(x.pnl.mean()))
    w, l = int((d.pnl > 0).sum()), int((d.pnl < 0).sum())
    out.append(f'    M1 median sign   n {len(d):5d} ({int(over.sum())} over / {int((~over).sum())} under)  '
               f'{w}-{l}-{len(d) - w - l}  ROI {e:+6.1f}% [{lo:+.1f}, {hi:+.1f}]  null {100 * null:+.1f}%')


def main():
    g, s = tp.fetch()
    t = tp.team_games(g, s)
    f = tp.features(g, t, 16, 8, 64)                 # the registered grid choice
    out = ['Addendum A: model shrunk toward the market-context median (research/totals_median.py). ± 95% week-cluster bootstrap.',
           'Protocol: research/TOTALS_PACE.md, Addendum A (committed before this run). Schedule quotes, no capture time.', '']
    shrunk = {}
    for arm in ('T1', 'T0'):
        p, _ = tp.walk_forward(f, arm, range(OOF_FIRST, NOW + 1))
        sh, info = shrunk[arm] = shrink(p, [*EVAL, NOW])
        out.append(f'===== {arm} shrunk (S1) and median alone (M1)')
        for y in (2017, 2021, 2025, 2026):
            out.append(f'  fit for {y}: {info[y]}')
        for label, seasons in (('2017–2025', EVAL), ('2026 to date (current-season diagnostic, not a verdict)', [NOW])):
            for st in ('M', 'E'):
                d = sh[sh.season.isin(list(seasons)) & (sh.stage == st)]
                out.append(f'  {arm} S1 stage {st}, {label}')
                tp.market_lines(d, out)
                m1(d, out)
        out.append('')
    sh = shrunk['T1'][0]
    out.append('== T1 S1 stage M by season')
    for y in EVAL:
        out.append(f'  {y}')
        tp.market_lines(sh[(sh.season == y) & (sh.stage == 'M')], out)
    text = '\n'.join(out) + '\n'
    (tp.OUT / 'MEDIAN_SHRINK.txt').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
