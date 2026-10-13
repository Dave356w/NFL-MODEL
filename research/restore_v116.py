"""Verify exact v1.16 restoration and replay every frozen original snapshot."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import nfl_model as m
from research import version_report


def run():
    # v1.18 runs production with a favorite penalty; this verification replays v1.16 itself.
    with m.revision_identity('boxscore-composite-v1.16',m.LEGACY_PRODUCT_RECIPE):_run()


def _run():
    out=ROOT/'research/restore_v116_results';out.mkdir(exist_ok=True)
    inputs=ROOT/'research/restore_v116_inputs'
    original=json.loads((ROOT/'data/frozen_recipe_2026_boxscore-composite-v1.16.json').read_text())
    if m.REVISION!='boxscore-composite-v1.16' or m.PRODUCT_RECIPE!=original['recipe'] or m.config_signature()[0]!=original['config_signature']:
        raise ValueError('Restoration does not match the original frozen v1.16 identity')
    f=pd.read_csv(ROOT/'research/shrinkage_results/frozen_training_features.csv.gz')
    reference=pd.read_csv(ROOT/'research/shrinkage_results/heldout_predictions.csv').set_index('game_id')
    historical=f[f.game_id.isin(reference.index)].copy()
    for (year,week),part in historical.groupby(['season','week'],sort=True):
        fit=m.fit_composite(f[m.before(f,year,week)],m.PRODUCT_RECIPE,int(year),int(week))
        historical.loc[part.index,'model_wp']=m.apply_fit(part,fit)
    historical['frozen_v116']=reference.loc[historical.game_id,'production'].to_numpy()
    error=float(abs(historical.model_wp-historical.frozen_v116).max())
    if error>1e-7:raise ValueError(f'Historical v1.16 mismatch: {error}')
    historical.to_csv(out/'historical_reproduction.csv',index=False)
    ledger=inputs/'forward_predictions.jsonl';before=ledger.read_bytes()
    schedules=pd.read_csv(inputs/'results.csv')
    state=m.STATE_DIR
    try:
        m.STATE_DIR=str(inputs)
        m.regrade_product_ledger({8.:f},schedules,out)
    finally:m.STATE_DIR=state
    if ledger.read_bytes()!=before:raise ValueError('Original snapshots were changed')
    replay=pd.read_csv(out/'regraded_ledger.csv')
    v116=replay[replay.original_revision=='boxscore-composite-v1.16']
    native_error=float(abs(v116.model_wp-v116.original_model_wp).max())
    if native_error>1e-7:raise ValueError(f'Native v1.16 replay mismatch: {native_error}')
    version_report.run(inputs,out)
    checks={'production_revision':m.REVISION,'configuration':m.config_signature()[0],
            'original_configuration_restored':True,'historical_games':len(historical),
            'historical_max_error':error,'native_v116_max_error':native_error,
            'original_snapshots':len(replay),'unique_games':int(replay.game_id.nunique()),
            'original_ledger_sha256':hashlib.sha256(before).hexdigest(),'ledger_unchanged':True,
            'basis':'frozen retrospective verification; not new native forward forecasts'}
    (out/'verification.json').write_text(json.dumps(checks,indent=2)+'\n')
    print(json.dumps(checks,indent=2))
    print(pd.read_csv(out/'regraded_summary.csv').to_string(index=False))


if __name__=='__main__':run()
