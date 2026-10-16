"""Separate market spread signal, incremental probabilities and ATS price cost."""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, xlogy

import plain_ats_110 as a

m=a.m
b=a.s.b
OUT=m.j.ROOT/'research/spread_signal_separation'
MARGIN_MODELS=('margin_market_spread','margin_zero','margin_prior_home','margin_market_linear','margin_plain','margin_AC1')
WIN_MODELS=('win_prior_home','win_fair','win_market_spread','win_market_spread_total','win_market_moneyline','win_plain','win_AC1')
ATS_MODELS=('ats_market_fair','ats_plain','ats_AC1','ats_legacy')


def design(spread,total,include_total=False):
    spread,total=np.broadcast_arrays(np.asarray(spread,float),np.asarray(total,float))
    x=spread.ravel()/7;t=(total.ravel()-44)/7
    values=[np.ones(len(x)),x]
    if include_total:values += [t,x*t]
    result=np.column_stack(values)
    if not np.isfinite(result).all():raise ValueError('Finite market predictors required')
    return result


def objective(beta,x,y,w):
    eta=x@beta
    return float(w@(np.logaddexp(0,eta)-y*eta)+.005*(beta@beta)),x.T@(w*(expit(eta)-y))+.01*beta


def fit(history,target):
    year,week=int(target['season']),int(target['week'])
    if not m.j.before(history,year,week).all() or (history.season<year-5).any():
        raise ValueError('Strictly earlier six-season market history required')
    if len(history)<100:raise ValueError('At least 100 historical games required')
    age=(year-history.season.to_numpy())*19+week-history.week.to_numpy()
    time=m.normalized_log_weights(-np.log(2)*age/38)
    margin=(history.home_score-history.away_score).to_numpy()
    x=design(history.spread_line,history.total_line)
    line_coef=np.linalg.lstsq(x*np.sqrt(time[:,None]),margin*np.sqrt(time),rcond=None)[0]
    decisive=margin!=0
    weights=time[decisive];weights=weights/weights.sum()*m.effective(weights)
    y=(margin[decisive]>0).astype(float)
    coefficients={};iterations={}
    for name,total in [('spread',False),('spread_total',True)]:
        xx=design(history.spread_line,history.total_line,total)[decisive]
        opt=minimize(objective,np.zeros(xx.shape[1]),args=(xx,y,weights),jac=True,
            method='L-BFGS-B',options=dict(gtol=1e-7,ftol=1e-12,maxiter=1000,maxls=100))
        if not opt.success or not np.isfinite(opt.x).all():raise RuntimeError(f'Market fit failed: {opt.message}')
        coefficients[name]=opt.x.tolist();iterations[name]=int(opt.nit)
    return dict(win_coefficients=coefficients,line_coefficients=line_coef.tolist(),
        prior_home_mean=float(time@margin),prior_home_win=float((weights@y+.5)/(weights.sum()+1)),
        training_games=len(history),training_decisive=int(decisive.sum()),
        training_max_season=int(history.season.max()),
        training_max_week=int(history[history.season.eq(history.season.max())].week.max()),iterations=iterations)


def forecast(target,fitted):
    if (fitted['training_max_season'],fitted['training_max_week']) >= (int(target['season']),int(target['week'])):
        raise ValueError('Future market-fit coefficients')
    spread,total=float(target['spread_line']),float(target['total_line'])
    return dict(margin_market_spread=spread,margin_zero=0.,margin_prior_home=fitted['prior_home_mean'],
        margin_market_linear=float((design(spread,total)@fitted['line_coefficients'])[0]),
        win_prior_home=fitted['prior_home_win'],win_fair=.5,
        win_market_spread=float(expit(design(spread,total)@fitted['win_coefficients']['spread'])[0]),
        win_market_spread_total=float(expit(design(spread,total,True)@fitted['win_coefficients']['spread_total'])[0]))


def loss(y,p):
    return -xlogy(y,p)-xlogy(1-y,1-p)


