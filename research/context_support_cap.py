"""Prior-week support cap on v1.16 pass hinges; see CONTEXT_SUPPORT_CAP.md."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import context_shrinkage as s

m, p, ROOT = s.m, s.p, s.ROOT
CONTEXTS = s.CONTEXTS
HINGES = CONTEXTS[1:]
CANDIDATES = {'cap_k5': 5, 'cap_k1': 1, 'cap_k10': 10}
PRIMARY = 'cap_k5'
ARMS = ('production', *CANDIDATES)
LEVEL = 1-.05/len(CANDIDATES)
REVISION = 'boxscore-composite-v1.16'
RECIPE = m.LEGACY_PRODUCT_RECIPE
PACK = ROOT/'research/shrinkage_results/frozen_training_features.csv.gz'
REFERENCE = ROOT/'research/restore_v116_results/historical_reproduction.csv'
SNAPSHOTS = ROOT/'research/restore_v116_inputs/forward_predictions.jsonl'
RESULTS = ROOT/'research/restore_v116_inputs/results.csv'
BASES = {'heldout': 'Exposed historical development: 2023-2025 held-out walk-forward, prior-week fits',
         'current': 'Current-season walk-forward diagnostic: 2026 games with outcomes in the frozen pack; not pooled',
         'replay': 'Counterfactual replay of native v1.16 snapshots at archived inputs; not forward evidence'}


def eligible(f):
    """Production's v1.16 training rows: ready, binary, priced, finite pass contexts."""
    return f.ready.astype(bool) & f['home won'].isin([0., 1.]) & np.isfinite(f.q) & np.isfinite(f[CONTEXTS]).all(axis=1)


def support_caps(train, k):
    """Per hinge: the k-th largest |x| among non-zero training values, else 0."""
    if isinstance(k, bool) or not isinstance(k, (int, np.integer)) or k < 1:
        raise ValueError('Support level must be a positive integer')
    raw = train[HINGES].to_numpy(float)
    if not np.isfinite(raw).all(): raise ValueError('Non-finite hinge training values')
    caps = {}
    for j, name in enumerate(HINGES):
        active = np.sort(np.abs(raw[raw[:, j] != 0, j]))[::-1]
        caps[name] = float(active[k-1]) if len(active) >= k else 0.
    return caps


def winsorize(frame, caps):
    """Clip each hinge to +/-cap; NaN, zero and in-support values are unchanged."""
    out = frame.copy()
    if caps is None: return out
    for name, cap in caps.items():
        if name not in HINGES or not np.isfinite(cap) or cap < 0: raise ValueError('Invalid support cap')
        out[name] = np.clip(out[name].to_numpy(float), -cap, cap)
    return out


def fit_arm(train, year, week, k=None):
    """Production fit after winsorizing hinges at caps read from these training rows only."""
    if not m.before(train, year, week).all(): raise ValueError('Training includes current/future week')
    rows = train[eligible(train)]
    caps = None if k is None else support_caps(rows, k)
    fitted = m.fit_composite(winsorize(rows, caps), RECIPE, int(year), int(week))
    if fitted['training_games'] != len(rows): raise ValueError('Support rows differ from training rows')
    active = {name: int((rows[name] != 0).sum()) for name in HINGES}
    return {**fitted, 'support_k': k, 'support_caps': caps, 'support_active_rows': active}


def predict_arm(frame, fitted):
    return m.apply_fit(winsorize(frame, fitted['support_caps']), fitted)


def slope(fitted, name):
    """Fitted log-odds per unit of the (winsorized) raw input."""
    i = fitted['names'].index(name)
    return float(fitted['beta'][i]/fitted['scale'][i])


def capped(frame, fitted):
    """True where the arm's cap changes at least one hinge input."""
    caps = fitted['support_caps']
    if caps is None: return np.zeros(len(frame), bool)
    return np.logical_or.reduce([(frame[name].abs() > caps[name]).to_numpy() for name in HINGES])


