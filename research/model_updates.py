"""Test 39: candidate model updates from Tests 36-38; see MODEL_UPDATES.md.

    python research/model_updates.py

Reads only committed files; no network access. Never writes data/ or the ledger. Development
evidence only: every historical basis informed the candidates.
"""
import contextlib
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import residual_trends as t  # noqa: E402
import feature_importance as fi  # noqa: E402

OUT = ROOT/'research/model_updates_results'
PROTOCOL_COMMIT = 'a35d3e7'
BASE = m.LEGACY_PRODUCT_RECIPE
BASES = fi.BASES
PRIMARY = ('ridge_0.3', 'ridge_1.0', 'shrink_0.5', 'prune_lobo')
DESCRIPTIVE = ('prune_8', 'no_site', 'half_life_4')
LEVEL = 1-.05/len(PRIMARY)
Z = float(norm.ppf(1-(1-LEVEL)/2))
IMPORTANCE = ROOT/'research/feature_importance_results/importance.csv'


def importance_table():
    i = pd.read_csv(IMPORTANCE)
    i = i[i.context == 'all'].copy()
    i['input'] = i.arm.str.replace(' (supplementary)', '', regex=False)
    i = i[i.input.isin(fi.FEATURES)]
    return i.pivot_table(index='input', columns='basis', values='importance_x1000')


def prune_set(basis, imp=None):
    """Inputs (home field included) with negative Test 38 importance on both other bases; for a
    basis outside the three (2014, 2026, native), negative on all three."""
    imp = importance_table() if imp is None else imp
    others = [b for b in BASES if b != basis] if basis in BASES else list(BASES)
    return sorted(imp.index[(imp[others] < 0).all(axis=1)])


def arm_spec(name, basis, imp=None):
    """(recipe, zeroed columns, departure multiplier, fit half-life in seasons)."""
    r, zero, k, hl = dict(BASE), [], 1., m.FIT_HALF_LIFE_SEASONS
    if name == 'ridge_0.3': r.update(ridge=.3, interaction_ridge=.3)
    elif name == 'ridge_1.0': r.update(ridge=1., interaction_ridge=1.)
    elif name == 'shrink_0.5': k = .5
    elif name == 'prune_lobo': zero = prune_set(basis, imp)
    elif name == 'prune_8': zero = sorted(i for i in prune_set('all three', imp) if i != 'site')
    elif name == 'no_site': zero = ['site']
    elif name == 'half_life_4': hl = 4.
    elif name != 'production': raise ValueError(f'Unknown arm {name}')
    return r, zero, k, hl


@contextlib.contextmanager
def fit_half_life(hl):
    old = m.FIT_HALF_LIFE_SEASONS; m.FIT_HALF_LIFE_SEASONS = hl
    try: yield
    finally: m.FIT_HALF_LIFE_SEASONS = old


def shrink(p16, q, k):
    return p16 if k == 1. else expit(logit(q)+k*(logit(p16)-logit(q)))


def weekly(pack, games, recipe, zero, k, hl):
    if zero: pack = pack.assign(**{c: 0. for c in zero}); games = games.assign(**{c: 0. for c in zero})
    out = []
    with fit_half_life(hl):
        for (y, w), g in games.groupby(['season', 'week']):
            train = pack[m.before(pack, int(y), int(w))]
            if not m.before(train, int(y), int(w)).all(): raise ValueError('Training includes current/future week')
            fit = m.fit_composite(train, recipe, int(y), int(w))
            q = m.market_ml_wp(g)
            out.append(pd.DataFrame({'game_id': g.game_id.to_numpy(), 'p16': shrink(m.apply_fit(g, fit), q, k)}))
    return pd.concat(out, ignore_index=True)


def basis_frame(parts, name, basis, imp=None):
    recipe, zero, k, hl = arm_spec(name, basis, imp)
    rows = [games.merge(weekly(pack, games, recipe, zero, k, hl), on='game_id', validate='one_to_one') for pack, games in parts]
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    return t.prepare(d)


