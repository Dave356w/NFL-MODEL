"""Production v1.23 injury-to-efficiency adapter. Frozen pre-2026 stage weights.
No research imports, point penalties, current-game labels, or individual talent ratings.
"""
import hashlib
import json
import numpy as np
import pandas as pd
POLICY='injury-efficiency-2026-11-13-v1'
GROUPS=['OL','WRTE','RB','DL','LB','DB']
STATUS={'Out':1.,'Doubtful':1.,'Questionable':.25,'Available':0.}
POSITION_GROUP={**dict.fromkeys(['T','G','C','OL','OT','OG','LT','RT','LG','RG'],'OL'),**dict.fromkeys(['WR','TE'],'WRTE'),**dict.fromkeys(['RB','FB','HB'],'RB'),**dict.fromkeys(['DE','DL','DT','NT','EDGE'],'DL'),**dict.fromkeys(['LB','ILB','OLB','MLB'],'LB'),**dict.fromkeys(['CB','DB','S','SS','FS','SAF'],'DB')}
TERMS=['d__for__rates_core__first_down_rate','d__for__rates_core__interception_pct','d__allowed__rates_core__first_down_rate','d__allowed__rates_core__interception_pct','d__allowed__rates_core__penalty_yards_per_game']
FROZEN={'coefficients': [[-0.3461660245279433, -0.02144446618663725, -0.4583352724404183, -0.0072759897633749735, -1.5695929831599618], [-0.14391391402906917, -0.0062705251684785765, -0.29622037901257336, 0.03571217561180927, -0.6124518269999847], [-0.19048441868760868, -0.06479558766562979, 0.18296896651983102, 0.004138163282453319, -0.23952520758926296], [-0.059443399954065765, 0.014554232743664361, -0.18282105811282343, -0.09823906142543881, 0.25302021336000785], [0.13671970146738896, 0.040049838802396216, 0.19967908539716167, -0.04717272183056863, -0.36618619098575705], [-0.079103785778619, 0.04198309541596197, 0.22854422344181285, 0.031401645839948866, -0.7004427011973992], [0.13048966211074173, -0.019573916344730977, 0.5068798680651456, -0.0533304261023252, -0.3276080150261796], [-0.2966093252014876, 0.03358625213884207, -0.14100223172387474, -0.006621388728917221, -0.16682163186215287], [0.13550580668714102, 0.011491387006478932, -0.13852844768419934, -0.05424402513229401, -0.4099146959525161], [-0.1742319526825345, -0.11615747786239158, -0.06458007871575382, 0.01738993083479487, -0.19844586569295652], [0.21080598207604476, -0.05069904833034602, 0.11310212399605626, 0.05330759799526653, 0.16022687823450213], [0.2158957818672991, 0.013749270422210871, -0.09507307488721607, 0.01950590384190827, 0.7843964179940208], [0.5094626146080367, -0.05871105999304078, 0.09786130256407101, -0.020650161177474813, -0.4379706038820816], [0.6174628660597438, -0.029688428298208586, -0.6246339088852458, 0.024243059125469372, 1.6409691449764863], [-0.313048257698581, 0.10255212073828757, 1.7032140619457306, -0.11693205374652023, -0.29092678327054117], [-0.27906990127016296, 0.030402802168138517, -0.2582195782971846, 0.08884279115454548, -0.9645735296952463], [0.914083193805775, -0.12146302885794039, 0.04117915393950824, -0.02089652354319919, -1.0033682644260102], [-0.2964683201941912, 0.18711225276001878, 0.21884270948730222, -0.1304913458494657, -1.667358212472188], [0.26144825663251753, 0.026972040806682588, -0.11595187019040683, 0.16297178873657148, -0.38060702182330464]], 'training_means': [0.0027849937636609317, 0.0011079665344239894, 0.0029876647274881827, 0.0025043991944368915, 0.005381122731654113, 0.003563501379794234, 0.0027849937636609317, 0.001107966534423989, 0.002987664727488181, 0.002504399194436891, 0.005381122731654115, 0.003563501379794233, 0.5, 31.443541900679023, 2.276673953985481, 31.555711148591538, 2.2625054775622195, 51.02913301723145], 'training_scales': [0.07757639716501342, 0.07854204625505755, 0.13441858136965393, 0.06851513004084464, 0.09698898433269422, 0.08328090199562992, 0.07757639716501341, 0.07854204625505755, 0.13441858136965393, 0.06851513004084464, 0.09698898433269422, 0.08328090199562992, 0.5, 1.6939945696121006, 0.4864734043290938, 1.399383418394647, 0.49666347618324624, 4.871981791734483]}
def identity():
 return {'policy':POLICY,'training_max_season':2025,'sha256':hashlib.sha256(json.dumps(FROZEN,sort_keys=True).encode()).hexdigest()}
