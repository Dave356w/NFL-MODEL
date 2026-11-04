"""Test 51: per-team market-implied points in the v1.19 fit; see MARKET_IMPLIED.md.

    python research/market_implied.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logit, ndtri
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import fixed_bands  # noqa: E402
import residual_trends as t  # noqa: E402
import feature_importance as fi  # noqa: E402
import slim_model as sm  # noqa: E402

OUT = ROOT/'research/market_implied_results'
SCORES = ROOT/'research/market_implied_inputs/schedule_scores.csv'
S3_FORECASTS = ROOT/'research/slim_model_results/forecasts.csv.gz'
PROTOCOL_COMMIT = '2e8c50c'
RECIPE = m.PRODUCT_RECIPE  # v1.19
BASES = fi.BASES
K = 2
Z_BAR = float(norm.ppf(1-.05/K/2))  # 2.24
REFERENCE_POINTS = 22.5
S3_CSV_TOL = 1e-5  # Test 50 stored forecasts at 6 significant digits

ARMS = {'A this game\'s implied points': ['mkt_home_implied', 'mkt_away_implied'],
        'B history vs implied points': ['d__mkt_off_resid', 'd__mkt_def_resid']}
ADDED = [c for v in ARMS.values() for c in v]

_model_terms = m.model_terms


def _model_terms_with_extra(recipe):
    """Research-only: append a recipe's 'extra_terms' to the fitted context terms (context ridge)."""
    main, ctx = _model_terms({k: v for k, v in recipe.items() if k != 'extra_terms'})
    return main, ctx + list(recipe.get('extra_terms', ()))


m.model_terms = _model_terms_with_extra


# --- inputs ---------------------------------------------------------------------------------------

def scores():
    g = pd.read_csv(SCORES)
    g['home_implied'] = (g.total_line + g.spread_line)/2
    g['away_implied'] = (g.total_line - g.spread_line)/2
    return g


def team_residual_rows(g):
    """Two rows per game: o = points - own implied, d = points allowed - opponent's implied."""
    rows = []
    for team, pts, opp_pts, own, other in (('home_team', 'home_score', 'away_score', 'home_implied', 'away_implied'),
                                           ('away_team', 'away_score', 'home_score', 'away_implied', 'home_implied')):
        rows.append(pd.DataFrame({'game_id': g.game_id, 'season': g.season, 'week': g.week, 'team': g[team],
                                  'o': g[pts]-g[own], 'd': g[opp_pts]-g[other]}))
    return pd.concat(rows, ignore_index=True).sort_values(['season', 'week', 'game_id']).reset_index(drop=True)


def pregame_residual(r, team, year, week):
    """Production's decayed point-margin rule: h8 by games ago, offseason halving, 4 pseudo-games at 0."""
    h = r[(r.team == team) & m.before(r, year, week) & (r.season >= year-m.MAX_HISTORY_SEASONS)]
    out = {}
    for c in ('o', 'd'):
        x = h[c].to_numpy(float); ok = np.isfinite(x); n = len(x)
        age = np.arange(n-1, -1, -1, dtype=float)
        w = np.exp2(-age/m.LEGACY_PRODUCT_RECIPE['half_life'])*np.power(m.OFFSEASON_RETENTION, year-h.season.to_numpy(float))
        out[c] = float(np.dot(w[ok], x[ok])/(w[ok].sum()+m.PRIOR_EQUIVALENT_GAMES))
    return out


def lookahead_check(g):
    """Negative fixture: changing a game's own and later scores leaves its pregame residuals unchanged.
    Positive fixture: changing an earlier game's score moves them."""
    gid = '2017_09_KC_DAL'; row = g[g.game_id == gid].iloc[0]; y, w = int(row.season), int(row.week)
    base = pregame_residual(team_residual_rows(g), row.home_team, y, w)
    later = g.copy(); k = ~m.before(later, y, w); later.loc[k, ['home_score', 'away_score']] += 30
    if pregame_residual(team_residual_rows(later), row.home_team, y, w) != base: raise ValueError('Arm B lookahead')
    earlier = g.copy(); k = m.before(earlier, y, w) & earlier.home_team.eq(row.home_team) & earlier.season.eq(y)
    earlier.loc[earlier.index[k][-1], 'home_score'] += 30
    if pregame_residual(team_residual_rows(earlier), row.home_team, y, w)['o'] <= base['o']:
        raise ValueError('Arm B ignores earlier games')
    return True


def add_market_terms(pack, g):
    """Arm A and arm B columns for every pack row (pack rows outside the score file stay NaN -> 0)."""
    f = pack.copy()
    j = f[['game_id']].merge(g[['game_id', 'home_implied', 'away_implied']], on='game_id', how='left', validate='one_to_one')
    f['mkt_home_implied'] = (j.home_implied-REFERENCE_POINTS).to_numpy()
    f['mkt_away_implied'] = (j.away_implied-REFERENCE_POINTS).to_numpy()
    r = team_residual_rows(g)
    cache = {}
    off, dfn = [], []
    for row in f.itertuples():
        v = {}
        for side, team in (('h', row.home), ('a', row.away)):
            key = (team, int(row.season), int(row.week))
            if key not in cache: cache[key] = pregame_residual(r, *key)
            v[side] = cache[key]
        off.append(v['h']['o']-v['a']['o']); dfn.append(v['h']['d']-v['a']['d'])
    f['d__mkt_off_resid'] = off; f['d__mkt_def_resid'] = dfn
    return f


