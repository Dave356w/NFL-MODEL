"""Test 17: does playoff-race context (clinched / eliminated) improve the composite?

    python research/season_context.py [CACHE_DIR]     # ~8 min warm

Test 13 found the model's worst week is week 18 (log loss 0.131 behind the market)
where clinched teams rest starters and eliminated teams fold. This builds, for
every team before every week, a playoff-race status from results of EARLIER weeks
only, then:

A. Diagnostic (production v1.10 held-out rows, 2023-25): does each status move the
   market-minus-model gap, and does it add to the outcome beyond the model or
   beyond the market? In-sample, by week group.
B. Real test: the v1.10 families plus three home-minus-away status inputs, run
   through the production grid with nested selection, scored game by game against
   v1.10 on the same priced held-out games.

Status (approximate: wins vs games remaining, ties as half a win, no tiebreakers,
division winners not seeded separately; 6 playoff spots per conference before
2020, 7 after):
  eliminated : at least `spots` conference rivals already have more wins than the
               team can still reach, and so does a division rival
  clinched   : fewer than `spots` conference rivals can still reach the team's wins,
               or no division rival can
  top_seed   : no conference rival can still reach the team's wins
"""
import numpy as np
import pandas as pd
from scipy.special import logit

from _common import DHEAD, HEAD, LAST, availability, cache_dir_from_argv, diff_row, load_inputs, log, m, outer, row, score
from market_info import logistic

DIVISIONS = {
    'AFC East': ('BUF', 'MIA', 'NE', 'NYJ'), 'AFC North': ('BAL', 'CIN', 'CLE', 'PIT'),
    'AFC South': ('HOU', 'IND', 'JAX', 'TEN'), 'AFC West': ('DEN', 'KC', 'LV', 'LAC'),
    'NFC East': ('DAL', 'NYG', 'PHI', 'WAS'), 'NFC North': ('CHI', 'DET', 'GB', 'MIN'),
    'NFC South': ('ATL', 'CAR', 'NO', 'TB'), 'NFC West': ('ARI', 'LA', 'SF', 'SEA')}
CONF = {t: d[:3] for d, ts in DIVISIONS.items() for t in ts}
DIV = {t: ts for ts in DIVISIONS.values() for t in ts}
STATUS = ('eliminated', 'clinched', 'top_seed')
CTX = tuple(f'd__ctx_{s}' for s in STATUS)


def team_status(sched):
    """(team, season, week) -> status flags using only games from earlier weeks."""
    out = {}
    for yr, s in sched.groupby('season'):
        spots = 6 if yr < 2020 else 7
        teams = sorted(set(s.home_team) | set(s.away_team))
        total = {t: int(((s.home_team == t) | (s.away_team == t)).sum()) for t in teams}
        for wk in sorted(s.week.unique()):
            done = s[(s.week < wk) & s.result.notna()]
            wins = {t: 0. for t in teams}; gp = {t: 0 for t in teams}
            for h, a, r in zip(done.home_team, done.away_team, done.result):
                gp[h] += 1; gp[a] += 1
                wins[h] += 1. if r > 0 else .5 if r == 0 else 0.
                wins[a] += 1. if r < 0 else .5 if r == 0 else 0.
            maxw = {t: wins[t] + total[t] - gp[t] for t in teams}
            for t in teams:
                rivals = [o for o in teams if o != t and CONF.get(o) == CONF.get(t)]
                div = [o for o in DIV[t] if o != t]
                wc_out = sum(wins[o] > maxw[t] for o in rivals) >= spots
                div_out = any(wins[o] > maxw[t] for o in div)
                won_div = all(maxw[o] < wins[t] for o in div)
                out[(t, int(yr), int(wk))] = {
                    'eliminated': float(wc_out and div_out),
                    'clinched': float(won_div or sum(maxw[o] >= wins[t] for o in rivals) < spots),
                    'top_seed': float(all(maxw[o] < wins[t] for o in rivals))}
    return out


def add_context(f, status):
    f = f.copy()
    for s, col in zip(STATUS, CTX):
        h = np.array([status.get((t, y, w), {}).get(s, 0.) for t, y, w in zip(f.home, f.season, f.week)])
        a = np.array([status.get((t, y, w), {}).get(s, 0.) for t, y, w in zip(f.away, f.season, f.week)])
        f[col] = h - a
    return f