def compare(held, base='production'):
    """Same-row ROI, proper scores and paired candidate differences for one basis."""
    held = held.assign(market=held.q)
    arms = [*ARMS, 'market']
    bets = {a: m.flat_bets(held, a) for a in arms}
    common = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    proper = held['home won'].isin([0., 1.]).to_numpy()
    groups = (held.season.astype(int).astype(str)+'_'+held.week.astype(int).astype(str)).to_numpy()
    y = held['home won'].to_numpy(float)
    losses = {a: s.loss(y, held[a].to_numpy(float)) for a in arms}
    briers = {a: (held[a].to_numpy(float)-y)**2 for a in arms}
    rows, pairs, annual = [], [], []
    for a in arms:
        rows.append({'arm': a, **m.roi_summary(bets[a].loc[common]),
                     'log_loss': float(losses[a][proper].mean()), 'brier': float(briers[a][proper].mean())})
        for year in sorted(held.season.unique()):
            mask = (held.season == year).to_numpy()
            annual.append({'arm': a, 'season': int(year), **m.roi_summary(bets[a].loc[common & mask]),
                           'log_loss': float(losses[a][proper & mask].mean())})
    for a in CANDIDATES:
        du = (bets[a].units-bets[base].units).to_numpy()
        dl, db = losses[base]-losses[a], briers[base]-briers[a]
        flips = common & ((held[a] > .5) != (held[base] > .5)).to_numpy()
        bind = held[a+'__capped'].to_numpy(bool)
        many = len(np.unique(groups)) > 1
        pairs.append({'arm': a, 'support_k': CANDIDATES[a], 'confidence_level': LEVEL,
                      'roi_delta': float(du[common].mean()),
                      'roi_delta_ci': p.cluster_interval(du[common], groups[common], LEVEL) if many else None,
                      'll_gain': float(dl[proper].mean()),
                      'll_gain_ci': p.cluster_interval(dl[proper], groups[proper], LEVEL) if many else None,
                      'brier_gain': float(db[proper].mean()),
                      'side_flips': int(flips.sum()), 'flip_units_delta': float(du[flips].sum()),
                      'capped_games': int(bind.sum()), 'capped_proper_games': int((bind & proper).sum()),
                      'capped_ll_gain_total': float(dl[bind & proper].sum()),
                      'uncapped_ll_gain_total': float(dl[~bind & proper].sum()),
                      'capped_units_delta': float(du[common & bind].sum()),
                      'capped_flips': held.loc[flips & bind, 'game_id'].tolist()})
    return {'results': rows, 'comparisons': pairs, 'by_season': annual, 'bets': int(common.sum()),
            'proper_games': int(proper.sum()), 'excluded_bets': held.loc[~common, 'game_id'].tolist()}


def verdict(primary):
    """Decision rule fixed in CONTEXT_SUPPORT_CAP.md before any backtest."""
    if primary['ll_gain'] <= 0 or primary['flip_units_delta'] < 0: return 'not supported'
    lo, hi = primary['ll_gain_ci']
    return 'positive; interval excludes zero (development only)' if lo > 0 else 'unresolved'


def replay(f, train_mask, snapshots, results, fits):
    """Refit each arm on earlier weeks and score archived v1.16 snapshot inputs and quotes."""
    out = []
    for r in snapshots:
        year, week = r['season'], r['week']
        row = pd.DataFrame([{**r['model_inputs'], 'q': r['market_no_vig_wp'], 'game_id': r['game_id'],
                             'season': year, 'week': week, 'home_moneyline': r['home_moneyline'],
                             'away_moneyline': r['away_moneyline']}])
        res = results.get(r['game_id'], np.nan)
        row['home won'] = m.won(res)
        item = {'game_id': r['game_id'], 'generated_utc': r['generated_utc'], 'season': year, 'week': week,
                'home': r['home'], 'away': r['away'], 'home_moneyline': r['home_moneyline'],
                'away_moneyline': r['away_moneyline'], 'q': r['market_no_vig_wp'], 'result': res,
                'home won': row['home won'].iloc[0], 'archived_probability': r['model_wp'],
                **{name: float(row[name].iloc[0]) for name in HINGES}}
        for arm in ARMS:
            key = (year, week, arm)
            if key not in fits: fits[key] = fit_arm(f[train_mask & m.before(f, year, week)], year, week, CANDIDATES.get(arm))
            prob, _, parts = m.apply_fit(winsorize(row, fits[key]['support_caps']), fits[key], contributions=True)
            item[arm] = float(prob[0])
            item[arm+'__hinge_logit'] = float(sum(parts[0][fits[key]['names'].index(n)] for n in HINGES))
            item[arm+'__capped'] = bool(capped(row, fits[key])[0])
            bet = m.flat_bets(row.assign(model_wp=item[arm]), 'model_wp').iloc[0]
            item[arm+'__units'] = float(bet.units)
        fav = m.flat_bets(row.assign(model_wp=row.q), 'model_wp').iloc[0]
        item['favorite__units'] = float(fav.units)
        out.append(item)
    return pd.DataFrame(out)


