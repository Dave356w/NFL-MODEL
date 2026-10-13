"""Selection-adjusted benchmark for the committed 2023-2025 model search.

How good would the best of all committed historical arms look if the market were
exactly right? Outcomes are drawn from the no-vig market; every arm is scored on its
paired units against the same-row market favorite and its log-loss gain over the market,
and the best arm is kept in each draw. White's Reality Check (week-cluster bootstrap of
centred differentials) asks the same question without assuming the market is right.

Forecasts are held fixed (arms are not refit on simulated outcomes), and only arms with
committed per-game predictions are included; many more configurations were tried. The
adjustment is therefore a lower bound. Exposed history; not forward evidence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'research/selection_benchmark_results'
STUDIES = {'qualification': 'qualification_results/heldout_predictions.csv',
           'context': 'context_results/heldout_predictions.csv',
           'market_offset': 'market_offset_results/heldout_predictions.csv',
           'shrinkage': 'shrinkage_results/heldout_predictions.csv',
           'profile_robustness': 'profile_robustness_results/heldout_predictions.csv',
           'margin_total': 'margin_total_results/heldout_win_predictions.csv',
           'market_residual': 'market_residual_results/heldout_win_predictions.csv',
           'monte_carlo': 'monte_carlo_results/heldout_predictions.csv',
           'chrono_calibration': 'chronological_calibration_results/heldout_predictions.csv',
           'support_cap': 'support_cap_results/heldout_predictions.csv'}
BASE = ['season', 'week', 'home won', 'home_moneyline', 'away_moneyline', 'q']
NOT_ARMS = set(BASE)|{'game_id', 'home', 'away', 'result', 'spread_line', 'ready', 'site', 'margin', 'total',
                      'market', 'market_only', 'price_calibrated', 'home won_forecast', 'q_forecast', 'site_forecast',
                      'market_cover_q', 'market_over_q', 'pass_product', 'pass_1sd_pp', 'pass_1sd_pn', 'pass_1sd_np',
                      'pass_1sd_nn', 'pass_total_interaction', 'total_homefield', 'margin_edge', 'total_context'}
NAMED = {'v1.16': 'context:hinge_1_fixed_r0.1', 'v1.17': 'market_residual:pass_total'}
SEED, DRAWS, BOOT = 20261013, 20000, 10000


def load_arms(root=ROOT/'research', studies=STUDIES):
    """Every committed per-game 2023-25 forecast, one column per distinct arm."""
    base, arms = None, {}
    for study, path in studies.items():
        d = pd.read_csv(Path(root)/path)
        d = d[d.season.between(2023, 2025)].set_index('game_id')
        if base is None: base = d[BASE].copy()
        for col in d.columns:
            if col in NOT_ARMS or col.startswith(('d__', 'sum__', 'pass_h', 'pass_a')) or '__' in col: continue
            if col.endswith(('_p05', '_p95', '_sd', '_tie', '_mc', '_mc_second')): continue
            v = pd.to_numeric(d[col], errors='coerce').reindex(base.index)
            if v.isna().any() or not v.between(0, 1).all() or v.nunique() < 50: continue
            arms[f'{study}:{col}'] = v
    keep, seen = {}, [base.q.to_numpy(float)]
    for name, v in arms.items():  # drop market copies and reproductions of an earlier arm
        x = v.to_numpy(float)
        if any(np.allclose(x, s, rtol=0, atol=1e-9) for s in seen): continue
        seen.append(x); keep[name] = v
    return base, pd.DataFrame(keep, index=base.index)


def payouts(ml):
    ml = np.asarray(ml, float)
    return np.where(ml > 0, ml/100, 100/-ml)


def differentials(y, q, p, pay_home, pay_away):
    """Per game: units minus the favorite's units, and log-loss gain over q, for each arm."""
    yy = y[:, None]
    home = p > .5
    units = np.where(home, yy*pay_home[:, None]-(1-yy), (1-yy)*pay_away[:, None]-yy)
    fav = np.where(q > .5, y*pay_home-(1-y), (1-y)*pay_away-y)
    gain = -(y*np.log(q)+(1-y)*np.log(1-q))[:, None]+(yy*np.log(p)+(1-yy)*np.log(1-p))
    return units-fav[:, None], gain


