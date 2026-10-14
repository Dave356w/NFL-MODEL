"""Test 38: feature importance, interactions and correlation structure; see FEATURE_IMPORTANCE.md.

    python research/feature_importance.py    # parts A-D on 2015-16, 2017-22, 2023-25 (+ native week 5 in A)

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import residual_trends as t  # noqa: E402

OUT = ROOT/'research/feature_importance_results'
PROTOCOL_COMMIT = '0d850c6'
RECIPE = m.LEGACY_PRODUCT_RECIPE
INPUTS = list(t.MODEL_INPUTS)  # the 28 non-site production inputs
FEATURES = ['site'] + INPUTS   # every fitted term
GROUPS = {'offense box rates': [n for n in INPUTS if n.startswith('d__for__')],
          'defense box rates': [n for n in INPUTS if n.startswith('d__allowed__')],
          'QB projection': ['d__avail__qb_delta'],
          'unit absences': [n for n in INPUTS if n.startswith('d__avail__') and n.endswith('_out_cs')],
          'lead/deficit peaks': ['d__max_lead', 'd__max_deficit'],
          'pass matchup product': ['pass_product'],
          'pass tail hinges': [n for n in m.PRODUCT_CONTEXT_NAMES if n.startswith('pass_1sd')],
          'home field': ['site']}
MULTI_GROUPS = [g for g, fs in GROUPS.items() if len(fs) > 1]
SUPPLEMENTARY_ARMS = {'site': ['site']}  # not in the protocol (28 non-site inputs); labelled as added
BASES = ('2015-16', '2017-22', '2023-25')
INTERACTION_MIN_Z, INTERACTION_MAX_K = 3.0, 10


def short(n):
    for a, b in (('d__for__rates_core__', 'off '), ('d__allowed__rates_core__', 'def '), ('d__avail__', ''), ('_out_cs', ' out'),
                 ('net_pass_yards_per_pass_play', 'pass yds/play'), ('rush_yards_per_attempt', 'rush yds/att'),
                 ('first_down_rate', '1st-down rate'), ('fumbles_lost_per_game', 'fumbles'), ('interception_pct', 'INT %'),
                 ('penalty_yards_per_game', 'penalty yds'), ('plays_per_game', 'plays'), ('d__', '')):
        n = n.replace(a, b)
    return n


# --- forecasts -------------------------------------------------------------------------------------

def weekly(pack, games, zero=()):
    """v1.16 refit before every week from earlier pack rows (columns in `zero` set to 0 everywhere,
    which is the same as fitting without them); returns game_id, p16 and per-term contributions."""
    zero = list(zero)
    if zero: pack = pack.assign(**{c: 0. for c in zero}); games = games.assign(**{c: 0. for c in zero})
    out = []
    for (y, w), g in games.groupby(['season', 'week']):
        train = pack[m.before(pack, int(y), int(w))]
        fit = m.fit_composite(train, RECIPE, int(y), int(w))
        p, _, parts = m.apply_fit(g, fit, contributions=True)
        out.append(pd.concat([pd.DataFrame({'game_id': g.game_id.to_numpy(), 'p16': p}),
                              pd.DataFrame(parts, columns=[f'c__{n}' for n in fit['names']])], axis=1))
    return pd.concat(out, ignore_index=True)


def basis_parts():
    oos, t36 = pd.read_csv(t.OOS_PACK), pd.read_csv(t.T36_PACK)
    return {'2015-16': [(oos, oos[oos.season.isin([2015, 2016])])],
            '2017-22': [(oos, oos[oos.season.isin([2017, 2018, 2019, 2020])]), (t36, t36[t36.season.isin([2021, 2022])])],
            '2023-25': [(t36, t36[t36.season.isin([2023, 2024, 2025])])]}


def forecasts(parts, zero=()):
    rows = []
    for pack, games in parts:
        f = weekly(pack, games, zero)
        rows.append(games.merge(f, on='game_id', validate='one_to_one'))
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    return t.prepare(d)


def reproduction(prod):
    """Production must reproduce the published forecasts (2017-20 and 2023-25 v1.16; 2021-22 v1.18)."""
    oos = pd.read_csv(t.OOS_PRED)[['game_id', 'production']].rename(columns={'production': 'ref'})
    hel = pd.read_csv(t.HELDOUT)[['game_id', 'model_wp']].rename(columns={'model_wp': 'ref'})
    ret = pd.read_csv(t.RETRO)[['game_id', 'model_wp']].rename(columns={'model_wp': 'ref'})
    errs = {}
    for name, ref, col, basis in (('2017-20', oos, 'p16', '2017-22'), ('2021-22', ret[ret.game_id.str[:4].isin(['2021', '2022'])], 'p', '2017-22'),
                                  ('2023-25', hel, 'p16', '2023-25')):
        j = prod[basis].merge(ref, on='game_id', validate='one_to_one')
        errs[name] = float(np.max(np.abs(j[col]-j.ref)))
        if errs[name] > 1e-9: raise ValueError(f'{name} does not reproduce the published forecasts ({errs[name]:.1e})')
    return errs


# --- statistics ------------------------------------------------------------------------------------

def ll(y, p):
    return -(y*np.log(p)+(1-y)*np.log(1-p))


def cmean(x, cl):
    """Mean and week-clustered SE."""
    x = np.asarray(x, float); cl = np.asarray(cl); k = np.isfinite(x); x, cl = x[k], cl[k]
    if len(x) < 2: return np.nan, np.nan
    r = pd.Series(x-x.mean()).groupby(cl).sum()
    return float(x.mean()), float(np.sqrt((r**2).sum())/len(x))


def reading(z):
    if not np.isfinite(z): return 'n/a'
    return 'helps' if z >= 2 else 'hurts' if z <= -2 else 'unresolved'


# --- A. attribution --------------------------------------------------------------------------------

def attribute(d):
    """Per game: contribution of every term and the log-loss effect of removing it (v1.18 view);
    positive effect = the term made the forecast more accurate."""
    b = d[d.y.notna()].reset_index(drop=True)
    lq = logit(b.q.to_numpy()); C = b[[f'c__{f}' for f in FEATURES]].to_numpy(float); D = C.sum(axis=1)
    y, q = b.y.to_numpy(float), b.q.to_numpy()
    prod = lambda s: m.favorite_penalized_wp(expit(s), q, m.FAVORITE_PENALTY)
    base = ll(y, prod(lq+D))
    out = b[['game_id', 'season', 'week', 'home', 'away', 'y', 'q', 'p', 'total_line', 'cluster']].copy()
    out['ll_gain_vs_market'] = ll(y, q)-base
    for f in FEATURES:
        out[f'c__{f}'] = b[f'c__{f}']
        out[f'eff__{f}'] = ll(y, prod(lq+D-b[f'c__{f}'].to_numpy()))-base
    for g, fs in GROUPS.items():
        cg = b[[f'c__{f}' for f in fs]].to_numpy().sum(axis=1)
        out[f'grp__{g}'] = cg
        out[f'geff__{g}'] = ll(y, prod(lq+D-cg))-base
    return out


def native_attribution():
    recs = [json.loads(line) for line in t.LEDGER.read_text().splitlines() if line.strip()]
    view = pd.read_csv(t.LEDGER_VIEW)[['experiment', 'game_id', 'home won']]
    h5 = pd.DataFrame([json.loads(line) for line in t.H5_TOTALS.read_text().splitlines() if line.strip()]).drop_duplicates('game_id')
    rows = []
    for r in recs:
        if r['revision'] != 'boxscore-composite-v1.16' or (r['season'], r['week']) >= t.FORWARD_FIRST: continue
        fit, x = r['coefficient_fit'], r['model_inputs']
        row = {'experiment': r['experiment'], 'game_id': r['game_id'], 'season': r['season'], 'week': r['week'],
               'home': r['home'], 'away': r['away'], 'q': r['market_no_vig_wp'], 'model_wp': r['model_wp']}
        for n, s, b in zip(fit['names'], fit['scale'], fit['beta']): row[f'c__{n}'] = (x[n] or 0.)/s*b
        rows.append(row)
    d = pd.DataFrame(rows).merge(view, on=['experiment', 'game_id']).merge(h5[['game_id', 'total_line']], on='game_id', how='left')
    d['y'] = d['home won'].where(d['home won'].isin([0., 1.]))
    d['cluster'] = d.season.astype(str)+'_'+d.week.astype(str)
    D = d[[f'c__{f}' for f in FEATURES]].sum(axis=1)
    err = float(np.max(np.abs(expit(logit(d.q)+D)-d.model_wp)))
    if err > 1e-9: raise ValueError(f'Native snapshots do not reproduce ({err:.1e})')
    d['p'] = m.favorite_penalized_wp(expit(logit(d.q)+D).to_numpy(), d.q.to_numpy(), m.FAVORITE_PENALTY)
    return attribute(d), err


def attribution_summary(a, basis):
    rows = []
    for ctx in t.CONTEXTS:
        s = a[t.context_mask(a.total_line, ctx)]
        for kind, names, pre, cpre in (('group', list(GROUPS), 'geff__', 'grp__'), ('feature', FEATURES, 'eff__', 'c__')):
            for nm in names:
                mu, se = cmean(s[pre+nm], s.cluster)
                active = s[cpre+nm].abs() > .01
                wrong = active & (np.sign(s[cpre+nm])*(2*s.y-1) < 0)
                rows.append({'basis': basis, 'context': ctx, 'kind': kind, 'name': nm, 'n': len(s), 'effect_x1000': 1000*mu,
                             'se_x1000': 1000*se, 'z': mu/se if se and se > 0 else np.nan,
                             'mean_abs_contribution': float(s[cpre+nm].abs().mean()),
                             'wrong_way_share': float(wrong.sum()/active.sum()) if active.sum() else np.nan})
    return pd.DataFrame(rows)


def culprits(a, basis):
    g = [f'geff__{k}' for k in GROUPS]
    loss, win = a[a.ll_gain_vs_market < 0], a[a.ll_gain_vs_market > 0]
    cul = loss[g].idxmin(axis=1).str[6:].value_counts(normalize=True)
    hero = win[g].idxmax(axis=1).str[6:].value_counts(normalize=True)
    return [{'basis': basis, 'group': k, 'culprit_share': float(cul.get(k, 0.)), 'helper_share': float(hero.get(k, 0.)),
             'misses': len(loss), 'hits': len(win)} for k in GROUPS]


def game_story(r, k=2):
    e = pd.Series({f: r[f'eff__{f}'] for f in FEATURES}); c = pd.Series({f: r[f'c__{f}'] for f in FEATURES})
    fmt = lambda s: ', '.join(f"{short(f)} {c[f]:+.2f} ({1000*v:+.0f})" for f, v in s.items()) or '-'
    return fmt(e[e < -1e-4].sort_values().head(k)), fmt(e[e > 1e-4].sort_values(ascending=False).head(k))


# --- B. drop-column importance ---------------------------------------------------------------------

def arms():
    a = {f: [f] for f in INPUTS}
    a.update({f'group: {g}': GROUPS[g] for g in MULTI_GROUPS})
    a.update({f'{k} (supplementary)': v for k, v in SUPPLEMENTARY_ARMS.items()})
    return a


def importance(prod, arm, basis, name):
    j = prod[['game_id', 'y', 'p', 'units', 'side', 'total_line', 'cluster']].merge(
        arm[['game_id', 'p', 'units', 'side']], on='game_id', suffixes=('', '_arm'), validate='one_to_one')
    rows = []
    for ctx in t.CONTEXTS:
        s = j[t.context_mask(j.total_line, ctx)]
        b = s[s.y.notna()]
        mu, se = cmean(ll(b.y, b.p_arm)-ll(b.y, b.p), b.cluster)
        bets = s[s.units.notna() & s.units_arm.notna()]
        flips = bets.side != bets.side_arm
        rows.append({'basis': basis, 'arm': name, 'context': ctx, 'n': len(b), 'importance_x1000': 1000*mu, 'se_x1000': 1000*se,
                     'z': mu/se if se and se > 0 else np.nan, 'reading': reading(mu/se if se and se > 0 else np.nan),
                     'units_prod_minus_arm': float((bets.units-bets.units_arm).sum()), 'bets': len(bets),
                     'side_flips': int(flips.sum()), 'flip_units_prod_minus_arm': float((bets.units-bets.units_arm)[flips].sum())})
    return rows


# --- C. interaction scan ---------------------------------------------------------------------------

def interaction_pairs():
    pairs = list(combinations(INPUTS, 2)) + [(f, 'market_logit') for f in INPUTS]
    return pairs


def interaction_scan(d, basis):
    """Week-clustered score z for every centred product, every context, against v1.18's residual."""
    pairs = interaction_pairs(); rows = []
    for ctx in t.CONTEXTS:
        s = d[t.context_mask(d.total_line, ctx) & d.y.notna().to_numpy()]
        if len(s) < 10: continue
        X = s[INPUTS+['market_logit']].to_numpy(float); X = X-X.mean(axis=0)
        ix = {n: i for i, n in enumerate(INPUTS+['market_logit'])}
        P = np.column_stack([X[:, ix[a]]*X[:, ix[b]] for a, b in pairs]); P = P-P.mean(axis=0)
        r = (s.y-s.p).to_numpy()
        S = r@P
        G = pd.DataFrame(r[:, None]*P).groupby(s.cluster.to_numpy()).sum().to_numpy()
        V = (G**2).sum(axis=0)
        info = (s.p*(1-s.p)).to_numpy()@(P**2)
        with np.errstate(divide='ignore', invalid='ignore'):
            z = np.where(V > 1e-18, S/np.sqrt(V), np.nan)
            eff = np.where(info > 1e-18, S/info*P.std(axis=0), np.nan)
        for (a, b), zz, ee in zip(pairs, z, eff):
            rows.append({'basis': basis, 'context': ctx, 'a': a, 'b': b, 'n': len(s), 'z': zz, 'effect_per_sd': ee})
    return pd.DataFrame(rows)