def run(output_dir):
    output_dir = Path(output_dir).resolve()
    if any(output_dir == x or x in output_dir.parents for x in (ROOT/'data', ROOT/'public')):
        raise ValueError('Research cannot write production outputs')
    f = pd.read_csv(PACK)
    train_mask = eligible(f)
    reference = pd.read_csv(REFERENCE)
    heldout = f.game_id.isin(reference.game_id)
    current = (f.season == 2026) & f.ready.astype(bool) & f['home won'].isin([0., .5, 1.]) & np.isfinite(f.q) \
        & np.isfinite(f[CONTEXTS]).all(axis=1)
    if heldout.sum() != len(reference): raise ValueError('Historical coverage differs')
    held = f.loc[heldout | current, p.BASE_COLS+HINGES].copy()
    fits, audit = {}, []
    for (year, week), rows in held.groupby(['season', 'week'], sort=True):
        year, week = int(year), int(week); train = f[train_mask & m.before(f, year, week)]; test = f.loc[rows.index]
        for arm in ARMS:
            fitted = fits[(year, week, arm)] = fit_arm(train, year, week, CANDIDATES.get(arm))
            held.loc[rows.index, arm] = predict_arm(test, fitted)
            held.loc[rows.index, arm+'__capped'] = capped(test, fitted)
            audit.append({'season': year, 'week': week, 'arm': arm, 'support_k': fitted['support_k'],
                          'training_games': fitted['training_games'], 'training_max_season': fitted['training_max_season'],
                          'training_max_week': fitted['training_max_week_in_latest_season'],
                          **{f'{n}__cap': (fitted['support_caps'] or {}).get(n, np.inf) for n in HINGES},
                          **{f'{n}__active_rows': fitted['support_active_rows'][n] for n in HINGES},
                          **{f'{n}__slope': slope(fitted, n) for n in CONTEXTS}})
        if week == 1: print(f'Fit season {year}', flush=True)
    if not np.isfinite(held[list(ARMS)]).all().all(): raise ValueError('Incomplete predictions')
    for c in [a+'__capped' for a in ARMS]: held[c] = held[c].astype(bool)
    audit = pd.DataFrame(audit)
    prior = (audit.training_max_season < audit.season) | ((audit.training_max_season == audit.season) & (audit.training_max_week < audit.week))
    if not prior.all(): raise ValueError('Training cutoff is not strictly prior')
    expected = reference.set_index('game_id').model_wp
    hist_err = float(abs(held.set_index('game_id').loc[expected.index, 'production']-expected).max())
    if hist_err >= 1e-7: raise ValueError(f'Committed v1.16 historical reproduction failed: {hist_err}')
    snapshots = [json.loads(x) for x in SNAPSHOTS.read_text().splitlines()]
    snapshots = [r for r in snapshots if r['revision'] == REVISION]
    results = pd.read_csv(RESULTS).set_index('game_id').result.to_dict()
    replayed = replay(f, train_mask, snapshots, results, fits)
    replay_err = float(abs(replayed.production-replayed.archived_probability).max())
    if replay_err >= 1e-9: raise ValueError(f'Archived v1.16 snapshot reproduction failed: {replay_err}')
    hist = held[held.season.between(2023, 2025)].reset_index(drop=True)
    cur = held[held.season == 2026].reset_index(drop=True)
    info = {'protocol': 'research/CONTEXT_SUPPORT_CAP.md', 'revision': REVISION, 'model_revision_at_run': m.REVISION,
            'recipe': RECIPE, 'candidates': CANDIDATES, 'primary': PRIMARY, 'confidence_level': LEVEL,
            'bases': BASES, 'heldout': compare(hist), 'current': compare(cur),
            'historical_max_probability_error': hist_err, 'replay_max_probability_error': replay_err,
            'fits': len(audit), 'all_training_cutoffs_prior': bool(prior.all())}
    primary = next(c for c in info['heldout']['comparisons'] if c['arm'] == PRIMARY)
    info['verdict'] = verdict(primary)
    sf = replayed.set_index('game_id').loc['2026_05_SF_SEA']
    info['posthoc'] = {
        'note': 'Added after the primary result; descriptive only and not part of the decision rule',
        'median_slope': {n: {a: float(audit.loc[audit.arm == a, f'{n}__slope'].median()) for a in ARMS} for n in CONTEXTS},
        'sf_sea_hinge_logit': {a: float(sf[a+'__hinge_logit']) for a in ARMS},
        'sf_sea_probability': {a: float(sf[a]) for a in ARMS}}
    graded = replayed[replayed['home won'].isin([0., .5, 1.])]
    proper = graded[graded['home won'].isin([0., 1.])]
    yr = proper['home won'].to_numpy(float)
    info['replay'] = {'snapshots': len(replayed), 'graded': len(graded), 'pending': int(len(replayed)-len(graded)),
                      **{a: {'units': float(graded[a+'__units'].sum()), 'bets': int(graded[a+'__units'].notna().sum()),
                             'log_loss': float(s.loss(yr, proper[a].to_numpy(float)).mean()),
                             'capped_games': int(replayed[a+'__capped'].sum())} for a in ARMS},
                      'market_log_loss': float(s.loss(yr, proper.q.to_numpy(float)).mean()),
                      'favorite_units': float(graded['favorite__units'].sum())}
    output_dir.mkdir(parents=True, exist_ok=True)
    held.to_csv(output_dir/'heldout_predictions.csv', index=False)
    audit.to_csv(output_dir/'caps.csv', index=False)
    replayed.to_csv(output_dir/'current_counterfactuals.csv', index=False)
    (output_dir/'results.json').write_text(json.dumps(info, indent=2, allow_nan=False)+'\n')
    sources = [Path(__file__).resolve(), ROOT/'research/CONTEXT_SUPPORT_CAP.md', ROOT/'research/context_shrinkage.py',
               ROOT/'nfl_model.py', PACK, REFERENCE, SNAPSHOTS, RESULTS]
    (output_dir/'provenance.json').write_text(json.dumps(
        {str(x.relative_to(ROOT)): hashlib.sha256(x.read_bytes()).hexdigest() for x in sources}, indent=2)+'\n')
    write_report(info, replayed, output_dir)
    print(json.dumps({'verdict': info['verdict'], 'primary': primary}, indent=2), flush=True)


