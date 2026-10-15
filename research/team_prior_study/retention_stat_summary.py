"""Compact views of retention_stat_pred_long.csv (copy of summarize_stat_prediction.py, adapted).
Writes team_prior/retention_stat_pred_{mode}_{subset}.csv, retention_stat_pred_pooled_{raw,recal}.csv and
retention_stat_pred_overview.csv (per comparison/mode/subset: metrics with CI<0, CI>0, median % change)."""
from pathlib import Path

import numpy as np
import pandas as pd

from paths import WORK as OUT  # noqa: E402
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 500)
L = pd.read_csv(OUT/'retention_stat_pred_long.csv')
L['metric'] = L.metric.str.replace('__rates_core__', ':')
ORDER = list(dict.fromkeys(L.metric))
SHORT = {'retention_cont_75_25': 'cont_75_25', 'retention_cont_50_25': 'cont_50_25',
         'retention_flat_75': 'flat_75', 'retention_flat_25': 'flat_25', 'league': 'league'}
L['comparison'] = L.variant.map(SHORT)+' vs '+L.reference.map(SHORT)
COMP_ORDER = ['cont_75_25 vs league', 'cont_50_25 vs league', 'flat_75 vs league', 'flat_25 vs league',
              'cont_75_25 vs flat_75', 'cont_50_25 vs flat_25']
SUBSETS = ['all', 'wk1', 'wk1-4', 'wk5-9', 'wk10-18', 'wk2-18', 'both_unchanged', 'coach_changed', 'qb_changed',
           'both_changed', 'cur_changed', 'cur_cont_older_changed', 'all3_continuous', 'all_excl_coach_mislabel']


def cell(r):
    if r.d_mse == 0 and r.d_mse_lo == 0 and r.d_mse_hi == 0: return 'identical'
    star = '*' if (r.d_mse_hi < 0) else ('+' if r.d_mse_lo > 0 else '')
    return f'{r.pct:+.2f} [{r.pct_lo:+.2f},{r.pct_hi:+.2f}]{star} {r.seasons_better}/{r.seasons}'


def pivot(mode, subset):
    x = L[(L['mode'] == mode) & (L.subset == subset)].copy()
    x['cell'] = x.apply(cell, axis=1)
    p = x.pivot(index='metric', columns='comparison', values='cell').reindex(ORDER)
    return p[[c for c in COMP_ORDER if c in p]].fillna('')


def overview():
    rows = []
    prof = [m for m in ORDER if m != 'margin']        # the 16 v1.18 profile regressors
    for (comp, mode, sub), g in L[L.metric.isin(prof)].groupby(['comparison', 'mode', 'subset']):
        rows.append({'comparison': comp, 'mode': mode, 'subset': sub, 'n_rows': int(g.n_rows.iloc[0]),
                     'metrics_ci_below_0': int((g.d_mse_hi < 0).sum()), 'metrics_ci_above_0': int((g.d_mse_lo > 0).sum()),
                     'metrics_point_better': int((g.d_mse < 0).sum()), 'of': len(g),
                     'median_pct': float(g.pct.median()), 'mean_pct': float(g.pct.mean()),
                     'rates_median_pct': float(g[~g.metric.isin(['max_lead', 'max_deficit'])].pct.median()),
                     'peaks_mean_pct': float(g[g.metric.isin(['max_lead', 'max_deficit'])].pct.mean())})
    o = pd.DataFrame(rows)
    o['comparison'] = pd.Categorical(o.comparison, COMP_ORDER, ordered=True)
    o['subset'] = pd.Categorical(o.subset, SUBSETS, ordered=True)
    return o.sort_values(['mode', 'comparison', 'subset'])


if __name__ == '__main__':
    for mode in ('raw', 'recal'):
        p = pivot(mode, 'all')
        p.to_csv(OUT/f'retention_stat_pred_pooled_{mode}.csv')
        print(f'\n=== {mode} / all: % change in MSE vs reference [95% team-season bootstrap], * = CI<0, + = CI>0; seasons better/10')
        print(p.to_string())
    for mode in ('raw', 'recal', 'recal_wk', 'stack'):
        for sub in SUBSETS:
            if sub == 'all' and mode in ('raw', 'recal'): continue
            pivot(mode, sub).to_csv(OUT/f'retention_stat_pred_{mode}_{sub}.csv')
    o = overview()
    o.to_csv(OUT/'retention_stat_pred_overview.csv', index=False, float_format='%.3f')
    print('\n=== overview over the 16 profile regressors (margin excluded)')
    print(o[o['mode'].isin(['raw', 'recal'])].to_string(index=False))
    for mode in ('raw', 'recal'):
        for sub in ('wk1-4', 'wk10-18', 'cur_changed', 'cur_cont_older_changed', 'all3_continuous'):
            print(f'\n=== {mode} / {sub}')
            print(pivot(mode, sub).to_string())
    x = L[(L['mode'] == 'raw') & (L.subset == 'all')]
    sig = x.assign(cell=lambda r: r.pct_signal_err.round(1).astype(str)+' / '+r.d_mse_over_between_var.round(3).astype(str)) \
        .pivot(index='metric', columns='comparison', values='cell').reindex(ORDER)
    print('\n=== raw pooled: dMSE as % of reference signal error / as share of between-team true variance')
    print(sig[[c for c in COMP_ORDER if c in sig]].to_string())
    C = pd.read_csv(OUT/'retention_stat_pred_coefs.csv')
    C['metric'] = C.metric.str.replace('__rates_core__', ':')
    st = C[C.kind == 'stack_b2'].copy()
    st['comparison'] = st.variant.map(SHORT)+' vs '+st.reference.map(SHORT)
    st['cell'] = st.apply(lambda r: f'{r.coef:+.2f} [{r.lo:+.2f},{r.hi:+.2f}]', axis=1)
    sp = st.pivot(index='metric', columns='comparison', values='cell').reindex(ORDER)
    sp = sp[[c for c in COMP_ORDER if c in sp]]
    sp.to_csv(OUT/'retention_stat_pred_stack_b2.csv')
    print('\n=== stacked b2 on (variant - reference), 2016-25 full sample, 95% team-season bootstrap (b2>0: the shift carries signal)')
    print(sp.to_string())