def select_interactions(disc):
    c = disc[np.abs(disc.z) >= INTERACTION_MIN_Z].assign(az=lambda x: x.z.abs())
    return c.sort_values(['az', 'context', 'a', 'b'], ascending=[False, True, True, True]).head(INTERACTION_MAX_K).drop(columns='az')


def test_interactions(cands, other, label):
    k = max(len(cands), 1); bar = float(norm.ppf(1-.05/k))
    j = cands[['context', 'a', 'b', 'z']].merge(other[['context', 'a', 'b', 'z']], on=['context', 'a', 'b'], suffixes=('_d', ''))
    j[f'z_{label}'] = np.sign(j.z_d)*j.z
    word = 'confirmed' if label == 'confirm' else 'replicated'
    j[f'verdict_{label}'] = np.where(j[f'z_{label}'] >= bar, word, np.where(j[f'z_{label}'] > 0, 'direction holds', 'reversed'))
    return j[['context', 'a', 'b', f'z_{label}', f'verdict_{label}']], bar


# --- D. correlation --------------------------------------------------------------------------------

def correlations(d, a, basis):
    X = d[INPUTS]; R = X.corr()
    vif = pd.Series(np.diag(np.linalg.pinv(R.to_numpy())), index=INPUTS)
    pairs = [{'basis': basis, 'a': x, 'b': y, 'r': float(R.loc[x, y])} for x, y in combinations(INPUTS, 2)]
    gc = a[[f'grp__{g}' for g in GROUPS]].corr(); ge = a[[f'geff__{g}' for g in GROUPS]].corr()
    gc.index = gc.columns = list(GROUPS); ge.index = ge.columns = list(GROUPS)
    return pd.DataFrame(pairs), vif.rename(basis), gc, ge