def _ci(v, scale=1., fmt='+.2f'):
    return 'n/a' if v is None else f'[{scale*v[0]:{fmt}}, {scale*v[1]:{fmt}}]'


def _table(block, title, level):
    lines = [f'## {title}', '', f"{block['bets']} common flat 1u bets; {block['proper_games']} binary proper scores.", '',
             '| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Log loss | Brier |', '|---|---:|---:|---:|---:|---:|---:|']
    for r in block['results']:
        name = 'market favorite' if r['arm'] == 'market' else r['arm']
        lines.append(f"| {name} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | "
                     f"{100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} | {100*r['null_roi']:+.2f}% | {r['log_loss']:.6f} | {r['brier']:.6f} |")
    lines += ['', f'Paired with production; week-cluster bootstrap intervals at {100*level:.2f}%. Positive values favor the cap.', '',
              '| Arm | ROI delta, pp [CI] | LL gain [CI] | Brier gain | Side flips | Flip units vs production | Capped games | LL gain on capped games (total) |',
              '|---|---:|---:|---:|---:|---:|---:|---:|']
    for c in block['comparisons']:
        lines.append(f"| {c['arm']} | {100*c['roi_delta']:+.2f} {_ci(c['roi_delta_ci'], 100)} | {c['ll_gain']:+.6f} "
                     f"{_ci(c['ll_gain_ci'], 1, '+.6f')} | {c['brier_gain']:+.6f} | {c['side_flips']} | {c['flip_units_delta']:+.2f} | "
                     f"{c['capped_games']} | {c['capped_ll_gain_total']:+.4f} |")
    return lines


