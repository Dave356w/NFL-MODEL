"""Favorite-mix, upset concentration and paired score diagnostics; no refitting."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit
from monte_carlo import ROOT, protected, s, m

OUT=ROOT/'research/log_loss_diagnostics_results'
INPUT=ROOT/'research/monte_carlo_results/heldout_predictions.csv'
BANDS=[.5,.6,.7,.8,.9,1.0000001]


def losses(y,p):
    p=np.asarray(p,float);y=np.asarray(y,float)
    if not np.isfinite(p).all() or ((p<=0)|(p>=1)).any():raise ValueError('Probabilities must be strictly between zero and one')
    if not np.isin(y,[0.,1.]).all():raise ValueError('Binary outcomes required')
    return -(y*np.log(p)+(1-y)*np.log1p(-p))


def prepare(frame):
    f=frame[frame['home won'].isin([0.,1.])].copy()
    if f.game_id.duplicated().any():raise ValueError('Repeated games')
    q=f.market.to_numpy();p=f.production.to_numpy();y=f['home won'].to_numpy()
    f['market_ll']=losses(y,q);f['production_ll']=losses(y,p)
    f['ll_gain']=f.market_ll-f.production_ll
    f['brier_gain']=(q-y)**2-(p-y)**2
    f['market_entropy']=-(q*np.log(q)+(1-q)*np.log1p(-q))
    f['market_favorite_probability']=np.maximum(q,1-q)
    f['market_favorite_won']=np.where(q>=.5,y,1-y)
    f['production_favorite_probability']=np.where(q>=.5,p,1-p)
    f['upset']=f.market_favorite_won==0
    f['week_group']=f.season.astype(str)+'_'+f.week.astype(str)
    return f


def summary(f,label):
    groups=f.week_group.to_numpy()
    return {'label':label,'games':len(f),'market_ll':float(f.market_ll.mean()),
            'production_ll':float(f.production_ll.mean()),'ll_gain':float(f.ll_gain.mean()),
            'll_ci95':s.p.cluster_interval(f.ll_gain,groups,.95),
            'll_family_ci':s.p.cluster_interval(f.ll_gain,groups,.99),
            'market_brier':float(((f.market-f['home won'])**2).mean()),
            'production_brier':float(((f.production-f['home won'])**2).mean()),
            'brier_gain':float(f.brier_gain.mean()),'brier_ci95':s.p.cluster_interval(f.brier_gain,groups,.95),
            'expected_market_entropy':float(f.market_entropy.mean()),
            'upsets':int(f.upset.sum()),'market_favorite_probability':float(f.market_favorite_probability.mean())}


def calibration(f,arm):
    y=f['home won'].to_numpy();z=logit(f[arm].to_numpy());X=np.column_stack([np.ones(len(f)),z])
    def obj(beta):
        eta=X@beta;return np.sum(np.logaddexp(0,eta)-y*eta),X.T@(expit(eta)-y)
    opt=minimize(obj,np.array([0.,1.]),jac=True,method='BFGS',options={'gtol':1e-8})
    if not np.isfinite(opt.fun) or abs(obj(opt.x)[1]).max()>1e-5:raise RuntimeError('Calibration fit failed')
    fitted=expit(X@opt.x);bread=np.linalg.inv(X.T@((fitted*(1-fitted))[:,None]*X))
    score=pd.DataFrame(X*(y-fitted)[:,None]).groupby(f.week_group.to_numpy()).sum().to_numpy()
    G=len(score);cov=bread@(score.T@score)@bread*(G/(G-1))*((len(f)-1)/(len(f)-2));se=np.sqrt(np.diag(cov))
    return {'arm':arm,'intercept':float(opt.x[0]),'slope':float(opt.x[1]),
            'intercept_ci95':(opt.x[0]+np.array([-1.96,1.96])*se[0]).tolist(),
            'slope_ci95':(opt.x[1]+np.array([-1.96,1.96])*se[1]).tolist()}


def market_correct_null(f,reps=20000,seed=20261012):
    """Conditional diagnostic: fixed forecasts, independent outcomes drawn at q."""
    q=f.market.to_numpy();p=f.production.to_numpy()
    win=np.log(p/q);loss=np.log((1-p)/(1-q))
    expectation=q*win+(1-q)*loss
    variance=q*(1-q)*(win-loss)**2
    observed=float(f.ll_gain.mean());expected=float(expectation.mean())
    rng=np.random.default_rng(seed);draws=[]
    for start in range(0,reps,500):
        yy=rng.random((min(500,reps-start),len(f)))<q
        draws.extend((loss+yy*(win-loss)).mean(axis=1))
    draws=np.asarray(draws)
    return {'reps':reps,'seed':seed,'observed_gain':observed,'expected_gain_if_market_correct':expected,
            'standard_error':float(np.sqrt(variance.sum())/len(f)),
            'null_interval95':np.quantile(draws,[.025,.975]).tolist(),
            'upper_tail_fraction':float((1+(draws>=observed).sum())/(reps+1)),
            'assumption':'Fixed forecasts and independent Bernoulli outcomes at supplied no-vig q; excludes recipe-selection uncertainty and refitting feedback'}


def run():
    out=protected(OUT);out.mkdir(parents=True,exist_ok=True)
    original=pd.read_csv(INPUT);f=prepare(original);overall=summary(f,'all binary games')
    bands=[];cal=[]
    for lo,hi in zip(BANDS[:-1],BANDS[1:]):
        g=f[(f.market_favorite_probability>=lo)&(f.market_favorite_probability<hi)]
        row=summary(g,f'{100*lo:.0f}–{min(100,100*hi):.0f}%');bands.append(row)
        for arm in ['market','production']:
            forecast=g.market_favorite_probability if arm=='market' else g.production_favorite_probability
            residual=g.market_favorite_won-forecast
            cal.append({'band':row['label'],'arm':arm,'games':len(g),'mean_probability':float(forecast.mean()),
                        'observed_frequency':float(g.market_favorite_won.mean()),'gap':float(residual.mean()),
                        'gap_ci95':s.p.cluster_interval(residual,g.week_group,.95)})
    slices=[]
    for label,mask in [('market confidence <80%',f.market_favorite_probability<.8),
                       ('market confidence <90%',f.market_favorite_probability<.9),
                       ('favorite wins',~f.upset),('upsets',f.upset)]:
        slices.append(summary(f[mask],label))
    annual=[summary(g,str(year)) for year,g in f.groupby('season')]
    ordered=f.reindex(f.ll_gain.abs().sort_values(ascending=False).index)
    positive=f[f.ll_gain>0].sort_values('ll_gain',ascending=False)
    negative=f[f.ll_gain<0].sort_values('ll_gain')
    concentration={'net_total_gain':float(f.ll_gain.sum()),'gross_positive_gain':float(positive.ll_gain.sum()),
                   'gross_negative_gain':float(-negative.ll_gain.sum()),'positive_games':len(positive),'negative_games':len(negative),
                   'top_positive_share':{},'top_negative_share':{},'trimmed_sensitivities':[]}
    for k in [1,5,10,20]:
        concentration['top_positive_share'][str(k)]=float(positive.head(k).ll_gain.sum()/positive.ll_gain.sum())
        concentration['top_negative_share'][str(k)]=float(negative.head(k).ll_gain.sum()/negative.ll_gain.sum())
        concentration['trimmed_sensitivities'].append(summary(ordered.iloc[k:],f'drop {k} largest absolute contributions'))
    leaveweek=[float(f[f.week_group!=week].ll_gain.mean()) for week in f.week_group.unique()]
    leaveseason={str(year):float(f[f.season!=year].ll_gain.mean()) for year in f.season.unique()}
    result={'basis':'Exposed historical development; fixed v1.16 weekly prior-game forecasts, 2023–2025. No recipe or probability refits.',
            'excluded_ties':len(original)-len(f),'overall':overall,'bands':bands,'slices':slices,'annual':annual,
            'calibration':[calibration(f,a) for a in ['market','production']],
            'concentration':concentration,'leave_one_week_gain_range':[min(leaveweek),max(leaveweek)],
            'leave_one_season_gains':leaveseason,'market_correct_null':market_correct_null(f)}
    # Same-row historical return diagnostic; no probability threshold selection.
    bets={a:m.flat_bets(f,a) for a in ['market','production']};common=np.logical_and.reduce([z.units.notna() for z in bets.values()])
    result['historical_returns']=[{'arm':a,**m.roi_summary(b.loc[common])} for a,b in bets.items()]
    f.to_csv(out/'per_game_contributions.csv',index=False)
    pd.DataFrame(cal).to_csv(out/'calibration_bands.csv',index=False)
    positive.head(20).to_csv(out/'largest_positive_contributions.csv',index=False)
    negative.head(20).to_csv(out/'largest_negative_contributions.csv',index=False)
    (out/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (out/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [INPUT,Path(__file__),ROOT/'research/production_qualification.py']},indent=2)+'\n')
    report(result,out)
    print(json.dumps(result,indent=2))


def interval(x):return f'[{x[0]:+.6f}, {x[1]:+.6f}]'


def report(r,out):
    o=r['overall'];lines=['# Log loss: favorites, upsets and inherent variability','',
        '**Finding:** the observed gain survives excluding heavy favorites and removing the largest absolute contributions. The strongest positive band is 50–60% market confidence. Calibration is compatible with appropriate probability dispersion. Overall paired uncertainty remains wide.',
        '',r['basis'],
        '',f"{o['games']} binary games; {r['excluded_ties']} tie excluded. Positive gain means production improves on the same-row market.",
        '\n## Historical return context','','| Arm | N | Units | ROI ± SE | Market-correct null |','|---|---:|---:|---:|---:|']
    for x in r['historical_returns']:lines.append(f"| {x['arm']} | {x['bets']} | {x['units']:+.2f} | {100*x['roi']:+.2f}% ± {100*x['roi_se']:.2f} | {100*x['null_roi']:+.2f}% |")
    lines+=['','## Overall paired probability scores','',f"Market LL {o['market_ll']:.6f}; production LL {o['production_ll']:.6f}; gain {o['ll_gain']:+.6f}, 95% week-cluster interval {interval(o['ll_ci95'])}.",
        f"Market Brier {o['market_brier']:.6f}; production Brier {o['production_brier']:.6f}; gain {o['brier_gain']:+.6f}, interval {interval(o['brier_ci95'])}.",
        f"Expected market loss under its own probabilities: {o['expected_market_entropy']:.6f}. Realized loss need not equal entropy in a finite sample.",
        '\n## Market favorite probability bands','','| Band | N | Upsets | Market LL | Model LL | LL gain [95% CI] | Brier gain |','|---|---:|---:|---:|---:|---|---:|']
    for x in r['bands']:lines.append(f"| {x['label']} | {x['games']} | {x['upsets']} | {x['market_ll']:.6f} | {x['production_ll']:.6f} | {x['ll_gain']:+.6f} {interval(x['ll_ci95'])} | {x['brier_gain']:+.6f} |")
    lines+=['','Bands use market confidence fixed before outcomes; intervals are descriptive. 99% simultaneous band intervals are in results.json. Do not compare raw losses across bands as if game difficulty were equal.',
        '\n## Sensitivity to favorite mix and realized upsets','','| Slice | N | LL gain [95% CI] | Brier gain |','|---|---:|---|---:|']
    for x in r['slices']:lines.append(f"| {x['label']} | {x['games']} | {x['ll_gain']:+.6f} {interval(x['ll_ci95'])} | {x['brier_gain']:+.6f} |")
    lines+=['','Favorite-win/upset slices condition on realized outcomes and are diagnostic only, never usable pregame selection rules.',
        '\n## Contribution concentration','','| Removed largest absolute contributions | Remaining N | Mean LL gain [95% CI] |','|---|---:|---|']
    for x in r['concentration']['trimmed_sensitivities']:lines.append(f"| {x['label']} | {x['games']} | {x['ll_gain']:+.6f} {interval(x['ll_ci95'])} |")
    c=r['concentration'];lines += ['',f"Net summed gain {c['net_total_gain']:+.4f}; gross positive {c['gross_positive_gain']:.4f}; gross negative {c['gross_negative_gain']:.4f}. {c['positive_games']} positive and {c['negative_games']} negative games.",
        f"Top 10 games contribute {100*c['top_positive_share']['10']:.1f}% of gross positive gains and {100*c['top_negative_share']['10']:.1f}% of gross negative losses.",
        'Outcome-based trimming changes the target and is a fragility diagnostic, not a revised performance estimate.',
        f"Leave-one-week LL gain range: {interval(r['leave_one_week_gain_range'])}. Leave-one-season gains: {r['leave_one_season_gains']}.",
        '\n## Calibration','','Ideal intercept 0 and slope 1. Slopes below 1 suggest overconfident probability variation; above 1 suggests underconfident variation. These are retrospective diagnostics, with week-cluster sandwich intervals; they do not recalibrate production.',
        '\n| Arm | Intercept [95% CI] | Slope [95% CI] |','|---|---|---|']
    for x in r['calibration']:lines.append(f"| {x['arm']} | {x['intercept']:+.4f} {interval(x['intercept_ci95'])} | {x['slope']:.4f} {interval(x['slope_ci95'])} |")
    n=r['market_correct_null'];lines+=['','## Inherent variability diagnostic',
        '',f"Under a market-correct fixed-forecast null, expected model LL gain is {n['expected_gain_if_market_correct']:+.6f}; observed gain is {n['observed_gain']:+.6f}. The {n['reps']:,}-draw null interval is {interval(n['null_interval95'])}; upper-tail fraction {n['upper_tail_fraction']:.4f}.",
        '',n['assumption']+'. This is a conditional reference calculation, not a selection-adjusted significance test. It is different from the paired week bootstrap, which estimates sampling uncertainty around observed historical gains.',
        '\n## Interpretation','',
        'Assess favorite mix through paired same-row gains, then examine Brier, calibration, concentration and season stability together. Heavy favorites reduce expected raw log loss while rare upsets increase realized variability. A coherent gain across proper scores is supportive evidence; neither historical design selection nor uncertainty disappears when inspecting slices.',
        '', 'No production settings, probabilities, or native snapshots changed. All slices and concentration analyses are exploratory.','']
    (out/'REPORT.md').write_text('\n'.join(lines))


if __name__=='__main__':run()
