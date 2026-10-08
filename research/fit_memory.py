"""Test 32: how long should old training games count in the composite fit?

    python research/fit_memory.py [CACHE_DIR]     # cold: ~20 min (downloads 2013-18); warm: ~12 min

Plan and decision rule: research/README.md, Test 32 (committed before any result).
fit_composite weights each earlier training game by 2^(-age / FIT_HALF_LIFE_SEASONS) with
FIT_HALF_LIFE_SEASONS = 2, set by hand. The arm crosses the production grid with
FIT_HALF_LIFE_SEASONS in {2, 4, inf} (72 candidates) and lets nested selection choose.
Primary basis: seasons no test has scored the composite on. 2013-2020 are rebuilt with the
v1.12 code unchanged (snap counts start in 2013): warmup 2013-14, walk-forward 2015-20,
nested held-out 2017-20. Secondary: the usual 2021-25 walk-forward with held-out 2023-25.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from _common import LAST, OUTER, SEASON, availability, boot_ci, cache_dir_from_argv, load_inputs, log, m, \
    null_and_favorite, score

OLD_YEARS = tuple(range(2013, 2021))
OLD_FIRST, OLD_LAST, OLD_OUTER = 2015, 2020, (2017, 2018, 2019, 2020)
HALF_LIVES = (2., 4., np.inf)
MIN_READY_PRICED = .90


def load_old(cache_dir):
    """Schedules, box scores, QB rows and availability inputs for OLD_YEARS (cached by nfl_model)."""
    m.CACHE_DIR = str(cache_dir); m.OUTPUT_ROOT = Path(cache_dir).parent
    sched = pd.concat([m.load_schedule(y) for y in OLD_YEARS], ignore_index=True)
    boxes, qbs = [], []
    for y in OLD_YEARS:
        b, q = m.load_boxes(y, sched[sched.season == y]); boxes.append(b); qbs.append(q)
    box = m.validate_boxes(pd.concat(boxes, ignore_index=True))
    a = m.load_availability(list(OLD_YEARS), SEASON)
    log(f'{OLD_YEARS[0]}-{OLD_YEARS[-1]} inputs loaded')
    return {'sched': sched, 'box': box, 'qb': pd.concat(qbs, ignore_index=True), 'a': a,
            'targets': m.availability_targets(sched)}


def candidates_by_half_life(feats, first, last, sched):
    """{(fit half-life, recipe key): walk-forward predictions} on the walk_forward_grid rows, and the rows."""
    saved = m.BACKTEST_FIRST_SEASON, m.FIT_HALF_LIFE_SEASONS
    out, rows = {}, None
    try:
        m.BACKTEST_FIRST_SEASON = first
        for hl in HALF_LIVES:
            m.FIT_HALF_LIFE_SEASONS = hl
            oof = m.walk_forward_grid(feats, last)
            if rows is None: rows = m.attach_moneylines(oof[['game_id', 'season', 'week', 'home', 'away', 'home won',
                                                             'market_wp', 'result', 'spread_line']], sched)
            elif not (oof.game_id.to_numpy() == rows.game_id.to_numpy()).all(): raise ValueError('row order')
            out.update({(hl, c[3:]): oof[c].to_numpy() for c in oof.columns if c.startswith('p__')})
            log(f'  fit half-life {hl:g}: {sum(k[0] == hl for k in out)} candidates')
    finally:
        m.BACKTEST_FIRST_SEASON, m.FIT_HALF_LIFE_SEASONS = saved
    return out, rows


def nested(cands, rows, seasons):
    """Each held-out season's candidate = min mean walk-forward log loss on earlier seasons."""
    y = rows['home won'].to_numpy(float); seas = rows.season.to_numpy()
    p = np.full(len(rows), np.nan); picks = {}
    for yr in seasons:
        tr = seas < yr
        best = min(cands, key=lambda k: m.ll(y[tr], cands[k][tr]).mean()); picks[yr] = best
        p[seas == yr] = cands[best][seas == yr]
    keep = np.isin(seas, seasons)
    return rows[keep].assign(model_wp=p[keep]).reset_index(drop=True), picks


def label(k): return f'hl {k[0]:g}, {k[1]}'


