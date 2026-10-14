"""Test 37: input trends in the model's wrong picks, by total context; see RESIDUAL_TRENDS.md.

    python research/residual_trends.py             # discovery 2017-22, confirmation 2023-25, 2026 diagnostic
    python research/residual_trends.py --forward   # H8 and H7 on the native ledger (PREREGISTRATION.md)
    python research/residual_trends.py --replicate # the H8 trends and H7 on never-scored 2015-16 (addendum)

Reads only committed files; no network access. Never writes data/ or the ledger.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nfl_model as m  # noqa: E402

OOS_PRED = ROOT/'research/out_of_sample_results/predictions.csv'
OOS_PACK = ROOT/'research/out_of_sample_results/frozen_features_2013_2020.csv.gz'
T36_PACK = ROOT/'research/shrinkage_results/frozen_training_features.csv.gz'
HELDOUT = ROOT/'research/restore_v116_results/historical_reproduction.csv'
RETRO = ROOT/'data/latest/retro_ledger.csv'
TOTALS = ROOT/'research/residual_trends_inputs/schedule_totals.csv'
LEDGER = ROOT/'data/forward_predictions.jsonl'
LEDGER_VIEW = ROOT/'data/forward_ledger.csv'
H5_TOTALS = ROOT/'data/h5_totals.jsonl'
OUT = ROOT/'research/residual_trends_results'
PROTOCOL_COMMIT = '72549f5'

RECIPE = m.LEGACY_PRODUCT_RECIPE  # v1.16; v1.18 = the favorite penalty applied after it
MODEL_INPUTS = [n for n in m.feature_names(RECIPE['family']) if n != 'site'] + list(m.PRODUCT_CONTEXT_NAMES)
INPUTS = MODEL_INPUTS + ['market_logit', 'departure']
CONTEXTS = ('all', 'total_low', 'total_mid', 'total_high')
CONTEXT_LABEL = {'all': 'all games', 'total_low': 'total <= 41', 'total_mid': 'total 41.5-47',
                 'total_high': 'total >= 47.5'}
MIN_Z, MAX_K, MAX_FORWARD = 2.0, 10, 5
FORWARD = {'H8': ('boxscore-composite-v1.18', '73636f306d54de2c12a0d8ba394f0aecae9d58d2cd9aa415a87c4b22bca58a20'),
           'H7': ('boxscore-composite-v1.16', '9dad9b9ad0eda3c043c4227d211e8c1cb460beaac6c649f09787c296a62dcd26')}
FORWARD_FIRST = (2026, 6)
BASIS = {'discovery': '2017-22 reconstructions, prior-week fits (exposed history; hypothesis generation only)',
         'confirmation': '2023-25 held-out reproduction (exposed development data; trends chosen on 2017-22 only)',
         'diagnostic': '2026 weeks 1-5 current-season walk-forward from the frozen Test 36 pack; reported only'}


def context_mask(total, ctx):
    t = pd.to_numeric(pd.Series(total), errors='coerce').to_numpy(float)
    if ctx == 'all': return np.ones(len(t), bool)
    if ctx == 'total_low': return t <= 41
    if ctx == 'total_mid': return (t >= 41.5) & (t <= 47)
    if ctx == 'total_high': return t >= 47.5
    raise ValueError(f'Unknown context {ctx}')


def prepare(frame):
    """Priced rows with q, v1.16 (p16) and v1.18 (p) probabilities, the two market inputs, the
    residual and flat bets. `frame` carries p16, both moneylines, total_line and the inputs."""
    d = frame.copy()
    d['q'] = m.market_ml_wp(d)
    d = d[np.isfinite(d.q) & np.isfinite(d.p16)].reset_index(drop=True)
    d['p'] = m.favorite_penalized_wp(d.p16.to_numpy(float), d.q.to_numpy(float), m.FAVORITE_PENALTY)
    d['market_logit'] = logit(d.q)
    d['departure'] = logit(d.p) - logit(d.q)
    d['departure16'] = logit(d.p16) - logit(d.q)
    d['y'] = d['home won'].where(d['home won'].isin([0., 1.]))
    b = m.flat_bets(d.assign(model_wp=d.p)); fb = m.flat_bets(d.assign(model_wp=d.q))
    d['side'] = b.side; d['units'] = b.units; d['null_ev'] = b.null_ev; d['fav_units'] = fb.units
    d['bet'] = b.units.notna() & fb.units.notna()  # same graded priced rows; pick'ems out (repo convention)
    d['cluster'] = d.season.astype(int).astype(str) + '_' + d.week.astype(int).astype(str)
    return d


def cell(d, x, prob='p'):
    """Score test for adding input x in these rows, with the model's log-odds as offset."""
    k = d.y.notna().to_numpy() & np.isfinite(d[x].to_numpy(float))
    y, p = d.y.to_numpy(float)[k], d[prob].to_numpy(float)[k]
    xt = d[x].to_numpy(float)[k]; xt = xt - xt.mean() if len(xt) else xt
    cl = d.cluster.to_numpy()[k]
    out = {'n': int(k.sum()), 'z': np.nan, 'effect_per_sd': np.nan, 'S': np.nan}
    if k.sum() < 10 or np.allclose(xt, 0): return out
    r = y - p; S = float(np.sum(r*xt))
    V = float((pd.Series(r*xt).groupby(cl).sum()**2).sum())
    info = float(np.sum(p*(1-p)*xt*xt))
    out.update(S=S, z=S/np.sqrt(V) if V > 0 else np.nan, effect_per_sd=S/info*float(xt.std()) if info > 0 else np.nan)
    return out


