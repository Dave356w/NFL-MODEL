"""Reconstructed 2026 replay; never edits locks or public grades. Run from repo root."""
import json,sys,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import nfl_model as m
import injury_efficiency as ie
import fixed_bands as fb
SOURCE=ROOT/'research/injury_efficiency_replay_inputs'
OUT=ROOT/'research/injury_efficiency_2026'
def run():
 OUT.mkdir(exist_ok=True)
 published=pd.read_csv(SOURCE/'published.csv.gz');published=published[published.result.notna()].copy()
 boxes=pd.read_csv(SOURCE/'boxes.csv.gz');boxes=boxes[boxes.season<2026]
 boxes=pd.concat([boxes,pd.read_csv(SOURCE/'boxes_2026.csv.gz')],ignore_index=True).drop(columns=['max_lead','max_deficit'],errors='ignore')
 schedules=pd.read_parquet(ROOT/'data/lock_inputs/schedules.parquet');schedules=schedules[schedules.game_type.eq('REG')]
 av=pd.read_parquet(ROOT/'data/lock_inputs/availability.parquet');snaps=pd.read_parquet(ROOT/'data/lock_inputs/snaps.parquet');inj=pd.read_parquet(ROOT/'data/lock_inputs/inj.parquet')
 m.FEATURE_FAMILIES=('rates_core_avail_cs',)
 print('Building prior-game profiles',flush=True)
 features={h:m.lagged_features(boxes,schedules[schedules.season>=2022],h,av,profile_families=('rates_core',)) for h in (8.,16.)}
 m.prepare_product_features(features,schedules)
 current=features[8.];current=current[current.game_id.isin(published.game_id)].copy()
 targets=pd.concat([current[['season','week',s]].rename(columns={s:'team'}) for s in ('home','away')]).drop_duplicates()
 print('Building prior medical references',flush=True)
 refs=ie.references(boxes,snaps,inj,av,targets);current=ie.attach(current,refs)
 states={(int(r.season),int(r.week),r.team):r.injury_report for r in av.itertuples()}
 for side in ('home','away'):
  current[side+'_availability_evidence']=[json.dumps(dict(report_complete=states.get((r.season,r.week,getattr(r,side)))=='final',blockers=[],observations=[])) for r in current.itertuples()]
 adjusted=ie.apply(current,replay=True)
 history=pd.read_csv(SOURCE/'training.csv.gz');history=history[history.season<2026]
 training=pd.concat([history,current],ignore_index=True)
 rules={(r['season'],r['week']):r for r in json.load(open(ROOT/'data/latest/fixed_band_rules.json'))}
 out=[]
 for week,g in current.groupby('week'):
  fit=m.fit_composite(training[m.before(training,2026,int(week))],m.PRODUCT_RECIPE,2026,int(week))
  assert (fit['training_max_season'],fit['training_max_week_in_latest_season'])<(2026,week)
  a=adjusted.loc[g.index];p0=m.apply_fit(g,fit);p1=m.apply_fit(a,fit)
  raw0=m.implied_spread(p0);raw1=m.implied_spread(p1)
  mapped0=fb.apply(raw0,rules[2026,int(week)]);mapped1=fb.apply(raw1,rules[2026,int(week)])
  for k,(ix,r) in enumerate(g.iterrows()):
   ok=bool(a.loc[ix,'injury_efficiency_ready'])
   out.append(dict(game_id=r.game_id,week=int(week),home=r.home,away=r.away,result=r.result,baseline_raw_margin=raw0[k],adjusted_raw_margin=raw1[k] if ok else None,baseline_median=mapped0[k],adjusted_median=mapped1[k] if ok else None,injury_ready=ok,injury_audit=a.loc[ix,'injury_efficiency_audit'],fit_training_max_season=fit['training_max_season'],fit_training_max_week=fit['training_max_week_in_latest_season']))
 d=pd.DataFrame(out).merge(published[['game_id','spread_line','model_spread','fixed_band_ats_result']],on='game_id',validate='one_to_one')
 saved=pd.read_csv(SOURCE/'saved_pairs.csv.gz');d['complete_saved_report_pair']=d.game_id.isin(saved.game_id)
 scores=[]
 for label,part in [('all_reconstructed',d),('complete_saved_pair_ids',d[d.complete_saved_report_pair])]:
  eligible=part[part.injury_ready].copy()
  for arm in ('baseline','adjusted'):
   grade,u=fb.grade(eligible,eligible[arm+'_median']);d.loc[eligible.index,arm+'_grade']=grade
   scores.append(dict(sample=label,arm=arm,n=len(eligible),wins=int(sum(grade=='W')),losses=int(sum(grade=='L')),pushes=int(sum(grade=='P')),units=float(u.sum()),roi=float(u.mean()) if len(u) else None,mae=float(abs(eligible.result-eligible[arm+'_median']).mean()),median_residual=float((eligible.result-eligible[arm+'_median']).median())))
 eligible=d[d.injury_ready]
 summary=dict(policy=ie.identity(),total_games=len(d),eligible_games=len(eligible),unavailable_games=int(sum(~d.injury_ready)),scores=scores,median_changes=int(sum(eligible.baseline_median!=eligible.adjusted_median)),pick_changes=int(sum(fb.pick(eligible.baseline_median,eligible.spread_line)!=fb.pick(eligible.adjusted_median,eligible.spread_line))),basis='Reconstructed archived final medical tables, not timestamp-verified historical executions. Saved report pair flag marks IDs only; this run uses archived final tables for every row. Core fits strictly prior weeks; injury weights frozen through 2025; weekly median maps held fixed. Original locks unchanged.')
 d['effective_median']=d.adjusted_median.where(d.injury_ready,d.baseline_median)
 grade,u=fb.grade(d,d.effective_median);d['effective_grade']=grade
 summary['all_games_with_unadjusted_fallback']=dict(n=len(d),wins=int(sum(grade=='W')),losses=int(sum(grade=='L')),pushes=int(sum(grade=='P')),units=float(u.sum()),mae=float(abs(d.result-d.effective_median).mean()),fallback_count=int(sum(~d.injury_ready)))
 d.to_csv(OUT/'games.csv',index=False);(OUT/'results.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':run()
