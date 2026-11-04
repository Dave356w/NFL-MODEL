"""Test 52: implied points as fitted features with no moneyline offset; see IMPLIED_NO_OFFSET.md.

    python research/implied_no_offset.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import contextlib
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit, ndtri
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import fixed_bands  # noqa: E402
import residual_trends as t  # noqa: E402
import feature_importance as fi  # noqa: E402
import slim_model as sm  # noqa: E402
import market_implied as mi  # noqa: E402

OUT = ROOT/'research/implied_no_offset_results'
PROTOCOL_COMMIT = '5e912a4'
RECIPE = m.PRODUCT_RECIPE  # v1.19
BASES = fi.BASES
K = 2
Z_BAR = float(norm.ppf(1-.05/K/2))  # 2.24
IMPLIED = ['mkt_home_implied', 'mkt_away_implied']
MAIN, CTX = mi._model_terms(RECIPE)  # v1.19's own terms (unpatched)
ARMS = {'C core + implied, no offset': dict(main=MAIN, ctx=CTX+IMPLIED),
        'C0 implied only, no offset': dict(main=['site'], ctx=IMPLIED)}


# --- fit: a research copy of nfl_model.fit_composite with the offset switchable ------------------

def fit(train, year, week, main, ctx, offset):
    t_ = train[train['home won'].isin([0., 1.]) & train.ready].copy()
    t_ = t_[np.isfinite(t_.q) & np.isfinite(t_[list(m.PRODUCT_CONTEXT_NAMES)]).all(axis=1)].copy()  # v1.19's rows
    if len(t_) < m.MIN_TRAIN_GAMES: raise ValueError(f'Only {len(t_)} eligible labeled games')
    if not m.before(t_, year, week).all(): raise ValueError('Training includes current/future week')
    names = list(main)+list(ctx)
    X = t_[names].to_numpy(float); X = np.where(np.isfinite(X), X, 0.)
    age = ((year-t_.season.to_numpy())*19+(week-t_.week.to_numpy()))/(19*m.FIT_HALF_LIFE_SEASONS)
    w = np.exp2(-age); w /= w.sum()
    mu = np.sum(w[:, None]*X, axis=0)
    scale = np.sqrt(np.sum(w[:, None]*(X-mu)**2, axis=0)); scale = np.where(scale > 1e-8, scale, 1.); scale[0] = 1.
    Z = X/scale; y = t_['home won'].to_numpy(float)
    pen = np.full(len(names), float(RECIPE['ridge'])); pen[0] *= .1; pen[len(main):] = float(RECIPE['interaction_ridge'])
    base = logit(np.clip(t_.q.to_numpy(), 1e-5, 1-1e-5)) if offset else np.zeros(len(t_))

    def obj(beta):
        eta = base+Z@beta
        return (np.sum(w*(np.logaddexp(0, eta)-y*eta))+.5*np.sum(pen*beta*beta), Z.T@(w*(expit(eta)-y))+pen*beta)
    return {'names': names, 'scale': scale, 'beta': m.checked_optimize(obj, len(names)), 'offset': offset}


def apply(df, f):
    x = df[f['names']].to_numpy(float); x = np.where(np.isfinite(x), x, 0.)/f['scale']
    s = x@f['beta']
    q = df.q.to_numpy(float)
    if f['offset']: s = s+logit(np.clip(q, 1e-5, 1-1e-5))
    valid = np.isfinite(q) & np.isfinite(df[list(m.PRODUCT_CONTEXT_NAMES)].to_numpy(float)).all(axis=1)
    return expit(np.where(valid, s, np.nan))


@contextlib.contextmanager
def no_penalty():
    """t.prepare applies m.FAVORITE_PENALTY; lambda 1 keeps the full departure (identity)."""
    old = m.FAVORITE_PENALTY; m.FAVORITE_PENALTY = 1.
    try: yield
    finally: m.FAVORITE_PENALTY = old


def forecasts(parts, main, ctx, offset):
    rows, fits = [], {}
    for pack, games in parts:
        out = []
        for (y, w), gm in games.groupby(['season', 'week']):
            try:
                f = fit(pack[m.before(pack, int(y), int(w))], int(y), int(w), main, ctx, offset)
            except ValueError as e:
                if 'eligible labeled games' in str(e): continue
                raise
            fits[(int(y), int(w))] = f
            out.append(pd.DataFrame({'game_id': gm.game_id.to_numpy(), 'p16': apply(gm, f)}))
        rows.append(games.merge(pd.concat(out, ignore_index=True), on='game_id', validate='one_to_one'))
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    if offset: d = t.prepare(d)
    else:
        with no_penalty(): d = t.prepare(d)
        if float(np.nanmax(np.abs(d.p-d.p16))) > 1e-12: raise ValueError('no-offset arm was penalized')
    d['model_spread'] = sm.SPREAD_SCALE*ndtri(np.clip(d.p.to_numpy(float), .005, .995))
    mapped = np.full(len(d), np.nan)
    for y in sorted(d.season.unique()):
        rule = fixed_bands.fit(d, int(y)); k = d.season.eq(y).to_numpy()
        mapped[k] = fixed_bands.apply(d.loc[k, 'model_spread'], rule)
    d['mapped_spread'] = mapped
    d['mapped_spread_prod_window'] = sm.prod_window_map(d)
    return d, fits


# --- summaries ------------------------------------------------------------------------------------

def vs_market(d, b, label):
    j = d[d.y.notna()]
    mu, se = fi.cmean(fi.ll(j.y, j.p)-fi.ll(j.y, j.q), j.cluster)
    return {'basis': b, 'model': label, 'n': len(j), 'll_model': float(fi.ll(j.y, j.p).mean()),
            'll_market': float(fi.ll(j.y, j.q).mean()), 'diff_x1000': 1000*mu, 'se_x1000': 1000*se}


def coefficients(fits, b, arm):
    s = {'2015-16': 2016, '2017-22': 2022, '2023-25': 2025}[b]
    f = fits[max(k for k in fits if k[0] == s)]
    ix = {n: i for i, n in enumerate(f['names'])}
    # per point: beta / scale
    return {'basis': b, 'arm': arm, **{f'{n} per point': float(f['beta'][ix[n]]/f['scale'][ix[n]]) for n in IMPLIED},
            'site': float(f['beta'][ix['site']])}


def all_row_baselines(fr, b):
    """Always-favorite and always-home on the same rows as the all-rows raw-spread view."""
    ok = None
    for d in fr.values():
        k = d.set_index('game_id'); g = k.index[np.isfinite(k.spread_line) & np.isfinite(k.result) & np.isfinite(k.model_spread)]
        ok = set(g) if ok is None else ok & set(g)
    s = fr['P'][fr['P'].game_id.isin(ok)]
    margin = s.result.to_numpy(float)-s.spread_line.to_numpy(float); line = s.spread_line.to_numpy(float)
    return [{'basis': b, 'arm': name, 'view': 'baseline, all rows (supplementary)', **sm.ats_record(side, margin)[0]}
            for name, side in (('always favorite', np.sign(line)), ('always home', np.ones(len(s))))]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    parts = mi.season_parts(mi.scores())
    full, fits = {}, {}
    full['P'], _ = mi.forecasts(parts)
    repro = mi.reproduction(full['P'])
    copy, _ = forecasts(parts, MAIN, CTX, offset=True)
    j = full['P'][['game_id', 'p']].merge(copy[['game_id', 'p']], on='game_id', suffixes=('', '_copy'), validate='one_to_one')
    repro['research fit copy vs P (offset on)'] = float(np.max(np.abs(j.p-j.p_copy)))
    if repro['research fit copy vs P (offset on)'] > 1e-9: raise ValueError(f'fit copy does not reproduce P ({repro})')
    for arm, a in ARMS.items(): full[arm], fits[arm] = forecasts(parts, a['main'], a['ctx'], offset=False)
    ll, mkt, ats, ml, coef = [], [], [], [], []
    for b in BASES:
        fr = {k: sm.basis(v, b) for k, v in full.items()}
        mkt.append(vs_market(fr['P'], b, 'P'))
        for arm in ARMS:
            ll.append({'basis': b, 'arm': arm, **sm.ll_row(fr['P'], fr[arm], b)})
            mkt.append(vs_market(fr[arm], b, arm))
            ml.append({'basis': b, 'arm': arm, **sm.ml_row(fr['P'], fr[arm], b)})
            coef.append(coefficients(fits[arm], b, arm))
        ats += sm.ats_rows(fr, b)
        # Supplementary, added after the run showed C/C0 maps missing in early seasons (bands < 30 games):
        ats += sm.ats_rows(fr, b, 'model_spread', 'raw spread, all rows (supplementary)')
        ats += all_row_baselines(fr, b)
        if b == '2023-25': ats += sm.ats_rows(fr, b, 'mapped_spread_prod_window', 'median map, 2021+ history (supplementary)')
    ll, mkt, ats, ml, coef = map(pd.DataFrame, (ll, mkt, ats, ml, coef))
    verdicts = {arm: mi.verdict(ll[ll.arm == arm].to_dict('records')) for arm in ARMS}
    for name, df in (('log_loss', ll), ('vs_market', mkt), ('ats', ats), ('moneyline_units', ml), ('coefficients', coef)):
        df.to_csv(out/f'{name}.csv', index=False, float_format='%.6g')
    pd.concat([d[['game_id', 'season', 'week', 'p', 'model_spread', 'mapped_spread']].assign(arm=k) for k, d in full.items()]
              ).to_csv(out/'forecasts.csv.gz', index=False, float_format='%.6g')
    res = {'protocol': 'research/IMPLIED_NO_OFFSET.md', 'protocol_commit': PROTOCOL_COMMIT,
           'reproduction_max_error': repro, 'z_bar': Z_BAR, 'verdicts': verdicts}
    (out/'results.json').write_text(json.dumps(res, indent=2))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/IMPLIED_NO_OFFSET.md', ROOT/'research/market_implied.py', ROOT/'nfl_model.py',
        ROOT/'fixed_bands.py', mi.SCORES, t.OOS_PACK, t.T36_PACK)}, indent=2))
    write_report(res, ll, mkt, ats, ml, coef, out)
    return res


def write_report(res, ll, mkt, ats, ml, coef, out):
    L = ['# Test 52: implied points as fitted features, no moneyline offset', '',
         f'Protocol: [IMPLIED_NO_OFFSET.md](../IMPLIED_NO_OFFSET.md), committed (`{res["protocol_commit"]}`) before any arm was scored. '
         'Diagnostic only; production v1.19 and the ledger are unchanged.', '',
         'Reproduction: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.', '',
         f'## Log loss (arm minus v1.19, x1000; negative = arm better; bar |z| >= {res["z_bar"]:.2f})', '',
         '| Arm | ' + ' | '.join(BASES) + ' | Verdict |', '|---|' + '---:|'*len(BASES) + '---|']
    for arm in ARMS:
        s = ll[ll.arm == arm].set_index('basis')
        L.append(f'| {arm} | ' + ' | '.join(
            f'{s.loc[b,"diff_x1000"]:+.2f} ± {s.loc[b,"se_x1000"]:.2f} (z {s.loc[b,"z"]:+.1f}, n {int(s.loc[b,"n"])})' for b in BASES)
            + f' | {res["verdicts"][arm]} |')
    L += ['', '## Against the no-vig moneyline alone (model minus market, x1000; negative = beats the market)', '',
          '| Model | ' + ' | '.join(BASES) + ' |', '|---|' + '---:|'*len(BASES)]
    for mod in mkt.model.unique():
        s = mkt[mkt.model == mod].set_index('basis')
        L.append(f'| {mod} | ' + ' | '.join(f'{s.loc[b,"diff_x1000"]:+.2f} ± {s.loc[b,"se_x1000"]:.2f}' for b in BASES) + ' |')
    L += ['', 'Market log loss per game: ' + ', '.join(f'{b} {mkt[mkt.basis == b].ll_market.iloc[0]:.5f}' for b in BASES) + '.', '',
          '## Implied-point coefficients in the last fit of each basis (log-odds per point)', '',
          '| Basis | Arm | Home implied | Away implied | Site (scaled) |', '|---|---|---:|---:|---:|']
    for _, r in coef.iterrows():
        L.append(f'| {r.basis} | {r.arm} | {r["mkt_home_implied per point"]:+.4f} | {r["mkt_away_implied per point"]:+.4f} | {r.site:+.3f} |')
    L += ['', '## ATS, flat 1u at -110 (same rows for every arm; each arm uses its own prior-season median map)', '',
          'Break-even cover rate 52.4%. ROI SE has pushes in the denominator. Flips and flip units are against v1.19 in the same view.', '',
          '| Basis | Arm | View | W-L-P | Skips | Units | ROI ± SE | Cover | Flips | Units on flips (arm − P) |',
          '|---|---|---|---|---:|---:|---:|---:|---:|---:|']
    for _, r in ats.iterrows():
        fl = '' if pd.isna(r.get('flips_vs_P')) else f'{int(r.flips_vs_P)}'
        fu = '' if pd.isna(r.get('units_arm_minus_P_on_flips')) else f'{r.units_arm_minus_P_on_flips:+.1f}'
        L.append(f'| {r.basis} | {r.arm} | {r.view} | {r.W}-{r.L}-{r.P} | {r.skips} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {100*r.cover:.1f}% | {fl} | {fu} |')
    L += ['', '## Moneyline flat units (legacy, same bets)', '', '| Basis | Arm | Bets | v1.19 | Arm |', '|---|---|---:|---:|---:|']
    for _, r in ml.iterrows():
        L.append(f'| {r.basis} | {r.arm} | {r.bets} | {r.units_prod:+.1f} | {r.units_arm:+.1f} |')
    (out/'REPORT.md').write_text('\n'.join(L) + '\n')


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
