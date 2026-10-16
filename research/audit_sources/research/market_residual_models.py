"""Market-only margin/total forecasts and honest production interactions."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logit
from scipy.stats import norm
import margin_total_models as t
s,m,p,ROOT=t.s,t.m,t.p,t.ROOT
RULES={f'resid_h{h}_k{k}':(h,k) for h in (4,16) for k in (4,12)}
ARMS=('market_centered','market_relationships',*RULES)
PRICE_NAMES={'margin':['spread10','moneyline_logit','total_context_price','spread_total_price','cover_logit'],
             'total':['total_context_price','abs_spread10','abs_moneyline_logit','spread_squared','over_logit']}
STACKS=t.STACKS


def price_features(f):
    f=f.copy();f['spread10']=f.margin_line/10.;f['moneyline_logit']=logit(np.clip(f.q,1e-5,1-1e-5))
    f['total_context_price']=(f.total_line-45.)/10.;f['spread_total_price']=f.spread10*f.total_context_price
    f['abs_spread10']=abs(f.spread10);f['abs_moneyline_logit']=abs(f.moneyline_logit);f['spread_squared']=f.spread10**2
    f['cover_logit']=logit(np.clip(f.market_cover_q,1e-5,1-1e-5));f['over_logit']=logit(np.clip(f.market_over_q,1e-5,1-1e-5))
    return f


def residual_profile(history,year,week,team,half,prior):
    if half<=0 or prior<0:raise ValueError('Invalid decay/prior')
    h=history[m.before(history,year,week)&(history.season>=year-3)&((history.home==team)|(history.away==team))].sort_values(['season','week','game_id'])
    if h.empty:return 0.,0.,0.,0.,-1,-1
    w=np.exp2(-np.arange(len(h)-1,-1,-1,dtype=float)/half)*np.power(.5,year-h.season.to_numpy())
    mr=(h.margin-h.margin_line).to_numpy()*np.where(h.home==team,1.,-1.)
    tr=(h.total-h.total_line).to_numpy();den=w.sum()+prior
    return float(w@mr/den),float(w@tr/den),float(w.sum()),float(w.sum()**2/(w@w)),int(h.season.max()),int(h[h.season==h.season.max()].week.max())


def add_residuals(f):
    f=f.copy();audit=[]
    eligible=np.isfinite(f[['margin','total','margin_line','total_line']]).all(axis=1)
    history=f.loc[eligible].copy()
    for (year,week),g in f.groupby(['season','week'],sort=True):
        for arm,(half,prior) in RULES.items():
            profiles={team:residual_profile(history,int(year),int(week),team,half,prior) for team in set(g.home)|set(g.away)}
            for ix,row in g.iterrows():
                h,a=profiles[row.home],profiles[row.away]
                f.loc[ix,arm+'__margin_history']=(h[0]-a[0])/10.
                f.loc[ix,arm+'__total_history']=(h[1]+a[1])/20.
                for side,z in [('home',h),('away',a)]:audit.append({'game_id':row.game_id,'season':int(year),'week':int(week),'arm':arm,'side':side,'margin_residual_mean':z[0],'total_residual_mean':z[1],'decayed_game_mass':z[2],'effective_games':z[3],'max_source_season':z[4],'max_source_week':z[5]})
    return f,pd.DataFrame(audit)


def select_forecasts(pred):
    pred=pred.copy();selections=[]
    for year in sorted(pred.season.unique()):
        earlier=pred[pred.season<year]
        for target in t.TARGETS:
            scores={}
            for arm in ('market_relationships',*RULES):
                if len(earlier):scores[arm]=float((-np.log(t.normal_bin(earlier[target].to_numpy(),earlier[f'{target}__{arm}__mean'].to_numpy(),earlier[f'{target}__{arm}__sd'].to_numpy()))).mean())
            choice=min(scores,key=lambda a:(scores[a],a)) if scores else 'market_relationships'
            mask=pred.season==year
            for field in ('mean','sd'):pred.loc[mask,f'{target}__selected__{field}']=pred.loc[mask,f'{target}__{choice}__{field}']
            selections.append({'season':int(year),'target':target,'chosen':choice,'selection_through':int(earlier.season.max()) if len(earlier) else None,'prior_scores':scores})
    return pred,selections


def distribution_summary(pred):
    held=pred[pred.season.between(2023,2025)].copy();groups=(held.season.astype(str)+'_'+held.week.astype(str)).to_numpy();rows=[];pairs=[];annual=[]
    for target in t.TARGETS:
        y=held[target].to_numpy();line=held[target+'_line'].to_numpy();q=held['market_cover_q' if target=='margin' else 'market_over_q'].to_numpy();nonpush=(y!=line);lab=(y>line).astype(float);ml=s.loss(lab,q);scores={}
        for arm in (*ARMS,'selected'):
            mu=held[f'{target}__{arm}__mean'].to_numpy();sd=held[f'{target}__{arm}__sd'].to_numpy();nll=-np.log(t.normal_bin(y,mu,sd));cp=t.crps(y,mu,sd);prob,_=t.event_prob(mu,sd,line);ll=s.loss(lab,prob);scores[arm]=(nll,cp)
            rows.append({'target':target,'arm':arm,'games':len(held),'nll':float(nll.mean()),'crps':float(cp.mean()),'mae':float(abs(y-mu).mean()),'rmse':float(np.sqrt(((y-mu)**2).mean())),'coverage90':float((abs(y-mu)<=norm.ppf(.95)*sd).mean()),'event_games':int(nonpush.sum()),'pushes':int((~nonpush).sum()),'event_ll':float(ll[nonpush].mean()),'market_event_ll':float(ml[nonpush].mean()),'event_ll_gain':float((ml-ll)[nonpush].mean()),'event_ll_gain_ci':p.cluster_interval((ml-ll)[nonpush],groups[nonpush],.9875)})
            for year in (2023,2024,2025):
                mask=(held.season==year).to_numpy();annual.append({'target':target,'arm':arm,'season':year,'nll':float(nll[mask].mean()),'event_ll':float(ll[mask&nonpush].mean()),'market_event_ll':float(ml[mask&nonpush].mean())})
        for comparator in ('market_centered','market_relationships'):
            dn=scores[comparator][0]-scores['selected'][0];dc=scores[comparator][1]-scores['selected'][1]
            pairs.append({'target':target,'comparator':comparator,'nll_gain':float(dn.mean()),'nll_gain_ci':p.cluster_interval(dn,groups,.9875),'crps_gain':float(dc.mean()),'crps_gain_ci':p.cluster_interval(dc,groups,.9875)})
    return {'results':rows,'comparisons':pairs,'by_season':annual}


def win_summary(held):
    arms=[*STACKS,'selected','production_full','direct_margin_selected','direct_margin_relationships','market'];bets={a:m.flat_bets(held,a) for a in arms}
    common=np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()]);proper=held['home won'].isin([0.,1.]).to_numpy();groups=(held.season.astype(str)+'_'+held.week.astype(str)).to_numpy();y=held['home won'].to_numpy();rows=[];annual=[];pairs=[]
    for arm in arms:
        ll=s.loss(y,held[arm]);rows.append({'arm':arm,**m.roi_summary(bets[arm].loc[common]),'log_loss':float(ll[proper].mean()),'brier':float(((held[arm]-y)**2).to_numpy()[proper].mean())})
        for year in (2023,2024,2025):
            mask=(held.season==year).to_numpy();annual.append({'arm':arm,'season':year,**m.roi_summary(bets[arm].loc[common&mask]),'log_loss':float(ll[proper&mask].mean())})
    contrasts=[(a,c,.9875) for a in STACKS[1:] for c in ('production_matched','production_full')]+[('selected','production_full',.95),('pass_total','pass_market_total',.95),('margin_total','forecast_additive',.95),('pass_total','forecast_additive',.95)]
    for a,c,level in contrasts:
        du=(bets[a].units-bets[c].units).to_numpy()[common];dl=(s.loss(y,held[c])-s.loss(y,held[a]))[proper]
        pairs.append({'arm':a,'comparator':c,'level':level,'roi_delta':float(du.mean()),'roi_delta_ci':p.cluster_interval(du,groups[common],level),'ll_gain':float(dl.mean()),'ll_gain_ci':p.cluster_interval(dl,groups[proper],level),'side_flips':int(((held[a]>.5)!=(held[c]>.5)).to_numpy()[common].sum())})
    return {'results':rows,'comparisons':pairs,'by_season':annual,'bets':int(common.sum()),'proper_games':int(proper.sum())}


def run(out):
    out=out.resolve()
    if any(out==x or x in out.parents for x in (ROOT/'data',ROOT/'public')):raise ValueError('Protected output')
    out.mkdir(parents=True,exist_ok=True);pack=out/'frozen_market_outcomes.csv.gz'
    if pack.exists():f=pd.read_csv(pack)
    else:
        original=pd.read_csv(ROOT/'research/margin_total_results/frozen_feature_prices.csv.gz')
        cols=['game_id','season','week','home','away','home won','result','spread_line','home_moneyline','away_moneyline','q','site','margin','total','margin_line','total_line','market_cover_q','market_over_q']
        f=original[cols].copy();f.to_csv(pack,index=False,compression={'method':'gzip','mtime':0})
    f['ready']=True;f=price_features(f);f,ra=add_residuals(f)
    valid=np.isfinite(f[['margin','total','margin_line','total_line','q','market_cover_q','market_over_q']]).all(axis=1)
    pred=f.loc[valid&f.season.between(2020,2026)].copy();audit=[]
    for (year,week),g in pred.groupby(['season','week'],sort=True):
        train=f[valid&m.before(f,year,week)];earlier=pred[m.before(pred,year,week)]
        pred.loc[g.index,'stage1_through_season']=int(train.season.max());pred.loc[g.index,'stage1_through_week']=int(train[train.season==train.season.max()].week.max())
        for target in t.TARGETS:
            for arm in ARMS:
                names=PRICE_NAMES[target]+([arm+f'__{target}_history'] if arm in RULES else [])
                mu,fit=t.fit_mean(train,g,target,names,'market_centered' if arm=='market_centered' else 'corrected')
                sigma,da=t.dispersion(earlier,train,target,arm,int(year),int(week))
                pred.loc[g.index,f'{target}__{arm}__mean']=mu;pred.loc[g.index,f'{target}__{arm}__sd']=sigma
                audit.append({'target':target,'arm':arm,'season':int(year),'week':int(week),'training_games':fit['training_games'],'training_max_season':int(train.season.max()),'training_max_week':int(train[train.season==train.season.max()].week.max()),**da})
        if week==1:print(f'Market targets {year}',flush=True)
    t.validate_oof(pred);pred,choices=select_forecasts(pred)
    if not all((r['dispersion_max_season'],r['dispersion_max_week'])<(r['season'],r['week']) for r in audit):raise ValueError('Future dispersion')
    if not ((ra.max_source_season<ra.season)|((ra.max_source_season==ra.season)&(ra.max_source_week<ra.week))).all():raise ValueError('Future residual source')
    original=pd.read_csv(ROOT/'research/shrinkage_results/frozen_training_features.csv.gz').set_index('game_id')
    oof=pred.copy()
    for c in [*t.MARGIN_NAMES,'ready']:
        oof[c]=original.loc[oof.game_id,c].to_numpy()
    oof['margin__corrected__mean']=oof.margin__selected__mean;oof['total__corrected__mean']=oof.total__selected__mean;oof=t.stack_features(oof)
    extra=list(dict.fromkeys(sum(t.EXTRAS.values(),[])));eligible=oof.ready&oof['home won'].isin([0.,1.])&np.isfinite(oof.q)&np.isfinite(oof[t.MARGIN_NAMES+extra]).all(axis=1)
    ev=oof.ready&oof['home won'].isin([0.,.5,1.])&np.isfinite(oof.q)&oof.season.between(2022,2025)
    scored=oof.loc[ev,p.BASE_COLS].copy();sa=[]
    for (year,week),g in scored.groupby(['season','week'],sort=True):
        tr=oof[eligible&m.before(oof,year,week)];te=oof.loc[g.index]
        for arm in STACKS:
            prob,fit=t.stack_fit(tr,te,arm);scored.loc[g.index,arm]=prob;sa.append({'arm':arm,'season':int(year),'week':int(week),'training_games':len(tr),'training_max_season':int(tr.season.max()),'training_max_week':int(tr[tr.season==tr.season.max()].week.max())})
        full=original.reset_index();full=full[full.ready&full['home won'].isin([0.,1.])&np.isfinite(full.q)&m.before(full,year,week)]
        fitted=s.fit(full,int(year),int(week));scored.loc[g.index,'production_full']=s.predict(te,fitted)
        if week==1:print(f'Market stack {year}',flush=True)
    held=scored[scored.season.between(2023,2025)].copy();winchoices=[]
    for year in (2023,2024,2025):
        earlier=scored[(scored.season<year)&scored['home won'].isin([0.,1.])];scores={a:float(s.loss(earlier['home won'].to_numpy(),earlier[a]).mean()) for a in STACKS};choice=min(scores,key=lambda a:(scores[a],a));held.loc[held.season==year,'selected']=held.loc[held.season==year,choice];winchoices.append({'season':year,'chosen':choice,'prior_scores':scores})
    held['market']=held.q
    for arm in ('selected','market_relationships'):
        rows=oof.loc[held.index];held['direct_margin_'+('relationships' if arm=='market_relationships' else arm)]=t.event_prob(rows[f'margin__{arm}__mean'].to_numpy(),rows[f'margin__{arm}__sd'].to_numpy(),np.zeros(len(rows)))[0]
    reference=pd.read_csv(ROOT/'research/production_adoption_results/historical_reproduction.csv').set_index('game_id');err=float(abs(held.production_full.to_numpy()-reference.loc[held.game_id,'production_probability'].to_numpy()).max())
    if err>1e-7:raise ValueError('Production reproduction')
    current=[];current_fits={}
    archive=ROOT/'research/shrinkage_results/archived_current_inputs.jsonl'
    for r in map(json.loads,archive.read_text().splitlines()):
        year,week=r['season'],r['week'];cutoff_fits=current_fits.setdefault(f'{year}_{week}',{});row=f[f.game_id==r['game_id']].copy()
        row['q']=r['market_no_vig_wp'];row['margin_line']=r['spread_line'];row=price_features(row)
        train=f[valid&m.before(f,year,week)];earlier=pred[m.before(pred,year,week)]
        item={'game_id':r['game_id'],'generated_utc':r['generated_utc'],'archived_production':r['model_wp'],'market_q':r['market_no_vig_wp'],'margin_line':float(row.margin_line.iloc[0]),'total_line':float(row.total_line.iloc[0]),'total_quote_basis':'schedule quote, capture time unknown'}
        for target in t.TARGETS:
            choice=next(c['chosen'] for c in choices if c['season']==year and c['target']==target)
            names=PRICE_NAMES[target]+([choice+f'__{target}_history'] if choice in RULES else [])
            mu,fit=t.fit_mean(train,row,target,names,'corrected');sigma,da=t.dispersion(earlier,train,target,choice,year,week)
            row[f'{target}__corrected__mean']=mu;item[target+'_mean']=float(mu[0]);item[target+'_sd']=sigma;item[target+'_rule']=choice;cutoff_fits[target]={**fit,**da}
        for c,v in r['model_inputs'].items():row[c]=v
        te=t.stack_features(row);tr=oof[eligible&m.before(oof,year,week)]
        for arm in STACKS:
            pp,fit=t.stack_fit(tr,te,arm);item[arm]=float(pp[0]);cutoff_fits[arm]=fit
        full=original.reset_index();full=full[full.ready&full['home won'].isin([0.,1.])&np.isfinite(full.q)&m.before(full,year,week)];fit=s.fit(full,year,week);item['production_full']=float(s.predict(te,fit)[0]);cutoff_fits['production_full']=fit;current.append(item)
    archive_error=max(abs(z['production_full']-z['archived_production']) for z in current)
    if archive_error>1e-7:raise ValueError('Archive reproduction')
    pd.DataFrame(current).to_csv(out/'current_counterfactuals.csv',index=False);(out/'current_fits.json').write_text(json.dumps(current_fits,indent=2)+'\n')
    result={'basis':'Exposed historical development; schedule quote timestamps unknown','distribution':distribution_summary(pred),'win':win_summary(held),'target_selections':choices,'win_selections':winchoices,'production_error':err,'all_cutoffs_prior_week':True,'archive_error':archive_error}
    pred.to_csv(out/'weekly_market_forecasts.csv.gz',index=False,compression={'method':'gzip','mtime':0});held.to_csv(out/'heldout_win_predictions.csv',index=False);ra.to_csv(out/'residual_support_audit.csv.gz',index=False,compression={'method':'gzip','mtime':0});pd.DataFrame(audit).to_csv(out/'distribution_fit_audit.csv',index=False);pd.DataFrame(sa).to_csv(out/'stack_fit_audit.csv',index=False)
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    sources=[ROOT/'research/qualified_interactions.py',ROOT/'research/production_qualification.py',ROOT/'research/shrinkage_results/frozen_training_features.csv.gz',ROOT/'research/production_adoption_results/historical_reproduction.csv',ROOT/'research/shrinkage_results/archived_current_inputs.jsonl',Path(__file__),ROOT/'research/MARKET_RESIDUAL_MODELS.md',ROOT/'research/margin_total_models.py',ROOT/'research/context_shrinkage.py',ROOT/'nfl_model.py',pack,ROOT/'research/shrinkage_results/frozen_training_features.csv.gz']
    (out/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},indent=2)+'\n');write_report(result,out);print(json.dumps(result['win']['results'],indent=2),flush=True)


def write_report(r,out):
    lines=['# Market-only forecasts and rolling residuals','','Exposed development; market quote capture times unknown. Stage one contains no box-score features.',f"\n{r['win']['bets']} common flat 1u bets; {r['win']['proper_games']} binary win scores.",'','| Win model | Units | ROI ± SE | Null ROI | LL | Brier |','|---|---:|---:|---:|---:|---:|']
    for x in r['win']['results']:lines.append(f"| {x['arm']} | {x['units']:+.2f} | {100*x['roi']:+.2f}% ± {100*x['roi_se']:.2f} | {100*x['null_roi']:+.2f}% | {x['log_loss']:.6f} | {x['brier']:.6f} |")
    lines+=['','## Paired win comparisons','','| Arm | Comparator | ROI gain [CI], pp | LL gain [CI] |','|---|---|---:|---:|']
    for x in r['win']['comparisons']:
        lo,hi=x['roi_delta_ci'];ll,lh=x['ll_gain_ci'];lines.append(f"| {x['arm']} | {x['comparator']} | {100*x['roi_delta']:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}] | {x['ll_gain']:+.6f} [{ll:+.6f}, {lh:+.6f}] |")
    lines+=['','Fixed candidate/production comparisons use 98.75% intervals; selection/interaction/source contrasts 95%.','','## Target distributions','','| Target | Arm | N | NLL ↓ | CRPS ↓ | RMSE | Event LL ↓ | Market event LL ↓ |','|---|---|---:|---:|---:|---:|---:|---:|']
    for x in r['distribution']['results']:lines.append(f"| {x['target']} | {x['arm']} | {x['games']} | {x['nll']:.6f} | {x['crps']:.4f} | {x['rmse']:.3f} | {x['event_ll']:.6f} | {x['market_event_ll']:.6f} |")
    lines+=['','## Selected distribution improvement','','| Target | Comparator | NLL gain [98.75% CI] | CRPS gain [CI] |','|---|---|---:|---:|']
    for x in r['distribution']['comparisons']:
        lo,hi=x['nll_gain_ci'];cl,ch=x['crps_gain_ci'];lines.append(f"| {x['target']} | {x['comparator']} | {x['nll_gain']:+.6f} [{lo:+.6f}, {hi:+.6f}] | {x['crps_gain']:+.4f} [{cl:+.4f}, {ch:+.4f}] |")
    lines+=['','## Prior-season target selections','']+[f"- {x['season']} {x['target']}: {x['chosen']} (through {x['selection_through']})" for x in r['target_selections'] if x['season']>=2023]
    lines+=['','## Annual production comparisons','','| Arm | Season | Units | ROI | LL |','|---|---:|---:|---:|---:|']
    for x in r['win']['by_season']:lines.append(f"| {x['arm']} | {x['season']} | {x['units']:+.2f} | {100*x['roi']:+.2f}% | {x['log_loss']:.6f} |")
    lines+=['',f"Production reproduction error {r['production_error']:.3g}. All histories and nested fits precede evaluation weeks. Paired week-cluster bootstrap excludes design-selection uncertainty. Gaussian approximation and unknown quote timing limit interpretation. No native forward qualification or production change.",'']
    current=pd.read_csv(out/'current_counterfactuals.csv');sf=current[current.game_id=='2026_05_SF_SEA']
    lines+=['','## Archived SF at SEA counterfactual','','Schedule total/cover/over prices have unknown lock timing. Seattle/home margin is positive.']
    if len(sf):
        row=sf.iloc[0]
        for name in ('margin_line','margin_mean','margin_sd','total_line','total_mean','total_sd'):lines.append(f"- {name}: {row[name]:.3f}")
        for name in (*STACKS,'production_full'):lines.append(f"- {name}: {100*row[name]:.2f}% Seattle")
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-dir',type=Path,default=ROOT/'research/market_residual_results');run(ap.parse_args().output_dir)