def price_decomposition(wins,losses,pushes):
    if min(wins,losses,pushes)<0:raise ValueError('Nonnegative counts required')
    n=wins+losses+pushes
    even=wins-losses;cost=wins/11;units=even-cost
    return dict(bets=n,wins=wins,losses=losses,pushes=pushes,even_money_units=float(even),
        price_cost=float(cost),units=float(units),roi=units/n if n else np.nan,
        fair_null_roi=-(wins+losses)/n/22 if n else np.nan)


def describe_margin(g):
    x=np.column_stack([np.ones(len(g)),g.spread_line]);y=g.margin.to_numpy()
    coef=np.linalg.lstsq(x,y,rcond=None)[0];residual=y-x@coef
    scores=pd.DataFrame(x*residual[:,None]).groupby(g.season.astype(str).to_numpy()+'_'+g.week.astype(str).to_numpy()).sum().to_numpy()
    bread=np.linalg.pinv(x.T@x);groups=len(scores)
    covariance=bread@(scores.T@scores)@bread*(groups/(groups-1))*((len(g)-1)/(len(g)-2))
    se=np.sqrt(np.diag(covariance))
    return dict(games=len(g),correlation=float(np.corrcoef(g.spread_line,y)[0,1]),
        raw_spread_R2=float(1-np.sum((y-g.spread_line)**2)/np.sum((y-y.mean())**2)),
        descriptive_intercept=float(coef[0]),descriptive_slope=float(coef[1]),
        intercept_ci95=(coef[0]+np.array([-1.96,1.96])*se[0]).tolist(),
        slope_ci95=(coef[1]+np.array([-1.96,1.96])*se[1]).tolist(),
        interpretation='Same-cohort descriptive OLS; not an out-of-sample forecast')