def scan(d, prob='p'):
    rows = []
    for ctx in CONTEXTS:
        sub = d[context_mask(d.total_line, ctx)]
        for x in INPUTS:
            col = 'departure16' if (x == 'departure' and prob == 'p16') else x
            rows.append({'context': ctx, 'input': x, **cell(sub, col, prob)})
    return pd.DataFrame(rows)


def select(disc):
    """Cells with |z| >= MIN_Z on discovery, ranked by |z|, at most MAX_K."""
    c = disc[np.abs(disc.z) >= MIN_Z].copy()
    c['abs_z'] = c.z.abs()
    return c.sort_values(['abs_z', 'context', 'input'], ascending=[False, True, True]).head(MAX_K).drop(columns='abs_z')


def confirm(cands, conf):
    """Directional confirmation z and verdicts (one-sided Bonferroni over the K candidates)."""
    k = len(cands)
    bar = float(norm.ppf(1-.05/k)) if k else np.nan
    c = cands.merge(conf[['context', 'input', 'n', 'z', 'effect_per_sd']], on=['context', 'input'],
                    suffixes=('_d', '_c'), validate='one_to_one')
    c['z_c_dir'] = np.sign(c.z_d)*c.z_c
    c['verdict'] = np.where(c.z_c_dir >= bar, 'confirmed', np.where(c.z_c_dir > 0, 'direction holds', 'not replicated'))
    c.loc[~np.isfinite(c.z_c_dir), 'verdict'] = 'not replicated'
    return c, bar


def forward_set(confirmed):
    f = confirmed[confirmed.z_c_dir > 0].copy()
    f['abs_z_d'] = f.z_d.abs()
    return f.sort_values(['z_c_dir', 'abs_z_d'], ascending=False).head(MAX_FORWARD).drop(columns='abs_z_d')


def signed_toward_model(d, x):
    v = d[x].to_numpy(float)
    return np.where(d.side == 'home', v, np.where(d.side == 'away', -v, np.nan))


def tercile_cuts(d, ctx, x):
    s = signed_toward_model(d[context_mask(d.total_line, ctx)], x)
    s = s[np.isfinite(s)]
    return [float(v) for v in np.quantile(s, [1/3, 2/3])] if len(s) >= 3 else [np.nan, np.nan]


def wrong_pick_view(d, ctx, x, cuts):
    """Per third of the input signed toward the model's side: graded bets, model-side wins minus
    expected wins under p, flat 1u units and the same-row favorite's units."""
    sub = d[context_mask(d.total_line, ctx) & d.bet].copy()
    sub['s'] = signed_toward_model(sub, x)
    lab = np.where(sub.s <= cuts[0], 'low', np.where(sub.s <= cuts[1], 'middle', 'high'))
    sub['third'] = np.where(np.isfinite(sub.s), lab, None)
    p_side = np.where(sub.side == 'home', sub.p, 1-sub.p)
    win = np.where(sub.side == 'home', sub.y, 1-sub.y)
    sub['excess'] = np.where(sub.y.notna(), win-p_side, np.nan)
    rows = []
    for t in ('low', 'middle', 'high'):
        g = sub[sub.third == t]
        n = len(g)
        rows.append({'third': t, 'bets': n, 'wins_minus_expected': float(np.nansum(g.excess)),
                     'units': float(g.units.sum()), 'roi': float(g.units.mean()) if n else np.nan,
                     'fav_units': float(g.fav_units.sum())})
    return rows


def roi_by_context(d):
    rows = []
    for ctx in CONTEXTS:
        b = d[context_mask(d.total_line, ctx) & d.bet]
        bets = m.flat_bets(b.assign(model_wp=b.p))
        s = m.roi_summary(bets)
        rows.append({'context': ctx, 'bets': s['bets'], 'w': s['wins'], 'l': s['losses'], 'p': s['pushes'],
                     'units': s['units'], 'roi': s['roi'], 'roi_se': s['roi_se'], 'null': s['null_roi'],
                     'fav_units': float(b.fav_units.sum()), 'fav_roi': float(b.fav_units.mean()) if len(b) else np.nan})
    return pd.DataFrame(rows)