def extra_parts():
    oos, t36 = pd.read_csv(t.OOS_PACK), pd.read_csv(t.T36_PACK)
    return {'2014 (sensitivity)': [(oos, oos[oos.season == 2014])],
            '2026 wk1-5 (diagnostic)': [(t36, t36[(t36.season == 2026) & t36['home won'].notna()])]}


def native_frame(name, imp=None):
    """The native week-5 v1.16 snapshots at archived inputs and moneylines, each arm refit on earlier
    pack rows (counterfactual replay, not forward evidence)."""
    recs = [json.loads(line) for line in t.LEDGER.read_text().splitlines() if line.strip()]
    view = pd.read_csv(t.LEDGER_VIEW)[['experiment', 'game_id', 'home won']]
    h5 = pd.DataFrame([json.loads(line) for line in t.H5_TOTALS.read_text().splitlines() if line.strip()]).drop_duplicates('game_id')
    v = [r for r in recs if r['revision'] == 'boxscore-composite-v1.16' and (r['season'], r['week']) < t.FORWARD_FIRST]
    X = pd.DataFrame([{k: (0. if x is None else x) for k, x in r['model_inputs'].items()} for r in v])
    meta = pd.DataFrame([{'experiment': r['experiment'], 'game_id': r['game_id'], 'season': r['season'], 'week': r['week'],
                          'home_moneyline': r['home_moneyline'], 'away_moneyline': r['away_moneyline'],
                          'archived': r['model_wp']} for r in v])
    g = pd.concat([meta, X], axis=1).merge(view, on=['experiment', 'game_id']).merge(h5[['game_id', 'total_line']], on='game_id', how='left')
    pack = pd.read_csv(t.T36_PACK)
    recipe, zero, k, hl = arm_spec(name, 'native', imp)
    g['q'] = m.market_ml_wp(g)
    if zero: pack = pack.assign(**{c: 0. for c in zero}); g = g.assign(**{c: 0. for c in zero})
    with fit_half_life(hl):
        fit = m.fit_composite(pack[m.before(pack, 2026, 5)], recipe, 2026, 5)
    q = m.market_ml_wp(g)
    g['p16'] = shrink(m.apply_fit(g, fit), q, k)
    if name == 'production':
        err = float(np.max(np.abs(g.p16-g.archived)))
        if err > 1e-9: raise ValueError(f'Native replay does not reproduce the archived snapshots ({err:.1e})')
    return t.prepare(g.drop(columns=['experiment']))


# --- comparison ------------------------------------------------------------------------------------

def ll(y, p):
    return -(y*np.log(p)+(1-y)*np.log(1-p))


def compare(prod, arm, basis, name):
    j = prod[['game_id', 'y', 'p', 'units', 'side', 'fav_units', 'null_ev', 'bet', 'total_line', 'cluster']].merge(
        arm[['game_id', 'p', 'units', 'side', 'null_ev']], on='game_id', suffixes=('', '_arm'), validate='one_to_one')
    rows = []
    for ctx in t.CONTEXTS:
        s = j[t.context_mask(j.total_line, ctx)]
        b = s[s.y.notna()]
        gain, se = fi.cmean(ll(b.y, b.p)-ll(b.y, b.p_arm), b.cluster)
        brier = float(((b.p-b.y)**2-(b.p_arm-b.y)**2).mean()) if len(b) else np.nan
        bets = s[s.bet & s.units_arm.notna()]
        u = bets.units_arm
        sm = {'bets': len(u), 'wins': int((u > 0).sum()), 'losses': int((u < 0).sum()), 'pushes': int((u == 0).sum()),
              'units': float(u.sum()), 'roi': float(u.mean()) if len(u) else np.nan,
              'roi_se': float(u.std(ddof=1)/np.sqrt(len(u))) if len(u) > 1 else np.nan, 'null_roi': float(bets.null_ev_arm.mean())}
        flips = bets.side != bets.side_arm
        rows.append({'basis': basis, 'arm': name, 'context': ctx, 'n': len(b), 'll_gain_x1000': 1000*gain, 'se_x1000': 1000*se,
                     'lo_x1000': 1000*(gain-Z*se), 'hi_x1000': 1000*(gain+Z*se), 'brier_gain_x1000': 1000*brier,
                     'bets': sm['bets'], 'w': sm['wins'], 'l': sm['losses'], 'p': sm['pushes'], 'units': sm['units'],
                     'roi': sm['roi'], 'roi_se': sm['roi_se'], 'null': sm['null_roi'],
                     'prod_units': float(bets.units.sum()), 'fav_units': float(bets.fav_units.sum()),
                     'units_vs_prod': float((bets.units_arm-bets.units).sum()), 'side_flips': int(flips.sum()),
                     'flip_units_vs_prod': float((bets.units_arm-bets.units)[flips].sum())})
    return rows


