"""Descriptive context support by category; no model fits or outcome selection."""
import argparse
from pathlib import Path

import pandas as pd

import schedule_context_empirical as s


def run(out=s.OUT):
    out=Path(out)
    f=pd.read_csv(out/'predictions.csv.gz')
    features=pd.read_csv(out/'feature_table.csv.gz')
    f=f[f.season.between(2023,2025)].merge(features[['game_id']+['feature_'+g for g in s.GROUPS]],
        on='game_id',validate='many_to_one')
    rows=[]
    for group in s.GROUPS:
        z=f[f.arm.eq(group+'_k100')]
        for key,g in z.groupby('feature_'+group,dropna=False):
            rows.append(dict(group=group,category=None if pd.isna(key) else key,games=len(g),
                mean_support=float(g.context_support.mean()),median_support=float(g.context_support.median()),
                context_weight=float(g.context_alpha.mean()),fallback_fraction=float(g.context_fallback.mean())))
    pd.DataFrame(rows).to_csv(out/'category_support.csv',index=False)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=s.OUT)
    run(parser.parse_args().output_dir)
