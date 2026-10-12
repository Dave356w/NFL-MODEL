"""Reproducible research-only joint outcomes and bootstrap model uncertainty."""
import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit

import context_shrinkage as s
import margin_total_models as t

m, ROOT = s.m, s.ROOT
OUT = ROOT / 'research/monte_carlo_results'
SEED = 20261012
ARMS = ['market', 'production', 'empirical', 'price_calibrated',
        'model_adjusted', 'feature_bootstrap', 'coefficient_bootstrap', 'combined']


def protected(path):
    path = Path(path).resolve()
    if any(path == p or p in path.parents for p in [ROOT/'data', ROOT/'public']):
        raise ValueError('Protected production output')
    return path


def prior(frame, year, week):
    ans = frame[m.before(frame, year, week)].copy()
    if len(ans) and not m.before(ans, year, week).all():
        raise ValueError('Future source')
    return ans


def score_projection(margin, total):
    """Coherent integer scores, including zero scores and ties."""
    home = np.maximum(np.rint((total+margin)/2), 0).astype(int)
    away = np.maximum(np.rint((total-margin)/2), 0).astype(int)
    return home-away, home+away


def event_features(margins, totals, row, win_q=None):
    mq = float(row.q if win_q is None else win_q)
    feats = [(margins > 0)-mq*(margins != 0)]
    # When replacing the win signal, do not also force the old spread price.
    if win_q is None:
        feats.append((margins > row.margin_line)-row.market_cover_q*(margins != row.margin_line))
    feats.append((totals > row.total_line)-row.market_over_q*(totals != row.total_line))
    return np.column_stack(feats)


def tilt(weights, features):
    """Minimum relative entropy reweighting to conditional price probabilities."""
    w = np.asarray(weights, float)
    if (w <= 0).any() or not np.isfinite(w).all():
        raise ValueError('Positive finite weights required')
    w = w/w.sum(); F = np.asarray(features, float)
    if not np.isfinite(F).all() or (F.min(axis=0)>0).any() or (F.max(axis=0)<0).any():
        raise ValueError('Price constraints outside empirical support')
    def objective(beta):
        v = F@beta; high = v.max(); z = w*np.exp(v-high); z /= z.sum()
        return high+np.log(np.sum(w*np.exp(v-high))), z@F
    fit = minimize(objective, np.zeros(F.shape[1]), jac=True, method='BFGS',
                   options={'gtol': 1e-10, 'maxiter': 500})
    v = F@fit.x; z = w*np.exp(v-v.max()); z /= z.sum()
    error = float(abs(z@F).max())
    if error > 1e-6:
        raise ValueError(f'Price constraints infeasible/not converged: {error}')
    return z, error


def conditional_probability(values, line, weights):
    nonpush = values != line
    mass = float(weights[nonpush].sum())
    if mass <= 0:
        raise ValueError('No non-push mass')
    return float(weights[values > line].sum()/mass), float(weights[~nonpush].sum())


def empirical_crps(values, weights, observed):
    order = np.argsort(values); x = np.asarray(values)[order]; w = np.asarray(weights)[order]
    before = np.cumsum(w)-w
    half_pair_distance = np.sum(w*x*(2*before+w-1))
    return float(np.sum(w*abs(x-observed))-half_pair_distance)


def quantile(values, weights, probs):
    ix = np.argsort(values); cdf = np.cumsum(weights[ix]); cdf[-1] = 1.
    return np.asarray(values)[ix[np.searchsorted(cdf, probs)]]


