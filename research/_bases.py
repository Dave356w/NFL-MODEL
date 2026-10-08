"""Shared runner for feature tests decided on two held-out bases (Tests 33-34).

Primary basis 'old': 2013-20 rebuilt with the production code (warm-up 2013-14, walk-forward
2015-20, nested held-out 2017-20), as in Test 32. Secondary basis 'recent': walk-forward 2021-25,
nested held-out 2023-25. Production and the arm run the v1.12 grid with nested selection; the arm
differs only in its feature frame and/or feature names. Research only.
"""
import numpy as np

from _common import LAST, OUTER, WEEK_GROUPS, availability, boot_ci, load_inputs, log, m, null_and_favorite, score
from fit_memory import OLD_FIRST, OLD_LAST, OLD_OUTER, OLD_YEARS, load_old, nested, ready_share

BASES = {'old': {'first': OLD_FIRST, 'last': OLD_LAST, 'outer': OLD_OUTER, 'years': OLD_YEARS},
         'recent': {'first': m.BACKTEST_FIRST_SEASON, 'last': LAST, 'outer': OUTER,
                    'years': tuple(range(m.BACKTEST_FIRST_SEASON - m.WARMUP_SEASONS, LAST + 1))}}


def load_basis(kind, cache):
    """Inputs, production availability and production features for one basis."""
    inp = load_old(cache) if kind == 'old' else load_inputs(cache)
    inp['avail'] = availability(inp)
    inp['feats'] = {h: m.lagged_features(inp['box'], inp['sched'], h, inp['avail']) for h in m.TEAM_HALF_LIVES}
    inp.update(BASES[kind]); inp['kind'] = kind
    log(f'{kind} basis: production features built')
    return inp


def grid(feats, basis, names=None):
    """{recipe key: walk-forward predictions} over the basis's walk-forward seasons, and the rows."""
    saved = m.BACKTEST_FIRST_SEASON, m.feature_names
    try:
        m.BACKTEST_FIRST_SEASON = basis['first']
        if names is not None: m.feature_names = names
        oof = m.walk_forward_grid(feats, basis['last'])
    finally:
        m.BACKTEST_FIRST_SEASON, m.feature_names = saved
    rows = m.attach_moneylines(oof[['game_id', 'season', 'week', 'home', 'away', 'home won', 'market_wp', 'result',
                                    'spread_line']], basis['sched'])
    return {c[3:]: oof[c].to_numpy() for c in oof.columns if c.startswith('p__')}, rows


def compare(label, basis, arm_feats=None, arm_names=None, level=.975):
    """Production vs the arm on one basis. Prints the goal-metric table, the gain by season and week
    group, and returns a dict with the gain vector, its CI and the masks the decision rules need."""
    prod, rows = grid(basis['feats'], basis)
    arm, rows_a = grid(arm_feats if arm_feats is not None else basis['feats'], basis, arm_names)
    if not (rows.game_id.to_numpy() == rows_a.game_id.to_numpy()).all(): raise ValueError('row order differs')
    hp, pp = nested(prod, rows, basis['outer']); ha, pa = nested(arm, rows, basis['outer'])
    log(f'{label} [{basis["kind"]}] production picks ' + '; '.join(f'{y}: {k}' for y, k in pp.items()))
    log(f'{label} [{basis["kind"]}] arm picks ' + '; '.join(f'{y}: {k}' for y, k in pa.items()))
    sp, sa = score(hp), score(ha)
    d = sp['ll_vec'] - sa['ll_vec']; lo, hi = boot_ci(d, level)
    ready = ready_share(basis['feats'][m.TEAM_HALF_LIVES[0]], basis['outer'])
    priced = float(np.isfinite(m.market_ml_wp(hp)).mean())
    null, fav = null_and_favorite(hp)
    du = (sa['units_vec'] - sp['units_vec']).dropna()
    print(f'\n#### {label}, {basis["kind"]} basis: held-out {basis["outer"][0]}–{basis["outer"][-1]}, n = {len(hp)} games '
          f'({100 * ready:.1f}% of decided games ready, {100 * priced:.1f}% priced)\n')
    print(f'| Arm | LL gain vs production [{100 * level:g}% CI] | ± SE | Bets | Units | ROI ± SE | Log loss | LL vs ML market |\n'
          '|---|---:|---:|---:|---:|---:|---:|---:|')
    for name, s, g in (('production (v1.12)', sp, None), (label, sa, d)):
        gain = '—' if g is None else f'{g.mean():+.4f} [{lo:+.4f}, {hi:+.4f}]'
        se = '—' if g is None else f'{g.std(ddof=1) / np.sqrt(len(g)):.4f}'
        print(f"| {name} | {gain} | {se} | {s['bets']} | {s['units']:+.2f} | {100 * s['roi']:+.1f}% ± {100 * s['roi_se']:.1f} | "
              f"{s['ll']:.4f} | {s['ll_vs_mkt']:+.4f} |")
    print(f'\nSame priced rows: market favorite {100 * fav:+.1f}%, market-correct null {100 * null:+.1f}%. '
          f'ROI difference, same games: {100 * du.mean():+.2f} pts ± {100 * du.std(ddof=1) / np.sqrt(len(du)):.2f}.')
    seas, wk = hp.season.to_numpy(), hp.week.to_numpy()
    groups = [(str(s), seas == s) for s in basis['outer']] + [(f'wk {n}', (wk >= a) & (wk <= b)) for a, b, n in WEEK_GROUPS]
    groups = [(n, k) for n, k in groups if k.any()]
    print('\n| LL gain vs production | ' + ' | '.join(n for n, _ in groups) + ' |\n|---|' + '---:|' * len(groups))
    print(f'| {label} | ' + ' | '.join(f'{d[k].mean():+.4f} ± {d[k].std(ddof=1) / np.sqrt(k.sum()):.4f} (n={k.sum()})'
                                       for _, k in groups) + ' |')
    return {'d': d, 'lo': lo, 'hi': hi, 'ready': ready, 'priced': priced, 'season': seas, 'week': wk, 'held': hp}


def data_ok(res, floor=.90):
    return res['ready'] >= floor and res['priced'] >= floor


def window_gain(res, lo_week, hi_week):
    k = (res['week'] >= lo_week) & (res['week'] <= hi_week)
    return float(res['d'][k].mean()), int(k.sum())
