"""Read-only audit of immutable ATS locks against actual QB-position play order.

python research/qb_saved_pick_audit.py --output-dir PATH
No reconstructed lineup is substituted for a missing saved projection. Large
quality error means >=1 net yard/dropback versus realized efficiency, with >=15
starter dropbacks. This is descriptive game noise, not a causal QB talent label.
"""
import argparse
from pathlib import Path
import sys
import json
import hashlib
import re
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import nfl_model as m
import ats_locks
from research.qb_actual_starters import corrected_schedules,ORDER


def journal(path):
    if not path.exists(): return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def normalized(name):
    return re.sub('[^a-z0-9]','',str(name).lower().replace(' jr.','').replace(' iii','').replace(' ii',''))


def name_index(qb,schedules,roster):
    names={}
    def add(pid,name):
        if pd.notna(pid) and pd.notna(name): names.setdefault(normalized(name),set()).add(pid)
    for r in qb.itertuples(): add(r.gsis_id,r.name)
    for side in ('home','away'):
        for pid,name in schedules[[side+'_qb_id',side+'_qb_name']].itertuples(index=False,name=None): add(pid,name)
    for col in ('full_name','football_name'):
        if col in roster:
            for pid,name in roster[['gsis_id',col]].itertuples(index=False,name=None):add(pid,name)
    return names


def resolve_name(name,index,eligible=None):
    ids=index.get(normalized(name),set())
    if len(ids)>1 and eligible is not None: ids=ids & eligible
    return next(iter(ids)) if len(ids)==1 else None


def quality(qb,pid,year,week):
    prior_rows=qb[m.before(qb,year,week)&(qb.season>=year-m.MAX_HISTORY_SEASONS)&~qb.leader.astype(bool)]
    if prior_rows.dropbacks.sum()<=0:return np.nan,0.
    prior=prior_rows.net_yards.sum()/prior_rows.dropbacks.sum()
    h=qb[(qb.gsis_id==pid)&m.before(qb,year,week)&(qb.season>=year-1)].sort_values(['season','week','game_id'])
    wt=np.exp2(-np.arange(len(h)-1,-1,-1,dtype=float)/m.QB_HALF_LIFE)*np.power(m.OFFSEASON_RETENTION,year-h.season.to_numpy(float))
    n=float((wt*h.dropbacks).sum())
    return float(((wt*h.net_yards).sum()+m.QB_PRIOR_DROPBACKS*prior)/(n+m.QB_PRIOR_DROPBACKS)),n


def saved_lineup(lock,candidates,refreshes,historical):
    if lock.get('source_snapshot',{}).get('board_row'):
        return lock['source_snapshot']['board_row'],None,'saved recovery board'
    c=candidates.get(lock.get('candidate_sha256'))
    if c and c.get('availability'):return None,c['availability'],'exact locked candidate'
    for r in refreshes:
        if all(r.get(k)==lock.get(k) for k in ('game_id','revision','generated_utc')):
            return r['board'],None,'exact forecast refresh'
    for r in historical:
        manifest=r['manifest']
        if (manifest.get('generated_utc')==lock['generated_utc'] and manifest.get('revision')==lock['revision']
                and pd.Timestamp(r['commit_utc'])<=pd.Timestamp(lock['lock_at_utc'])):
            for board in r['rows']:
                if board['game_id']==lock['game_id']:
                    # Match saved spread and handicap too: timestamp alone is insufficient.
                    if abs(float(board['model_spread'])-float(lock['raw_spread']))>1e-4: continue
                    if abs(float(board['spread_line'])-float(lock['market_spread']))>1e-6: continue
                    return board,None,'exact historical board '+r['commit']
    return None,None,'missing at-lock QB evidence'


def record(sign):
    sign=np.asarray(sign);return f'{int((sign>0).sum())}-{int((sign<0).sum())}-{int((sign==0).sum())}'


