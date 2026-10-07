"""Test 19: does the closing moneyline misprice a team's in-season situation?

    python research/team_situations.py [CACHE_DIR]     # ~10 s (schedules only)

Team-game rows 2010-2025 (each priced, decided game counted once per team; a game
where both teams share a situation cancels). Target: the team's result minus its
no-vig closing-moneyline probability. Every situation uses only the team's EARLIER
games that season, plus its published schedule (next opponent):

  form       last game won/lost by 17+; win or losing streak of 3+
  market     beat its price last game (actual - implied > 0); season-to-date
             actual - implied (does the market under- or over-react?)
  schedule   next opponent strong (win% >= .600 so far, 3+ games): look-ahead;
             sandwich (previous and next opponents strong, this one not);
             division rematch after losing the first meeting (revenge)

Read |z| < ~2.9 as noise (about 12 situations tested).
"""
import math

import numpy as np
import pandas as pd

from _common import cache_dir_from_argv, log, m

FIRST, LAST = 2010, 2025


def team_rows(sched):
    s = sched[(sched.season >= FIRST) & (sched.season <= LAST)].copy()
    s['q'] = m.market_ml_wp(s)
    rows = []
    for r in s.itertuples(index=False):
        for team, opp, side in ((r.home_team, r.away_team, 'home'), (r.away_team, r.home_team, 'away')):
            sign = 1 if side == 'home' else -1
            res = getattr(r, 'result')
            q = r.q if side == 'home' else 1 - r.q
            price = r.home_moneyline if side == 'home' else r.away_moneyline
            rows.append({'game_id': r.game_id, 'season': r.season, 'week': r.week, 'team': team, 'opp': opp,
                         'div': r.div_game, 'margin': sign * res if pd.notna(res) else np.nan,
                         'won': (1. if sign * res > 0 else 0. if sign * res < 0 else .5) if pd.notna(res) else np.nan,
                         'q': q, 'price': price})
    return pd.DataFrame(rows).sort_values(['team', 'season', 'week']).reset_index(drop=True)


def situations(t):
    t = t.copy()
    t['res'] = t.won - t.q
    g = t.groupby(['team', 'season'], sort=False)
    t['last_margin'] = g.margin.shift(1)
    t['last_res'] = g.res.shift(1)
    t['res_to_date'] = g.res.transform(lambda x: x.shift(1).expanding().mean())
    t['games_before'] = g.cumcount()

    def streak(won):
        out, cur = [], 0
        for w in won:
            out.append(cur)  # streak entering this game
            cur = (cur + 1 if cur > 0 else 1) if w == 1 else (cur - 1 if cur < 0 else -1) if w == 0 else 0
        return out
    t['streak'] = g.won.transform(lambda x: pd.Series(streak(list(x)), index=x.index))
    # win% so far for every team-week (for opponent strength)
    t['wins_before'] = g.won.transform(lambda x: x.shift(1).fillna(0).cumsum())
    t['wpct'] = np.where(t.games_before >= 3, t.wins_before / t.games_before.where(t.games_before > 0), np.nan)
    key = t.set_index(['team', 'season', 'week']).wpct
    t['opp_wpct'] = [key.get((o, s, w), np.nan) for o, s, w in zip(t.opp, t.season, t.week)]
    # next opponent's win% as of THIS week (its result this week is not known yet; NaN if it is on a bye)
    t['next_opp_wpct'] = [key.get((o, s, w), np.nan) if isinstance(o, str) else np.nan
                          for o, s, w in zip(g.opp.shift(-1), t.season, t.week)]
    t['prev_opp_wpct'] = g.opp_wpct.shift(1)
    first_meet = {}
    revenge = []
    for r in t.itertuples(index=False):
        k = (r.team, r.opp, r.season)
        revenge.append(float(bool(r.div) and first_meet.get(k) == 0.))
        if k not in first_meet and pd.notna(r.won):
            first_meet[k] = r.won
    t['revenge'] = revenge
    return t


