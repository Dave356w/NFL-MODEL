"""Test 42: a model built only from features production does not use; see DISJOINT_FEATURES.md.

    python research/disjoint_features.py

Reads only committed files; no network access. Never writes data/ or the ledger. Development evidence only.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logit, ndtr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import residual_trends as t  # noqa: E402
import feature_importance as fi  # noqa: E402
import model_updates as mu  # noqa: E402
import kalman_ratings as kr  # noqa: E402
import kalman_iterations as ki  # noqa: E402

OUT = ROOT/'research/disjoint_features_results'
CONTEXT_FILE = ROOT/'research/disjoint_features_inputs/schedule_context.csv'
PROTOCOL_COMMIT = '69b104c'
RATINGS = ['pass_edge', 'rush_edge', 'margin_edge', 'ats_edge']
CONTEXT = ['rest_diff', 'ml_spread_gap', 'total_x_market', 'div_x_market']
DISJOINT = RATINGS+CONTEXT
PRODUCTION = list(m.feature_names(m.LEGACY_PRODUCT_RECIPE['family']))+list(m.PRODUCT_CONTEXT_NAMES)
ARMS = {'disjoint': DISJOINT, 'production_plus_disjoint': PRODUCTION+DISJOINT,
        'disjoint_ratings': RATINGS, 'disjoint_context': CONTEXT}
PRIMARY = ('disjoint', 'production_plus_disjoint', 'blend')
DESCRIPTIVE = ('disjoint_ratings', 'disjoint_context')
if set(DISJOINT) & set(PRODUCTION): raise RuntimeError('Disjoint features overlap production')


def market_structure(df):
    """The schedule and market-structure features, from columns already on the frame."""
    d = df.copy()
    lq = logit(np.clip(d.q.to_numpy(float), 1e-5, 1-1e-5))
    q_spread = ndtr(pd.to_numeric(d.spread_line, errors='coerce').to_numpy(float)/m.MARKET_SIGMA)
    d['ml_spread_gap'] = lq-logit(np.clip(q_spread, 1e-5, 1-1e-5))
    d['total_x_market'] = (pd.to_numeric(d.total_line, errors='coerce')-45.)/10.*lq
    d['div_x_market'] = pd.to_numeric(d.div_game, errors='coerce')*lq
    d['rest_diff'] = np.clip(pd.to_numeric(d.home_rest, errors='coerce')-pd.to_numeric(d.away_rest, errors='coerce'), -7, 7)
    return d


def augment(df, edges, ctx):
    """Attach the disjoint features (missing stays NaN; the fit treats it as 0, production's convention)."""
    d = df.drop(columns=[c for c in ('total_line',) if c in df]).merge(t._totals(), on='game_id', how='left', validate='many_to_one')
    d = d.merge(ctx[['game_id', 'div_game', 'home_rest', 'away_rest']], on='game_id', how='left', validate='many_to_one')
    d = d.merge(edges[['game_id']+RATINGS], on='game_id', how='left', validate='many_to_one')
    return market_structure(d)


def arm_frame(parts, edges, ctx, names, ridge=.1):
    rows, coefs = [], []
    for pack, games in parts:
        pk, gm = augment(pack, edges, ctx), augment(games, edges, ctx)
        for (y, w), g in gm.groupby(['season', 'week']):
            f = kr.fit(pk[m.before(pk, int(y), int(w))], names, int(y), int(w), ridge=ridge)
            rows.append(g.assign(p16=kr.predict(g, f)))
            coefs.append({'season': int(y), 'week': int(w), **dict(zip(names, map(float, f['beta'])))})
    d = pd.concat(rows, ignore_index=True)
    return t.prepare(d), pd.DataFrame(coefs)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    edges, tuning = ki.all_edges()
    ctx = pd.read_csv(CONTEXT_FILE)
    parts = {**fi.basis_parts(), '2026 wk1-5 (diagnostic)': mu.extra_parts()['2026 wk1-5 (diagnostic)']}
    prod = {b: mu.basis_frame(p, 'production', b) for b, p in parts.items()}
    repro = fi.reproduction({b: prod[b] for b in fi.BASES})
    # production_plus_disjoint with no disjoint signal must equal production: check the joint fitter on production's names.
    frames, coefs, rows, mkt, corr, cover = {}, {}, [], [], {}, {}
    for b, p in parts.items():
        for a, names in ARMS.items():
            frames[(b, a)], c = arm_frame(p, edges, ctx, names)
            coefs[(b, a)] = {n: float(c[n].mean()) for n in names if n in DISJOINT or n in ('site', 'd__avail__qb_delta')}
        frames[(b, 'blend')] = kr.blend_frame(prod[b], frames[(b, 'disjoint')])
        j = prod[b][['game_id', 'departure16']].merge(frames[(b, 'disjoint')][['game_id', 'departure16']], on='game_id', suffixes=('_p', '_d'))
        corr[b] = float(np.corrcoef(j.departure16_p, j.departure16_d)[0, 1])
        aug = augment(prod[b][['game_id', 'q', 'spread_line']], edges, ctx)
        cover[b] = {n: float(aug[n].notna().mean()) for n in DISJOINT}
        for a in PRIMARY+DESCRIPTIVE:
            rows += kr.compare(prod[b], frames[(b, a)], b, a)
            g, se = kr.vs_market(frames[(b, a)]); mkt.append({'basis': b, 'arm': a, 'll_gain_vs_market_x1000': g, 'se_x1000': se})
        g, se = kr.vs_market(prod[b]); mkt.append({'basis': b, 'arm': 'production', 'll_gain_vs_market_x1000': g, 'se_x1000': se})
    res = pd.DataFrame(rows); res.to_csv(out/'arms.csv', index=False, float_format='%.6g')
    mkt = pd.DataFrame(mkt); mkt.to_csv(out/'vs_market.csv', index=False, float_format='%.6g')
    pd.concat([d[['game_id', 'p']].assign(basis=b, arm=a) for (b, a), d in frames.items()] +
              [d[['game_id', 'p']].assign(basis=b, arm='production') for b, d in prod.items()]).to_csv(
        out/'predictions.csv.gz', index=False, float_format='%.6g')
    prod_roi = {b: m.roi_summary(m.flat_bets(d[d.bet].assign(model_wp=d.p[d.bet]))) for b, d in prod.items()}
    info = {'protocol': 'research/DISJOINT_FEATURES.md', 'protocol_commit': PROTOCOL_COMMIT, 'level': kr.LEVEL,
            'reproduction_max_error': repro, 'verdicts': {a: kr.verdict(res[res.arm == a]) for a in PRIMARY},
            'departure_corr_prod_vs_disjoint': corr, 'feature_coverage': cover,
            'coefficients_mean_per_sd': {f'{b}|{a}': v for (b, a), v in coefs.items()},
            'binary_games': {b: int(d.y.notna().sum()) for b, d in prod.items()},
            'production_roi': {b: {k: float(v) if isinstance(v, (int, float, np.integer, np.floating)) else v for k, v in s.items()}
                               for b, s in prod_roi.items()}}
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=True))
    prov = {str(p.relative_to(ROOT)): sha(p) for p in (Path(__file__), ROOT/'research/DISJOINT_FEATURES.md', ROOT/'research/kalman_iterations.py',
                                                       ROOT/'research/kalman_ratings.py', ROOT/'nfl_model.py', CONTEXT_FILE, kr.TEAM_GAMES,
                                                       t.OOS_PACK, t.T36_PACK, t.OOS_PRED, t.HELDOUT, t.RETRO, t.TOTALS)}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2))
    write_report(info, res, mkt, prod_roi, out)
    return info, res, mkt


