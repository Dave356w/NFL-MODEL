"""Test 36: one-at-a-time sweep of the model's shrinkage settings; see SHRINKAGE_SWEEP.md.

    python research/shrinkage_sweep.py --prepare [--inputs DIR]   # download raw inputs, score nothing
    python research/shrinkage_sweep.py --select  [--inputs DIR]   # 2023-25 selection run
    python research/shrinkage_sweep.py --confirm [--inputs DIR]   # one-time 2017-20 confirmation

Each arm changes exactly one nfl_model setting inside this process, rebuilds every
feature it touches from raw inputs (normalization references included), then refits
the fixed v1.16 recipe before every evaluation week on strictly earlier games.
"""
import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'research'))
import out_of_sample_2017_2020 as o  # noqa: E402

m, s = o.m, o.s
RECIPE = m.LEGACY_PRODUCT_RECIPE
CONTEXTS = o.CONTEXTS
FEATURES = o.FEATURES
OUT = ROOT/'research/shrinkage_sweep_results'
DEFAULT_INPUTS = Path.home()/'shrinkage_sweep_inputs'
ALL_YEARS = list(range(2013, 2026))
# knob -> (nfl_model attribute, production value, alternatives)
KNOBS = {'qb_prior': ('QB_PRIOR_DROPBACKS', 150., (75., 300., 600.)),
         'pseudo_games': ('PRIOR_EQUIVALENT_GAMES', 4., (2., 8., 16.)),
         'retention': ('OFFSEASON_RETENTION', .5, (.25, .75)),
         'fit_half_life': ('FIT_HALF_LIFE_SEASONS', 2., (1., 4.))}
FEATURE_KNOBS = ('qb_prior', 'pseudo_games', 'retention')  # fit_half_life only changes the weekly fit
# window: (input seasons, evaluation seasons, held-out seasons)
WINDOWS = {'select': (list(range(2019, 2026)), (2021, 2025), (2023, 2025)),
           'confirm': (list(range(2013, 2021)), (2017, 2020), (2017, 2020))}
REFERENCE = {'select': (ROOT/'research/production_adoption_results/historical_reproduction.csv', 'production_probability'),
             'confirm': (ROOT/'research/out_of_sample_results/predictions.csv', 'production')}
LEVEL_FLOOR = .9875


def arms():
    out = {'production': None}
    for knob, (_, prod, alts) in KNOBS.items():
        for v in alts: out[f'{knob}={v:g}'] = (knob, v)
    return out


def check_values():
    for knob, (attr, prod, _) in KNOBS.items():
        if getattr(m, attr) != prod: raise ValueError(f'{attr} is {getattr(m, attr)}, protocol expects {prod}')


def prepare(inputs):
    """Download and pickle raw inputs. No arm is built or scored."""
    o.YEARS = ALL_YEARS
    schedules, boxes, qb, a = o.load_inputs(inputs)
    with (inputs/'raw_inputs.pkl').open('wb') as f:
        pickle.dump({'schedules': schedules, 'boxes': boxes, 'qb': qb, 'a': a,
                     'peak_repairs': list(o.PEAK_REPAIRS)}, f)
    print({k: len(v) for k, v in (('schedules', schedules), ('boxes', boxes), ('qb', qb))}, flush=True)


class setting:
    """Temporarily set one nfl_model attribute."""
    def __init__(self, attr, value): self.attr, self.value = attr, value
    def __enter__(self):
        self.old = getattr(m, self.attr); setattr(m, self.attr, self.value)
    def __exit__(self, *exc): setattr(m, self.attr, self.old)


def load_raw(inputs):
    with (inputs/'raw_inputs.pkl').open('rb') as f: return pickle.load(f)


def window_features(raw, years):
    """Features for one window from its own input seasons, under the current settings."""
    keep = lambda d: d[d.season.isin(years)].copy()
    av = o.availability(raw['schedules'], raw['qb'], raw['a'], years)
    f, refs = o.build_features(keep(raw['schedules']), keep(raw['boxes']), av)
    ok = ((refs.max_reference_season < refs.season)
          | ((refs.max_reference_season == refs.season) & (refs.max_reference_week < refs.week))).all()
    if not ok: raise ValueError('Future normalization reference')
    return f