# --- run -------------------------------------------------------------------------------------------

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    parts = basis_parts()
    prod = {b: forecasts(parts[b]) for b in BASES}
    repro = reproduction(prod)
    # A
    attr = {b: attribute(prod[b]) for b in BASES}
    attr['native wk5'], native_err = native_attribution()
    summ = pd.concat([attribution_summary(a, b) for b, a in attr.items()], ignore_index=True)
    cul = pd.DataFrame([r for b in BASES for r in culprits(attr[b], b)])
    pd.concat([a.assign(basis=b) for b, a in attr.items()], ignore_index=True).to_csv(
        out/'attribution_per_game.csv.gz', index=False, float_format='%.5g')
    summ.to_csv(out/'attribution_summary.csv', index=False, float_format='%.6g')
    # B
    imp = []
    for name, cols in arms().items():
        for b in BASES:
            imp += importance(prod[b], forecasts(parts[b], cols), b, name)
    imp = pd.DataFrame(imp); imp.to_csv(out/'importance.csv', index=False, float_format='%.6g')
    # C
    scans = {b: interaction_scan(prod[b], b) for b in BASES}
    pd.concat(scans.values(), ignore_index=True).to_csv(out/'interactions.csv.gz', index=False, float_format='%.5g')
    cands = select_interactions(scans['2017-22'])
    conf, bar = test_interactions(cands, scans['2023-25'], 'confirm')
    rep, _ = test_interactions(cands, scans['2015-16'], 'replicate')
    inter = cands.merge(conf, on=['context', 'a', 'b']).merge(rep, on=['context', 'a', 'b'])
    # D
    corr = [correlations(prod[b], attr[b], b) for b in BASES]
    pair_r = pd.concat([c[0] for c in corr]).pivot_table(index=['a', 'b'], columns='basis', values='r')
    vif = pd.concat([c[1] for c in corr], axis=1)
    pair_r.to_csv(out/'input_correlations.csv', float_format='%.4f'); vif.to_csv(out/'vif.csv', float_format='%.4f')
    res = {'protocol': 'research/FEATURE_IMPORTANCE.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'native_reproduction_max_error': native_err, 'binary_games': {b: int(attr[b].shape[0]) for b in attr},
           'interaction_cells_per_basis': int(len(scans['2017-22'])), 'interaction_bar': bar,
           'interaction_candidates': json.loads(inter.to_json(orient='records')),
           'interaction_cells_abs_z_ge_3': {b: int((s.z.abs() >= 3).sum()) for b, s in scans.items()},
           'culprit_helper': json.loads(cul.to_json(orient='records')),
           'group_contribution_corr': {b: json.loads(c[2].to_json()) for b, c in zip(BASES, corr)},
           'group_effect_corr': {b: json.loads(c[3].to_json()) for b, c in zip(BASES, corr)}}
    (out/'results.json').write_text(json.dumps(res, indent=2, allow_nan=True))
    prov = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/'research/FEATURE_IMPORTANCE.md', ROOT/'research/residual_trends.py',
                                                       ROOT/'nfl_model.py', t.OOS_PACK, t.OOS_PRED, t.T36_PACK, t.HELDOUT, t.RETRO, t.TOTALS,
                                                       t.LEDGER, t.LEDGER_VIEW, t.H5_TOTALS)}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2))
    write_report(res, summ, cul, attr, imp, inter, pair_r, vif, corr, out)
    return res