def write_report(info, res, mkt, prod_roi, out):
    B = list(fi.BASES); D = '2026 wk1-5 (diagnostic)'; allr = res[res.context == 'all']
    L = ['# Test 42: a model built only from features production does not use', '',
         f"Protocol: [DISJOINT_FEATURES.md](../DISJOINT_FEATURES.md), pushed (`{PROTOCOL_COMMIT}`) before any feature was built or scored. "
         'Production v1.18 and the ledger are unchanged. Development evidence only.', '',
         'Production reproduces its published forecasts: ' + ', '.join(f'{k} {v:.1e}' for k, v in info['reproduction_max_error'].items()) + '.', '',
         '**Disjoint features:** ratings `pass_edge`, `rush_edge`, `margin_edge`, `ats_edge`; schedule `rest_diff`; market structure '
         '`ml_spread_gap`, `total_x_market`, `div_x_market`. None is a production input.', '',
         '## Verdicts (log-loss gain over production decides)', '']
    for a, v in info['verdicts'].items(): L.append(f"- **{a}**: {v}")
    L += ['', 'Rule: better if the gain is positive on all three bases and its 98.33% interval excludes zero on at least one; not better if '
          '<= 0 on two or more; otherwise unresolved.', '',
          '## Log-loss gain over production (x1000 per game; [98.33% interval])', '',
          '| Arm | ' + ' | '.join(B) + ' | 2026 wk1-5 (diag.) |', '|---|' + '---:|'*(len(B)+1)]
    for a in PRIMARY+DESCRIPTIVE:
        r = allr[allr.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join(f"{r.loc[b, 'll_gain_x1000']:+.2f} [{r.loc[b, 'lo_x1000']:+.2f}, {r.loc[b, 'hi_x1000']:+.2f}]" for b in B)
                 + f" | {r.loc[D, 'll_gain_x1000']:+.2f} |")
    L += ['', '## Log-loss gain over the market (x1000 per game ± SE)', '', '| Model | ' + ' | '.join(B) + ' | 2026 wk1-5 |', '|---|' + '---:|'*(len(B)+1)]
    for a in ('production',)+PRIMARY+DESCRIPTIVE:
        r = mkt[mkt.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join(f"{r.loc[b, 'll_gain_vs_market_x1000']:+.2f} ± {r.loc[b, 'se_x1000']:.2f}" for b in B+[D]) + ' |')
    L += ['', '## Flat 1u ROI (goal metric; reported, not used for the verdict)', '',
          '| Model | ' + ' | '.join(B) + ' |', '|---|' + '---:|'*len(B),
          '| production | ' + ' | '.join(f"{100*prod_roi[b]['roi']:+.2f}% ± {100*prod_roi[b]['roi_se']:.2f} ({prod_roi[b]['units']:+.1f}u)" for b in B) + ' |']
    for a in PRIMARY+DESCRIPTIVE:
        r = allr[allr.arm == a].set_index('basis')
        L.append(f"| {a} | " + ' | '.join(f"{100*r.loc[b, 'roi']:+.2f}% ± {100*r.loc[b, 'roi_se']:.2f}; {r.loc[b, 'units_vs_prod']:+.1f}u vs prod, "
                                          f"{int(r.loc[b, 'side_flips'])} flips" for b in B) + ' |')
    r0 = allr[allr.arm == 'disjoint'].set_index('basis')
    L += ['', 'Same-row market favorite and market-correct null: ' + '; '.join(
        f"{b} favorite {r0.loc[b, 'fav_units']:+.1f}u, null {100*r0.loc[b, 'null']:+.2f}%" for b in B) + '.', '',
          '## By total band (log-loss gain over production x1000; units vs production)', '',
          '| Arm | Basis | total <= 41 | total 41.5-47 | total >= 47.5 |', '|---|---|---:|---:|---:|']
    for a in PRIMARY:
        for b in B:
            r = res[(res.arm == a) & (res.basis == b)].set_index('context')
            L.append(f"| {a} | {b} | " + ' | '.join(f"{r.loc[c, 'll_gain_x1000']:+.2f} ({r.loc[c, 'units_vs_prod']:+.1f}u)"
                                                    for c in ('total_low', 'total_mid', 'total_high')) + ' |')
    L += ['', '## What the disjoint features learn (mean fitted coefficient per SD over the weekly fits)', '',
          '| Feature | ' + ' | '.join(f'{b} disjoint' for b in B) + ' | ' + ' | '.join(f'{b} joint' for b in B) + ' |', '|---|' + '---:|'*(2*len(B))]
    for n in DISJOINT:
        L.append(f"| {n} | " + ' | '.join(f"{info['coefficients_mean_per_sd'][f'{b}|disjoint'][n]:+.3f}" for b in B) + ' | '
                 + ' | '.join(f"{info['coefficients_mean_per_sd'][f'{b}|production_plus_disjoint'][n]:+.3f}" for b in B) + ' |')
    L += ['', 'Correlation of production\'s and the disjoint model\'s departures from the market, game by game: '
          + ', '.join(f'{b} {v:+.2f}' for b, v in info['departure_corr_prod_vs_disjoint'].items()) + '.', '',
          'Feature coverage (share of evaluation games with a value; missing counts as 0): ' + '; '.join(
              f"{b}: " + ', '.join(f'{n} {v:.0%}' for n, v in c.items() if v < .999) for b, c in info['feature_coverage'].items()
              if any(v < .999 for v in c.values())) + ('' if any(any(v < .999 for v in c.values()) for c in info['feature_coverage'].values())
                                                      else 'complete on every basis') + '.', '',
          '## Limits', '',
          'Exposed history. Rest and the ratings were examined before (Tests 20, 40, 41); the market-structure features are new. History uses '
          'the last recorded lines for q, the spread and the total alike. A "better" verdict would justify only a forward shadow test. Tables: '
          '`arms.csv`, `vs_market.csv`, `predictions.csv.gz`.', '', 'Run: `python research/disjoint_features.py`.']
    (out/'REPORT.md').write_text('\n'.join(L)+'\n')


if __name__ == '__main__':
    run()