def diagnostic(held, status):
    d = add_context(held, status)
    d['q'] = m.market_ml_wp(d)
    d = d[np.isfinite(d.q) & d['home won'].isin([0., 1.])]
    lines = ['| Weeks | Status (home − away) | Games with status ≠ 0 | Moves market − model gap | Beyond model: coef, LL gain | Beyond market: coef, LL gain |',
             '|---|---|---:|---:|---:|---:|']
    for lo, hi, name in ((12, 16, '12–16'), (17, 17, '17'), (18, 18, '18'), (12, 18, '12–18')):
        g = d[(d.week >= lo) & (d.week <= hi)]
        y = g['home won'].to_numpy(float)
        mk, md = logit(g.q.to_numpy()), logit(np.clip(g.model_wp.to_numpy(), 1e-4, 1 - 1e-4))
        _, _, ll_md = logistic(md[:, None], y); _, _, ll_mk = logistic(mk[:, None], y)
        for col, s in zip(CTX, STATUS):
            x = g[col].to_numpy(float); n = int((x != 0).sum())
            if n < 5:
                lines.append(f'| {name} | {s} | {n} | – | – | – |'); continue
            A = np.column_stack([np.ones(len(x)), x]); bg = np.linalg.lstsq(A, mk - md, rcond=None)[0]
            res = mk - md - A @ bg; se = np.sqrt(np.sum(res ** 2) / (len(x) - 2) / np.sum((x - x.mean()) ** 2))
            b1, s1, l1 = logistic(np.column_stack([md, x]), y); b2, s2, l2 = logistic(np.column_stack([mk, x]), y)
            lines.append(f'| {name} | {s} | {n} | {bg[1]:+.3f} ± {se:.3f} | {b1[2]:+.3f} ± {s1[2]:.3f}, {ll_md - l1:+.4f} | '
                         f'{b2[2]:+.3f} ± {s2[2]:.3f}, {ll_mk - l2:+.4f} |')
    return '\n'.join(lines)


def main():
    inp = load_inputs(cache_dir_from_argv())
    sched = inp['sched']; status = team_status(sched)
    avail = availability(inp)
    feats = {h: add_context(m.lagged_features(inp['box'], sched, h, avail), status) for h in m.TEAM_HALF_LIVES}
    log('features built')
    base = tuple(m.FEATURE_FAMILIES)  # v1.10 production families
    ctx = tuple(f + '_ctx' for f in base)
    names = m.feature_names
    m.feature_names = lambda fam: names(fam[:-4]) + list(CTX) if fam.endswith('_ctx') else names(fam)
    m.FEATURE_FAMILIES = base + ctx
    oof = m.attach_moneylines(m.walk_forward_grid(feats, LAST), sched)
    prod, pp = outer(oof, base); var, pv = outer(oof, ctx)
    log(f'v1.10 picks {pp}'); log(f'+context picks {pv}')
    f8 = feats[m.TEAM_HALF_LIVES[0]]
    counts = {c: int((f8.loc[f8.season.between(2023, LAST), c] != 0).sum()) for c in CTX}
    log(f'held-out games with a nonzero status: {counts}')
    print('\n### Test 17A: diagnostic (v1.10 held-out rows, in-sample)\n')
    print(diagnostic(prod, status))
    a, b = score(prod), score(var)
    print('\n### Test 17B: v1.10 + playoff-race status, nested selection\n' + HEAD)
    print(row('v1.10 production', a)); print(row('+ playoff-race status', b))
    print('\n' + DHEAD); print(diff_row('+ status vs v1.10', b, a))
    print('\n| Weeks | Games | ROI difference | Log-loss gain |\n|---|---:|---:|---:|')
    wk = prod.week.to_numpy()
    for lo, hi, name in ((1, 11, '1–11'), (12, 16, '12–16'), (17, 17, '17'), (18, 18, '18')):
        k = (wk >= lo) & (wk <= hi)
        du = (b['units_vec'] - a['units_vec']).to_numpy()[k]; du = du[np.isfinite(du)]
        dl = (a['ll_vec'] - b['ll_vec'])[k]
        print(f'| {name} | {k.sum()} | {100 * du.mean():+.2f} pts ± {100 * du.std(ddof=1) / np.sqrt(len(du)):.2f} | '
              f'{dl.mean():+.4f} ± {dl.std(ddof=1) / np.sqrt(len(dl)):.4f} |')
    log('done')


if __name__ == '__main__':
    main()
