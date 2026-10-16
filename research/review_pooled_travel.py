"""Descriptive paired controls and support audit; no model fitting or selection."""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import pooled_travel_empirical as p


def review(out=p.OUT):
    f=pd.read_csv(out/'predictions.csv.gz',low_memory=False)
    pairs=[];support=[]
    for basis,mask in [('2023-25',f.season.between(2023,2025)),
                       ('2017-22',f.season.between(2017,2022)),('2026 diagnostic',f.season.eq(2026))]:
        sub=f[mask]
        a=sub[sub.arm.eq('selected')].set_index('game_id').sort_index()
        for comparator in ['plain','SC1_travel_k100','SC1_selected']:
            z=sub[sub.arm.eq(comparator)].set_index('game_id').sort_index()
            if not a.index.equals(z.index):raise AssertionError('Unpaired rows')
            cols=['primary_crps','win_ll','cover_ll','over_ll']
            delta=z[cols].to_numpy()-a[cols].to_numpy()
            boot=p.b.week_bootstrap(delta,a.season,a.week)
            for i,col in enumerate(cols):
                pairs.append(dict(basis=basis,arm='selected',comparator=comparator,metric=col,
                    gain=float(np.nanmean(delta[:,i])),ci95=p.b.interval(boot[:,i]),descriptive=True))
        plain=sub[sub.arm.eq('plain')].set_index('game_id')
        for (arm,key),g in sub[sub.arm.isin(['selected','SC1_travel_k100'])].groupby(['arm','feature_travel'],dropna=False):
            z=plain.loc[g.game_id]
            support.append(dict(basis=basis,arm=arm,travel=None if pd.isna(key) else key,n=len(g),
                mean_support=float(g.pooled_support.mean()),median_support=float(g.pooled_support.median()),
                mean_alpha=float(g.travel_alpha.mean()),fallback_fraction=float(g.travel_fallback.mean()),
                primary_crps_gain=float(np.mean(z.primary_crps.to_numpy()-g.primary_crps.to_numpy())),
                home_win_probability_shift=float(np.mean(g.p_home_non_tie.to_numpy()-z.p_home_non_tie.to_numpy())),
                margin_mean_shift=float(np.mean(g.margin_mean.to_numpy()-z.margin_mean.to_numpy()))))
    p.m.dump(out/'paired_controls.json',pairs)
    p.m.dump(out/'support_comparison.json',support)
    p.m.dump(out/'review_provenance.json',dict(source_sha256=p.m.j.sha256(Path(__file__)),
        prediction_sha256=p.m.j.sha256(out/'predictions.csv.gz'),descriptive_only=True))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=p.OUT)
    review(parser.parse_args().output_dir)