def verdict(rows):
    a = rows[rows.context == 'all'].set_index('basis').reindex(list(BASES))
    if (a.ll_gain_x1000 <= 0).sum() >= 2: return 'not supported'
    if (a.ll_gain_x1000 > 0).all() and (a.lo_x1000 > 0).any(): return 'supported for a forward shadow test'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    imp = importance_table()
    parts = {**fi.basis_parts(), **extra_parts()}
    prod = {b: basis_frame(parts[b], 'production', b, imp) for b in parts}
    prod['native wk5 (replay)'] = native_frame('production', imp)
    repro = fi.reproduction({b: prod[b] for b in BASES})
    rows, preds = [], []
    for name in PRIMARY+DESCRIPTIVE:
        for b in prod:
            arm = native_frame(name, imp) if b.startswith('native') else basis_frame(parts[b], name, b, imp)
            rows += compare(prod[b], arm, b, name)
            preds.append(arm[['game_id', 'p']].assign(basis=b, arm=name))
    for b, d in prod.items(): preds.append(d[['game_id', 'p']].assign(basis=b, arm='production'))
    res = pd.DataFrame(rows); res.to_csv(out/'arms.csv', index=False, float_format='%.6g')
    pd.concat(preds, ignore_index=True).to_csv(out/'predictions.csv.gz', index=False, float_format='%.6g')
    verdicts = {a: verdict(res[res.arm == a]) for a in PRIMARY}
    prod_roi = {b: m.roi_summary(m.flat_bets(d[d.bet].assign(model_wp=d.p[d.bet]))) for b, d in prod.items()}
    info = {'protocol': 'research/MODEL_UPDATES.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
            'level': LEVEL, 'verdicts': verdicts, 'prune_sets': {b: prune_set(b, imp) for b in (*BASES, 'other bases')},
            'binary_games': {b: int(d.y.notna().sum()) for b, d in prod.items()},
            'production_roi': {b: {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v) for k, v in s.items()}
                               for b, s in prod_roi.items()}}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=True))
    prov = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/'research/MODEL_UPDATES.md', ROOT/'research/feature_importance.py',
                                                       ROOT/'research/residual_trends.py', ROOT/'nfl_model.py', IMPORTANCE, t.OOS_PACK,
                                                       t.OOS_PRED, t.T36_PACK, t.HELDOUT, t.RETRO, t.TOTALS, t.LEDGER, t.LEDGER_VIEW, t.H5_TOTALS)}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2))
    write_report(info, res, prod_roi, out)
    return info, res


def _f(x, fmt='+.2f'):
    return 'n/a' if x is None or not np.isfinite(x) else format(x, fmt)


