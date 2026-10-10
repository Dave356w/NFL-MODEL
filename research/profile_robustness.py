"""Prior-week passing profile and tail robustness experiments."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import context_shrinkage as s
m,p,ROOT=s.m,s.p,s.ROOT
ARMS={'production':(0.,None),'profile_4':(4.,None),'profile_12':(12.,None),'bounded_2':(0.,2.),'combined_4_2':(4.,2.)}
STAT='net_pass_yards_per_pass_play'
COLS=[f'{side}__{role}__rates_core__{STAT}' for side,role in [('home','for'),('away','allowed'),('away','for'),('home','allowed')]]


def rate(numer,denom,league_num,league_den,extra):
    if not np.isfinite(extra) or extra<0:raise ValueError('Invalid extra prior')
    return (numer+(m.PRIOR_EQUIVALENT_GAMES+extra)*league_num)/(denom+(m.PRIOR_EQUIVALENT_GAMES+extra)*league_den)


def contexts(desc,bound=None):
    z=desc[['pass_ho','pass_ad','pass_ao','pass_hd']].to_numpy(float)
    if bound is not None:
        if not np.isfinite(bound) or bound<=1:raise ValueError('Invalid bound')
        z=np.clip(z,-bound,bound)
    out=desc.copy();out[['pass_ho','pass_ad','pass_ao','pass_hd']]=z
    out['pass_product']=z[:,0]*z[:,1]-z[:,2]*z[:,3]
    for a,sa in [('p',1.),('n',-1.)]:
        for b,sb in [('p',1.),('n',-1.)]:
            out[f'pass_1sd_{a}{b}']=np.maximum(sa*z[:,0]-1,0)*np.maximum(sb*z[:,1]-1,0)-np.maximum(sa*z[:,2]-1,0)*np.maximum(sb*z[:,3]-1,0)
    return out


def build_statistics(f,box=None):
    cache=ROOT/'.nfl_cache/shrinkage_inputs'
    box=m.validate_boxes(pd.read_csv(cache/'boxes.csv') if box is None else box)
    opp=box[['game_id','team','net_pass_yards','pass_plays']].rename(columns={'team':'opponent','net_pass_yards':'opp_net_pass_yards','pass_plays':'opp_pass_plays'})
    both=box.merge(opp,on=['game_id','opponent'],validate='one_to_one');records=[]
    for (year,week),games in f.groupby(['season','week'],sort=True):
        hist=both[m.before(both,year,week)&(both.season>=year-m.MAX_HISTORY_SEASONS)]
        valid=np.isfinite(hist.net_pass_yards)&np.isfinite(hist.pass_plays)&(hist.pass_plays>0)
        ln=hist.loc[valid,'net_pass_yards'].mean();ld=hist.loc[valid,'pass_plays'].mean()
        profiles={}
        for team in set(games.home)|set(games.away):
            h=hist[hist.team==team].sort_values(['season','week','game_id']);age=np.arange(len(h)-1,-1,-1,dtype=float)
            for half in (8.,16.):
                w=np.exp2(-age/half)*np.power(m.OFFSEASON_RETENTION,year-h.season.to_numpy(float))
                for role,prefix in [('for',''),('allowed','opp_')]:
                    n=h[prefix+'net_pass_yards'].to_numpy(float);d=h[prefix+'pass_plays'].to_numpy(float)
                    ok=np.isfinite(n)&np.isfinite(d)&(d>0);ww=w[ok];mass=ww*d[ok]
                    profiles[team,half,role]=(float(ww@n[ok]),float(ww@d[ok]),float(ww.sum()**2/(ww@ww)) if len(ww) else 0.,float(mass.sum()**2/(mass@mass)) if len(mass) else 0.)
        for _,g in games.iterrows():
            for half in (8.,16.):
                for side in ('home','away'):
                    for role in ('for','allowed'):
                        n,d,eg,ep=profiles[g[side],half,role]
                        records.append({'game_id':g.game_id,'half_life':half,'side':side,'role':role,'numerator':n,'denominator':d,'league_num':ln,'league_den':ld,'effective_games':eg,'effective_pass_mass_games':ep,'max_source_season':int(hist.season.max()) if len(hist) else -1,'max_source_week':int(hist[hist.season==hist.season.max()].week.max()) if len(hist) else -1})
    return pd.DataFrame(records)


def features(f,stats,extra,bound):
    frames={}
    for half in (8.,16.):
        fr=f[['game_id','season','week']].copy()
        for side in ('home','away'):
            for role in ('for','allowed'):
                rows=stats[(stats.half_life==half)&(stats.side==side)&(stats.role==role)].set_index('game_id').loc[f.game_id]
                fr[f'{side}__{role}__rates_core__{STAT}']=rate(rows.numerator.to_numpy(),rows.denominator.to_numpy(),rows.league_num.to_numpy(),rows.league_den.to_numpy(),extra)
        frames[half]=fr
    desc,refs=m.pass_contexts(frames[16.]);desc=contexts(desc,bound)
    out=f.copy()
    for role in ('for','allowed'):
        name=f'd__{role}__rates_core__{STAT}'
        out[name]=frames[8.][f'home__{role}__rates_core__{STAT}']-frames[8.][f'away__{role}__rates_core__{STAT}']
    for c in desc:out[c]=desc[c]
    return out,refs


def summarize(held):
    arms=[*ARMS,'selected','market'];bets={a:m.flat_bets(held,a) for a in arms}
    common=np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()]);proper=held['home won'].isin([0.,1.]).to_numpy()
    groups=(held.season.astype(str)+'_'+held.week.astype(str)).to_numpy();y=held['home won'].to_numpy()
    results=[];pairs=[];annual=[];slices=[]
    for a in arms:
        ll=s.loss(y,held[a]);results.append({'arm':a,**m.roi_summary(bets[a].loc[common]),'log_loss':float(ll[proper].mean()),'brier':float(((held[a]-y)**2).to_numpy()[proper].mean())})
        if a not in ('production','market'):
            level=.95 if a=='selected' else .9875;du=(bets[a].units-bets['production'].units).to_numpy()[common];dl=(s.loss(y,held.production)-ll)[proper]
            pairs.append({'arm':a,'confidence_level':level,'roi_delta':float(du.mean()),'roi_delta_ci':p.cluster_interval(du,groups[common],level),'ll_gain':float(dl.mean()),'ll_gain_ci':p.cluster_interval(dl,groups[proper],level),'side_flips':int(((held[a]>.5)!=(held.production>.5)).to_numpy()[common].sum())})
        for year in sorted(held.season.unique()):
            mask=(held.season==year).to_numpy();annual.append({'arm':a,'season':int(year),**m.roi_summary(bets[a].loc[common&mask]),'log_loss':float(ll[proper&mask].mean())})
        for label,mask in [('production >=90%',np.maximum(held.production,1-held.production).to_numpy()>=.9),('production profile >2 SD',held['tail'].to_numpy(bool))]:
            mask=mask&proper;slices.append({'arm':a,'slice':label,'binary_games':int(mask.sum()),'log_loss':float(ll[mask].mean()),**m.roi_summary(bets[a].loc[common&mask])})
    return {'results':results,'comparisons':pairs,'by_season':annual,'slices':slices,'bets':int(common.sum()),'proper_games':int(proper.sum())}


def run(out):
    out=out.resolve()
    if any(out==x or x in out.parents for x in (ROOT/'data',ROOT/'public')):raise ValueError('Protected output')
    out.mkdir(parents=True,exist_ok=True);pack=ROOT/'research/shrinkage_results/frozen_training_features.csv.gz';f=pd.read_csv(pack)
    sp=out/'passing_sufficient_statistics.csv.gz'
    if sp.exists():stats=pd.read_csv(sp)
    else:
        stats=build_statistics(f);stats.to_csv(sp,index=False,compression={'method':'gzip','mtime':0})
    cut=stats.merge(f[['game_id','season','week']],on='game_id',validate='many_to_one')
    assert ((cut.max_source_season<cut.season)|((cut.max_source_season==cut.season)&(cut.max_source_week<cut.week))).all()
    fs={};refs=[]
    for a,(extra,bound) in ARMS.items():
        fs[a],r=features(f,stats,extra,bound);r['arm']=a;refs.append(r)
    names=m.feature_names(s.q.BASE_FAMILY)+s.CONTEXTS
    error=float(np.nanmax(abs(fs['production'][names].to_numpy()-f[names].to_numpy())))
    if error>1e-8:raise ValueError(f'Feature reproduction failed {error}')
    mask=f.ready&f['home won'].isin([0.,.5,1.])&np.isfinite(f.q)&np.isfinite(f[s.CONTEXTS]).all(axis=1)&f.season.between(2021,2025)
    pred=f.loc[mask,p.BASE_COLS].copy();audit=[]
    for (year,week),rows in pred.groupby(['season','week'],sort=True):
        for a in ARMS:
            ff=fs[a];train=ff[m.before(ff,year,week)];fit=s.fit(train,int(year),int(week));pred.loc[rows.index,a]=s.predict(ff.loc[rows.index],fit)
            audit.append({'arm':a,'evaluation_season':int(year),'evaluation_week':int(week),'training_games':fit['training_games'],'training_max_season':fit['training_max_season'],'training_max_week':fit['training_max_week']})
        if week==1:print(f'Completed season {year}',flush=True)
    if not np.isfinite(pred[list(ARMS)]).all().all():raise ValueError('Incomplete probabilities')
    held=pred[pred.season.between(2023,2025)].copy();choices=[]
    for year in (2023,2024,2025):
        prior=pred[(pred.season<year)&pred['home won'].isin([0.,1.])];scores={a:float(s.loss(prior['home won'].to_numpy(),prior[a]).mean()) for a in ARMS};choice=min(scores,key=lambda a:(scores[a],a));held.loc[held.season==year,'selected']=held.loc[held.season==year,choice];choices.append({'season':year,'chosen':choice,'prior_losses':scores})
    held['market']=held.q;held['tail']=(abs(fs['production'].loc[held.index,['pass_ho','pass_ad','pass_ao','pass_hd']])>2).any(axis=1)
    reference=pd.read_csv(ROOT/'research/production_adoption_results/historical_reproduction.csv').set_index('game_id');prob_err=float(abs(held.production.to_numpy()-reference.loc[held.game_id,'production_probability'].to_numpy()).max())
    if prob_err>1e-7:raise ValueError('Prediction reproduction failed')
    current=[];fits={};contributions=[]
    archive=ROOT/'research/shrinkage_results/archived_current_inputs.jsonl'
    for r in map(json.loads,archive.read_text().splitlines()):
        ix=f.index[f.game_id==r['game_id']][0];item={'game_id':r['game_id'],'generated_utc':r['generated_utc'],'archived_probability':r['model_wp'],'market':r['market_no_vig_wp']}
        for a in ARMS:
            ff=fs[a];key=(r['season'],r['week'],a)
            if key not in fits:fits[key]=s.fit(ff[m.before(ff,*key[:2])],*key[:2])
            row=pd.DataFrame([{**r['model_inputs'],'q':r['market_no_vig_wp']}])
            for c in [f'd__{role}__rates_core__{STAT}' for role in ('for','allowed')]+s.CONTEXTS:row[c]=ff.loc[ix,c]
            item[a]=float(s.predict(row,fits[key])[0])
            fitted=fits[key]
            impact=row[fitted['names']].to_numpy(float)[0]/np.array(fitted['scale'])*np.array(fitted['beta'])
            contributions.append({'game_id':r['game_id'],'arm':a,**{c:float(ff.loc[ix,c]) for c in ['pass_ho','pass_ad','pass_ao','pass_hd']},**dict(zip(fitted['names'],impact.tolist()))})
        current.append(item)
    ce=max(abs(r['production']-r['archived_probability']) for r in current)
    if ce>1e-7:raise ValueError('Archive reproduction failed')
    info=summarize(held);info.update({'basis':'Exposed historical development, not forward evidence','revision':m.REVISION,'selections':choices,'feature_max_error':error,'historical_max_error':prob_err,'archive_max_error':ce,'all_fits_prior_week':all((r['training_max_season'],r['training_max_week'])<(r['evaluation_season'],r['evaluation_week']) for r in audit)})
    refs=pd.concat(refs)
    if not ((refs.max_reference_season<refs.season)|((refs.max_reference_season==refs.season)&(refs.max_reference_week<refs.week))).all():raise ValueError('Future reference')
    if pd.DataFrame(audit).groupby(['evaluation_season','evaluation_week']).training_games.nunique().max()!=1:raise ValueError('Training cohort mismatch')
    pd.DataFrame(contributions).to_csv(out/'current_contributions.csv',index=False)
    (out/'current_fits.json').write_text(json.dumps({str(k):v for k,v in fits.items()},indent=2)+'\n')
    refs.to_csv(out/'reference_audit.csv',index=False);pd.DataFrame(audit).to_csv(out/'fit_audit.csv',index=False);held.to_csv(out/'heldout_predictions.csv',index=False);pd.DataFrame(current).to_csv(out/'current_counterfactuals.csv',index=False)
    (out/'results.json').write_text(json.dumps(info,indent=2,allow_nan=False)+'\n')
    src=[Path(__file__),ROOT/'research/PROFILE_ROBUSTNESS.md',ROOT/'nfl_model.py',pack,sp,archive]
    (out/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in src},indent=2)+'\n')
    lines=['# Passing profile robustness results','','Basis: exposed historical development; not native forward evidence.',f"\n{info['bets']} common flat 1u bets; {info['proper_games']} binary scores.",'','| Arm | Units | ROI ± SE | Market-null ROI | LL | Brier |','|---|---:|---:|---:|---:|---:|']
    for r in info['results']:lines.append(f"| {r['arm']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} | {100*r['null_roi']:+.2f}% | {r['log_loss']:.6f} | {r['brier']:.6f} |")
    lines+=['','| Arm | ROI change [CI], pp | LL gain [CI] | Side flips |','|---|---:|---:|---:|']
    for r in info['comparisons']:
        lo,hi=r['roi_delta_ci'];ll,lh=r['ll_gain_ci'];lines.append(f"| {r['arm']} | {100*r['roi_delta']:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}] | {r['ll_gain']:+.6f} [{ll:+.6f}, {lh:+.6f}] | {r['side_flips']} |")
    lines+=['','Annual results, diagnostic slices, prior-season selections, cutoff audits and support counts accompany this report in results.json and CSVs. Fixed comparisons use 98.75% intervals; selected uses 95%. Intervals omit design-selection uncertainty.','',f'Reproduction errors: features {error:.3g}; historical predictions {prob_err:.3g}; archived forecasts {ce:.3g}.','','## Archived SF at SEA','','| Arm | SEA probability |','|---|---:|']
    for r in current:
        if r['game_id']=='2026_05_SF_SEA':
            for a in [*ARMS,'market']:lines.append(f'| {a} | {100*r[a]:.2f}% |')
    lines+=['','## Annual results','','| Arm | Season | Units | ROI | LL |','|---|---:|---:|---:|---:|']
    for r in info['by_season']:lines.append(f"| {r['arm']} | {r['season']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% | {r['log_loss']:.6f} |")
    lines+=['','## Diagnostic slices','','| Arm | Slice | Binary games | LL | Units |','|---|---|---:|---:|---:|']
    for r in info['slices']:lines.append(f"| {r['arm']} | {r['slice']} | {r['binary_games']} | {r['log_loss']:.6f} | {r['units']:+.2f} |")
    lines+=['','## Prior-season log-loss selection','']+[f"- {r['season']}: {r['chosen']}" for r in choices]
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(info['results'],indent=2),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output-dir',type=Path,default=ROOT/'research/profile_robustness_results');run(ap.parse_args().output_dir)
