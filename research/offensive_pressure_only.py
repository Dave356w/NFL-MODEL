"""One-feature offensive pressure ablation; see OFFENSIVE_PRESSURE_ONLY.md."""
import numpy as np
import pandas as pd

import pressure_margin as p

OUTPUT=p.ROOT/'research/offensive_pressure_results'
EXTRA=['pressure_allowed_diff']


def profiles(f,g,lag):
    rows=[]
    for (season,week),batch in f.groupby(['season','week'],sort=True):
        hist=g[p.eligible(g,season,week,lag)]
        if hist.empty:raise ValueError('No earlier offensive pressure history')
        prior_pressure=float(hist.times_pressured.mean());prior_opportunities=float(hist.opportunities.mean())
        rates={}
        for t in set(batch.home)|set(batch.away):
            h=hist[hist.team.eq(t)].sort_values(['season','week','game_id'])
            if h.empty:raise ValueError(f'No offensive pressure history for {t}')
            if (h.opportunities<=0).any():raise ValueError('Nonpositive pressure opportunities')
            age=np.arange(len(h)-1,-1,-1);w=np.exp2(-age/8)*.5**(season-h.season.to_numpy())
            rates[t]=(w@h.times_pressured+4*prior_pressure)/(w@h.opportunities+4*prior_opportunities)
        last=hist.sort_values(['season','week']).iloc[-1]
        for r in batch.itertuples():
            rows.append(dict(game_id=r.game_id,lag_weeks=lag,source_max_season=int(last.season),source_max_week=int(last.week),
                             home_pressure_allowed=rates[r.home],away_pressure_allowed=rates[r.away],
                             pressure_allowed_diff=(rates[r.home]-rates[r.away])/.05))
    return f.merge(pd.DataFrame(rows),on='game_id',validate='one_to_one')


def team_diagnostics(output=OUTPUT,arm='model_offensive_pressure',selection_note=None):
    f=pd.read_csv(output/'predictions.csv.gz');f=f[f.lag_weeks.eq(2)&f.season.eq(2026)]
    a=f[f.arm.eq(arm)].copy()
    a=a.merge(f[f.arm.eq('model_control')][['game_id','mean']].rename(columns={'mean':'control'}),on='game_id',validate='one_to_one')
    all_rows=[];summary=[]
    for t in sorted(set(a.home)|set(a.away)):
        q=a[a.home.eq(t)|a.away.eq(t)].copy();sgn=np.where(q.home.eq(t),1,-1)
        q['team']=t;q['team_actual_margin']=sgn*q.result;q['team_original_margin']=sgn*q.prediction
        q['team_control_margin']=sgn*q.control;q['team_adjusted_margin']=sgn*q['mean']
        q['feature_only_change']=sgn*(q['mean']-q.control);q['full_overlay_change']=sgn*(q['mean']-q.prediction)
        original=p.picked_side(q.prediction,q.spread_line);control=p.picked_side(q.control,q.spread_line);adjusted=p.picked_side(q['mean'],q.spread_line)
        q['original_backed_team']=original==sgn;q['adjusted_backed_team']=adjusted==sgn
        q['flipped_vs_original']=original!=adjusted;q['flipped_vs_control']=control!=adjusted
        summary.append(dict(team=t,n=len(q),average_feature_only_change=float(q.feature_only_change.mean()),
                            average_full_overlay_change=float(q.full_overlay_change.mean()),
                            original_mae=float(abs(q.result-q.prediction).mean()),control_mae=float(abs(q.result-q.control).mean()),
                            adjusted_mae=float(abs(q.result-q['mean']).mean()),pick_flips_vs_original=int(q.flipped_vs_original.sum()),
                            pick_flips_vs_control=int(q.flipped_vs_control.sum())))
        all_rows.append(q)
    pd.DataFrame(summary).to_csv(output/'team_summary_2026.csv',index=False)
    pd.concat(all_rows,ignore_index=True).to_csv(output/'team_games_2026.csv',index=False)
    report=output/'REPORT.md'
    lines=['','## Requested LAC/PHI diagnostic','','Positive change favors the named team. Feature-only excludes shared intercept recalibration.',
           'All teams are saved in team_summary_2026.csv; this slice did not select the fit.','',
           '| Team | n | Feature-only change | Full change | Original MAE | Control MAE | Adjusted MAE | Pick flips vs original/control |',
           '|---|---:|---:|---:|---:|---:|---:|---|']
    for r in summary:
        if r['team'] not in ['LAC','PHI']:continue
        lines.append(f"| {r['team']} | {r['n']} | {r['average_feature_only_change']:+.3f} | {r['average_full_overlay_change']:+.3f} | {r['original_mae']:.3f} | {r['control_mae']:.3f} | {r['adjusted_mae']:.3f} | {r['pick_flips_vs_original']}/{r['pick_flips_vs_control']} |")
    if selection_note is None:selection_note='This ablation was requested after seeing the full-pressure team slices. It is selected historical development, not fresh confirmation.'
    lines+=['',selection_note,'']
    report.write_text(report.read_text()+'\n'.join(lines))


if __name__=='__main__':
    g=pd.read_csv(p.INPUT/'team_games.csv.gz')
    p.run(frame_builder=lambda f,lag:profiles(f,g,lag),output=OUTPUT,extra_columns=EXTRA,feature_label='offensive_pressure')
    team_diagnostics()