def write_report(info, res, prod_roi, out):
    allr = res[res.context == 'all']
    L = ['# Test 39: candidate model updates from Tests 36-38', '',
         f"Protocol: [MODEL_UPDATES.md](../MODEL_UPDATES.md), pushed (`{PROTOCOL_COMMIT}`) before any candidate was scored. "
         'Production v1.18 and the ledger are unchanged. **Development evidence only**: every historical basis informed the '
         'candidates; the clean test of any of them is forward.', '',
         'Production reproduces the published forecasts: ' + ', '.join(f'{k} {v:.1e}' for k, v in info['reproduction_max_error'].items())
         + '; the native week-5 replay reproduces the archived snapshots to 1e-9 or better.', '',
         '## Verdicts (primary candidates; log-loss gain over production decides)', '']
    for a in PRIMARY: L.append(f"- **{a}**: {info['verdicts'][a]}")
    L += ['', f"Rule: supported if the gain is positive on all three bases and its {100*LEVEL:.2f}% interval excludes zero on at least "
          'one; not supported if the gain is <= 0 on two or more; otherwise unresolved.', '',
          '## Log-loss gain over production (x1000 per game, all games; [98.75% interval])', '',
          '| Arm | 2015-16 | 2017-22 | 2023-25 | 2014 (sens.) | 2026 wk1-5 (diag.) | native wk5 (replay) |', '|---|---:|---:|---:|---:|---:|---:|']
    cols = list(BASES)+['2014 (sensitivity)', '2026 wk1-5 (diagnostic)', 'native wk5 (replay)']
    for a in PRIMARY+DESCRIPTIVE:
        r = allr[allr.arm == a].set_index('basis')
        cells = []
        for b in cols:
            x = r.loc[b]
            cells.append(f"{x.ll_gain_x1000:+.2f} [{x.lo_x1000:+.2f}, {x.hi_x1000:+.2f}]" if b in BASES else f"{x.ll_gain_x1000:+.2f}")
        L.append(f"| {a}{' (descriptive)' if a in DESCRIPTIVE else ''} | " + ' | '.join(cells) + ' |')
    L += ['', '## Flat 1u ROI (goal metric; reported, not used for the verdict)', '',
          'Arm ROI ± SE, units versus production on the same bets, and side flips (units on flipped games).', '',
          '| Arm | ' + ' | '.join(BASES) + ' |', '|---|' + '---:|'*len(BASES)]
    L.append('| production | ' + ' | '.join(f"{100*prod_roi[b]['roi']:+.2f}% ± {100*prod_roi[b]['roi_se']:.2f} ({prod_roi[b]['units']:+.1f}u)" for b in BASES) + ' |')
    for a in PRIMARY+DESCRIPTIVE:
        r = allr[allr.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join(f"{100*r.loc[b, 'roi']:+.2f}% ± {100*r.loc[b, 'roi_se']:.2f}; {r.loc[b, 'units_vs_prod']:+.1f}u vs prod; "
                                          f"{int(r.loc[b, 'side_flips'])} flips ({r.loc[b, 'flip_units_vs_prod']:+.1f}u)" for b in BASES) + ' |')
    r0 = allr[allr.arm == PRIMARY[0]].set_index('basis')
    L += ['', 'Same-row market favorite and market-correct null: ' + '; '.join(
        f"{b} favorite {r0.loc[b, 'fav_units']:+.1f}u, null {100*r0.loc[b, 'null']:+.2f}%" for b in BASES) + '.', '',
          '## By total band (log-loss gain x1000; units vs production)', '',
          '| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |', '|---|---|---:|---:|---:|']
    for a in PRIMARY:
        for b in BASES:
            r = res[(res.arm == a) & (res.basis == b)].set_index('context')
            L.append(f"| {a} | {b} | " + ' | '.join(f"{r.loc[c, 'll_gain_x1000']:+.2f} ({r.loc[c, 'units_vs_prod']:+.1f}u)"
                                                    for c in ('total_low', 'total_mid', 'total_high')) + ' |')
    L += ['', '## Pruned inputs (prune_lobo)', '']
    for b, s in info['prune_sets'].items():
        L.append(f"- {b}: " + (', '.join(fi.short(x) for x in s) or 'none'))
    L += ['', '## Limits', '',
          'All historical bases informed these candidates (Tests 36-38), so even the leave-one-basis-out pruning is not a clean '
          'test. The decision rule uses log loss, as the protocol requires; ROI is reported. Supported means only "worth a forward '
          'shadow test"; any production change is a new REVISION and the owner\'s decision. Full tables: `arms.csv`, '
          '`predictions.csv.gz`.', '', 'Run: `python research/model_updates.py`.']
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    run()
