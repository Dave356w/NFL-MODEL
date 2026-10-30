#!/usr/bin/env python3
"""Pace x efficiency totals (O/U) model, walk-forward. Protocol: research/TOTALS_PACE.md.

Research only: reads nflverse schedules and team-week stats, writes
research/totals_pace_results/. Nothing here touches nfl_model.py, data/ or the pages.
"""
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research' / 'totals_pace_results'
CACHE = ROOT / '.nfl_cache' / 'totals_pace'   # raw downloads, git-ignored
GAMES_URL = 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv'
STATS_URL = 'https://github.com/nflverse/nflverse-data/releases/download/stats_team/stats_team_week_{}.parquet'
FIRST, PRIOR0, LAST = 2006, 2005, 2025
GRID_SEASONS, EVAL = range(2009, 2017), range(2017, 2026)   # grid: walk-forward 2009-16 (first fit on 2008)
FIT_FIRST = 2008
REGRESS, EARLY = 0.40, 4
FRANCHISE = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'}
BOOT, RNG = 2000, np.random.default_rng(20261030)


def fetch():
    CACHE.mkdir(parents=True, exist_ok=True)
    gp = CACHE / 'games.csv'
    if not gp.exists():
        pd.read_csv(GAMES_URL).to_csv(gp, index=False)
    g = pd.read_csv(gp)
    g = g[(g.game_type == 'REG') & g.season.between(PRIOR0, LAST) & g.result.notna()].copy()
    st = []
    for y in range(PRIOR0, LAST + 1):
        sp = CACHE / f'stats_team_week_{y}.csv'
        if not sp.exists():
            pd.read_parquet(STATS_URL.format(y)).to_csv(sp, index=False)
        st.append(pd.read_csv(sp))
    s = pd.concat(st, ignore_index=True)
    s = s[s.season_type == 'REG'].copy()
    sacks = 'sacks_suffered' if 'sacks_suffered' in s else 'sacks'
    s['plays'] = s.attempts + s[sacks] + s.carries
    for c in ('home_team', 'away_team'):
        g[c] = g[c].replace(FRANCHISE)
    s['team'] = s.team.replace(FRANCHISE)
    return g, s[['season', 'week', 'team', 'plays']]


def team_games(g, s):
    """Two rows per game: the team's points/plays and its opponent's."""
    rows = []
    for side, opp in (('home', 'away'), ('away', 'home')):
        rows.append(pd.DataFrame({'game_id': g.game_id, 'season': g.season, 'week': g.week,
                                  'team': g[f'{side}_team'], 'opp': g[f'{opp}_team'],
                                  'pts': g[f'{side}_score'], 'opp_pts': g[f'{opp}_score']}))
    t = pd.concat(rows, ignore_index=True)
    t = t.merge(s, on=['season', 'week', 'team'], how='left')
    t = t.merge(s.rename(columns={'team': 'opp', 'plays': 'opp_plays'}), on=['season', 'week', 'opp'], how='left')
    t['ppp'] = t.pts / t.plays
    t['opp_ppp'] = t.opp_pts / t.opp_plays
    return t.sort_values(['team', 'season', 'week']).reset_index(drop=True)


STATS = {'pf': 'pts', 'pa': 'opp_pts', 'plays': 'plays', 'plays_a': 'opp_plays', 'ppp': 'ppp', 'ppp_a': 'opp_ppp'}


def pregame_rates(t, h, K):
    """Decayed means from strictly earlier games this season, prior = last season regressed."""
    season_mean = t.groupby(['team', 'season'])[list(STATS.values())].mean()
    league_mean = t.groupby('season')[list(STATS.values())].mean()
    out = []
    for (team, season), d in t.groupby(['team', 'season'], sort=False):
        lg = league_mean.loc[season - 1] if season - 1 in league_mean.index else league_mean.loc[season]
        prior = {}
        for k, c in STATS.items():
            last = season_mean[c].get((team, season - 1), np.nan)
            prior[k] = lg[c] if pd.isna(last) else (1 - REGRESS) * last + REGRESS * lg[c]
        n = len(d)
        age = np.arange(n)[:, None] - np.arange(n)[None, :] - 1          # games between j and i, minus one
        w = np.where(age >= 0, 0.5 ** (age / h), 0.)
        r = {'game_id': d.game_id.to_numpy(), 'team': team, 'gp': np.arange(n)}
        for k, c in STATS.items():
            x = d[c].to_numpy(float)
            ok = np.isfinite(x)
            ww = w * ok[None, :]
            r[k] = (K * prior[k] + ww @ np.nan_to_num(x)) / (K + ww.sum(1))
        pts = d.pts.to_numpy(float)
        last3 = [pts[max(0, i - 3):i].mean() if i else np.nan for i in range(n)]
        r['form'] = np.nan_to_num(np.array(last3) - r['pf'])
        out.append(pd.DataFrame(r))
    return pd.concat(out, ignore_index=True)