def benchmark(y, q, p, pay_home, pay_away, weeks, names, named=NAMED, draws=DRAWS, boot=BOOT, seed=SEED):
    """Best-arm statistics against the market-correct null and White's Reality Check."""
    missing = sorted(set(named.values())-set(names))
    if missing: raise ValueError(f'Named arms missing or deduplicated: {missing}')
    n = len(y)
    du, dl = differentials(y, q, p, pay_home, pay_away)
    obs_u, obs_l = du.mean(0), dl.mean(0)
    rng = np.random.default_rng(seed)
    max_u, max_l, own = np.empty(draws), np.empty(draws), {k: np.empty(draws) for k in named}
    for s in range(draws):
        a, b = differentials((rng.random(n) < q).astype(float), q, p, pay_home, pay_away)
        mu, ml = a.mean(0), b.mean(0)
        max_u[s], max_l[s] = mu.max(), ml.max()
        for k, arm in named.items(): own[k][s] = mu[names.index(arm)]
    clusters = np.unique(weeks)
    cu = np.array([du[weeks == w].sum(0) for w in clusters]); cl = np.array([dl[weeks == w].sum(0) for w in clusters])
    cn = np.array([(weeks == w).sum() for w in clusters])
    pick = rng.integers(0, len(clusters), (boot, len(clusters)))

    def reality_check(c, obs):
        centred = (c[pick].sum(1)/cn[pick].sum(1)[:, None]-obs[None, :]).max(1)
        return float((centred >= obs.max()).mean()), float(np.quantile(centred, .95))
    rc_u, rc_u_crit = reality_check(cu, obs_u); rc_l, rc_l_crit = reality_check(cl, obs_l)
    info = {'games': int(n), 'arms': len(names), 'draws': draws, 'bootstrap': boot, 'seed': seed,
            'units_vs_favorite': {
                'best_arm': names[int(obs_u.argmax())], 'best_units': float(obs_u.max()*n),
                'null_best_median_units': float(np.median(max_u)*n), 'null_best_p95_units': float(np.quantile(max_u, .95)*n),
                'market_null_p': float((max_u >= obs_u.max()).mean()),
                'reality_check_p': rc_u, 'reality_check_critical_per_game': rc_u_crit},
            'log_loss_gain': {
                'best_arm': names[int(obs_l.argmax())], 'best_gain': float(obs_l.max()),
                'null_best_median': float(np.median(max_l)), 'null_best_p95': float(np.quantile(max_l, .95)),
                'market_null_p': float((max_l >= obs_l.max()).mean()),
                'reality_check_p': rc_l, 'reality_check_critical': rc_l_crit},
            'named': {k: {'arm': arm, 'units_vs_favorite': float(obs_u[names.index(arm)]*n),
                          'll_gain': float(obs_l[names.index(arm)]),
                          'unadjusted_market_null_p': float((own[k] >= obs_u[names.index(arm)]).mean()),
                          'market_null_p_against_best_arm': float((max_u >= obs_u[names.index(arm)]).mean())}
                      for k, arm in named.items()}}
    return info, obs_u*n, obs_l


def run(out=OUT, draws=DRAWS, boot=BOOT):
    out = Path(out).resolve()
    if any(out == x or x in out.parents for x in (ROOT/'data', ROOT/'public')):
        raise ValueError('Research cannot write production outputs')
    base, arms = load_arms()
    y, q = base['home won'].to_numpy(float), base.q.to_numpy(float)
    p = arms.to_numpy(float)
    ok = (y != .5) & ~np.isclose(q, .5) & ~np.isclose(p, .5).any(axis=1)  # ties push; no side at .5
    weeks = (base.season.astype(int).astype(str)+'_'+base.week.astype(int).astype(str)).to_numpy()[ok]
    names = list(arms.columns)
    stats, units, gain = benchmark(y[ok], q[ok], p[ok], payouts(base.home_moneyline.to_numpy()[ok]),
                                   payouts(base.away_moneyline.to_numpy()[ok]), weeks, names, draws=draws, boot=boot)
    info = {'basis': 'Exposed 2023-2025 held-out walk-forward; fixed committed forecasts; not forward evidence', **stats}
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({'arm': names, 'units_vs_favorite': units, 'll_gain': gain}).to_csv(out/'arms.csv', index=False)
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    sources = [Path(__file__).resolve()]+[ROOT/'research'/path for path in STUDIES.values()]
    (out/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)): hashlib.sha256(x.read_bytes()).hexdigest()
                                                   for x in sources}, indent=2)+'\n')
    write_report(info, out)
    print(json.dumps(info, indent=2), flush=True)
    return info


def summary_lines(info):
    """Plain summary shared by REPORT.md and the version report."""
    u, l, v16, v17 = info['units_vs_favorite'], info['log_loss_gain'], info['named']['v1.16'], info['named']['v1.17']
    return [f"Across {info['arms']} committed arms on the same {info['games']} games, if the market were exactly right the best "
            f"arm would beat the same-row favorite by a median {u['null_best_median_units']:+.1f}u by luck alone "
            f"(95th percentile {u['null_best_p95_units']:+.1f}u).",
            f"Observed best: {u['best_arm']} beats it by {u['best_units']:+.1f}u (market-correct p {u['market_null_p']:.3f}; "
            f"Reality Check p {u['reality_check_p']:.3f}). v1.16 beats it by {v16['units_vs_favorite']:+.1f}u "
            f"(p {v16['market_null_p_against_best_arm']:.3f} against the best-arm null; {v16['unadjusted_market_null_p']:.3f} unadjusted). "
            f"v1.17 beats it by {v17['units_vs_favorite']:+.1f}u (p {v17['market_null_p_against_best_arm']:.3f}).",
            f"Log loss: best arm {l['best_arm']} gains {l['best_gain']:+.4f} over the market "
            f"(market-correct p {l['market_null_p']:.3f}; Reality Check p {l['reality_check_p']:.3f}).",
            'Forecasts are fixed and only committed arms are included. Many more configurations were tried, '
            'so the real selection adjustment is larger and these p-values are optimistic.']


def write_report(info, out):
    lines = ['# Selection-adjusted benchmark', '', 'Basis: '+info['basis']+'.', '', *summary_lines(info), '',
             f"Seed {info['seed']}; {info['draws']} market-correct draws; {info['bootstrap']} week-cluster bootstrap draws. "
             'Per-arm observed values are in `arms.csv`.', '',
             'Run: `python research/selection_benchmark.py`.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, default=OUT)
    run(ap.parse_args().output_dir)
