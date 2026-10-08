"""Shared plumbing for research scripts. Research only: imports nfl_model and
changes module settings at runtime inside the research process; nothing here
touches data/, the frozen recipe or the forward ledger.

Every variant is judged the way production judges itself: for each held-out
season (2023-2025) the variant's recipe is the candidate with the lowest mean
walk-forward log loss on earlier seasons; all variants are scored on the same
priced games with flat 1u moneyline ROI and log loss, and compared game by game.
"""
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nfl_model as m  # noqa: E402

LAST, SEASON, OUTER = 2025, 2026, (2023, 2024, 2025)
FULL = ('rates_core_avail_cs', 'rates_core_adj_avail_cs')
T0 = time.time()


def log(s):
    print(f'[{time.time() - T0:6.0f}s] {s}', flush=True)


def load_inputs(cache_dir):
    """Schedules, box scores, QB rows and availability inputs through LAST (cached by nfl_model)."""
    m.CACHE_DIR = str(cache_dir)
    m.OUTPUT_ROOT = Path(cache_dir).parent
    years = list(range(m.BACKTEST_FIRST_SEASON - m.WARMUP_SEASONS, LAST + 1))
    sched = pd.concat([m.load_schedule(y) for y in years], ignore_index=True)
    boxes, qbs = [], []
    for y in years:
        b, q = m.load_boxes(y, sched[sched.season == y])
        boxes.append(b); qbs.append(q)
    box = m.validate_boxes(pd.concat(boxes, ignore_index=True))
    qb = pd.concat(qbs, ignore_index=True)
    a = m.load_availability(years, SEASON)
    targets = m.availability_targets(sched)  # with kickoffs, for the v1.11 depth-chart rule
    log('inputs loaded')
    return {'sched': sched, 'box': box, 'qb': qb, 'a': a, 'targets': targets}


def availability(inp):
    a = inp['a']
    return m.availability_table(inp['targets'], inp['qb'], a['snaps'], a['inj'], a['rost'], depth=a.get('depth'))


def grid(inp, avail, families, label):
    """Walk-forward grid (production half-lives x ridges) for `families` on `avail`."""
    feats = {h: m.lagged_features(inp['box'], inp['sched'], h, avail) for h in m.TEAM_HALF_LIVES}
    m.FEATURE_FAMILIES = tuple(families)
    oof = m.walk_forward_grid(feats, LAST)
    log(f'{label}: {len(m.candidates())} candidates done')
    return m.attach_moneylines(oof, inp['sched'])


def _ll(y, p):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def outer(oof, families, seasons=OUTER):
    """Production selection: each held-out season's recipe = min mean LL on earlier seasons."""
    cols = [c for c in oof.columns if c.startswith('p__') and any(c[3:].startswith(f + '_h') for f in families)]
    y = oof['home won'].to_numpy(float)
    parts, picks = [], {}
    for yr in seasons:
        tr = (oof.season < yr).to_numpy()
        best = min(cols, key=lambda c: _ll(y[tr], oof[c].to_numpy()[tr]).mean())
        te = oof[oof.season == yr].copy()
        te['model_wp'] = te[best]
        parts.append(te); picks[yr] = best[3:]
    return pd.concat(parts).sort_values('game_id').reset_index(drop=True), picks


def score(df):
    d = df.copy(); d['market_ml_wp'] = m.market_ml_wp(d)
    mb, kb = m.flat_bets(d, 'model_wp'), m.flat_bets(d, 'market_ml_wp')
    keep = mb.units.notna() & kb.units.notna()
    r = m.roi_summary(mb[keep]); y = d['home won'].to_numpy(float)
    l = _ll(y, d.model_wp.to_numpy()); lk = _ll(y, np.clip(d.market_ml_wp.to_numpy(), 1e-6, 1 - 1e-6))
    return {'bets': r['bets'], 'units': r['units'], 'roi': r['roi'], 'roi_se': r['roi_se'],
            'fav_roi': float(kb.units[keep].mean()), 'll': float(l.mean()), 'll_vs_mkt': float(np.nanmean(lk - l)),
            'units_vec': mb.units.where(keep), 'll_vec': l}