def departure_slope(d, dep='departure16'):
    """b in logit P(home) = logit(q) + b*d (Newton), with a cluster-robust SE by week (H7)."""
    k = d.y.notna().to_numpy()
    y, off = d.y.to_numpy(float)[k], logit(d.q.to_numpy(float)[k])
    x, cl = d[dep].to_numpy(float)[k], d.cluster.to_numpy()[k]
    if k.sum() < 2 or np.sum(x*x) < 1e-12: return np.nan, np.nan, int(k.sum())
    b = 1.
    for _ in range(100):
        p = expit(off+b*x); H = np.sum(p*(1-p)*x*x); step = np.sum((y-p)*x)/H; b += step
        if abs(step) < 1e-12: break
    p = expit(off+b*x); H = np.sum(p*(1-p)*x*x)
    se = np.sqrt((pd.Series((y-p)*x).groupby(cl).sum()**2).sum())/H
    return float(b), float(se), int(k.sum())


def h7(d):
    """Pre-registered H7: departure slope, high-total band minus low-total band."""
    hi = departure_slope(d[context_mask(d.total_line, 'total_high')])
    lo = departure_slope(d[context_mask(d.total_line, 'total_low')])
    delta, se = hi[0]-lo[0], float(np.hypot(hi[1], lo[1]))
    if min(hi[2], lo[2]) < 30: verdict = 'no verdict before 30 graded games per band'
    elif np.isfinite(se) and delta >= 2*se: verdict = 'supported (delta >= 2 SE)'
    elif min(hi[2], lo[2]) >= 60 and delta <= 0: verdict = 'falsified (both bands >= 60, delta <= 0)'
    else: verdict = 'unresolved'
    return {'b_high': hi[0], 'se_high': hi[1], 'n_high': hi[2], 'b_low': lo[0], 'se_low': lo[1], 'n_low': lo[2],
            'delta': delta, 'se': se, 'verdict': verdict}


# --- bases -----------------------------------------------------------------------------------------

def _totals():
    return pd.read_csv(TOTALS)[['game_id', 'total_line']]


def _refit(pack, games):
    """v1.16 refit before every week from earlier pack rows only (the production weekly fit)."""
    out = []
    for (y, w), g in games.groupby(['season', 'week']):
        train = pack[m.before(pack, int(y), int(w))]
        if not m.before(train, int(y), int(w)).all(): raise ValueError('Training includes current/future week')
        fit = m.fit_composite(train, RECIPE, int(y), int(w))
        out.append(pd.DataFrame({'game_id': g.game_id.to_numpy(), 'p16': m.apply_fit(g, fit)}))
    return pd.concat(out, ignore_index=True)


def discovery():
    oos = pd.read_csv(OOS_PRED)[['game_id', 'production']].rename(columns={'production': 'p16'})
    pack = pd.read_csv(OOS_PACK)
    a = pack.merge(oos, on='game_id', how='inner', validate='one_to_one')
    t36 = pd.read_csv(T36_PACK)
    ev = t36[t36.season.isin([2021, 2022])]
    b = ev.merge(_refit(t36, ev), on='game_id', validate='one_to_one')
    retro = pd.read_csv(RETRO)[['game_id', 'model_wp']]
    chk = prepare(b.merge(_totals(), on='game_id', how='left')).merge(retro, on='game_id', validate='one_to_one')
    err = float(np.max(np.abs(chk.p-chk.model_wp)))
    if err > 1e-9: raise ValueError(f'2021-22 refit does not reproduce retro_ledger v1.18 (max error {err:.2e})')
    d = pd.concat([a, b], ignore_index=True).merge(_totals(), on='game_id', how='left', validate='one_to_one')
    return prepare(d), {'reproduction_2021_22_max_error': err}


def confirmation():
    h = pd.read_csv(HELDOUT).rename(columns={'model_wp': 'p16'})
    return prepare(h.merge(_totals(), on='game_id', how='left', validate='one_to_one'))


def diagnostic():
    t36 = pd.read_csv(T36_PACK)
    ev = t36[(t36.season == 2026) & t36['home won'].notna()]
    if not len(ev): return None
    d = ev.merge(_refit(t36, ev), on='game_id', validate='one_to_one')
    return prepare(d.merge(_totals(), on='game_id', how='left', validate='one_to_one'))


def gates(disc, conf):
    """Published totals: 2017-20 1,017 bets -0.42u; 2023-25 812 bets +29.06u."""
    out = {}
    for name, d, n, u in (('2017-20', disc[disc.season <= 2020], 1017, -.42), ('2023-25', conf, 812, 29.06)):
        b = d[d.bet]
        out[name] = {'bets': int(len(b)), 'units': round(float(b.units.sum()), 2)}
        if len(b) != n or abs(b.units.sum()-u) > .006:
            raise ValueError(f'{name} does not match the published totals: {out[name]}')
    return out


# --- forward ---------------------------------------------------------------------------------------

