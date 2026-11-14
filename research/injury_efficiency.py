"""Saved-report injury -> efficiency -> frozen win model -> median-map prototype."""
import json,sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit,logit
import injury_saved_inputs as s
ROOT=s.ROOT;sys.path.insert(0,str(ROOT))
import nfl_model as m
import fixed_bands as fb
OUT=ROOT/'research/injury_efficiency_results'
KEYS=['off_fd','off_int','def_fd','def_int','def_penalty']
TERMS=['d__for__rates_core__first_down_rate','d__for__rates_core__interception_pct','d__allowed__rates_core__first_down_rate','d__allowed__rates_core__interception_pct','d__allowed__rates_core__penalty_yards_per_game']

def rate(h,w):
 def ratio(n,d):return float(w@h[n].to_numpy())/float(w@h[d].to_numpy())*100
 return np.array([ratio('first_downs','plays'),ratio('interceptions','pass_attempts'),ratio('opp_first_downs','opp_plays'),ratio('opp_interceptions','opp_pass_attempts'),float(w@h.opp_penalty_yards)/sum(w)])

def ridge_fit(x,y):
 mu=x.mean(0);sd=x.std(0);sd[sd<1e-8]=1
 z=np.column_stack([np.ones(len(x)),(x-mu)/sd]);pen=np.diag([0]+[10]*x.shape[1])
 b=np.linalg.solve(z.T@z+pen,z.T@y)
 return b,mu,sd

def efficiency_adjustment(fresh,b,scale,baseline):
 delta=(np.asarray(fresh)/scale[:12])@b[1:13]
 adjusted=np.asarray(baseline)+delta
 adjusted[:4]=np.clip(adjusted[:4],0,100);adjusted[4]=max(adjusted[4],0)
 return adjusted-baseline

def propagate_probability(inputs,fit,q):
 score=logit(q)+sum(inputs[n]*beta/scale for n,beta,scale in zip(fit['names'],fit['beta'],fit['scale']))
 return float(m.favorite_penalized_wp([expit(score)],[q],fit['recipe'].get('favorite_penalty',1.))[0])