def league_to_date(t, L):
    """League per-team points, plays and points per play over completed weeks before each week."""
    wk = t.groupby(['season', 'week']).agg(pts=('pts', 'sum'), plays=('plays', 'sum'), n=('pts', 'size'))
    rows = []
    for season, d in wk.groupby(level=0):
        prev = wk.loc[season - 1] if season - 1 in wk.index.get_level_values(0) else d.loc[season]
        p_pts, p_plays = prev.pts.sum() / prev.n.sum(), prev.plays.sum() / prev.n.sum()
        cp, cl, cn = 0., 0., 0.
        for (_, week), r in d.iterrows():
            pts = (L * p_pts + cp) / (L + cn)
            plays = (L * p_plays + cl) / (L + cn)
            rows.append({'season': season, 'week': week, 'lg_pts': pts, 'lg_plays': plays, 'lg_ppp': pts / plays})
            cp, cl, cn = cp + r.pts, cl + r.plays, cn + r.n
    return pd.DataFrame(rows)


def features(g, t, h, K, L):
    r = pregame_rates(t, h, K)
    lg = league_to_date(t, L)
    f = g[['game_id', 'season', 'week', 'home_team', 'away_team', 'home_score', 'away_score', 'total_line',
           'over_odds', 'under_odds', 'roof', 'home_rest', 'away_rest', 'div_game']].merge(lg, on=['season', 'week'])
    for side in ('home', 'away'):
        rr = r.rename(columns={c: f'{side}_{c}' for c in r.columns if c != 'game_id'})
        f = f.merge(rr, left_on=['game_id', f'{side}_team'], right_on=['game_id', f'{side}_team'])
    f['total'] = f.home_score + f.away_score
    f['league'] = 2 * f.lg_pts
    n_pace = 0.
    for x, y in (('home', 'away'), ('away', 'home')):
        plays = f[f'{x}_plays'] + f[f'{y}_plays_a'] - f.lg_plays
        ppp = f[f'{x}_ppp'] + f[f'{y}_ppp_a'] - f.lg_ppp
        n_pace = n_pace + plays * ppp
    f['n_pace'] = n_pace - f.league
    f['n_pts'] = f.home_pf + f.away_pa + f.away_pf + f.home_pa - 2 * f.league
    f['phase'] = np.clip((f.home_gp + f.away_gp) / 2, 0, 8)
    roof = f.roof.astype(str).str.lower()
    f['dome'] = (roof == 'dome').astype(float)
    f['retract'] = roof.isin(['open', 'closed']).astype(float)
    rest = f[['home_rest', 'away_rest']]
    f['short'] = (rest <= 4).sum(axis=1).astype(float)
    f['bye'] = (rest >= 10).sum(axis=1).astype(float)
    f['div'] = f.div_game.fillna(0).astype(float)
    f['form'] = f.home_form + f.away_form
    f['stage'] = np.where(np.minimum(f.home_gp, f.away_gp) < EARLY, 'E', 'M')
    return f[f.season >= FIRST].reset_index(drop=True)


ARMS = {'P0': ['n_pts', 'phase'], 'T0': ['n_pace', 'phase'],
        'T1': ['n_pace', 'phase', 'dome', 'retract', 'short', 'bye', 'div', 'form']}