def run():
    OUT.mkdir(exist_ok=True)
    source=m.load_inputs()
    old=pd.read_csv(a.INPUT,low_memory=False);f=old[old.arm.eq('plain')&old.season.ge(2019)].copy()
    if f.game_id.duplicated().any():raise ValueError('Duplicate plain forecasts')
    f['margin']=f.home_score-f.away_score
    f['winner_y']=np.where(f.margin==0,np.nan,(f.margin>0).astype(float))
    f['ats_y']=np.where(f.margin==f.spread_line,np.nan,(f.margin>f.spread_line).astype(float))
    f['margin_plain']=f.margin_mean;f['win_plain']=f.p_home_non_tie;f['win_market_moneyline']=f.q
    f['ats_plain']=f.cover_conditional;f['ats_market_fair']=.5
    cal_path=m.OUT.parent/'R003_ats_calibration/predictions.csv.gz'
    cal=pd.read_csv(cal_path);cal=cal[cal.configuration.eq('selected')].set_index('game_id')
    if not f.game_id.isin(cal.index).all():raise AssertionError('Missing calibrated ATS records')
    f['ats_AC1']=f.game_id.map(cal.p)
    shape_path=m.OUT.parent/'R003_ats_calibration/distribution_metrics.csv'
    shape=pd.read_csv(shape_path);shape=shape[shape.configuration.eq('selected')].set_index('game_id')
    f['win_AC1']=f.game_id.map(shape.p_home_non_tie);f['margin_AC1']=f.game_id.map(shape.margin_mean)
    rows=[];fits=[]
    for (year,week),g in f.groupby(['season','week'],sort=True):
        history=m.prior(source,g.iloc[0]);fitted=fit(history,g.iloc[0])
        fits.append(dict(target_season=int(year),target_week=int(week),**fitted))
        for _,row in g.iterrows():rows.append(dict(game_id=row.game_id,**forecast(row,fitted)))
    f=f.merge(pd.DataFrame(rows),on='game_id',validate='one_to_one')
    margin_metrics=[];prob_metrics=[];comparisons=[];moneyline=[];ats_returns=[];descriptive=[];bands=[]
    legacy_path=m.OUT.parent/'R003_score_support/predictions.csv.gz'
    legacy=pd.read_csv(legacy_path);legacy=legacy[legacy.arm.eq('empirical__R003_score_support')].set_index('game_id')
    f['ats_legacy']=f.game_id.map(legacy.cover_conditional);f['push_legacy']=f.game_id.map(legacy.cover_push)
    bases=[('2023-25',f.season.between(2023,2025)),('2019-22',f.season.between(2019,2022)),('2026 diagnostic',f.season.eq(2026))]
    for basis,mask in bases:
        g=f[mask].copy();descriptive.append(dict(basis=basis,**describe_margin(g)))
        for col in MARGIN_MODELS:
            z=g[g[col].notna()];error=z.margin-z[col]
            margin_metrics.append(dict(basis=basis,model=col,games=len(z),mae=float(error.abs().mean()),
                rmse=float(np.sqrt((error**2).mean())),mean_actual_minus_predicted=float(error.mean())))
            if len(z):
                for baseline in ['margin_market_spread','margin_prior_home']:
                    delta=np.column_stack([abs(z.margin-z[baseline])-abs(error),(z.margin-z[baseline])**2-error**2])
                    boot=b.week_bootstrap(delta,z.season,z.week)
                    for i,metric in enumerate(['absolute_error','squared_error']):
                        comparisons.append(dict(basis=basis,task='margin',model=col,comparator=baseline,metric=metric,
                            n=len(z),gain=float(delta[:,i].mean()),ci95=b.interval(boot[:,i]),sensitivity_ci=b.interval(boot[:,i],.99)))
        for task,label,prefix,baselines in [('winner','winner_y','win_',['win_prior_home','win_market_spread','win_market_spread_total','win_market_moneyline']),
                                             ('ATS','ats_y','ats_',['ats_market_fair'])]:
            for col in WIN_MODELS if task=='winner' else ATS_MODELS:
                z=g[g[col].notna()&g[label].notna()]
                if not len(z):continue
                ll=loss(z[label],z[col]);brier=(z[label]-z[col])**2
                prob_metrics.append(dict(basis=basis,task=task,model=col,n=len(z),log_loss=float(ll.mean()),
                    brier=float(brier.mean()),accuracy=float(((z[col]>=.5)==z[label]).mean())))
                for baseline in baselines:
                    delta=loss(z[label],z[baseline])-ll;boot=b.week_bootstrap(delta,z.season,z.week)[:,0]
                    comparisons.append(dict(basis=basis,task=task,model=col,comparator=baseline,metric='log_loss',n=int(delta.notna().sum()),
                        gain=float(delta.mean()),ci95=b.interval(boot),sensitivity_ci=b.interval(boot,.99)))
                if task=='winner':
                    graded=m.j.add_binary_and_bet_scores(g.assign(p_home_non_tie=g[col]))
                    bets=graded[graded.model_units.notna()&g[col].notna()]
                    if len(bets):
                        boot=b.week_bootstrap(bets.model_units,bets.season,bets.week)[:,0]
                        moneyline.append(dict(basis=basis,model=col,bets=len(bets),units=float(bets.model_units.sum()),
                            roi=float(bets.model_units.mean()),roi_se=float(bets.model_units.std(ddof=1)/np.sqrt(len(bets))),
                            roi_ci95=b.interval(boot),favorite_units=float(bets.favorite_units.sum()),null_roi=float(bets.model_null.mean())))
        for col in ['ats_market_fair','ats_plain','ats_AC1','ats_legacy']:
            p=g[col].to_numpy();push=g.push_legacy.to_numpy() if col=='ats_legacy' else g.cover_push.to_numpy()
            confidence=np.maximum(p,1-p);ev=(1-push)*(confidence*(1+a.PROFIT)-1);eligible=ev>1e-12
            home=p>=.5;delta=g.margin-g.spread_line
            units=np.where(delta==0,0,np.where(np.where(home,delta>0,delta<0),a.PROFIT,-1))
            actual=units[eligible];z=g[eligible]
            result=price_decomposition(int((actual>0).sum()),int((actual<0).sum()),int((actual==0).sum()))
            favorite=np.where(delta==0,0,np.where(np.where(g.spread_line>=0,delta>0,delta<0),a.PROFIT,-1))
            result.update(basis=basis,model=col,passes=int((~eligible).sum()),
                roi_se=float(actual.std(ddof=1)/np.sqrt(len(actual))) if len(actual)>1 else np.nan,
                favorite_units=float(favorite[eligible].sum()),
                roi_ci95=b.interval(b.week_bootstrap(actual,z.season,z.week)[:,0]) if len(z) else None,
                expected_units=float(ev[eligible].sum()))
            if not np.isclose(result['units'],actual.sum(),atol=1e-10):raise AssertionError('Price decomposition mismatch')
            ats_returns.append(result)
        g['spread_band']=pd.cut(g.spread_line,[-np.inf,-7,-3,0,3,7,np.inf],include_lowest=True)
        for band,z in g.groupby('spread_band',observed=True):
            bands.append(dict(basis=basis,band=str(band),games=len(z),mean_spread=float(z.spread_line.mean()),
                mean_margin=float(z.margin.mean()),mean_residual=float((z.margin-z.spread_line).mean()),
                home_win_rate=float(z.winner_y.mean()),mean_spread_win_probability=float(z.win_market_spread.mean()),
                home_cover_rate=float(z.ats_y.mean())))
    pd.DataFrame(margin_metrics).to_csv(OUT/'margin_metrics.csv',index=False)
    pd.DataFrame(prob_metrics).to_csv(OUT/'probability_metrics.csv',index=False)
    pd.DataFrame(bands).to_csv(OUT/'signed_spread_bands.csv',index=False)
    m.dump(OUT/'paired_comparisons.json',comparisons);m.dump(OUT/'moneyline_returns.json',moneyline)
    m.dump(OUT/'ATS_price_decomposition.json',ats_returns);m.dump(OUT/'descriptive_spread_signal.json',descriptive)
    m.dump(OUT/'fitted_windows.json',fits)
    columns=['game_id','season','week','home_score','away_score','spread_line','total_line','q','margin','winner_y','ats_y']
    columns += [c for c in f if c.startswith(('win_','margin_','ats_')) and c not in columns]
    f[columns].to_csv(OUT/'per_game.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    paths=[m.INPUT,a.INPUT,cal_path,shape_path,legacy_path,Path(__file__),Path(a.__file__),Path(m.__file__),
           m.j.ROOT/'research/joint_market_residuals.py',m.j.ROOT/'research/joint_market_residuals_report.py',OUT/'PLAN.md']
    m.dump(OUT/'provenance.json',dict(basis='Exposed historical development; no independent confirmation',
        new_models='Fixed market-only prior-week baselines, no model/ROI selection',forecast_games=len(f),
        hashes={str(p.resolve().relative_to(m.j.ROOT)):m.j.sha256(p) for p in paths},
        ATS_price_assumption='Both sides -110; not verified historical offers',
        price_comparison='Even-money decomposition keeps the original -110 selected games fixed; no repricing/reselection',
        moneyline_policy='Flat 1u on more likely winner, same quoted prices and pickem exclusions as existing research',
        descriptive_regression='Fits current evaluation outcomes for diagnosis only; separate from prior-trained forecasts',
        AC1_margin_winner_availability='2023-25 only; no raw substitutes for missing older coherent distributions',
        production_changed=False))
    print(pd.DataFrame(prob_metrics).query("basis=='2023-25'").to_string(index=False))
    print(pd.DataFrame(margin_metrics).query("basis=='2023-25'").to_string(index=False))
    print(ats_returns[:4])


if __name__=='__main__':run()