def run():
 OUT.mkdir(exist_ok=True)
 boxes=pd.read_csv(ROOT/'research/form_windows_inputs/boxes.csv');boxes=boxes[boxes.season<2026]
 cachefile=OUT/'boxes_2026.csv.gz'
 if cachefile.exists():current=pd.read_csv(cachefile)
 else:
  raw=pd.read_csv(ROOT.parent/'pressure_inputs/play_by_play_2026.csv.gz',low_memory=False)
  schedule=pd.read_parquet(ROOT/'data/lock_inputs/schedules.parquet');schedule=schedule[(schedule.season==2026)&schedule.game_type.eq('REG')]
  current=m.aggregate_boxscores(raw,schedule,2026);current.to_csv(cachefile,index=False,compression={'method':'gzip','mtime':0})
 boxes=pd.concat([boxes,current],ignore_index=True)
 opp=boxes[['game_id','team','plays','pass_attempts','first_downs','interceptions','penalty_yards']].rename(columns={'team':'opponent',**{k:'opp_'+k for k in ['plays','pass_attempts','first_downs','interceptions','penalty_yards']}})
 boxes=boxes.merge(opp,on=['game_id','opponent'],validate='one_to_one')
 windows=s.SnapWindows(pd.read_parquet(ROOT/'data/lock_inputs/snaps.parquet'))
 inj=pd.read_parquet(ROOT/'data/lock_inputs/inj.parquet');im={(int(y),int(w),t):q[['gsis_id','report_status']].rename(columns={'report_status':'status'}).to_dict('records') for (y,w,t),q in inj.groupby(['season','week','team'])}
 av=pd.read_parquet(ROOT/'data/lock_inputs/availability.parquet');states={(int(r.season),int(r.week),r.team):r.injury_report for r in av.itertuples()}
 burdens={}
 for r in boxes.itertuples():
  if states.get((r.season,r.week,r.team))!='final':continue
  try:b,_=s.burden(windows,r.team,r.season,r.week,im.get((r.season,r.week,r.team),[]));burdens[r.game_id,r.team]=np.array([b[g] for g in s.GROUPS])
  except ValueError:pass
 cache={}
 def profile(team,year,week):
  key=(team,year,week)
  if key in cache:return cache[key]
  before=(boxes.season<year)|((boxes.season==year)&(boxes.week<week));league=boxes[before&(boxes.season>=year-5)];h=league[league.team==team].sort_values(['season','week','game_id'])
  if len(h)<4:raise ValueError('Too little history')
  wt=np.exp2(-np.arange(len(h)-1,-1,-1)/8)*.5**(year-h.season.to_numpy())
  # League pseudo-games preserve count-ratio profiles rather than averaging percentages.
  counts=['plays','pass_attempts','first_downs','interceptions','opp_plays','opp_pass_attempts','opp_first_downs','opp_interceptions','opp_penalty_yards']
  prior=pd.DataFrame([{c:league[c].mean() for c in counts}]);hh=pd.concat([h[prior.columns],prior],ignore_index=True);eff=rate(hh,np.r_[wt,4.])
  known=[(i,burdens.get((r.game_id,team))) for i,r in enumerate(h.itertuples())];known=[(i,b) for i,b in known if b is not None]
  coverage=sum(wt[i] for i,b in known)/sum(wt)
  eligible_ids=set(league.game_id)
  lb=[b for (gid,t),b in burdens.items() if gid in eligible_ids]
  avg=np.mean(lb,axis=0) if lb else np.zeros(6)
  exposure=(sum((wt[i]*b for i,b in known),start=np.zeros(6))+4*avg)/(sum(wt[i] for i,b in known)+4)
  cache[key]=(eff,exposure,coverage);return cache[key]
 full=pd.read_parquet(ROOT/'data/lock_inputs/schedules.parquet').set_index('game_id')
 X=[];Y=[];train_receipts=[]
 for r in boxes[boxes.season.between(2020,2025)].itertuples():
  if (r.game_id,r.team) not in burdens or (r.game_id,r.opponent) not in burdens:continue
  try:own,old,cov=profile(r.team,r.season,r.week);op,opold,ocov=profile(r.opponent,r.season,r.week)
  except ValueError:continue
  if min(cov,ocov)<.9:continue
  home=float(full.home_team.get(r.game_id,'')==r.team)
  row=pd.DataFrame([r._asdict()]);actual=rate(row,np.ones(1))
  X.append(np.r_[burdens[r.game_id,r.team]-old,burdens[r.game_id,r.opponent]-opold,home,op]);Y.append(actual-own);train_receipts.append((r.game_id,r.team,r.season,r.week))
 X=np.array(X);Y=np.array(Y);b,mu,sd=ridge_fit(X,Y)
 pd.DataFrame(train_receipts,columns=['game_id','team','season','week']).to_csv(OUT/'training_cutoffs.csv',index=False)
 coef=pd.DataFrame(b[1:12+1]/sd[:12,None],index=['own_'+g for g in s.GROUPS]+['opponent_'+g for g in s.GROUPS],columns=KEYS);coef.to_csv(OUT/'efficiency_weights.csv')
 pd.DataFrame(np.column_stack([X,Y]),columns=['fresh_own_'+g for g in s.GROUPS]+['fresh_opponent_'+g for g in s.GROUPS]+['home']+['opponent_'+k for k in KEYS]+['target_'+k for k in KEYS]).to_csv(OUT/'training_values.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 (OUT/'stage_fit.json').write_text(json.dumps(dict(coefficients=b.tolist(),training_means=mu.tolist(),training_scales=sd.tolist()),indent=2)+'\n')
 reports=s.read_jsonl(ROOT/'research/injury_weight_inputs/selected_reports.jsonl');by={(r['game_id'],r['team']):r for r in reports}
 games=pd.read_csv(ROOT/'research/injury_weight_inputs/saved_reports_2026.csv');native=s.read_jsonl(ROOT/'data/forward_predictions.jsonl');rules={(r['season'],r['week']):r for r in json.load(open(ROOT/'data/latest/fixed_band_rules.json'))}
 out=[];effrows=[]
 for r in games.itertuples():
  eligible=[v for v in native if v['game_id']==r.game_id and len(v.get('coefficient_fit',{}).get('names',[]))==10 and s.aware_time(v['generated_utc'])<=s.aware_time(r.cutoff_utc)]
  if not eligible:continue
  v=max(eligible,key=lambda v:v['generated_utc']);fit=v['coefficient_fit'];assert (fit['training_max_season'],fit['training_max_week_in_latest_season'])<(2026,r.week);q=v.get('market_no_vig_wp',v['market_wp']);original=v['model_inputs'].copy();changes={}
  for team,other in [(r.home,r.away),(r.away,r.home)]:
   own,old,cov=profile(team,2026,r.week);op,opold,ocov=profile(other,2026,r.week)
   now,_=s.burden(windows,team,2026,r.week,by[r.game_id,team]['parsed']['rows']);oppnow,_=s.burden(windows,other,2026,r.week,by[r.game_id,other]['parsed']['rows'])
   fresh=np.r_[np.array([now[g] for g in s.GROUPS])-old,np.array([oppnow[g] for g in s.GROUPS])-opold]
   changes[team]=efficiency_adjustment(fresh,b,sd,own)
   actual=rate(boxes[(boxes.game_id==r.game_id)&(boxes.team==team)],np.ones(1))
   for k,key in enumerate(KEYS):effrows.append(dict(actual_efficiency=actual[k],game_id=r.game_id,team=team,efficiency=key,baseline_profile=own[k],injury_change=changes[team][k],history_coverage=cov))
  changed=original.copy()
  for k,term in enumerate(TERMS):changed[term]+=changes[r.home][k]-changes[r.away][k]
  p0=propagate_probability(original,fit,q);p1=propagate_probability(changed,fit,q);assert abs(p0-v['model_wp'])<1e-9
  rule=rules[2026,r.week];mapped=fb.apply(m.implied_spread([p0,p1]),rule)
  out.append(dict(game_id=r.game_id,week=r.week,home=r.home,away=r.away,result=r.result,spread_line=v['spread_line'],baseline_wp=p0,adjusted_wp=p1,baseline_raw_margin=float(m.implied_spread([p0])[0]),adjusted_raw_margin=float(m.implied_spread([p1])[0]),baseline_median=mapped[0],adjusted_median=mapped[1],saved_generated_utc=v['generated_utc']))
 d=pd.DataFrame(out);d.to_csv(OUT/'predictions.csv',index=False);pd.DataFrame(effrows).to_csv(OUT/'efficiency_changes.csv',index=False)
 scores=[]
 for arm in ['baseline','adjusted']:
  grade,u=fb.grade(d,d[arm+'_median']);scores.append(dict(arm=arm,n=len(d),wins=int(sum(grade=='W')),losses=int(sum(grade=='L')),pushes=int(sum(grade=='P')),units=float(u.sum()),mae=float(abs(d.result-d[arm+'_median']).mean())))
 info=dict(training_team_games=len(X),training_max_season=max(x[2] for x in train_receipts),scores=scores,median_changes=int(sum(d.baseline_median!=d.adjusted_median)),pick_changes=int(sum(fb.pick(d.baseline_median,d.spread_line)!=fb.pick(d.adjusted_median,d.spread_line))))
 (OUT/'results.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info,indent=2))
if __name__=='__main__':run()