def walk_forward(f, arm, seasons):
    cols, parts, fits = ARMS[arm], [], {}
    for y in seasons:
        tr, te = f[f.season.between(FIT_FIRST, y - 1)], f[f.season == y].copy()
        X = np.column_stack([np.ones(len(tr)), tr[cols].to_numpy(float)])
        beta = np.linalg.lstsq(X, (tr.total - tr.league).to_numpy(float), rcond=None)[0]
        res = tr.total - tr.league - X @ beta
        sig = {st: float(res[tr.stage == st].std()) for st in ('E', 'M')}
        Xt = np.column_stack([np.ones(len(te)), te[cols].to_numpy(float)])
        te['T'] = te.league + Xt @ beta
        te['sigma'] = te.stage.map(sig)
        parts.append(te)
        fits[y] = dict(zip(['a', *cols], np.round(beta, 3).tolist())) | {'sigma': sig}
    return pd.concat(parts, ignore_index=True), fits


def decimal(a):
    return np.where(a > 0, 1 + a / 100, 1 + 100 / np.abs(a))


def market(d):
    io, iu = 1 / decimal(d.over_odds), 1 / decimal(d.under_odds)
    d = d.copy()
    d['q'] = io / (io + iu)
    d['P'] = 1 - ndtr((d.total_line - d['T']) / d.sigma)
    d['push'] = d.total == d.total_line
    d['over'] = (d.total > d.total_line).astype(float)
    return d


def clusters(d):
    return d.groupby(['season', 'week']).ngroup().to_numpy()


def boot(d, stat):
    """Point estimate and 95% week-cluster bootstrap interval of stat(d)."""
    cid = clusters(d)
    groups = [np.flatnonzero(cid == c) for c in range(cid.max() + 1)]
    est, draws = stat(d), []
    for _ in range(BOOT):
        pick = RNG.integers(0, len(groups), len(groups))
        draws.append(stat(d.iloc[np.concatenate([groups[i] for i in pick])]))
    lo, hi = np.nanpercentile(draws, [2.5, 97.5])
    return est, lo, hi


def fmt(e, lo, hi, p=4):
    return f'{e:+.{p}f} [{lo:+.{p}f}, {hi:+.{p}f}]'