def forward_frame(revision, signature, ledger=LEDGER, view=LEDGER_VIEW, h5=H5_TOTALS):
    """First snapshot per game of one experiment, games from 2026 week 6 on, with inputs from the
    snapshot, q from its moneylines, outcomes from the regenerated ledger view and the lock total."""
    recs = [json.loads(line) for line in Path(ledger).read_text().splitlines() if line.strip()]
    rows = []
    for r in recs:
        if r.get('revision') != revision or not str(r.get('experiment', '')).startswith(signature): continue
        if (int(r['season']), int(r['week'])) < FORWARD_FIRST: continue
        rows.append({'experiment': r['experiment'], 'game_id': r['game_id'], 'season': int(r['season']),
                     'week': int(r['week']), 'generated_utc': r['generated_utc'], 'p16': np.nan, 'p_snap': r['model_wp'],
                     'home_moneyline': r.get('home_moneyline'), 'away_moneyline': r.get('away_moneyline'),
                     **{k: (np.nan if v is None else v) for k, v in (r.get('model_inputs') or {}).items()}})
    cols = ['experiment', 'game_id', 'season', 'week', 'generated_utc', 'p16', 'p_snap', 'home_moneyline', 'away_moneyline']
    f = pd.DataFrame(rows, columns=cols if not rows else None)
    if not len(f): return f
    f = f.sort_values('generated_utc').drop_duplicates(['experiment', 'game_id'])  # first snapshot only
    v = pd.read_csv(view)[['experiment', 'game_id', 'home won']] if Path(view).exists() else pd.DataFrame(columns=['experiment', 'game_id', 'home won'])
    f = f.merge(v, on=['experiment', 'game_id'], how='left')
    tot = pd.DataFrame([json.loads(line) for line in Path(h5).read_text().splitlines() if line.strip()]) if Path(h5).exists() else pd.DataFrame()
    lock = tot.drop_duplicates('game_id')[['game_id', 'total_line']] if len(tot) else pd.DataFrame(columns=['game_id', 'total_line'])
    f = f.merge(lock, on='game_id', how='left').merge(_totals().rename(columns={'total_line': 'sched_total'}), on='game_id', how='left')
    f['total_line'] = f.total_line.fillna(f.sched_total)
    return f


def forward_prepare(f, penalized):
    """Snapshot probability is the model's own; v1.18 rows are already penalized."""
    d = f.copy(); d['p16'] = d.p_snap
    d = prepare(d)
    if not penalized: d['p'] = d.p16; d['departure'] = d.departure16
    else: d['p'] = d.p_snap; d['departure'] = logit(d.p)-logit(d.q)
    b = m.flat_bets(d.assign(model_wp=d.p)); d['units'] = b.units; d['side'] = b.side
    return d


def forward_verdict(z_dir, n, k):
    if n < 30 or not np.isfinite(z_dir): return 'no verdict before 30 graded games in the context'
    if z_dir >= norm.ppf(1-.05/k): return 'supported'
    if n >= 100 and z_dir <= 0: return 'falsified'
    return 'unresolved'


def run_forward():
    res = json.loads((OUT/'results.json').read_text())
    trends = res['forward_set']
    print(f'Test 37 forward (protocol {PROTOCOL_COMMIT}; rules in research/PREREGISTRATION.md, H7 and H8)')
    f8 = forward_frame(*FORWARD['H8'])
    d8 = forward_prepare(f8, penalized=True) if len(f8) else None
    print(f'\nH8: first v1.18 snapshots from 2026 week 6: {0 if d8 is None else len(d8)} rows, '
          f'{0 if d8 is None else int(d8.y.notna().sum())} graded binary')
    for t in trends:
        if d8 is None or not len(d8):
            print(f"  {CONTEXT_LABEL[t['context']]} x {t['input']}: no rows yet"); continue
        sub = d8[context_mask(d8.total_line, t['context'])]
        c = cell(sub, t['input'])
        z_dir = np.sign(t['z_d'])*c['z'] if np.isfinite(c['z']) else np.nan
        print(f"  {CONTEXT_LABEL[t['context']]} x {t['input']}: n={c['n']}, z_F*={z_dir:+.2f}, "
              f"effect/SD {c['effect_per_sd']:+.3f}; {forward_verdict(z_dir, c['n'], len(trends))}")
        for w in wrong_pick_view(d8, t['context'], t['input'], t['cuts']):
            print(f"      {w['third']:>6} third: {w['bets']} bets, wins - expected {w['wins_minus_expected']:+.2f}, "
                  f"{w['units']:+.2f}u (favorite {w['fav_units']:+.2f}u)")
    f7 = forward_frame(*FORWARD['H7'])
    if len(f7):
        s = h7(forward_prepare(f7, penalized=False))
        print(f"\nH7 (v1.16 sample): b_high {s['b_high']:+.2f} ± {s['se_high']:.2f} (n={s['n_high']}), "
              f"b_low {s['b_low']:+.2f} ± {s['se_low']:.2f} (n={s['n_low']}), delta {s['delta']:+.2f} ± {s['se']:.2f}; {s['verdict']}")
    else:
        print('\nH7 (v1.16 sample): no rows yet')
    print('\nJudged only at the season checkpoints; interim numbers are not acted on.')


