"""Offline market-benchmark gate for future candidate iterations; never deploys."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

import numpy as np
import pandas as pd
from scipy.special import xlogy

import plain_ats_110 as a

m=a.m
b=a.s.b
REQUIRED={'game_id','season','week','iteration','recipe_sha256','margin_mean','p_home_win',
    'p_home_cover','p_push','spread_line','total_line','home_moneyline','away_moneyline',
    'home_spread_odds','away_spread_odds','market_spread_win','market_spread_total_win'}
TIME_FIELDS={'forecast_utc','kickoff_utc','quote_utc','feature_available_utc',
             'benchmark_available_utc','retained_utc','training_cutoff_utc'}


def validate(predictions,basis):
    if basis not in ['development','forward_declared']:raise ValueError('Unknown evidence basis')
    f=predictions.copy()
    if not REQUIRED<=set(f):raise ValueError(f'Missing forecast fields: {sorted(REQUIRED-set(f))}')
    if {'home_score','away_score','result','units'}&set(f):raise ValueError('Outcomes cannot be in forecast input')
    if f.empty or f.game_id.duplicated().any():raise ValueError('One unique forecast per game required')
    if f.iteration.nunique()!=1 or f.recipe_sha256.nunique()!=1:raise ValueError('One frozen iteration/recipe per evaluation')
    if not all(re.fullmatch('[0-9a-f]{64}',str(v)) for v in f.recipe_sha256):raise ValueError('Invalid recipe hash')
    numeric=['season','week','margin_mean','spread_line','total_line','p_home_win','p_home_cover','p_push',
             'market_spread_win','market_spread_total_win','home_moneyline','away_moneyline','home_spread_odds','away_spread_odds']
    if not np.isfinite(f[numeric].to_numpy(float)).all():raise ValueError('Finite forecast inputs required')
    for name in ['p_home_win','p_home_cover','p_push','market_spread_win','market_spread_total_win']:
        if not f[name].between(0,1).all():raise ValueError('Invalid probability')
    for name in ['home_moneyline','away_moneyline','home_spread_odds','away_spread_odds']:
        if (f[name].abs()<100).any():raise ValueError('Actual American odds required; no default proxy')
    if ((f.season%1!=0)|(f.week%1!=0)|~f.week.between(1,19)|(f.total_line<=0)|((f.spread_line*2)%1!=0)).any():
        raise ValueError('Invalid season/week or market line')
    if basis=='forward_declared':
        extra=TIME_FIELDS|{'training_max_season','training_max_week','snapshot_sha256','retention_url','book'}
        if not extra<=set(f):raise ValueError('Forward evaluation requires timestamp, retention and training metadata')
        if not all(re.fullmatch('[0-9a-f]{64}',str(v)) for v in f.snapshot_sha256):raise ValueError('Invalid snapshot hash')
        if not f.retention_url.astype(str).str.startswith('https://').all() or f.book.isna().any() or f.book.astype(str).str.strip().eq('').any():
            raise ValueError('External retention URL and real quote book required')
        if any(not f[k].astype(str).str.contains(r'(?:Z|[+-]\d\d:\d\d)$',regex=True).all() for k in TIME_FIELDS):
            raise ValueError('Explicit timezone required for every forward timestamp')
        times={k:pd.to_datetime(f[k],utc=True,errors='raise') for k in TIME_FIELDS}
        if any(v.isna().any() for v in times.values()):raise ValueError('Missing forward timestamps')
        forecast=times['forecast_utc'];kickoff=times['kickoff_utc']
        if not ((times['quote_utc']<=forecast)&(forecast-times['quote_utc']<=pd.Timedelta(minutes=5))&
            (times['feature_available_utc']<=forecast)&(times['benchmark_available_utc']<=forecast)&
            (times['training_cutoff_utc']<=forecast)&(forecast<=times['retained_utc'])&(times['retained_utc']<kickoff)).all():
            raise ValueError('Quotes/features/benchmarks must be available and snapshots retained before kickoff')
        if not np.isfinite(f[['training_max_season','training_max_week']].to_numpy(float)).all():raise ValueError('Invalid training cutoff')
        if ((f.training_max_season%1!=0)|(f.training_max_week%1!=0)).any():raise ValueError('Integer training cutoff required')
        if not all((int(r.training_max_season),int(r.training_max_week))<(r.season,r.week) for r in f.itertuples()):
            raise ValueError('Training must exclude forecast week')
    return f


def choose(p,push,home_odds,away_odds):
    profit=lambda odds:odds/100 if odds>0 else 100/-odds
    home=(1-push)*(p*profit(home_odds)-(1-p))
    away=(1-push)*((1-p)*profit(away_odds)-p)
    side=('home' if home>=away else 'away') if max(home,away)>1e-12 else 'pass'
    return side,profit(home_odds if side=='home' else away_odds),max(home,away) if side!='pass' else 0.


def evaluate(predictions,outcomes,basis='development'):
    f=validate(predictions,basis)
    if not {'game_id','home_score','away_score'}<=set(outcomes) or outcomes.game_id.duplicated().any():raise ValueError('Unique outcome records required')
    if not f.game_id.isin(outcomes.game_id).all():raise ValueError('Pending outcomes: evaluate the full fixed cohort, not completed subsets')
    f=f.merge(outcomes[['game_id','home_score','away_score']],on='game_id',validate='one_to_one')
    score=f[['home_score','away_score']].to_numpy(float)
    if not np.isfinite(score).all() or (score<0).any() or (score%1!=0).any():raise ValueError('Nonnegative integer outcomes required')
    margin=f.home_score-f.away_score
    y_win=np.where(margin==0,np.nan,(margin>0).astype(float))
    y_cover=np.where(margin==f.spread_line,np.nan,(margin>f.spread_line).astype(float))
    ll=lambda y,p:-xlogy(y,p)-xlogy(1-y,1-p)
    q=m.j.fair_moneyline(f.home_moneyline.to_numpy(),f.away_moneyline.to_numpy())
    contrasts={
        'margin_MAE_vs_spread':abs(margin-f.spread_line)-abs(margin-f.margin_mean),
        'winner_LL_vs_spread':ll(y_win,f.market_spread_win)-ll(y_win,f.p_home_win),
        'winner_LL_vs_spread_total':ll(y_win,f.market_spread_total_win)-ll(y_win,f.p_home_win),
        'winner_LL_vs_moneyline':ll(y_win,q)-ll(y_win,f.p_home_win),
        'ATS_LL_vs_fair':ll(y_cover,.5)-ll(y_cover,f.p_home_cover)}
    comparisons={}
    for key,values in contrasts.items():
        if np.isinf(values).any() or not np.isfinite(values).any():
            comparisons[key]=dict(gain=float(np.nanmean(values)),ci95=None,finite=False)
        else:
            boot=b.week_bootstrap(values,f.season,f.week)[:,0]
            comparisons[key]=dict(gain=float(np.nanmean(values)),ci95=b.interval(boot),finite=True)
    units=[];favorites=[];nulls=[];sides=[]
    for r in f.itertuples():
        side,profit,_=choose(r.p_home_cover,r.p_push,r.home_spread_odds,r.away_spread_odds)
        delta=r.home_score-r.away_score-r.spread_line
        won=delta>0 if side=='home' else delta<0
        sides.append(side);units.append(0. if side=='pass' or delta==0 else profit if won else -1.)
        favorite_home=r.spread_line>=0;odds=r.home_spread_odds if favorite_home else r.away_spread_odds
        favorite_profit=odds/100 if odds>0 else 100/-odds
        favorites.append(0. if delta==0 else favorite_profit if (delta>0)==favorite_home else -1.)
        nulls.append(.5*profit-.5)
    f['ATS_side']=sides;f['ATS_units']=units;f['favorite_units']=favorites;f['fair_null']=nulls
    bets=f[f.ATS_side.ne('pass')]
    ci=b.interval(b.week_bootstrap(bets.ATS_units,bets.season,bets.week)[:,0]) if len(bets) else None
    decisive=bets.home_score-bets.away_score!=bets.spread_line
    null=float(bets.loc[decisive,'fair_null'].sum()/len(bets)) if len(bets) else np.nan
    clusters=f[['season','week']].drop_duplicates().shape[0]
    info=comparisons['ATS_LL_vs_fair']
    gates=dict(forward_declared=basis=='forward_declared',sample_size=len(f)==512 and len(bets)>=200 and clusters>=20,
        incremental_ATS_information=info['finite'] and info['gain']>=.002 and info['ci95'][0]>0,
        positive_priced_ROI=ci is not None and ci[0]>0)
    verdict='eligible for independent forward review' if all(gates.values()) else 'incremental ATS edge not established'
    result=dict(iteration=f.iteration.iloc[0],basis=basis,games=len(f),week_clusters=clusters,
        comparisons=comparisons,ATS=dict(bets=len(bets),passes=len(f)-len(bets),units=float(bets.ATS_units.sum()),
        roi=float(bets.ATS_units.mean()),roi_se=float(bets.ATS_units.std(ddof=1)/np.sqrt(len(bets))) if len(bets)>1 else np.nan,
        roi_ci95=ci,same_row_favorite_units=float(bets.favorite_units.sum()),fair_null_roi=null),
        gates=gates,verdict=verdict,production_promotion=False,
        evidence='Timestamp/hash/retention fields are declarations to audit externally; this evaluator cannot authenticate providers, establish first-snapshot completeness or prove a recipe was preregistered.')
    return result,f


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions',required=True,type=Path);parser.add_argument('--outcomes',required=True,type=Path)
    parser.add_argument('--basis',choices=['development','forward_declared'],default='development')
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args();out=args.output_dir.resolve();root=m.j.ROOT.resolve()
    if out==root or any(out==root/p or (root/p) in out.parents for p in ['data','public']):raise ValueError('Protected production output')
    result,rows=evaluate(pd.read_csv(args.predictions),pd.read_csv(args.outcomes),args.basis)
    out.mkdir(parents=True,exist_ok=True);m.dump(out/'evaluation.json',result);rows.to_csv(out/'graded_view.csv',index=False)
    m.dump(out/'inputs.json',dict(predictions_sha256=m.j.sha256(args.predictions),outcomes_sha256=m.j.sha256(args.outcomes),source_sha256=m.j.sha256(Path(__file__))))
    print(result['verdict'])


if __name__=='__main__':main()
