"""Direct margin/total distributions and leakage-safe production interactions."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import ndtr,expit,logit
from scipy.stats import norm
import context_shrinkage as s
m,p,ROOT=s.m,s.p,s.ROOT
TARGETS=('margin','total')
DISTRIBUTIONS=('market_centered','corrected','standalone')
PRIMARY_STACKS=('production_matched','forecast_additive','margin_total','pass_total')
STACKS=PRIMARY_STACKS+('pass_market_total',)
EXTRAS={'production_matched':[],'forecast_additive':['margin_edge','total_homefield'],
        'margin_total':['margin_edge','total_homefield','margin_total_interaction'],
        'pass_total':['margin_edge','total_homefield','pass_total_interaction'],
        'pass_market_total':['margin_edge','market_total_homefield','pass_market_total_interaction']}
MARGIN_NAMES=m.feature_names(s.q.BASE_FAMILY)+s.CONTEXTS


def weights(frame,year,week):
    if not m.before(frame,year,week).all():raise ValueError('Current/future training')
    age=((year-frame.season.to_numpy())*19+week-frame.week.to_numpy())/(19*m.FIT_HALF_LIFE_SEASONS)
    w=np.exp2(-age);return w/w.sum()


def normal_bin(y,mu,sd):
    y,mu,sd=np.asarray(y),np.asarray(mu),np.asarray(sd)
    if np.any(sd<=0) or not np.isfinite(sd).all():raise ValueError('Invalid dispersion')
    lo=(y-.5-mu)/sd;hi=(y+.5-mu)/sd
    # Survival function avoids catastrophic cancellation in the upper tail.
    return np.maximum(np.where(lo>0,ndtr(-lo)-ndtr(-hi),ndtr(hi)-ndtr(lo)),1e-15)


def event_prob(mu,sd,line):
    line=np.asarray(line,float);integer=np.isclose(line,np.round(line),atol=1e-10,rtol=0)
    # Integer outcomes exceeding noninteger lines start at floor(line)+1.
    lower=np.where(integer,line-.5,np.floor(line)+.5)
    upper=np.where(integer,line+.5,np.floor(line)+.5)
    below=ndtr((lower-mu)/sd);above=ndtr((mu-upper)/sd)
    push=np.where(integer,1-below-above,0.)
    return above/np.maximum(above+below,1e-15),push


def crps(y,mu,sd):
    z=(np.asarray(y)-mu)/sd
    return sd*(z*(2*ndtr(z)-1)+2*norm.pdf(z)-1/np.sqrt(np.pi))


def price_probability(first,second):
    first,second=np.asarray(first,float),np.asarray(second,float)
    def implied(x):
        with np.errstate(divide='ignore',invalid='ignore'):
            return np.where(x<0,-x/(-x+100),100/(x+100))
    a,b=implied(first),implied(second)
    valid=np.isfinite(first)&np.isfinite(second)&(abs(first)>=100)&(abs(second)>=100)
    return np.where(valid,a/(a+b),np.nan)


def fit_mean(train,test,target,names,arm):
    year,week=int(test.season.iloc[0]),int(test.week.iloc[0])
    t=train[np.isfinite(train[target])&np.isfinite(train[target+'_line'])&train.ready].copy()
    if len(t)<m.MIN_TRAIN_GAMES:raise ValueError('Insufficient target training')
    w=weights(t,year,week)
    if arm=='market_centered':return test[target+'_line'].to_numpy(float),{'training_games':len(t),'center_only':True}
    raw=np.nan_to_num(t[names].to_numpy(float),nan=0.,posinf=0.,neginf=0.)
    mu=w@raw;scale=np.sqrt(w@((raw-mu)**2));scale[scale<1e-8]=1.
    X=np.column_stack([np.ones(len(t)),raw/scale]);T=np.column_stack([np.ones(len(test)),np.nan_to_num(test[names].to_numpy(float),nan=0.,posinf=0.,neginf=0.)/scale])
    offset=t[target+'_line'].to_numpy() if arm=='corrected' else np.zeros(len(t))
    y=(t[target].to_numpy()-offset)/10.;pen=np.r_[0.,np.full(len(names),.1)]
    beta=np.linalg.solve(X.T@(w[:,None]*X)+np.diag(pen),X.T@(w*y))
    base=test[target+'_line'].to_numpy() if arm=='corrected' else np.zeros(len(test))
    return base+10*(T@beta),{'training_games':len(t),'names':['intercept',*names],'scale':scale.tolist(),'beta':beta.tolist()}


def dispersion(earlier,train,target,arm,year,week):
    col=f'{target}__{arm}__mean'
    if len(earlier) and col in earlier:
        t=earlier[np.isfinite(earlier[col])&np.isfinite(earlier[target])].copy()
    else:t=pd.DataFrame()
    if len(t)>=80:
        residual=t[target].to_numpy()-t[col].to_numpy();source='prior_weekly_forecast_errors'
    else:
        t=train[train.ready&np.isfinite(train[target])&np.isfinite(train[target+'_line'])].copy()
        residual=t[target].to_numpy()-t[target+'_line'].to_numpy();source='prior_market_residual_fallback'
    w=weights(t,year,week);sigma=max(float(np.sqrt(w@(residual*residual))),3.)
    return sigma,{'dispersion_source':source,'dispersion_games':len(t),'dispersion_max_season':int(t.season.max()),'dispersion_max_week':int(t[t.season==t.season.max()].week.max())}


def stack_features(frame):
    f=frame.copy();f['margin_edge']=(f.margin__corrected__mean-f.margin_line)/10.
    f['total_context']=(f.total__corrected__mean-45.)/10.
    f['total_homefield']=f.site*f.total_context
    f['margin_total_interaction']=f.margin_edge*f.total_context
    f['pass_total_interaction']=f.pass_product*f.total_context
    f['market_total_context']=(f.total_line-45.)/10.
    f['market_total_homefield']=f.site*f.market_total_context
    f['pass_market_total_interaction']=f.pass_product*f.market_total_context
    return f


def validate_oof(frame):
    required=['stage1_through_season','stage1_through_week','season','week']
    if not set(required)<=set(frame):raise ValueError('Missing OOF cutoff metadata')
    if not np.isfinite(frame[required]).all().all():raise ValueError('Missing OOF cutoff')
    prior=(frame.stage1_through_season<frame.season)|((frame.stage1_through_season==frame.season)&(frame.stage1_through_week<frame.week))
    if not prior.all():raise ValueError('Forecast fit includes its own/future outcome')


def stack_fit(train,test,arm):
    year,week=int(test.season.iloc[0]),int(test.week.iloc[0]);names=MARGIN_NAMES+EXTRAS[arm]
    validate_oof(train)
    if not m.before(train,year,week).all():raise ValueError('Future stack training')
    if len(train)<m.MIN_TRAIN_GAMES:raise ValueError('Insufficient stack training')
    # Exact production feature/penalty math on the matched OOF cohort.
    w=weights(train,year,week);raw=np.nan_to_num(train[names].to_numpy(float),nan=0.,posinf=0.,neginf=0.)
    mu=w@raw;scale=np.sqrt(w@((raw-mu)**2));scale[scale<1e-8]=1.;scale[0]=1.
    X=raw/scale;pen=np.full(len(names),.1);pen[0]=.01
    base=logit(np.clip(train.q.to_numpy(),1e-5,1-1e-5));y=train['home won'].to_numpy()
    def obj(beta):
        eta=base+X@beta
        return np.sum(w*(np.logaddexp(0,eta)-y*eta))+.5*np.sum(pen*beta**2),X.T@(w*(expit(eta)-y))+pen*beta
    beta=m.checked_optimize(obj,len(names));fit={'names':names,'scale':scale.tolist(),'beta':beta.tolist(),'market_offset':True,'training_games':len(train)}
    return s.predict(test,fit),fit


def prepare_pack(out):
    path=out/'frozen_feature_prices.csv.gz'
    if path.exists():return pd.read_csv(path)
    cache=ROOT/'.nfl_cache/shrinkage_inputs';schedule=pd.read_csv(cache/'schedule.csv');box=pd.read_csv(cache/'boxes.csv');av=pd.read_pickle(cache/'availability.pkl')
    # Unused adjusted families are expensive; exclude only their independent construction.
    saved=m.ADJUSTED_FAMILIES
    try:
        m.ADJUSTED_FAMILIES={};raw=m.lagged_features(box,schedule,8.,av)
    finally:m.ADJUSTED_FAMILIES=saved
    f=pd.read_csv(ROOT/'research/shrinkage_results/frozen_training_features.csv.gz')
    if raw.game_id.tolist()!=f.game_id.tolist():raise ValueError('Feature alignment')
    total_names=[]
    for role in ('for','allowed'):
        for metric in m.FAMILIES['rates_core']:
            if metric=='sacks_taken_pct':continue
            c=f'sum__{role}__{metric}';f[c]=raw[f'home__{role}__rates_core__{metric}']+raw[f'away__{role}__rates_core__{metric}'];total_names.append(c)
    for c in m.AVAIL_FAMILY_COLS[s.q.BASE_FAMILY]:
        name='sum__avail__'+c;f[name]=raw['home__avail__'+c]+raw['away__avail__'+c];total_names.append(name)
    for c in m.PEAK_COLUMNS:
        name='sum__'+c;f[name]=raw['home__'+c]+raw['away__'+c];total_names.append(name)
    extra=['home_score','away_score','total_line','home_spread_odds','away_spread_odds','over_odds','under_odds']
    f['feature_through_week']=raw.train_through_week
    f=f.merge(schedule[['game_id',*extra]],on='game_id',how='left',validate='one_to_one')
    f['margin']=f.home_score-f.away_score;f['total']=f.home_score+f.away_score
    f['margin_line']=f.spread_line;f['market_cover_q']=price_probability(f.home_spread_odds,f.away_spread_odds);f['market_over_q']=price_probability(f.over_odds,f.under_odds)
    f.to_csv(path,index=False,compression={'method':'gzip','mtime':0});return f


def dist_summary(pred):
    held=pred[pred.season.between(2023,2025)].copy();rows=[];pairs=[];annual=[]
    groups=(held.season.astype(str)+'_'+held.week.astype(str)).to_numpy()
    for target in TARGETS:
        y=held[target].to_numpy();line=held[target+'_line'].to_numpy();q=held['market_cover_q' if target=='margin' else 'market_over_q'].to_numpy()
        nonpush=(y!=line)&np.isfinite(q);label=(y>line).astype(float);marketloss=s.loss(label,q)
        scores={}
        for arm in DISTRIBUTIONS:
            mu=held[f'{target}__{arm}__mean'].to_numpy();sd=held[f'{target}__{arm}__sd'].to_numpy();prob,push=event_prob(mu,sd,line)
            nll=-np.log(normal_bin(y,mu,sd));cp=crps(y,mu,sd);ll=s.loss(label,prob);scores[arm]=(nll,cp,ll)
            rows.append({'target':target,'arm':arm,'games':len(held),'nll':float(nll.mean()),'crps':float(cp.mean()),'mae':float(abs(y-mu).mean()),'rmse':float(np.sqrt(((y-mu)**2).mean())),'interval90_coverage':float((abs(y-mu)<=norm.ppf(.95)*sd).mean()),'event_games':int(nonpush.sum()),'pushes':int((y==line).sum()),'event_log_loss':float(ll[nonpush].mean()),'market_event_log_loss':float(marketloss[nonpush].mean()),'market_event_ll_gain':float((marketloss-ll)[nonpush].mean()),'market_event_ll_gain_ci':p.cluster_interval((marketloss-ll)[nonpush],groups[nonpush],.9875)})
            for year in (2023,2024,2025):
                mask=(held.season==year).to_numpy();annual.append({'target':target,'arm':arm,'season':year,'nll':float(nll[mask].mean()),'crps':float(cp[mask].mean()),'event_log_loss':float(ll[mask&nonpush].mean()),'market_event_log_loss':float(marketloss[mask&nonpush].mean())})
        for arm in ('corrected','standalone'):
            dn=scores['market_centered'][0]-scores[arm][0];dc=scores['market_centered'][1]-scores[arm][1]
            pairs.append({'target':target,'arm':arm,'nll_gain':float(dn.mean()),'nll_gain_ci':p.cluster_interval(dn,groups,.9875),'crps_gain':float(dc.mean()),'crps_gain_ci':p.cluster_interval(dc,groups,.9875)})
    return {'results':rows,'comparisons':pairs,'by_season':annual}


def stack_summary(held):
    arms=[*STACKS,'selected','production_full','direct_margin_corrected','direct_margin_standalone','market'];bets={a:m.flat_bets(held,a) for a in arms}
    common=np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()]);proper=held['home won'].isin([0.,1.]).to_numpy();groups=(held.season.astype(str)+'_'+held.week.astype(str)).to_numpy();y=held['home won'].to_numpy()
    rows=[];pairs=[];annual=[]
    for a in arms:
        ll=s.loss(y,held[a]);rows.append({'arm':a,**m.roi_summary(bets[a].loc[common]),'log_loss':float(ll[proper].mean()),'brier':float(((held[a]-y)**2).to_numpy()[proper].mean())})
        if a in ('forecast_additive','margin_total','pass_total','selected','production_full'):
            level=.95 if a in ('selected','production_full') else 1-.05/3
            du=(bets[a].units-bets['production_matched'].units).to_numpy()[common];dl=(s.loss(y,held.production_matched)-ll)[proper]
            pairs.append({'arm':a,'confidence_level':level,'roi_delta':float(du.mean()),'roi_delta_ci':p.cluster_interval(du,groups[common],level),'ll_gain':float(dl.mean()),'ll_gain_ci':p.cluster_interval(dl,groups[proper],level),'side_flips':int(((held[a]>.5)!=(held.production_matched>.5)).to_numpy()[common].sum())})
        for year in (2023,2024,2025):
            mask=(held.season==year).to_numpy();annual.append({'arm':a,'season':year,**m.roi_summary(bets[a].loc[common&mask]),'log_loss':float(ll[proper&mask].mean())})
    additional=[]
    for comparator,arm,level in [('forecast_additive','margin_total',.975),('forecast_additive','pass_total',.975)]+[('production_full',a,1-.05/3) for a in ('forecast_additive','margin_total','pass_total')]+[('pass_market_total','pass_total',.95)]:
        du=(bets[arm].units-bets[comparator].units).to_numpy()[common];dl=(s.loss(y,held[comparator])-s.loss(y,held[arm]))[proper]
        additional.append({'arm':arm,'comparator':comparator,'confidence_level':level,'roi_delta':float(du.mean()),'roi_delta_ci':p.cluster_interval(du,groups[common],level),'ll_gain':float(dl.mean()),'ll_gain_ci':p.cluster_interval(dl,groups[proper],level)})
    return {'results':rows,'comparisons':pairs,'additional_comparisons':additional,'by_season':annual,'bets':int(common.sum()),'proper_games':int(proper.sum())}


def run(out):
    out=out.resolve()
    if any(out==x or x in out.parents for x in (ROOT/'data',ROOT/'public')):raise ValueError('Protected output')
    out.mkdir(parents=True,exist_ok=True);f=prepare_pack(out);total_names=['site']+[c for c in f if c.startswith('sum__')]
    valid=f.ready&np.isfinite(f.margin)&np.isfinite(f.total)&np.isfinite(f.margin_line)&np.isfinite(f.total_line)&np.isfinite(f[s.CONTEXTS]).all(axis=1)
    ix=f.index[valid&f.season.between(2020,2026)];pred=f.loc[ix].copy();audit=[];fits={}
    for (year,week),g in pred.groupby(['season','week'],sort=True):
        train=f[valid&m.before(f,year,week)];earlier=pred[m.before(pred,year,week)]
        pred.loc[g.index,'stage1_through_season']=int(train.season.max());pred.loc[g.index,'stage1_through_week']=int(train[train.season==train.season.max()].week.max())
        for target,names in [('margin',MARGIN_NAMES),('total',total_names)]:
            for arm in DISTRIBUTIONS:
                mean,fit=fit_mean(train,g,target,names,arm);sd,da=dispersion(earlier,train,target,arm,int(year),int(week))
                pred.loc[g.index,f'{target}__{arm}__mean']=mean;pred.loc[g.index,f'{target}__{arm}__sd']=sd
                audit.append({'target':target,'arm':arm,'evaluation_season':int(year),'evaluation_week':int(week),'training_games':fit['training_games'],'training_max_season':int(train.season.max()),'training_max_week':int(train[train.season==train.season.max()].week.max()),**da})
        if week==1:print(f'Distributions {year}',flush=True)
    # Check every nested fit and dispersion reference before stage-two reuse.
    if not all((r['training_max_season'],r['training_max_week'])<(r['evaluation_season'],r['evaluation_week']) and (r['dispersion_max_season'],r['dispersion_max_week'])<(r['evaluation_season'],r['evaluation_week']) for r in audit):raise ValueError('Timing violation')
    validate_oof(pred)
    oof=stack_features(pred);eligible=oof.ready&oof['home won'].isin([0.,1.])&np.isfinite(oof.q)&np.isfinite(oof[MARGIN_NAMES+list(dict.fromkeys(sum(EXTRAS.values(),[])))]).all(axis=1)
    ev=oof['home won'].isin([0.,.5,1.])&np.isfinite(oof.q)&oof.season.between(2022,2025)
    scored=oof.loc[ev,s.p.BASE_COLS].copy();sa=[]
    for (year,week),g in scored.groupby(['season','week'],sort=True):
        tr=oof[eligible&m.before(oof,year,week)];te=oof.loc[g.index]
        for arm in STACKS:
            pp,fit=stack_fit(tr,te,arm);scored.loc[g.index,arm]=pp;sa.append({'arm':arm,'evaluation_season':int(year),'evaluation_week':int(week),'training_games':len(tr),'training_max_season':int(tr.season.max()),'training_max_week':int(tr[tr.season==tr.season.max()].week.max())})
        original=f[f.ready&f['home won'].isin([0.,1.])&np.isfinite(f.q)&m.before(f,year,week)]
        fitted=s.fit(original,int(year),int(week));scored.loc[g.index,'production_full']=s.predict(te,fitted)
        if week==1:print(f'Stack {year}',flush=True)
    held=scored[scored.season.between(2023,2025)].copy();choices=[]
    for year in (2023,2024,2025):
        earlier=scored[(scored.season<year)&scored['home won'].isin([0.,1.])];scores={a:float(s.loss(earlier['home won'].to_numpy(),earlier[a]).mean()) for a in PRIMARY_STACKS};choice=min(scores,key=lambda a:(scores[a],a));held.loc[held.season==year,'selected']=held.loc[held.season==year,choice];choices.append({'season':year,'prior_through':int(earlier.season.max()),'choice':choice,'prior_losses':scores})
    held['market']=held.q
    for arm in ('corrected','standalone'):
        rows=oof.loc[held.index];held['direct_margin_'+arm]=event_prob(rows[f'margin__{arm}__mean'].to_numpy(),rows[f'margin__{arm}__sd'].to_numpy(),np.zeros(len(rows)))[0]
    reference=pd.read_csv(ROOT/'research/production_adoption_results/historical_reproduction.csv').set_index('game_id');err=float(abs(held.production_full.to_numpy()-reference.loc[held.game_id,'production_probability'].to_numpy()).max())
    if err>1e-7:raise ValueError('Full production reproduction')
    current=[];current_fits={}
    archive=ROOT/'research/shrinkage_results/archived_current_inputs.jsonl'
    for r in map(json.loads,archive.read_text().splitlines()):
        year,week=r['season'],r['week'];cutoff_fits=current_fits.setdefault(f'{year}_{week}',{});row=f[f.game_id==r['game_id']].copy()
        if len(row)!=1:raise ValueError('Archive alignment')
        for c,v in r['model_inputs'].items():row[c]=v
        row['q']=r['market_no_vig_wp'];row['margin_line']=r['spread_line']
        tr=f[valid&m.before(f,year,week)];earlier=pred[m.before(pred,year,week)]
        item={'game_id':r['game_id'],'generated_utc':r['generated_utc'],'archived_production':r['model_wp'],'market_q':r['market_no_vig_wp'],'margin_line':float(row.margin_line.iloc[0]),'total_line':float(row.total_line.iloc[0]),'total_line_basis':'schedule quote, capture time unknown'}
        for target,names in [('margin',MARGIN_NAMES),('total',total_names)]:
            for arm in DISTRIBUTIONS:
                mean,fit=fit_mean(tr,row,target,names,arm);sd,da=dispersion(earlier,tr,target,arm,year,week);row[f'{target}__{arm}__mean']=mean;row[f'{target}__{arm}__sd']=sd;item[f'{target}__{arm}__mean']=float(mean[0]);item[f'{target}__{arm}__sd']=sd;cutoff_fits[str((target,arm))]={**fit,**da}
        te=stack_features(row);stack_train=oof[eligible&m.before(oof,year,week)]
        for arm in STACKS:
            pp,fit=stack_fit(stack_train,te,arm);item[arm]=float(pp[0]);cutoff_fits[arm]=fit
        full=s.fit(f[f.ready&f['home won'].isin([0.,1.])&np.isfinite(f.q)&m.before(f,year,week)],year,week);item['production_full']=float(s.predict(te,full)[0]);cutoff_fits['production_full']=full
        item['direct_margin_corrected']=float(event_prob(row.margin__corrected__mean.to_numpy(),row.margin__corrected__sd.to_numpy(),np.array([0.]))[0][0]);current.append(item)
    archive_error=max(abs(r['production_full']-r['archived_production']) for r in current)
    if archive_error>1e-7:raise ValueError('Archive production reproduction')
    pd.DataFrame(current).to_csv(out/'current_counterfactuals.csv',index=False)
    (out/'current_fits.json').write_text(json.dumps(current_fits,indent=2)+'\n')
    result={'basis':'Exposed historical development; schedule market quotes lack capture timestamps','revision':'boxscore-composite-v1.16','distribution':dist_summary(pred),'stack':stack_summary(held),'selections':choices,'historical_full_production_error':err,'all_cutoffs_prior_week':True,'archived_production_error':archive_error}
    pred.to_csv(out/'weekly_oof_forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0});held.to_csv(out/'heldout_win_predictions.csv',index=False);pd.DataFrame(audit).to_csv(out/'distribution_fit_audit.csv',index=False);pd.DataFrame(sa).to_csv(out/'stack_fit_audit.csv',index=False)
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    sources=[ROOT/'research/qualified_interactions.py',ROOT/'research/production_qualification.py',ROOT/'research/shrinkage_results/frozen_training_features.csv.gz',ROOT/'research/production_adoption_results/historical_reproduction.csv',ROOT/'research/shrinkage_results/archived_current_inputs.jsonl',Path(__file__),ROOT/'research/MARGIN_TOTAL_MODELS.md',ROOT/'nfl_model.py',ROOT/'research/context_shrinkage.py',out/'frozen_feature_prices.csv.gz',archive]
    (out/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},indent=2)+'\n')
    write_report(result,out);print(json.dumps(result['stack']['results'],indent=2),flush=True)


def write_report(r,out):
    lines=['# Direct margin/total and production interaction results','','Exposed historical development, not native forward qualification. Schedule quotes have no known lock timestamps. Gaussian approximation and market-centered benchmarks; true market event probabilities use both no-vig prices.',f"\nStack: {r['stack']['bets']} common flat 1u bets; {r['stack']['proper_games']} binary scores.",'','| Win model | Units | ROI ± SE | Market-null | LL | Brier |','|---|---:|---:|---:|---:|---:|']
    for x in r['stack']['results']:lines.append(f"| {x['arm']} | {x['units']:+.2f} | {100*x['roi']:+.2f}% ± {100*x['roi_se']:.2f} | {100*x['null_roi']:+.2f}% | {x['log_loss']:.6f} | {x['brier']:.6f} |")
    lines+=['','Positive paired gains favor the new arm over matched-cohort production. Fixed contrasts use 98.333% intervals; selected/full-history diagnostics 95%.','','| Arm | ROI delta [CI], pp | LL gain [CI] | Side flips |','|---|---:|---:|---:|']
    for x in r['stack']['comparisons']:
        lo,hi=x['roi_delta_ci'];ll,lh=x['ll_gain_ci'];lines.append(f"| {x['arm']} | {100*x['roi_delta']:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}] | {x['ll_gain']:+.6f} [{ll:+.6f}, {lh:+.6f}] | {x['side_flips']} |")
    lines+=['','## Interaction benefit and full-history production comparisons','','| Arm | Comparator | ROI delta [CI], pp | LL gain [CI] |','|---|---|---:|---:|']
    for x in r['stack']['additional_comparisons']:
        lo,hi=x['roi_delta_ci'];ll,lh=x['ll_gain_ci'];lines.append(f"| {x['arm']} | {x['comparator']} | {100*x['roi_delta']:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}] | {x['ll_gain']:+.6f} [{ll:+.6f}, {lh:+.6f}] |")
    lines+=['','Interactions vs additive use 97.5% intervals (two contrasts); comparisons vs full production use 98.333% (three). The supplementary pass_market_total contrast uses a descriptive 95% interval. Direct-margin win probabilities condition on a non-tie.','','## Distribution forecasts','','| Target | Arm | N | NLL ↓ | CRPS ↓ | MAE | RMSE | 90% coverage |','|---|---|---:|---:|---:|---:|---:|---:|']
    for x in r['distribution']['results']:lines.append(f"| {x['target']} | {x['arm']} | {x['games']} | {x['nll']:.6f} | {x['crps']:.4f} | {x['mae']:.3f} | {x['rmse']:.3f} | {100*x['interval90_coverage']:.1f}% |")
    lines+=['','| Target | Arm | NLL gain vs market-centered [CI] | CRPS gain [CI] |','|---|---|---:|---:|']
    for x in r['distribution']['comparisons']:
        lo,hi=x['nll_gain_ci'];cl,ch=x['crps_gain_ci'];lines.append(f"| {x['target']} | {x['arm']} | {x['nll_gain']:+.6f} [{lo:+.6f}, {hi:+.6f}] | {x['crps_gain']:+.4f} [{cl:+.4f}, {ch:+.4f}] |")
    lines+=['','## Cover/over probabilities at market lines','','Pushes excluded from both arms. These compare actual no-vig prices, not a reconstructed 50% baseline. 98.75% intervals.','','| Target | Arm | Nonpush N | Pushes | Event LL ↓ | Market LL ↓ | LL gain [CI] |','|---|---|---:|---:|---:|---:|---:|']
    for x in r['distribution']['results']:
        lo,hi=x['market_event_ll_gain_ci'];lines.append(f"| {x['target']} | {x['arm']} | {x['event_games']} | {x['pushes']} | {x['event_log_loss']:.6f} | {x['market_event_log_loss']:.6f} | {x['market_event_ll_gain']:+.6f} [{lo:+.6f}, {hi:+.6f}] |")
    lines+=['','## Annual win results','','| Arm | Season | Units | ROI | LL |','|---|---:|---:|---:|---:|']
    for x in r['stack']['by_season']:lines.append(f"| {x['arm']} | {x['season']} | {x['units']:+.2f} | {100*x['roi']:+.2f}% | {x['log_loss']:.6f} |")
    lines+=['','## Prior-season stack selection','']+[f"- {x['season']}: {x['choice']} (selection through {x['prior_through']})" for x in r['selections']]
    lines+=['',f"Full-history production reproduction error: {r['historical_full_production_error']:.3g}.",'All stage-one features, coefficient fits, variance calibration and stage-two coefficient fits precede evaluation weeks. Stage-two warm-up removes early training games; production_full discloses its impact. These intervals omit model-design selection uncertainty.','']
    current=pd.read_csv(out/'current_counterfactuals.csv');sf=current[current.game_id=='2026_05_SF_SEA']
    lines+=['','## Archived SF at SEA counterfactual','','Schedule total quote is not a known lock quote. Seattle/home margin is positive.']
    if len(sf):
        row=sf.iloc[0]
        for name in ('margin_line','total_line','margin__corrected__mean','margin__corrected__sd','total__corrected__mean','total__corrected__sd'):lines.append(f"- {name}: {row[name]:.3f}")
        for name in (*STACKS,'production_full','direct_margin_corrected'):lines.append(f"- {name}: {100*row[name]:.2f}% Seattle")
    (out/'REPORT.md').write_text('\n'.join(lines))

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-dir',type=Path,default=ROOT/'research/margin_total_results');run(ap.parse_args().output_dir)