def bootstrap_coefficients(train, fitted, year, week, draws, rng):
    names = fitted['names']; scale = np.asarray(fitted['scale'])
    X = train[names].to_numpy(float)/scale
    y = train['home won'].to_numpy(); base = logit(train.q.to_numpy())
    age = ((year-train.season.to_numpy())*19+week-train.week.to_numpy())/(19*m.FIT_HALF_LIFE_SEASONS)
    original_w = np.exp2(-age)
    groups = pd.factorize(pd.MultiIndex.from_arrays([train.season, train.week]))[0]
    pen = np.full(X.shape[1], .1); pen[0] = .01
    betas = []
    for _ in range(draws):
        w = original_w*rng.exponential(size=groups.max()+1)[groups]; w /= w.sum()
        def obj(beta):
            eta = base+X@beta
            return np.sum(w*(np.logaddexp(0, eta)-y*eta))+.5*np.sum(pen*beta**2), X.T@(w*(expit(eta)-y))+pen*beta
        opt = minimize(obj, np.asarray(fitted['beta']), jac=True, method='L-BFGS-B',
                       options={'gtol': 1e-8, 'ftol': 1e-12, 'maxiter': 500})
        if not np.isfinite(opt.fun) or abs(obj(opt.x)[1]).max() > 2e-5:
            raise RuntimeError('Bootstrap coefficient fit failed')
        betas.append(opt.x)
    return np.asarray(betas)


def pass_terms(z):
    z = np.asarray(z)
    out = [z[:, 0]*z[:, 1]-z[:, 2]*z[:, 3]]
    for a in [1., -1.]:
        for b in [1., -1.]:
            out.append(np.maximum(a*z[:, 0]-1, 0)*np.maximum(b*z[:, 1]-1, 0)
                       -np.maximum(a*z[:, 2]-1, 0)*np.maximum(b*z[:, 3]-1, 0))
    return np.column_stack(out)


def profiles(history, team, year, multipliers):
    """Joint team-game Bayesian bootstrap; fixed priors and original time weights."""
    h = history[history.team == team].sort_values(['season','week','game_id'])
    game_idx = h['_game_index'].to_numpy(int)
    ix = {c: i for i, c in enumerate(m.COUNTS)}
    league = history[list(m.COUNTS)].to_numpy(float)
    answer = {}
    for half in [8., 16.]:
        base = np.exp2(-np.arange(len(h)-1, -1, -1)/half)*np.power(.5, year-h.season.to_numpy())
        W = multipliers[:, game_idx]*base
        # First row has unit multipliers and is the reconstructed point profile.
        for role, cols in [('for', list(m.COUNTS)), ('allowed', ['opp_'+c for c in m.COUNTS])]:
            vals = h[cols].to_numpy(float)
            for metric, (num, den, mult) in m.RATES_CORE.items():
                a = vals[:, ix[num]]; b = np.ones(len(h)) if den is None else vals[:, ix[den]]
                la = league[:, ix[num]]; lb = np.ones(len(league)) if den is None else league[:, ix[den]]
                good = np.isfinite(a)&np.isfinite(b)&(b > 0)
                lg = np.isfinite(la)&np.isfinite(lb)&(lb > 0)
                numerator = W[:, good]@a[good]+4*la[lg].mean()
                denominator = W[:, good]@b[good]+4*lb[lg].mean()
                answer[(half, role, metric)] = mult*numerator/denominator
        for peak in m.PEAK_COLUMNS:
            answer[(half, peak)] = (W@h[peak].to_numpy())/(W.sum(axis=1)+4)
    return answer, len(h)


def feature_draws(row, history, multiplier, reference, names):
    hp, hn = profiles(history, row.home, int(row.season), multiplier)
    ap, an = profiles(history, row.away, int(row.season), multiplier)
    X = np.tile(row[names].to_numpy(float), (len(multiplier), 1))
    for j, name in enumerate(names):
        if name.startswith('d__for__') or name.startswith('d__allowed__'):
            _, role, _, metric = name.split('__'); v = hp[(8., role, metric)]-ap[(8., role, metric)]
            X[:, j] += v-v[0]
        elif name in m.PEAK_FEATURES:
            key = name.split('__')[1]; v = hp[(8., key)]-ap[(8., key)]
            X[:, j] += v-v[0]
    z = []
    for team, role in [(hp,'for'), (ap,'allowed'), (ap,'for'), (hp,'allowed')]:
        mu, sd = reference[role]
        z.append((team[(16., role, 'net_pass_yards_per_pass_play')]-mu)/sd)
    context = pass_terms(np.column_stack(z))
    for j, name in enumerate(s.CONTEXTS):
        X[:, names.index(name)] += context[:, j]-context[0, j]
    if not np.isfinite(X).all():
        raise ValueError('Invalid bootstrap features')
    return X[1:], min(hn, an)