def season_parts(g):
    oos, t36 = add_market_terms(pd.read_csv(t.OOS_PACK), g), add_market_terms(pd.read_csv(t.T36_PACK), g)
    return [(oos, oos[oos.season.between(2014, 2020)]), (t36, t36[t36.season.between(2021, 2025)])]


# --- forecasts ------------------------------------------------------------------------------------

def weekly(pack, games, recipe):
    out, fits = [], {}
    for (y, w), gm in games.groupby(['season', 'week']):
        train = pack[m.before(pack, int(y), int(w))]
        if not m.before(train, int(y), int(w)).all(): raise ValueError('Training includes current/future week')
        try:
            fit = m.fit_composite(train, recipe, int(y), int(w))
        except ValueError as e:
            if 'eligible labeled games' in str(e): continue  # early 2014 weeks: not enough history
            raise
        fits[(int(y), int(w))] = fit
        out.append(pd.DataFrame({'game_id': gm.game_id.to_numpy(), 'p16': m.apply_fit(gm, fit, raw=True),
                                 'p_direct': m.apply_fit(gm, fit)}))
    return pd.concat(out, ignore_index=True), fits


def forecasts(parts, extra=()):
    recipe = dict(RECIPE, extra_terms=list(extra)) if extra else RECIPE
    rows, fits = [], {}
    for pack, games in parts:
        w, f = weekly(pack, games, recipe); fits.update(f)
        rows.append(games.merge(w, on='game_id', validate='one_to_one'))
    d = pd.concat(rows, ignore_index=True).merge(t._totals(), on='game_id', how='left', validate='one_to_one')
    d = t.prepare(d)
    err = float(np.nanmax(np.abs(d.p-d.p_direct)))
    if err > 1e-12: raise ValueError(f'prepare() penalty does not match apply_fit ({err})')
    d['model_spread'] = sm.SPREAD_SCALE*ndtri(np.clip(d.p.to_numpy(float), .005, .995))
    mapped = np.full(len(d), np.nan)
    for y in sorted(d.season.unique()):
        rule = fixed_bands.fit(d, int(y)); k = d.season.eq(y).to_numpy()
        mapped[k] = fixed_bands.apply(d.loc[k, 'model_spread'], rule)
    d['mapped_spread'] = mapped
    d['mapped_spread_prod_window'] = sm.prod_window_map(d)
    return d, fits


def reproduction(prod):
    errs = {}
    r = pd.read_csv(t.RETRO)[['game_id', 'model_wp']]
    j = prod[prod.season.between(2021, 2025)].merge(r, on='game_id', validate='one_to_one')
    errs['v1.19 retro_ledger 2021-25'] = float(np.max(np.abs(j.p-j.model_wp)))
    if errs['v1.19 retro_ledger 2021-25'] > 1e-9: raise ValueError(f'P does not reproduce v1.19 ({errs})')
    s3 = pd.read_csv(S3_FORECASTS); s3 = s3[s3.arm == 'S3 core'][['game_id', 'p']]
    j = prod[prod.season.between(2014, 2020)].merge(s3, on='game_id', suffixes=('', '_s3'), validate='one_to_one')
    errs['Test 50 S3 2014-20 (6-digit CSV)'] = float(np.max(np.abs(j.p-j.p_s3)))
    if errs['Test 50 S3 2014-20 (6-digit CSV)'] > S3_CSV_TOL: raise ValueError(f'P does not reproduce Test 50 S3 ({errs})')
    errs['fixed_band_spread 2023-25'] = sm.map_reproduction(prod)
    return errs


# --- summaries ------------------------------------------------------------------------------------

def last_fit_coefficients(fits, b, terms):
    s = {'2015-16': 2016, '2017-22': 2022, '2023-25': 2025}[b]
    key = max(k for k in fits if k[0] == s)
    f = fits[key]; ix = {n: i for i, n in enumerate(f['names'])}
    return {'fit_season': key[0], 'fit_week': key[1], **{n: float(f['beta'][ix[n]]) for n in terms}}


def term_correlations(prod, b):
    rows = []
    dep = logit(prod.p)-logit(prod.q)
    for c in ADDED:
        x = prod[c].to_numpy(float); k = np.isfinite(x)
        rows.append({'basis': b, 'term': c, 'mean': float(np.mean(x[k])), 'sd': float(np.std(x[k])),
                     'corr_market_logit': float(np.corrcoef(x[k], prod.market_logit[k])[0, 1]),
                     'corr_P_departure': float(np.corrcoef(x[k], dep[k])[0, 1])})
    return rows