# --- replication on 2015-16 (protocol addendum) ----------------------------------------------------

REPLICATION = {'2015-16': (2015, 2016), '2014 (sensitivity)': (2014,)}
REPLICATION_PRIMARY = '2015-16'
REPLICATION_COMMIT = '816f35c'


def replication_basis(seasons):
    """v1.16 refit before every week from earlier pack rows only (training from 2013), v1.18 by the
    penalty; the same prepare() as every other basis."""
    pack = pd.read_csv(OOS_PACK)
    ev = pack[pack.season.isin(seasons)]
    d = ev.merge(_refit(pack, ev), on='game_id', validate='one_to_one')
    return prepare(d.merge(_totals(), on='game_id', how='left', validate='one_to_one'))


def replication_gate():
    """The pack and the weekly refit must reproduce the published 2017-20 forecasts."""
    pack, pred = pd.read_csv(OOS_PACK), pd.read_csv(OOS_PRED)
    ev = pack[pack.game_id.isin(pred.game_id)]
    r = _refit(pack, ev).merge(pred[['game_id', 'production']], on='game_id', validate='one_to_one')
    err = float(np.nanmax(np.abs(r.p16-r.production)))
    if len(r) != len(pred) or err > 1e-9: raise ValueError(f'Pack refit does not reproduce 2017-20 ({err:.2e})')
    return err


def replication_verdict(z_dir, k):
    if not np.isfinite(z_dir): return 'no estimate'
    if z_dir >= norm.ppf(1-.05/k): return 'replicated'
    return 'direction holds' if z_dir > 0 else 'reversed'


def h7_replication_verdict(s):
    if not (np.isfinite(s['delta']) and np.isfinite(s['se'])): return 'no estimate'
    if s['delta'] >= 2*s['se']: return 'supported'
    return 'contradicted' if s['delta'] <= 0 else 'unresolved'


def run_replication(out=OUT):
    res = json.loads((OUT/'results.json').read_text())
    trends, k = res['forward_set'], len(res['forward_set'])
    gate = replication_gate()
    rep = {'protocol_addendum_commit': REPLICATION_COMMIT, 'reproduction_2017_20_max_error': gate,
           'bar_one_sided': float(norm.ppf(1-.05/k)), 'bases': {}}
    for name, seasons in REPLICATION.items():
        d = replication_basis(seasons)
        rows = []
        for t in trends:
            c = cell(d[context_mask(d.total_line, t['context'])], t['input'])
            z_dir = float(np.sign(t['z_d'])*c['z'])
            rows.append({**t, 'n': c['n'], 'z_dir': z_dir, 'effect_per_sd': c['effect_per_sd'],
                         'verdict': replication_verdict(z_dir, k) if name == REPLICATION_PRIMARY else 'sensitivity only',
                         'wrong_picks': wrong_pick_view(d, t['context'], t['input'], t['cuts'])})
        s16 = h7(d); s18 = h7(d.assign(departure16=d.departure))
        s16['replication_verdict'] = h7_replication_verdict(s16) if name == REPLICATION_PRIMARY else 'sensitivity only'
        rep['bases'][name] = {'seasons': list(seasons), 'binary_games': int(d.y.notna().sum()), 'trends': rows,
                              'h7': {'v1.16': s16, 'v1.18': s18},
                              'roi_by_context': json.loads(roi_by_context(d).to_json(orient='records')),
                              'll_gain_vs_market': float(np.nanmean(np.where(d.y.notna(),
                                  -(d.y*np.log(d.q)+(1-d.y)*np.log(1-d.q))+(d.y*np.log(d.p)+(1-d.y)*np.log(1-d.p)), np.nan)))}
    (out/'replication_2015_16.json').write_text(json.dumps(rep, indent=2, allow_nan=True))
    write_replication_report(rep, res, out)
    return rep