def ll(y, p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def bets(d, gap=0.0):
    d = d[(d.P - d.q).abs() >= gap].copy()
    over = d.P > d.q
    odds = np.where(over, d.over_odds, d.under_odds)
    pfair = np.where(over, d.q, 1 - d.q)
    win = np.where(over, d.total > d.total_line, d.total < d.total_line)
    d['pnl'] = np.where(d.push, 0., np.where(win, decimal(odds) - 1, -1.))
    d['null'] = pfair * (decimal(odds) - 1) - (1 - pfair)    # expected ROI if the no-vig price is right
    return d


def market_lines(d, out):
    d = d.dropna(subset=['total_line', 'over_odds', 'under_odds'])
    d = market(d)
    se = lambda x: ((x.total - x['T']) ** 2).mean() - ((x.total - x.total_line) ** 2).mean()
    rm = lambda c: np.sqrt(((d.total - d[c]) ** 2).mean())
    out.append(f'    n {len(d):5d}  RMSE line {rm("total_line"):.3f} model {rm("T"):.3f}   '
               f'model − line sq err {fmt(*boot(d, se), 2)}')

    def wfit(x):
        u = (x['T'] - x.total_line).to_numpy()
        return float(u @ (x.total - x.total_line).to_numpy() / (u @ u))
    out.append(f'    weight on (T − line) {fmt(*boot(d, wfit), 3)}')
    n = d[~d.push]
    gain = lambda x: float((ll(x.over, x.q) - ll(x.over, x.P)).mean())
    out.append(f'    P(over) LL model {ll(n.over, n.P).mean():.4f} market {ll(n.over, n.q).mean():.4f}  '
               f'gain {fmt(*boot(n, gain))}  (pushes {int(d.push.sum())} excluded)')
    for gap, lab in ((0., 'all'), (0.05, '|P − q| ≥ 0.05')):
        b = bets(d, gap)
        if len(b) == 0:
            continue
        roi = lambda x: 100 * float(x.pnl.mean())
        e, lo, hi = boot(b, roi)
        nov = int((b.P > b.q).sum())
        out.append(f'    model side, {lab:<16} n {len(b):5d} ({nov} over / {len(b) - nov} under)  '
                   f'ROI {e:+6.1f}% [{lo:+.1f}, {hi:+.1f}]  null {100 * b.null.mean():+.1f}%  '
                   f'won {100 * float((b.pnl > 0).sum() / max(1, (~b.push).sum())):.1f}%')
    return d


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    g, s = fetch()
    t = team_games(g, s)
    miss = int(t.plays.isna().sum())
    out = ['Pace x efficiency totals (O/U) model, walk-forward (research/totals_pace.py). ± 95% week-cluster bootstrap.',
           'Protocol: research/TOTALS_PACE.md (committed before this run). Historical, exposed; quotes have no capture time.',
           f'Team-games without a plays count: {miss} (their rates skip that game).', '']
    scores = {}
    for h, K, L in itertools.product((4, 8, 16), (4, 8), (16, 64)):
        f = features(g, t, h, K, L)
        p, _ = walk_forward(f, 'T0', GRID_SEASONS)
        scores[(h, K, L)] = float(np.sqrt(((p.total - p['T']) ** 2).mean()))
    best = min(scores, key=scores.get)
    out.append('Grid (half-life h, prior weight K, league prior L) on 2009–2016 walk-forward T0 RMSE: '
               + ', '.join(f'{k}: {v:.3f}' for k, v in sorted(scores.items())))
    out.append(f'Chosen (h, K, L) = {best}; fixed for every arm and every evaluation season.')
    f = features(g, t, *best)
    preds = {}
    for arm in ARMS:
        preds[arm], fits = walk_forward(f, arm, EVAL)
        if arm == 'T1':
            out.append(f'T1 last fit (2025): {json.dumps(fits[2025])}')
    out += ['', '== 1. Against outcomes, 2017–2025 (stages never pooled)']
    for st in ('M', 'E'):
        for arm, p in preds.items():
            d = p[p.stage == st]
            line = d.dropna(subset=['total_line'])
            out.append(f'  stage {st} {arm}  n {len(d):5d}  RMSE {np.sqrt(((d.total - d["T"]) ** 2).mean()):.3f}  '
                       f'line {np.sqrt(((line.total - line.total_line) ** 2).mean()):.3f}  '
                       f'mean T − total {float((d["T"] - d.total).mean()):+.2f}')
    out += ['', '== 2. Against the schedule total (2017–2025 and by season; stages never pooled)']
    for arm in ('T0', 'T1', 'P0'):
        for st in ('M', 'E'):
            d = preds[arm][preds[arm].stage == st]
            out.append(f'  {arm} stage {st}, 2017–2025')
            market_lines(d, out)
    out += ['', '== 3. T1 stage M by season']
    for y in EVAL:
        d = preds['T1'][(preds['T1'].stage == 'M') & (preds['T1'].season == y)]
        out.append(f'  {y}')
        market_lines(d, out)
    out += ['', '== 4. T1 stage M by posted total and model side (descriptive, not filters)']
    d = market(preds['T1'][preds['T1'].stage == 'M'].dropna(subset=['total_line', 'over_odds', 'under_odds']))
    b = bets(d)
    groups = {'< 41': b.total_line < 41, '41–44.5': b.total_line.between(41, 44.5),
              '45–47.5': b.total_line.between(45, 47.5), '≥ 48': b.total_line >= 48,
              'model over': b.P > b.q, 'model under': b.P <= b.q}
    for lab, m in groups.items():
        x = b[m]
        out.append(f'  {lab:<12} n {len(x):5d}  overs hit {100 * x.over[~x.push].mean():.1f}% (market {100 * x.q.mean():.1f}%)  '
                   f'model − line {float((x["T"] - x.total_line).mean()):+.2f}  ROI {100 * x.pnl.mean():+.1f}%  '
                   f'null {100 * x.null.mean():+.1f}%')
    text = '\n'.join(out) + '\n'
    (OUT / 'RESULTS.txt').write_text(text, encoding='utf-8')
    pd.concat([p.assign(arm=a) for a, p in preds.items()])[
        ['arm', 'game_id', 'season', 'week', 'stage', 'total', 'total_line', 'over_odds', 'under_odds', 'T', 'sigma']
    ].to_csv(OUT / 'predictions.csv.gz', index=False)
    print(text)


if __name__ == '__main__':
    main()