def verdict(rows):
    if any(r['z'] >= Z_BAR for r in rows): return 'stop'
    if all(r['diff_x1000'] < 0 for r in rows) and any(r['z'] <= -Z_BAR for r in rows): return 'better'
    if sum(r['diff_x1000'] < 0 for r in rows) >= 2: return 'forward candidate'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    g = scores()
    lookahead_check(g)
    parts = season_parts(g)
    full, fits = {}, {}
    full['P'], fits['P'] = forecasts(parts)
    repro = reproduction(full['P'])
    for arm, extra in ARMS.items(): full[arm], fits[arm] = forecasts(parts, extra)
    ll, ats, ml, coef, corr = [], [], [], [], []
    for b in BASES:
        fr = {k: sm.basis(v, b) for k, v in full.items()}
        for arm, extra in ARMS.items():
            ll.append({'basis': b, 'arm': arm, **sm.ll_row(fr['P'], fr[arm], b)})
            ml.append({'basis': b, 'arm': arm, **sm.ml_row(fr['P'], fr[arm], b)})
            coef.append({'basis': b, 'arm': arm, **last_fit_coefficients(fits[arm], b, extra)})
        corr += term_correlations(fr['P'], b)
        ats += sm.ats_rows(fr, b)
        if b == '2023-25': ats += sm.ats_rows(fr, b, 'mapped_spread_prod_window', 'median map, 2021+ history (supplementary)')
    ll, ats, ml, coef, corr = map(pd.DataFrame, (ll, ats, ml, coef, corr))
    verdicts = {arm: verdict(ll[ll.arm == arm].to_dict('records')) for arm in ARMS}
    ll.to_csv(out/'log_loss.csv', index=False, float_format='%.6g')
    ats.to_csv(out/'ats.csv', index=False, float_format='%.6g')
    ml.to_csv(out/'moneyline_units.csv', index=False, float_format='%.6g')
    coef.to_csv(out/'coefficients.csv', index=False, float_format='%.6g')
    corr.to_csv(out/'term_correlations.csv', index=False, float_format='%.6g')
    pd.concat([d[['game_id', 'season', 'week', 'p', 'model_spread', 'mapped_spread']].assign(arm=k) for k, d in full.items()]
              ).to_csv(out/'forecasts.csv.gz', index=False, float_format='%.6g')
    res = {'protocol': 'research/MARKET_IMPLIED.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction_max_error': repro,
           'z_bar': Z_BAR, 'verdicts': verdicts}
    (out/'results.json').write_text(json.dumps(res, indent=2))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/MARKET_IMPLIED.md', ROOT/'nfl_model.py', ROOT/'fixed_bands.py', SCORES,
        t.OOS_PACK, t.T36_PACK, S3_FORECASTS)}, indent=2))
    write_report(res, ll, ats, ml, coef, corr, out)
    return res


def write_report(res, ll, ats, ml, coef, corr, out):
    L = ['# Test 51: per-team market-implied points in the v1.19 fit', '',
         f'Protocol: [MARKET_IMPLIED.md](../MARKET_IMPLIED.md), committed (`{res["protocol_commit"]}`) before any arm was scored. '
         'Diagnostic only; production v1.19 and the ledger are unchanged. All bases were exposed earlier (see protocol).', '',
         'Reproduction by P: ' + ', '.join(f'{k} {v:.1e}' for k, v in res['reproduction_max_error'].items()) + '.', '',
         f'## Log loss (arm minus v1.19, x1000; negative = arm better; bar |z| >= {res["z_bar"]:.2f})', '',
         '| Arm | ' + ' | '.join(BASES) + ' | Verdict |', '|---|' + '---:|'*len(BASES) + '---|']
    for arm in ARMS:
        s = ll[ll.arm == arm].set_index('basis')
        L.append(f'| {arm} | ' + ' | '.join(
            f'{s.loc[b,"diff_x1000"]:+.2f} ± {s.loc[b,"se_x1000"]:.2f} (z {s.loc[b,"z"]:+.1f}, n {int(s.loc[b,"n"])})' for b in BASES)
            + f' | {res["verdicts"][arm]} |')
    L += ['', 'v1.19 log loss per game: ' + ', '.join(f'{b} {ll[ll.basis == b].ll_prod.iloc[0]:.5f}' for b in BASES) + '.', '',
          '## Added coefficients in the last fit of each basis (per weighted-RMS unit, log-odds)', '',
          '| Basis | Arm | Fit | Coefficients |', '|---|---|---|---|']
    for _, r in coef.iterrows():
        cs = ', '.join(f'{c} {r[c]:+.3f}' for c in ADDED if c in r and pd.notna(r[c]))
        L.append(f'| {r.basis} | {r.arm} | {int(r.fit_season)} wk {int(r.fit_week)} | {cs} |')
    L += ['', '## Added terms: spread and overlap with the market', '',
          '| Basis | Term | Mean | SD | Corr with market log-odds | Corr with v1.19 departure |', '|---|---|---:|---:|---:|---:|']
    for _, r in corr.iterrows():
        L.append(f'| {r.basis} | {r.term} | {r["mean"]:+.2f} | {r.sd:.2f} | {r.corr_market_logit:+.2f} | {r.corr_P_departure:+.2f} |')
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