def write_replication_report(rep, res, out):
    P = rep['bases'][REPLICATION_PRIMARY]
    L = ['# Test 37 replication: the H8 trends and H7 on never-scored 2015-16', '',
         f"Protocol addendum in [RESIDUAL_TRENDS.md](../RESIDUAL_TRENDS.md), pushed (`{REPLICATION_COMMIT}`) before any "
         "2013-16 forecast was compared with an outcome. Nothing was re-selected: the four trends are Test 37's forward set "
         "and H7 is as registered. A backward replication; it does not replace the forward test.", '',
         f"Basis: 2015-16 regular seasons, {P['binary_games']} binary games; v1.16 refit before every week from earlier rows "
         f"of the frozen 2013-20 pack (training from 2013), v1.18 by the favorite penalty. The same refit reproduces the "
         f"published 2017-20 forecasts to {rep['reproduction_2017_20_max_error']:.1e}. 2014 is a sensitivity basis "
         "(trained on 190 games of 2013) and decides nothing.", '',
         '## Trends (z in the discovery direction; positive = the trend continues)', '',
         f"Replicated at z >= {rep['bar_one_sided']:.2f} (one-sided, Bonferroni over 4).", '',
         '| Context x input | z 2017-22 | z 2023-25 | z 2015-16 | Effect/SD 2015-16 | Verdict | z 2014 (sensitivity) |',
         '|---|---:|---:|---:|---:|---|---:|']
    sens = {f"{t['context']}|{t['input']}": t for t in rep['bases']['2014 (sensitivity)']['trends']}
    for t in P['trends']:
        s = sens[f"{t['context']}|{t['input']}"]
        L.append(f"| {CONTEXT_LABEL[t['context']]} x `{t['input']}` | {_f(t['z_d'])} | {_f(t['z_c_dir'])} | {_f(t['z_dir'])} | "
                 f"{_f(t['effect_per_sd'], '+.3f')} | {t['verdict']} | {_f(s['z_dir'])} |")
    L += ['', '## Wrong picks by third of the input signed toward the model\'s side (2017-22 cut points), 2015-16', '',
          '| Context x input | Third | Bets | Wins - expected | Units (same-row favorite) |', '|---|---|---:|---:|---:|']
    for t in P['trends']:
        for w in t['wrong_picks']:
            L.append(f"| {CONTEXT_LABEL[t['context']]} x `{t['input']}` | {w['third']} | {w['bets']} | {w['wins_minus_expected']:+.1f} | "
                     f"{w['units']:+.2f} ({w['fav_units']:+.2f}) |")
    L += ['', '## H7: departure slope, high-total band minus low-total band', '',
          '| Basis | Model | b high (n) | b low (n) | Delta ± SE | Verdict |', '|---|---|---:|---:|---:|---|']
    for name, b in rep['bases'].items():
        for mdl, s in b['h7'].items():
            v = s.get('replication_verdict', 'secondary') if mdl == 'v1.16' else 'secondary'
            L.append(f"| {name} | {mdl} | {_f(s['b_high'])} ± {s['se_high']:.2f} ({s['n_high']}) | {_f(s['b_low'])} ± {s['se_low']:.2f} "
                     f"({s['n_low']}) | {_f(s['delta'])} ± {s['se']:.2f} | {v} |")
    L += ['', 'History for comparison (v1.16): 2017-22 delta ' + _f(res['h7_history']['discovery']['v1.16']['delta']) + ' ± '
          + f"{res['h7_history']['discovery']['v1.16']['se']:.2f}; 2023-25 " + _f(res['h7_history']['confirmation']['v1.16']['delta'])
          + f" ± {res['h7_history']['confirmation']['v1.16']['se']:.2f}.", '',
          '## Flat 1u ROI by context (goal metric; v1.18 and v1.16 make the same bets)', '',
          '| Basis | Context | W-L-P | Units | ROI ± SE | Null | Same-row favorite |', '|---|---|---:|---:|---:|---:|---:|']
    for name, b in rep['bases'].items():
        for r in b['roi_by_context']:
            L.append(f"| {name} | {CONTEXT_LABEL[r['context']]} | {r['w']}-{r['l']}-{r['p']} | {r['units']:+.2f} | "
                     f"{100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} | {100*r['null']:+.2f}% | {r['fav_units']:+.2f}u ({100*r['fav_roi']:+.2f}%) |")
        L.append(f"| {name} | log-loss gain vs market, all games (v1.18) | | | {b['ll_gain_vs_market']:+.5f} | | |")
    L += ['', 'Limits: older seasons with different rules, play styles and pre-2017 data quality; 2015-16 is a third '
          'basis, never pooled with 2017-22 or 2023-25. Expected z if a trend were real at its discovery size was 1.0-1.7 '
          '(protocol), so "direction holds" is the likely best case and "reversed" counts against a trend.', '',
          'Run: `python research/residual_trends.py --replicate`.']
    (out/'REPLICATION_2015_16.md').write_text('\n'.join(L)+'\n')


