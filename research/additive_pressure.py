"""Separate additive offensive/defensive pressure coefficients; no interaction."""
import json
import pandas as pd

import pressure_margin as p
import offensive_pressure_only as offense

OUTPUT=p.ROOT/'research/additive_pressure_results'
EXTRA=['pressure_allowed_diff','pressure_generated_diff']


def profiles(f,g,lag):
    return p.profiles(f,g,lag).drop(columns=['pressure_matchup'])


def compare_offensive_only():
    new=pd.read_csv(OUTPUT/'predictions.csv.gz')
    old=pd.read_csv(offense.OUTPUT/'predictions.csv.gz')
    rows=[]
    for lag in [2,1]:
        for cohort,seasons in [('2024',[2024]),('2025',[2025]),('2024-25',[2024,2025]),('2026',[2026])]:
            for offset in ['model','market']:
                a=new[new.lag_weeks.eq(lag)&new.season.isin(seasons)&new.arm.eq(offset+'_additive_pressure')].sort_values('game_id').reset_index(drop=True)
                b=old[old.lag_weeks.eq(lag)&old.season.isin(seasons)&old.arm.eq(offset+'_offensive_pressure')].sort_values('game_id').reset_index(drop=True)
                if not a.game_id.equals(b.game_id):raise ValueError('Offensive-only comparison cohort mismatch')
                rows.append(dict(lag=lag,cohort=cohort,offset=offset,**p.bootstrap(b,a)))
    (OUTPUT/'vs_offensive_only.json').write_text(json.dumps(rows,indent=2)+'\n')
    report=OUTPUT/'REPORT.md'
    lines=['','## Direct incremental value of defensive pressure','','Positive gain favors adding defensive pressure to offensive pressure.',
           'Same earlier-season fits and same paired games; no interaction.','',
           '| Cohort | Offset | MAE gain [95%] | Cover LL gain [95%] |','|---|---|---|---|']
    for r in rows:
        if r['lag']!=2 or r['cohort'] not in ['2024-25','2026']:continue
        a,b=r['mae_gain_ci95'];c,d=r['log_loss_gain_ci95']
        lines.append(f"| {r['cohort']} | {r['offset']} | {r['mae_gain']:+.4f} [{a:+.4f}, {b:+.4f}] | {r['log_loss_gain']:+.6f} [{c:+.6f}, {d:+.6f}] |")
    report.write_text(report.read_text()+'\n'.join(lines)+'\n')


if __name__=='__main__':
    g=pd.read_csv(p.INPUT/'team_games.csv.gz')
    p.run(frame_builder=lambda f,lag:profiles(f,g,lag),output=OUTPUT,extra_columns=EXTRA,feature_label='additive_pressure')
    offense.team_diagnostics(output=OUTPUT,arm='model_additive_pressure',selection_note='This additive follow-up was requested after the full-pressure and offensive-only arms. It is selected historical development, not fresh confirmation.')
    compare_offensive_only()