def _f(x, fmt='+.2f'):
    return 'n/a' if x is None or not np.isfinite(x) else format(x, fmt)


def write_report(res, summ, cul, attr, imp, inter, pair_r, vif, corr, out):
    L = ['# Test 38: feature importance, interactions and correlation structure', '',
         f"Protocol: [FEATURE_IMPORTANCE.md](../FEATURE_IMPORTANCE.md), pushed (`{PROTOCOL_COMMIT}`) before parts B-D were "
         "computed; part A was computed first and is post hoc. Diagnostic only; production v1.18 and the ledger are unchanged.", '',
         f"Bases (never pooled): 2015-16 {res['binary_games']['2015-16']}, 2017-22 {res['binary_games']['2017-22']}, "
         f"2023-25 {res['binary_games']['2023-25']} binary games; native week 5 {res['binary_games']['native wk5']} (part A only). "
         'Production reproduces the published forecasts: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items())
         + f"; native snapshots {res['native_reproduction_max_error']:.1e}.", '',
         'Units: log loss per game x1000. Positive = the input makes the forecast more accurate. z is week-clustered.', '']
    # B first: the importance question
    L += ['## B. Drop-column importance (refit without the input)', '',
          'Importance = log loss without the input minus with it. "Units" = production minus the arm on the same bets.', '',
          '| Arm | 2015-16 | 2017-22 | 2023-25 | Same sign | Units (15-16 / 17-22 / 23-25) | Side flips |', '|---|---:|---:|---:|---|---|---:|']
    allg = imp[imp.context == 'all']
    order = allg.groupby('arm').z.sum().sort_values(ascending=False).index
    for a in order:
        r = allg[allg.arm == a].set_index('basis')
        z = r.z.reindex(BASES)
        same = 'yes' if np.sign(z).nunique() == 1 else ''
        cells = [f"{r.loc[b, 'importance_x1000']:+.2f} ({r.loc[b, 'z']:+.1f})" for b in BASES]
        L.append(f"| {short(a)} | " + ' | '.join(cells) + f" | {same} | " + ' / '.join(f"{r.loc[b, 'units_prod_minus_arm']:+.1f}" for b in BASES)
                 + f" | {int(r.side_flips.sum())} |")
    n2 = int((imp.z.abs() >= 2).sum())
    L += ['', '**Across the 28 single-input arms** (post-hoc summary, all games):', '']
    single = allg[allg.arm.isin(INPUTS)]
    for b in BASES:
        s = single[single.basis == b]
        L.append(f"- {b}: the refit without the input scores better in {int((s.importance_x1000 < 0).sum())} of 28 "
                 f"(mean importance {s.importance_x1000.mean():+.3f}); removing it costs production units in "
                 f"{int((s.units_prod_minus_arm > 0).sum())} of 28 (median {s.units_prod_minus_arm.median():+.1f}u; {int(s.side_flips.sum())} side flips).")
    p = single.pivot_table(index='arm', columns='basis', values='importance_x1000')
    L += [f"- Same sign on all three bases: {int((np.sign(p).nunique(axis=1) == 1).sum())} of 28, all of them negative "
          f"({int((p < 0).all(axis=1).sum())} negative, {int((p > 0).all(axis=1).sum())} positive): "
          + ', '.join(short(x) for x in p[(p < 0).all(axis=1)].index) + '.' if (p > 0).all(axis=1).sum() == 0 else
          f"- Same sign on all three bases: {int((np.sign(p).nunique(axis=1) == 1).sum())} of 28.",
          '- Reading: no input reliably earns its place in log loss once the model is refit without it; the inputs with a '
          'consistent sign are ones the model scores slightly better without, which points to mild over-fitting (the same '
          'direction as Test 37\'s oversized departures). Removals cost units on 2017-25 but not on never-scored 2015-16. '
          'Design tuning cannot explain all of that: a post-hoc split shows the same on 2017-20 (22 of 28 arms), scored only '
          'after v1.16 was fixed. Era or chance remain open; each arm flips about 10 bets per basis, so units are noisy.']
    L += ['', f"Cells at |z| >= 2 across arms, contexts and bases: {n2} of {len(imp)} (about {round(.0455*len(imp))} expected by chance). "
          'The site arm is supplementary (not in the protocol\'s 28).', '',
          '**Context cells at |z| >= 2:** ' + ('; '.join(f"{short(r.arm)}, {t.CONTEXT_LABEL[r.context]}, {r.basis}: {r.importance_x1000:+.2f} (z {r.z:+.1f})"
                                                       for r in imp[(imp.z.abs() >= 2) & (imp.context != 'all')].itertuples()) or 'none'), '']
    # C
    L += ['## C. Interaction scan', '',
          f"{res['interaction_cells_per_basis']} cells per basis (406 interactions x 4 contexts). |z| >= 3: "
          + ', '.join(f'{b} {n}' for b, n in res['interaction_cells_abs_z_ge_3'].items()) + ' (about 4 expected by chance on each). '
          f"Bar for confirmation and replication: one-sided z >= {res['interaction_bar']:.2f}.", '']
    if len(inter):
        L += ['| Context | Interaction | z 2017-22 | z 2023-25 (dir.) | Verdict | z 2015-16 (dir.) | Verdict |', '|---|---|---:|---:|---|---:|---|']
        for r in inter.itertuples():
            L.append(f"| {t.CONTEXT_LABEL[r.context]} | {short(r.a)} x {short(r.b)} | {r.z:+.2f} | {r.z_confirm:+.2f} | {r.verdict_confirm} | "
                     f"{r.z_replicate:+.2f} | {r.verdict_replicate} |")
    else:
        L.append('No discovery cell reached |z| >= 3; the scan ends with no candidate.')
    # A
    L += ['', '## A. Per-game attribution (post hoc)', '',
          'Effect of removing each fitted contribution from each game (no refit), by group, all games:', '',
          '| Group | 2015-16 | 2017-22 | 2023-25 | native wk5 | Culprit / helper share 2017-22 |', '|---|---:|---:|---:|---:|---:|']
    g = summ[(summ.kind == 'group') & (summ.context == 'all')].set_index(['name', 'basis'])
    for k in GROUPS:
        c = cul[(cul.basis == '2017-22') & (cul.group == k)].iloc[0]
        L.append(f"| {k} | " + ' | '.join(f"{g.loc[(k, b), 'effect_x1000']:+.2f}" + (f" ({g.loc[(k, b), 'z']:+.1f})" if b != 'native wk5' else '')
                                         for b in (*BASES, 'native wk5')) + f" | {c.culprit_share:.0%} / {c.helper_share:.0%} |")
    f = summ[(summ.kind == 'feature') & (summ.basis.isin(BASES))].pivot_table(index=['context', 'name'], columns='basis', values='z')
    same = f[np.sign(f[list(BASES)]).nunique(axis=1) == 1].assign(comb=lambda x: x[list(BASES)].sum(axis=1)/np.sqrt(3)).sort_values('comb')
    L += ['', f"Feature x context cells with the same sign on all three bases: {len(same)} of {len(f)} (about {round(len(f)/4)} expected). "
          'Most harmful and most helpful of those (combined z = sum/sqrt 3, for ranking only):', '']
    for r in pd.concat([same.head(5), same.tail(3)]).itertuples():
        L.append(f"- {short(r.Index[1])}, {t.CONTEXT_LABEL[r.Index[0]]}: z " + ' / '.join(f'{getattr(r, "_"+str(i+1)):+.2f}' for i in range(3)) + f" (combined {r.comb:+.2f})")
    L += ['', 'Worst games against the market, with the inputs that hurt most (contribution, effect x1000):', '']
    for b in ('2023-25', '2017-22', '2015-16'):
        for r in attr[b].nsmallest(3, 'll_gain_vs_market').to_dict('records'):
            bad, _ = game_story(r, 3)
            L.append(f"- {r['game_id']} (total {r['total_line']}): market {r['q']:.2f}, model {r['p']:.2f}, home {'won' if r['y'] else 'lost'}; "
                     f"{1000*r['ll_gain_vs_market']:+.0f} vs market. Hurt: {bad}")
    L += ['', 'Native week 5 (locked v1.16 snapshots, v1.18 view):', '']
    for r in attr['native wk5'].sort_values('ll_gain_vs_market').to_dict('records'):
        bad, good = game_story(r)
        L.append(f"- {r['away']}@{r['home']}: market {r['q']:.2f}, model {r['p']:.2f}, {('home' if r['y'] else 'away')} won, "
                 f"{1000*r['ll_gain_vs_market']:+.0f} vs market. Hurt: {bad}. Helped: {good}")
    # D
    strong = pair_r[(pair_r[list(BASES)].abs() >= .5).all(axis=1)].assign(m=lambda x: x[list(BASES)].mean(axis=1)).sort_values('m', key=abs, ascending=False)
    L += ['', '## D. Correlation structure', '',
          f"Input pairs with |r| >= 0.5 on all three bases: {len(strong)}.", '']
    for (a, b), r in strong.head(10).iterrows():
        L.append(f"- {short(a)} vs {short(b)}: " + ' / '.join(f'{r[x]:+.2f}' for x in BASES))
    L += ['', 'Highest variance inflation factors (collinearity): ' + '; '.join(
        f"{short(i)} " + '/'.join(f'{v:.1f}' for v in vif.loc[i, list(BASES)]) for i in vif.mean(axis=1).sort_values(ascending=False).head(6).index), '']
    gc = sum(c[2] for c in corr)/3; ge = sum(c[3] for c in corr)/3
    def top(Mx, k=4, sign=1):
        p = [(a, b, Mx.loc[a, b]) for a, b in combinations(GROUPS, 2)]
        return sorted(p, key=lambda x: sign*x[2])[:k]
    L += ['Group contributions across games, mean r over bases. Most offsetting: ' + '; '.join(f'{a} vs {b} {r:+.2f}' for a, b, r in top(gc)) + '.',
          'Group accuracy effects across games (do they fail together?). Most aligned: ' + '; '.join(f'{a} vs {b} {r:+.2f}' for a, b, r in top(ge, sign=-1))
          + '. Most opposed: ' + '; '.join(f'{a} vs {b} {r:+.2f}' for a, b, r in top(ge)) + '.', '',
          '## Limits', '',
          'All bases are exposed history; part A was seen before the protocol; drop-column importance is correlated with part A. '
          'Multiplicity is large (396 importance cells, 1,624 interaction cells per basis). Nothing here changes the model; removing, '
          'reweighting or adding a term is a new REVISION and the owner\'s decision, and only forward data can test it cleanly. '
          'Full tables: `importance.csv`, `interactions.csv.gz`, `attribution_summary.csv`, `attribution_per_game.csv.gz`, '
          '`input_correlations.csv`, `vif.csv`.', '', 'Run: `python research/feature_importance.py`.']
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    run()
