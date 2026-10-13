"""Read-only assessment of the frozen prospective v1.16 cohort."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=ROOT/'research/forward_v116_protocol.json'
OUT=ROOT/'research/forward_v116_assessment_results'


def utc(value):
    stamp=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError('Timezone required')
    return stamp.astimezone(dt.timezone.utc)


def load_protocol(path=PROTOCOL):
    envelope=json.loads(Path(path).read_text());rules=envelope['rules']
    canonical=json.dumps(rules,sort_keys=True,separators=(',',':')).encode()
    if hashlib.sha256(canonical).hexdigest()!=envelope['rules_sha256']:raise ValueError('Frozen protocol hash mismatch')
    document=ROOT/'research/FORWARD_V116_COMPARISON.md'
    if hashlib.sha256(document.read_bytes()).hexdigest()!=rules['protocol_document_sha256']:raise ValueError('Frozen protocol document changed')
    return rules,envelope['rules_sha256']


def prices(home,away):
    a,b=float(home),float(away)
    if not np.isfinite([a,b]).all() or min(abs(a),abs(b))<100:raise ValueError('Invalid moneylines')
    implied=lambda x:-x/(-x+100) if x<0 else 100/(x+100)
    x,y=implied(a),implied(b)
    return x/(x+y)


def cohort(records,grades,rules,asof):
    start=utc(rules['start_utc']);asof=utc(asof)
    matching=[];excluded=[];changes=[]
    for record in records:
        r=dict(record)
        try:
            generated=utc(r['generated_utc']);kickoff=utc(r['kickoff_utc'])
        except (KeyError,ValueError,TypeError):
            excluded.append({'game_id':r.get('game_id'),'reason':'invalid_timestamp'});continue
        if generated>asof:continue
        sig=str(r.get('experiment','')).split(':')[0]
        matches=(r.get('revision')==rules['revision'] and sig==rules['config_signature'] and r.get('recipe')==rules['recipe'])
        if not matches:
            excluded.append({'game_id':r.get('game_id'),'reason':'other_experiment'})
            if start<generated<kickoff:changes.append(generated)
            continue
        r['_generated']=generated;r['_kickoff']=kickoff;matching.append(r)
    stop=min(changes) if changes else None
    # First matching native lock is authoritative, even when it predates the freeze.
    first={}
    for r in sorted(matching,key=lambda x:(x['_generated'],x['game_id'])):
        if r['game_id'] in first:
            excluded.append({'game_id':r['game_id'],'reason':'later_duplicate_lock'});continue
        first[r['game_id']]=r
    result_map={}
    for game,g in grades.groupby('game_id') if len(grades) else []:
        settled=g[g.status.isin(['graded','tie'])]
        values=pd.to_numeric(settled.result,errors='coerce').dropna().unique()
        if len(values)>1:raise ValueError('Conflicting final grades '+game)
        if len(values):result_map[game]=float(values[0])
    rows=[]
    for game,r in first.items():
        reason=None
        if r['_generated']<=start:reason='locked_before_freeze'
        elif r['_generated']>=r['_kickoff']:reason='not_pregame'
        elif stop and r['_generated']>=stop:reason='enrollment_stopped_after_recipe_change'
        else:
            try:
                q=prices(r['home_moneyline'],r['away_moneyline']);p=float(r['model_wp'])
                if not np.isfinite(p) or not 0<p<1:raise ValueError('Invalid probability')
            except (KeyError,ValueError,TypeError):reason='invalid_price_or_probability'
            fit=r.get('coefficient_fit') or {}
            cutoff=(fit.get('training_max_season',9999),fit.get('training_max_week_in_latest_season',9999))
            if cutoff>=(r['season'],r['week']):reason='missing_or_nonprior_fit_cutoff'
            injury=r.get('injury_report') or {}
            if not (injury.get('home')=='final' and injury.get('away')=='final') and (r['_kickoff']-r['_generated']).total_seconds()>21600:
                reason='injury_gate_not_met'
        if reason:
            excluded.append({'game_id':game,'reason':reason});continue
        result=result_map.get(game,np.nan)
        rows.append({'game_id':game,'season':r['season'],'week':r['week'],'home':r['home'],'away':r['away'],
                     'generated_utc':r['_generated'].isoformat(),'kickoff_utc':r['_kickoff'].isoformat(),
                     'model_wp':p,'q':q,'home_moneyline':r['home_moneyline'],'away_moneyline':r['away_moneyline'],
                     'result':result,'status':'pending' if not np.isfinite(result) else ('tie' if result==0 else 'graded')})
    frame=pd.DataFrame(rows)
    if len(frame):frame=frame.sort_values(['kickoff_utc','game_id']).reset_index(drop=True)
    return frame,excluded,stop.isoformat() if stop else None


def cluster_ci(values,groups,level,rules):
    v=np.asarray(values,float)
    if len(v)==0:return None
    z=pd.DataFrame({'v':v,'group':groups}).groupby('group').v.agg(['sum','count'])
    if len(z)<2:return None
    rng=np.random.default_rng(rules['bootstrap_seed']);ix=rng.integers(0,len(z),(rules['bootstrap_reps'],len(z)))
    draws=z['sum'].to_numpy()[ix].sum(axis=1)/z['count'].to_numpy()[ix].sum(axis=1)
    tail=(1-level)/2
    return np.quantile(draws,[tail,1-tail]).tolist()


def probability_summary(frame,rules):
    f=frame[frame.status=='graded'].copy() if len(frame) else frame
    if len(f)==0:return {'games':0,'ll_gain':None,'brier_gain':None,'ll_ci':None,'brier_ci':None}
    y=(f.result>0).to_numpy(float);p=f.model_wp.to_numpy();q=f.q.to_numpy()
    ll=lambda z:-(y*np.log(z)+(1-y)*np.log1p(-z))
    gain=ll(q)-ll(p);brier=(q-y)**2-(p-y)**2
    groups=(f.season.astype(str)+'_'+f.week.astype(str)).to_numpy()
    return {'games':len(f),'market_ll':float(ll(q).mean()),'model_ll':float(ll(p).mean()),
            'll_gain':float(gain.mean()),'ll_ci':cluster_ci(gain,groups,rules['probability_interval_level'],rules),
            'market_brier':float(((q-y)**2).mean()),'model_brier':float(((p-y)**2).mean()),
            'brier_gain':float(brier.mean()),'brier_ci':cluster_ci(brier,groups,.95,rules)}


def financial_summary(frame,rules):
    if not len(frame):return {'games':0,'roi':None,'gate_intervals':{}}
    f=frame[frame.status!='pending'].copy()
    f=f[(abs(f.model_wp-.5)>rules['decision_tolerance'])&(abs(f.q-.5)>rules['decision_tolerance'])]
    if not len(f):return {'games':0,'roi':None,'gate_intervals':{}}
    home=f.model_wp>.5;favhome=f.q>.5;win=f.result>0;tie=f.result==0
    price=np.where(home,f.home_moneyline,f.away_moneyline);favprice=np.where(favhome,f.home_moneyline,f.away_moneyline)
    payout=lambda x:np.where(x<0,100/abs(x),x/100)
    units=np.where(tie,0.,np.where(home==win,payout(price),-1.))
    fav=np.where(tie,0.,np.where(favhome==win,payout(favprice),-1.))
    qside=np.where(home,f.q,1-f.q);null=qside*payout(price)-(1-qside)
    groups=(f.season.astype(str)+'_'+f.week.astype(str)).to_numpy()
    return {'games':len(f),'wins':int(((home==win)&~tie).sum()),'losses':int(((home!=win)&~tie).sum()),
            'pushes':int(tie.sum()),'units':float(units.sum()),'roi':float(units.mean()),
            'roi_se':float(units.std(ddof=1)/np.sqrt(len(f))) if len(f)>1 else None,
            'favorite_units':float(fav.sum()),'favorite_roi':float(fav.mean()),'market_null_roi':float(null.mean()),
            'gate_intervals':{name:cluster_ci(value,groups,rules['financial_interval_level'],rules)
                for name,value in [('net_roi',units),('versus_favorite',units-fav),('versus_market_null',units-null)]}}


def assess(frame,rules,formal=False):
    close=frame[np.maximum(frame.q,1-frame.q)<rules['close_threshold']] if len(frame) else frame
    probability=probability_summary(frame,rules);close_probability=probability_summary(close,rules)
    financial=financial_summary(frame,rules)
    status='descriptive_only'
    if formal:
        cis=list(financial['gate_intervals'].values())
        status='financial_support' if len(cis)==3 and all(x is not None and x[0]>0 for x in cis) else 'unresolved'
        if status=='unresolved' and any(x is not None and x[1]<0 for x in cis):status='adverse_component'
    def support(z):
        ci=z['ll_ci']
        return 'descriptive_only' if not formal else ('supported' if ci and ci[0]>0 else ('adverse' if ci and ci[1]<0 else 'unresolved'))
    return {'unique_games':len(frame),'settled_games':int((frame.status!='pending').sum()) if len(frame) else 0,
            'ties':int((frame.status=='tie').sum()) if len(frame) else 0,'financial':financial,
            'probability':probability,'close_probability':close_probability,'financial_assessment':status,
            'overall_probability_assessment':support(probability),'close_probability_assessment':support(close_probability),
            'seasons':{str(y):probability_summary(g,rules) for y,g in frame.groupby('season')} if len(frame) else {},
            'bands':{f'{lo:.1f}–{hi:.1f}':probability_summary(frame[(np.maximum(frame.q,1-frame.q)>=lo)&(np.maximum(frame.q,1-frame.q)<hi)],rules)
                     for lo,hi in zip([.5,.6,.7,.8,.9],[.6,.7,.8,.9,1.0000001])} if len(frame) else {}}


def checkpoints(frame,rules,asof):
    ready=[];prefix=0
    if len(frame):
        for status in frame.status:
            if status=='pending':break
            prefix+=1
    for n in rules['monitoring_counts']+[rules['formal_count']]:
        if prefix>=n:ready.append({'id':f'games_{n}','formal':n==rules['formal_count'],'frame':frame.iloc[:n]})
    season=rules['season_review'];g=frame[(frame.season==season['season'])&(frame.week<=season['max_regular_week'])] if len(frame) else frame
    if utc(asof)>=utc(season['not_before_utc']) and len(g) and (g.status!='pending').all():
        ready.append({'id':f"season_{season['season']}_regular",'formal':False,'frame':g})
    return prefix,ready


def save_checkpoint(path,payload):
    content=json.dumps(payload,indent=2,allow_nan=False)+'\n'
    if path.exists() and path.read_text()!=content:raise ValueError('Checkpoint changed; preserve old assessment and issue an explicit correction: '+path.name)
    if not path.exists():path.write_text(content)


def run(args):
    rules,hashvalue=load_protocol(args.protocol);out=Path(args.output_dir).resolve()
    if any(out==p or p in out.parents for p in [ROOT/'data',ROOT/'public']):raise ValueError('Protected production output')
    out.mkdir(parents=True,exist_ok=True);folder=out/'checkpoints';folder.mkdir(exist_ok=True)
    asof=args.asof or dt.datetime.now(dt.timezone.utc).isoformat()
    records=[json.loads(x) for x in Path(args.ledger).read_text().splitlines() if x.strip()]
    grades=pd.read_csv(args.grades);frame,excluded,stop=cohort(records,grades,rules,asof)
    prefix,ready=checkpoints(frame,rules,asof)
    assessments=[]
    for item in ready:
        payload={'protocol_id':rules['id'],'rules_sha256':hashvalue,'checkpoint_id':item['id'],
                 'sample_game_ids':item['frame'].game_id.tolist(),'sample_rows':item['frame'].to_dict('records'),
                 'assessment':assess(item['frame'],rules,item['formal'])}
        save_checkpoint(folder/(item['id']+'.json'),payload);assessments.append(payload)
    result={'protocol_id':rules['id'],'rules_sha256':hashvalue,'start_utc':rules['start_utc'],'asof_utc':asof,
            'enrollment_stopped_utc':stop,'eligible_locks':len(frame),'settled_prefix':prefix,
            'pending':int((frame.status=='pending').sum()) if len(frame) else 0,
            'exclusion_counts':pd.Series([x['reason'] for x in excluded],dtype=str).value_counts().to_dict(),
            'descriptive_current':assess(frame,rules),'ready_checkpoints':assessments,
            'source_hashes':{str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [args.ledger,args.grades]},
            'assessor_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'automatic_model_changes':False}
    (out/'assessment.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    pd.DataFrame(excluded).to_csv(out/'exclusions.csv',index=False)
    lines=['# Frozen prospective v1.16 assessment','',f"Protocol `{rules['id']}`; starts {rules['start_utc']}; assessed {asof}.",
        f"Rules SHA-256: `{hashvalue}`.",'',f"Eligible new locks: {len(frame)}. Settled kickoff-ordered prefix: {prefix}. Pending: {result['pending']}.",
        '',f"Exclusions: {result['exclusion_counts']}",'','Ready checkpoints: '+(', '.join(x['checkpoint_id'] for x in assessments) or 'none')+'.',
        '', '100/250/500 and season-end reviews are descriptive. The single formal checkpoint is 1,000 settled eligible games. No individual result or interim estimate can change production.',
        '', 'Financial and probability support are assessed separately under the frozen rules. Historical captures and reconstructed forecasts cannot enter the prospective cohort.',
        '', 'Full metrics, confidence bands, season summaries and checkpoint decisions are in assessment.json. No production or native ledger changes were made.','']
    if stop:lines.append('Enrollment stopped after a different production recipe/config appeared at '+stop+'.')
    (out/'REPORT.md').write_text('\n'.join(lines));print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=PROTOCOL)
    parser.add_argument('--ledger',type=Path,default=ROOT/'data/forward_predictions.jsonl')
    parser.add_argument('--grades',type=Path,default=ROOT/'data/forward_ledger.csv')
    parser.add_argument('--output-dir',type=Path,default=OUT)
    parser.add_argument('--asof')
    run(parser.parse_args())