def prepare_boxes(out):
    import nflreadpy as nfl
    out = protected(out); out.mkdir(parents=True, exist_ok=True)
    m.CACHE_DIR = str(out/'cache'); m.UPSTREAM_RETRIES = 2
    schedules = nfl.load_schedules(list(range(2019,2026))).to_pandas()
    schedules = m.normalize_teams(schedules[schedules.game_type == 'REG'].copy())
    schedules['home won'] = schedules.result.map(m.won)
    schedules['site'] = np.where(schedules.location.str.lower() == 'neutral', 0., 1.)
    from scipy.special import ndtr
    schedules['market WP'] = ndtr(schedules.spread_line/m.MARKET_SIGMA)
    schedules.to_csv(out/'schedule.csv', index=False)
    parts = []
    for year in range(2019,2026):
        b, _ = m.load_boxes(year, schedules[schedules.season == year])
        parts.append(b); print(f'Boxes ready {year}', flush=True)
    pd.concat(parts).to_csv(out/'boxes.csv.gz', index=False, compression={'method':'gzip','mtime':0})


def summarize(held, distributions, out):
    y = held['home won'].to_numpy(); binary = np.isin(y, [0.,1.])
    groups = (held.season.astype(str)+'_'+held.week.astype(str)).to_numpy()
    bets = {a: m.flat_bets(held, a) for a in ARMS}
    common = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    result = {'basis':'Exposed historical development, 2023–2025; unknown historical quote capture times',
              'common_bets':int(common.sum()), 'binary_games':int(binary.sum()), 'arms':[], 'comparisons':[], 'annual':[]}
    calibration = []
    for arm in ARMS:
        prob = held[arm].to_numpy(); ll = s.loss(y, prob)
        result['arms'].append({'arm':arm, **m.roi_summary(bets[arm].loc[common]),
                              'log_loss':float(ll[binary].mean()), 'brier':float(((prob-y)**2)[binary].mean())})
        for year in sorted(held.season.unique()):
            mask = (held.season == year).to_numpy()
            result['annual'].append({'arm':arm,'season':int(year), **m.roi_summary(bets[arm].loc[mask&common]),
                                     'log_loss':float(ll[mask&binary].mean())})
        for lo in np.arange(0,1,.1):
            mask = binary&(prob >= lo)&(prob < lo+.1)
            if mask.any(): calibration.append({'arm':arm,'lower':lo,'n':int(mask.sum()),
                                               'probability':float(prob[mask].mean()),'frequency':float(y[mask].mean())})
        if arm not in ['market','production']:
            for comparator in ['market','production']:
                delta = (bets[arm].units-bets[comparator].units).to_numpy()[common]
                gain = (s.loss(y, held[comparator])-ll)[binary]
                result['comparisons'].append({'arm':arm,'comparator':comparator,'roi_gain':float(delta.mean()),
                    'roi_ci95':s.p.cluster_interval(delta,groups[common],.95),
                    'll_gain':float(gain.mean()),'ll_ci95':s.p.cluster_interval(gain,groups[binary],.95),
                    'll_family_ci':s.p.cluster_interval(gain,groups[binary],1-.05/12)})
    ds = pd.DataFrame(distributions); summaries = []
    for (arm,target), g in ds.groupby(['arm','target']):
        nonpush=g.observed!=g.line
        summaries.append({'arm':arm,'target':target,'n':len(g),'crps':float(g.crps.mean()),
                          'event_games':int(nonpush.sum()),
                          'event_log_loss':float(s.loss((g.observed>g.line).to_numpy(float),g.event_probability)[nonpush].mean()),
                          'event_brier':float(((g.event_probability-(g.observed>g.line))**2)[nonpush].mean()),
                          **{c:float(g[c].mean()) for c in ['coverage50','coverage80','coverage90','width90','push_probability','tail_probability']}})
    result['distributions'] = summaries
    result['distribution_comparisons'] = []
    result['uncertainty'] = []
    for arm in ['empirical','feature_bootstrap','coefficient_bootstrap','combined']:
        result['uncertainty'].append({'arm':arm,'average_probability_sd':float(held[arm+'_sd'].mean()),
             'average_p05_p95_width':float((held[arm+'_p95']-held[arm+'_p05']).mean()),
             'crosses_half':int(((held[arm+'_p05']<.5)&(held[arm+'_p95']>.5)).sum())})
    for target in ['margin','total']:
        z = ds[ds.target == target].pivot(index='game_id',columns='arm',values='crps')
        gg = held.set_index('game_id').loc[z.index]; group = (gg.season.astype(str)+'_'+gg.week.astype(str)).to_numpy()
        for arm in ['empirical','price_calibrated','model_adjusted']:
            gain = z.gaussian_market-z[arm]
            result['distribution_comparisons'].append({'arm':arm,'target':target,'crps_gain':float(gain.mean()),
                'ci95':s.p.cluster_interval(gain,group,.95),'family_ci':s.p.cluster_interval(gain,group,1-.05/6)})
    ds.to_csv(out/'distribution_predictions.csv',index=False)
    pd.DataFrame(calibration).to_csv(out/'calibration_bins.csv',index=False)
    return result


