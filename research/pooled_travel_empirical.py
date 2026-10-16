"""R003-PT1: regularized pooled travel likelihoods tilt observed score atoms."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp

import schedule_context_empirical as s

m = s.m
b = s.b
OUT = m.OUT.parent / 'R003_pooled_travel'
CLASSES = ('small_shift', 'eastward2plus', 'westward2plus')


@dataclass(frozen=True)
class Config:
    name: str
    quadratic: bool = False
    ridge: float = 20.


PLAIN = Config('plain')
CANDIDATES = (PLAIN,) + tuple(Config(f'{shape}_r{ridge}', shape == 'quadratic', ridge)
    for shape in ['linear', 'quadratic'] for ridge in [20, 100])


def design(spread, total, home, away, quadratic):
    spread, total, home, away = np.broadcast_arrays(spread, total, home, away)
    x = spread.ravel() / 10
    y = (total.ravel() - 44) / 10
    r = np.clip((home.ravel() - away.ravel() - spread.ravel()) / 14, -4, 4)
    u = np.clip((home.ravel() + away.ravel() - total.ravel()) / 14, -4, 4)
    columns = [np.ones(len(x)), x, y, x*x, y*y, x*y, r, u]
    if quadratic:
        columns += [r*r-1, u*u-1, r*u]
    result = np.column_stack(columns)
    if not np.isfinite(result).all():
        raise ValueError('Nonfinite design')
    return result


def log_probabilities(x, coef):
    logits = np.column_stack([np.zeros(len(x)), x @ coef])
    return logits - logsumexp(logits, axis=1, keepdims=True)


def objective(flat, x, y, weights, penalty):
    coef = flat.reshape(x.shape[1], 2)
    lp = log_probabilities(x, coef)
    loss = -weights @ lp[np.arange(len(y)), y] + .5*np.sum(penalty[:, None]*coef**2)
    error = np.exp(lp)
    error[np.arange(len(y)), y] -= 1
    grad = x.T @ (weights[:, None]*error[:, 1:]) + penalty[:, None]*coef
    return float(loss), grad.ravel()


def fit(history, target, config):
    if (not m.j.before(history, int(target['season']), int(target['week'])).all()
            or (history.season < int(target['season'])-5).any()):
        raise ValueError('Training violates prior-week/window contract')
    valid = history.feature_travel.isin(CLASSES)
    h = history[valid]
    age = (int(target['season'])-h.season.to_numpy())*19 + int(target['week'])-h.week.to_numpy()
    time = m.normalized_log_weights(-np.log(2)*age/38) if len(h) else np.array([])
    labels = h.feature_travel.map({v:i for i,v in enumerate(CLASSES)}).to_numpy(int)
    support = [m.effective(time[labels == i]) if (labels == i).any() else 0. for i in range(3)]
    audit = dict(training_games=len(h), class_counts=[int((labels == i).sum()) for i in range(3)],
                 class_support=support, training_max_season=int(history.season.max()),
                 training_max_week=int(history[history.season.eq(history.season.max())].week.max()))
    if len(h) < 200:
        return dict(coef=None, **audit, converged=True, reason='small_pooled_support')
    x = design(h.spread_line, h.total_line, h.home_score, h.away_score, config.quadratic)
    penalty = np.r_[.01, np.ones(5), np.full(x.shape[1]-6, config.ridge)]
    weights = time * m.effective(time)
    result = minimize(objective, np.zeros(x.shape[1]*2), args=(x, labels, weights, penalty),
                      jac=True, method='L-BFGS-B',
                      options=dict(gtol=1e-7, ftol=1e-12, maxiter=1000))
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError(f'Pooled fit failed: {result.message}')
    return dict(coef=result.x.reshape(x.shape[1], 2), **audit, converged=True,
                iterations=int(result.nit), objective=float(result.fun), reason='fitted')


def tilt(base, history, target, config, fitted):
    if not np.array_equal(base['source_ids'], history.game_id.to_numpy()):
        raise ValueError('Source atom/history alignment mismatch')
    if (fitted['training_max_season'], fitted['training_max_week']) >= (int(target['season']), int(target['week'])):
        raise ValueError('Future fitted coefficients')
    w = base['weights']
    key = target['feature_travel']
    index = CLASSES.index(key) if isinstance(key, str) and key in CLASSES else None
    support = fitted['class_support'][index] if index is not None else 0.
    audit = dict(pooled_support=float(support), travel_alpha=0., travel_fallback=True,
                 weight_l1=0., ratio_capped_fraction=0., fallback_reason='unknown_or_sparse')
    if index is None or fitted['coef'] is None or support < 20:
        return dict(base, audit=dict(base['audit'], **audit))
    # Market-only coefficients cancel: no score dependence implies exactly plain.
    if not np.any(fitted['coef'][6:, :]):
        return dict(base, audit=dict(base['audit'], **dict(audit, fallback_reason='no_shape_signal')))
    x = design(float(target['spread_line']), float(target['total_line']),
               base['home'], base['away'], config.quadratic)
    lp = log_probabilities(x, fitted['coef'])[:, index]
    log_mass = logsumexp(np.log(w, where=w>0, out=np.full_like(w, -np.inf)) + lp)
    ratio = np.exp(np.clip(lp-log_mass, -np.log(2), np.log(2)))
    tilted = w*ratio
    tilted /= tilted.sum()
    alpha = support/(support+100)
    weights = (1-alpha)*w + alpha*tilted
    if not np.isfinite(weights).all() or (weights < 0).any() or not np.isclose(weights.sum(), 1, atol=1e-12):
        raise AssertionError('Invalid tilted distribution')
    audit.update(travel_alpha=float(alpha), travel_fallback=False, fallback_reason='pooled_tilt',
                 weight_l1=float(np.abs(weights-w).sum()),
                 ratio_capped_fraction=float(w[np.abs(lp-log_mass)>np.log(2)].sum()))
    return dict(base, weights=weights, audit=dict(base['audit'], **audit, final_ess=m.effective(weights)))


def select(archive, year):
    eligible = archive[archive.season < year]
    if eligible.season.nunique() < 2:
        raise ValueError('Need two earlier OOF seasons')
    choices = [c.name for c in CANDIDATES]
    groups = eligible[eligible.arm.isin(choices)].groupby('arm')
    losses = groups.win_ll.mean()
    if set(losses.index) != set(choices) or groups.size().nunique() != 1 or not np.isfinite(losses).all():
        raise ValueError('Incomplete/nonfinite selection paths')
    chosen = min(choices, key=lambda name: losses[name])
    return chosen, dict(target_season=int(year), selection_max_season=int(eligible.season.max()),
                        chosen=chosen, criterion='winner_log_loss', losses=losses.to_dict())


def summarize(result, selections, out):
    metrics, comparisons, returns, slices = [], [], [], []
    bases = [('2023-25', result.season.between(2023,2025)),
             ('2017-22', result.season.between(2017,2022)), ('2026 diagnostic', result.season.eq(2026))]
    score_cols = list(m.LOSSES) + ['margin3_probability', 'margin7_probability', 'p_tie']
    score_cols += [f'{t}_{metric}{level}' for t in ['home','away','margin','total']
                   for metric in ['coverage','width'] for level in [50,80,90]]
    for basis, mask in bases:
        sub = result[mask]
        plain = sub[sub.arm.eq('plain')].set_index('game_id').sort_index()
        for name, g in sub.groupby('arm'):
            g = g.set_index('game_id').sort_index()
            if not g.index.equals(plain.index):
                raise AssertionError('Unpaired populations')
            metrics.append(dict(basis=basis, arm=name, games=len(g), **{c:float(g[c].mean()) for c in score_cols}))
            cols = ['primary_crps','margin_crps','total_crps','win_ll','cover_ll','over_ll','model_units']
            delta = plain[cols].to_numpy()-g[cols].to_numpy()
            # Returns are positive in the opposite direction from proper losses.
            delta[:, -1] *= -1
            finite = ~np.isinf(delta).any(axis=0)
            boot = b.week_bootstrap(delta[:,finite], g.season, g.week)
            k = 0
            for i, col in enumerate(cols):
                ci = b.interval(boot[:,k]) if finite[i] else None
                adjusted = b.interval(boot[:,k], 1-.05/4) if finite[i] else None
                comparisons.append(dict(basis=basis, arm=name, metric=col,
                    gain=float(np.nanmean(delta[:,i])), ci95=ci, sensitivity_ci=adjusted))
                k += int(finite[i])
        returns.extend(b.roi_rows(sub,basis))
        for (arm,key), g in sub.groupby(['arm','feature_travel'],dropna=False):
            slices.append(dict(basis=basis,arm=arm,travel=key,n=len(g),primary_crps=float(g.primary_crps.mean()),
                win_ll=float(g.win_ll.mean()),units=float(g.model_units.sum()),
                mean_alpha=float(g.travel_alpha.mean()),fallback_fraction=float(g.travel_fallback.mean()),
                mean_support=float(g.pooled_support.mean()),mean_weight_l1=float(g.weight_l1.mean())))
    pd.DataFrame(metrics).to_csv(out/'metrics.csv',index=False)
    m.dump(out/'comparisons.json', comparisons)
    m.dump(out/'moneyline.json', returns)
    m.dump(out/'travel_slices.json', slices)
    main = result[result.season.between(2023,2025)]
    plain = main[main.arm.eq('plain')].set_index('game_id').sort_index()
    selected = main[main.arm.eq('selected')].set_index('game_id').loc[plain.index]
    delta = plain.primary_crps-selected.primary_crps
    annual = delta.groupby(plain.season).mean()
    primary = next(r for r in comparisons if r['basis']=='2023-25' and r['arm']=='selected' and r['metric']=='primary_crps')
    secondary = {c:float(plain[c].mean()-selected[c].mean()) for c in ['margin_crps','total_crps','win_ll','cover_ll','over_ll']}
    gates = dict(practical_gain=primary['gain']>=.01, positive_interval=primary['ci95'][0]>0,
                 annual_consistency=bool((annual>0).all()), secondary_scores=all(np.isfinite(v) and v>=-.002 for v in secondary.values()), integrity=True)
    decision = dict(experiment='R003-PT1', gates=gates,
        recommendation='retain for research' if all(gates.values()) else 'no qualified improvement',
        independent_validation=False, production_promotion=False)
    m.dump(out/'decision.json',decision)
    weekly = pd.DataFrame(dict(s=plain.season,w=plain.week,d=delta)).groupby(['s','w']).d.agg(['sum','count'])
    loo = (delta.sum()-weekly['sum'])/(len(delta)-weekly['count'])
    m.dump(out/'stability.json',dict(annual_primary_gain=annual.to_dict(),secondary_gains=secondary,
        leave_one_season_gain={str(y):float(delta[plain.season!=y].mean()) for y in annual.index},
        leave_one_week_gain_range=[float(loo.min()),float(loo.max())]))
    lines = ['# R003-PT1 — pooled travel adjustment', '',
        f"**Decision: {decision['recommendation']}.** Exposed historical development, not forward confirmation.", '',
        '## Flat 1u moneyline returns', '',
        '| Basis | Arm | Bets | Units | ROI ± SE | Favorite units | Market null |',
        '|---|---|---:|---:|---:|---:|---:|']
    for r in returns:
        if r['arm'] not in ['plain','selected']: continue
        favorite = next(x for x in returns if x['basis']==r['basis'] and x['arm']=='control_favorite')
        lines.append(f"| {r['basis']} | {r['arm']} | {r['bets']} | {r['units']:+.3f} | {100*r['roi']:+.2f}% ±{100*r['roi_se']:.2f} pp | {favorite['units']:+.3f} | {100*r['market_null']:+.2f}% |")
    lines += ['', 'Same-row eligible games; ties push. Full W–L–P, paired intervals and all fixed arms are in moneyline.json. No ATS/total ROI without offered prices.', '',
        '## Distribution scores, 816 games 2023–25', '',
        '| Arm | Primary CRPS ↓ | Gain vs plain | Win LL ↓ | Cover LL ↓ | Over LL ↓ |',
        '|---|---:|---:|---:|---:|---:|']
    for r in metrics:
        if r['basis']=='2023-25':
            lines.append(f"| {r['arm']} | {r['primary_crps']:.6f} | {plain.primary_crps.mean()-r['primary_crps']:+.6f} | {r['win_ll']:.6f} | {r['cover_ll']:.6f} | {r['over_ll']:.6f} |")
    lines += ['', f"Selected-policy gain: {primary['gain']:+.6f}; 95% paired week interval {primary['ci95']}; four-challenger sensitivity {primary['sensitivity_ci']}.",
        f"Annual gains: {annual.to_dict()}. Gates: {gates}.",
        f"Annual choices: {[(r['target_season'],r['chosen']) for r in selections]}.", '',
        '## Interpretation and limits', '',
        'The multinomial classifier shares prior-game evidence across market contexts and both travel directions. It estimates travel likelihood from market controls and residual score shape; capped Bayes density ratios reweight the SAME observed paired-score atoms. Ridge, ratio cap and class-support shrinkage constrain the adjustment. Target outcomes and source travel labels are not used to assign atom likelihoods at prediction time.', '',
        'Selection uses winner log loss from strictly earlier OOF seasons, including plain. The primary distribution score is average margin/total CRPS. All fixed arms and comparisons to earlier SC1 travel and selected paths are retained; post-hoc best-arm rank is not qualification.', '',
        'Pooling replaces exact-market travel subgroup scarcity with assumptions about a common relationship across market contexts. Travel labels are home-base timezone proxies, not actual itineraries or acclimation; neutral/unknown locations revert to plain. Team geography and market selection can confound the association. No causal travel effect is established.', '',
        'All historical years were exposed, and SC1 motivated this family. Bootstrap intervals condition on fitted forecast paths (10,000 whole-week resamples within season, seed 20261016); four-arm sensitivity does not correct all earlier adaptive research. Schedule revisions and historical quote timestamps remain unaudited. Nothing here establishes a forward betting edge.', '',
        'See PROTOCOL.md, registration_record.json, fitted_windows.json, feature_table.csv.gz, per-game predictions, provenance and travel_slices.json. Production and original experiments remain unchanged.', '',
        'Reproduce: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/pooled_travel_empirical.py`', '']
    (out/'REPORT.md').write_text('\n'.join(lines))


def run(out=OUT):
    out = m.guarded_output(out)
    if not out.name.startswith('R003_pooled_travel'):
        raise ValueError('Use a separate R003_pooled_travel output directory')
    registration = json.loads((out/'registration_record.json').read_text())
    if registration['protocol_sha256'] != m.j.sha256(out/'PROTOCOL.md'):
        raise ValueError('Registered protocol changed')
    frame = s.add_features(m.load_inputs(),pd.read_csv(s.REST))
    frame[['game_id','season','week','feature_travel']].to_csv(out/'feature_table.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    old_path = s.OUT/'predictions.csv.gz'
    old = pd.read_csv(old_path)
    saved = old[old.arm.eq('plain')].set_index('game_id')
    records, fits = [], []
    error = 0.
    for (year,week),test in frame[frame.season>=2015].groupby(['season','week'],sort=True):
        history = m.prior(frame,test.iloc[0])
        fitted = {c.name:fit(history,test.iloc[0],c) for c in CANDIDATES[1:]}
        fits += [dict(season=int(year),week=int(week),arm=name,**f) for name,f in fitted.items()]
        for _,row in test.iterrows():
            base = m.distribution(m.prepare_pool(history,row),s.PLAIN_CONFIG)
            meta = {k:row[k] for k in ['game_id','season','week','home_team','away_team','home_score','away_score',
                'spread_line','total_line','home_moneyline','away_moneyline','feature_travel']}
            for config in CANDIDATES:
                dist = base if config==PLAIN else tilt(base,history,row,config,fitted[config.name])
                metrics = m.grade(dist,row)
                if config==PLAIN:
                    metrics.update(pooled_support=0.,travel_alpha=0.,travel_fallback=True,weight_l1=0.,ratio_capped_fraction=0.)
                    if year>=2017:
                        error = max(error,max(abs(metrics[c]-saved.loc[row.game_id,c]) for c in
                            ['primary_crps','p_home_non_tie','cover_win','over_win']))
                        if error>1e-10: raise AssertionError('Plain reproduction failed')
                records.append(dict(arm=config.name,**meta,**metrics))
        if week==1: print(f'Completed {int(year)} W1',flush=True)
    raw = pd.DataFrame(records)
    selections, selected = [], []
    for year in sorted(raw.loc[raw.season>=2017,'season'].unique()):
        name,audit = select(raw,int(year));selections.append(audit)
        z = raw[raw.season.eq(year)&raw.arm.eq(name)].copy()
        z['configuration']=name;z['arm']='selected';selected.append(z)
    raw = raw[raw.season>=2017].copy();raw['configuration']=raw.arm
    result = pd.concat([raw,*selected],ignore_index=True)
    result['q'] = m.j.fair_moneyline(result.home_moneyline.to_numpy(),result.away_moneyline.to_numpy())
    result = s.exact_scores(result)
    features = frame.set_index('game_id').feature_travel
    controls = old[old.arm.isin(['travel_k100','selected_all'])].copy()
    controls['arm'] = controls.arm.map({'travel_k100':'SC1_travel_k100','selected_all':'SC1_selected'})
    controls['feature_travel'] = controls.game_id.map(features)
    controls['travel_alpha'] = controls.context_alpha
    controls['travel_fallback'] = controls.context_fallback
    controls['pooled_support'] = controls.context_support
    result = pd.concat([result,controls],ignore_index=True)
    checks = m.verify(result,selections)
    checks['unchanged_score_atoms'] = bool(result.removed_mass.eq(0).all())
    if not all(checks.values()): raise AssertionError(checks)
    s.serialization.write_predictions(result,out/'predictions.csv.gz')
    m.dump(out/'annual_selections.json',selections)
    # Convert coefficient arrays explicitly before serializing the audit log.
    for f in fits:
        if f['coef'] is not None: f['coef']=f['coef'].tolist()
    m.dump(out/'fitted_windows.json',fits)
    paths = [m.INPUT,s.REST,old_path,Path(__file__).resolve(),Path(s.__file__),Path(m.__file__),
             m.j.ROOT/'research/joint_market_residuals.py',m.j.ROOT/'research/joint_market_residuals_report.py']
    m.dump(out/'provenance.json',dict(experiment='R003-PT1',registration=registration,
        hashes={str(p.relative_to(m.j.ROOT)):m.j.sha256(p) for p in paths},
        configurations=[asdict(c) for c in CANDIDATES],verification=checks,
        baseline_reproduction_max_error=error,numpy=np.__version__,pandas=pd.__version__,
        independent_validation=False,production_changed=False))
    summarize(result,selections,out)
    print((out/'REPORT.md').read_text(),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=OUT)
    run(parser.parse_args().output_dir)