# --- history ---------------------------------------------------------------------------------------

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    disc, info = discovery(); conf = confirmation(); diag = diagnostic()
    info['gates'] = gates(disc, conf)
    grids = {}
    for basis, d in (('discovery', disc), ('confirmation', conf), ('diagnostic', diag)):
        if d is None: continue
        for prob in ('p', 'p16'):
            grids[(basis, prob)] = scan(d, prob).assign(basis=basis, model='v1.18' if prob == 'p' else 'v1.16')
    pd.concat(grids.values(), ignore_index=True).to_csv(out/'scan.csv', index=False, float_format='%.6g')
    cands = select(grids[('discovery', 'p')])
    conf_tab, bar = confirm(cands, grids[('confirmation', 'p')])
    if diag is not None:
        dg = grids[('diagnostic', 'p')][['context', 'input', 'n', 'z']].rename(columns={'n': 'n_2026', 'z': 'z_2026'})
        conf_tab = conf_tab.merge(dg, on=['context', 'input'], how='left')
    v16 = {b: grids[(b, 'p16')][['context', 'input', 'z']] for b in ('discovery', 'confirmation')}
    conf_tab = conf_tab.merge(v16['discovery'].rename(columns={'z': 'z_d_v116'}), on=['context', 'input'], how='left')
    conf_tab = conf_tab.merge(v16['confirmation'].rename(columns={'z': 'z_c_v116'}), on=['context', 'input'], how='left')
    fwd = forward_set(conf_tab)
    views = {}
    for t in conf_tab.itertuples():
        cuts = tercile_cuts(disc, t.context, t.input)
        views[f'{t.context}|{t.input}'] = {'cuts': cuts, 'discovery': wrong_pick_view(disc, t.context, t.input, cuts),
                                           'confirmation': wrong_pick_view(conf, t.context, t.input, cuts)}
    conf_tab.to_csv(out/'candidates.csv', index=False, float_format='%.6g')
    roi = {b: roi_by_context(d) for b, d in (('discovery', disc), ('confirmation', conf), ('diagnostic', diag)) if d is not None}
    h7s = {b: {'v1.16': h7(d), 'v1.18': h7(d.assign(departure16=d.departure))} for b, d in
           (('discovery', disc), ('confirmation', conf)) }
    h7s['2017-20 only'] = {'v1.16': h7(disc[disc.season <= 2020])}
    results = {'protocol': 'research/RESIDUAL_TRENDS.md', 'protocol_commit': PROTOCOL_COMMIT, 'bases': BASIS,
               'cells_per_basis': len(CONTEXTS)*len(INPUTS), 'min_z': MIN_Z, 'max_k': MAX_K,
               'confirmation_bar_one_sided': bar, 'candidates': json.loads(conf_tab.to_json(orient='records')),
               'forward_set': [{'context': r.context, 'input': r.input, 'z_d': float(r.z_d), 'z_c_dir': float(r.z_c_dir),
                                'cuts': views[f'{r.context}|{r.input}']['cuts']} for r in fwd.itertuples()],
               'wrong_pick_views': views, 'roi_by_context': {b: json.loads(t.to_json(orient='records')) for b, t in roi.items()},
               'h7_history': h7s, 'binary_games': {b: int(d.y.notna().sum()) for b, d in
                                                   (('discovery', disc), ('confirmation', conf), ('diagnostic', diag)) if d is not None},
               **info}
    (out/'results.json').write_text(json.dumps(results, indent=2, allow_nan=True))
    prov = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/'research/RESIDUAL_TRENDS.md', ROOT/'nfl_model.py',
                                                       OOS_PRED, OOS_PACK, T36_PACK, HELDOUT, RETRO, TOTALS)}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2))
    write_report(results, grids, roi, out)
    return results


def _f(x, fmt='+.2f'):
    return 'n/a' if x is None or not np.isfinite(x) else format(x, fmt)