def run(args):
    out = protected(args.output_dir); out.mkdir(parents=True,exist_ok=True)
    inputs = ROOT/'research/monte_carlo_inputs'
    if args.prepare_boxes:
        prepare_boxes(inputs); return
    features_path = ROOT/'research/shrinkage_results/frozen_training_features.csv.gz'
    forecast_path = ROOT/'research/market_residual_results/weekly_market_forecasts.csv.gz'
    f = pd.read_csv(features_path); forecasts = pd.read_csv(forecast_path)
    t.validate_oof(forecasts)
    boxes = pd.read_csv(inputs/'boxes.csv.gz'); schedules = pd.read_csv(inputs/'schedule.csv')
    saved = m.ADJUSTED_FAMILIES
    try:
        m.ADJUSTED_FAMILIES = {}; raw16 = m.lagged_features(boxes,schedules,16.)
    finally:
        m.ADJUSTED_FAMILIES = saved
    opp = boxes[['game_id','team',*m.COUNTS]].rename(columns={'team':'opponent',**{c:'opp_'+c for c in m.COUNTS}})
    boxes = boxes.merge(opp,on=['game_id','opponent'],validate='one_to_one')
    eligible = f.ready&f['home won'].isin([0.,1.])&np.isfinite(f.q)&np.isfinite(f[s.CONTEXTS]).all(axis=1)
    ev = f.ready&f['home won'].isin([0.,.5,1.])&f.season.between(2023,2025)&np.isfinite(f.q)&np.isfinite(f[s.CONTEXTS]).all(axis=1)
    held = f[ev].merge(forecasts,on='game_id',suffixes=('','_forecast'),validate='one_to_one')
    full_n = int(ev.sum()); held = held.reset_index(drop=True)
    refs = pd.read_csv(ROOT/'research/production_adoption_results/historical_reproduction.csv').set_index('game_id')
    rng = np.random.default_rng(args.seed); audit=[]; distributions=[]; feature_audit=[]; coefficients=[]; coefficient_audit=[]
    for (year,week), g in held.groupby(['season','week'],sort=True):
        year,week=int(year),int(week)
        train = prior(f[eligible],year,week); fit=s.fit(train,year,week)
        base_prob = s.predict(g,fit); held.loc[g.index,'production']=base_prob
        held.loc[g.index,'market']=g.q.to_numpy()
        betas=bootstrap_coefficients(train,fit,year,week,args.coefficient_draws,rng)
        coefficient_audit.extend({'season':year,'week':week,'feature':name,'point':fit['beta'][j],
                                  'bootstrap_sd':float(betas[:,j].std(ddof=1))} for j,name in enumerate(fit['names']))
        hist=prior(boxes,year,week);hist=hist[hist.season>=year-3].copy()
        hist['_game_index']=pd.factorize(hist.game_id)[0]
        multiplier=np.vstack([np.ones(hist._game_index.max()+1),rng.exponential(size=(args.feature_draws,hist._game_index.max()+1))])
        ref=prior(raw16,year,week);ref=ref[ref.season>=year-4];cur=ref[ref.season==year]
        if cur.empty:cur=ref[ref.season==year-1]
        reference={}
        for role in ['for','allowed']:
            cols=[f'{side}__{role}__rates_core__net_pass_yards_per_pass_play' for side in ['home','away']]
            reference[role]=(float(np.nanmean(cur[cols])),float(np.nanstd(ref[cols],ddof=1)))
        errors=prior(forecasts,year,week)
        error_groups=pd.factorize(pd.MultiIndex.from_arrays([errors.season,errors.week]))[0]
        error_multipliers=rng.exponential(size=(args.feature_draws,error_groups.max()+1))[:,error_groups]
        residual=np.column_stack([errors[target]-errors[f'{target}__market_relationships__mean'] for target in ['margin','total']])
        age=((year-errors.season.to_numpy())*19+week-errors.week.to_numpy())/38.
        max_mc_difference=0.; max_constraint_error=0.
        for ix,row in g.iterrows():
            rawdraw,n_history=feature_draws(row,hist,multiplier,reference,fit['names'])
            scaled=rawdraw/np.asarray(fit['scale']); base=logit(row.q); beta=np.asarray(fit['beta'])
            fp=expit(base+scaled@beta)
            cp=expit(base+(row[fit['names']].to_numpy(float)/np.asarray(fit['scale']))@betas.T)
            bp=expit(base+np.sum(scaled*betas[np.arange(len(scaled))%len(betas)],axis=1))
            for arm,draw in [('feature_bootstrap',fp),('coefficient_bootstrap',cp),('combined',bp)]:
                held.loc[ix,arm]=draw.mean()
                for label,value in [('p05',np.quantile(draw,.05)),('p95',np.quantile(draw,.95)),('sd',draw.std(ddof=1))]:held.loc[ix,arm+'_'+label]=value
            for j,name in enumerate(fit['names']):
                feature_audit.append({'game_id':row.game_id,'feature':name,'point':row[name],
                    'bootstrap_sd':float(rawdraw[:,j].std(ddof=1)),
                    'p05':float(np.quantile(rawdraw[:,j],.05)),'p95':float(np.quantile(rawdraw[:,j],.95))})
            covariance=np.cov(rawdraw,rowvar=False)
            # Full feature covariance retained as JSON, rather than discarded for independent sampling.
            coefficients.append({'game_id':row.game_id,'feature_names':fit['names'],'feature_covariance':covariance.tolist()})
            distance=((errors.margin_line.to_numpy()-row.margin_line)/7)**2+((errors.total_line.to_numpy()-row.total_line)/10)**2
            w=np.exp2(-age)*np.exp(-.5*np.minimum(distance,60));w/=w.sum()
            margins,totals=score_projection(row.margin__market_relationships__mean+residual[:,0],row.total__market_relationships__mean+residual[:,1])
            ew=error_multipliers*w
            ep=(ew[:,margins>0].sum(axis=1)/ew[:,margins!=0].sum(axis=1))
            for label,value in [('p05',np.quantile(ep,.05)),('p95',np.quantile(ep,.95)),('sd',ep.std(ddof=1))]:held.loc[ix,'empirical_'+label]=value
            calibrated,e1=tilt(w,event_features(margins,totals,row))
            adjusted,e2=tilt(w,event_features(margins,totals,row,float(held.loc[ix,'production'])))
            max_constraint_error=max(max_constraint_error,e1,e2)
            for arm,weights in [('empirical',w),('price_calibrated',calibrated),('model_adjusted',adjusted)]:
                prob,tie=conditional_probability(margins,0,weights)
                # Price-constrained arms use their exact targets, avoiding floating-point pick'em flips.
                held.loc[ix,arm]=row.q if arm=='price_calibrated' else (held.loc[ix,'production'] if arm=='model_adjusted' else prob)
                held.loc[ix,arm+'_tie']=tie
                effective=1/np.sum(weights**2);held.loc[ix,arm+'_effective_residuals']=effective
                # Exact weighted probabilities are used for scoring; draws verify Monte Carlo approximation.
                draw=rng.choice(len(weights),args.outcome_draws,p=weights)
                other=np.random.default_rng(args.seed+1+int(ix)).choice(len(weights),args.outcome_draws,p=weights)
                for seedlabel,indices in [('mc',draw),('mc_second',other)]:
                    estimate=(margins[indices]>0).sum()/max((margins[indices]!=0).sum(),1)
                    held.loc[ix,arm+'_'+seedlabel]=estimate
                    max_mc_difference=max(max_mc_difference,abs(estimate-prob))
                for target,values in [('margin',margins),('total',totals)]:
                    obs=row[target];line=row[target+'_line'];event,push=conditional_probability(values,line,weights)
                    record={'game_id':row.game_id,'season':year,'week':week,'arm':arm,'target':target,
                            'observed':float(obs),'line':float(line),
                            'mean':float(weights@values),'sd':float(np.sqrt(weights@((values-weights@values)**2))),
                            'margin_total_correlation':float((weights@((margins-weights@margins)*(totals-weights@totals)))/np.sqrt((weights@((margins-weights@margins)**2))*(weights@((totals-weights@totals)**2)))),
                            'crps':empirical_crps(values,weights,obs),'event_probability':event,'push_probability':push,
                            'tail_probability':float(weights[(abs(values)>=21) if target=='margin' else (values>=60)].sum())}
                    for level in [.5,.8,.9]:
                        lo,hi=quantile(values,weights,[(1-level)/2,(1+level)/2]);record[f'coverage{int(level*100)}']=float(lo<=obs<=hi)
                        if level==.9:record['width90']=float(hi-lo)
                    distributions.append(record)
            for target in ['margin','total']:
                mu=row[f'{target}__market_relationships__mean'];sd=row[f'{target}__market_relationships__sd'];obs=row[target]
                from scipy.stats import norm
                event,push=t.event_prob(np.array([mu]),np.array([sd]),np.array([row[target+'_line']]))
                record={'game_id':row.game_id,'season':year,'week':week,'arm':'gaussian_market','target':target,
                        'observed':float(obs),'line':float(row[target+'_line']),'mean':float(mu),'sd':float(sd),'margin_total_correlation':np.nan,
                        'crps':float(t.crps(obs,mu,sd)),'event_probability':float(event[0]),'push_probability':float(push[0]),
                        'tail_probability':float(norm.cdf((-21-mu)/sd)+norm.sf((21-mu)/sd) if target=='margin' else norm.sf((60-mu)/sd))}
                for level in [.5,.8,.9]:
                    width=norm.ppf((1+level)/2)*sd;record[f'coverage{int(level*100)}']=float(abs(obs-mu)<=width)
                    if level==.9:record['width90']=float(2*width)
                distributions.append(record)
        audit.append({'season':year,'week':week,'training_games':len(train),'error_games':len(errors),
                      'training_max_season':int(train.season.max()),'training_max_week':int(train[train.season==train.season.max()].week.max()),
                      'errors_max_season':int(errors.season.max()),'errors_max_week':int(errors[errors.season==errors.season.max()].week.max()),
                      'boxes_max_season':int(hist.season.max()),'boxes_max_week':int(hist[hist.season==hist.season.max()].week.max()),
                      'max_price_constraint_error':max_constraint_error,'max_mc_error':max_mc_difference})
        print(f'Completed {year} week {week}: {len(g)} games',flush=True)
    err=float(abs(held.production.to_numpy()-refs.loc[held.game_id,'production_probability'].to_numpy()).max())
    if err>1e-7:raise ValueError('Production reproduction failed')
    for arm in ARMS:
        held.loc[np.isclose(held[arm],.5,atol=1e-12,rtol=0),arm]=.5
    if not np.isfinite(held[ARMS]).all().all():raise ValueError('Incomplete predictions')
    result=summarize(held,distributions,out)
    result.update({'seed':args.seed,'feature_draws':args.feature_draws,'coefficient_draws':args.coefficient_draws,
                   'outcome_draws':args.outcome_draws,'production_max_error':err,'eligible_win_games':full_n,
                   'excluded_missing_target_prices':full_n-len(held),'evaluated_games':len(held),
                   'minimum_effective_residuals':float(held[[a+'_effective_residuals' for a in ARMS[2:5]]].min().min()),
                   'monte_carlo_mean_absolute_error':float(np.mean([abs(held[a+'_mc']-held[a]).mean() for a in ARMS[2:5]]))})
    held.to_csv(out/'heldout_predictions.csv',index=False)
    pd.DataFrame(audit).to_csv(out/'cutoff_audit.csv',index=False)
    pd.DataFrame(feature_audit).to_csv(out/'feature_uncertainty.csv',index=False)
    pd.DataFrame(coefficient_audit).to_csv(out/'coefficient_uncertainty.csv',index=False)
    (out/'feature_covariance.jsonl.gz').write_bytes(gzip.compress(''.join(json.dumps(x)+'\n' for x in coefficients).encode(),mtime=0))
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    sources=[Path(__file__),ROOT/'research/MONTE_CARLO.md',features_path,forecast_path,inputs/'boxes.csv.gz',inputs/'schedule.csv',ROOT/'nfl_model.py']
    (out/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},indent=2)+'\n')
    write_report(result,out)


