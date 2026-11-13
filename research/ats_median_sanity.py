"""Independent frozen ATS median/sign/grading audit. Run from repository root.

Writes research/ats_median_audit only; no production/data mutation.
"""
import sys,json,collections
from pathlib import Path
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));import fixed_bands as f
hist=pd.read_csv(ROOT/'data/latest/retro_ledger.csv');rules=json.load(open(ROOT/'data/latest/fixed_band_rules.json'))
(ROOT/'research/ats_median_audit').mkdir(parents=True,exist_ok=True)
checks=[]
for saved in rules:
 s,w=saved['season'],saved['week'];ref=f.fit_weekly(hist,s,w);assert ref==saved;assert f.trained_before(saved,s,w)
 before=(hist.season<s)|((hist.season==s)&(hist.week<w));h=hist[before&hist.model_spread.ne(0)&hist[['model_spread','result']].notna().all(axis=1)].copy()
 age=((s-h.season)*19+(w-h.week))/19;weights=2.**(-age.to_numpy());signed=np.sign(h.model_spread.to_numpy())*h.result.to_numpy();bands=np.digitize(abs(h.model_spread),[3,7,10])
 for k,median in enumerate(saved['magnitudes']):
  y=signed[bands==k];wt=weights[bands==k];loss=(wt*abs(y-median)).sum();candidates=np.unique(y);best=min((wt*abs(y-v)).sum() for v in candidates)
  assert loss<=best+1e-8
 poison=hist.copy();poison.loc[~before,'result']=10000.;assert f.fit_weekly(poison,s,w)==saved
checks.append(dict(rules=len(rules),reproduced=True,weighted_L1_optimal=True,no_target_future_labels=True))
base=pd.read_csv(ROOT/'research/pressure_inputs/base_forecasts.csv');pub=pd.read_csv(ROOT/'research/pressure_inputs/ats_2026_results.csv');pub=pub[pub.ats_status.eq('graded')]
pred=pub.model_spread.to_numpy(float);line=pub.spread_line.to_numpy(float);actual=pub.result.to_numpy(float)
grade,units=f.grade(pub,pred);assert np.array_equal(grade,pub.fixed_band_ats_result);side=f.pick(pred,line);savedside=np.where(pub.fixed_band_ats_side.eq('home'),1,-1);assert np.array_equal(side,savedside)
assert np.allclose(np.where(side==1,-line,line),pub.fixed_band_ats_handicap)
price=pub.ats_price.to_numpy(float);payout=np.where(price>0,price/100,100/abs(price));mixed=np.where(grade=='W',payout,np.where(grade=='L',-1,0));assert np.allclose(mixed,pub.fixed_band_ats_units)
def record(g):
 c=collections.Counter(g);return {k:int(c[k]) for k in ['W','L','P','S']}
def rec_prediction(p,a=pub):
 r,u=f.grade(a,p);return dict(**record(r),units=float(np.nansum(u)))
print('CHECKS',checks)
print('PUBLIC',len(pub),record(grade),float(units.sum()),float(mixed.sum()))
byrules={(x['season'],x['week']):x for x in rules}
line_mapped=np.array([f.apply([r.spread_line],byrules[(int(r.season),int(r.week))])[0] for r in pub.itertuples()]);lmgrade,lmu=f.grade(pub,line_mapped)
print('LINEONLY',rec_prediction(line_mapped),'same picks',sum(f.pick(line_mapped,line)==side))
raw=pub[['game_id']].merge(hist[['game_id','model_spread']],on='game_id',how='left');ok=raw.model_spread.notna();print('RAW',sum(ok),rec_prediction(raw.loc[ok,'model_spread'].to_numpy(),pub.loc[ok].reset_index(drop=True)))
equal=abs(pred-line)<=f.EPS
print('ZEROEDGE',sum(equal),record(grade[equal]),float(units[equal].sum()),'NONZERO',record(grade[~equal]),float(units[~equal].sum()))
print('PREDICTIONS',pd.Series(pred).value_counts().sort_index().to_dict())
print('STEPS')
for s in [2023,2024,2025,2026]:
 a=base[base.season.eq(s)].copy();tie=abs(a.prediction-a.spread_line)<=f.EPS;r,u=f.grade(a,a.prediction)
 print(s,len(a),'ties',sum(tie),'record',record(r),'tieRecord',record(r[tie]))
