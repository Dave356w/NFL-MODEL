"""Independent numerical replay of the exploratory every-season retest.

Does not import the retest implementation, fit production models, fetch data,
or write forecasts. Its sampled fits use an independent BFGS implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit, ndtri

YEARS=tuple(range(2021,2027))
PATHS=('raw','own_median','shared_median')
SCORE_EPS=1e-12
ROI_EPS=1e-10


def settlement(margin,line,result):
    """Independent favorite-on-equality selection and flat −110 settlement."""
    edge=np.asarray(margin)-np.asarray(line)
    side=np.where(abs(edge)<=1e-10,np.sign(line),np.sign(edge))
    outcome=np.asarray(result)-np.asarray(line)
    selected=np.isfinite(side)&(side!=0)
    push=selected&(abs(outcome)<=1e-10)
    units=np.where(~np.isfinite(side),np.nan,np.where(~selected|push,0.,np.where(side*outcome>0,1/1.1,-1.)))
    return side,units


def median_prediction(games,history_margin,target_margin,year):
    mask=games.season.ge(2021)&games.season.lt(year)&np.isfinite(history_margin)&(history_margin!=0)&np.isfinite(games.result)
    h=games.loc[mask];margin=np.asarray(history_margin)[mask]
    bins=np.searchsorted([3.,7.,10.],abs(margin),side='right')
    counts=np.bincount(bins,minlength=4)
    if h.season.nunique()<2 or len(h)<300 or counts.min()<30:return np.full(np.shape(target_margin),np.nan)
    signed=np.sign(margin)*h.result.to_numpy()
    medians=np.array([np.median(signed[bins==k])for k in range(4)])
    target=np.asarray(target_margin)
    return np.sign(target)*medians[np.searchsorted([3.,7.,10.],abs(target),side='right')]


def independent_week(pack,target,columns,anchor,gamma):
    year,week=int(target.season.iloc[0]),int(target.week.iloc[0])
    before=(pack.season<year)|((pack.season==year)&(pack.week<week))
    tr=pack.loc[before&pack['home won'].isin([0.,1.])]
    age=(year-tr.season.to_numpy())*19+week-tr.week.to_numpy()
    w=np.exp2(-age/38);w/=w.sum();y=tr['home won'].to_numpy()
    def solve(x,base,penalty):
        def objective(beta):
            z=base+x@beta
            return float(np.sum(w*(np.logaddexp(0,z)-y*z))+.5*np.dot(penalty,beta**2)),x.T@(w*(expit(z)-y))+penalty*beta
        opt=minimize(objective,np.zeros(x.shape[1]),jac=True,method='BFGS',options={'gtol':1e-10,'maxiter':2000})
        if np.max(abs(objective(opt.x)[1]))>1e-7:raise AssertionError('Independent fit did not converge')
        return opt.x
    if anchor=='moneyline':base,testbase=logit(tr.q.to_numpy()),logit(target.q.to_numpy())
    else:
        def design(f):
            s=f.spread_line.to_numpy()/7;t=(f.total_line.to_numpy()-44)/7
            return np.column_stack([np.ones(len(f)),s,t,s*t])
        x,xx=design(tr),design(target)
        beta=solve(x,np.zeros(len(tr)),np.full(4,.01*np.sum(w*w)))
        base,testbase=x@beta,xx@beta
    if not columns:return expit(testbase)
    raw=np.nan_to_num(tr[columns].to_numpy(float),nan=0.,posinf=0.,neginf=0.)
    mean=w@raw;sd=np.sqrt(w@((raw-mean)**2));sd=np.where(sd>1e-8,sd,1.)
    if 'site'in columns:sd[columns.index('site')]=1.
    penalty=np.array([.01 if c=='site'else .1 for c in columns])
    coef=solve(raw/sd,base,penalty)
    xx=np.nan_to_num(target[columns].to_numpy(float),nan=0.,posinf=0.,neginf=0.)/sd
    return expit(testbase+gamma*xx@coef)


def _same(actual,expected,label):
    if not np.allclose(actual,expected,rtol=0,atol=1e-11,equal_nan=True):raise AssertionError(label)


def verify(directory):
    directory=Path(directory)
    games=pd.read_csv(directory/'games.csv');variants=pd.read_csv(directory/'variants.csv')
    annual=pd.read_csv(directory/'annual_scores.csv');gates=pd.read_csv(directory/'gate_summary.csv')
    frozen=pd.read_csv(directory/'frozen_inputs.csv.gz');audit=pd.read_csv(directory/'fit_audit.csv')
    provenance=json.loads((directory/'provenance.json').read_text())
    for name,expected in provenance['artifacts'].items():
        assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected, name+' artifact hash'
    with np.load(directory/'predictions.npz')as archive:data={k:archive[k]for k in archive.files}
    assert not games.game_id.duplicated().any() and not variants.id.duplicated().any()
    assert np.array_equal(data['game_ids'],games.game_id) and np.array_equal(data['variant_ids'],variants.id)
    p=data['probabilities'];assert p.shape==(1451,333) and np.isfinite(p).all()and((p>0)&(p<1)).all()
    assert games.groupby('season').size().to_dict()==dict(zip(YEARS,[272,271,272,272,272,92]))
    assert (audit.training_max_key<audit.target_key).all() and (audit.minimum_age_weeks>0).all()
    assert not audit.duplicated(['season','week','anchor']).any() and len(audit)==192
    assert (frozen.train_through_week<frozen.week).all()
    features=json.loads(variants.loc[variants.candidate.eq('full29'),'feature_list'].iloc[0])
    contexts=[c for c in features if c.startswith('pass_')]
    eligible=frozen.ready&frozen['home won'].isin([0.,.5,1.])&np.isfinite(frozen.result)&np.isfinite(frozen.q)
    eligible &= np.isfinite(frozen[contexts+['spread_line','total_line']]).all(axis=1)
    pack=frozen[eligible].sort_values(['season','week','game_id']).reset_index(drop=True)
    assert pack[pack.season.isin(YEARS)].game_id.tolist()==games.game_id.tolist()
    prices=games[['home_moneyline','away_moneyline']].to_numpy(float)
    implied=np.empty_like(prices);negative=prices<0
    implied[negative]=-prices[negative]/(100-prices[negative]);implied[~negative]=100/(100+prices[~negative])
    _same(games.q,implied[:,0]/implied.sum(axis=1),'market identity')
    controls={a:int(np.flatnonzero(variants.id.eq('market:'+a))[0])for a in ('moneyline','spread_total')}
    _same(p[:,controls['moneyline']],games.q,'moneyline control')
    _same(data['margins_raw'],12.37*ndtri(np.clip(p,.005,.995)),'raw conversion')
    incumbent=int(np.flatnonzero(variants.id.eq('incumbent:v118'))[0])
    for year in YEARS:
        mask=games.season.eq(year).to_numpy()
        raw=data['margins_raw']
        shared=median_prediction(games,raw[:,incumbent],raw[mask],year)
        _same(data['margins_shared_median'][mask],shared,'shared prior-season median')
        for k in range(len(variants)):
            own=median_prediction(games,raw[:,k],raw[mask,k],year)
            _same(data['margins_own_median'][mask,k],own,'own prior-season median')
    line=games.spread_line.to_numpy()[:,None];result=games.result.to_numpy()[:,None]
    _,favorite=settlement(line+np.sign(line),line,result)
    _,home=settlement(line+1,line,result)
    _same(data['favorite_units'],favorite[:,0],'favorite control')
    _same(data['home_units'],home[:,0],'home control')
    annual_check=annual.set_index(['path','season','variant_id']).sort_index()
    for path in PATHS:
        sides,units=settlement(data['margins_'+path],line,result)
        _same(data['sides_'+path],sides,'side selection');_same(data['units_'+path],units,'push/−110 settlement')
        for year in YEARS:
            keep=games.season.eq(year).to_numpy();binary=keep&games['home won'].isin([0.,1.]).to_numpy()
            y=games.loc[binary,'home won'].to_numpy()[:,None];pp=p[binary]
            ll=np.mean(-(y*np.log(pp)+(1-y)*np.log1p(-pp)),axis=0);br=np.mean((pp-y)**2,axis=0)
            active=np.isfinite(units[keep]);selected=active&(sides[keep]!=0)
            total=np.nansum(units[keep],axis=0);bets=selected.sum(axis=0)
            roi=np.divide(total,bets,out=np.full(len(variants),np.nan),where=bets>0)
            actual=annual_check.loc[(path,year)].reindex(variants.id)
            _same(actual.log_loss,ll,'annual log loss');_same(actual.brier,br,'annual Brier')
            _same(actual.bets,bets,'push-inclusive stakes');_same(actual.roi,roi,'annual ROI')
            for k,row in enumerate(variants.itertuples()):
                block=actual.iloc[k]; own=controls[row.anchor]; full=bool(active[:,k].all())
                probability=all([ll[controls['moneyline']]-ll[k]>SCORE_EPS,
                    ll[controls['spread_total']]-ll[k]>SCORE_EPS,
                    br[controls['moneyline']]-br[k]>SCORE_EPS,br[controls['spread_total']]-br[k]>SCORE_EPS])
                assert block.probability_pass==probability
                fav_roi=float(np.mean(favorite[keep,0]))if full else np.nan
                ats=bool(full and roi[k]>ROI_EPS and roi[k]-roi[own]>ROI_EPS and roi[k]-fav_roi>ROI_EPS)
                assert block.ats_pass==ats
                assert block.full_coverage==full
    check_gates=gates.set_index(['variant_id','path'])
    for (identity,path),block in annual.groupby(['variant_id','path']):
        assert tuple(sorted(block.season))==YEARS
        probability=bool(block.probability_pass.all())
        ats=bool(block.full_coverage.all()and block.ats_pass.all())
        got=check_gates.loc[(identity,path)]
        assert got.all_seasons_probability_pass==probability and got.all_seasons_ats_pass==ats
        assert got.all_seasons_joint_pass==(probability and ats)
    # Deterministic weeks across all six seasons, plus the newest partial week.
    sampled=[]
    for year in YEARS:
        week=int(games.loc[games.season.eq(year),'week'].min());sampled.append((year,week))
    sampled.append((2026,int(games.loc[games.season.eq(2026),'week'].max())))
    chosen=variants[variants.candidate.isin(['market','single:site',
        'single:d__allowed__rates_core__net_pass_yards_per_pass_play',
        'pair:d__allowed__rates_core__net_pass_yards_per_pass_play|d__avail__qb_delta','full29'])
        &variants.gamma.isin([0.,.1,.5,1.])]
    errors=[];refits=0
    for year,week in sampled:
        use=(games.season.eq(year)&games.week.eq(week)).to_numpy();target=games.loc[use]
        for k,row in enumerate(variants.itertuples()):
            if row.id not in set(chosen.id):continue
            expected=independent_week(pack,target,json.loads(row.feature_list),row.anchor,float(row.gamma))
            error=float(np.max(abs(p[use,k]-expected)));errors.append(error);refits+=1
            assert error<4e-7,(row.id,year,week,error)
    feature=gates[~gates.is_control]
    return dict(status='PASS',games=len(games),variants=len(variants),annual_rows_checked=len(annual),
        policy_rows_checked=len(gates),sampled_week_models=refits,max_independent_probability_error=max(errors),
        all_settlement_arrays_match=True,all_prior_season_median_maps_match=True,
        missing_2021_22_medians_preserved=True,
        six_season_probability_pass=int(feature[feature.path.eq('raw')].all_seasons_probability_pass.sum()),
        six_season_ats_pass=int(feature.all_seasons_ats_pass.sum()),six_season_joint_pass=int(feature.all_seasons_joint_pass.sum()),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    parser.add_argument('--output',type=Path);args=parser.parse_args();result=verify(args.directory)
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