def walk_forward(f, seasons):
    """Fixed v1.16 recipe refit before every evaluation week on strictly earlier eligible games."""
    train_mask = o.eligible(f)
    scored = (f.season.between(*seasons) & f.ready.astype(bool) & f['home won'].isin([0., .5, 1.])
              & np.isfinite(f.q) & np.isfinite(f[CONTEXTS]).all(axis=1))
    out = pd.Series(np.nan, index=f.index[scored])
    for (year, week), rows in f[scored].groupby(['season', 'week'], sort=True):
        train = f[train_mask & m.before(f, year, week)]
        fitted = o.fit_arm(train, int(year), int(week), 'production')
        if (fitted['training_max_season'], fitted['training_max_week_in_latest_season']) >= (year, week):
            raise ValueError('Training cutoff is not strictly prior')
        out.loc[rows.index] = m.apply_fit(f.loc[rows.index], fitted)
    if not np.isfinite(out).all(): raise ValueError('Incomplete predictions')
    return f.loc[scored, o.p.BASE_COLS].assign(prob=out.to_numpy())


def run_arms(raw, window, names):
    """{arm: predictions frame} for one window."""
    years, seasons, _ = WINDOWS[window]
    base = window_features(raw, years)
    preds = {}
    for name in names:
        spec = arms()[name]
        if spec is None: preds[name] = walk_forward(base, seasons)
        else:
            attr = KNOBS[spec[0]][0]
            with setting(attr, spec[1]):
                f = base if spec[0] not in FEATURE_KNOBS else window_features(raw, years)
                preds[name] = walk_forward(f, seasons)
        print(f'{window}: {name} done', flush=True)
    return preds


def reproduce(window, prod):
    path, col = REFERENCE[window]
    ref = pd.read_csv(path).set_index('game_id')[col]
    mine = prod.set_index('game_id').prob
    shared = mine.index.intersection(ref.index)
    if len(shared) < .95*len(ref): raise ValueError(f'Reproduction covers {len(shared)} of {len(ref)} games')
    err = float((mine[shared]-ref[shared]).abs().max())
    if err >= 1e-7: raise ValueError(f'Production reproduction failed: max error {err}')
    return {'games': int(len(shared)), 'max_error': err}


def log_loss(y, p):
    p = np.clip(np.asarray(p, float), 1e-12, 1-1e-12)
    return -(y*np.log(p)+(1-y)*np.log1p(-p))


def table(preds):
    """One frame: base columns, each arm's probability, and the v1.18 favorite-penalized versions."""
    names = list(preds)
    t = preds['production'].drop(columns='prob').copy()
    for n in names:
        if not preds[n].game_id.equals(t.game_id): raise ValueError(f'{n} scored different rows')
        t[n] = preds[n].prob.to_numpy()
        t[f'{n}|fp'] = m.favorite_penalized_wp(t[n].to_numpy(), t.q.to_numpy())
    t['market'] = t.q
    return t


def compare(t, arms_, level, suffix=''):
    """Same-row flat 1u ROI and proper scores per arm, and paired differences vs production."""
    cols = [a+suffix for a in arms_]
    bets = {a: m.flat_bets(t, c) for a, c in zip(arms_, cols)}
    bets['market favorite'] = m.flat_bets(t, 'market')
    common = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    proper = t['home won'].isin([0., 1.]).to_numpy()
    y = t['home won'].to_numpy(float)
    groups = (t.season.astype(int).astype(str)+'_'+t.week.astype(int).astype(str)).to_numpy()
    ll = {a: log_loss(y, t[c]) for a, c in zip(arms_, cols)}
    ll['market favorite'] = log_loss(y, t.market)
    rows, pairs = [], []
    for a in [*arms_, 'market favorite']:
        c = 'market' if a == 'market favorite' else a+suffix
        rows.append({'arm': a, **m.roi_summary(bets[a].loc[common]), 'log_loss': float(ll[a][proper].mean()),
                     'brier': float(((t[c]-t['home won'])**2).to_numpy()[proper].mean())})
        if a in ('production', 'market favorite'): continue
        du = (bets[a].units-bets['production'].units).to_numpy()[common]
        dl = (ll['production']-ll[a])[proper]
        pairs.append({'arm': a, 'level': level, 'll_gain': float(dl.mean()),
                      'll_gain_ci': o.p.cluster_interval(dl, groups[proper], level),
                      'roi_delta': float(du.mean()), 'roi_delta_ci': o.p.cluster_interval(du, groups[common], level),
                      'side_flips': int(((t[a+suffix] > .5) != (t['production'+suffix] > .5)).to_numpy()[common].sum())})
    seasons = []
    for yr in sorted(t.season.unique()):
        mk = (t.season == yr).to_numpy()
        seasons.append({'season': int(yr), **{a: {'units': float(bets[a].units[common & mk].sum()),
                                                   'log_loss': float(ll[a][proper & mk].mean())} for a in arms_}})
    return {'bets': int(common.sum()), 'proper_games': int(proper.sum()), 'results': rows, 'pairs': pairs, 'seasons': seasons}