def write_report(r,out):
    lines=['# NFL Monte Carlo simulation results','',
           '**Finding:** the simulations add useful outcome ranges and sensitivity measurements, but no challenger establishes improved predictive accuracy. Keep production unchanged.',
           '',r['basis']+'. No production changes or native forward claims.',
           f"\n{r['evaluated_games']} common priced games; {r['common_bets']} common historical flat-unit observations; {r['binary_games']} binary win scores.",
           '\n| Arm | Units | Historical ROI ± SE | Market-null ROI | Log loss ↓ | Brier ↓ |',
           '|---|---:|---:|---:|---:|---:|']
    for x in r['arms']:lines.append(f"| {x['arm']} | {x['units']:+.2f} | {100*x['roi']:+.2f}% ± {100*x['roi_se']:.2f} | {100*x['null_roi']:+.2f}% | {x['log_loss']:.6f} | {x['brier']:.6f} |")
    lines+=['','## Paired probability comparisons','','Positive gain means lower challenger loss. Family intervals correct for 12 comparisons. They do not account for earlier design exploration.','','| Challenger | Comparator | LL gain | 95% interval | Family interval |','|---|---|---:|---|---|']
    for x in r['comparisons']:lines.append(f"| {x['arm']} | {x['comparator']} | {x['ll_gain']:+.6f} | {x['ll_ci95']} | {x['ll_family_ci']} |")
    lines+=['','## Uncertainty in estimated probabilities','','Ranges below describe conditional bootstrap sensitivity; they are separate from outcome prediction intervals and Monte Carlo numerical error. Market empirical ranges hold fitted target centers fixed.','','| Arm | Average probability SD, pp | Average 5–95% width, pp | Ranges crossing 50% |','|---|---:|---:|---:|']
    for x in r['uncertainty']:lines.append(f"| {x['arm']} | {100*x['average_probability_sd']:.2f} | {100*x['average_p05_p95_width']:.2f} | {x['crosses_half']} |")
    lines+=['','## Outcome distributions','','Tail = absolute margin ≥21 or total ≥60. Intervals are central prediction intervals; discrete boundaries can overcover.','','| Arm | Target | CRPS ↓ | 50% coverage | 80% coverage | 90% coverage | 90% width |','|---|---|---:|---:|---:|---:|---:|']
    for x in r['distributions']:lines.append(f"| {x['arm']} | {x['target']} | {x['crps']:.3f} | {100*x['coverage50']:.1f}% | {100*x['coverage80']:.1f}% | {100*x['coverage90']:.1f}% | {x['width90']:.1f} |")
    lines+=['','## Paired distribution comparisons','','Against prior-week Gaussian market relationship forecast. Positive CRPS gain means improvement.','','| Arm | Target | CRPS gain | 95% interval | Family interval |','|---|---|---:|---|---|']
    for x in r['distribution_comparisons']:lines.append(f"| {x['arm']} | {x['target']} | {x['crps_gain']:+.4f} | {x['ci95']} | {x['family_ci']} |")
    lines+=['','## Spread/total probability scores','','Pushes excluded from conditional binary scores.','','| Arm | Target | Non-push games | Event log loss ↓ | Event Brier ↓ |','|---|---|---:|---:|---:|']
    for x in r['distributions']:lines.append(f"| {x['arm']} | {x['target']} | {x['event_games']} | {x['event_log_loss']:.6f} | {x['event_brier']:.6f} |")
    lines+=['','## By season','','| Arm | Year | Units | Historical ROI | Log loss ↓ |','|---|---:|---:|---:|---:|']
    for x in r['annual']:lines.append(f"| {x['arm']} | {x['season']} | {x['units']:+.2f} | {100*x['roi']:+.2f}% | {x['log_loss']:.6f} |")
    lines+=['','## Numerical and source checks','',f"- Exact production reproduction: maximum probability error {r['production_max_error']:.3g}.",
            f"- Draws: {r['feature_draws']} feature / {r['coefficient_draws']} coefficient / {r['outcome_draws']} outcomes, seed {r['seed']}.",
            f"- Outcome draw mean absolute probability error: {100*r['monte_carlo_mean_absolute_error']:.3f} percentage points. Exact weighted probabilities score the candidates.",
            f"- Minimum effective residual sample size: {r['minimum_effective_residuals']:.1f}.",
            f"- Missing target-price exclusions: {r['excluded_missing_target_prices']} of {r['eligible_win_games']} eligible win games.",
            '- Price-calibrated simulations reproduce the supplied moneyline by construction; model-adjusted simulations reproduce production by construction. Neither provides an independent new win signal.',
            '- Model-adjusted scores constrain win and total probabilities; spread probabilities are allowed to change with the win signal.',
            '- Availability and normalization reference uncertainty are held fixed. Feature bootstrap ranges are conditional sensitivity intervals, not validated confidence intervals.',
            '- Whole games preserve within-game relationships; Bayesian multipliers measure profile estimation uncertainty, not future-game randomness. Historical regime shifts are not explicitly modelled.',
            '- Integer score projection preserves parity and nonnegative scores, but is not a drive simulation and does not guarantee exact football key-number mass.',
            '- Unknown quote timing and reconstructed upstream boxes limit historical interpretation. Recentered profile deviations preserve archived baseline inputs.',
            '- Input hashes, full covariance matrices, per-feature SDs, annual summaries, calibration bins and source cutoffs are provided alongside this report.',
            '- No historical winner is automatically adopted. A new forward experiment is required before making a production change.','']
    (out/'REPORT.md').write_text('\n'.join(lines))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare-boxes',action='store_true')
    parser.add_argument('--output-dir',type=Path,default=OUT)
    parser.add_argument('--feature-draws',type=int,default=256)
    parser.add_argument('--coefficient-draws',type=int,default=64)
    parser.add_argument('--outcome-draws',type=int,default=8192)
    parser.add_argument('--seed',type=int,default=SEED)
    args=parser.parse_args()
    if min(args.feature_draws,args.coefficient_draws,args.outcome_draws)<2:parser.error('At least two draws required')
    run(args)
