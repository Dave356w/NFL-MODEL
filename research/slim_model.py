"""Test 50: slim models from the fit analysis; see SLIM_MODEL.md.

    python research/slim_model.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtri
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import fixed_bands  # noqa: E402
import residual_trends as t  # noqa: E402
import feature_importance as fi  # noqa: E402

OUT = ROOT/'research/slim_model_results'
PROTOCOL_COMMIT = '4b11376'
RECIPE = m.LEGACY_PRODUCT_RECIPE
BASES = fi.BASES
K = 3
Z_BAR = float(norm.ppf(1-.05/K/2))  # 2.39
PROD_MAP_FIRST = 2021  # data/latest/fixed_band_ledger.csv history
SPREAD_SCALE = 12.37  # production's WP -> model spread (production_sanity.py)

F = 'd__for__rates_core__'; A = 'd__allowed__rates_core__'; V = 'd__avail__'
INT_FOR, INT_ALLOWED = F+'interception_pct', A+'interception_pct'
ALL_TERMS = ['site'] + fi.INPUTS
TRIM_DROP = ['d__max_lead', 'd__max_deficit', V+'RB_out_cs', V+'LB_out_cs', V+'DB_out_cs',
             F+'net_pass_yards_per_pass_play', A+'net_pass_yards_per_pass_play']
CORE_KEEP = ['site', F+'first_down_rate', A+'first_down_rate', INT_FOR, INT_ALLOWED, A+'penalty_yards_per_game',
             V+'qb_delta', 'pass_product', 'pass_1sd_pn', 'pass_1sd_np']
ARMS = {'S1 trim': dict(zero=TRIM_DROP, merge_int=False),
        'S2 trim + one INT term': dict(zero=TRIM_DROP, merge_int=True),
        'S3 core': dict(zero=[c for c in ALL_TERMS if c not in CORE_KEEP], merge_int=False)}
VERDICT_BASES = {'S3 core': ['2015-16']}


def transform(frame, zero, merge_int):
    f = frame.copy()
    if merge_int:
        f[INT_FOR] = f[INT_FOR].fillna(0.) + f[INT_ALLOWED].fillna(0.)
        zero = list(zero) + [INT_ALLOWED]
    for c in zero: f[c] = 0.
    return f


def terms(arm):
    a = ARMS[arm]; z = set(a['zero']) | ({INT_ALLOWED} if a['merge_int'] else set())
    return len([c for c in ALL_TERMS if c not in z])


def season_parts():
    """Every forecast season with its pack (2014-20 from the 2013-20 pack, 2021-25 from Test 36's)."""
    oos, t36 = pd.read_csv(t.OOS_PACK), pd.read_csv(t.T36_PACK)
    return [(oos, oos[oos.season.between(2014, 2020)]), (t36, t36[t36.season.between(2021, 2025)])]


def weekly(pack, games):
    out = []
    for (y, w), g in games.groupby(['season', 'week']):
        train = pack[m.before(pack, int(y), int(w))]
        try:
            fit = m.fit_composite(train, RECIPE, int(y), int(w))
        except ValueError as e:
            if 'eligible labeled games' in str(e): continue  # early 2014 weeks: not enough history
            raise
        out.append(pd.DataFrame({'game_id': g.game_id.to_numpy(), 'p16': m.apply_fit(g, fit)}))
    return pd.concat(out, ignore_index=True)


def prod_window_map(d):
    """Supplementary (not in the protocol): production's map history starts in 2021."""
    h = d[d.season >= PROD_MAP_FIRST]; mapped = np.full(len(d), np.nan)
    for y in sorted(h.season.unique()):
        rule = fixed_bands.fit(h, int(y)); k = d.season.eq(y).to_numpy()
        if rule is not None: mapped[k] = fixed_bands.apply(d.loc[k, 'model_spread'], rule)
    return mapped


def forecasts(parts, zero=(), merge_int=False):
    rows = []
    for pack, games in parts:
        pk, gm = transform(pack, zero, merge_int), transform(games, zero, merge_int)
        rows.append(games.merge(weekly(pk, gm), on='game_id', validate='one_to_one'))
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    d = t.prepare(d)
    d['model_spread'] = SPREAD_SCALE*ndtri(np.clip(d.p.to_numpy(float), .005, .995))
    mapped = np.full(len(d), np.nan)
    for y in sorted(d.season.unique()):
        rule = fixed_bands.fit(d, int(y)); k = d.season.eq(y).to_numpy()
        mapped[k] = fixed_bands.apply(d.loc[k, 'model_spread'], rule)
    d['mapped_spread'] = mapped
    d['mapped_spread_prod_window'] = prod_window_map(d)
    return d


def basis(d, b):
    s = {'2015-16': (2015, 2016), '2017-22': (2017, 2022), '2023-25': (2023, 2025)}[b]
    return d[d.season.between(*s)].reset_index(drop=True)


def ll_row(prod, arm, b):
    j = prod[['game_id', 'y', 'p', 'cluster']].merge(arm[['game_id', 'p']], on='game_id', suffixes=('', '_arm'), validate='one_to_one')
    j = j[j.y.notna()]
    mu, se = fi.cmean(fi.ll(j.y, j.p_arm)-fi.ll(j.y, j.p), j.cluster)
    return {'n': len(j), 'll_prod': float(fi.ll(j.y, j.p).mean()), 'll_arm': float(fi.ll(j.y, j.p_arm).mean()),
            'diff_x1000': 1000*mu, 'se_x1000': 1000*se, 'z': mu/se if se > 0 else np.nan}


def ats_record(side, margin):
    side, margin = np.asarray(side, float), np.asarray(margin, float)
    edge = side*margin
    ret = np.where(edge > fixed_bands.EPS, 1/1.1, np.where(edge < -fixed_bands.EPS, -1., 0.))
    bet = side != 0; r = ret[bet]
    w, l = int((r > 0).sum()), int((r < 0).sum()); n = len(r); u = float(r.sum())
    return {'W': w, 'L': l, 'P': n-w-l, 'skips': int((~bet).sum()), 'bets': n, 'units': u,
            'roi': u/n if n else np.nan, 'roi_se': float(r.std(ddof=1)/np.sqrt(n)) if n > 1 else np.nan,
            'cover': w/(w+l) if w+l else np.nan}, ret


def map_reproduction(prod):
    f = pd.read_csv(ROOT/'data/latest/fixed_band_ledger.csv')[['game_id', 'fixed_band_spread']]
    j = prod.merge(f, on='game_id', validate='one_to_one')
    j = j[j.season.between(2023, 2025)]
    err = float(np.nanmax(np.abs(j.fixed_band_spread-j.mapped_spread_prod_window)))
    if err > 1e-9 or j.mapped_spread_prod_window.isna().any():
        raise ValueError(f'production-window map does not reproduce fixed_band_spread ({err})')
    return err


def ats_rows(frames, b, col='mapped_spread', label='median map'):
    """Same rows for every arm: graded, with a spread and a map for every arm."""
    ok = None
    for d in frames.values():
        k = d.set_index('game_id')
        g = k.index[np.isfinite(k.spread_line) & np.isfinite(k.result) & np.isfinite(k[col])]
        ok = set(g) if ok is None else ok & set(g)
    rows, sides = [], {}
    for arm, d in frames.items():
        s = d[d.game_id.isin(ok)].sort_values('game_id').reset_index(drop=True)
        margin = s.result.to_numpy(float) - s.spread_line.to_numpy(float)
        line = s.spread_line.to_numpy(float)
        views = (((label, s[col]), ('raw spread', s.model_spread)) if col == 'mapped_spread' else ((label, s[col]),))
        for view, pred in views:
            side = fixed_bands.pick(pred.to_numpy(float), line)
            rec, ret = ats_record(side, margin)
            sides[(arm, view)] = (side, ret)
            rows.append({'basis': b, 'arm': arm, 'view': view, **rec})
        if arm == 'P' and col == 'mapped_spread':
            for name, side in (('always favorite', np.sign(line)), ('always home', np.ones(len(s)))):
                rec, _ = ats_record(side, margin)
                rows.append({'basis': b, 'arm': name, 'view': 'baseline', **rec})
    for r in rows:
        if r['view'] in (label, 'raw spread') and r['arm'] != 'P':
            sa, ra = sides[(r['arm'], r['view'])]; sp, rp = sides[('P', r['view'])]
            f = sa != sp
            r['flips_vs_P'] = int(f.sum()); r['units_arm_minus_P_on_flips'] = float((ra-rp)[f].sum())
    return rows


def ml_row(prod, arm, b):
    j = prod[['game_id', 'units']].merge(arm[['game_id', 'units']], on='game_id', suffixes=('', '_arm'))
    j = j[j.units.notna() & j.units_arm.notna()]
    return {'bets': len(j), 'units_prod': float(j.units.sum()), 'units_arm': float(j.units_arm.sum())}


def verdict(rows, arm):
    use = [r for r in rows if r['basis'] in VERDICT_BASES.get(arm, BASES)]
    if any(r['z'] >= Z_BAR for r in use): return 'stop'
    need = 2 if len(use) == 3 else len(use)
    return 'forward candidate' if sum(r['diff_x1000'] < 0 for r in use) >= need else 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    parts = season_parts()
    full = {'P': forecasts(parts)}
    repro = fi.reproduction({b: basis(full['P'], b) for b in BASES})
    repro['fixed_band_spread 2023-25'] = map_reproduction(full['P'])
    for arm, a in ARMS.items(): full[arm] = forecasts(parts, a['zero'], a['merge_int'])
    ll, ats, ml = [], [], []
    for b in BASES:
        fr = {k: basis(v, b) for k, v in full.items()}
        for arm in ARMS:
            ll.append({'basis': b, 'arm': arm, 'terms': terms(arm), **ll_row(fr['P'], fr[arm], b)})
            ml.append({'basis': b, 'arm': arm, **ml_row(fr['P'], fr[arm], b)})
        ats += ats_rows(fr, b)
        if b == '2023-25': ats += ats_rows(fr, b, 'mapped_spread_prod_window', 'median map, 2021+ history (supplementary)')
    ll, ats, ml = pd.DataFrame(ll), pd.DataFrame(ats), pd.DataFrame(ml)
    verdicts = {arm: verdict(ll[ll.arm == arm].to_dict('records'), arm) for arm in ARMS}
    ll.to_csv(out/'log_loss.csv', index=False, float_format='%.6g')
    ats.to_csv(out/'ats.csv', index=False, float_format='%.6g')
    ml.to_csv(out/'moneyline_units.csv', index=False, float_format='%.6g')
    pd.concat([d[['game_id', 'season', 'week', 'p', 'model_spread', 'mapped_spread']].assign(arm=k) for k, d in full.items()]
              ).to_csv(out/'forecasts.csv.gz', index=False, float_format='%.6g')
    res = {'protocol': 'research/SLIM_MODEL.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'z_bar': Z_BAR, 'verdicts': verdicts, 'terms': {'P': 29, **{a: terms(a) for a in ARMS}}}
    (out/'results.json').write_text(json.dumps(res, indent=2))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/SLIM_MODEL.md', ROOT/'nfl_model.py', ROOT/'fixed_bands.py', t.OOS_PACK, t.T36_PACK)}, indent=2))
    write_report(res, ll, ats, ml, out)
    return res


def write_report(res, ll, ats, ml, out):
    L = ['# Test 50: slim models from the fit analysis', '',
         f'Protocol: [SLIM_MODEL.md](../SLIM_MODEL.md), committed (`{res["protocol_commit"]}`) before any arm was scored. '
         'Diagnostic only; production v1.18 and the ledger are unchanged. All bases were exposed before the arms were chosen.', '',
         'Reproduction of published forecasts by P: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.', '',
         f'## Log loss (arm minus v1.18, x1000; negative = slim arm better; bar |z| >= {res["z_bar"]:.2f})', '',
         '| Arm | Terms | ' + ' | '.join(BASES) + ' | Verdict |', '|---|---:|' + '---:|'*len(BASES) + '---|']
    for arm in ARMS:
        s = ll[ll.arm == arm].set_index('basis')
        L.append(f'| {arm} | {res["terms"][arm]} | ' + ' | '.join(
            f'{s.loc[b,"diff_x1000"]:+.2f} ± {s.loc[b,"se_x1000"]:.2f} (z {s.loc[b,"z"]:+.1f}, n {int(s.loc[b,"n"])})' for b in BASES)
            + f' | {res["verdicts"][arm]} |')
    L += ['', 'v1.18 log loss per game: ' + ', '.join(f'{b} {ll[ll.basis == b].ll_prod.iloc[0]:.5f}' for b in BASES) +
          '. S3 verdict counts 2015-16 only (protocol).', '',
          '## ATS, flat 1u at -110 (same rows for every arm; each arm uses its own prior-season median map)', '',
          'Break-even cover rate 52.4%. ROI SE has pushes in the denominator. Flips and flip units are against v1.18 in the same view.', '',
          '| Basis | Arm | View | W-L-P | Skips | Units | ROI ± SE | Cover | Flips | Units on flips (arm − P) |',
          '|---|---|---|---|---:|---:|---:|---:|---:|---:|']
    for _, r in ats.iterrows():
        fl = '' if pd.isna(r.get('flips_vs_P')) else f'{int(r.flips_vs_P)}'
        fu = '' if pd.isna(r.get('units_arm_minus_P_on_flips')) else f'{r.units_arm_minus_P_on_flips:+.1f}'
        L.append(f'| {r.basis} | {r.arm} | {r.view} | {r.W}-{r.L}-{r.P} | {r.skips} | {r.units:+.1f} | '
                 f'{100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | {100*r.cover:.1f}% | {fl} | {fu} |')
    L += ['', '## Moneyline flat units (legacy, same bets)', '', '| Basis | Arm | Bets | v1.18 | Arm |', '|---|---|---:|---:|---:|']
    for _, r in ml.iterrows():
        L.append(f'| {r.basis} | {r.arm} | {r.bets} | {r.units_prod:+.1f} | {r.units_arm:+.1f} |')
    (out/'REPORT.md').write_text('\n'.join(L) + '\n')


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
