"""Earlier-season-only tests of correction recalibration and close-game stability."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit,logit
from monte_carlo import ROOT,protected,s,m
import log_loss_diagnostics as d

OUT=ROOT/'research/chronological_calibration_results'
ARMS=['market','production','global_calibration','close_only_calibration','selected_scale']
SCALES=[0.,.25,.5,.75,1.,1.25]


def fit_calibration(train,year,close_only=False):
    if not (train.season<year).all():raise ValueError('Calibration contains evaluation season')
    if close_only:train=train[np.maximum(train.market,1-train.market)<.6].copy()
    if len(train)<50:raise ValueError('Insufficient earlier-season calibration games')
    q=train.market.to_numpy();p=train.production.to_numpy();y=train['home won'].to_numpy()
    z=logit(p)-logit(q);X=np.column_stack([np.ones(len(train)),z]);offset=logit(q)
    w=np.exp2(-(year-train.season.to_numpy())/2);w/=w.sum();prior=np.array([0.,1.])
    def obj(beta):
        eta=offset+X@beta
        return np.sum(w*(np.logaddexp(0,eta)-y*eta))+.005*np.sum((beta-prior)**2),X.T@(w*(expit(eta)-y))+.01*(beta-prior)
    opt=minimize(obj,prior,jac=True,method='BFGS',options={'gtol':1e-9})
    if abs(obj(opt.x)[1]).max()>1e-6 or not np.isfinite(opt.fun):raise RuntimeError('Calibration did not converge')
    return {'intercept':float(opt.x[0]),'correction_scale':float(opt.x[1]),'training_games':len(train),'max_source_season':int(train.season.max()),'close_only':close_only}


def apply_calibration(frame,fit):
    q=frame.market.to_numpy();p=frame.production.to_numpy()
    value=expit(logit(q)+fit['intercept']+fit['correction_scale']*(logit(p)-logit(q)))
    return np.where(np.maximum(q,1-q)<.6,value,p) if fit['close_only'] else value


def select_scale(train,year):
    if not (train.season<year).all():raise ValueError('Scale selection contains evaluation season')
    y=train['home won'].to_numpy();base=logit(train.market.to_numpy());delta=logit(train.production.to_numpy())-base
    scores={scale:float(d.losses(y,expit(base+scale*delta)).mean()) for scale in SCALES}
    selected=min(SCALES,key=lambda x:(scores[x],abs(x-1),x))
    return {'chosen_scale':selected,'scores':scores,'max_source_season':int(train.season.max())}


def score(frame,arm,label):
    y=frame['home won'].to_numpy();p=frame[arm].to_numpy();reference=frame.production.to_numpy()
    gain=d.losses(y,reference)-d.losses(y,p);brier=(reference-y)**2-(p-y)**2
    groups=(frame.season.astype(str)+'_'+frame.week.astype(str)).to_numpy()
    return {'arm':arm,'slice':label,'games':len(frame),'log_loss':float(d.losses(y,p).mean()),
            'brier':float(((p-y)**2).mean()),'ll_gain_vs_production':float(gain.mean()),
            'll_ci95':s.p.cluster_interval(gain,groups,.95),'ll_family_ci':s.p.cluster_interval(gain,groups,1-.05/3),
            'brier_gain_vs_production':float(brier.mean()),'brier_ci95':s.p.cluster_interval(brier,groups,.95)}


def run():
    out=protected(OUT);out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'research/shrinkage_results/frozen_training_features.csv.gz';f=pd.read_csv(source)
    eligible=f.ready&f['home won'].isin([0.,1.])&np.isfinite(f.q)&np.isfinite(f[s.CONTEXTS]).all(axis=1)
    training=f[eligible];oof=training[training.season.between(2021,2025)].copy();cutoffs=[]
    for (year,week),g in oof.groupby(['season','week'],sort=True):
        train=training[m.before(training,year,week)]
        fit=s.fit(train,int(year),int(week));oof.loc[g.index,'production']=s.predict(g,fit)
        cutoffs.append({'season':int(year),'week':int(week),'training_games':len(train),
                       'source_max_season':int(train.season.max()),'source_max_week':int(train[train.season==train.season.max()].week.max())})
    oof['market']=oof.q;held=oof[oof.season.between(2023,2025)].copy();audit=[]
    reference=pd.read_csv(ROOT/'research/monte_carlo_results/heldout_predictions.csv').set_index('game_id')
    error=float(abs(held.production.to_numpy()-reference.loc[held.game_id,'production'].to_numpy()).max())
    if error>1e-7:raise ValueError('Production reproduction failed')
    for year,g in held.groupby('season'):
        prior=oof[oof.season<year]
        for arm,close in [('global_calibration',False),('close_only_calibration',True)]:
            fit=fit_calibration(prior,int(year),close);held.loc[g.index,arm]=apply_calibration(g,fit)
            audit.append({'evaluation_season':int(year),'arm':arm,**fit})
        choice=select_scale(prior,int(year));held.loc[g.index,'selected_scale']=expit(logit(g.market.to_numpy())+choice['chosen_scale']*(logit(g.production.to_numpy())-logit(g.market.to_numpy())))
        audit.append({'evaluation_season':int(year),'arm':'selected_scale',**choice})
    close=np.maximum(held.market,1-held.market)<.6
    summaries=[score(held,a,'all') for a in ARMS]+[score(held[close],a,'market confidence <60%') for a in ARMS]
    annual=[{'season':int(year),**score(g,a,'all')} for year,g in held.groupby('season') for a in ARMS]
    annual_close=[{'season':int(year),**score(g,a,'market confidence <60%')} for year,g in held[close].groupby('season') for a in ['market','production']]
    diagnostic=d.prepare(held[close]);trims=[]
    ordered=diagnostic.reindex(diagnostic.ll_gain.abs().sort_values(ascending=False).index)
    for k in [0,1,5,10]:trims.append(d.summary(ordered.iloc[k:],f'close games, drop {k} largest absolute contributions'))
    bets={a:m.flat_bets(held,a) for a in ARMS};common=np.logical_and.reduce([b.units.notna() for b in bets.values()])
    returns=[{'arm':a,**m.roi_summary(b.loc[common])} for a,b in bets.items()]
    result={'basis':'Exposed historical development; each evaluation season calibrated/selected using earlier-season OOF forecasts only',
            'production_max_error':error,'binary_games':len(held),'close_games':int(close.sum()),
            'summaries':summaries,'annual':annual,'annual_close':annual_close,'close_concentration':trims,
            'fit_audit':audit,'historical_returns':returns}
    held.to_csv(out/'heldout_predictions.csv',index=False);oof.to_csv(out/'prior_week_oof_predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    pd.DataFrame(cutoffs).to_csv(out/'source_cutoffs.csv',index=False)
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (out/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [source,Path(__file__),ROOT/'research/CHRONOLOGICAL_CALIBRATION.md',ROOT/'research/context_shrinkage.py',ROOT/'research/monte_carlo_results/heldout_predictions.csv']},indent=2)+'\n')
    report(result,out);print(json.dumps(result,indent=2))


def report(r,out):
    lines=['# Earlier-season calibration and close-game stability','',r['basis']+'. Formula design followed exposed history, so these are not untouched forward tests.',
        '',f"{r['binary_games']} binary games, {r['close_games']} with market confidence <60%. Production reproduction error {r['production_max_error']:.3g}.",
        '\n## Historical return context','','| Arm | N | Units | ROI ± SE | Market-correct null |','|---|---:|---:|---:|---:|']
    for x in r['historical_returns']:lines.append(f"| {x['arm']} | {x['bets']} | {x['units']:+.2f} | {100*x['roi']:+.2f}% ± {100*x['roi_se']:.2f} | {100*x['null_roi']:+.2f}% |")
    lines+=['','## Paired probability comparisons','','Positive gain means the arm improves over production. Intervals use season/week clusters. Simultaneous intervals correct three all-game challenger comparisons; close slices remain descriptive.','','| Slice | Arm | N | LL ↓ | LL gain [95% CI] | Brier ↓ |','|---|---|---:|---:|---|---:|']
    for x in r['summaries']:lines.append(f"| {x['slice']} | {x['arm']} | {x['games']} | {x['log_loss']:.6f} | {x['ll_gain_vs_production']:+.6f} {d.interval(x['ll_ci95'])} | {x['brier']:.6f} |")
    lines+=['','## Close-matchup annual replication','','| Season | N | Market LL | Production LL | Production gain [95% CI] |','|---|---:|---:|---:|---|']
    for year in [2023,2024,2025]:
        q=next(x for x in r['annual_close'] if x['season']==year and x['arm']=='market');p=next(x for x in r['annual_close'] if x['season']==year and x['arm']=='production')
        ci=[-q['ll_ci95'][1],-q['ll_ci95'][0]]
        lines.append(f"| {year} | {p['games']} | {q['log_loss']:.6f} | {p['log_loss']:.6f} | {-q['ll_gain_vs_production']:+.6f} {d.interval(ci)} |")
    lines+=['','## Earlier-season fit choices','']
    for x in r['fit_audit']:
        if x['arm']=='selected_scale':lines.append(f"- {x['evaluation_season']} selected correction scale {x['chosen_scale']}; source through {x['max_source_season']}.")
        else:lines.append(f"- {x['evaluation_season']} {x['arm']}: intercept {x['intercept']:+.4f}, correction scale {x['correction_scale']:.4f}; {x['training_games']} games through {x['max_source_season']}.")
    lines+=['','## Close-band contribution sensitivity','','| Removed largest absolute contributions | N | Production LL gain [95% CI] |','|---|---:|---|']
    for x in r['close_concentration']:lines.append(f"| {x['label']} | {x['games']} | {x['ll_gain']:+.6f} {d.interval(x['ll_ci95'])} |")
    lines+=['','Trimming conditions on outcomes and is only a fragility diagnostic. Inspect annual consistency before interpreting the pooled close-band average.',
        '', 'Recalibration holds market prices fixed and adjusts only the model correction and intercept. The fixed ridge/scale grid are research choices; earlier-season fitting prevents calibration leakage but cannot remove historical design selection. No production, price source, native snapshots or deployment changes.','']
    (out/'REPORT.md').write_text('\n'.join(lines))


if __name__=='__main__':run()
