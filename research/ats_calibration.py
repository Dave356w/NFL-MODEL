"""R003-AC1: chronological calibration and stability-gated ATS decisions."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit, xlogy

import plain_ats_110 as ats

s=ats.s
m=s.m
b=s.b
OUT=m.OUT.parent/'R003_ats_calibration'


@dataclass(frozen=True)
class Config:
    name: str
    family: str
    ridge: int=0


CONFIGS=(Config('fair','fair'),Config('raw','raw'))+tuple(
    Config(f'{family}_r{ridge}',family,ridge)
    for family in ['temperature','platt','context'] for ridge in [10,100])
MAP={c.name:c for c in CONFIGS}


def design(frame,config):
    p=np.asarray(frame.cover_conditional,float)
    if not np.isfinite(p).all() or ((p<0)|(p>1)).any():raise ValueError('Invalid raw cover probabilities')
    z=logit(np.clip(p,1e-6,1-1e-6))
    if config.family=='temperature':return z[:,None]
    if config.family=='platt':return np.column_stack([np.ones(len(z)),z])
    spread=np.asarray(frame.spread_line,float)/7
    total=(np.asarray(frame.total_line,float)-44)/7
    ess=np.asarray(frame.final_ess,float)
    if (ess<=0).any():raise ValueError('Positive effective sample size required')
    x=np.column_stack([np.ones(len(z)),z,spread,total,spread*total,z*50/(ess+50)])
    if not np.isfinite(x).all():raise ValueError('Nonfinite calibration design')
    return x


def objective(coef,x,y,weights,penalty):
    eta=x@coef
    return (float(weights@(np.logaddexp(0,eta)-y*eta)+.5*np.sum(penalty*coef**2)),
            x.T@(weights*(expit(eta)-y))+penalty*coef)


def fit(history,target,config):
    year,week=int(target['season']),int(target['week'])
    if not m.j.before(history,year,week).all() or (history.season<year-5).any():
        raise ValueError('Calibration requires prior-week six-season history')
    h=history[history.home_score-history.away_score!=history.spread_line].copy()
    audit=dict(training_games=len(h),training_seasons=int(h.season.nunique()),
        training_max_season=int(history.season.max()) if len(history) else -1,
        training_max_week=int(history[history.season.eq(history.season.max())].week.max()) if len(history) else -1)
    if len(h)<300 or h.season.nunique()<2:
        return dict(coef=None,reason='insufficient_OOF_data',converged=True,**audit)
    x=design(h,config)
    y=((h.home_score-h.away_score)>h.spread_line).to_numpy(float)
    age=(year-h.season.to_numpy())*19+week-h.week.to_numpy()
    time=m.normalized_log_weights(-np.log(2)*age/38)
    weights=time*m.effective(time)
    penalty=np.full(x.shape[1],float(config.ridge))
    slope=0 if config.family=='temperature' else 1
    if config.family!='temperature':penalty[0]=100
    bounds=[(None,None)]*x.shape[1];bounds[slope]=(0.,1.)
    result=minimize(objective,np.zeros(x.shape[1]),args=(x,y,weights,penalty),jac=True,
        method='L-BFGS-B',bounds=bounds,options=dict(gtol=1e-7,ftol=1e-12,maxiter=1000,maxls=100))
    if not result.success or not np.isfinite(result.x).all():
        raise RuntimeError(f'Calibration optimizer failed: {result.message}')
    return dict(coef=result.x.tolist(),reason='fitted',converged=True,iterations=int(result.nit),
        objective=float(result.fun),**audit)


def predict(frame,fitted,config):
    if not all((fitted['training_max_season'],fitted['training_max_week'])<(r.season,r.week) for r in frame.itertuples()):
        raise ValueError('Future calibration coefficients')
    if fitted['coef'] is None:return np.full(len(frame),.5)
    return expit(design(frame,config)@np.asarray(fitted['coef']))


def decision(p,p_stable,push,ess,rule,support_fallback=False):
    if not 0<=p<=1 or not 0<=p_stable<=1 or not 0<=push<=1 or ess<=0:
        raise ValueError('Invalid decision inputs')
    if rule not in ['EV','Stable']:raise ValueError('Unknown decision rule')
    offer=ats.choose((1-push)*p,push,(1-push)*(1-p))
    side=offer['side']
    if support_fallback:return dict(offer,side='pass',selected_ev=0.,reason='unsupported_atoms')
    if rule=='Stable' and side!='pass':
        alternate=ats.choose((1-push)*p_stable,push,(1-push)*(1-p_stable))
        if ess<50 or alternate['side']!=side:
            return dict(offer,side='pass',selected_ev=0.,reason='insufficient_support_or_unstable')
    return dict(offer,reason='positive_EV' if side!='pass' else 'no_positive_EV')


def reweight(dist,line,p):
    if not np.isfinite(p) or not 0<=p<=1:raise ValueError('Invalid calibration probability')
    w=dist['weights'];margin=dist['home']-dist['away']
    home=margin>line;away=margin<line
    mass_h=float(w[home].sum());mass_a=float(w[away].sum());decisive=mass_h+mass_a
    if decisive<=0 or (mass_h==0 and p>0) or (mass_a==0 and p<1):return dist,True
    new=w.copy()
    if mass_h:new[home]*=decisive*p/mass_h
    if mass_a:new[away]*=decisive*(1-p)/mass_a
    if not np.isclose(new.sum(),1,atol=1e-12,rtol=0) or (new<0).any():
        raise AssertionError('Invalid calibrated atom weights')
    return dict(dist,weights=new,audit=dict(dist['audit'],final_ess=m.effective(new))),False


def select(archive,year):
    h=archive[(archive.season<year)&(archive.season>=2017)]
    if h.season.nunique()<2:raise ValueError('Need two earlier OOF seasons for selection')
    losses=h.groupby('configuration').cover_ll.mean();counts=h.groupby('configuration').size()
    names=[c.name for c in CONFIGS]
    if set(losses.index)!=set(names) or counts.nunique()!=1 or not np.isfinite(losses).all():
        raise ValueError('Incomplete/nonfinite calibration selection paths')
    name=min(names,key=lambda key:losses[key])
    return name,dict(target_season=int(year),selection_max_season=int(h.season.max()),chosen=name,
                     criterion='cover_log_loss',losses=losses.to_dict())


def load_oof():
    old=pd.read_csv(ats.INPUT,low_memory=False)
    old=old[old.arm.eq('plain')].copy()
    source=m.load_inputs();rows=[]
    fields=['game_id','season','week','home_team','away_team','home_score','away_score','spread_line',
            'total_line','cover_win','cover_push','cover_lose','cover_conditional','final_ess']
    for _,target in source[source.season.between(2015,2016)].iterrows():
        dist=m.forecast(source,target,s.PLAIN_CONFIG)
        grade=m.grade(dist,target)
        rows.append({k:target[k] if k in target else grade[k] for k in fields})
    return pd.concat([pd.DataFrame(rows),old[fields]],ignore_index=True).sort_values(['season','week','game_id']).reset_index(drop=True)


def summaries(predictions,policies,selections,out):
    metrics=[];comparisons=[];returns=[]
    bases=[('2023-25',predictions.season.between(2023,2025)),
           ('2019-22',predictions.season.between(2019,2022)),('2026 diagnostic',predictions.season.eq(2026))]
    bases += [(str(y),predictions.season.eq(y)) for y in sorted(predictions.season.unique()) if y>=2019]
    for basis,mask in bases:
        sub=predictions[mask]
        raw=sub[sub.configuration.eq('raw')].set_index('game_id').sort_index()
        for name,g in sub.groupby('configuration'):
            g=g.set_index('game_id').sort_index()
            if not g.index.equals(raw.index):raise AssertionError('Unpaired probabilities')
            metrics.append(dict(basis=basis,configuration=name,games=len(g),decisive=int(g.cover_ll.notna().sum()),
                cover_ll=float(g.cover_ll.mean()),cover_brier=float(g.cover_brier.mean()),
                mean_probability=float(g.p.mean()),observed_home_cover=float(g.label.mean()),
                mean_absolute_edge=float((g.p-.5).abs().mean())))
            for baseline in ['raw','fair']:
                control=raw if baseline=='raw' else sub[sub.configuration.eq('fair')].set_index('game_id').loc[g.index]
                delta=control.cover_ll-g.cover_ll
                boot=b.week_bootstrap(delta,g.season,g.week)
                comparisons.append(dict(basis=basis,configuration=name,comparator=baseline,
                    gain=float(delta.mean()),ci95=b.interval(boot[:,0]),sensitivity_ci=b.interval(boot[:,0],1-.05/14)))
        psub=policies[policies.game_id.isin(raw.index)]
        raw_units=psub[psub.policy.eq('raw_EV')].set_index('game_id').units
        for name,g in psub.groupby('policy'):
            g=g.sort_values('game_id');bets=g[g.side.ne('pass')]
            wins=int((bets.units>0).sum());losses=int((bets.units<0).sum());pushes=int((bets.units==0).sum())
            per_game=g.units.to_numpy()-raw_units.loc[g.game_id].to_numpy()
            paired=b.week_bootstrap(per_game,g.season,g.week)[:,0]
            if len(bets):
                boot=b.week_bootstrap(np.column_stack([bets.units,bets.units-bets.favorite_units]),bets.season,bets.week)
                roi_ci=b.interval(boot[:,0]);adjusted=b.interval(boot[:,0],1-.05/14)
                favorite_ci=b.interval(boot[:,1])
            else:roi_ci=adjusted=favorite_ci=None
            returns.append(dict(basis=basis,policy=name,games=len(g),bets=len(bets),passes=len(g)-len(bets),
                wins=wins,losses=losses,pushes=pushes,units=float(bets.units.sum()),
                roi=float(bets.units.mean()),roi_se=float(bets.units.std(ddof=1)/np.sqrt(len(bets))) if len(bets)>1 else np.nan,
                roi_ci95=roi_ci,sensitivity_roi_ci=adjusted,favorite_units=float(bets.favorite_units.sum()),
                paired_favorite_ci95=favorite_ci,null_roi=-(wins+losses)/len(bets)/22 if len(bets) else np.nan,
                expected_units=float(bets.selected_ev.sum()),predicted_cover=float(bets.picked_p.mean()),
                realized_cover=wins/(wins+losses) if wins+losses else np.nan,
                calendar_gain_vs_raw=float(per_game.mean()),calendar_gain_ci95=b.interval(paired)))
    pd.DataFrame(metrics).to_csv(out/'metrics.csv',index=False)
    m.dump(out/'comparisons.json',comparisons);m.dump(out/'returns.json',returns)
    main=next(r for r in returns if r['basis']=='2023-25' and r['policy']=='selected_Stable')
    annual=[r for r in returns if r['basis'] in ['2023','2024','2025'] and r['policy']=='selected_Stable']
    contrasts=[r for r in comparisons if r['basis']=='2023-25' and r['configuration']=='selected']
    gates=dict(sample_size=main['bets']>=200 and all(r['bets']>=50 for r in annual),
        positive_ROI_interval=main['roi_ci95'] is not None and main['roi_ci95'][0]>0,
        positive_adjusted_ROI_interval=main['sensitivity_roi_ci'] is not None and main['sensitivity_roi_ci'][0]>0,
        annual_positive=all(r['units']>0 for r in annual),
        proper_score_vs_fair=any(r['comparator']=='fair' and r['gain']>=.0005 and r['ci95'][0]>0 for r in contrasts),
        proper_score_vs_raw=any(r['comparator']=='raw' and r['gain']>=.002 and r['ci95'][0]>0 for r in contrasts),integrity=True)
    decision=dict(experiment='R003-AC1',gates=gates,
        recommendation='retain ATS-edge hypothesis for fresh validation' if all(gates.values()) else 'no established ATS edge',
        independent_confirmation=False,production_promotion=False)
    m.dump(out/'decision.json',decision)
    lines=['# R003-AC1: ATS calibration and stable selection','',f"**{decision['recommendation']}.** Exposed historical development at assumed −110, not forward confirmation.",
        '', '## Return results, 816 games 2023–25', '',
        '| Policy | Bets | W–L–P | Units | ROI ± SE | Same-row favorite units | Null |',
        '|---|---:|---|---:|---:|---:|---:|']
    for r in returns:
        if r['basis']!='2023-25':continue
        roi=f"{100*r['roi']:+.2f}% ±{100*r['roi_se']:.2f} pp" if r['bets'] else 'undefined (no bets)'
        null=f"{100*r['null_roi']:.2f}%" if r['bets'] else '—'
        lines.append(f"| {r['policy']} | {r['bets']} | {r['wins']}–{r['losses']}–{r['pushes']} | {r['units']:+.3f} | {roi} | {r['favorite_units']:+.3f} | {null} |")
    lines+=['','## All-game conditional cover proper scores','','| Model | Cover LL ↓ | Brier ↓ | Mean absolute edge |','|---|---:|---:|---:|']
    for r in metrics:
        if r['basis']=='2023-25':lines.append(f"| {r['configuration']} | {r['cover_ll']:.6f} | {r['cover_brier']:.6f} | {r['mean_absolute_edge']:.6f} |")
    lines+=['',f"Annual choices: {[(r['target_season'],r['chosen']) for r in selections]}.",f'Gates: {gates}.',
        '', 'Primary policy is selected_Stable; EV is a fixed secondary rule, never chosen from historical ROI. All fixed variants, including unfavorable/no-bet arms, are retained. Betting fewer games or matching the market is not an established edge.',
        '', 'Calibration fits only earlier OOF binary outcomes, excluding pushes. Six settings: temperature/Platt/context × ridge 10/100. Model selection uses earlier OOF cover log loss; fair 0.5 and raw are explicit choices. Stable requires raw ESS >=50 and positive EV on the same side after removing the latest available training season.',
        '', 'Historical paired-score atoms and raw push mass are retained by within-cover-group reweighting. No synthetic scores, score translation, ROI tuning, fees, live quotes, production updates or ledger changes. See distribution_metrics.csv for coherent score-distribution side effects.',
        '', 'All history was exposed, including the failures that motivated this family. Intervals use 10,000 paired whole-week draws within season, seed 20261016, conditional on fitted forecasts. Sensitivity uses 14 fixed non-fair policies; it does not correct all adaptive research. Pass-only ROI is undefined, not zero-risk edge evidence.',
        '', 'Prices are assumed uniformly -110 per the user; historical quote timing/availability is unaudited. An established/executable edge requires new independently retained predictions and real contemporaneous offers.',
        '', 'Full per-game probabilities, decisions, annual selections, weekly coefficients/cutoffs, protocol, hashes, proper-score comparisons, returns and independent repeat checks accompany this report.',
        '', 'Reproduce: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/ats_calibration.py`','']
    (out/'REPORT.md').write_text('\n'.join(lines))


def run(out=OUT):
    out=m.guarded_output(out)
    if not out.name.startswith('R003_ats_calibration'):raise ValueError('Use a separate R003_ats_calibration output')
    registered=json.loads((out/'registration_record.json').read_text())
    if registered['protocol_sha256']!=m.j.sha256(out/'PROTOCOL.md'):raise ValueError('Protocol changed')
    oof=load_oof()
    oof.to_csv(out/'base_OOF.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    rows=[];fits=[]
    for (year,week),test in oof[oof.season>=2017].groupby(['season','week'],sort=True):
        history=oof[m.j.before(oof,year,week)&(oof.season>=year-5)]
        reduced=history[history.season<history.season.max()]
        for config in CONFIGS:
            if config.family in ['fair','raw']:
                probabilities=test.cover_conditional.to_numpy() if config.family=='raw' else np.full(len(test),.5)
                alternate=probabilities.copy();cutoff=(int(history.season.max()),int(history[history.season.eq(history.season.max())].week.max()))
            else:
                full=fit(history,test.iloc[0],config);reduced_fit=fit(reduced,test.iloc[0],config)
                probabilities=predict(test,full,config);alternate=predict(test,reduced_fit,config)
                cutoff=(full['training_max_season'],full['training_max_week'])
                for kind,f in [('full',full),('exclude_latest_season',reduced_fit)]:
                    fits.append(dict(target_season=int(year),target_week=int(week),configuration=config.name,kind=kind,**f))
            for row,p,other in zip(test.itertuples(),probabilities,alternate):
                label=float(row.home_score-row.away_score>row.spread_line) if row.home_score-row.away_score!=row.spread_line else np.nan
                support_fallback=(row.cover_win==0 and p>0) or (row.cover_lose==0 and p<1)
                if support_fallback and config.family not in ['fair','raw']:p=row.cover_conditional
                loss=float(-xlogy(label,p)-xlogy(1-label,1-p)) if np.isfinite(label) else np.nan
                meta={k:getattr(row,k) for k in ['game_id','season','week','home_score','away_score','spread_line','total_line','final_ess','cover_push']}
                rows.append(dict(configuration=config.name,**meta,p=float(p),p_stable=float(other),label=label,
                    cover_ll=loss,cover_brier=(p-label)**2,calibration_max_season=cutoff[0],calibration_max_week=cutoff[1],support_fallback=bool(support_fallback)))
        if week==1:print(f'Calibrated {int(year)} W1',flush=True)
    archive=pd.DataFrame(rows);selections=[];chosen=[]
    for year in sorted(archive.loc[archive.season>=2019,'season'].unique()):
        name,audit=select(archive,int(year));selections.append(audit)
        g=archive[archive.season.eq(year)&archive.configuration.eq(name)].copy()
        g['chosen_configuration']=name;g['configuration']='selected';chosen.append(g)
    archive['chosen_configuration']=archive.configuration
    predictions=pd.concat([archive,*chosen],ignore_index=True)
    policies=[]
    for r in predictions.itertuples():
        for rule in ['EV','Stable']:
            d=decision(r.p,r.p_stable,r.cover_push,r.final_ess,rule,r.support_fallback)
            result=r.home_score-r.away_score
            policies.append(dict(game_id=r.game_id,season=r.season,week=r.week,policy=r.configuration+'_'+rule,
                configuration=r.configuration,chosen_configuration=r.chosen_configuration,
                p=r.p,p_stable=r.p_stable,push=r.cover_push,**d,
                units=ats.settle(d['side'],result,r.spread_line),
                favorite_units=ats.settle('home' if r.spread_line>=0 else 'away',result,r.spread_line),
                picked_p=r.p if d['side']=='home' else 1-r.p if d['side']=='away' else np.nan))
    policies=pd.DataFrame(policies)
    # Fixed arms from 2017–18 exist for selection; common reporting begins 2019.
    report_predictions=predictions[predictions.season>=2019]
    report_policies=policies[policies.season>=2019]
    if not all((r.calibration_max_season,r.calibration_max_week)<(r.season,r.week) for r in predictions.itertuples()):
        raise AssertionError('Future calibration cutoff')
    if not all(r['selection_max_season']<r['target_season'] for r in selections):raise AssertionError('Future model selection')
    if predictions.duplicated(['configuration','game_id']).any():raise AssertionError('Duplicate predictions')
    if not all(len(g)==816 for _,g in predictions[predictions.season.between(2023,2025)].groupby('configuration')):
        raise AssertionError('Main population mismatch')
    distribution_rows=[];source=m.load_inputs()
    main=predictions[predictions.season.between(2023,2025)]
    for game_id,group in main.groupby('game_id',sort=True):
        target=source[source.game_id.eq(game_id)].iloc[0]
        base=m.forecast(source,target,s.PLAIN_CONFIG)
        for r in group.itertuples():
            dist,fallback=reweight(base,float(r.spread_line),r.p)
            grade=m.grade(dist,target)
            if not fallback and abs(grade['cover_conditional']-r.p)>1e-12:raise AssertionError('Calibrated atom mismatch')
            distribution_rows.append(dict(game_id=game_id,configuration=r.configuration,**grade,support_fallback=fallback))
    pd.DataFrame(distribution_rows).to_csv(out/'distribution_metrics.csv',index=False)
    predictions.to_csv(out/'predictions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    policies.to_csv(out/'decisions.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    m.dump(out/'fitted_windows.json',fits);m.dump(out/'annual_selections.json',selections)
    paths=[ats.INPUT,m.INPUT,Path(__file__),Path(ats.__file__),Path(s.__file__),Path(m.__file__),
        m.j.ROOT/'research/joint_market_residuals.py',m.j.ROOT/'research/joint_market_residuals_report.py']
    m.dump(out/'provenance.json',dict(experiment='R003-AC1',registration=registered,
        configurations=[asdict(c) for c in CONFIGS],hashes={str(p.resolve().relative_to(m.j.ROOT)):m.j.sha256(p) for p in paths},
        probability_forecasts=len(predictions),fitted_windows=len(fits),raw2015_16_reconstruction=int(oof.season.between(2015,2016).sum()),
        independent_validation=False,production_changed=False))
    summaries(report_predictions,report_policies,selections,out)
    print((out/'REPORT.md').read_text(),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=OUT)
    run(parser.parse_args().output_dir)
