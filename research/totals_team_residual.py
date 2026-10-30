#!/usr/bin/env python3
"""Addendum C of research/TOTALS_PACE.md: per-team residuals against the market's
implied points, used to adjust the posted O/U.

Research only: reuses research/totals_pace.py and writes
research/totals_pace_results/TEAM_RESIDUAL.txt. Nothing touches data/ or the pages.
"""
import itertools

import numpy as np
import pandas as pd

import totals_pace as tp

tp.LAST = 2026                       # 2026 to date is shown apart, never in the verdict
GRID_SEASONS, EVAL, NOW = range(2009, 2017), range(2017, 2026), 2026
FIT_FIRST, CARRY = 2008, 0.5


def residual_games(g):
    """Two rows per game: offense residual o (points - own implied) and
    defense residual d (points allowed - opponent's implied)."""
    imp_h = (g.total_line + g.spread_line) / 2
    imp_a = (g.total_line - g.spread_line) / 2
    rows = []
    for team, opp, pts, opp_pts, own, other in (
            ('home_team', 'away_team', 'home_score', 'away_score', imp_h, imp_a),
            ('away_team', 'home_team', 'away_score', 'home_score', imp_a, imp_h)):
        rows.append(pd.DataFrame({'game_id': g.game_id, 'season': g.season, 'week': g.week, 'team': g[team],
                                  'o': g[pts] - own, 'd': g[opp_pts] - other}))
    return pd.concat(rows, ignore_index=True).sort_values(['team', 'season', 'week']).reset_index(drop=True)


def pregame(r, h, K, carry):
    """Decayed earlier-game mean this season, shrunk to a prior with weight K.
    Prior = 0, or (carry) last season's mean regressed 50%."""
    last = r.groupby(['team', 'season'])[['o', 'd']].mean()
    out = []
    for (team, season), d in r.groupby(['team', 'season'], sort=False):
        n = len(d)
        age = np.arange(n)[:, None] - np.arange(n)[None, :] - 1
        w = np.where(age >= 0, 0.5 ** (age / h), 0.)
        row = {'game_id': d.game_id.to_numpy(), 'team': team}
        for c in ('o', 'd'):
            prior = 0.
            if carry and (team, season - 1) in last.index:
                prior = (1 - CARRY) * float(last.at[(team, season - 1), c])
            x = np.nan_to_num(d[c].to_numpy(float))
            row[c] = (K * prior + w @ x) / (K + w.sum(1))
        out.append(pd.DataFrame(row))
    return pd.concat(out, ignore_index=True)


def signal(f, r, h, K, carry):
    p = pregame(r, h, K, carry)
    f = f.copy()
    for side in ('home', 'away'):
        f = f.merge(p.rename(columns={'team': f'{side}_team', 'o': f'{side}_o', 'd': f'{side}_d'}),
                    on=['game_id', f'{side}_team'], how='left')
    f['R'] = f.home_o + f.away_d + f.away_o + f.home_d
    return f


def adjust(f, seasons, first=FIT_FIRST):
    parts, ks = [], {}
    for y in seasons:
        tr, te = f[f.season.between(first, y - 1)], f[f.season == y].copy()
        u, v = tr.R.to_numpy(), (tr.total - tr.total_line).to_numpy()
        k = float(u @ v / (u @ u))
        res = v - k * u
        sig = {st: float(res[(tr.stage == st).to_numpy()].std()) for st in ('E', 'M')}
        te['T'] = te.total_line + k * te.R
        te['sigma'] = te.stage.map(sig)
        parts.append(te)
        ks[y] = round(k, 3)
    return pd.concat(parts, ignore_index=True), ks


def main():
    g, s = tp.fetch()
    t = tp.team_games(g, s)
    f = tp.features(g, t, 16, 8, 64)[lambda x: x.total_line.notna()]
    sp = g[['game_id', 'spread_line']]
    f = f.merge(sp, on='game_id', how='left')
    r = residual_games(g[g.total_line.notna() & g.spread_line.notna()])
    out = ['Addendum C: per-team residuals vs market implied points (research/totals_team_residual.py). ± 95% week-cluster bootstrap.',
           'Protocol: research/TOTALS_PACE.md, Addendum C (committed before this run). Schedule quotes, no capture time.', '']
    for arm, carry in (('C1 within-season', False), ('C2 carry last season 50%', True)):
        scores = {}
        for h, K in itertools.product((4, 8, 16), (2, 4, 8)):
            fs = signal(f, r, h, K, carry)
            p, _ = adjust(fs, GRID_SEASONS)
            scores[(h, K)] = float(np.sqrt(((p.total - p['T']) ** 2).mean()))
        best = min(scores, key=scores.get)
        line_rmse = float(np.sqrt(((p.total - p.total_line) ** 2).mean()))
        out.append(f'===== {arm}')
        out.append(f'  grid (h, K) 2009–2016 RMSE (line {line_rmse:.3f}): '
                   + ', '.join(f'{k}: {v:.3f}' for k, v in sorted(scores.items())) + f'  → chosen {best}')
        fs = signal(f, r, *best, carry)
        p, ks = adjust(fs, [*EVAL, NOW])
        out.append(f'  k by evaluation season: {ks}')
        out.append(f'  sd of R (2017–2025): {p[p.season < NOW].R.std():.2f} pts')
        for label, seasons in (('2017–2025', EVAL), ('2026 to date (current-season diagnostic, not a verdict)', [NOW])):
            for st in ('M', 'E'):
                d = p[p.season.isin(list(seasons)) & (p.stage == st)]
                out.append(f'  stage {st}, {label}')
                tp.market_lines(d, out)
        if not carry:
            out.append('  == C1 stage M by season')
            for y in EVAL:
                out.append(f'    {y}')
                tp.market_lines(p[(p.season == y) & (p.stage == 'M')], out)
        out.append('')
    text = '\n'.join(out) + '\n'
    (tp.OUT / 'TEAM_RESIDUAL.txt').write_text(text, encoding='utf-8')
    print(text)


if __name__ == '__main__':
    main()
