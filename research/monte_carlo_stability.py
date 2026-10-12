"""Compare the fixed Monte Carlo experiment with its doubled-draw repeat."""
import json
import numpy as np
import pandas as pd
from monte_carlo import OUT, ROOT, protected


def run():
    out=protected(OUT); repeat=ROOT/'research/monte_carlo_stability'
    a=pd.read_csv(out/'heldout_predictions.csv').set_index('game_id')
    b=pd.read_csv(repeat/'heldout_predictions.csv').set_index('game_id').loc[a.index]
    exact_error=float(abs(a[['market','production','empirical','price_calibrated','model_adjusted']]-b[['market','production','empirical','price_calibrated','model_adjusted']]).max().max())
    if exact_error>1e-12:raise ValueError('Seed-independent arms changed')
    first=json.loads((out/'results.json').read_text());second=json.loads((repeat/'results.json').read_text())
    rows=[]
    for arm in ['feature_bootstrap','coefficient_bootstrap','combined']:
        x=next(x for x in first['arms'] if x['arm']==arm);y=next(x for x in second['arms'] if x['arm']==arm)
        diff=abs(a[arm]-b[arm])
        rows.append({'arm':arm,'mean_absolute_probability_change':float(diff.mean()),
                     'max_absolute_probability_change':float(diff.max()),
                     'changed_sides':int(((a[arm]>.5)!=(b[arm]>.5)).sum()),
                     'first_log_loss':x['log_loss'],'repeat_log_loss':y['log_loss'],
                     'first_roi':x['roi'],'repeat_roi':y['roi']})
    r={'first_seed':first['seed'],'repeat_seed':second['seed'],'exact_arm_max_error':exact_error,
       'first_common_bets':first['common_bets'],'repeat_common_bets':second['common_bets'],'rows':rows}
    (out/'stability.json').write_text(json.dumps(r,indent=2)+'\n')
    lines=['# Simulation stability check','',
           'Repeat uses an independent seed and doubles profile draws (256 → 512) and coefficient refits (64 → 128). Outcome draws remain 8,192; exact weighted outcome probabilities are scored.',
           '',f'Seed-independent market, production and empirical outcome arms match to {exact_error:.3g}. Common historical return cohorts: '+str(first['common_bets'])+' / '+str(second['common_bets'])+'.',
           '', '| Arm | Mean probability change, pp | Maximum change, pp | Changed sides | First LL | Repeat LL |',
           '|---|---:|---:|---:|---:|---:|']
    for x in rows:lines.append(f"| {x['arm']} | {100*x['mean_absolute_probability_change']:.3f} | {100*x['max_absolute_probability_change']:.3f} | {x['changed_sides']} | {x['first_log_loss']:.6f} | {x['repeat_log_loss']:.6f} |")
    lines+=['','The repeat does not establish a predictive gain over production. Bootstrap averages near 50% can change direction with numerical sampling. Use uncertainty ranges for reporting; increase coefficient refits before treating tiny probability differences as meaningful. Two runs check sensitivity, not full convergence.','']
    (out/'STABILITY.md').write_text('\n'.join(lines))
    report=out/'REPORT.md';text=report.read_text()
    marker='\nSee [STABILITY.md](STABILITY.md) for the independent-seed, doubled-draw sensitivity check.\n'
    if marker not in text:report.write_text(text+marker)
    return r


if __name__=='__main__':
    print(json.dumps(run(),indent=2))