def evaluate(name, cands, rows, seasons, primary):
    prod = {k: v for k, v in cands.items() if k[0] == 2.}
    arms = {'production (fit half-life 2)': prod,
            'Test 32: fit half-life in {2, 4, ∞}': cands,
            'fixed fit half-life 4': {k: v for k, v in cands.items() if k[0] == 4.},
            'fixed fit half-life ∞': {k: v for k, v in cands.items() if k[0] == np.inf}}
    held, sc = {}, {}
    for a, cs in arms.items():
        held[a], picks = nested(cs, rows, seasons); sc[a] = score(held[a])
        log(f'{name} {a}: picks ' + '; '.join(f'{yr}: {label(k)}' for yr, k in picks.items()))
    hp = held['production (fit half-life 2)']
    priced = float(np.isfinite(m.market_ml_wp(hp)).mean())
    null, fav = null_and_favorite(hp)
    print(f'\n#### {name}: held-out {seasons[0]}–{seasons[-1]}, n = {len(hp)} games ({100 * priced:.0f}% priced)\n')
    print('| Arm | LL gain vs production [95% CI] | ± SE | Bets | Units | ROI ± SE | Log loss | LL vs ML market |'
          + (' Verdict |' if primary else '') + '\n|---|---:|---:|---:|---:|---:|---:|---:|' + ('---|' if primary else ''))
    base = sc['production (fit half-life 2)']; verdict = None
    for a, s in sc.items():
        cells = f"{s['bets']} | {s['units']:+.2f} | {100 * s['roi']:+.1f}% ± {100 * s['roi_se']:.1f} | {s['ll']:.4f} | {s['ll_vs_mkt']:+.4f}"
        if a.startswith('production'):
            print(f'| {a} | — | — | {cells} |' + (' — |' if primary else '')); continue
        d = base['ll_vec'] - s['ll_vec']; lo, hi = boot_ci(d, .95)
        v = ''
        if primary and a.startswith('Test 32'):
            verdict = 'dropped' if hi < .001 else 'supported' if lo > 0 else 'unresolved'; v = f' {verdict} |'
        elif primary: v = ' (reported) |'
        print(f'| {a} | {d.mean():+.4f} [{lo:+.4f}, {hi:+.4f}] | {d.std(ddof=1) / np.sqrt(len(d)):.4f} | {cells} |{v}')
    print(f'\nSame priced rows: market favorite {100 * fav:+.1f}%, market-correct null {100 * null:+.1f}%.')
    seas = hp.season.to_numpy()
    print('\n| LL gain vs production, by season | ' + ' | '.join(map(str, seasons)) + ' |\n|---|' + '---:|' * len(seasons))
    for a in list(sc)[1:]:
        d = base['ll_vec'] - sc[a]['ll_vec']
        print(f'| {a} | ' + ' | '.join(f'{d[seas == s].mean():+.4f} ± {d[seas == s].std(ddof=1) / np.sqrt((seas == s).sum()):.4f}'
                                       for s in seasons) + ' |')
    return priced, verdict


def ready_share(features, seasons):
    """Share of decided games in `seasons` that are ready (both teams have MIN_TEAM_HISTORY games)."""
    d = features[features.season.isin(seasons) & features['home won'].isin([0., 1.])]
    return float(d.ready.mean()) if len(d) else 0.


def main():
    cache = cache_dir_from_argv()
    old = load_old(cache)
    feats = {h: m.lagged_features(old['box'], old['sched'], h, availability(old)) for h in m.TEAM_HALF_LIVES}
    log('2013-20 features built')
    cands, rows = candidates_by_half_life(feats, OLD_FIRST, OLD_LAST, old['sched'])
    print('\n### Test 32 result')
    priced, verdict = evaluate('Primary basis (untouched seasons)', cands, rows, OLD_OUTER, True)
    ready = ready_share(feats[m.TEAM_HALF_LIVES[0]], OLD_OUTER)
    ok = ready >= MIN_READY_PRICED and priced >= MIN_READY_PRICED
    print(f'\nData check: {100 * ready:.1f}% of held-out games ready, {100 * priced:.1f}% priced '
          f'(both must be >= {100 * MIN_READY_PRICED:.0f}%): ' + ('passed' if ok else 'FAILED, primary basis not usable'))
    print(f'**Primary verdict: {verdict if ok else "not run (data check failed)"}**')
    inp = load_inputs(cache)
    feats = {h: m.lagged_features(inp['box'], inp['sched'], h, availability(inp)) for h in m.TEAM_HALF_LIVES}
    cands, rows = candidates_by_half_life(feats, m.BACKTEST_FIRST_SEASON, LAST, inp['sched'])
    evaluate('Secondary basis (seen in the exploratory sweep)', cands, rows, OUTER, False)
    log('done')


if __name__ == '__main__':
    main()