def paired(a, b):
    """a minus b on the same games: (ROI diff, SE, LL gain, SE); positive = a better."""
    du = (a['units_vec'] - b['units_vec']).dropna(); dl = b['ll_vec'] - a['ll_vec']
    return du.mean(), du.std(ddof=1) / np.sqrt(len(du)), dl.mean(), dl.std(ddof=1) / np.sqrt(len(dl))


def row(name, s):
    return (f"| {name} | {s['bets']} | {s['units']:+.2f} | {100 * s['roi']:+.1f}% ± {100 * s['roi_se']:.1f} | "
            f"{s['ll']:.4f} | {s['ll_vs_mkt']:+.4f} |")


def diff_row(name, a, b):
    du, se, dl, sl = paired(a, b)
    return f"| {name} | {100 * du:+.2f} pts ± {100 * se:.2f} | {dl:+.4f} ± {sl:.4f} |"


HEAD = "| Variant | Bets | Units | ROI ± SE | Log loss | LL vs ML market |\n|---|---:|---:|---:|---:|---:|"
DHEAD = "| Comparison (same games) | ROI difference | Log-loss gain |\n|---|---:|---:|"


def cache_dir_from_argv(default='.nfl_cache'):
    return Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get('NFL_CACHE_DIR', default))


# Shared reporting for tests run as a family (Tests 29-31): bootstrap CI of the per-game
# log-loss gain, plus the secondary goal-metric and by-season / by-week tables.
WEEK_GROUPS = ((1, 4, '1–4'), (5, 9, '5–9'), (10, 13, '10–13'), (14, 17, '14–17'), (18, 18, '18'))


def boot_ci(d, level, reps=4000):
    """Game-bootstrap interval of the mean of per-game values d."""
    d = np.asarray(d, float); rng = np.random.default_rng(m.SEED)
    means = np.array([d[rng.integers(0, len(d), len(d))].mean() for _ in range(reps)])
    a = (1 - level) / 2
    return float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def same_rows(*held):
    """Held-out frames from outer() must hold the same games in the same order."""
    ids = held[0].game_id.to_numpy()
    for h in held[1:]:
        if not (h.game_id.to_numpy() == ids).all(): raise ValueError('held-out rows differ between arms')


def null_and_favorite(df):
    """Market-correct null and the market favorite's ROI on the rows score() grades."""
    d = df.copy(); d['market_ml_wp'] = m.market_ml_wp(d)
    mb, kb = m.flat_bets(d, 'model_wp'), m.flat_bets(d, 'market_ml_wp')
    keep = mb.units.notna() & kb.units.notna()
    return m.roi_summary(mb[keep])['null_roi'], m.roi_summary(kb[keep])['roi']


def report_family(prod_held, sc, level):
    """sc: {name: score()} with production first. Prints the goal-metric table, paired
    differences and the gain by season and week group; returns {arm: (gain vector)}."""
    names = list(sc); base = sc[names[0]]
    print('\n' + HEAD)
    for n in names: print(row(n, sc[n]))
    null, fav = null_and_favorite(prod_held)
    print(f'\nSame priced rows: market favorite {100 * fav:+.1f}%, market-correct null {100 * null:+.1f}%.')
    print('\n' + DHEAD)
    for n in names[1:]: print(diff_row(f'{n} vs {names[0]}', sc[n], base))
    seas = prod_held.season.to_numpy(); wk = prod_held.week.to_numpy()
    groups = [(str(s), seas == s) for s in OUTER] + [(f'wk {g}', (wk >= lo) & (wk <= hi)) for lo, hi, g in WEEK_GROUPS]
    print('\n| LL gain vs production | ' + ' | '.join(g for g, _ in groups) + ' |\n|---|' + '---:|' * len(groups))
    gains = {}
    for n in names[1:]:
        d = base['ll_vec'] - sc[n]['ll_vec']; gains[n] = d
        print(f'| {n} | ' + ' | '.join(f'{d[k].mean():+.4f} ± {d[k].std(ddof=1) / np.sqrt(k.sum()):.4f} (n={k.sum()})'
                                       for _, k in groups) + ' |')
    return gains


def primary_row(name, d, level, verdict):
    lo, hi = boot_ci(d, level)
    print(f'| {name} | {d.mean():+.4f} [{lo:+.4f}, {hi:+.4f}] | {d.std(ddof=1) / np.sqrt(len(d)):.4f} | {verdict(d.mean(), lo, hi)} |')
    return lo, hi