def summarize(t, mask, label):
    g = t[mask & t.won.isin([0., 1.]) & np.isfinite(t.q)]
    n = len(g)
    if n < 20:
        return f'| {label} | {n} | – | – | – |'
    units = np.where(g.won == 1, np.where(g.price > 0, g.price / 100, 100 / -g.price), -1.)
    null = (g.q * np.where(g.price > 0, g.price / 100, 100 / -g.price) - (1 - g.q)).mean()
    se = g.res.std(ddof=1) / math.sqrt(n)
    return (f'| {label} | {n} | {100 * g.res.mean():+.1f} pts ± {100 * se:.1f} | {g.res.mean() / se:+.1f} | '
            f'{100 * units.mean():+.1f}% ± {100 * units.std(ddof=1) / math.sqrt(n):.1f} (null {100 * null:+.1f}%) |')


def main():
    m.CACHE_DIR = str(cache_dir_from_argv())
    sched = pd.concat([m.load_schedule(y) for y in range(FIRST, LAST + 1)], ignore_index=True)
    t = situations(team_rows(sched))
    log(f'{int(t.won.isin([0., 1.]).sum())} decided team-games')
    strong = .600
    rows = [
        ('Won last game by 17+', t.last_margin >= 17), ('Lost last game by 17+', t.last_margin <= -17),
        ('Win streak 3+', t.streak >= 3), ('Losing streak 3+', t.streak <= -3),
        ('Beat its price last game', t.last_res > 0), ('Missed its price last game', t.last_res < 0),
        ('Season to date: beat price by 10+ pts (3+ games)', (t.res_to_date >= .10) & (t.games_before >= 3)),
        ('Season to date: missed price by 10+ pts (3+ games)', (t.res_to_date <= -.10) & (t.games_before >= 3)),
        ('Look-ahead: next opponent strong, this one not', (t.next_opp_wpct >= strong) & (t.opp_wpct < .5)),
        ('Sandwich: previous and next strong, this one not', (t.prev_opp_wpct >= strong) & (t.next_opp_wpct >= strong) & (t.opp_wpct < .5)),
        ('Division revenge (lost the first meeting)', t.revenge == 1),
    ]
    # opponent's blowout last game, looked up from the opponent's own row
    om = t.set_index(['team', 'season', 'week']).last_margin
    t['opp_last_margin'] = [om.get((o, s, w), np.nan) for o, s, w in zip(t.opp, t.season, t.week)]
    rows += [('Opponent won its last game by 17+', t.opp_last_margin >= 17),
             ('Opponent lost its last game by 17+', t.opp_last_margin <= -17)]
    print('\n### Test 19A: team situations vs the closing moneyline (team perspective)\n')
    print('| Situation | Team-games | Actual − implied | z | Flat ROI backing the team |\n|---|---:|---:|---:|---:|')
    for label, mask in rows:
        print(summarize(t, mask.fillna(False).to_numpy(bool), label))
    # persistence of the market residual: does beating the price carry over?
    k = (t.games_before >= 3) & t.won.isin([0., 1.]) & np.isfinite(t.res_to_date) & np.isfinite(t.res)
    x, y = t.loc[k, 'res_to_date'].to_numpy(), t.loc[k, 'res'].to_numpy()
    A = np.column_stack([np.ones(len(x)), x]); b = np.linalg.lstsq(A, y, rcond=None)[0]; r = y - A @ b
    se = math.sqrt(r.var(ddof=2) / ((x - x.mean()) ** 2).sum())
    print(f'\n### Test 19B: persistence\n\nThis game actual − implied regressed on the season-to-date average '
          f'(3+ earlier games, n = {k.sum()}): slope {b[1]:+.3f} ± {se:.3f} (0 = the market fully updates; '
          f'> 0 = it under-reacts; < 0 = it over-reacts).')
    by = t[k].assign(b=pd.qcut(t.loc[k, 'res_to_date'], 5, labels=['lowest', '2', '3', '4', 'highest']))
    print('\n| Season-to-date actual − implied (quintile) | Team-games | Mean to date | This game actual − implied |\n|---|---:|---:|---:|')
    for q, g in by.groupby('b', observed=True):
        print(f'| {q} | {len(g)} | {100 * g.res_to_date.mean():+.1f} pts | {100 * g.res.mean():+.1f} pts ± {100 * g.res.std(ddof=1) / math.sqrt(len(g)):.1f} |')
    log('done')


if __name__ == '__main__':
    main()
