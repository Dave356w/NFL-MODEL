"""Clean weekly-refitted market-offset ablation; see MARKET_OFFSET_ABLATION.md."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import context_shrinkage as s

m, p, ROOT = s.m, s.p, s.ROOT
ARMS = ('with_market', 'without_market', 'market_only')


def summarize(held):
    bets={a:m.flat_bets(held,a) for a in ARMS}
    common=np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    proper=held['home won'].isin([0.,1.]).to_numpy()
    groups=(held.season.astype(str)+'_'+held.week.astype(str)).to_numpy()
    y=held['home won'].to_numpy(); losses={a:s.loss(y,held[a]) for a in ARMS}
    rows=[];annual=[]
    for arm in ARMS:
        b=bets[arm].loc[common]
        rows.append({'arm':arm,**m.roi_summary(b),
                     'roi_ci95':p.cluster_interval(b.units,groups[common],.95),
                     'log_loss':float(losses[arm][proper].mean()),
                     'brier':float(((held[arm]-held['home won'])**2).to_numpy()[proper].mean())})
        for year in sorted(held.season.unique()):
            mask=(held.season==year).to_numpy()
            annual.append({'arm':arm,'season':int(year),**m.roi_summary(bets[arm].loc[common&mask]),
                           'log_loss':float(losses[arm][proper&mask].mean())})
    pairs=[]
    for comparator in ('without_market','market_only'):
        du=(bets['with_market'].units-bets[comparator].units).to_numpy()[common]
        dl=(losses[comparator]-losses['with_market'])[proper]
        db=(((held[comparator]-held['home won'])**2-(held.with_market-held['home won'])**2).to_numpy())[proper]
        pairs.append({'comparator':comparator,'roi_gain':float(du.mean()),
                      'roi_gain_ci95':p.cluster_interval(du,groups[common],.95),
                      'll_gain':float(dl.mean()),'ll_gain_ci95':p.cluster_interval(dl,groups[proper],.95),
                      'brier_gain':float(db.mean()),'brier_gain_ci95':p.cluster_interval(db,groups[proper],.95),
                      'side_flips':int(((held.with_market>.5)!=(held[comparator]>.5)).to_numpy()[common].sum())})
    return {'results':rows,'comparisons':pairs,'by_season':annual,'bets':int(common.sum()),
            'proper_games':int(proper.sum()),'excluded_bets':held.loc[~common,'game_id'].tolist()}


def run(output_dir):
    output_dir=output_dir.resolve()
    if any(output_dir==x or x in output_dir.parents for x in (ROOT/'data',ROOT/'public')):
        raise ValueError('Research cannot write production outputs')
    pack=ROOT/'research/shrinkage_results/frozen_training_features.csv.gz'
    archive=ROOT/'research/shrinkage_results/archived_current_inputs.jsonl'
    f=pd.read_csv(pack)
    eligible=f.ready & f['home won'].isin([0.,1.]) & np.isfinite(f.q) & np.isfinite(f[s.CONTEXTS]).all(axis=1)
    evaluation=f.ready & f['home won'].isin([0.,.5,1.]) & np.isfinite(f.q) & np.isfinite(f[s.CONTEXTS]).all(axis=1) & f.season.between(2023,2025)
    held=f.loc[evaluation,p.BASE_COLS].copy();audit=[]
    for (year,week),rows in held.groupby(['season','week'],sort=True):
        train=f[eligible&m.before(f,year,week)];test=f.loc[rows.index]
        for arm,offset in [('with_market',True),('without_market',False)]:
            fitted=s.fit(train,int(year),int(week),market_offset=offset)
            held.loc[rows.index,arm]=s.predict(test,fitted)
            audit.append({'arm':arm,'evaluation_season':int(year),'evaluation_week':int(week),
                          'training_games':fitted['training_games'],'training_max_season':fitted['training_max_season'],
                          'training_max_week':fitted['training_max_week'],'market_offset':offset})
        if week==1:print(f'Completed season {year} week 1',flush=True)
    held['market_only']=held.q
    if not np.isfinite(held[list(ARMS)]).all().all():raise ValueError('Incomplete predictions')
    committed=pd.read_csv(ROOT/'research/production_adoption_results/historical_reproduction.csv').set_index('game_id')
    reference=committed.loc[held.game_id,'production_probability'].to_numpy()
    error=float(np.max(np.abs(held.with_market.to_numpy()-reference)))
    if error>=1e-7:raise ValueError('Production reproduction failed')
    current=[];fits={}
    for r in [json.loads(x) for x in archive.read_text().splitlines()]:
        year,week=r['season'],r['week'];train=f[eligible&m.before(f,year,week)]
        test=pd.DataFrame([{**r['model_inputs'],'q':r['market_no_vig_wp']}])
        item={'game_id':r['game_id'],'generated_utc':r['generated_utc'],'archived_probability':r['model_wp'],
              'market_only':r['market_no_vig_wp']}
        for arm,offset in [('with_market',True),('without_market',False)]:
            key=(year,week,arm)
            if key not in fits:fits[key]=s.fit(train,year,week,market_offset=offset)
            item[arm]=float(s.predict(test,fits[key])[0])
        current.append(item)
    current_error=max(abs(r['with_market']-r['archived_probability']) for r in current)
    if current_error>=1e-7:raise ValueError('Archived forecast reproduction failed')
    timing=all((r['training_max_season'],r['training_max_week'])<(r['evaluation_season'],r['evaluation_week']) for r in audit)
    if not timing:raise ValueError('Future training rows')
    result=summarize(held)
    result.update({'basis':'Exposed historical development; fixed recipe, weekly prior-game refits',
                   'historical_max_probability_error':error,'current_max_probability_error':current_error,
                   'all_fits_prior_week':timing,'fits':len(audit),'revision':m.REVISION})
    output_dir.mkdir(parents=True,exist_ok=True)
    held.to_csv(output_dir/'heldout_predictions.csv',index=False)
    pd.DataFrame(current).to_csv(output_dir/'current_counterfactuals.csv',index=False)
    pd.DataFrame(audit).to_csv(output_dir/'fit_audit.csv',index=False)
    (output_dir/'current_fits.json').write_text(json.dumps({str(k):v for k,v in fits.items()},indent=2)+'\n')
    (output_dir/'results.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    sources=[Path(__file__),ROOT/'research/MARKET_OFFSET_ABLATION.md',ROOT/'research/context_shrinkage.py',ROOT/'nfl_model.py',pack,archive]
    (output_dir/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},indent=2)+'\n')
    write_report(result,current,output_dir)
    print(json.dumps(result['results'],indent=2),flush=True)


def write_report(result,current,out):
    lines=['# Market starting point ablation','','Only difference: the market-logit offset is removed and all coefficients are refitted. Same features, scaling, training rows and penalties.',
           '\nBasis: '+result['basis']+'. Not native forward evidence.',
           f"\n{result['bets']} common flat 1u bets; {result['proper_games']} binary proper scores.",
           '\n| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Log loss | Brier |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for r in result['results']:lines.append(f"| {r['arm']} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} | {100*r['null_roi']:+.2f}% | {r['log_loss']:.6f} | {r['brier']:.6f} |")
    lines+=['','## Paired differences','', 'Positive values favor retaining the market offset. Intervals are 95% week-cluster bootstrap.',
            '\n| Comparator | ROI gain [CI], pp | LL gain [CI] | Brier gain [CI] | Side flips |','|---|---:|---:|---:|---:|']
    for r in result['comparisons']:
        lo,hi=r['roi_gain_ci95'];ll,lh=r['ll_gain_ci95'];bl,bh=r['brier_gain_ci95']
        lines.append(f"| {r['comparator']} | {100*r['roi_gain']:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}] | {r['ll_gain']:+.6f} [{ll:+.6f}, {lh:+.6f}] | {r['brier_gain']:+.6f} [{bl:+.6f}, {bh:+.6f}] | {r['side_flips']} |")
    lines+=['','## Annual results','','| Arm | Season | Units | ROI | Log loss |','|---|---:|---:|---:|---:|']
    for r in result['by_season']:lines.append(f"| {r['arm']} | {r['season']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% | {r['log_loss']:.6f} |")
    lines+=['','## Archived SF at SEA counterfactual','','Seattle/home probabilities; earlier-week refits at archived inputs, not new snapshots.']
    for r in current:
        if r['game_id']=='2026_05_SF_SEA':lines+=['']+[f'- {a}: {100*r[a]:.2f}%' for a in ARMS]
    lines+=['','## Checks and interpretation','',f"Historical maximum production reproduction error: {result['historical_max_probability_error']:.3g}.",
            f"Archived current maximum reproduction error: {result['current_max_probability_error']:.3g}.",
            f"All {result['fits']} fits used strictly earlier weeks. Excluded bets: "+', '.join(result['excluded_bets'])+'.',
            'The ablation removes the direct market starting point, not all information correlated with prices. No new intercept or retuned penalties were added.',
            'The effect is conditional on the existing frozen recipe. Model design used these seasons; bootstrap intervals omit that selection uncertainty.',
            'Production and forward snapshots are unchanged. Run: `python research/market_offset_ablation.py`.','']
    (out/'REPORT.md').write_text('\n'.join(lines))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output-dir',type=Path,default=ROOT/'research/market_offset_results')
    args=ap.parse_args();run(args.output_dir)
