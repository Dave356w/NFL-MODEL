"""Compact views of stat_pred_long.csv / persistence.csv (written by eval_stat_prediction.py)."""
from pathlib import Path

import numpy as np
import pandas as pd

from paths import WORK as OUT  # noqa: E402
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 500)
L = pd.read_csv(OUT/'stat_pred_long.csv')
L['metric'] = L.metric.str.replace('__rates_core__', ':')
ORDER = list(dict.fromkeys(L.metric))


def cell(r):
    star = '*' if (r.d_mse_hi < 0) else ('+' if r.d_mse_lo > 0 else '')
    return f'{r.pct:+.2f} [{r.pct_lo:+.2f},{r.pct_hi:+.2f}]{star} {r.seasons_better}/{r.seasons}'


def pivot(mode, subset, refmap=True, value=cell):
    x = L[(L['mode'] == mode) & (L.subset == subset)].copy()
    # primary reference: league for rates/margin; league_level for team-type on peaks
    peaks = x.metric.isin(['max_lead', 'max_deficit'])
    keep = ~peaks | (x.variant.isin(['league_level', 'none']) & (x.reference == 'league')) | \
           (x.variant.isin(['team_window', 'team_prior', 'continuity', 'coach']) & (x.reference == 'league_level'))
    x = x[keep] if refmap else x
    x['cell'] = x.apply(value, axis=1)
    p = x.pivot(index='metric', columns='variant', values='cell').reindex(ORDER)
    cols = [c for c in ['team_window', 'team_prior', 'continuity', 'coach', 'qb_offense', 'league_level', 'none'] if c in p]
    return p[cols].fillna('')


if __name__ == '__main__':
    for mode in ('raw', 'recal'):
        for sub in ('all',):
            p = pivot(mode, sub)
            p.to_csv(OUT/f'stat_pred_pooled_{mode}.csv')
            print(f'\n=== {mode} / {sub}: % change in MSE vs reference [95% team-season bootstrap], * = CI<0, + = CI>0; seasons better/10')
            print(p.to_string())
    # signal-scale table (raw, pooled)
    x = L[(L['mode'] == 'raw') & (L.subset == 'all')]
    x = x[~x.metric.isin(['max_lead', 'max_deficit']) | ((x.reference == 'league_level') & x.variant.isin(['team_window', 'team_prior', 'continuity', 'coach'])) |
          ((x.reference == 'league') & x.variant.isin(['league_level', 'none']))]
    sig = x.assign(cell=lambda r: r.pct_signal_err.round(1).astype(str)+' / '+r.d_mse_over_between_var.round(3).astype(str)) \
        .pivot(index='metric', columns='variant', values='cell').reindex(ORDER)
    print('\n=== raw pooled: dMSE as % of league signal error / as share of between-team true variance')
    print(sig.to_string())
    base = x[x.variant == 'team_window'][['metric', 'mse_ref', 'noise_var', 'signal_err_ref', 'signal_rmse_ref_sd']]
    print('\n=== league reference decomposition (raw pooled)')
    print(base.round(4).to_string(index=False))
    for mode in ('raw', 'recal'):
        for sub in ('wk1', 'wk1-4', 'wk5-9', 'wk10-18', 'wk2-18', 'both_unchanged', 'coach_changed', 'qb_changed', 'both_changed', 'all_excl_coach_mislabel'):
            p = pivot(mode, sub)
            p.to_csv(OUT/f'stat_pred_{mode}_{sub}.csv')
            if mode == 'raw' or sub in ('wk1-4', 'wk10-18', 'both_unchanged', 'qb_changed', 'coach_changed'):
                print(f'\n=== {mode} / {sub}')
                print(p.to_string())
    P = pd.read_csv(OUT/'persistence.csv')
    P['metric'] = P.metric.str.replace('__rates_core__', ':')
    R = pd.read_csv(OUT/'persistence_reliability.csv'); R['metric'] = R.metric.str.replace('__rates_core__', ':')
    q = P[~P.split.str.startswith('diff')].copy()
    q['cell'] = q.apply(lambda r: f'{r.r:.2f} [{r.r_lo:.2f},{r.r_hi:.2f}] n={r.n_pairs}', axis=1)
    pt = q.pivot(index='metric', columns='split', values='cell').reindex(ORDER)
    pt = pt[['all', 'coach_same', 'coach_changed', 'qb_same', 'qb_changed', 'both_same', 'both_changed']]
    dz = P[P.split.str.startswith('diff')].pivot(index='metric', columns='split', values='z_diff').reindex(ORDER).round(2)
    dis = q[q.split == 'all'].set_index('metric').r_disattenuated.reindex(ORDER).round(2)
    pt = pt.join(R.set_index('metric').season_reliability_sb.round(2).rename('season_reliability')).join(dis.rename('r_all_disattenuated')).join(dz)
    pt.to_csv(OUT/'persistence_table.csv')
    print('\n=== year-to-year persistence (season-demeaned)')
    print(pt.to_string())
