"""Historical backup-team margin residual fit; see QB_BACKUP_RESIDUALS.md."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.special import ndtr
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import nfl_model as m
import fixed_bands as fb
from research.qb_saved_pick_audit import name_index,resolve_name
from research.qb_actual_starters import corrected_schedules,ORDER

INPUT=ROOT/'research/qb_backup_residual_inputs'
OUT=ROOT/'research/qb_backup_residual_results'
SEED=20261113


def incumbent(schedule,roster,team,year,week):
    past=schedule[(schedule.season==year)&(schedule.week<week)&schedule.result.notna()]
    starts=[]
    for side in ('home','away'):
        g=past[past[side+'_team'].eq(team)]
        starts += [(int(r.week),getattr(r,side+'_qb_id')) for r in g.itertuples() if pd.notna(getattr(r,side+'_qb_id'))]
    if not starts:return None
    counts={p:sum(pid==p for _,pid in starts) for _,p in starts}
    pid=max(counts,key=lambda p:(counts[p],max(w for w,pid in starts if pid==p)))
    if counts[pid]<2:return None
    rs=roster[(roster.season==year)&roster.team.eq(team)&(roster.week<week)]
    if rs.empty:return '__unknown_roster__'
    rs=rs[rs.week.eq(rs.week.max())]
    return pid if ((rs.gsis_id==pid)&rs.position.eq('QB')).any() else None


def prepare():
    INPUT.mkdir(exist_ok=True)
    print('preparing historical inputs',flush=True)
    paths=['data/latest/retro_ledger.csv','data/lock_inputs/availability.parquet',
           'data/lock_inputs/schedules.parquet','data/lock_inputs/rost.parquet',
           'data/lock_inputs/qb.parquet','data/lock_inputs/depth.parquet',str(ORDER.relative_to(ROOT)),'research/qb_saved_pick_audit_inputs/pbp_provenance.json']
    d=pd.read_csv(ROOT/paths[0]);d=d[d.season.between(2021,2025)].copy()
    av=pd.read_parquet(ROOT/paths[1]);sch=corrected_schedules(pd.read_parquet(ROOT/paths[2]));rost=pd.read_parquet(ROOT/paths[3])
    qb=pd.read_parquet(ROOT/paths[4]);depth=pd.read_parquet(ROOT/paths[5]);depth['_t']=pd.to_datetime(depth.dt,utc=True)
    order=pd.read_csv(ORDER)
    idx=name_index(pd.concat([qb,order],ignore_index=True),sch,rost)
    # Full roster names supply canonical IDs even when QB pbp coverage starts later.
    for r in rost[rost.position.eq('QB')].itertuples():
        nm=str(r.full_name).split()
        if len(nm)>1:
            from research.qb_saved_pick_audit import normalized
            short=nm[0][0]+'.'+' '.join(nm[1:])
            idx.setdefault(normalized(short),set()).add(r.gsis_id)
    actual=sch.set_index('game_id');av=av.set_index(['season','week','team'])
    rows=[]
    inc_cache={}
    for side in ('home','away'):
        for r in d.itertuples(index=False):
            team=getattr(r,side)
            inc_cache[(r.season,r.week,team)]=incumbent(sch,rost,team,int(r.season),int(r.week))
    print('incumbent histories prepared',flush=True)
    for r in d.itertuples(index=False):
        if r.game_id not in actual.index:continue
        s=actual.loc[r.game_id];row=dict(game_id=r.game_id,season=int(r.season),week=int(r.week),
            home=r.home,away=r.away,result=float(r.result),market_margin=float(r.spread_line),raw_margin=float(r.model_spread))
        for side in ('home','away'):
            team=getattr(r,side);key=(r.season,r.week,team)
            name=av.loc[key,'qb_expected'] if key in av.index else None
            eligible=set(rost.loc[rost.season.eq(r.season)&rost.team.eq(team)&(rost.week<=r.week)&rost.position.eq('QB'),'gsis_id'])
            blended=isinstance(name,str) and ' (Q) / ' in name
            pid=resolve_name(name,idx,eligible) if not blended else None
            inc=inc_cache[(r.season,r.week,team)]
            # No established incumbent is an ordinary/non-replacement classification.
            flag=(np.nan if inc=='__unknown_roster__' else float(pid!=inc) if inc is not None and pid is not None else 0. if inc is None and pid is not None else np.nan)
            correct=(pid==s[side+'_qb_id']) if pid is not None and pd.notna(s[side+'_qb_id']) else None
            rank=np.nan;stamp=None
            ko=m.kickoff_utc(s)
            if ko is not None and r.season>=2025 and pid is not None:
                cut=pd.Timestamp(ko)-pd.Timedelta(hours=24)
                h=depth[(depth.season==r.season)&depth.team.eq(team)&(depth._t<=cut)]
                if len(h):
                    last=h._t.max()
                    if cut-last<=pd.Timedelta(days=7):
                        ranks=h.loc[h._t.eq(last)&h.gsis_id.eq(pid),'pos_rank']
                        rank=float(ranks.min()) if len(ranks) else np.nan;stamp=last
            row.update({side+'_projected_qb':name,side+'_projected_id':pid,side+'_actual_qb':s[side+'_qb_name'],
                        side+'_actual_id':s[side+'_qb_id'],side+'_incumbent_id':inc,side+'_replacement':flag,
                        side+'_correct':correct,side+'_chart_rank':rank,side+'_chart_utc':stamp})
        rows.append(row)
    out=pd.DataFrame(rows).sort_values(['season','week','game_id']).reset_index(drop=True)
    # Weekly mapped projections use results strictly earlier than the target week.
    mapbase=out.rename(columns={'raw_margin':'model_spread'})
    out['mapped_margin']=np.nan
    for (y,w),g in out.groupby(['season','week']):
        rule=fb.fit_weekly(mapbase,int(y),int(w))
        if rule is not None:out.loc[g.index,'mapped_margin']=fb.apply(g.raw_margin,rule)
    out.to_csv(INPUT/'games.csv',index=False)
    print('historical inputs saved: '+str(len(out)),flush=True)
    (INPUT/'provenance.json').write_text(json.dumps({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},indent=2)+'\n')


def ols(d,target='raw_margin',flag='replacement'):
    x=(d['home_'+flag]-d['away_'+flag]).to_numpy(float)
    y=(d.result-d[target]).to_numpy(float)
    X=np.column_stack([np.ones(len(x)),x])
    return np.linalg.lstsq(X,y,rcond=None)[0]


def coefficient_ci(d,target='raw_margin',flag='replacement',reps=4000):
    f=d[['season','week']].copy()
    f['x']=(d['home_'+flag]-d['away_'+flag]).to_numpy(float)
    f['y']=(d.result-d[target]).to_numpy(float)
    f['xx']=f.x**2; f['xy']=f.x*f.y;f['n']=1.
    stats=f.groupby(['season','week'])[['n','x','y','xx','xy']].sum().to_numpy()
    if len(stats)<2:return None
    rng=np.random.default_rng(SEED)
    weights=rng.multinomial(len(stats),np.full(len(stats),1/len(stats)),size=reps)
    totals=weights@stats
    n,x,y,xx,xy=totals.T
    det=n*xx-x*x
    beta=np.divide(n*xy-x*y,det,out=np.zeros(reps),where=det>1e-12)
    intercept=(y-beta*x)/n
    return np.quantile(np.column_stack([intercept,beta]),[.025,.975],axis=0).tolist()


def mean_ci(d,column,reps=4000):
    f=d[['season','week',column]].copy()
    g=f.groupby(['season','week'])[column].agg(['size','sum']).to_numpy(float)
    if len(g)<2:return None
    rng=np.random.default_rng(SEED)
    w=rng.multinomial(len(g),np.full(len(g),1/len(g)),size=reps)
    total=w@g
    return np.quantile(total[:,1]/total[:,0],[.025,.975]).tolist()


def ats(pred,line,actual):
    side=np.sign(np.asarray(pred)-np.asarray(line));zero=side==0
    side[zero]=np.sign(np.asarray(line)[zero])
    sign=side*np.sign(np.asarray(actual)-np.asarray(line));valid=side!=0
    u=np.where(sign>0,1/1.1,np.where(sign<0,-1.,0.))
    u=u[valid];sg=sign[valid]
    return dict(n=len(u),WLP=f'{sum(sg>0)}-{sum(sg<0)}-{sum(sg==0)}',units=float(u.sum()),
                roi=float(u.mean()),roi_se=float(u.std(ddof=1)/np.sqrt(len(u))) if len(u)>1 else None)


def score(d,column):
    e=d.result-d[column];p=ndtr(d[column]/m.MARKET_SIGMA)
    y=(d.result>0).astype(float);k=d.result!=0
    return dict(n=len(d),mean_home_residual=float(e.mean()),mae=float(e.abs().mean()),mse=float((e**2).mean()),
                brier=float(((p[k]-y[k])**2).mean()),**{'ats':ats(d[column],d.market_margin,d.result)})


def walk_forward(d):
    preds=[];fit_history=[]
    for year in (2023,2024,2025):
        tr=d[d.season<year];te=d[d.season==year].copy()
        if te.empty: continue
        b=ols(tr)
        assert tr.season.max()<year
        te['adjusted_margin']=te.raw_margin+b[0]+b[1]*te.backup_difference
        te['intercept_margin']=te.raw_margin+float((tr.result-tr.raw_margin).mean())
        te['intercept_only']=float((tr.result-tr.raw_margin).mean())
        te['train_max_season']=int(tr.season.max());te['backup_beta']=b[1];te['intercept']=b[0]
        preds.append(te);fit_history.append(dict(test_season=year,training_seasons=sorted(tr.season.unique().astype(int).tolist()),n=len(tr),
                          intercept=float(b[0]),intercept_only=float((tr.result-tr.raw_margin).mean()),backup_coefficient=float(b[1])))
    return pd.concat(preds,ignore_index=True),fit_history

def run():
    OUT.mkdir(exist_ok=True)
    all_=pd.read_csv(INPUT/'games.csv');d=all_[all_.home_replacement.notna()&all_.away_replacement.notna()].copy()
    d['backup_difference']=d.home_replacement-d.away_replacement
    fits=[]
    for target in ('raw_margin','mapped_margin','market_margin'):
        g=d[d[target].notna()]
        b=ols(g,target)
        fits.append(dict(cohort='replacement proxy',projection=target,n=len(g),seasons=sorted(g.season.unique().astype(int).tolist()),backup_team_games=int((g.home_replacement+g.away_replacement).sum()),
                         intercept=float(b[0]),backup_coefficient=float(b[1]),ci95=coefficient_ci(g,target)))
    # Matched 2023-25 rows make the mapped comparison fair; correct-starter
    # restriction is an outcome-conditioned diagnostic, never deployment evidence.
    for cohort,sub in [('replacement proxy; mapped-eligible rows',d[d.mapped_margin.notna()]),
                       ('replacement proxy; both starters matched',d[d.home_correct.eq(True)&d.away_correct.eq(True)])]:
        for target in ('raw_margin','market_margin'):
            b=ols(sub,target)
            fits.append(dict(cohort=cohort,projection=target,n=len(sub),seasons=sorted(sub.season.unique().astype(int).tolist()),
                backup_team_games=int((sub.home_replacement+sub.away_replacement).sum()),intercept=float(b[0]),
                backup_coefficient=float(b[1]),ci95=coefficient_ci(sub,target)))
    # Single-season strict chart result, explicitly separate from the long-history proxy.
    chart=all_[all_.season.eq(2025)&all_.home_chart_rank.notna()&all_.away_chart_rank.notna()].copy()
    chart['home_chart_backup']=chart.home_chart_rank.gt(1).astype(float);chart['away_chart_backup']=chart.away_chart_rank.gt(1).astype(float)
    for target in ('raw_margin','mapped_margin','market_margin'):
        g=chart[chart[target].notna()];b=ols(g,target,'chart_backup')
        fits.append(dict(cohort='2025 strict chart',projection=target,n=len(g),seasons=sorted(g.season.unique().astype(int).tolist()),backup_team_games=int((g.home_chart_backup+g.away_chart_backup).sum()),
                         intercept=float(b[0]),backup_coefficient=float(b[1]),ci95=coefficient_ci(g,target,'chart_backup')))
    pred,fit_history=walk_forward(d)
    pred['mse_gain']=(pred.result-pred.raw_margin)**2-(pred.result-pred.adjusted_margin)**2
    pred['incremental_mse_gain']=(pred.result-pred.intercept_margin)**2-(pred.result-pred.adjusted_margin)**2
    stats=[]
    for label,g in [('all eligible',pred),('replacement involved',pred[(pred.home_replacement+pred.away_replacement)>0])]:
        for arm in ('raw_margin','adjusted_margin','intercept_margin','market_margin'):
            stats.append(dict(cohort=label,arm=arm,**score(g,arm)))
        stats.append(dict(cohort=label,arm='paired MSE gain',n=len(g),gain=float(g.mse_gain.mean()),
                          ci95=mean_ci(g,'mse_gain'),
                          incremental_gain_over_intercept=float(g.incremental_mse_gain.mean()),
                          incremental_ci95=mean_ci(g,'incremental_mse_gain')))
        stats.append(dict(cohort=label,arm='always favorite',**ats(g.market_margin*2,g.market_margin,g.result)))
        stats.append(dict(cohort=label,arm='always home',**ats(g.market_margin+1,g.market_margin,g.result)))
    # Team-oriented diagnostics; do not duplicate these rows in regression fitting.
    teams=[]
    for definition,frame,flag in [('replacement proxy',d,'replacement'),('2025 strict chart',chart,'chart_backup')]:
        for r in frame.to_dict('records'):
            for side,orient in [('home',1.),('away',-1.)]:
                if r[side+'_'+flag]!=1:continue
                teams.append(dict(definition=definition,game_id=r['game_id'],season=r['season'],week=r['week'],team=r[side],
                    projected_qb=r[side+'_projected_qb'],actual_qb=r[side+'_actual_qb'],correct=r[side+'_correct'],
                    raw_residual=(r['result']-r['raw_margin'])*orient,mapped_residual=(r['result']-r['mapped_margin'])*orient,
                    market_residual=(r['result']-r['market_margin'])*orient))
    teams=pd.DataFrame(teams)
    annual=[]
    for keys,g in teams.groupby(['definition','season','correct'],dropna=False):
        annual.append(dict(definition=keys[0],season=int(keys[1]),correct=None if pd.isna(keys[2]) else bool(keys[2]),n=len(g),
            raw_residual=float(g.raw_residual.mean()),mapped_residual=float(g.mapped_residual.mean()) if g.mapped_residual.notna().any() else None,
            market_residual=float(g.market_residual.mean())))
    teams.to_csv(OUT/'team_residuals.csv',index=False);pred.to_csv(OUT/'walk_forward.csv',index=False)
    yearly=[]
    for y,g in pred.groupby('season'):
        yearly.append(dict(season=int(y),n=len(g),replacement_games=int(((g.home_replacement+g.away_replacement)>0).sum()),
            mse_gain=float(g.mse_gain.mean()),incremental_mse_gain=float(g.incremental_mse_gain.mean())))
    results=dict(fits=fits,annual=annual,yearly_walk_forward=yearly,walk_forward_fits=fit_history,scores=stats,
                 coverage=dict(total_games=len(all_),eligible=len(d),unresolved=len(all_)-len(d),chart2025=len(chart)))
    (OUT/'results.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
    print(json.dumps(results,indent=2,allow_nan=False))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare-inputs',action='store_true');args=p.parse_args()
    if args.prepare_inputs:prepare()
    run()