class SnapWindows:
    def __init__(self,snaps):
        s=snaps.copy();s['team']=s.team.replace({'LAR':'LA','STL':'LA','SD':'LAC','OAK':'LV'})
        s['unit']=s.position.map(POSITION_GROUP)
        self.teams={t:q for t,q in s.groupby('team')};self.cache={}

    def get(self,team,season,week):
        key=(team,int(season),int(week))
        if key in self.cache:return self.cache[key]
        if team not in self.teams:raise ValueError(f'No earlier snap source for {team}')
        s=self.teams[team]
        h=s[(s.season<season)|((s.season==season)&(s.week<week))]
        games=h[['season','week','game_id']].drop_duplicates().sort_values(['season','week','game_id'])
        current=games[games.season==season]
        use=(current if len(current)>=2 else games).tail(4)
        h=h[h.game_id.isin(use.game_id)].copy()
        h['role_snaps']=np.where(h.unit.isin(['OL','WRTE','RB']),h.offense_snaps,h.defense_snaps)
        counts=h[h.unit.isin(GROUPS)].groupby(['unit','gsis_id']).role_snaps.sum()
        denominator={u:float(counts.get(u,pd.Series(dtype=float)).sum()) for u in GROUPS}
        if any(n<=0 for n in denominator.values()):raise ValueError(f'Missing earlier positional snaps {key}')
        self.cache[key]=(counts,denominator)
        return self.cache[key]

def burden(windows,team,season,week,status_rows):
    counts,den=windows.get(team,season,week)
    severity={}
    for r in status_rows:
        if r.get('status') not in STATUS:continue
        pid=r.get('gsis_id')
        if pid:severity[pid]=max(severity.get(pid,0.),STATUS[r['status']])
    out={u:0. for u in GROUPS}
    known=set()
    for (unit,pid),n in counts.items():
        if pid in severity:
            out[unit]+=float(n)*severity[pid]/den[unit];known.add(pid)
    if any(v<0 or v>1+1e-10 for v in out.values()):raise ValueError('Invalid snap-weighted burden')
    unseen=sum(v>0 and pid not in known for pid,v in severity.items())
    return out,int(unseen)

def rate(h,w):
 def ratio(n,d):return float(w@h[n].to_numpy())/float(w@h[d].to_numpy())*100
 return np.array([ratio('first_downs','plays'),ratio('interceptions','pass_attempts'),ratio('opp_first_downs','opp_plays'),ratio('opp_interceptions','opp_pass_attempts'),float(w@h.opp_penalty_yards)/sum(w)])

def references(box,snaps,inj,availability,targets):
 """Build only prior-game references; no current/future outcome enters context."""
 window=SnapWindows(snaps);hist=box.copy()
 opp=hist[['game_id','team','plays','pass_attempts','first_downs','interceptions','penalty_yards']].rename(columns={'team':'opponent',**{k:'opp_'+k for k in ['plays','pass_attempts','first_downs','interceptions','penalty_yards']}})
 hist=hist.merge(opp,on=['game_id','opponent'],validate='one_to_one')
 states={(int(r.season),int(r.week),r.team):r.injury_report for r in availability.itertuples()}
 medical={(int(y),int(w),t):q[['gsis_id','report_status']].rename(columns={'report_status':'status'}).to_dict('records') for (y,w,t),q in inj.groupby(['season','week','team'])}
 burdens={}
 for r in hist.itertuples():
  if states.get((r.season,r.week,r.team))!='final':continue
  try:b,_=burden(window,r.team,r.season,r.week,medical.get((r.season,r.week,r.team),[]));burdens[r.game_id,r.team]=np.array([b[g] for g in GROUPS])
  except ValueError:continue
 out={}
 for r in targets.itertuples():
  team,y,w=r.team,int(r.season),int(r.week)
  try:
   league=hist[((hist.season<y)|((hist.season==y)&(hist.week<w)))&(hist.season>=y-5)]
   h=league[league.team==team].sort_values(['season','week','game_id'])
   if len(h)<4:raise ValueError('Insufficient prior games')
   wt=np.exp2(-np.arange(len(h)-1,-1,-1)/8)*.5**(y-h.season.to_numpy())
   counts=['plays','pass_attempts','first_downs','interceptions','opp_plays','opp_pass_attempts','opp_first_downs','opp_interceptions','opp_penalty_yards']
   prior=pd.DataFrame([{c:league[c].mean() for c in counts}]);eff=rate(pd.concat([h[counts],prior],ignore_index=True),np.r_[wt,4.])
   known=[(i,burdens.get((q.game_id,team))) for i,q in enumerate(h.itertuples())];known=[(i,b) for i,b in known if b is not None]
   coverage=sum(wt[i] for i,b in known)/sum(wt)
   if coverage<.9:raise ValueError('Insufficient prior medical-report coverage')
   ids=set(league.game_id);lb=[b for (gid,t),b in burdens.items() if gid in ids];avg=np.mean(lb,axis=0)
   exposure=(sum((wt[i]*b for i,b in known),start=np.zeros(6))+4*avg)/(sum(wt[i] for i,b in known)+4)
   player,den=window.get(team,y,w)
   shares={}
   for (unit,pid),n in player.items():shares.setdefault(pid,{})[unit]=float(n/den[unit])
   out[y,w,team]=dict(policy=POLICY,team=team,season=y,week=w,baseline=eff.tolist(),prior_burden=exposure.tolist(),shares=shares,
                     statuses=medical.get((y,w,team),[]),coverage=coverage,source_max_season=int(h.season.max()),source_max_week=int(h[h.season==h.season.max()].week.max()))
  except (ValueError,ZeroDivisionError) as exc:out[y,w,team]={'error':str(exc)}
 return out