def write_report(info, replayed, out):
    h = info['heldout']; primary = next(c for c in h['comparisons'] if c['arm'] == PRIMARY)
    lines = ['# Context support cap backtest', '',
             'Protocol: [CONTEXT_SUPPORT_CAP.md](../CONTEXT_SUPPORT_CAP.md), committed before this run. '
             'Production v1.16 and its ledger are unchanged.', '',
             f"**Verdict for the primary arm ({PRIMARY}), by the pre-registered rule: {info['verdict']}.** "
             f"Pooled 2023–2025 log-loss gain over production {primary['ll_gain']:+.6f} {_ci(primary['ll_gain_ci'], 1, '+.6f')}; "
             f"{primary['side_flips']} side flips worth {primary['flip_units_delta']:+.2f}u against production.", '',
             'Basis: '+BASES['heldout']+'. Recipe design used this history; not forward evidence.', '']
    lines += _table(h, '2023–2025 held-out (primary basis)', info['confidence_level'])
    lines += ['', '### By season', '', '| Arm | Season | W-L-P | Units | ROI | Log loss |', '|---|---:|---:|---:|---:|---:|']
    for r in h['by_season']:
        name = 'market favorite' if r['arm'] == 'market' else r['arm']
        lines.append(f"| {name} | {r['season']} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% | {r['log_loss']:.6f} |")
    ph = info['posthoc']
    lines += ['', '## Post-hoc diagnostics', '', ph['note']+'.', '']
    for c in h['comparisons']:
        named = ', '.join(c['capped_flips']) or 'none'
        lines.append(f"- {c['arm']}: {c['side_flips']} side flips worth {c['flip_units_delta']:+.2f}u; flips on capped games: "
                     f"{named} ({c['capped_units_delta']:+.2f}u); the rest moved only through refitted coefficients "
                     f"({c['flip_units_delta']-c['capped_units_delta']:+.2f}u).")
    slopes = ph['median_slope']
    steeper = [n for n in HINGES if abs(slopes[n][PRIMARY]) > abs(slopes[n]['production'])]
    flatter = [n for n in HINGES if n not in steeper]
    lines += ['', 'Median refitted slope over all evaluation weeks, in log-odds per unit of hinge input. Winsorizing shrinks a '
              'hinge\'s training SD, and the ridge penalty applies to SD-standardized coefficients, so the raw slope is penalized '
              f"less. With {PRIMARY} the median slope is steeper than production's for {', '.join(steeper) or 'no hinge'}"
              + (f" and flatter for {', '.join(flatter)}" if flatter else '') + '; a capped input can keep much of its contribution.', '',
              '| Context | '+' | '.join(ARMS)+' |', '|---|'+'---:|'*len(ARMS)]
    for n in CONTEXTS:
        lines.append(f'| {n} | '+' | '.join(f"{ph['median_slope'][n][a]:+.3f}" for a in ARMS)+' |')
    lines += ['', 'SF@SEA at its archived inputs, hinge contribution to the log-odds (Seattle probability): '
              + '; '.join(f"{a} {ph['sf_sea_hinge_logit'][a]:+.2f} ({100*ph['sf_sea_probability'][a]:.1f}%)" for a in ARMS)+'.']
    lines += [''] + _table(info['current'], '2026 diagnostic (not pooled)', info['confidence_level'])
    lines += ['', 'Basis: '+BASES['current']+'.', '', '## Native v1.16 snapshot replay (counterfactual)', '',
              'Home-team probabilities at the archived inputs and moneylines, each arm refitted on earlier weeks. '
              'Not new forward snapshots; the native ledger is unchanged.', '',
              '| Game | Market q | Archived | production | '+' | '.join(CANDIDATES)+' | Result | PN input |',
              '|---|---:|---:|---:|'+'---:|'*len(CANDIDATES)+'---:|---:|']
    for _, r in replayed.iterrows():
        res = 'pending' if pd.isna(r.result) else f'{r.result:+.0f}'
        lines.append(f"| {r.away}@{r.home} | {100*r.q:.1f}% | {100*r.archived_probability:.1f}% | {100*r.production:.1f}% | "
                     + ' | '.join(f'{100*r[a]:.1f}%' for a in CANDIDATES) + f" | {res} | {r.pass_1sd_pn:+.3f} |")
    rp = info['replay']
    lines += ['', f"Replay totals over {rp['graded']} graded snapshots ({rp['pending']} pending): "
              + '; '.join(f"{a} {rp[a]['units']:+.2f}u, LL {rp[a]['log_loss']:.4f}, {rp[a]['capped_games']} capped" for a in ARMS)
              + f"; market LL {rp['market_log_loss']:.4f}; favorite {rp['favorite_units']:+.2f}u.", '',
              '## Reproduction and limits', '',
              f"Production arm vs committed v1.16 history: max probability error {info['historical_max_probability_error']:.3g}. "
              f"Production arm vs archived v1.16 snapshots: max probability error {info['replay_max_probability_error']:.3g}. "
              f"All {info['fits']} weekly fits train strictly before their evaluation week; caps read only those training rows.",
              'Caps change only the few games with large hinge values, so power is low and the historical comparison cannot settle '
              'whether the cap helps. Intervals omit model-design selection uncertainty. Exposed history; no forward confirmation. '
              'Adoption would be an owner decision and a new REVISION.', '',
              'Run: `python research/context_support_cap.py`.', '']
    (out/'REPORT.md').write_text('\n'.join(lines))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir', type=Path, default=ROOT/'research/support_cap_results')
    run(ap.parse_args().output_dir)
