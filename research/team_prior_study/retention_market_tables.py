"""Format the retention market-test CSVs into compact tables (copy of team_prior_market_tables.py, adapted).
Writes team_prior/retention_market_test_table_*.csv and prints markdown."""
import ast
import json
from pathlib import Path

import pandas as pd

from paths import WORK as T  # noqa: E402
R = pd.read_csv(T / 'retention_market_test_summary.csv')
ARMS = ['retention_cont_75_25', 'retention_cont_50_25', 'retention_flat_75', 'retention_flat_25']
LBL = {'league': 'simplified league', 'retention_cont_75_25': 'cont_75_25 (arm)', 'retention_cont_50_25': 'cont_50_25 (arm)',
       'retention_flat_75': 'flat_75 (control)', 'retention_flat_25': 'flat_25 (control)'}


def iv(s, mult=1e3, k=2):
    if isinstance(s, (list, tuple)): a, b = s
    elif isinstance(s, str): a, b = ast.literal_eval(s)
    else: return ''
    return f'[{a*mult:+.{k}f}, {b*mult:+.{k}f}]'


def md(df):
    cols = list(df.columns)
    out = ['| ' + ' | '.join(cols) + ' |', '|' + '|'.join(['---'] * len(cols)) + '|']
    for _, r in df.iterrows():
        out.append('| ' + ' | '.join(str(r[c]) for c in cols) + ' |')
    return '\n'.join(out)


tabs = {}
rows = []
for _, r in R[R.model.isin(['league'] + ARMS)].iterrows():
    rows.append({'era': r.era, 'model': LBL[r.model], 'n bets': int(r.bets),
                 'W-L-P': r.wlp, 'units': f'{r.units:+.2f}', 'ROI +- SE': f'{100*r.roi:+.2f}% +- {100*r.roi_se:.2f}',
                 'market-null ROI': f'{100*r.null_roi:+.2f}%', 'favorite units (ROI)': f'{r.fav_units:+.2f} ({100*r.fav_roi:+.2f}%)',
                 'units vs league': '' if r.model == 'league' else f'{r.units_vs_league:+.2f}',
                 'ROI diff vs league, 95% [Bonf k=9]': '' if r.model == 'league' else
                 f"{100*r.roi_diff_vs_league:+.2f} pts {iv(r.roi_diff_vs_league_ci95, 100)} {iv(r.roi_diff_vs_league_ci_bonf, 100)}",
                 'flips (variant W-L-P; u var/lg; null var/lg)': '' if r.model == 'league' else
                 f'{int(r.side_flips)} ({r.flip_wlp_variant}; {r.flip_units_variant:+.2f}/{r.flip_units_league:+.2f}; '
                 f'{r.flip_null_units_variant:+.2f}/{r.flip_null_units_league:+.2f})'})
tabs['roi'] = pd.DataFrame(rows)

rows = []
for _, r in R[R.model.isin(['league'] + ARMS)].iterrows():
    rows.append({'era': r.era, 'model': LBL[r.model], 'n': int(r.n_ll),
                 'LL model': f'{r.ll_model:.5f}', 'LL market': f'{r.ll_market:.5f}',
                 'gain vs market x1e3 [95%]': f'{1e3*r.ll_gain_vs_market:+.2f} {iv(r.ll_gain_vs_market_ci95)}',
                 'gain vs league x1e3 [95%] [Bonf k=9]': '' if r.model == 'league' else
                 f'{1e3*r.ll_gain_vs_league:+.3f} {iv(r.ll_gain_vs_league_ci95)} {iv(r.ll_gain_vs_league_ci_bonf)}',
                 'after fav. penalty 0.2: gain vs league x1e3 [95%]': '' if pd.isna(r.get('fp_ll_gain_vs_league')) else
                 f'{1e3*r.fp_ll_gain_vs_league:+.3f} {iv(r.fp_ll_gain_vs_league_ci95)}'})
tabs['logloss'] = pd.DataFrame(rows)

V = pd.read_csv(T / 'retention_market_test_vs_control.csv')
tabs['vs_control'] = pd.DataFrame([{'era': r.era, 'arm vs control': f"{LBL[r.arm].split(' ')[0]} vs {LBL[r.control].split(' ')[0]}",
                                    'n': int(r.n_ll), 'LL gain x1e3 [95%]': f'{1e3*r.ll_gain_vs_control:+.3f} {iv(r.ll_gain_vs_control_ci95)}',
                                    'bets': int(r.bets), 'units arm / control': f'{r.units_arm:+.2f} / {r.units_control:+.2f}',
                                    'units diff (ROI diff 95%)': f'{r.units_vs_control:+.2f} ({100*r.roi_diff_vs_control:+.2f} pts {iv(r.roi_diff_vs_control_ci95, 100)})',
                                    'flips (arm W-L-P; u arm/ctl; null arm/ctl)': f'{int(r.side_flips)} ({r.flip_wlp_variant}; {r.flip_units_variant:+.2f}/{r.flip_units_ref:+.2f}; '
                                    f'{r.flip_null_units_variant:+.2f}/{r.flip_null_units_ref:+.2f})'} for _, r in V.iterrows()])

