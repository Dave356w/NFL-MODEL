"""R003-MC1: observed historical outcomes conditional on spread/total context.

No Gaussian, possible-score enumeration, production imports or network requests.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import xlogy

import joint_market_residuals as j
import joint_market_residuals_report as bootstrap
import distribution_ablations as serialization
import r003_spread_ev as settlement

OUT = j.ROOT / 'research/experiments/R003_market_context'
INPUT = j.ROOT / 'research/experiments/R000_reproduction/frozen_inputs.csv.gz'


@dataclass(frozen=True)
class Config:
    name: str
    family: str = 'direct_kernel'
    spread_bandwidth: float = 4.
    total_bandwidth: float = 6.
    pseudo_games: float = 80.
    neighbors: int = 0
    translated: bool = False
    global_only: bool = False


CANDIDATES = tuple(
    Config(f'direct_h{h:g}_t{t:g}_p{p}', spread_bandwidth=h, total_bandwidth=t, pseudo_games=p)
    for h, t in [(2., 3.), (4., 6.), (8., 10.)] for p in [20, 80]
) + tuple(Config(f'neighbors_{k}', family='direct_neighbor', neighbors=k) for k in [100, 250]) + tuple(
    Config(f'residual_p{p}', family='residual', pseudo_games=p, translated=True) for p in [20, 80])
CONTROLS = (Config('global_direct', global_only=True),
            Config('global_residual', family='residual', translated=True, global_only=True))
REFINEMENTS = tuple(Config(f'direct_ref_h{h:g}_t{t:g}_p{p}',spread_bandwidth=h,total_bandwidth=t,pseudo_games=p)
    for h,t in [(1.,2.),(2.,3.),(4.,6.)] for p in [0,5]) + tuple(
    Config(f'neighbors_ref_{k}_p{p}',family='direct_neighbor',neighbors=k,pseudo_games=p)
    for k in [100,250] for p in [0,5])
CONFIGS = {c.name: c for c in CANDIDATES + REFINEMENTS + CONTROLS}
SELECTED = ('selected_all', 'selected_direct_kernel', 'selected_direct_neighbor', 'selected_residual')
LOSSES = ('primary_crps', 'home_crps', 'away_crps', 'margin_crps', 'total_crps',
          'win_ll', 'win_brier', 'cover_ll', 'cover_brier', 'over_ll', 'over_brier',
          'tie_ll', 'tie_brier')


def load_inputs(path=INPUT):
    f = pd.read_csv(path)
    if f.game_id.duplicated().any():
        raise ValueError('Duplicate source game IDs')
    fields = ['home_score', 'away_score', 'spread_line', 'total_line']
    complete = f[np.isfinite(f[fields]).all(axis=1)].copy()
    scores = complete[['home_score', 'away_score']].to_numpy(float)
    if (scores < 0).any() or not np.equal(scores, np.floor(scores)).all():
        raise ValueError('Observed scores must be nonnegative integers')
    return complete.sort_values(['season', 'week', 'game_id']).reset_index(drop=True)


def prior(frame, target):
    year, week = int(target['season']), int(target['week'])
    if year != target['season'] or week != target['week'] or not 1 <= week <= 19:
        raise ValueError('Invalid target season/week')
    f = frame[j.before(frame, year, week) & (frame.season >= year - 5)].copy()
    if f.empty or f.game_id.duplicated().any():
        raise ValueError('Need unique earlier source games')
    if str(target['game_id']) in set(f.game_id):
        raise ValueError('Target game appears in source history')
    return f.sort_values('game_id').reset_index(drop=True)


def prepare_pool(history, target):
    """Only prices and identity are consumed from the target; outcomes are absent."""
    spread, total = float(target['spread_line']), float(target['total_line'])
    if not np.isfinite([spread, total]).all() or total <= 0:
        raise ValueError('Finite spread and positive total are required')
    year, week = int(target['season']), int(target['week'])
    if not j.before(history, year, week).all() or (history.season < year - 5).any():
        raise ValueError('Source history violates the prior-week/window contract')
    age = (year - history.season.to_numpy(float)) * 19 + week - history.week.to_numpy(float)
    time_log_weight = -np.log(2.) * age / 38.
    return dict(ids=history.game_id.to_numpy(), seasons=history.season.to_numpy(),
                weeks=history.week.to_numpy(), home=history.home_score.to_numpy(float),
                away=history.away_score.to_numpy(float), spread=history.spread_line.to_numpy(float),
                total=history.total_line.to_numpy(float), time_log_weight=time_log_weight,
                target_spread=spread, target_total=total)


def effective(weights):
    w = np.asarray(weights, float)
    return float(w.sum()**2 / (w @ w))


def normalized_log_weights(logw):
    z = np.exp(logw - np.max(logw))
    return z / z.sum()


def distribution(pool, config):
    """A weighted set of historical paired-score atoms, never an 81x81 grid."""
    time = normalized_log_weights(pool['time_log_weight'])
    distance = ((pool['spread'] - pool['target_spread']) / config.spread_bandwidth)**2
    distance += ((pool['total'] - pool['target_total']) / config.total_bandwidth)**2
    if config.global_only:
        local = time.copy(); alpha = 0.
    elif config.neighbors:
        take = np.argsort(distance, kind='stable')[:config.neighbors]
        local = np.zeros(len(time)); local[take] = time[take] / time[take].sum()
        alpha = effective(local) / (effective(local) + config.pseudo_games)
    else:
        local = normalized_log_weights(pool['time_log_weight'] - .5 * distance)
        alpha = effective(local) / (effective(local) + config.pseudo_games)
    weights = alpha * local + (1-alpha) * time
    home, away = pool['home'].copy(), pool['away'].copy()
    if config.translated:
        home += ((pool['target_total']+pool['target_spread']) - (pool['total']+pool['spread'])) / 2
        away += ((pool['target_total']-pool['target_spread']) - (pool['total']-pool['spread'])) / 2
        home, away = np.floor(home + .5), np.floor(away + .5)
    valid = (home >= 0) & (away >= 0)
    lost = float(weights[~valid].sum())
    if not valid.any() or weights[valid].sum() <= 0:
        raise ValueError('No valid empirical atoms remain')
    weights = weights[valid]; weights /= weights.sum()
    last = max(zip(pool['seasons'], pool['weeks']))
    audit = dict(source_games=len(time), retained_games=int(valid.sum()), local_ess=effective(local),
                 final_ess=effective(weights), local_fraction=float(alpha), removed_mass=lost,
                 removed_atoms=int((~valid).sum()), largest_atom=float(weights.max()),
                 training_max_season=int(last[0]), training_max_week=int(last[1]))
    return dict(home=home[valid], away=away[valid], weights=weights,
                source_ids=pool['ids'][valid], audit=audit)


def forecast(frame, target, config):
    return distribution(prepare_pool(prior(frame, target), target), config)


def event(values, line, weights):
    win = float(weights[values > line].sum()); push = float(weights[values == line].sum())
    lose = float(weights[values < line].sum())
    if not np.isclose(win+push+lose, 1, atol=1e-12, rtol=0):
        raise AssertionError('Event probabilities do not sum to one')
    return win, push, lose, win/(win+lose) if win+lose > 0 else np.nan


def binary_loss(y, p):
    """Exact endpoint loss: an incorrect zero/one forecast remains infinite."""
    return float(-xlogy(y, p)-xlogy(1-y, 1-p))


def empirical_crps(values, weights, actual):
    order = np.argsort(values, kind='stable'); x, w = values[order], weights[order]
    half_distance = np.sum(w*x*(2*np.cumsum(w)-w-1))
    return float(weights @ np.abs(values-actual) - half_distance)


def quantiles(values, weights, probs):
    order = np.argsort(values, kind='stable'); x, w = values[order], weights[order]
    cdf = np.cumsum(w); cdf[-1] = 1.
    return x[np.searchsorted(cdf, probs)]


def grade(dist, row):
    h, a, w = dist['home'], dist['away'], dist['weights']
    actual_h, actual_a = float(row.home_score), float(row.away_score)
    out = dict(dist['audit'])
    margin, total = h-a, h+a
    ph, pt, pa, pw = event(margin, 0, w)
    out.update(p_home=ph, p_tie=pt, p_away=pa, p_home_non_tie=pw,
               rare_either_probability=float(w[np.isin(h,[1,2,4,5])|np.isin(a,[1,2,4,5])].sum()),
               margin3_probability=float(w[abs(margin)==3].sum()),
               margin7_probability=float(w[abs(margin)==7].sum()))
    for name, values, actual in [('home',h,actual_h),('away',a,actual_a),
                                  ('margin',margin,actual_h-actual_a),('total',total,actual_h+actual_a)]:
        mean = float(w @ values)
        out[name+'_mean'] = mean; out[name+'_crps'] = empirical_crps(values,w,actual)
        out[name+'_sq_error'] = (mean-actual)**2
        out[name+'_abs_error'] = abs(mean-actual)
        out[name+'_pit_mid'] = float(w[values<actual].sum()+.5*w[values==actual].sum())
        qs = quantiles(values,w,[.05,.10,.25,.75,.90,.95])
        for level,lo,hi in [(50,qs[2],qs[3]),(80,qs[1],qs[4]),(90,qs[0],qs[5])]:
            out[f'{name}_coverage{level}'] = float(lo<=actual<=hi)
            out[f'{name}_width{level}'] = float(hi-lo)
    out['primary_crps'] = .5*(out['margin_crps']+out['total_crps'])
    win_y = float(actual_h>actual_a)
    out['win_ll'] = binary_loss(win_y,pw) if actual_h!=actual_a else np.nan
    out['win_brier'] = (win_y-pw)**2 if actual_h!=actual_a else np.nan
    for prefix,values,line,actual in [('cover',margin,float(row.spread_line),actual_h-actual_a),
                                       ('over',total,float(row.total_line),actual_h+actual_a)]:
        win,push,lose,p = event(values,line,w)
        out.update({prefix+'_win':win,prefix+'_push':push,prefix+'_lose':lose,prefix+'_conditional':p,
                    prefix+'_ll':binary_loss(float(actual>line),p) if actual!=line else np.nan,
                    prefix+'_brier':(float(actual>line)-p)**2 if actual!=line else np.nan})
    out['tie_ll'] = binary_loss(float(actual_h==actual_a),pt)
    out['tie_brier'] = (float(actual_h==actual_a)-pt)**2
    return out


def select_names(archive, year, family=None, candidates=CANDIDATES):
    eligible = archive[archive.season < year]
    if eligible.season.nunique()<2:
        raise ValueError('Annual selection needs two earlier OOF seasons')
    choices = [c.name for c in candidates if family is None or c.family==family]
    losses = eligible[eligible.arm.isin(choices)].groupby('arm').primary_crps.mean()
    counts = eligible[eligible.arm.isin(choices)].groupby('arm').size()
    if set(losses.index)!=set(choices) or counts.nunique()!=1 or not np.isfinite(losses).all():
        raise ValueError('Incomplete or nonfinite candidate selection paths')
    chosen = min(choices,key=lambda name:losses[name])
    return chosen,dict(target_season=int(year),family=family or 'all',chosen=chosen,
                       selection_max_season=int(eligible.season.max()),
                       selection_games=int(counts.iloc[0]),
                       losses={name:float(losses[name]) for name in choices})


def safe_json(value):
    if isinstance(value,dict):return {str(k):safe_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [safe_json(v) for v in value]
    if isinstance(value,(np.floating,float)):
        return float(value) if np.isfinite(value) else ('Infinity' if np.isinf(value) else None)
    if isinstance(value,np.integer):return int(value)
    if isinstance(value,np.bool_):return bool(value)
    return value


def dump(path,value):
    path.write_text(json.dumps(safe_json(value),indent=2,allow_nan=False)+'\n')


def guarded_output(path):
    out=Path(path).resolve(); root=(j.ROOT/'research/experiments').resolve()
    if not out.is_relative_to(root) or out==root:
        raise ValueError('Use a separate market-context experiment directory')
    protected=['R000_reproduction','R001_tie_hurdle','R002_ot_transitions','R003_score_support','R003_rare_frequency']
    if any(out==root/p or (root/p) in out.parents for p in protected):
        raise ValueError('Original experiment is protected')
    return out


def run(out=OUT,input_path=INPUT,candidates=CANDIDATES):
    out=guarded_output(out)
    registration=json.loads((out/'registration_record.json').read_text())
    if registration['protocol_sha256']!=j.sha256(out/'PROTOCOL.md'):
        raise ValueError('Registered protocol changed')
    frame=load_inputs(input_path); records=[]
    for (year,week),test in frame[frame.season>=2015].groupby(['season','week'],sort=True):
        target=dict(season=int(year),week=int(week),game_id=str(test.iloc[0].game_id))
        history=prior(frame,target)
        for _,row in test.iterrows():
            pool=prepare_pool(history,row)
            metadata={k:row[k] for k in ['game_id','season','week','home_team','away_team','home_score','away_score',
                      'spread_line','total_line','home_moneyline','away_moneyline']}
            for c in candidates+CONTROLS:
                dist=distribution(pool,c)
                records.append(dict(arm=c.name,**metadata,**grade(dist,row)))
    raw=pd.DataFrame(records); selection=[]; chosen_rows=[]
    for year in sorted(raw.loc[raw.season>=2017,'season'].unique()):
        for family in [None,*dict.fromkeys(c.family for c in candidates)]:
            name,audit=select_names(raw,int(year),family,candidates); selection.append(audit)
            z=raw[raw.season.eq(year)&raw.arm.eq(name)].copy()
            z['configuration']=name;z['arm']='selected_'+(family or 'all');chosen_rows.append(z)
    raw=raw[raw.season>=2017].copy();raw['configuration']=raw.arm
    result=pd.concat([raw,*chosen_rows],ignore_index=True)
    result['q']=j.fair_moneyline(result.home_moneyline.to_numpy(),result.away_moneyline.to_numpy())
    result=j.add_binary_and_bet_scores(result)
    # Existing grader computes the same proper scores, with endpoint clipping.
    # Restore exact empirical endpoint losses instead of accepting those floors.
    margin=result.home_score-result.away_score;total=result.home_score+result.away_score
    for prefix,prob,y,valid in [('win','p_home_non_tie',(margin>0),margin!=0),
                              ('cover','cover_conditional',margin>result.spread_line,margin!=result.spread_line),
                              ('over','over_conditional',total>result.total_line,total!=result.total_line)]:
        p=result[prob].to_numpy(); labels=y.to_numpy(float)
        with np.errstate(divide='ignore',invalid='ignore'):
            loss=-xlogy(labels,p)-xlogy(1-labels,1-p)
        result[prefix+'_ll']=np.where(valid,loss,np.nan)
    checks=verify(result,selection)
    serialization.write_predictions(result,out/'predictions.csv.gz')
    dump(out/'annual_selections.json',selection)
    sources=['research/market_context_empirical.py','research/joint_market_residuals.py',
             'research/joint_market_residuals_report.py','research/r003_spread_ev.py']
    dump(out/'provenance.json',dict(experiment=registration['experiment'],registration=registration,
         input_sha256=j.sha256(input_path),source_hashes={p:j.sha256(j.ROOT/p) for p in sources},
         configurations=[asdict(c) for c in candidates+CONTROLS],verification=checks,
         numpy=np.__version__,pandas=pd.__version__,fresh_validation=False,
         historical_quote_timestamps='unknown',production_changed=False))
    write_report(result,selection,out,registration['experiment'])
    print((out/'REPORT.md').read_text())
    return result


def verify(frame,selections):
    counts=frame.groupby('arm').size()
    checks=dict(no_duplicate_predictions=not frame.duplicated(['arm','game_id']).any(),
        identical_populations=counts.nunique()==1,
        main_n_816=all(len(g)==816 for _,g in frame[frame.season.between(2023,2025)].groupby('arm')),
        prior_week_inputs=all((r.training_max_season,r.training_max_week)<(r.season,r.week) for r in frame.itertuples()),
        prior_season_selection=all(r['selection_max_season']<r['target_season'] for r in selections),
        normalized_events=all(np.allclose(frame[a]+frame[b]+frame[c],1,atol=1e-12) for a,b,c in
            [('p_home','p_tie','p_away'),('cover_win','cover_push','cover_lose'),('over_win','over_push','over_lose')]),
        finite_primary=bool(np.isfinite(frame.primary_crps).all()),
        coherent_means=bool(np.allclose(frame.total_mean,frame.home_mean+frame.away_mean) and
                            np.allclose(frame.margin_mean,frame.home_mean-frame.away_mean)),
        direct_no_dropped_atoms=bool(frame[frame.configuration.str.startswith(('direct','neighbors','global_direct'))].removed_mass.eq(0).all()))
    if not all(checks.values()):raise AssertionError(checks)
    return {k:bool(v) for k,v in checks.items()}


def reference_rows():
    path=j.ROOT/'research/experiments/R003_score_support/predictions.csv.gz'
    r=pd.read_csv(path);r=r[r.arm.eq('empirical__R003_score_support')].copy()
    r['primary_crps']=.5*(r.margin_crps+r.total_crps);r['arm']='reference_R003'
    return r,path


def write_report(frame,selections,out,experiment='R003-MC1'):
    reference,reference_path=reference_rows()
    combined=pd.concat([frame,reference],ignore_index=True)
    summary=[];comparisons=[];returns=[];calibration=[]
    bases=[('2023-25',combined.season.between(2023,2025)),('2017-22',combined.season.between(2017,2022)),
           ('2026 diagnostic',combined.season.eq(2026))]
    bases += [(str(y),combined.season.eq(y)) for y in sorted(combined.season.unique())]
    extra=[f'{t}_{m}{level}' for t in ['home','away','margin','total'] for level in [50,80,90] for m in ['coverage','width']]
    for basis,mask in bases:
        sub=combined[mask]
        for name,g in sub.groupby('arm'):
            row=dict(basis=basis,arm=name,games=len(g),**{m:float(g[m].mean()) for m in LOSSES+tuple(extra)},
                     mean_tie_probability=float(g.p_tie.mean()),actual_ties=int((g.home_score==g.away_score).sum()))
            if name!='reference_R003':
                row.update(mean_final_ess=float(g.final_ess.mean()),min_final_ess=float(g.final_ess.min()),
                           mean_local_fraction=float(g.local_fraction.mean()),mean_removed_mass=float(g.removed_mass.mean()))
            summary.append(row)
        # Secondary intervals are descriptive; fixed 10k draws with exact paired IDs.
        b=sub[sub.arm.eq('reference_R003')].set_index('game_id').sort_index()
        for name,c in sub.groupby('arm'):
            if name=='reference_R003':continue
            c=c.set_index('game_id').sort_index()
            if not b.index.equals(c.index):raise AssertionError('Unpaired reference')
            metrics=['primary_crps','margin_crps','total_crps','win_ll','cover_ll','over_ll']
            delta=b[metrics].to_numpy()-c[metrics].to_numpy()
            if basis in ['2023-25','2017-22','2026 diagnostic']:
                finite_columns=~np.isinf(delta).any(axis=0)
                boot=bootstrap.week_bootstrap(delta[:,finite_columns],b.season,b.week)
                columns={col:pos for pos,col in enumerate(np.flatnonzero(finite_columns))}
                for ix,m in enumerate(metrics):
                    comparisons.append(dict(basis=basis,arm=name,metric=m,gain=float(np.nanmean(delta[:,ix])),
                        ci95=bootstrap.interval(boot[:,columns[ix]]) if ix in columns else None,
                        ci995=bootstrap.interval(boot[:,columns[ix]],.995) if ix in columns else None))
        if basis in ['2023-25','2017-22','2026 diagnostic']:
            returns.extend(bootstrap.roi_rows(sub,basis))
            for name,g in sub.groupby('arm'):
                m=g.home_score-g.away_score;tot=g.home_score+g.away_score
                for event_name,prob,y,valid in [('win',g.p_home_non_tie,m>0,m!=0),
                    ('cover',g.cover_conditional,m>g.spread_line,m!=g.spread_line),
                    ('over',g.over_conditional,tot>g.total_line,tot!=g.total_line)]:
                    z=pd.DataFrame(dict(p=prob,y=y.astype(float)))[valid]
                    for bin_id,gp in z.groupby(np.minimum((z.p*10).astype(int),9)):
                        calibration.append(dict(basis=basis,arm=name,event=event_name,bin=int(bin_id),n=len(gp),
                                                predicted=float(gp.p.mean()),observed=float(gp.y.mean())))
    pd.DataFrame(summary).to_csv(out/'metrics.csv',index=False)
    dump(out/'comparisons.json',comparisons);dump(out/'moneyline.json',returns)
    dump(out/'reliability.json',calibration)
    decision,notes=decision_and_stability(combined,comparisons,out,experiment)
    dump(out/'decision.json',decision)
    main=pd.DataFrame(summary);main=main[main.basis.eq('2023-25')]
    lines=['| Arm | Primary CRPS ↓ | Margin CRPS ↓ | Total CRPS ↓ | Win LL ↓ | Cover LL ↓ | Over LL ↓ |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for r in main.sort_values('primary_crps').itertuples():
        lines.append(f'| {r.arm} | {r.primary_crps:.5f} | {r.margin_crps:.5f} | {r.total_crps:.5f} | {r.win_ll:.6f} | {r.cover_ll:.6f} | {r.over_ll:.6f} |')
    money=['| Basis | Policy | Bets | Units | ROI ± SE | Favorite units | Null ROI |',
           '|---|---|---:|---:|---:|---:|---:|']
    for r in returns:
        if r['arm'] not in ['selected_all','selected_direct_kernel','selected_direct_neighbor','selected_residual','reference_R003']:continue
        fav=next(x['units'] for x in returns if x['basis']==r['basis'] and x['arm']=='control_favorite')
        money.append(f"| {r['basis']} | {r['arm']} | {r['bets']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} pp | {fav:+.2f} | {100*r['market_null']:.2f}% |")
    primary=next(x for x in comparisons if x['basis']=='2023-25' and x['arm']=='selected_all' and x['metric']=='primary_crps')
    sel=[x for x in selections if x['family']=='all']
    market=[]
    for basis,mask in bases[:3]:
        g=combined[mask&combined.arm.eq('selected_all')]
        market.append(dict(basis=basis,win_n=int(g.market_win_ll.notna().sum()),market_win_ll=float(g.market_win_ll.mean()),
            model_win_ll=float(g.win_ll.mean()),neutral_nonpush_cover_ll=float(np.log(2)),neutral_nonpush_total_ll=float(np.log(2)),
            note='Cover/total 0.5 is a neutral proxy; actual spread/total prices absent.'))
    dump(out/'market_controls.json',market)
    iteration_description=(
        'MC1: kernel widths (2/3,4/6,8/10), pseudo-games (20/80), neighbor counts (100/250), and two residual translations.'
        if experiment=='R003-MC1' else
        'MC2: direct kernel widths (1/2,2/3,4/6), pseudo-games (0/5), nearest 100/250 with pseudo-games (0/5). No translated candidate. This exploratory batch was specified after MC1 results; it is not an independent confirmation.')
    text=f'''# {experiment} — empirical market-context iterations

**Decision: {decision['recommendation']}.** Historical development, not fresh
confirmation or an executable-price result. Distributions contain only weighted
observed score pairs, or explicitly labeled market-relative translations.
There is no Gaussian component, support enumeration, rare-score penalty or
production-model feature. Signed spread and total are the two context inputs.

## Flat 1u moneyline returns (reported, never used for selection)

{chr(10).join(money)}

Ties push; market pick'ems and missing prices excluded identically across policies.
Full W-L-P, controls and paired week intervals are in moneyline.json. These returns
are not evidence of executable historical prices. No spread or total ROI is
computed because actual odds are absent.

## All fixed iterations and earlier-season selected policies, 2023–25

{chr(10).join(lines)}

Primary score = half the sum of margin and total empirical CRPS, in points.
Winner scores condition on decisive results; cover/total scores condition on
nonpush results. Ties and pushes are retained in distributions and audited.
Exact-score NLL is not scored: zero mass at unseen score pairs is not concealed
by a Gaussian or a probability floor. Wrong binary endpoint losses remain infinite.

Primary selected-policy gain versus original R003: **{primary['gain']:+.6f}**,
95% paired week interval **{primary['ci95']}**; 99.5% ten-candidate sensitivity
{primary['ci995']}. Bootstrap uses 10,000 whole-week draws within season, seed
20261016, without refitting forecasts or selection. These intervals do not remove
prior historical exposure or full adaptive research uncertainty. Every fixed arm,
including worse ones, remains reported. Fixed-arm/family intervals are descriptive.

## Selection, support and interpretation

Settings were fixed before candidate scoring in PROTOCOL.md. Annual selection
minimizes earlier-season primary CRPS only, with two OOF seasons required.
Selections: {[(x['target_season'],x['chosen']) for x in sel]}.
Candidate order resolves ties. Family-selected paths are reported separately.

{iteration_description}
Settings are fixed within each batch. MC1 results remain separately reported.
Global controls test whether localization helps.
Local ESS governs shrinkage into broader historical frequencies; uncertainty in
those frequencies is not itself a per-game predictive interval.

Residual atoms translate each observed pair by implied-team-point differences,
round half-up, and discard negative transformed scores with lost mass logged.
They are labeled synthetic translations of observations, not unmodified history.
Direct arms never drop or invent score pairs. No mirrored games inflate counts.

{notes}

Forecasting gates: {decision['gates']}. Any failed gate prevents advancement;
net profitability requires separate evidence regardless of forecast-score gains.
Compare winner probabilities with the actual no-vig moneyline in market_controls.json.
Neutral 0.5 spread/total controls are proxies, not recorded bookmaker probabilities.

## Files, integrity and reproduction

Per-game predictions include original prices/outcomes, configuration, source cutoff,
ESS, backoff fraction, removed residual mass, probabilities and scores. Full annual
metrics, coverage/width, reliability, stability, market controls, source/protocol
hashes and deterministic-repeat checks accompany this report. Historical quote
times are unknown; production forecasts, original research and ledgers are unchanged.

Run `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/market_context_empirical.py{' --refine-direct' if experiment=='R003-MC2' else ''}`.
For an independent repeat, copy PROTOCOL.md and registration_record.json into a
new separate directory under research/experiments and use --output-dir.
Use --forecast REQUEST.json with explicit --arm to reconstruct source atoms and
price supplied spread offers. No network, deployment, quote capture or wagering.
'''
    (out/'REPORT.md').write_text(text)
    dump(out/'reference_provenance.json',dict(path=str(reference_path.relative_to(j.ROOT)),sha256=j.sha256(reference_path)))


def decision_and_stability(f,comparisons,out,experiment='R003-MC1'):
    g=f[f.season.between(2023,2025)]
    b=g[g.arm.eq('reference_R003')].set_index('game_id')
    c=g[g.arm.eq('selected_all')].set_index('game_id').loc[b.index]
    delta=b.primary_crps-c.primary_crps
    annual=delta.groupby(b.season).mean()
    reference_global=g[g.arm.eq('global_direct')].set_index('game_id').loc[b.index]
    primary=next(x for x in comparisons if x['basis']=='2023-25' and x['arm']=='selected_all' and x['metric']=='primary_crps')
    ll_gains={m:float(b[m].mean()-c[m].mean()) for m in ['win_ll','cover_ll','over_ll']}
    gates=dict(practical_gain=primary['gain']>=.02,positive_interval=primary['ci95'][0]>0,
               annual_consistency=bool((annual>0).all()),better_than_global=bool(c.primary_crps.mean()<reference_global.primary_crps.mean()),
               event_scores=all(np.isfinite(x) and x>=-.002 for x in ll_gains.values()),integrity=True)
    weekly=pd.DataFrame(dict(s=b.season,w=b.week,d=delta)).groupby(['s','w']).d.agg(['sum','count'])
    loo=(delta.sum()-weekly['sum'])/(len(delta)-weekly['count'])
    stability=dict(annual_primary_gain={str(k):float(v) for k,v in annual.items()},
                   leave_one_season_out={str(y):float(delta[b.season!=y].mean()) for y in annual.index},
                   leave_one_week_range=[float(loo.min()),float(loo.max())],
                   influential_games={k:float(delta.loc[k]) for k in delta.abs().nlargest(10).index},
                   event_ll_gains=ll_gains)
    dump(out/'stability.json',stability)
    return dict(experiment=experiment,gates=gates,recommendation='retain for research' if all(gates.values()) else 'fails advancement gate',
                independent_validation=False,production_promotion=False), f'Annual selected-policy primary gains versus R003: {stability["annual_primary_gain"]}. Winner/cover/total LL gains: {ll_gains}.'


def evaluate_request(frame,request,arm):
    if not isinstance(request,dict) or set(request)!={'target','offers'}:
        raise ValueError('Request needs target and offers; outcomes are not accepted')
    target=request['target']
    fields={'game_id','season','week','spread_line','total_line'}
    if not isinstance(target,dict) or set(target)!=fields or not isinstance(target['game_id'],str):
        raise ValueError('Target needs only game identity, season/week, spread and total')
    if arm not in CONFIGS:raise ValueError('Choose an explicit fixed empirical arm')
    dist=forecast(frame,target,CONFIGS[arm]);margin=dist['home']-dist['away']
    support,inverse=np.unique(margin,return_inverse=True)
    pmf=np.bincount(inverse,weights=dist['weights'])
    decision=settlement.evaluate_offers(pmf,support,request['offers'])
    decision['policy']='R003-MC1-SPREAD-EV-v1'
    ph,pt,pa,pw=event(margin,0,dist['weights'])
    indices=np.argsort(-dist['weights'],kind='stable')[:20]
    return dict(arm=arm,game_id=target['game_id'],configuration=asdict(CONFIGS[arm]),
                p_home=ph,p_tie=pt,p_away=pa,p_home_non_tie=pw,
                implied_home=(target['total_line']+target['spread_line'])/2,
                implied_away=(target['total_line']-target['spread_line'])/2,
                source_audit=dist['audit'],top_comparables=[dict(game_id=str(dist['source_ids'][i]),
                weight=float(dist['weights'][i]),home_score=float(dist['home'][i]),away_score=float(dist['away'][i])) for i in indices],
                evidence='Research calculation; supplied prices/times not independently verified; no execution',**decision)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--input',type=Path,default=INPUT)
    parser.add_argument('--forecast',type=Path)
    parser.add_argument('--arm',choices=list(CONFIGS),default='direct_h4_t6_p80')
    parser.add_argument('--refine-direct',action='store_true',help='Run the separately specified MC2 direct localization batch')
    args=parser.parse_args(argv)
    if args.forecast:
        result=evaluate_request(load_inputs(args.input),json.loads(args.forecast.read_text()),args.arm)
        print(json.dumps(safe_json(result),indent=2,allow_nan=False))
    else:
        out=args.output_dir or (OUT.parent/'R003_market_context_refinement' if args.refine_direct else OUT)
        run(out,args.input,REFINEMENTS if args.refine_direct else CANDIDATES)


if __name__=='__main__':main()
