"""Post-experiment diagnostics; no candidate fits or specification changes."""
from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd

import market_context_empirical as m
import joint_market_residuals_report as b


def run(out=m.OUT):
    a=pd.read_csv(m.OUT/'predictions.csv.gz');a=a[a.season.between(2023,2025)]
    refined=m.OUT.parent/'R003_market_context_refinement'
    z=pd.read_csv(refined/'predictions.csv.gz');z=z[z.season.between(2023,2025)]
    results=[]
    for label,base,cand,column in [
        ('MC2 direct vs MC1 selected direct',a[a.arm.eq('selected_direct_kernel')],z[z.arm.eq('selected_all')],'primary_crps'),
        ('MC1 local residual vs global residual',a[a.arm.eq('global_residual')],a[a.arm.eq('selected_all')],'primary_crps'),
        ('MC1 local residual win vs no-vig market',a[a.arm.eq('selected_all')],a[a.arm.eq('selected_all')],'win_ll'),
        ('MC2 direct win vs no-vig market',z[z.arm.eq('selected_all')],z[z.arm.eq('selected_all')],'win_ll')]:
        base=base.set_index('game_id').sort_index();cand=cand.set_index('game_id').loc[base.index]
        delta=(base.market_win_ll if 'no-vig' in label else base[column])-cand[column]
        valid=delta.notna();x=delta[valid]
        draws=b.week_bootstrap(x,base.loc[valid,'season'],base.loc[valid,'week'])[:,0]
        results.append(dict(comparison=label,n=len(x),gain=float(x.mean()),ci95=b.interval(draws)))
    frame=m.load_inputs();bad=[]
    for _,row in a[a.arm.eq('selected_all')].iterrows():
        dist=m.forecast(frame,row,m.CONFIGS[row.configuration])
        h,away,w=dist['home'],dist['away'],dist['weights']
        invalid=((h==1)&((away<6)|(away==7)))|((away==1)&((h<6)|(h==7)))
        bad.append(w[invalid].sum())
    results.append(dict(comparison='MC1 translated unsupported football pair mass; diagnostic, not masked',
                        mean=float(np.mean(bad)),max=float(np.max(bad))))
    for label,f in [('MC1 local residual',a[a.arm.eq('selected_all')]),('MC2 direct',z[z.arm.eq('selected_all')])]:
        results.append(dict(comparison=label+' pooled event calibration',tie_predicted=float(f.p_tie.mean()),
            tie_observed=float((f.home_score==f.away_score).mean()),margin3_predicted=float(f.margin3_probability.mean()),
            margin3_observed=float((abs(f.home_score-f.away_score)==3).mean()),
            margin7_predicted=float(f.margin7_probability.mean()),
            margin7_observed=float((abs(f.home_score-f.away_score)==7).mean())))
    wrong_endpoints={}
    for label,f in [('MC1',a),('MC2',z)]:
        wrong_endpoints[label]={c:int(np.isinf(f[c]).sum()) for c in ['win_ll','cover_ll','over_ll']}
    result=dict(method='Exploratory diagnostics after both batches; not additional confirmatory comparisons. Fixed paths, 10000 season-stratified week draws, seed 20261016.',
                comparisons=results,infinite_binary_losses=wrong_endpoints,
                source_hashes={str(p.relative_to(m.j.ROOT)):m.j.sha256(p) for p in
                    [m.OUT/'predictions.csv.gz',refined/'predictions.csv.gz',Path(__file__).resolve()]})
    m.dump(Path(out)/'exploratory_diagnostics.json',result)
    print(json.dumps(m.safe_json(result),indent=2,allow_nan=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=m.OUT)
    run(parser.parse_args().output_dir)