Cn = pd.read_csv(T / 'retention_market_test_by_continuity.csv')
tabs['by_continuity'] = pd.DataFrame([{'split (All 2017-25)': r.split, 'model': LBL.get(r.model, r.model.replace('league+delta_retention_', 'delta ')),
                                       'n games': int(r.n_ll), 'LL gain vs league x1e3 [95%]': f'{1e3*r.ll_gain_vs_league:+.3f} {iv(r.ll_gain_vs_league_ci95)}',
                                       'bets': int(r.bets), 'units (ROI +- SE)': f'{r.units:+.2f} ({100*r.roi:+.2f}% +- {100*r.roi_se:.2f})',
                                       'market-null ROI': f'{100*r.null_roi:+.2f}%', 'league units': f'{r.league_units:+.2f}',
                                       'favorite units (ROI)': f'{r.fav_units:+.2f} ({100*r.fav_roi:+.2f}%)',
                                       'units vs league [ROI diff 95%]': f'{r.units_vs_league:+.2f} {iv(r.roi_diff_vs_league_ci95, 100)}',
                                       'flips (W-L-P)': f'{int(r.side_flips)} ({r.flip_wlp_variant})'} for _, r in Cn.iterrows()])

I = pd.read_csv(T / 'retention_market_test_delta_logit_size.csv')
rows = []
for _, r in R[R.model.str.startswith('league+delta_')].iterrows():
    v = r.model.replace('league+delta_', '')
    sz = I[(I.era == r.era) & (I.variant == v)].iloc[0]
    rows.append({'era': r.era, 'delta of': LBL[v], 'ref': sz.delta_ref, 'n delta feats': 16,
                 'joint LL gain vs simplified league x1e3 [95%] [Bonf]':
                 f'{1e3*r.ll_gain_vs_league:+.3f} {iv(r.ll_gain_vs_league_ci95)} {iv(r.ll_gain_vs_league_ci_bonf)}',
                 'SD delta logit': f'{sz.sd_delta_logit:.3f}', 'mean |delta| pp': f'{sz.mean_abs_delta_logit_pp:.2f}',
                 'units (vs league)': f'{r.units:+.2f} ({r.units_vs_league:+.2f})', 'flips': int(r.side_flips),
                 'ROI diff 95%': f"{iv(r.roi_diff_vs_league_ci95, 100)}"})
tabs['delta'] = pd.DataFrame(rows)

C = pd.read_csv(T / 'retention_market_test_delta_coef_stability.csv')
rows = []
for (v, f), g in C[C.era != 'All 2017-25'].groupby(['variant', 'feature']):
    sp = g.set_index('era').share_positive; mb = g.set_index('era').mean_beta_std
    allpos, allneg = (sp >= .9).all(), (sp <= .1).all()
    rows.append({'delta of': LBL[v], 'feature': f, 'mean beta/SD 17-20': f"{mb['2017-20']:+.3f}", '21-22': f"{mb['2021-22']:+.3f}",
                 '23-25': f"{mb['23-25' if '23-25' in mb else '2023-25']:+.3f}", 'share>0 17-20/21-22/23-25':
                 f"{sp['2017-20']:.2f}/{sp['2021-22']:.2f}/{sp['2023-25']:.2f}",
                 'sign stable all eras': 'positive' if allpos else 'negative' if allneg else 'no'})
cs = pd.DataFrame(rows)
tabs['coef_all'] = cs
tabs['coef_stable'] = cs[cs['sign stable all eras'] != 'no']
tabs['coef_summary'] = cs.groupby('delta of')['sign stable all eras'].apply(lambda s: f"{(s != 'no').sum()} of {len(s)}").reset_index()

W = pd.read_csv(T / 'retention_market_test_by_week_group.csv')
W['cell'] = [f'{1e3*a:+.2f} {iv(c)}' for a, c in zip(W.ll_gain_vs_league, W.ci95)]
tabs['weeks'] = W.pivot(index='model', columns='weeks', values='cell').reset_index()

pr = R[(R.model == 'league') & R.prod_v116_matched_n.notna()]
tabs['prod_ref'] = pd.DataFrame([{'era': r.era, 'matched n': int(r.prod_v116_matched_n),
                                  'full v1.16 LL gain vs market x1e3': f'{1e3*r.prod_v116_ll_gain_vs_market:+.2f}',
                                  'simplified league LL gain x1e3': f'{1e3*r.simplified_league_ll_gain_vs_market_matched:+.2f}',
                                  'full v1.16 units (ROI +- SE)': f'{r.prod_v116_units:+.2f} ({100*r.prod_v116_roi:+.2f}% +- {100*r.prod_v116_roi_se:.2f})',
                                  'simplified league units': f'{r.simplified_league_units_matched:+.2f}',
                                  'favorite units': f'{r.fav_units_matched:+.2f}', 'bets': int(r.prod_v116_bets)}
                                 for _, r in pr.iterrows()])
res = json.load(open(T / 'retention_market_test_results.json'))
for k, v in tabs.items():
    v.to_csv(T / f'retention_market_test_table_{k}.csv', index=False)
    print(f'\n### {k}\n'); print(md(v))
print('\ncoach sensitivity', res['coach_sensitivity'])
print('validation', res['validation_vs_earlier_p_league'])