def summarize(g):
    out={'n':len(g),'model_WLP':record(g.model_ats),'favorite_WLP':record(g.favorite_ats),'home_WLP':record(g.home_ats)}
    for col in ['model','favorite','home']:
        u=g[col+'_units'].to_numpy(float)
        out[col+'_units']=float(u.sum());out[col+'_roi']=float(u.mean())
        out[col+'_roi_se']=float(u.std(ddof=1)/np.sqrt(len(u))) if len(u)>1 else None
    for col in ['model_signed_error','market_signed_error','model_absolute_error','market_absolute_error','brier','market_brier']:
        out[col]=float(g[col].mean()) if g[col].notna().any() else None
    paired_scores=g[g.market_brier.notna()&g.brier.notna()]
    out['paired_brier_n']=len(paired_scores)
    out['paired_model_brier']=float(paired_scores.brier.mean()) if len(paired_scores) else None
    out['paired_market_brier']=float(paired_scores.market_brier.mean()) if len(paired_scores) else None
    diff=(g.model_units-g.favorite_units).to_numpy(float)
    out['paired_roi_gain']=float(diff.mean())
    # A week-cluster bootstrap, preserving paired game rows. Tiny cohorts stay unresolved.
    weeks=sorted(g.week.unique())
    if len(weeks)>=2:
        rng=np.random.default_rng(20261113)
        groups={w:g.loc[g.week.eq(w)] for w in weeks}
        vals=[]
        for _ in range(4000):
            chosen=[groups[w] for w in rng.choice(weeks,len(weeks),replace=True)]
            vals.append(sum((x.model_units-x.favorite_units).sum() for x in chosen)/sum(len(x) for x in chosen))
        out['paired_roi_gain_week_bootstrap_95']=list(np.quantile(vals,[.025,.975]))
    else: out['paired_roi_gain_week_bootstrap_95']=None
    return out


