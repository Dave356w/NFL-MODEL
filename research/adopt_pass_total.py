"""Verify production against the frozen challenger and replay all snapshot quotes."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import nfl_model as m


def run():
    out=ROOT/'research/pass_total_adoption_results';out.mkdir(exist_ok=True)
    pack=pd.read_csv(ROOT/'research/market_residual_results/frozen_market_outcomes.csv.gz')
    original=pd.read_csv(ROOT/'research/shrinkage_results/frozen_training_features.csv.gz').set_index('game_id')
    pred,audit,support,choices,fits=m.prepare_market_target_forecasts(pack)
    frozen=pd.read_csv(ROOT/'research/market_residual_results/weekly_market_forecasts.csv.gz').set_index('game_id')
    common=pred[pred.game_id.isin(frozen.index)]
    cols=[f'{t}__selected__{c}' for t in m.MARKET_TARGETS for c in ('mean','sd')]
    target_error=float(abs(common[cols].to_numpy()-frozen.loc[common.game_id,cols].to_numpy()).max())
    if target_error>1e-10:raise ValueError(f'Target mismatch {target_error}')
    for c in m.feature_names(m.PRODUCT_RECIPE['family'])+list(m.PRODUCT_CONTEXT_NAMES)+['ready']:
        pred[c]=original.loc[pred.game_id,c].to_numpy()
    pred['total_homefield']=pred.site*pred.total_context;pred['pass_total_interaction']=pred.pass_product*pred.total_context
    reference=pd.read_csv(ROOT/'research/market_residual_results/heldout_win_predictions.csv').set_index('game_id')
    evaluated=pred[pred.game_id.isin(reference.index)].copy()
    for (year,week),g in evaluated.groupby(['season','week'],sort=True):
        fit=m.fit_composite(pred[m.before(pred,year,week)],m.PRODUCT_RECIPE,int(year),int(week))
        evaluated.loc[g.index,'model_wp']=m.apply_fit(g,fit)
    evaluated['frozen_challenger']=reference.loc[evaluated.game_id,'pass_total'].to_numpy()
    win_error=float(abs(evaluated.model_wp-evaluated.frozen_challenger).max())
    if win_error>1e-7:raise ValueError(f'Production mismatch {win_error}')
    evaluated.to_csv(out/'historical_reproduction.csv',index=False)
    audit.to_csv(out/'market_target_audit.csv',index=False)
    (out/'market_target_selections.json').write_text(json.dumps(choices,indent=2)+'\n')
    # Include all priced future rows in reconstruction; earlier unpriced rows
    # do not enter stage two and have no forecast, exactly as the tested recipe.
    source=pd.read_csv(ROOT/'research/margin_total_results/frozen_feature_prices.csv.gz')
    f=source.drop(columns=[c for c in source if c in pred and c not in ('game_id',)]).merge(pred,on='game_id',how='right',validate='one_to_one')
    features={8.:f,'market_target_selections':choices,'market_target_fits':fits}
    m.STATE_DIR=str(ROOT/'research/pass_total_adoption_inputs');ledger=Path(m.STATE_DIR)/'forward_predictions.jsonl';ledger_before=ledger.read_bytes()
    schedule=pack[['game_id','margin']].rename(columns={'margin':'result'})
    m.regrade_product_ledger(features,schedule,out)
    if ledger.read_bytes()!=ledger_before:raise ValueError('Ledger changed')
    current=[];current_fits={}
    for week in sorted(f.loc[f.season==2026,'week'].unique()):
        te=f[(f.season==2026)&(f.week==week)].copy()
        fit=m.fit_composite(f[m.before(f,2026,week)],m.PRODUCT_RECIPE,2026,int(week))
        te['model_wp']=m.apply_fit(te,fit);te['revision']=m.REVISION
        current.append(te);current_fits[str(int(week))]=fit
    pd.concat(current,ignore_index=True).to_csv(out/'current_projections.csv',index=False)
    (out/'current_fits.json').write_text(json.dumps(current_fits,indent=2)+'\n')
    rows=m.flat_bets(evaluated);summary=m.roi_summary(rows)
    reference_rows=reference.reset_index()
    arms=['production_matched','forecast_additive','margin_total','pass_total','pass_market_total','selected','production_full','direct_margin_selected','direct_margin_relationships','market']
    matched=np.logical_and.reduce([m.flat_bets(reference_rows,a).units.notna().to_numpy() for a in arms])
    matched_summary=m.roi_summary(rows.loc[matched])
    verification={'revision':m.REVISION,'target_max_error':target_error,'win_max_error':win_error,'historical_games':len(evaluated),'ledger_sha256':hashlib.sha256(ledger_before).hexdigest(),'ledger_unchanged':True,'common_812_roi':matched_summary,'all_eligible_roi':summary,'log_loss':float(m.ll(evaluated.loc[evaluated['home won'].isin([0.,1.]),'home won'],evaluated.loc[evaluated['home won'].isin([0.,1.]),'model_wp']).mean())}
    (out/'verification.json').write_text(json.dumps(verification,indent=2)+'\n')
    print(json.dumps(verification,indent=2))

if __name__=='__main__':run()
