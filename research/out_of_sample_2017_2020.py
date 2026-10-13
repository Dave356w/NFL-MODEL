"""One-time out-of-sample 2017-2020 test of v1.16; see OUT_OF_SAMPLE_2017_2020.md.

`--prepare` downloads 2013-2020 inputs, freezes the feature pack and checks the
pipeline against the committed v1.16 pack; it scores nothing. The default run
scores the pre-registered arms from the frozen pack without network access.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
import context_shrinkage as s

m, p, ROOT = s.m, s.p, s.ROOT
CONTEXTS = s.CONTEXTS
RECIPE = m.LEGACY_PRODUCT_RECIPE
FEATURES = m.feature_names(RECIPE['family'])
YEARS = list(range(2013, 2021))
SCORED = (2017, 2020)
CLOSE = .60
ARMS = ('production', 'close_fit', 'v116_close_only')
LEVEL = .975
OUT = ROOT/'research/out_of_sample_results'
PACK = 'frozen_features_2013_2020.csv.gz'
REFERENCE_PACK = ROOT/'research/shrinkage_results/frozen_training_features.csv.gz'
BASES = {'primary': 'One-time out-of-sample basis: 2017-2020 regular seasons, 2013-2016 training history only; '
                    'exposure disclosed in the protocol (Test 32, Test 24, warm-up use)'}


def protect(path):
    path = Path(path).resolve()
    if any(path == x or x in path.parents for x in (ROOT/'data', ROOT/'public')):
        raise ValueError('Research cannot write production outputs')
    return path


def build_features(schedules, boxes, av):
    """v1.16 inputs exactly as the committed pack builds them."""
    f8 = m.lagged_features(boxes, schedules, 8., av); f16 = m.lagged_features(boxes, schedules, 16., av)
    if f8.game_id.tolist() != f16.game_id.tolist(): raise ValueError('Profile alignment mismatch')
    desc, refs = m.pass_contexts(f16)
    f = m.attach_moneylines(f8, schedules); f['q'] = m.market_ml_wp(f); f = pd.concat([f, desc], axis=1)
    cols = list(dict.fromkeys(p.BASE_COLS+['ready']+FEATURES+CONTEXTS))
    return f[cols].copy(), refs


PEAK_REPAIRS = []
STRICT_PEAKS = m.aggregate_score_peaks


def repaired_score_peaks(pbp, schedule):
    """Production peaks game by game; where clock order fails only the monotone check
    (a mis-stamped quarter or clock upstream), re-order that game's scoring plays by play ID
    and accept it only if that order is monotone and ends at the official final score."""
    parts = []
    for gid in schedule.game_id:
        one = schedule[schedule.game_id == gid]
        try: parts.append(STRICT_PEAKS(pbp[pbp.game_id == gid], one))
        except ValueError as error:
            if 'not monotone' not in str(error): raise
            g = one.iloc[0]
            states = pbp[(pbp.game_id == gid) & pbp.season_type.eq('REG')]
            if 'play_deleted' in states: states = states[m.numeric(states, 'play_deleted') != 1]
            states = states[states.sp.eq(1)].sort_values('play_id')
            scores = states[['total_home_score', 'total_away_score']]
            final = tuple(scores.iloc[-1]) if len(scores) else None
            if scores.isna().any().any() or (scores.diff() < 0).any().any() or final != (g.home_score, g.away_score):
                raise
            margin = (scores.total_home_score-scores.total_away_score).to_numpy(float)
            lead, deficit = max(0., float(margin.max())), max(0., float(-margin.min()))
            parts.append(pd.DataFrame([{'game_id': gid, 'team': g.home_team, 'max_lead': lead, 'max_deficit': deficit},
                                       {'game_id': gid, 'team': g.away_team, 'max_lead': deficit, 'max_deficit': lead}]))
            PEAK_REPAIRS.append({'game_id': gid, 'rule': 'scoring plays re-ordered by play ID',
                                 'home_max_lead': lead, 'home_max_deficit': deficit})
    return pd.concat(parts, ignore_index=True) if parts else STRICT_PEAKS(pbp, schedule)


def load_inputs(input_dir):
    """Schedules, team boxes, QB rows and raw availability inputs, as the research packs load them."""
    import concurrent.futures
    from scipy.special import ndtr
    import nflreadpy as nfl
    input_dir = Path(input_dir).resolve(); input_dir.mkdir(parents=True, exist_ok=True)
    m.CACHE_DIR = str(input_dir/'cache'); m.OUTPUT_ROOT = input_dir; m.UPSTREAM_RETRIES = 2
    s = nfl.load_schedules(YEARS).to_pandas()
    s = m.normalize_teams(s[s.game_type == 'REG'].copy())
    s['home won'] = s.result.map(m.won)
    s['site'] = np.where(s.location.str.lower() == 'neutral', 0., 1.)
    s['market WP'] = ndtr(s.spread_line/m.MARKET_SIGMA)
    def boxes(y):
        b, qb = m.load_boxes(y, s[s.season == y]); print('boxes ready', y, flush=True); return b, qb
    m.aggregate_score_peaks = repaired_score_peaks
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            raw = pool.submit(m.load_availability, YEARS, 2026)
            parts = list(pool.map(boxes, YEARS))
            a = raw.result()
    finally:
        m.aggregate_score_peaks = STRICT_PEAKS
    box = m.validate_boxes(pd.concat([x[0] for x in parts], ignore_index=True))
    qb = pd.concat([x[1] for x in parts], ignore_index=True)
    return s, box, qb, a


def availability(s, qb, a, years):
    """Availability table from inputs of `years` only, so earlier seasons cannot leak into a window check."""
    keep = lambda d: d[d.season.isin(years)].copy()
    return m.availability_table(m.availability_targets(keep(s)), keep(qb), keep(a['snaps']), keep(a['inj']),
                                keep(a['rost']), depth=a.get('depth'))


def prepare(input_dir, out):
    """Download inputs, freeze the 2013-2020 pack and compare 2019-20 with the committed pack."""
    schedules, boxes, qb, a = load_inputs(input_dir)
    f, refs = build_features(schedules, boxes, availability(schedules, qb, a, YEARS))
    out.mkdir(parents=True, exist_ok=True)
    f.to_csv(out/PACK, index=False, compression={'method': 'gzip', 'mtime': 0})
    refs.to_csv(out/'normalization_references.csv', index=False)
    (out/'score_peak_repairs.json').write_text(json.dumps(sorted(PEAK_REPAIRS, key=lambda r: r['game_id']), indent=2)+'\n')
    # Pipeline check: the committed pack started in 2019, so rebuild 2019-20 from their inputs alone.
    window = [2019, 2020]
    keep = lambda d: d[d.season.isin(window)].copy()
    check, _ = build_features(keep(schedules), keep(boxes), availability(schedules, qb, a, window))
    ref = pd.read_csv(REFERENCE_PACK); ref = ref[ref.season.between(2019, 2020)].set_index('game_id')
    mine = check.set_index('game_id').reindex(ref.index)
    cols = FEATURES+CONTEXTS+['q']
    diff = (mine[cols]-ref[cols]).abs()
    both = mine[cols].notna() & ref[cols].notna()
    result = {'games_compared': int(len(ref)), 'missing_in_rebuild': int(mine['season'].isna().sum()),
              'ready_agreement': float((mine.ready.astype(bool) == ref.ready.astype(bool)).mean()),
              'missingness_agreement': float((mine[cols].isna() == ref[cols].isna()).to_numpy().mean()),
              'max_abs_difference': float(np.nanmax(diff.where(both).to_numpy())),
              'games_identical_within_1e-9': float((diff.where(both).fillna(0) <= 1e-9).all(axis=1).mean()),
              'worst_columns': diff.where(both).max().sort_values(ascending=False).head(5).round(12).to_dict()}
    (out/'pipeline_check.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2), flush=True)
    return result


def close(frame):
    """Games whose no-vig market favorite is under the pre-registered 60% line."""
    return (np.maximum(frame.q, 1-frame.q) < CLOSE).to_numpy()


def eligible(f):
    return f.ready.astype(bool) & f['home won'].isin([0., 1.]) & np.isfinite(f.q) & np.isfinite(f[CONTEXTS]).all(axis=1)


def fit_arm(train, year, week, arm):
    if not m.before(train, year, week).all(): raise ValueError('Training includes current/future week')
    rows = train[eligible(train)]
    if arm == 'close_fit': rows = rows[close(rows)]
    fitted = m.fit_composite(rows, RECIPE, int(year), int(week))
    if fitted['training_games'] != len(rows): raise ValueError('Training rows differ from eligible rows')
    return fitted


def forecast(test, fitted, arm, production=None):
    """close_fit and v116_close_only forecast close games only; elsewhere they return q."""
    if arm == 'production': return m.apply_fit(test, fitted)
    inside = close(test)
    model = m.apply_fit(test, fitted) if arm == 'close_fit' else np.asarray(production)
    return np.where(inside, model, test.q.to_numpy(float))


def flat_units(held, col):
    return m.flat_bets(held, col)


def logistic(y, x, offset=None):
    """Intercept/slope (or offset multiplier) by maximum likelihood with Hessian SEs."""
    X = np.column_stack([np.ones(len(y)), x]) if offset is None else np.asarray(x, float)[:, None]
    o = np.zeros(len(y)) if offset is None else offset
    def f(b):
        eta = o+X@b; return np.sum(np.logaddexp(0, eta)-y*eta)
    def g(b):
        eta = o+X@b; return X.T@(expit(eta)-y)
    r = minimize(f, np.zeros(X.shape[1]), jac=g, method='BFGS')
    eta = o+X@r.x; w = expit(eta)*(1-expit(eta))
    se = np.sqrt(np.diag(np.linalg.inv(X.T@(w[:, None]*X))))
    return [float(v) for v in r.x], [float(v) for v in se]


def compare(held):
    held = held.assign(market=held.q)
    arms = [*ARMS, 'market']
    bets = {a: flat_units(held, a) for a in arms}
    common = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    proper = held['home won'].isin([0., 1.]).to_numpy()
    groups = (held.season.astype(int).astype(str)+'_'+held.week.astype(int).astype(str)).to_numpy()
    y = held['home won'].to_numpy(float)
    losses = {a: s.loss(y, held[a].to_numpy(float)) for a in arms}
    near = close(held)
    rows = []
    for a in arms:
        rows.append({'arm': a, **m.roi_summary(bets[a].loc[common]), 'log_loss': float(losses[a][proper].mean()),
                     'brier': float(((held[a]-held['home won'])**2).to_numpy()[proper].mean()),
                     'close_log_loss': float(losses[a][proper & near].mean())})
    du_a = (bets['production'].units-bets['market'].units).to_numpy()
    dl_b = losses['market']-losses['production']
    du_c = (bets['close_fit'].units-bets['production'].units).to_numpy()
    dl_d = losses['production']-losses['close_fit']
    stats = {
        'A_units_vs_favorite': {'per_bet': float(du_a[common].mean()), 'units': float(du_a[common].sum()),
                                'interval': p.cluster_interval(du_a[common], groups[common], LEVEL)},
        'B_ll_gain_vs_market': {'mean': float(dl_b[proper].mean()),
                                'interval': p.cluster_interval(dl_b[proper], groups[proper], LEVEL)},
        'C_units_vs_production': {'per_bet': float(du_c[common].mean()), 'units': float(du_c[common].sum()),
                                  'interval': p.cluster_interval(du_c[common], groups[common], LEVEL)},
        'D_close_ll_gain_vs_production': {'mean': float(dl_d[proper & near].mean()), 'games': int((proper & near).sum()),
                                          'interval': p.cluster_interval(dl_d[proper & near], groups[proper & near], LEVEL)}}
    picks = (held.production > .5).to_numpy() != (held.q > .5).to_numpy()
    favorite = np.maximum(held.q, 1-held.q).to_numpy()
    bands = []
    for lo, hi in [(.5, .55), (.55, .6), (.6, .65), (.65, 1.01)]:
        m_ = common & picks & (favorite >= lo) & (favorite < hi)
        bands.append({'favorite_band': f'{100*lo:.0f}-{min(100*hi, 100):.0f}%', 'underdog_picks': int(m_.sum()),
                      'units_vs_favorite': float(du_a[m_].sum())})
    return {'results': rows, 'statistics': stats, 'underdog_picks_by_band': bands,
            'underdog_picks': int((common & picks).sum()), 'bets': int(common.sum()),
            'proper_games': int(proper.sum()), 'close_proper_games': int((proper & near).sum()),
            'excluded_bets': held.loc[~common, 'game_id'].tolist()}


def verdict_q1(a):
    lo, hi = a['interval']
    return 'supported' if lo > 0 else 'contradicted' if hi < 0 else 'unresolved'


def verdict_q2(c, d):
    if c['per_bet'] <= 0 or d['mean'] <= 0: return 'not supported'
    return 'supported' if c['interval'][0] > 0 and d['interval'][0] > 0 else 'favored, unresolved'


def descriptive(held):
    y = held['home won'].to_numpy(float); proper = np.isin(y, [0., 1.])
    out = {'by_season': [], 'calibration': {}, 'offset_multiplier': []}
    for year in sorted(held.season.unique()):
        part = compare(held[held.season == year].reset_index(drop=True))
        out['by_season'].append({'season': int(year), 'results': part['results'],
                                 'units_vs_favorite': part['statistics']['A_units_vs_favorite']['units'],
                                 'll_gain_vs_market': part['statistics']['B_ll_gain_vs_market']['mean'],
                                 'close_fit_units_vs_production': part['statistics']['C_units_vs_production']['units'],
                                 'underdog_picks': part['underdog_picks']})
    early = held[held.season <= 2018].reset_index(drop=True)
    out['seasons_2017_2018'] = {k: v for k, v in compare(early).items() if k in ('results', 'statistics', 'underdog_picks')}
    for arm in ('production', 'market'):
        prob = held.q if arm == 'market' else held[arm]
        (a, b), (sa, sb) = logistic(y[proper], logit(np.clip(prob.to_numpy(float)[proper], 1e-6, 1-1e-6)))
        out['calibration'][arm] = {'intercept': a, 'intercept_se': sa, 'slope': b, 'slope_se': sb}
    lq = logit(np.clip(held.q.to_numpy(float), 1e-6, 1-1e-6)); off = logit(np.clip(held.production.to_numpy(float), 1e-6, 1-1e-6))-lq
    for year in [*sorted(held.season.unique()), 'all']:
        mk = proper & ((held.season == year).to_numpy() if year != 'all' else True)
        (k,), (se,) = logistic(y[mk], off[mk], offset=lq[mk])
        out['offset_multiplier'].append({'season': year if year == 'all' else int(year), 'k': k, 'se': se, 'games': int(mk.sum())})
    return out


def run(out):
    out = protect(out)
    f = pd.read_csv(out/PACK)
    refs = pd.read_csv(out/'normalization_references.csv')
    reference_ok = bool(((refs.max_reference_season < refs.season) | ((refs.max_reference_season == refs.season) & (refs.max_reference_week < refs.week))).all())
    if not reference_ok: raise ValueError('Future normalization reference')
    train_mask = eligible(f)
    scored = f.season.between(*SCORED) & f.ready.astype(bool) & f['home won'].isin([0., .5, 1.]) & np.isfinite(f.q) \
        & f.home_moneyline.notna() & f.away_moneyline.notna() & np.isfinite(f[CONTEXTS]).all(axis=1)
    held = f.loc[scored, p.BASE_COLS].copy(); audit = []
    for (year, week), rows in held.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week); train = f[train_mask & m.before(f, year, week)]; test = f.loc[rows.index]
        fits = {arm: fit_arm(train, year, week, arm) for arm in ('production', 'close_fit')}
        prod = forecast(test, fits['production'], 'production')
        held.loc[rows.index, 'production'] = prod
        held.loc[rows.index, 'close_fit'] = forecast(test, fits['close_fit'], 'close_fit')
        held.loc[rows.index, 'v116_close_only'] = forecast(test, None, 'v116_close_only', prod)
        for arm, fitted in fits.items():
            audit.append({'season': year, 'week': week, 'arm': arm, 'training_games': fitted['training_games'],
                          'training_max_season': fitted['training_max_season'],
                          'training_max_week': fitted['training_max_week_in_latest_season'],
                          'effective_training_games': fitted['effective_training_games']})
        if week == 1: print(f'Scored season {year}', flush=True)
    if not np.isfinite(held[list(ARMS)]).all().all(): raise ValueError('Incomplete predictions')
    audit = pd.DataFrame(audit)
    prior = (audit.training_max_season < audit.season) | ((audit.training_max_season == audit.season) & (audit.training_max_week < audit.week))
    if not prior.all(): raise ValueError('Training cutoff is not strictly prior')
    held = held.reset_index(drop=True)
    info = {'protocol': 'research/OUT_OF_SAMPLE_2017_2020.md', 'revision': 'boxscore-composite-v1.16',
            'model_revision_at_run': m.REVISION, 'recipe': RECIPE, 'close_line': CLOSE, 'confidence_level': LEVEL,
            'basis': BASES['primary'], 'primary': compare(held), 'all_training_cutoffs_prior': bool(prior.all()),
            'all_references_prior_week': reference_ok, 'fits': len(audit),
            'pipeline_check': json.loads((out/'pipeline_check.json').read_text())}
    st = info['primary']['statistics']
    info['verdicts'] = {'Q1': verdict_q1(st['A_units_vs_favorite']),
                        'Q2': verdict_q2(st['C_units_vs_production'], st['D_close_ll_gain_vs_production'])}
    info['descriptive'] = descriptive(held)
    held.to_csv(out/'predictions.csv', index=False)
    audit.to_csv(out/'fit_audit.csv', index=False)
    (out/'results.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    sources = [Path(__file__).resolve(), ROOT/'research/OUT_OF_SAMPLE_2017_2020.md', ROOT/'research/context_shrinkage.py',
               ROOT/'nfl_model.py', out/PACK, out/'normalization_references.csv', REFERENCE_PACK]
    (out/'provenance.json').write_text(json.dumps(
        {str(x.relative_to(ROOT)): hashlib.sha256(x.read_bytes()).hexdigest() for x in sources}, indent=2)+'\n')
    write_report(info, out)
    print(json.dumps({'verdicts': info['verdicts'], 'statistics': st}, indent=2), flush=True)


def _iv(v, scale=1., fmt='+.2f'):
    return f'[{scale*v[0]:{fmt}}, {scale*v[1]:{fmt}}]'


def _arm_table(results):
    lines = ['| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Log loss | Close-game LL | Brier |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in results:
        name = 'market favorite' if r['arm'] == 'market' else r['arm']
        lines.append(f"| {name} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} | "
                     f"{100*r['null_roi']:+.2f}% | {r['log_loss']:.6f} | {r['close_log_loss']:.6f} | {r['brier']:.6f} |")
    return lines


def write_report(info, out):
    pr, st, v, d = info['primary'], info['primary']['statistics'], info['verdicts'], info['descriptive']
    a, b, c, dd = st['A_units_vs_favorite'], st['B_ll_gain_vs_market'], st['C_units_vs_production'], st['D_close_ll_gain_vs_production']
    lines = ['# Out-of-sample 2017–2020 results', '',
             'Protocol: [OUT_OF_SAMPLE_2017_2020.md](../OUT_OF_SAMPLE_2017_2020.md), pushed before any 2017–2020 forecast existed. '
             'Production v1.16 and its ledger are unchanged.', '',
             f"**Q1, does v1.16 beat the market favorite out of sample? {v['Q1']}.** Paired units vs the favorite "
             f"{a['units']:+.2f}u ({100*a['per_bet']:+.2f} pts per bet, {100*info['confidence_level']:.1f}% interval {_iv(a['interval'], 100)} pts). "
             f"Log-loss gain vs the market {b['mean']:+.6f} {_iv(b['interval'], 1, '+.6f')}.", '',
             f"**Q2, does the close-game challenger beat v1.16? {v['Q2']}.** Units vs v1.16 {c['units']:+.2f}u "
             f"({100*c['per_bet']:+.2f} pts per bet, {_iv(c['interval'], 100)}); close-game log-loss gain {dd['mean']:+.6f} "
             f"{_iv(dd['interval'], 1, '+.6f')} on {dd['games']} games.", '',
             'Basis: '+info['basis']+'.', '', '## All arms, 2017–2020', '',
             f"{pr['bets']} common flat 1u bets; {pr['proper_games']} binary scores, {pr['close_proper_games']} of them close games "
             f"(favorite under {100*info['close_line']:.0f}%). v1.16 backed the market underdog {pr['underdog_picks']} times.", '']
    lines += _arm_table(pr['results'])
    lines += ['', '## By season', '', '| Season | v1.16 units vs favorite | v1.16 LL gain vs market | Underdog picks | close_fit units vs v1.16 |',
              '|---|---:|---:|---:|---:|']
    for r in d['by_season']:
        lines.append(f"| {r['season']} | {r['units_vs_favorite']:+.2f} | {r['ll_gain_vs_market']:+.6f} | {r['underdog_picks']} | {r['close_fit_units_vs_production']:+.2f} |")
    early = d['seasons_2017_2018']['statistics']
    lines += ['', f"2017–2018 only (least exposed): v1.16 vs favorite {early['A_units_vs_favorite']['units']:+.2f}u, "
              f"LL gain vs market {early['B_ll_gain_vs_market']['mean']:+.6f}; close_fit vs v1.16 {early['C_units_vs_production']['units']:+.2f}u.", '',
              '## Underdog picks by favorite band (v1.16)', '', '| Favorite band | Picks | Units vs favorite |', '|---|---:|---:|']
    for r in pr['underdog_picks_by_band']:
        lines.append(f"| {r['favorite_band']} | {r['underdog_picks']} | {r['units_vs_favorite']:+.2f} |")
    cal = d['calibration']
    lines += ['', '## Calibration and the value of v1.16\'s market departures', '',
              f"Calibration slope: v1.16 {cal['production']['slope']:.3f} ± {cal['production']['slope_se']:.3f}; market "
              f"{cal['market']['slope']:.3f} ± {cal['market']['slope_se']:.3f} (1 SE). Offset multiplier k (1 = right-sized, 0 = no value): "
              + '; '.join(f"{r['season']} {r['k']:+.2f} ± {r['se']:.2f}" for r in d['offset_multiplier'])+'.', '',
              '## Reproduction and limits', '',
              f"Pipeline check against the committed v1.16 pack (2019–2020 rebuilt alone): {info['pipeline_check']['games_compared']} games, "
              f"max input difference {info['pipeline_check']['max_abs_difference']:.3g}, "
              f"{100*info['pipeline_check']['games_identical_within_1e-9']:.1f}% of games identical within 1e-9.",
              f"All {info['fits']} weekly fits train strictly before their scored week; all pass-context references are prior weeks.",
              'These seasons were used once before (disclosed in the protocol). One use of about 1,000 bets has limited power; '
              'an unresolved verdict does not show a zero effect. Adoption would be an owner decision and a new REVISION.', '',
              'Run: `python research/out_of_sample_2017_2020.py` (frozen pack); `--prepare` rebuilds inputs from nflverse.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, default=OUT)
    ap.add_argument('--input-dir', type=Path, default=ROOT/'.nfl_cache/oos_2017_2020_inputs')
    ap.add_argument('--prepare', action='store_true', help='Download inputs, freeze the pack and run the pipeline check only')
    args = ap.parse_args()
    if args.prepare: prepare(args.input_dir, protect(args.output_dir))
    else: run(args.output_dir)
