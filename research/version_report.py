"""Report every committed competing-model test without mixing evidence bases.

This module grades existing forecasts only. It never fits or selects a model,
changes a production recipe, or writes a native snapshot.
"""
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import nfl_model as m
import grade_ledger

STUDIES=('qualification','context','market_offset','shrinkage','profile_robustness','margin_total','market_residual')
LEGACY_STUDIES=('qualification','context')


def historical_tests():
    rows=[]
    for study in STUDIES:
        data=json.loads((ROOT/f'research/{study}_results/results.json').read_text())
        section=data.get('win',data.get('stack',data))
        results=section['results']
        market=next(r for r in results if r['arm'] in ('market','market_only','q'))
        for result in results:
            label=result['arm']
            comparator='pre-v1.16 selected production' if study in LEGACY_STUDIES else 'v1.16 full-history production'
            rows.append({'study':study,'arm':label,'basis':'exposed 2023-2025 chronological development',
                         'study_production_label':comparator,'bets':result['bets'],
                         'binary_games':data.get('proper_games',section.get('proper_games',815)),
                         **{k:result[k] for k in ('wins','losses','pushes','units','roi','roi_se','null_roi','log_loss','brier')},
                         'favorite_units':market['units'],'favorite_roi':market['roi'],
                         'market_log_loss':market['log_loss'],'market_brier':market['brier'],
                         'source':f'research/{study}_results/results.json'})
    return pd.DataFrame(rows)


def archived_tests(ledger):
    """Grade frozen old-input counterfactuals once per game at the original quotes."""
    records=[json.loads(line) for line in (ROOT/'research/shrinkage_results/archived_current_inputs.jsonl').read_text().splitlines() if line.strip()]
    base=pd.DataFrame([{k:r[k] for k in ('game_id','season','week','home','away','home_moneyline','away_moneyline')} for r in records])
    if base.game_id.duplicated().any():raise ValueError('Archived comparison repeats a game')
    outcomes=ledger[['game_id','result','home won']].drop_duplicates()
    if outcomes.game_id.duplicated().any():raise ValueError('Conflicting snapshot outcomes')
    base=base.merge(outcomes,on='game_id',how='left',validate='one_to_one')
    rows=[]
    for study in STUDIES:
        path=ROOT/f'research/{study}_results/current_counterfactuals.csv'
        if not path.exists():continue
        forecasts=pd.read_csv(path)
        specification=json.loads((ROOT/f'research/{study}_results/results.json').read_text())
        section=specification.get('win',specification.get('stack',specification))
        arms=[r['arm'] for r in section['results']]
        for arm in arms:
            if arm not in forecasts:continue
            frame=base.merge(forecasts[['game_id',arm]],on='game_id',validate='one_to_one')
            frame['model_wp']=frame[arm];frame['market_wp']=m.market_ml_wp(frame)
            bets=m.flat_bets(frame);s=m.roi_summary(bets)
            favorite=m.flat_bets(frame.assign(market_ml_wp=frame.market_wp),'market_ml_wp').loc[bets.units.notna()]
            scored=frame[frame['home won'].isin([0.,1.])&np.isfinite(frame.model_wp)&np.isfinite(frame.market_wp)]
            y=scored['home won'];p=scored.model_wp;q=scored.market_wp
            rows.append({'study':study,'arm':arm,'basis':'frozen archived-input counterfactual; not native forward',
                         'games':len(frame),'pending':int(frame.result.isna().sum()),'bets':s['bets'],
                         **{k:s[k] for k in ('wins','losses','pushes','units','roi','roi_se','null_roi')},
                         'favorite_units':float(favorite.units.sum()),'favorite_roi':float(favorite.units.mean()),
                         'binary_games':len(scored),'log_loss':float(m.ll(y,p).mean()) if len(scored) else np.nan,'market_log_loss':float(m.ll(y,q).mean()) if len(scored) else np.nan,
                         'brier':float(((p-y)**2).mean()),'market_brier':float(((q-y)**2).mean()),
                         'source':str(path.relative_to(ROOT))})
    return pd.DataFrame(rows)


