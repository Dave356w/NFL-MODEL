"""One fixed first-start fade candidate; see QB_FIRST_START_FADE.md."""
import json
import hashlib
from pathlib import Path
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research import qb_backup_residuals as base
from research.qb_actual_starters import corrected_schedules

OUT=ROOT/'research/qb_first_start_fade_results'
HALF_LIFE=2.


def prior_stint_start(history,team,season,week,pid):
    if pd.isna(pid):return np.nan
    h=history[(history.season==season)&(history.week<week)&history.team.eq(team)].sort_values('week',ascending=False)
    n=1
    for actual in h.actual_id:
        if pd.isna(actual):return np.nan
        if actual!=pid:break
        n+=1
    return n


def with_exposures(d,history):
    out=d.copy()
    for side in ('home','away'):
        out[side+'_stint_start']=[prior_stint_start(history,r[side],int(r['season']),int(r['week']),r[side+'_projected_id']) for r in out.to_dict('records')]
        out[side+'_fade']=np.where(out[side+'_replacement'].eq(0),0.,out[side+'_replacement']*np.exp2(-(out[side+'_stint_start']-1)/HALF_LIFE))
    out['fade_difference']=out.home_fade-out.away_fade
    return out


def walk_forward(d):
    rows=[];fits=[]
    for year in (2023,2024,2025):
        tr=d[d.season<year];te=d[d.season==year].copy()
        if te.empty:continue
        b=base.ols(tr,flag='fade');bb=base.ols(tr,flag='replacement')
        assert tr.season.max()<year
        te['fade_margin']=te.raw_margin+b[0]+b[1]*te.fade_difference
        te['blanket_margin']=te.raw_margin+bb[0]+bb[1]*(te.home_replacement-te.away_replacement)
        te['intercept_margin']=te.raw_margin+float((tr.result-tr.raw_margin).mean())
        te['train_max_season']=int(tr.season.max());te['fade_beta']=float(b[1])
        rows.append(te);fits.append(dict(test_season=year,n=len(tr),train_max_season=int(tr.season.max()),intercept=float(b[0]),fade_beta=float(b[1]),blanket_beta=float(bb[1])))
    out=pd.concat(rows,ignore_index=True)
    out['gain_over_intercept']=(out.result-out.intercept_margin)**2-(out.result-out.fade_margin)**2
    out['gain_over_blanket']=(out.result-out.blanket_margin)**2-(out.result-out.fade_margin)**2
    return out,fits


def run():
    OUT.mkdir(exist_ok=True)
    d=pd.read_csv(base.INPUT/'games.csv')
    d=d[d.home_replacement.notna()&d.away_replacement.notna()].copy()
    s=corrected_schedules(pd.read_parquet(ROOT/'data/lock_inputs/schedules.parquet'))
    s=s[s.season<=2025]
    h=pd.concat([s[s.result.notna()][['season','week',side+'_team',side+'_qb_id']].rename(columns={side+'_team':'team',side+'_qb_id':'actual_id'}) for side in ('home','away')],ignore_index=True)
    d=with_exposures(d,h)
    d=d[d.home_fade.notna()&d.away_fade.notna()].copy()
    pred,folds=walk_forward(d)
    b=base.ols(d,flag='fade');ci=base.coefficient_ci(d,flag='fade')
    scores=[]
    for label,g in [('all eligible',pred),('replacement involved',pred[(pred.home_replacement+pred.away_replacement)>0])]:
        for arm in ('raw_margin','intercept_margin','blanket_margin','fade_margin','market_margin'):
            scores.append(dict(cohort=label,arm=arm,**base.score(g,arm)))
        scores.append(dict(cohort=label,arm='paired MSE gain',n=len(g),gain_over_intercept=float(g.gain_over_intercept.mean()),ci95_intercept=base.mean_ci(g,'gain_over_intercept'),gain_over_blanket=float(g.gain_over_blanket.mean()),ci95_blanket=base.mean_ci(g,'gain_over_blanket')))
        scores.append(dict(cohort=label,arm='always favorite',**base.ats(g.market_margin*2,g.market_margin,g.result)))
        scores.append(dict(cohort=label,arm='always home',**base.ats(g.market_margin+1,g.market_margin,g.result)))
    teams=[]
    for r in d.to_dict('records'):
        for side,sign in [('home',1),('away',-1)]:
            if r[side+'_replacement']!=1:continue
            teams.append(dict(game_id=r['game_id'],season=r['season'],week=r['week'],team=r[side],projected_qb=r[side+'_projected_qb'],correct=r[side+'_correct'],start_number=r[side+'_stint_start'],exposure=r[side+'_fade'],raw_residual=sign*(r['result']-r['raw_margin']),market_residual=sign*(r['result']-r['market_margin'])))
    teams=pd.DataFrame(teams)
    groups=[]
    for k,g in teams.groupby('start_number'):
        groups.append(dict(start_number=int(k),n=len(g),raw_residual=float(g.raw_residual.mean()),market_residual=float(g.market_residual.mean())))
    out=dict(definition='fixed two-start half-life, current team-stint',half_life_starts=HALF_LIFE,n=len(d),seasons=sorted(d.season.unique().astype(int).tolist()),intercept=float(b[0]),fade_beta=float(b[1]),ci95=ci,folds=folds,scores=scores,start_groups=groups)
    (OUT/'results.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n')
    d.to_csv(OUT/'input_games.csv',index=False);pred.to_csv(OUT/'walk_forward.csv',index=False);teams.to_csv(OUT/'team_residuals.csv',index=False)
    paths=[base.INPUT/'games.csv',ROOT/'data/lock_inputs/schedules.parquet',ROOT/'research/qb_saved_pick_audit_inputs/qb_play_order.csv']
    (OUT/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')
    print(json.dumps(out,indent=2))


if __name__=='__main__':run()
