"""Median-aligned saved-2026 injury replay and prospective positional weights.

python research/positional_injury_weights.py --prepare
python research/positional_injury_weights.py
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from scipy.optimize import linprog
from scipy import sparse

import injury_saved_inputs as source

ROOT=source.ROOT
sys.path.insert(0,str(ROOT))
import fixed_bands as ats

OUT=ROOT/'research/injury_weight_results'
ALPHA=.02
FEATURES=source.FEATURES
SEED=20261113


def fit_median(train,features=FEATURES,alpha=ALPHA):
    residual=(train.result-train.prediction).to_numpy(float)
    if len(train)==0 or not np.isfinite(residual).all():raise ValueError('Missing training outcomes')
    if not features:
        return dict(intercept=float(np.median(residual)),beta=np.array([]),mu=np.array([]),scale=np.array([]),features=[],n=len(train))
    raw=train[features].to_numpy(float)
    if not np.isfinite(raw).all():raise ValueError('Missing positional injury input')
    mu=raw.mean(axis=0);scale=raw.std(axis=0);scale[scale<1e-8]=1.
    x=np.column_stack([np.ones(len(train)),(raw-mu)/scale]);n,k=x.shape;p=k-1
    # Variables: [unpenalized intercept, free betas, nonnegative residual sizes,
    #             nonnegative coefficient sizes]. Exact .5-quantile/L1 objective.
    a=sparse.hstack([sparse.csr_matrix(x),-sparse.eye(n),sparse.csr_matrix((n,p))],format='csr')
    b=sparse.hstack([-sparse.csr_matrix(x),-sparse.eye(n),sparse.csr_matrix((n,p))],format='csr')
    c=sparse.hstack([sparse.csr_matrix((p,1)),sparse.eye(p),sparse.csr_matrix((p,n)),-sparse.eye(p)],format='csr')
    d=sparse.hstack([sparse.csr_matrix((p,1)),-sparse.eye(p),sparse.csr_matrix((p,n)),-sparse.eye(p)],format='csr')
    result=linprog(np.r_[np.zeros(k),np.full(n,.5/n),np.full(p,alpha)],
                   A_ub=sparse.vstack([a,b,c,d],format='csr'),b_ub=np.r_[residual,-residual,np.zeros(2*p)],
                   bounds=[(None,None)]*k+[(0,None)]*(n+p),method='highs',
                   options={'primal_feasibility_tolerance':1e-8,'dual_feasibility_tolerance':1e-8})
    if not result.success:raise ValueError('Median fit failed: '+result.message)
    coef=result.x[:k];coef[abs(coef)<1e-9]=0.
    return dict(intercept=float(coef[0]),beta=coef[1:],mu=mu,scale=scale,features=list(features),n=n)


def predict(frame,fit):
    return frame.prediction.to_numpy(float)+fit['intercept']+(
        (frame[fit['features']].to_numpy(float)-fit['mu'])/fit['scale'])@fit['beta']


def cover_probability(medians,residuals,line):
    """Prior empirical errors, integer-margin interpolation, conditional on no push."""
    simulated=np.asarray(medians)[:,None]+np.asarray(residuals)[None,:]
    line=np.asarray(line)[:,None]
    # Equivalent to uniform dequantization followed by rounding; integer
    # outcomes retain their mass, including key-number pushes.
    home=np.clip(simulated-np.floor(line),0,1).sum(axis=1)
    away=np.clip(np.ceil(line)-simulated,0,1).sum(axis=1)
    return (home+.5)/(home+away+1.)


def metrics(a):
    grade,units=ats.grade(a,a.adjusted_median)
    skip=grade=='S';w,l,p=(int(sum(grade==s)) for s in ['W','L','P']);n=int(sum(~skip))
    err=a.result-a.adjusted_median;dec=abs(a.result-a.spread_line)>ats.EPS
    y=(a.loc[dec,'result']>a.loc[dec,'spread_line']).to_numpy(float);prob=a.loc[dec,'p_home_cover'].to_numpy(float)
    policy=a.arm.iloc[0] in ['always_favorite','always_home']
    return dict(n=len(a),bets=n,wins=w,losses=l,pushes=p,skips=int(skip.sum()),cover_rate=w/(w+l) if w+l else None,
                units=float(units.sum()),roi=float(units.sum()/n),roi_se=float(units[~skip].std(ddof=1)/np.sqrt(n)) if n>1 else None,
                median_residual=None if policy else float(err.median()),mae=None if policy else float(abs(err).mean()),
                pinball=None if policy else float(.5*abs(err).mean()),rmse=None if policy else float(np.sqrt((err**2).mean())),
                cover_n=int(sum(dec)),log_loss=float(-(y*np.log(prob)+(1-y)*np.log1p(-prob)).mean()),brier=float(((y-prob)**2).mean()))


def serialize_fit(fit):
    out={k:v for k,v in fit.items() if k not in ['beta','mu','scale']}
    out.update({k:fit[k].tolist() for k in ['beta','mu','scale']})
    return out


def earlier_training(history,current,week):
    if not history.season.lt(2026).all() or not current.season.eq(2026).all():
        raise ValueError('Wrong historical/evaluation season')
    train=pd.concat([history,current[current.week<week]],ignore_index=True)
    if any((train.season>2026)|((train.season==2026)&(train.week>=week))):raise ValueError('Future fit label')
    return train


def physical_weights(fit):
    factors=np.array([1. if x=='qb_delta' else .1 for x in fit['features']])
    return fit['beta']/fit['scale']*factors


def paired_interval(base,new,reps=5000):
    base=base.sort_values('game_id').reset_index(drop=True);new=new.sort_values('game_id').reset_index(drop=True)
    if not base.game_id.equals(new.game_id):raise ValueError('Different held-out comparison games')
    y=base.result.gt(base.spread_line).to_numpy(float);dec=base.result.ne(base.spread_line).to_numpy()
    ll=lambda f:-(y*np.log(f.p_home_cover)+(1-y)*np.log1p(-f.p_home_cover))
    d=pd.DataFrame({'week':base.week,'mae':abs(base.result-base.adjusted_median)-abs(new.result-new.adjusted_median),
                    'll':(ll(base)-ll(new)).where(dec)})
    agg=d.groupby('week').agg(mae_sum=('mae','sum'),n=('mae','size'),ll_sum=('ll','sum'),nd=('ll','count')).to_numpy()
    rng=np.random.default_rng(SEED);sample=agg[rng.integers(0,len(agg),size=(reps,len(agg)))].sum(axis=1)
    return dict(mae_gain=float(d.mae.mean()),mae_gain_ci95=np.quantile(sample[:,0]/sample[:,1],[.025,.975]).tolist(),
                log_loss_gain=float(d.ll.mean()),log_loss_gain_ci95=np.quantile(sample[:,2]/sample[:,3],[.025,.975]).tolist(),
                evaluation_weeks=int(len(agg)))


def coefficient_stability(train,reps=200):
    groups=[a for _,a in train.groupby(['season','week'],sort=True)]
    rng=np.random.default_rng(SEED);samples=[]
    for _ in range(reps):
        b=pd.concat([groups[i] for i in rng.integers(0,len(groups),len(groups))],ignore_index=True)
        samples.append(physical_weights(fit_median(b)))
    a=np.asarray(samples)
    return np.quantile(a,[.025,.975],axis=0),np.mean(a>1e-9,axis=0),np.mean(a<-1e-9,axis=0)


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    all_predictions=[];fitlog=[];weight_rows=[];all_metrics=[];comparisons=[];reliability=[];unpenalized=[]
    for cohort,hname,cname in [('saved_vectors','historical_vectors','saved_vectors_2026'),
                              ('official_reports','historical_medical','saved_reports_2026')]:
        history=pd.read_csv(source.INPUT/(hname+'.csv'));current=pd.read_csv(source.INPUT/(cname+'.csv'))
        if history.season.max()>=2026:raise ValueError('Historical prior contains evaluation labels')
        prior=fit_median(history);prior_control=fit_median(history,[])
        pred=[]
        for week,test in current.groupby('week',sort=True):
            train=earlier_training(history,current,week)
            rolling=fit_median(train);rolling_control=fit_median(train,[])
            original=dict(prior_control,intercept=0.)
            for arm,fit,cal in [('original',original,history),('prior_median_control',prior_control,history),
                                ('prior_injury',prior,history),('rolling_median_control',rolling_control,train),('rolling_injury',rolling,train)]:
                a=test.copy();a['adjusted_median']=predict(test,fit);a['arm']=arm;a['cohort']=cohort
                errors=cal.result.to_numpy()-predict(cal,fit)
                a['p_home_cover']=cover_probability(a.adjusted_median,errors,a.spread_line)
                a['training_n']=len(cal);a['training_2026_n']=int(sum(cal.season==2026))
                pred.append(a)
                latest=cal.sort_values(['season','week']).iloc[-1]
                fitlog.append(dict(cohort=cohort,evaluation_week=int(week),arm=arm,
                                   training_max_season=int(latest.season),training_max_week=int(latest.week),**serialize_fit(fit)))
            for arm in ['always_favorite','always_home']:
                a=test.copy();a['adjusted_median']=a.spread_line+(1. if arm=='always_home' else 0.)
                a['p_home_cover']=.5;a['arm']=arm;a['cohort']=cohort;pred.append(a)
        d=pd.concat(pred,ignore_index=True);all_predictions.append(d)
        for arm,a in d.groupby('arm'):
            all_metrics.append(dict(cohort=cohort,arm=arm,**metrics(a)))
            decisive=a[a.result.ne(a.spread_line)].copy();decisive['bin']=pd.cut(decisive.p_home_cover,[0,.2,.4,.6,.8,1],include_lowest=True)
            for band,b in decisive.groupby('bin',observed=True):
                reliability.append(dict(cohort=cohort,arm=arm,band=str(band),n=len(b),predicted=float(b.p_home_cover.mean()),observed=float((b.result>b.spread_line).mean())))
        for baseline,challenger in [('original','prior_injury'),('prior_median_control','prior_injury'),
                                    ('original','rolling_injury'),('rolling_median_control','rolling_injury'),('prior_injury','rolling_injury')]:
            comparisons.append(dict(cohort=cohort,baseline=baseline,challenger=challenger,
                                    **paired_interval(d[d.arm.eq(baseline)],d[d.arm.eq(challenger)])))
        final_train=pd.concat([history,current],ignore_index=True);final=fit_median(final_train)
        interval,positive,negative=coefficient_stability(final_train)
        fitlog.extend([dict(cohort=cohort,stage='historical_prior',**serialize_fit(prior)),
                       dict(cohort=cohort,stage='all_completed_2026_future_use_only',**serialize_fit(final))])
        for i,feature in enumerate(FEATURES):
            old=physical_weights(prior)[i];new=physical_weights(final)[i]
            weight_rows.append(dict(cohort=cohort,feature=feature,unit='per +1 net yard/dropback' if feature=='qb_delta' else 'per +10pp home-minus-away absence',
                                    prior_points=float(old),updated_points=float(new),update_points=float(new-old),
                                    descriptive_bootstrap_lo=float(interval[0,i]),descriptive_bootstrap_hi=float(interval[1,i]),
                                    share_positive=float(positive[i]),share_negative=float(negative[i])))
        # Post-hoc estimation diagnostic only: checks whether zero weights were
        # imposed by shrinkage. These fits never generate held-out predictions,
        # select alpha, or replace the prespecified penalized model.
        unpen_prior=fit_median(history,alpha=0.)
        unpen_final=fit_median(final_train,alpha=0.)
        for i,feature in enumerate(FEATURES):
            unpenalized.append(dict(cohort=cohort,feature=feature,estimation_only_not_backtested=True,
                                    historical_points=float(physical_weights(unpen_prior)[i]),
                                    all_completed_2026_points=float(physical_weights(unpen_final)[i])))
        print(cohort,'historical',len(history),'saved2026',len(current),flush=True)
    predictions=pd.concat(all_predictions,ignore_index=True)
    predictions.to_csv(OUT/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(all_metrics).to_csv(OUT/'metrics.csv',index=False)
    pd.DataFrame(weight_rows).to_csv(OUT/'positional_weights.csv',index=False)
    pd.DataFrame(reliability).to_csv(OUT/'reliability.csv',index=False)
    pd.DataFrame(unpenalized).to_csv(OUT/'unpenalized_estimation_only.csv',index=False)
    (OUT/'fit_audit.json').write_text(json.dumps(fitlog,indent=2)+'\n')
    (OUT/'comparisons.json').write_text(json.dumps(comparisons,indent=2)+'\n')
    report(all_metrics,weight_rows,comparisons,unpenalized)
    print(pd.DataFrame(all_metrics)[['cohort','arm','n','wins','losses','pushes','units','mae','log_loss']].to_string(index=False))


def report(scores,weights,comparisons,unpenalized):
    meta=json.load(open(source.INPUT/'provenance.json'))
    lines=['# Saved 2026 injuries: median replay and learned positional weights','',
           'Research only. Every scored forecast uses weights fitted before its evaluation week. Final updated weights use',
           'all completed eligible games and are for future review only, never the weights used to claim their own backtest.',
           'No production coefficient, report, lock, journal or public forecast is rewritten.','',
           '**Scope:** this fits injury-to-margin residual corrections. It does not estimate a starter-to-replacement',
           'efficiency change, rebuild the team efficiency inputs, or propagate that change through the base fit/median map.',
           'Zero coefficients here do not reject that separate injury-to-efficiency mechanism.','',
           '**Observed result:** every prespecified penalized positional/QB correction is zero in the historical,',
           'weekly-updated and final fits. ATS picks and point forecasts are unchanged. Any rolling cover-score',
           'difference from the original comes from the updated empirical error reference, not injury coefficients.','',
           '## Coverage','',f"Saved pre-T60 vectors: {meta['saved_vector_n']} completed games. Both-team complete saved official reports: {meta['official_report_n']}.",
           f"Historical training: {meta['historical_vector_n']} production-proxy games; {meta['historical_medical_n']} final-report medical-only games.",
           f"Historical medical exclusions for nonfinal/missing report state: {len(meta['historical_medical_nonfinal_report_exclusions'])} games.",
           'The two evidence cohorts use different absence definitions and must not be pooled or treated as independent replicas.',
           'Saved vectors include roster-departure proxies and can predate final inactives. Official reports are captured by T60,',
           'but their snap weights use reconstructed earlier snap data whose original publication timestamps are unverified.','',
           '## Held-out 2026 replay','',
           'Flat 1u risk at assumed -110, pushes refunded/included in ROI denominator. Cover rates exclude pushes.',
           'Original and control comparisons use identical eligible games within each cohort. Lower MAE/cover LL is better.','',
           '| Evidence | Arm | n | W-L-P | Units | ROI ± SE | MAE | Median residual | Cover LL |',
           '|---|---|---:|---|---:|---:|---:|---:|---:|']
    for r in scores:
        mae='—' if r['mae'] is None else f"{r['mae']:.3f}"
        median='—' if r['median_residual'] is None else f"{r['median_residual']:.3f}"
        lines.append(f"| {r['cohort']} | {r['arm']} | {r['n']} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | {100*r['roi']:+.1f}% ± {100*r['roi_se']:.1f}pp | {mae} | {median} | {r['log_loss']:.5f} |")
    lines+=['','## Learned corrections, not causal injury valuations','',
            'Non-QB units: points per +10 percentage points of home-minus-away absence share. QB: incremental points per',
            '+1 net yard/dropback in home-minus-away projected-QB delta, beyond the base model\'s existing QB term.',
            'Positive coefficients can reflect market overreaction or confounding; they are not evidence an injury helps a team.',
            'Bootstrap ranges use 200 whole-week refits, are descriptive, and do not adjust the prior research selection.','',
            '| Evidence | Term | Historical prior | After completed eligible 2026 games | Update | Bootstrap range |',
            '|---|---|---:|---:|---:|---|']
    for r in weights:lines.append(f"| {r['cohort']} | {r['feature']} | {r['prior_points']:+.3f} | {r['updated_points']:+.3f} | {r['update_points']:+.3f} | [{r['descriptive_bootstrap_lo']:+.3f}, {r['descriptive_bootstrap_hi']:+.3f}] |")
    lines+=['','## Unpenalized estimation diagnostic — not a backtest','',
            'Added after observing the zero penalized coefficients, solely to check shrinkage/solver behavior.',
            'These estimates use alpha=0; they did not choose settings, generate the replay scores or replace',
            'the prespecified alpha=.02 model. The all-2026 column is fitted on those outcomes and has NO held-out claim.',
            'Units match the positional-weight table above. These are incremental residual corrections, not injury values.','',
            '| Evidence | Term | Earlier-season estimate | Estimate including completed 2026 games |',
            '|---|---|---:|---:|']
    for r in unpenalized:lines.append(f"| {r['cohort']} | {r['feature']} | {r['historical_points']:+.3f} | {r['all_completed_2026_points']:+.3f} |")
    lines+=['','## Paired predictive uncertainty','',
            'Positive gains favor the challenger. 5000 whole-week resamples. The official-report cohort has only two weeks;',
            'its interval is especially fragile and cannot establish dependable positional weights.','',
            '| Evidence | Comparison | MAE gain [95%] | Cover LL gain [95%] |','|---|---|---|---|']
    for r in comparisons:
        a,b=r['mae_gain_ci95'];c,d=r['log_loss_gain_ci95']
        lines.append(f"| {r['cohort']} | {r['challenger']} vs {r['baseline']} | {r['mae_gain']:+.3f} [{a:+.3f}, {b:+.3f}] | {r['log_loss_gain']:+.5f} [{c:+.5f}, {d:+.5f}] |")
    lines+=['','## Method and limitations','',
            '- Exact .5-quantile regression with fixed alpha=.02 L1 shrinkage; no squared-error mean correction.',
            '- Weekly updates add only earlier saved 2026 games. No same-week or later outcome trains a scored prediction.',
            '- Final all-2026 weights are separated from held-out scores; fitting and scoring them on the same games would be lookahead.',
            '- Historical base recipes, injury inputs and all evaluated outcomes are exposed research; this is not independent confirmation.',
            '- Injury collection/selection is audited separately from original capture/publication and from medical severity or player quality.',
            '- Snap shares quantify recent dependence; players without prior team snaps have no measurable share and are counted in the input audit.',
            '- Conditional cover probabilities use a prior empirical residual distribution with integer interpolation and half-count smoothing.',
            '- Six non-QB units and the incremental QB correction have separate learned coefficients; no team-specific or injury-interaction terms.',
            '- Coefficient changes may be unstable or shrink to zero; no larger penalty is imposed just to explain LAC/PHI.', '',
            'Reproduce: `python research/positional_injury_weights.py`; rebuild frozen inputs with `--prepare`. See POSITIONAL_INJURY_WEIGHTS.md.','']
    (OUT/'REPORT.md').write_text('\n'.join(lines))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',action='store_true');args=parser.parse_args()
    if args.prepare:source.prepare()
    run()