def write_report(res, grids, roi, out):
    c = pd.DataFrame(res['candidates'])
    n_conf = int((c.verdict == 'confirmed').sum()) if len(c) else 0
    n_hold = int((c.verdict == 'direction holds').sum()) if len(c) else 0
    L = ['# Test 37: input trends in the model\'s wrong picks, by total context', '',
         f"Protocol: [RESIDUAL_TRENDS.md](../RESIDUAL_TRENDS.md), pushed (`{PROTOCOL_COMMIT}`) before any residual "
         'was computed. Production v1.18, its v1.16 shadow and the ledger are unchanged.', '',
         f"**Result.** {len(c)} of {res['cells_per_basis']} discovery cells reached |z| >= {MIN_Z}. On 2023-25, "
         f"{n_conf} confirmed (one-sided z >= {res['confirmation_bar_one_sided']:.2f}), {n_hold} kept the discovery "
         f"direction without confirming, {len(c)-n_conf-n_hold} reversed. H8 carries {len(res['forward_set'])} forward.", '',
         f"Bases: discovery {res['binary_games']['discovery']} binary games ({BASIS['discovery']}); confirmation "
         f"{res['binary_games']['confirmation']} ({BASIS['confirmation']}).", '',
         'Residual r = y - p with p production v1.18. z > 0: where the input (home minus away) is high, the home team '
         'won more often than the model said, so the model under-weights the input in that context. Effect per SD is '
         'the log-odds per SD of the input the data would add (one Newton step). z is cluster-robust by week.', '',
         '## Candidates (selected on 2017-22, tested on 2023-25)', '',
         '| Context | Input | n D | z D | effect/SD D | n C | z C (discovery direction) | effect/SD C | Verdict | z 2026 | z D / z C under v1.16 |',
         '|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|']
    for r in c.itertuples():
        L.append(f"| {CONTEXT_LABEL[r.context]} | `{r.input}` | {r.n_d} | {_f(r.z_d)} | {_f(r.effect_per_sd_d, '+.3f')} | "
                 f"{r.n_c} | {_f(r.z_c_dir)} | {_f(r.effect_per_sd_c, '+.3f')} | {r.verdict} | "
                 f"{_f(getattr(r, 'z_2026', np.nan))} | {_f(r.z_d_v116)} / {_f(r.z_c_v116)} |")
    L += ['', f"Forward set (H8): " + (', '.join(f"{CONTEXT_LABEL[t['context']]} x `{t['input']}`" for t in res['forward_set']) or 'none') + '.', '',
          '## Wrong picks by third of the input, signed toward the model\'s side', '',
          'Cut points are the 2017-22 terciles of the signed input in that context. "Wins - expected" is the model '
          'side\'s wins minus the wins its own probabilities expected; negative means more wrong picks than the model said.', '']
    for r in c.itertuples():
        v = res['wrong_pick_views'][f'{r.context}|{r.input}']
        L += [f"**{CONTEXT_LABEL[r.context]} x `{r.input}`** (z D {_f(r.z_d)}, z C {_f(r.z_c_dir)}; cuts {v['cuts'][0]:.3g}, {v['cuts'][1]:.3g})", '',
              '| Third | Bets D | Wins - exp D | Units D (favorite) | Bets C | Wins - exp C | Units C (favorite) |', '|---|---:|---:|---:|---:|---:|---:|']
        for a, b in zip(v['discovery'], v['confirmation']):
            L.append(f"| {a['third']} | {a['bets']} | {a['wins_minus_expected']:+.1f} | {a['units']:+.2f} ({a['fav_units']:+.2f}) | "
                     f"{b['bets']} | {b['wins_minus_expected']:+.1f} | {b['units']:+.2f} ({b['fav_units']:+.2f}) |")
        L.append('')
    L += ['## Flat 1u ROI by context (goal metric; v1.18 and v1.16 make the same bets)', '',
          '| Basis | Context | W-L-P | Units | ROI ± SE | Null | Same-row favorite |', '|---|---|---:|---:|---:|---:|---:|']
    for b, t in roi.items():
        for r in t.itertuples():
            L.append(f"| {b} | {CONTEXT_LABEL[r.context]} | {r.w}-{r.l}-{r.p} | {r.units:+.2f} | {100*r.roi:+.2f}% ± {100*r.roi_se:.2f} | "
                     f"{100*r.null:+.2f}% | {r.fav_units:+.2f}u ({100*r.fav_roi:+.2f}%) |")
    L += ['', '## Strongest cells on each basis (v1.18), for context', '']
    for b in ('discovery', 'confirmation'):
        g = grids[(b, 'p')].assign(a=lambda t: t.z.abs()).sort_values('a', ascending=False).head(8)
        L.append(f"*{b}*: " + '; '.join(f"{CONTEXT_LABEL[r.context]} x `{r.input}` {r.z:+.2f}" for r in g.itertuples()))
        L.append('')
    n_abs2 = {b: int((grids[(b, 'p')].z.abs() >= 2).sum()) for b in ('discovery', 'confirmation')}
    L += [f"Cells at |z| >= 2: discovery {n_abs2['discovery']}, confirmation {n_abs2['confirmation']} of "
          f"{res['cells_per_basis']} (about 6 expected with no effect, fewer independent).", '',
          '## H7 on history (source figures; the forward test is in PREREGISTRATION.md)', '',
          '| Basis | Model | b high (n) | b low (n) | Delta ± SE |', '|---|---|---:|---:|---:|']
    for b, d in res['h7_history'].items():
        for mdl, s in d.items():
            L.append(f"| {b} | {mdl} | {_f(s['b_high'])} ± {s['se_high']:.2f} ({s['n_high']}) | {_f(s['b_low'])} ± {s['se_low']:.2f} ({s['n_low']}) | "
                     f"{_f(s['delta'])} ± {s['se']:.2f} |")
    g = res['gates']
    L += ['', '## Reproduction and limits', '',
          f"2021-22 refit vs `retro_ledger.csv` (v1.18): max error {res['reproduction_2021_22_max_error']:.1e}. "
          f"Published totals matched: 2017-20 {g['2017-20']['bets']} bets {g['2017-20']['units']:+.2f}u; "
          f"2023-25 {g['2023-25']['bets']} bets {g['2023-25']['units']:+.2f}u.",
          'All bases are exposed history; the total bands were chosen after aggregate slices were seen. 120 cells per '
          'basis, correlated and nested, so some discovery cells pass by luck; confirmation is one-sided and Bonferroni '
          'over the candidates. A confirmed trend changes nothing by itself; acting on it is a new REVISION and the '
          'owner\'s decision. Full grids for both models and all bases: `scan.csv`.', '',
          'Run: `python research/residual_trends.py`; forward: `--forward`.']
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--forward', action='store_true', help='grade H8 and H7 on the native ledger')
    ap.add_argument('--replicate', action='store_true', help='the H8 trends and H7 on never-scored 2015-16')
    a = ap.parse_args()
    run_forward() if a.forward else run_replication() if a.replicate else run()