def knob_values(knob):
    attr, prod, alts = KNOBS[knob]
    return ['production', *[f'{knob}={v:g}' for v in alts]]


def chosen_values(t, through=None):
    """Per knob, the arm with the lowest log loss on evaluation seasons < through (all if None).
    Exact ties go to production."""
    d = t if through is None else t[t.season < through]
    y = d['home won'].to_numpy(float); proper = d['home won'].isin([0., 1.]).to_numpy()
    out = {}
    for knob in KNOBS:
        scores = {a: float(log_loss(y, d[a])[proper].mean()) for a in knob_values(knob)}
        best = min(scores.values())
        out[knob] = {'chosen': 'production' if scores['production'] == best else min(scores, key=scores.get),
                     'losses': scores}
    return out


def annual_selected(t, held):
    """Per knob, a column forecasting each held-out season with the value chosen on earlier seasons."""
    picks = []
    for yr in range(held[0], held[1]+1):
        c = chosen_values(t, through=yr)
        for knob, v in c.items():
            t.loc[t.season == yr, f'selected:{knob}'] = t.loc[t.season == yr, v['chosen']]
            t.loc[t.season == yr, f'selected:{knob}|fp'] = t.loc[t.season == yr, v['chosen']+'|fp']
        picks.append({'season': yr, **{k: v['chosen'] for k, v in c.items()}})
    return picks


def verdict(chosen, pair):
    if chosen == 'production': return 'keep production (production chosen)'
    lo, hi = pair['ll_gain_ci']
    if lo > 0: return 'candidate for a new REVISION (owner decides)'
    if hi < 0: return 'keep production (arm worse, interval excludes zero)'
    return 'unresolved, keep production'