def attach(frame,refs):
 out=frame.copy()
 for side in ['home','away']:
  out[side+'_injury_efficiency_reference']=[json.dumps(refs.get((int(r.season),int(r.week),getattr(r,side)),{'error':'Missing reference'}),sort_keys=True) for r in out.itertuples()]
 return out

def current_burden(ref,evidence):
 statuses={}
 for r in ref['statuses']:
  if r.get('gsis_id'):statuses[r['gsis_id']]=max(statuses.get(r['gsis_id'],0.),STATUS.get(r.get('status'),0.))
 for r in evidence.get('observations',[]):
  if r.get('field')=='report_status':statuses[r['gsis_id']]=STATUS[r['value']]
 values=np.zeros(6)
 for pid,weight in statuses.items():
  for group,share in ref['shares'].get(pid,{}).items():values[GROUPS.index(group)]+=weight*share
 if (values>1+1e-8).any():raise ValueError('Invalid current snap burden')
 return values

def apply(frame,replay=False):
 """Idempotent refresh: restore original inputs, then apply newest resolved facts."""
 out=frame.copy()
 for i,row in out.iterrows():
  if pd.notna(row.get('result')) and not replay:continue
  if int(row.get('season',0))<2026 and not replay:continue
  ko=row.get('kickoff_utc')
  if not ko and row.get('gameday') and row.get('gametime'):
   ko=pd.Timestamp(str(row['gameday'])+' '+str(row['gametime']),tz='America/New_York').tz_convert('UTC')
  if not replay and ko is not None and pd.notna(ko) and pd.Timestamp(ko)-pd.Timedelta(minutes=60)<pd.Timestamp('2026-11-13T21:32:30Z'):continue
  original_ready=row.get('injury_efficiency_original_ready')
  original_ready=bool(row.get('ready',False)) if original_ready is None or pd.isna(original_ready) else bool(original_ready)
  out.loc[i,'injury_efficiency_original_ready']=original_ready
  out.loc[i,'ready']=original_ready
  original=row.get('injury_efficiency_original_inputs')
  original=json.loads(original) if isinstance(original,str) and original else {n:float(row[n]) for n in TERMS}
  for n,v in original.items():out.loc[i,n]=v
  out.loc[i,'injury_efficiency_original_inputs']=json.dumps(original,sort_keys=True)
  try:
   refs={side:json.loads(row[side+'_injury_efficiency_reference']) for side in ['home','away']}
   ev={side:json.loads(row[side+'_availability_evidence']) if isinstance(row[side+'_availability_evidence'],str) else row[side+'_availability_evidence'] for side in ['home','away']}
   for side in refs:
    ref=refs[side]
    if ref.get('error'):raise ValueError(ref['error'])
    if (ref['source_max_season'],ref['source_max_week'])>=(int(row.season),int(row.week)):raise ValueError('Reference has target/future games')
    if not ev[side].get('report_complete') or ev[side].get('blockers'):raise ValueError('Availability unresolved')
   now={side:current_burden(refs[side],ev[side]) for side in refs};delta={}
   b=np.array(FROZEN['coefficients']);scale=np.array(FROZEN['training_scales'])
   for side,other in [('home','away'),('away','home')]:
    fresh=np.r_[now[side]-refs[side]['prior_burden'],now[other]-refs[other]['prior_burden']]
    base=np.array(refs[side]['baseline']);adjusted=base+(fresh/scale[:12])@b[1:13]
    adjusted[:4]=np.clip(adjusted[:4],0,100);adjusted[4]=max(adjusted[4],0);delta[side]=adjusted-base
   for k,n in enumerate(TERMS):out.loc[i,n]=original[n]+delta['home'][k]-delta['away'][k]
   audit=dict(**identity(),changes={side:delta[side].tolist() for side in delta},current_burden={side:now[side].tolist() for side in now},references=refs)
   out.loc[i,'injury_efficiency_ready']=True
  except (KeyError,TypeError,ValueError) as exc:
   out.loc[i,'ready']=False;out.loc[i,'injury_efficiency_ready']=False;audit=dict(**identity(),blocker=str(exc))
  out.loc[i,'injury_efficiency_audit']=json.dumps(audit,sort_keys=True)
 return out
