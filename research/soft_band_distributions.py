"""SB1: neighboring-band empirical margin mixtures; research, never production.

See SOFT_BAND_DISTRIBUTIONS.md for the fixed pre-result protocol.
Ordinary replay uses frozen inputs, with no network access or production-model refit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtri

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / 'research/soft_band_distribution_inputs/games.csv'
OUTPUT = ROOT / 'research/soft_band_distribution_results'
GRID = np.arange(-100, 101, dtype=float)
CUTS = np.array([3., 7., 10.])
POLICY = 'SB1-neighbor-empirical-bands-2026-10-26-v1'
ARMS = ('soft_ev', 'hard_ev', 'median', 'raw', 'favorite', 'home')
EPS = 1e-10
REPEATS = 6000
SEED = 20261026


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def writable(path):
    path = Path(path).resolve()
    for protected in (ROOT/'data', ROOT/'public'):
        if path == protected or protected in path.parents:
            raise ValueError('research cannot write production data or public files')
    return path


def valid_price(value):
    try:
        x = float(value)
        return np.isfinite(x) and abs(x) >= 100
    except (ValueError, TypeError):
        return False


def payout(odds):
    if not valid_price(odds):
        raise ValueError('American spread price must have magnitude at least 100')
    odds = float(odds)
    return odds/100 if odds > 0 else 100/-odds


def market_probability(home, away):
    qh, qa = 1/(1+payout(home)), 1/(1+payout(away))
    return qh/(qh+qa)


def prepare_inputs(path=INPUT):
    """Explicit one-time pack preparation. No source or archive is modified."""
    import ats_locks
    import build_site
    import nfl_model
    import season_ats

    path = writable(path)
    source = ROOT/'data'
    latest = build_site.load_latest(source/'latest')
    latest['ats_locks'] = ats_locks.display_records(source)
    past = latest['retro_ledger'].query('season < 2026').copy()
    current = season_ats.build(latest, build_site.load_ledger(source))
    current = current.loc[current.fixed_band_ats_result.isin(list('WLP'))].copy()
    past['input_basis'] = 'exposed historical weekly reconstruction'
    current['input_basis'] = current.ats_basis
    cols = ['game_id', 'season', 'week', 'home', 'away', 'model_wp', 'spread_line', 'result', 'input_basis']
    frame = pd.concat([past[cols], current[cols]], ignore_index=True)
    frame['raw_spread'] = 12.37*ndtri(np.clip(frame.model_wp, .005, .995))
    saved = current.set_index('game_id').fixed_band_spread
    frame['saved_median_spread'] = frame.game_id.map(saved)
    frame['home_spread_odds'] = np.nan
    frame['away_spread_odds'] = np.nan
    frame['paired_price_basis'] = 'unavailable'
    frame['paired_price_source'] = ''
    price_path = ROOT/'research/margin_total_results/frozen_feature_prices.csv.gz'
    prices = pd.read_csv(price_path, usecols=['game_id', 'spread_line', 'home_spread_odds', 'away_spread_odds'])
    if prices.game_id.duplicated().any():
        raise ValueError('duplicate archived price identity')
    lookup = prices.set_index('game_id')
    current = current.set_index('game_id')
    for i, row in frame.iterrows():
        if row.season < 2026 and row.game_id in lookup.index:
            q = lookup.loc[row.game_id]
            if abs(q.spread_line-row.spread_line) <= EPS and valid_price(q.home_spread_odds) and valid_price(q.away_spread_odds):
                frame.loc[i, ['home_spread_odds', 'away_spread_odds']] = [q.home_spread_odds, q.away_spread_odds]
                frame.loc[i, 'paired_price_basis'] = 'historical_schedule_capture_time_unknown'
                frame.loc[i, 'paired_price_source'] = str(price_path.relative_to(ROOT))
        elif row.game_id in current.index:
            q = current.loc[row.game_id]
            if valid_price(q.ats_home_odds) and valid_price(q.ats_away_odds):
                frame.loc[i, ['home_spread_odds', 'away_spread_odds']] = [q.ats_home_odds, q.ats_away_odds]
                frame.loc[i, 'paired_price_basis'] = q.ats_price_basis
                frame.loc[i, 'paired_price_source'] = q.get('ats_evidence_sha256', '')
    frame = clean(frame)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, float_format='%.17g')
    sources = [source/'latest/retro_ledger.csv', source/'latest/board.csv',
               source/'latest/manifest.json', source/'forward_ledger.csv',
               source/'ats_locks.jsonl', source/'ats_forward_shadow.jsonl',
               source/'espn_spreads.jsonl', price_path, ROOT/'nfl_model.py', ROOT/'fixed_bands.py']
    dump(path.with_name('provenance.json'), dict(policy=POLICY,
         model_revision=nfl_model.REVISION, model_config_signature=latest['manifest']['config_signature'],
         production_generated_utc=latest['manifest']['generated_utc'],
         exposure='All historical data and 2026 diagnostic are exposed development, not forward validation.',
         source_hashes={str(p.relative_to(ROOT)): sha(p) for p in sources},
         frozen_input_sha256=sha(path), games=len(frame),
         paired_prices=int(frame.paired_price_basis.ne('unavailable').sum()),
         historical_quote_times_verified=False, production_modified=False))
    return frame


def clean(frame):
    frame = frame.copy()
    required = ['game_id', 'season', 'week', 'raw_spread', 'spread_line', 'result']
    if not set(required) <= set(frame):
        raise ValueError('missing required forecast columns')
    if frame.game_id.isna().any() or frame.game_id.duplicated().any():
        raise ValueError('missing or duplicate game identity')
    for name in required[1:]:
        frame[name] = pd.to_numeric(frame[name], errors='coerce')
    if not np.isfinite(frame[required[1:]]).all().all():
        raise ValueError('forecast, line, outcome and season/week must be finite')
    if frame.raw_spread.eq(0).any():
        raise ValueError('zero raw projection has no preferred-winner orientation')
    if ((frame.result != np.rint(frame.result)) | frame.result.abs().gt(100)).any():
        raise ValueError('margin must be an observed integer within supported range')
    for name in ('season', 'week'):
        if not frame[name].eq(np.rint(frame[name])).all():
            raise ValueError('season/week must be integers')
        frame[name] = frame[name].astype(int)
    for name in ('home_spread_odds', 'away_spread_odds', 'saved_median_spread'):
        if name not in frame:
            frame[name] = np.nan
        frame[name] = pd.to_numeric(frame[name], errors='coerce')
    for name in ('paired_price_basis', 'paired_price_source', 'input_basis'):
        if name not in frame:
            frame[name] = 'unavailable'
    return frame.sort_values(['season', 'week', 'game_id'], kind='stable').reset_index(drop=True)


def fit_prior(training, target_season):
    if len(training) and not training.season.lt(target_season).all():
        raise ValueError('own/future seasons in empirical distribution fit')
    training = clean(training)
    if training.season.nunique() < 2 or len(training) < 300:
        raise ValueError('need two earlier seasons and at least 300 observations')
    x = training.raw_spread.abs().to_numpy()
    y = np.sign(training.raw_spread.to_numpy())*training.result.to_numpy()
    band = np.digitize(x, CUTS)
    counts, centers, medians, n = [], [], [], []
    for k in range(4):
        mask = band == k
        if mask.sum() < 30:
            raise ValueError('need at least 30 observations in each band')
        counts.append(np.bincount((y[mask]+100).astype(int), minlength=len(GRID)).tolist())
        centers.append(float(np.median(x[mask])))
        medians.append(float(np.median(y[mask])))
        n.append(int(mask.sum()))
    fit = dict(policy=POLICY, target_season=int(target_season),
               training_min_season=int(training.season.min()), training_max_season=int(training.season.max()),
               training_games=len(training), band_counts=n, centers=centers, counts=counts, medians=medians,
               source_games_sha256=digest(sorted(training.game_id.tolist())))
    fit['fit_sha256'] = digest(fit)
    return fit


def validate_fit(fit):
    if fit['training_max_season'] >= fit['target_season']:
        raise ValueError('own/future labels in saved fit')
    if fit['policy'] != POLICY or digest({k:v for k,v in fit.items() if k != 'fit_sha256'}) != fit['fit_sha256']:
        raise ValueError('fit policy or integrity hash mismatch')
    counts = np.asarray(fit['counts'], float)
    if counts.shape != (4, len(GRID)) or not np.isfinite(counts).all() or (counts < 0).any():
        raise ValueError('invalid observed-margin counts')
    if not np.equal(counts, np.rint(counts)).all() or not np.array_equal(counts.sum(axis=1), fit['band_counts']):
        raise ValueError('count totals do not match observed band sizes')
    if min(fit['band_counts']) < 30 or sum(fit['band_counts']) != fit['training_games']:
        raise ValueError('insufficient or inconsistent training support')
    centers = np.asarray(fit['centers'], float)
    if not np.isfinite(centers).all() or not (np.diff(centers) > 0).all():
        raise ValueError('anchors must increase strictly')


def weights(magnitude, centers):
    if not np.isfinite(magnitude) or magnitude < 0:
        raise ValueError('raw magnitude must be finite and nonnegative')
    centers = np.asarray(centers, float)
    if centers.shape != (4,) or not np.isfinite(centers).all() or not (np.diff(centers)>0).all():
        raise ValueError('four increasing anchors required')
    w = np.zeros(4)
    if magnitude <= centers[0]:
        w[0] = 1.
    elif magnitude >= centers[-1]:
        w[-1] = 1.
    else:
        upper = int(np.searchsorted(centers, magnitude, side='right'))
        fraction = (magnitude-centers[upper-1])/(centers[upper]-centers[upper-1])
        w[upper-1], w[upper] = 1-fraction, fraction
    return w


def forecast(raw, fit, soft=True):
    validate_fit(fit)
    if not np.isfinite(raw) or raw == 0:
        raise ValueError('finite nonzero raw projection required')
    counts = np.asarray(fit['counts'], float)
    pmfs = counts/counts.sum(axis=1, keepdims=True)
    w = weights(abs(raw), fit['centers']) if soft else np.eye(4)[np.digitize(abs(raw), CUTS)]
    p = w@pmfs
    return (p if raw > 0 else p[::-1]), w


def event(pmf, line):
    p = np.asarray(pmf, float)
    if p.shape != GRID.shape or not np.isfinite(p).all() or (p < 0).any() or not np.isclose(p.sum(), 1., atol=1e-12, rtol=0):
        raise ValueError('invalid margin PMF')
    if not np.isfinite(line):
        raise ValueError('finite handicap required')
    home = float(p[GRID > line+EPS].sum())
    away = float(p[GRID < line-EPS].sum())
    push = float(p[np.abs(GRID-line) <= EPS].sum())
    return np.array([home, push, away])


def point_median(pmf):
    cdf = np.cumsum(pmf)
    lower = int(np.flatnonzero(cdf >= .5-1e-12)[0])
    upper = int(np.flatnonzero(cdf > .5+1e-12)[0])
    return float((GRID[lower]+GRID[upper])/2)


def choose(probabilities, home_odds, away_odds):
    p = np.asarray(probabilities, float)
    if p.shape != (3,) or not np.isfinite(p).all() or (p < 0).any() or not np.isclose(p.sum(), 1., atol=1e-12, rtol=0):
        raise ValueError('cover/push/loss probabilities must sum to one')
    home = payout(home_odds)*p[0]-p[2]
    away = payout(away_odds)*p[2]-p[0]
    side = ('home' if home >= away else 'away') if max(home, away) > 1e-12 else 'pass'
    return side, float(max(home, away)) if side != 'pass' else 0.


def spread_side(prediction, line):
    direction = line if abs(prediction-line) <= EPS else prediction-line
    return 'home' if direction > EPS else 'away' if direction < -EPS else 'pass'


def settle(side, margin, line, home_odds, away_odds):
    if side not in ('home', 'away', 'pass'):
        raise ValueError('unknown selected side')
    if not np.isfinite([margin, line]).all():
        raise ValueError('finite margin and line required')
    if side == 'pass':
        return 'S', 0.
    if abs(margin-line) <= EPS:
        return 'P', 0.
    won = (margin > line) == (side == 'home')
    return ('W', payout(home_odds if side == 'home' else away_odds)) if won else ('L', -1.)


def evaluate(frame, start_season=2023):
    frame = clean(frame)
    rows, fits = [], []
    for year in sorted(y for y in frame.season.unique() if y >= start_season):
        fit = fit_prior(frame[frame.season < year], int(year))
        fits.append(fit)
        for source in frame[frame.season.eq(year)].to_dict('records'):
            raw, margin, line = source['raw_spread'], source['result'], source['spread_line']
            row = dict(source, fit_sha256=fit['fit_sha256'], training_max_season=fit['training_max_season'])
            probabilities = {}
            actual = 0 if margin > line+EPS else 2 if margin < line-EPS else 1
            row['actual_event'] = actual
            row['binary_scored'] = actual != 1
            for name, soft in [('soft', True), ('hard', False)]:
                p, w = forecast(raw, fit, soft)
                ev = event(p, line)
                probabilities[name] = ev
                if ev[0]+ev[2] <= 0:
                    raise ValueError('conditional cover probability undefined: all forecast mass is push')
                q = float(ev[0]/(ev[0]+ev[2]))
                row.update({name+'_home_cover':ev[0], name+'_push':ev[1], name+'_away_cover':ev[2],
                            name+'_conditional_home':q, name+'_median':point_median(p),
                            name+'_mae':abs(point_median(p)-margin),
                            name+'_crps':float(np.square(np.cumsum(p)[:-1]-(GRID[:-1] >= margin)).sum()),
                            name+'_event_ll':float(-np.log(max(ev[actual], 1e-12))),
                            name+'_zero_event':bool(ev[actual] == 0),
                            name+'_cover_ll':float(-np.log(np.clip(q if actual == 0 else 1-q, 1e-12, 1.))) if actual != 1 else np.nan,
                            name+'_cover_brier':float((q-float(actual == 0))**2) if actual != 1 else np.nan})
                for k in range(4):
                    row[f'{name}_weight_{k}'] = float(w[k])
            k = int(np.digitize(abs(raw), CUTS))
            mapped = np.sign(raw)*fit['medians'][k]
            if year == 2026 and np.isfinite(source['saved_median_spread']):
                mapped = source['saved_median_spread']
            row['median_spread'] = float(mapped)
            paired = valid_price(source['home_spread_odds']) and valid_price(source['away_spread_odds'])
            row['paired_prices'] = paired
            row['fair_cover_ll'] = float(np.log(2)) if actual != 1 else np.nan
            row['fair_cover_brier'] = .25 if actual != 1 else np.nan
            row['market_conditional_home'] = market_probability(source['home_spread_odds'], source['away_spread_odds']) if paired else np.nan
            q = row['market_conditional_home']
            row['market_cover_ll'] = float(-np.log(np.clip(q if actual == 0 else 1-q, 1e-12, 1.))) if paired and actual != 1 else np.nan
            row['market_cover_brier'] = float((q-float(actual == 0))**2) if paired and actual != 1 else np.nan
            for scenario in ('assumed110', 'paired'):
                if scenario == 'paired' and not paired:
                    continue
                home, away = (-110., -110.) if scenario == 'assumed110' else (source['home_spread_odds'], source['away_spread_odds'])
                decisions = {'soft_ev':choose(probabilities['soft'], home, away),
                             'hard_ev':choose(probabilities['hard'], home, away),
                             'median':(spread_side(mapped, line), np.nan),
                             'raw':(spread_side(raw, line), np.nan),
                             'favorite':('home' if line >= 0 else 'away', np.nan),
                             'home':('home', np.nan)}
                for arm, (side, expected) in decisions.items():
                    grade, units = settle(side, margin, line, home, away)
                    prefix = scenario+'_'+arm
                    row.update({prefix+'_side':side, prefix+'_grade':grade,
                                prefix+'_units':units, prefix+'_expected_units':expected})
                    if arm in ('soft_ev', 'hard_ev'):
                        p = probabilities[arm.split('_')[0]]
                        row[prefix+'_selected_conditional'] = float(p[0 if side == 'home' else 2]/(p[0]+p[2])) if side != 'pass' else np.nan
            rows.append(row)
    return pd.DataFrame(rows), fits


def bootstrap_totals(frame, columns):
    """Paired whole-week resampling within season; no model refit or selection."""
    frame = frame.copy()
    grouped = frame.groupby(['season', 'week'])[columns].sum()
    rng = np.random.default_rng(SEED)
    total = np.zeros((REPEATS, len(columns)))
    for year in grouped.index.get_level_values(0).unique():
        values = grouped.loc[year].to_numpy(float)
        draws = rng.multinomial(len(values), np.full(len(values), 1/len(values)), size=REPEATS)
        total += draws@values
    return total


def interval(values, alpha=.05):
    values = np.asarray(values)
    values = values[np.isfinite(values)]
    return np.quantile(values, [alpha/2, 1-alpha/2]).tolist() if len(values) else None


def paired_gain(frame, baseline, challenger, alpha=.05):
    if not len(frame):
        return dict(n=0, gain=None, interval=None, confidence=1-alpha)
    g = frame.dropna(subset=[baseline, challenger]).copy()
    if len(g) < 2:
        return dict(n=len(g), gain=None, interval=None, confidence=1-alpha)
    g['gain'] = g[baseline]-g[challenger]
    g['n'] = 1.
    boot = bootstrap_totals(g, ['gain', 'n'])
    return dict(n=len(g), gain=float(g.gain.mean()), interval=interval(boot[:,0]/boot[:,1], alpha),
                confidence=1-alpha, clusters=int(g.groupby(['season', 'week']).ngroups))


def summary(frame, scenario, arm):
    g = frame if scenario == 'assumed110' else frame[frame.paired_prices]
    prefix = scenario+'_'+arm
    if not len(g):
        return dict(games=0, bets=0, passes=0, wins=0, losses=0, pushes=0, units=0., roi=None, roi_se=None, roi_ci95=None)
    played = g[prefix+'_side'].ne('pass')
    d = g.loc[played]
    grades = d[prefix+'_grade']
    u = d[prefix+'_units']
    boot_frame = g[['season', 'week']].copy()
    boot_frame['u'] = g[prefix+'_units']
    boot_frame['bets'] = played.astype(float)
    names = ('median', 'raw', 'favorite', 'home')
    for name in names:
        boot_frame[name+'_gain'] = np.where(played, g[prefix+'_units']-g[scenario+'_'+name+'_units'], 0.)
    boot = bootstrap_totals(boot_frame, ['u', 'bets']+[name+'_gain' for name in names])
    ratios = np.divide(boot[:,0], boot[:,1], out=np.full(REPEATS, np.nan), where=boot[:,1] > 0)
    w, l, p = [int(grades.eq(c).sum()) for c in 'WLP']
    controls = {}
    for i,name in enumerate(names, start=2):
        difference = u-d[scenario+'_'+name+'_units']
        gain = np.divide(boot[:,i], boot[:,1], out=np.full(REPEATS, np.nan), where=boot[:,1]>0)
        controls[name] = dict(units=float(d[scenario+'_'+name+'_units'].sum()),
                             roi=float(d[scenario+'_'+name+'_units'].mean()) if len(d) else None,
                             policy_minus_control_units=float(difference.sum()),
                             policy_minus_control_roi_ci95=interval(gain))
    conditional = prefix+'_selected_conditional'
    decisive = grades.isin(['W','L'])
    predicted = float(d.loc[decisive,conditional].mean()) if conditional in d and decisive.any() else None
    return dict(games=len(g), bets=len(d), passes=int((~played).sum()), wins=w, losses=l, pushes=p,
                units=float(u.sum()), roi=float(u.mean()) if len(d) else None,
                units_per_opportunity=float(g[prefix+'_units'].mean()),
                roi_se=float(u.std(ddof=1)/np.sqrt(len(d))) if len(d) > 1 else None,
                roi_ci95=interval(ratios), cover_rate=w/(w+l) if w+l else None,
                expected_units=float(d[prefix+'_expected_units'].sum()) if arm in ('soft_ev', 'hard_ev') else None,
                mean_predicted_selected_conditional=predicted,
                selected_calibration_gap=predicted-w/(w+l) if predicted is not None and w+l else None,
                same_selected_controls=controls)


def calibration(frame):
    rows = []
    for basis, g in [('2023-25', frame[frame.season.between(2023,2025)]), ('2026 diagnostic', frame[frame.season.eq(2026)])]:
        g = g[g.binary_scored].copy()
        for arm in ('soft', 'hard'):
            q = g[arm+'_conditional_home']
            bins = np.minimum((q*10).astype(int), 9)
            for k in sorted(bins.unique()):
                d = g[bins.eq(k)]
                rows.append(dict(basis=basis, arm=arm, bin=f'{k/10:.1f}-{(k+1)/10:.1f}', n=len(d),
                                 predicted=float(d[arm+'_conditional_home'].mean()),
                                 observed=float(d.actual_event.eq(0).mean())))
    return pd.DataFrame(rows)


def boundary_diagnostics(fits):
    rows = []
    for fit in fits:
        for cutoff in CUTS:
            for delta in (-.01,0.,.01):
                row = dict(target_season=fit['target_season'], cutoff=cutoff, raw=cutoff+delta,
                           hypothetical_line=cutoff, basis='outcome-free numerical diagnostic')
                for name,soft in [('soft',True),('hard',False)]:
                    pmf,_ = forecast(cutoff+delta,fit,soft)
                    probabilities = event(pmf,cutoff)
                    row[name+'_conditional_home'] = float(probabilities[0]/(probabilities[0]+probabilities[2]))
                    row[name+'_push'] = float(probabilities[1])
                    row[name+'_side_at_assumed110'] = choose(probabilities,-110.,-110.)[0]
                rows.append(row)
    return pd.DataFrame(rows)


def report(frame, fits):
    if not frame.season.between(2023,2025).any():
        raise ValueError('main 2023-25 evaluation cohort is missing')
    bases = [('2023-25', frame[frame.season.between(2023,2025)]),
             ('2026 diagnostic', frame[frame.season.eq(2026)])]
    bases += [(str(y), g) for y,g in frame.groupby('season') if y < 2026]
    summaries = {}
    for label, g in bases:
        if not len(g):
            continue
        scores = {name:float(g[name].mean()) if g[name].notna().any() else None for name in
                  ['soft_cover_ll','hard_cover_ll','fair_cover_ll','market_cover_ll',
                   'soft_cover_brier','hard_cover_brier','market_cover_brier',
                   'soft_event_ll','hard_event_ll','soft_crps','hard_crps','soft_mae','hard_mae']}
        paired = g[g.paired_prices]
        scores['soft_cover_ll_paired'] = float(paired.soft_cover_ll.mean()) if len(paired) else None
        scores['hard_cover_ll_paired'] = float(paired.hard_cover_ll.mean()) if len(paired) else None
        summaries[label] = dict(games=len(g), decisive=int(g.binary_scored.sum()), paired_games=len(paired),
            scores=scores, zero_probability_events={a:int(g[a+'_zero_event'].sum()) for a in ('soft','hard')},
            gains=dict(soft_vs_hard_cover=paired_gain(g,'hard_cover_ll','soft_cover_ll',.025),
                       soft_vs_market_cover=paired_gain(paired,'market_cover_ll','soft_cover_ll',.025),
                       soft_vs_fair_cover=paired_gain(g,'fair_cover_ll','soft_cover_ll'),
                       soft_vs_hard_crps=paired_gain(g,'hard_crps','soft_crps')),
            policy_gains={scenario:paired_gain(g if scenario=='assumed110' else paired,
                scenario+'_soft_ev_units',scenario+'_hard_ev_units') for scenario in ('assumed110','paired')},
            scenarios={scenario:{arm:summary(g,scenario,arm) for arm in ARMS} for scenario in ('assumed110','paired')})
    primary = summaries['2023-25']['gains']
    advance = all(primary[name]['interval'] is not None and primary[name]['interval'][0] > 0
                  for name in ('soft_vs_hard_cover','soft_vs_market_cover'))
    return dict(policy=POLICY, status='development gate passed; forward registration still required' if advance else 'development gate failed; do not promote',
                production_changed=False, independent_validation=False, fitted_target_seasons=[f['target_season'] for f in fits],
                source_fit_max_seasons=[f['training_max_season'] for f in fits], bases=summaries)


def markdown(result):
    main = result['bases']['2023-25']
    lines = ['# SB1: soft neighboring-band empirical distributions', '',
             '**'+result['status']+'.** Production, live forecasts and original archives are unchanged.', '',
             'Exposed retrospective development. Each scored season uses strictly earlier-season PMFs and anchors. '
             'No smoothing parameter, threshold or ROI-selected variant was searched.', '',
             '## Forecast scores: 2023-25', '',
             '| Forecast | Conditional cover log loss | Brier | Margin CRPS | Median MAE |',
             '| --- | ---: | ---: | ---: | ---: |']
    scores = main['scores']
    fmt = lambda value: f'{value:.6f}' if value is not None else 'Unavailable'
    for name in ('hard','soft'):
        values = [fmt(scores[name+'_'+metric]) for metric in ('cover_ll','cover_brier','crps','mae')]
        lines.append(f"| {name} empirical bands | " + ' | '.join(values) + ' |')
    lines += [f"| Actual paired-price market (conditional only) | {fmt(scores['market_cover_ll'])} | {fmt(scores['market_cover_brier'])} | Unidentified | Unidentified |", '',
              f"All-game cohort {main['games']}; decisive {main['decisive']}; exact paired-price cohort {main['paired_games']}. "
              'Pushes are excluded identically from conditional cover scoring. Paired-subset soft/hard scores are retained in results.json.', '',
              '## Primary paired gains', '', 'Positive favors soft. The two intervals are 97.5% each (Bonferroni familywise 95%).', '']
    for name in ('soft_vs_hard_cover','soft_vs_market_cover'):
        g = main['gains'][name]
        gain = f"{g['gain']:+.6f}" if g['gain'] is not None else 'Unavailable'
        lines.append(f"- {name}: gain {gain}; interval {g['interval']}; n={g['n']}.")
    lines += ['', '## ATS returns', '',
              'Uniform -110 is hypothetical. Paired prices require both exact-handicap side prices. Historical schedule capture times '
              'are unknown, and 2026 ESPN closes are retrospective estimates; neither scenario certifies execution at lock.', '',
              '| Period | Prices | Policy | Bets / passes | W-L-P | Units | ROI +/- SE | Same-selected favorite units |',
              '| --- | --- | --- | ---: | --- | ---: | ---: | ---: |']
    for basis in ('2023-25','2026 diagnostic'):
        if basis not in result['bases']:
            continue
        for scenario, arms in result['bases'][basis]['scenarios'].items():
            for arm,r in arms.items():
                roi = f"{100*r['roi']:+.2f}%" if r['roi'] is not None else 'Undefined'
                se = f" +/- {100*r['roi_se']:.2f} pp" if r.get('roi_se') is not None else ''
                control = r.get('same_selected_controls',{}).get('favorite',{}).get('units')
                control = f'{control:+.3f}' if control is not None else 'Undefined'
                lines.append(f"| {basis} | {scenario} | {arm} | {r['bets']} / {r['passes']} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.3f} | {roi}{se} | {control} |")
    lines += ['', '## Annual paired-price results', '',
              '| Season | Soft cover LL | Market cover LL | Soft EV bets | Soft EV ROI |',
              '| --- | ---: | ---: | ---: | ---: |']
    for year in ('2023','2024','2025','2026 diagnostic'):
        if year not in result['bases']:
            continue
        b=result['bases'][year];r=b['scenarios']['paired']['soft_ev']
        roi=f"{100*r['roi']:+.2f}%" if r['roi'] is not None else 'Undefined'
        lines.append(f"| {year} | {fmt(b['scores']['soft_cover_ll_paired'])} | {fmt(b['scores']['market_cover_ll'])} | {r['bets']} | {roi} |")
    r=main['scenarios']['paired']['soft_ev']
    if r['roi'] is not None and r['mean_predicted_selected_conditional'] is not None:
        lines += ['', f"Main paired-price soft EV ROI 95% interval: {r['roi_ci95']}. "
                  f"Mean predicted conditional cover on its decisive selections: {100*r['mean_predicted_selected_conditional']:.2f}%; "
                  f"realized: {100*r['cover_rate']:.2f}%. Expected units: {r['expected_units']:+.3f}; realized units: {r['units']:+.3f}."]
    lines += ['', 'Complete yearly tables, bootstrap ROI intervals, expected returns, calibration bins, zero-probability events '
              'and same-selected median/raw/favorite/home controls are in results.json and calibration.csv.', '',
              '## Interpretation and limitations', '',
              '- This tests one fixed interpolation of the empirical band distributions, with a matched hard-PMF control.',
              '- Empirical key-number masses and tails are preserved; the mixture can have median jumps even when its cover probabilities are continuous.',
              '- The endpoint PMFs are clamped outside their prior median anchors. The separate raw-sign orientation boundary at zero is not solved.',
              '- Small bands can have zero mass on an event later observed. Forecasts are unchanged; score clipping and zero-event counts are explicit.',
              '- Bootstrap intervals resample complete weeks within season; they omit recipe/design-selection uncertainty and refitting uncertainty.',
              '- All historical data and the 2026 diagnostic are exposed. No result is independent forward validation or a production adoption decision.', '',
              'Reproduce: `python -m research.soft_band_distributions`', '']
    return '\n'.join(lines)


def run(input_path=INPUT, output_dir=OUTPUT):
    output_dir = writable(output_dir)
    raw = pd.read_csv(input_path)
    forecasts, fits = evaluate(raw)
    result = report(forecasts, fits)
    output_dir.mkdir(parents=True, exist_ok=True)
    forecasts.to_csv(output_dir/'predictions.csv', index=False, float_format='%.17g')
    dump(output_dir/'fits.json', fits)
    dump(output_dir/'results.json', result)
    calibration(forecasts).to_csv(output_dir/'calibration.csv', index=False, float_format='%.17g')
    boundary_diagnostics(fits).to_csv(output_dir/'boundary_diagnostics.csv', index=False, float_format='%.17g')
    (output_dir/'REPORT.md').write_text(markdown(result))
    dump(output_dir/'provenance.json', dict(policy=POLICY, bootstrap_repeats=REPEATS, bootstrap_seed=SEED,
         protocol_sha256=sha(ROOT/'research/SOFT_BAND_DISTRIBUTIONS.md'),
         code_sha256=sha(Path(__file__)), frozen_input_sha256=sha(input_path),
         production_changed=False, independent_validation=False, price_search=False,
         assumption='Uniform -110 and exact paired archived offers are distinct retrospective scenarios.'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=INPUT)
    parser.add_argument('--output-dir', type=Path, default=OUTPUT)
    parser.add_argument('--prepare-inputs', action='store_true')
    args = parser.parse_args()
    if args.prepare_inputs:
        prepare_inputs(args.input)
        print(f'Frozen research pack: {args.input}')
    else:
        result = run(args.input, args.output_dir)
        print(json.dumps(dict(policy=POLICY, status=result['status'], results=str(args.output_dir)), indent=2))


if __name__ == '__main__':
    main()