def audit(root=ROOT,historical_dir=None):
    data=root/'data'; inp=data/'lock_inputs'
    qb=pd.read_parquet(inp/'qb.parquet'); schedules=corrected_schedules(pd.read_parquet(inp/'schedules.parquet'))
    roster=pd.read_parquet(inp/'rost.parquet');idx=name_index(qb,schedules,roster)
    depth=pd.read_parquet(inp/'depth.parquet')
    depth['_t']=pd.to_datetime(depth.dt,utc=True)
    candidates={r['candidate_sha256']:r for r in journal(data/'ats_lock_candidates.jsonl')}
    refreshes=journal(data/'forecast_refreshes.jsonl')
    # This root's append-only lock store is the saved evidence basis. Do not use public replay picks.
    stores=[data]+ats_locks.runtime_stores(data)
    locks=[r for store in stores for r in journal(store/'ats_locks.jsonl')]
    for store in stores[1:]:
        candidates.update({r['candidate_sha256']:r for r in journal(store/'ats_lock_candidates.jsonl')})
        refreshes+=journal(store/'forecast_refreshes.jsonl')
    historical=[json.loads(p.read_text()) for p in sorted(historical_dir.glob('*.json'))] if historical_dir else []
    unique={}
    for r in locks:
        k=(r['revision'],r['game_id'])
        if k in unique and unique[k]!=r:raise ValueError('conflicting lock identity')
        unique[k]=r
    game_rows=[];team_rows=[]
    outcomes=schedules.set_index('game_id')
    for lock in unique.values():
        if lock['game_id'] not in outcomes.index:continue
        s=outcomes.loc[lock['game_id']]
        if pd.isna(s.result):continue
        board,av,source=saved_lineup(lock,candidates,refreshes,historical)
        states=[];errors=[]
        for side in ('home','away'):
            name=board.get(side+'_qb_expected') if board else (av or {}).get(side,{}).get('qb_expected')
            actual=s[side+'_qb_id'];actual_name=s[side+'_qb_name']
            blend=isinstance(name,str) and ' (Q) / ' in name
            team=s[side+'_team']
            eligible=set(qb.loc[qb.team.eq(team)&m.before(qb,int(s.season),int(s.week)),'gsis_id'])
            projected=resolve_name(name.split(' (Q) / ')[0] if isinstance(name,str) else name,idx,eligible)
            state='unknown' if projected is None or pd.isna(actual) else 'blend' if blend else 'correct' if projected==actual else 'wrong'
            states.append(state)
            eff,n=quality(qb,projected,int(s.season),int(s.week)) if projected else (np.nan,0.)
            observed=qb[(qb.game_id==s.name)&(qb.team==s[side+'_team'])&(qb.gsis_id==actual)]
            db=float(observed.dropbacks.sum());realized=float(observed.net_yards.sum()/db) if db>0 else np.nan
            err=eff-realized if state=='correct' and db>=15 else np.nan
            errors.append(err)
            cut=min(pd.Timestamp(lock['generated_utc']),pd.Timestamp(lock['kickoff_utc'])-pd.Timedelta(hours=24))
            chart=depth[(depth.season==s.season)&depth.team.eq(team)&(depth._t<=cut)]
            rank=np.nan; chart_time=None
            if len(chart):
                chart_time=chart._t.max()
                if cut-chart_time<=pd.Timedelta(days=7):
                    ranks=chart.loc[chart._t.eq(chart_time)&chart.gsis_id.eq(actual),'pos_rank']
                    rank=float(ranks.min()) if len(ranks) else np.nan
            prior=schedules[(schedules.season==s.season)&(schedules.week<s.week)&schedules.result.notna()]
            counts={}
            for si in ('home','away'):
                for pid in prior.loc[prior[si+'_team'].eq(s[side+'_team']),si+'_qb_id'].dropna():counts[pid]=counts.get(pid,0)+1
            incumbent=max(counts,key=counts.get) if counts else None
            team_rows.append(dict(game_id=s.name,revision=lock['revision'],week=int(s.week),side=side,team=s[side+'_team'],
                evidence=source,saved_qb=name,projected_id=projected,actual_qb=actual_name,actual_id=actual,actual_source=s[side+'_actual_source'],schedule_qb_id=s['schedule_'+side+'_qb_id'],
                selection=state,actual_depth_rank=rank,depth_snapshot_utc=chart_time,
                actual_differs_from_season_most_starts=actual!=incumbent if incumbent else None,
                pregame_efficiency=eff,effective_prior_dropbacks=n,realized_starter_dropbacks=db,realized_efficiency=realized,
                quality_overestimate=err,large_quality_error=bool(abs(err)>=1) if np.isfinite(err) else None))
        group=('wrong starter' if 'wrong' in states else 'unknown lineup' if 'unknown' in states else
               'questionable blend' if 'blend' in states else 'correct; large realized quality error' if any(abs(x)>=1 for x in errors if np.isfinite(x)) else
               'correct; quality unmeasurable' if not all(np.isfinite(x) for x in errors) else 'correct; smaller realized quality error')
        line=float(lock['market_spread']);pred=float(lock['fixed_band_spread']);actual_margin=float(s.result)
        selected=lock.get('selected_side');edge=actual_margin-line
        model_sign=np.sign(edge)*(1 if selected=='home' else -1) if selected in ('home','away') else np.nan
        # Match market favorite AND home on exactly this saved handicap. Pick'em favorites excluded, with counts retained.
        fav_sign=np.sign(edge)*(1 if line>0 else -1) if line!=0 else np.nan
        home_sign=np.sign(edge)
        unit=lambda x:np.nan if not np.isfinite(x) else 1/1.1 if x>0 else -1. if x<0 else 0.
        p=float(lock['model_wp']);market_p=float(board['market_wp']) if board and board.get('market_wp') else np.nan
        won=float(actual_margin>0)
        # Only use a market probability saved in the exact same forecast board.
        game_rows.append(dict(game_id=s.name,revision=lock['revision'],week=int(s.week),
            basis='recovered saved board' if lock.get('retro_locked') else 'native saved lock',
            group=group,evidence=source,home=s.home_team,away=s.away_team,selected_side=selected,
            market_spread=line,model_spread=pred,raw_spread=float(lock['raw_spread']),actual_home_margin=actual_margin,
            model_signed_error=pred-actual_margin,raw_model_signed_error=float(lock['raw_spread'])-actual_margin,market_signed_error=line-actual_margin,
            model_absolute_error=abs(pred-actual_margin),market_absolute_error=abs(line-actual_margin),
            model_ats=model_sign,favorite_ats=fav_sign,home_ats=home_sign,
            model_units=unit(model_sign),favorite_units=unit(fav_sign),home_units=unit(home_sign),
            brier=(p-won)**2 if actual_margin!=0 else np.nan,
            market_brier=(market_p-won)**2 if actual_margin!=0 else np.nan))
    games=pd.DataFrame(game_rows);teams=pd.DataFrame(team_rows)
    # Orient residuals toward each audited QB's team. Positive means the team
    # outperformed its projection; this is the opposite sign to quality_overestimate.
    keys=['game_id','revision']
    margins=games[keys+['model_signed_error','raw_model_signed_error','market_signed_error']]
    teams=teams.merge(margins,on=keys,validate='many_to_one')
    direction=teams.side.map({'home':1.,'away':-1.})
    teams['team_margin_residual']=-teams.model_signed_error*direction
    teams['raw_team_margin_residual']=-teams.raw_model_signed_error*direction
    teams['market_team_margin_residual']=-teams.market_signed_error*direction
    teams['efficiency_residual']=-teams.quality_overestimate
    summaries=[]
    for keys,g in games.groupby(['basis','revision','group'],dropna=False):
        paired=g[g.model_ats.notna()&g.favorite_ats.notna()]
        if len(paired):summaries.append(dict(zip(['basis','revision','group'],keys),**summarize(paired)))
    return games,teams,summaries


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--historical-dir',type=Path,default=ROOT/'research/qb_saved_pick_audit_inputs/historical_boards');args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    games,teams,summary=audit(historical_dir=args.historical_dir)
    games.to_csv(args.output_dir/'games.csv',index=False);teams.to_csv(args.output_dir/'team_qbs.csv',index=False)
    overall=[dict(basis=b,group='all',**summarize(g)) for b,g in games.groupby('basis')]
    overall += [dict(basis=b,group=k,**summarize(g)) for (b,k),g in games.groupby(['basis','group'])]
    (args.output_dir/'summary_by_basis.json').write_text(json.dumps(overall,indent=2,allow_nan=False)+'\n')
    (args.output_dir/'summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
    sources=[str(ORDER.relative_to(ROOT)),'research/qb_saved_pick_audit_inputs/pbp_provenance.json','data/ats_locks.jsonl','data/ats_lock_candidates.jsonl','data/forecast_refreshes.jsonl',
             'data/lock_inputs/qb.parquet','data/lock_inputs/depth.parquet','data/lock_inputs/schedules.parquet','data/lock_inputs/rost.parquet']
    sources += [str(p.relative_to(ROOT)) for store in ats_locks.runtime_stores(ROOT/'data') for p in store.glob('*.jsonl') if p.name in ('ats_locks.jsonl','ats_lock_candidates.jsonl','forecast_refreshes.jsonl')]
    sources += [str(p.relative_to(ROOT)) for p in sorted(args.historical_dir.glob('*.json'))] if args.historical_dir and args.historical_dir.is_relative_to(ROOT) else []
    (args.output_dir/'provenance.json').write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},indent=2)+'\n')
    print(games.groupby(['basis','group']).size().to_string());print(teams.selection.value_counts().to_string())


if __name__=='__main__':main()