def save(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT/name).write_text(json.dumps(obj, indent=1, allow_nan=False, default=float)+'\n')


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def select(inputs):
    raw = load_raw(inputs)
    preds = run_arms(raw, 'select', list(arms()))
    repro = reproduce('select', preds['production'])
    t = table(preds)
    lo, hi = WINDOWS['select'][2]
    picks = annual_selected(t, (lo, hi))
    final = chosen_values(t)
    held = t[t.season.between(lo, hi)].reset_index(drop=True)
    names = list(arms())
    sel_cols = [f'selected:{k}' for k in KNOBS]
    res = {'window': 'select', 'held_out': [lo, hi], 'reproduction': repro, 'annual_picks': picks,
           'final_choice': final, 'fixed_arms': compare(held, names, .95),
           'annual_selected': compare(held, ['production', *sel_cols], .95),
           'fixed_arms_v118': compare(held, names, .95, '|fp')}
    OUT.mkdir(parents=True, exist_ok=True)
    held.to_csv(OUT/'select_predictions.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    save('select_results.json', res)
    return res


def confirm(inputs):
    sel = json.loads((OUT/'select_results.json').read_text())
    chosen = {k: v['chosen'] for k, v in sel['final_choice'].items()}
    todo = [a for a in chosen.values() if a != 'production']
    k = max(len(todo), 1); level = max(1-.05/k, LEVEL_FLOOR)
    raw = load_raw(inputs)
    preds = run_arms(raw, 'confirm', ['production', *todo])
    combined = None
    if len(todo) >= 2:
        years, seasons, _ = WINDOWS['confirm']
        specs = [arms()[a] for a in todo]
        ctx = [setting(KNOBS[kn][0], v) for kn, v in specs]
        for c in ctx: c.__enter__()
        try: preds['combined'] = walk_forward(window_features(raw, years), seasons)
        finally:
            for c in reversed(ctx): c.__exit__()
        combined = todo
    repro = reproduce('confirm', preds['production'])
    t = table(preds)
    names = ['production', *todo]
    res = {'window': 'confirm', 'held_out': list(WINDOWS['confirm'][2]), 'reproduction': repro,
           'chosen': chosen, 'level': level, 'primary': compare(t, names, level),
           'v118': compare(t, names, level, '|fp')}
    if combined:
        res['combined'] = {'arms': combined, **compare(t, ['production', 'combined'], .95)}
    pairs = {p_['arm']: p_ for p_ in res['primary']['pairs']}
    res['verdicts'] = {knob: verdict(a, pairs.get(a)) for knob, a in chosen.items()}
    t.to_csv(OUT/'confirm_predictions.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    save('confirm_results.json', res)
    return res


def sensitivity(arm, seeds=20):
    """Post-hoc, not gating: the confirmed arm's 2017-20 interval across bootstrap seeds and a
    week-clustered normal interval, for v1.16 and the v1.18 favorite-penalized forecasts."""
    from scipy.special import ndtri
    t = pd.read_csv(OUT/'confirm_predictions.csv.gz')
    level = json.loads((OUT/'confirm_results.json').read_text())['level']
    proper = t['home won'].isin([0., 1.]).to_numpy(); y = t['home won'].to_numpy(float)
    g = (t.season.astype(str)+'_'+t.week.astype(str)).to_numpy()[proper]
    out, seed0 = {}, o.p.SEED
    try:
        for label, suf in (('v1.16', ''), ('v1.18', '|fp')):
            d = (log_loss(y, t['production'+suf])-log_loss(y, t[arm+suf]))[proper]
            lows = []
            for sd in range(seeds):
                o.p.SEED = sd; lows.append(o.p.cluster_interval(d, g, level)[0])
            a = pd.DataFrame({'v': d, 'g': g}).groupby('g').v.agg(['sum', 'count'])
            mu = float(d.mean()); se = float(np.sqrt(((a['sum']-mu*a['count'])**2).sum())/a['count'].sum())
            z = float(ndtri(.5+level/2))
            out[label] = {'mean': mu, 'cluster_se': se, 'normal_ci': [mu-z*se, mu+z*se],
                          'bootstrap_lower_min': min(lows), 'bootstrap_lower_max': max(lows),
                          'share_of_seeds_excluding_zero': float(np.mean(np.array(lows) > 0)), 'seeds': seeds}
    finally:
        o.p.SEED = seed0
    return out


def write_report():
    sel = json.loads((OUT/'select_results.json').read_text())
    con = json.loads((OUT/'confirm_results.json').read_text())
    cand = [a for k, a in con['chosen'].items() if con['verdicts'][k].startswith('candidate')]
    sens = {a: sensitivity(a) for a in cand}
    save('sensitivity.json', sens)
    pct = lambda x: f'{100*x:+.2f}%'
    iv = lambda c, s=1, f='+.5f': f'[{s*c[0]:{f}}, {s*c[1]:{f}}]'
    def arm_rows(block):
        rows = ['| Arm | W-L-P | Units | ROI ± SE | Null | Log loss | Brier |', '|---|---|---:|---:|---:|---:|---:|']
        for r in block['results']:
            rows.append(f"| {r['arm']} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | {pct(r['roi'])} ± {100*r['roi_se']:.2f} | "
                        f"{pct(r['null_roi'])} | {r['log_loss']:.6f} | {r['brier']:.6f} |")
        return rows
    def pair_rows(block):
        rows = ['| Arm vs production | LL gain [CI] | ROI Δ pts [CI] | Side flips |', '|---|---:|---:|---:|']
        for q in block['pairs']:
            rows.append(f"| {q['arm']} | {q['ll_gain']:+.5f} {iv(q['ll_gain_ci'])} | {100*q['roi_delta']:+.2f} "
                        f"{iv(q['roi_delta_ci'], 100, '+.2f')} | {q['side_flips']} |")
        return rows
    L = ['# Test 36: one-at-a-time shrinkage sweep', '',
         'Protocol: [SHRINKAGE_SWEEP.md](../SHRINKAGE_SWEEP.md), pushed before any arm was built. Stage 1 choices were '
         'committed before any 2017–20 candidate arm was scored. Basis: held-out walk-forward reconstructions '
         '(2023–25 heavily exposed; 2017–20 never used for these settings). Not forward evidence.', '',
         f"Production reproduction: 2023–25 {sel['reproduction']['games']} games, max error {sel['reproduction']['max_error']:.1e}; "
         f"2017–20 {con['reproduction']['games']} games, max error {con['reproduction']['max_error']:.1e}.", '',
         '## Verdicts (2017–20 confirmation, v1.16 forecasts)', '']
    for k, v in con['verdicts'].items():
        L.append(f"* **{k}** → {con['chosen'][k]}: {v}")
    L += ['', f"## Stage 2: 2017–20, {con['primary']['bets']} common bets, {con['primary']['proper_games']} binary games, "
          f"{100*con['level']:.2f}% week-cluster intervals", '', *arm_rows(con['primary']), '', *pair_rows(con['primary']),
          '', 'Same comparisons after the v1.18 favorite penalty (λ = 0.2):', '', *pair_rows(con['v118'])]
    if 'combined' in con:
        c = con['combined']; q = c['pairs'][0]
        L += ['', f"Combined arm ({', '.join(c['arms'])}), descriptive, 95%: LL gain {q['ll_gain']:+.5f} {iv(q['ll_gain_ci'])}, "
              f"ROI Δ {100*q['roi_delta']:+.2f} pts, {q['side_flips']} side flips."]
    L += ['', '| Season | ' + ' | '.join(a for a in con['primary']['seasons'][0] if a != 'season') + ' |',
          '|---|' + '---:|'*(len(con['primary']['seasons'][0])-1)]
    for srow in con['primary']['seasons']:
        L.append(f"| {srow['season']} | " + ' | '.join(f"{v['log_loss']:.5f}" for k, v in srow.items() if k != 'season') + ' |')
    for a, sv in sens.items():
        L += ['', f'### Post-hoc sensitivity for {a} (not gating)', '',
              '| Forecast | LL gain | Cluster SE | Normal interval | Bootstrap lower bound over seeds | Seeds excluding zero |',
              '|---|---:|---:|---:|---:|---:|']
        for lab, x in sv.items():
            L.append(f"| {lab} | {x['mean']:+.5f} | {x['cluster_se']:.5f} | {iv(x['normal_ci'])} | "
                     f"{x['bootstrap_lower_min']:+.6f} to {x['bootstrap_lower_max']:+.6f} | {100*x['share_of_seeds_excluding_zero']:.0f}% of {x['seeds']} |")
    L += ['', f"## Stage 1: 2023–25, {sel['fixed_arms']['bets']} common bets, {sel['fixed_arms']['proper_games']} binary games, 95% intervals", '',
          'Chosen on 2021–25 log loss: ' + ', '.join(f"{k} → {v['chosen']}" for k, v in sel['final_choice'].items()) + '.',
          'Annual picks: ' + '; '.join(f"{p['season']}: " + ', '.join(f"{k}={p[k]}" for k in KNOBS) for p in sel['annual_picks']) + '.',
          '', *arm_rows(sel['fixed_arms']), '', *pair_rows(sel['fixed_arms']), '',
          'Annually selected arms (each season chosen on earlier seasons only):', '', *pair_rows(sel['annual_selected'])]
    (OUT/'REPORT.md').write_text('\n'.join(L)+'\n')


def provenance(inputs):
    files = [ROOT/'research/shrinkage_sweep.py', ROOT/'research/SHRINKAGE_SWEEP.md', ROOT/'nfl_model.py',
             ROOT/'research/out_of_sample_2017_2020.py', *[x for x in OUT.glob('*') if x.name != 'provenance.json']]
    prov = {str(x.relative_to(ROOT)): sha(x) for x in files if x.exists()}
    prov['raw_inputs.pkl (not committed)'] = sha(inputs/'raw_inputs.pkl')
    save('provenance.json', prov)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', type=Path, default=DEFAULT_INPUTS)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare', action='store_true')
    g.add_argument('--select', action='store_true')
    g.add_argument('--confirm', action='store_true')
    g.add_argument('--report', action='store_true', help='rewrite REPORT.md from saved results')
    args = ap.parse_args()
    check_values()
    inputs = args.inputs.resolve()
    if args.report: write_report(); provenance(inputs); raise SystemExit
    if args.prepare: prepare(inputs)
    elif args.select: r = select(inputs); print(json.dumps({k: v['chosen'] for k, v in r['final_choice'].items()}))
    else: r = confirm(inputs); print(json.dumps(r['verdicts'], indent=1))
    if args.confirm: write_report()
    if not args.prepare: provenance(inputs)