def native_tests(ledger):
    rows=[]
    for (revision,experiment),part in ledger.groupby(['revision','experiment'],sort=True):
        if part.game_id.duplicated().any():raise ValueError('Native experiment repeats a game')
        s=grade_ledger.summary(part);r=s['roi']
        rows.append({'revision':revision,'experiment':experiment,'basis':'native first pregame snapshots',
                     'games':s['snapshots'],'pending':s['pending'],'binary_games':s['scored'],
                     **{k:r[k] for k in ('wins','losses','pushes','units','roi','roi_se')},
                     'null_roi':r['null_roi'],'favorite_units':r['fav_units'],'favorite_roi':r['fav_roi'],
                     'log_loss':s.get('model_log_loss',np.nan),'market_log_loss':s.get('market_log_loss',np.nan),
                     'brier':s.get('model_brier',np.nan),'market_brier':s.get('market_brier',np.nan)})
    return pd.DataFrame(rows)


def markdown_table(frame,identity):
    lines=['| '+identity+' | N | W-L-P | Units | ROI ± SE | Favorite units | Null ROI | LL ↓ | Market LL ↓ |',
           '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for r in frame.to_dict('records'):
        label=r.get('revision',f"{r.get('study')}: {r.get('arm')}")
        n=r.get('bets',r.get('games'))
        def fmt(x,spec):return format(x,spec) if pd.notna(x) else '—'
        lines.append(f"| {label} | {n} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | {fmt(100*r['roi'],'+.2f')}% ± {fmt(100*r['roi_se'],'.2f')} | {r['favorite_units']:+.2f} | {fmt(100*r['null_roi'],'+.2f')}% | {fmt(r['log_loss'],'.6f')} | {fmt(r['market_log_loss'],'.6f')} |")
    return '\n'.join(lines)


def run(data,out):
    data,out=Path(data),Path(out);out.mkdir(parents=True,exist_ok=True)
    ledger=pd.read_csv(data/'forward_ledger.csv')
    historical=historical_tests();archived=archived_tests(ledger);native=native_tests(ledger)
    for name,frame in [('historical',historical),('archived',archived),('native',native)]:
        frame.to_csv(out/f'version_{name}.csv',index=False)
    lines=['# Production restoration and all competing-model results','',
           f'Current production: **{m.REVISION}**, exact original Product + 1 SD recipe.',
           f'Configuration: `{m.config_signature()[0]}`. Owner-directed restoration on 2026-10-12.',
           'Original forecasts and frozen recipes remain unchanged. This report grades existing predictions; it does not retune or select a candidate.',
           '', '## Native forward results', '',
           'Each experiment contains one original pregame forecast per game. Different revisions can overlap and have different lock quotes; do not pool them. Ties push; binary scores exclude ties. Pending games remain ungraded.', '',
           markdown_table(native,'Original revision'), '', '## Frozen archived-input counterfactuals', '',
           'These forecasts use the archived v1.16 input cohort and original moneylines. Total/cover/over schedule quote capture times are unknown. They are reconstructed research forecasts, not executable native locks. No missing games are backfilled. Outcomes are taken from the current graded ledger.', '',
           markdown_table(archived,'Study and arm'), '', '## All committed historical tests', '',
           'Exposed 2023–2025 chronological development. Compare arms within each study; cohorts differ (811 versus 812 bets), warm-up training histories differ, and the label production in the older qualification/context studies describes the pre-v1.16 model. Repeated control rows are not independent evidence.', '',
           markdown_table(historical,'Study and arm'), '', '## Interpretation', '',
           'v1.17 has the highest tested historical return among the recent fixed challengers, but its paired advantage over v1.16 remains unresolved (98.75% ROI-difference interval −0.27 to +4.89 percentage points). v1.16 has better historical binary scores than v1.17. The extra passing-by-total interaction beats the additive market-target challenger on returns through one changed historical pick. Shrinkage and bounded variants do not establish replacement superiority.',
           'Historical intervals condition on exposed model development and omit design-selection uncertainty. ROI ± SE is one standard error, not a confidence interval. Native results are small-sample descriptive evidence. Source reports retain paired week-cluster intervals and annual comparisons.',
           'The restored production is not qualified as reliably profitable. Retrospective snapshot grades are reported separately from native outcomes, and repeated snapshots are never counted as independent games.','']
    (out/'version_report.md').write_text('\n'.join(lines))
    return historical,archived,native


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,default=ROOT/'data');parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();run(args.data,args.out)
