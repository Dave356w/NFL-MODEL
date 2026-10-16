"""Descriptive calibration/distribution audit of AC1; no new fit or selection."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import ats_calibration as a


def review(out=a.OUT):
    p=pd.read_csv(out/'predictions.csv.gz')
    d=pd.read_csv(out/'decisions.csv.gz')
    main=p[p.season.between(2023,2025)]
    raw=d[d.season.between(2023,2025)&d.policy.eq('raw_EV')&d.side.ne('pass')]
    rows=[]
    for name,g in main.groupby('configuration'):
        g=g.set_index('game_id').loc[raw.game_id]
        chosen=np.where(raw.side.eq('home'),g.p.to_numpy(),1-g.p.to_numpy())
        y=np.where(raw.side.eq('home'),g.label.to_numpy(),1-g.label.to_numpy())
        valid=np.isfinite(y)
        gap=y-chosen
        boot=a.b.week_bootstrap(gap,g.season,g.week)
        rows.append(dict(configuration=name,original_raw_bets=len(raw),decisive=int(valid.sum()),
            predicted_cover=float(chosen[valid].mean()),actual_cover=float(y[valid].mean()),
            calibration_residual=float(np.nanmean(gap)),calibration_residual_ci95=a.b.interval(boot[:,0])))
    a.m.dump(out/'original_bet_cohort_calibration.json',rows)
    shape=pd.read_csv(out/'distribution_metrics.csv')
    paired=[]
    for name in ['selected','fair']:
        g=shape[shape.configuration.eq(name)].set_index('game_id').sort_index()
        for baseline in ['raw','fair']:
            control=shape[shape.configuration.eq(baseline)].set_index('game_id').loc[g.index]
            meta=main[main.configuration.eq('raw')].set_index('game_id').loc[g.index]
            cols=['primary_crps','margin_crps','total_crps','win_ll','cover_ll','over_ll']
            delta=control[cols].to_numpy()-g[cols].to_numpy()
            boot=a.b.week_bootstrap(delta,meta.season,meta.week)
            for i,col in enumerate(cols):
                paired.append(dict(configuration=name,comparator=baseline,metric=col,
                    gain=float(np.nanmean(delta[:,i])),ci95=a.b.interval(boot[:,i]),descriptive=True))
    a.m.dump(out/'distribution_comparisons.json',paired)
    a.m.dump(out/'review_provenance.json',dict(source_sha256=a.m.j.sha256(Path(__file__)),
        inputs={n:a.m.j.sha256(out/n) for n in ['predictions.csv.gz','decisions.csv.gz','distribution_metrics.csv']},
        descriptive_only=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=a.OUT)
    review(parser.parse_args().output_dir)