# Compare every saved research pick/return to canonical ATS grading, including tolerance.
folders=['pressure_margin_results','scoring_finishing_results','punt_results','ppp_results','offensive_pressure_results','additive_pressure_results'];research_checks=[]
for folder in folders:
 d=pd.read_csv(ROOT/'research'/folder/'predictions.csv.gz');canonical=f.pick(d['mean'],d.spread_line);exact=np.where(d['mean']>d.spread_line,1,np.where(d['mean']<d.spread_line,-1,np.sign(d.spread_line)))
 assert np.array_equal(canonical,exact)
 for (lag,season,arm),g in d.groupby(['lag_weeks','season','arm']):
  r,u=f.grade(g,g['mean']);e=(g.result-g.spread_line)*f.pick(g['mean'],g.spread_line);sg=np.where(e>0,'W',np.where(e<0,'L',np.where(f.pick(g['mean'],g.spread_line)==0,'S','P')));assert np.array_equal(r,sg)
 research_checks.append(dict(folder=folder,rows=len(d),canonical_pick_and_grade_match=True))
print('RESEARCH_CHECKS',research_checks)
# Show intercept/tie contribution without fitting anything new.
d=pd.read_csv(ROOT/'research/additive_pressure_results/predictions.csv.gz');q=d[d.lag_weeks.eq(2)&d.season.eq(2026)]
for arm in ['model_original','model_control','model_additive_pressure']:
 a=q[q.arm.eq(arm)].sort_values('game_id');o=q[q.arm.eq('model_original')].sort_values('game_id');zero=abs(o.prediction-o.spread_line)<=f.EPS;g,u=f.grade(a,a['mean']);os=f.pick(o['mean'],o.spread_line);ss=f.pick(a['mean'],a.spread_line)
 print('INTERCEPT',arm,rec_prediction(a['mean'].to_numpy(),a),'flips',sum(ss!=os),'zeroedgeflips',sum((ss!=os)&zero.to_numpy()))
# Detailed frozen 2026 per-game receipts.
a=pub[['game_id','season','week','home','away','model_spread','spread_line','result','fixed_band_ats_result']].copy();a['zero_edge']=equal;a['line_only_mapped']=line_mapped;a['line_only_grade']=lmgrade;a['original_minus_lineonly_units']=units-lmu
a.to_csv(ROOT/'research/ats_median_audit/games_2026.csv',index=False)
summary=dict(map_checks=checks,public=dict(n=len(pub),record=record(grade),minus110_units=float(units.sum()),mixed_price_units=float(mixed.sum())),zero_edge=dict(n=int(equal.sum()),record=record(grade[equal]),minus110_units=float(units[equal].sum())),line_only_map=dict(**rec_prediction(line_mapped),same_picks=int(sum(f.pick(line_mapped,line)==side))),research_checks=research_checks)


# Methodological receipt: intercepts that minimize squared vs absolute error.
intercepts=[]
for season in [2024,2025,2026]:
 train=base[base.season<season];residual=train.result-train.prediction
 intercepts.append(dict(evaluation_season=season,training_n=len(train),mean_residual=float(residual.mean()),median_residual=float(residual.median())))
summary['earlier_season_intercepts']=intercepts
summary['source_timing']='Reconstructed/exposed history; no verified first-publication times or native-forward claim'
import hashlib
summary['source_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['data/latest/retro_ledger.csv','data/latest/fixed_band_rules.json','data/latest/fixed_band_ledger.csv','research/pressure_inputs/base_forecasts.csv','research/pressure_inputs/ats_2026_results.csv']}
# Verify historical stored grades too; keep zero/unavailable games out of this assertion.
history_mapped=pd.read_csv(ROOT/'data/latest/fixed_band_ledger.csv');history_mapped=history_mapped[history_mapped.fixed_band_spread.notna()]
r,_=f.grade(history_mapped,history_mapped.fixed_band_spread);assert np.array_equal(r,history_mapped.fixed_band_ats_result)
summary['historical_mapped_grades_checked']=len(history_mapped)
assert all(np.all(np.diff(r['magnitudes'])>=0) for r in rules)
summary['all_exported_maps_monotonic']=True
(ROOT/'research/ats_median_audit/results.json').write_text(json.dumps(summary,indent=2)+'\n')
