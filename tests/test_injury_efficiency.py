import json
import numpy as np
import pandas as pd
import injury_efficiency as ie


def board():
 ref=dict(team='X',season=2026,week=11,baseline=[30,2,30,2,50],prior_burden=[0]*6,shares={'p':{'OL':.2}},statuses=[],source_max_season=2026,source_max_week=10)
 row=dict(season=2026,week=11,result=np.nan,kickoff_utc='2026-11-15T18:00:00Z',ready=True)
 row.update({n:0. for n in ie.TERMS})
 for side in ('home','away'):
  row[side+'_injury_efficiency_reference']=json.dumps(ref)
  row[side+'_availability_evidence']=json.dumps(dict(report_complete=True,blockers=[],observations=[]))
 return pd.DataFrame([row])


def test_adjustment_reaches_inputs_and_refresh_is_idempotent():
 b=board();ev=dict(report_complete=True,blockers=[],observations=[dict(field='report_status',gsis_id='p',value='Out')])
 b.loc[0,'home_availability_evidence']=json.dumps(ev)
 first=ie.apply(b);second=ie.apply(first)
 assert first.loc[0,'injury_efficiency_ready']
 assert np.any(first[ie.TERMS].to_numpy()!=0)
 np.testing.assert_allclose(first[ie.TERMS],second[ie.TERMS])
 # A corrected report restores the pre-adjustment inputs before recomputing.
 second.loc[0,'home_availability_evidence']=b.loc[0,'away_availability_evidence']
 np.testing.assert_allclose(ie.apply(second)[ie.TERMS],0,atol=1e-12)


def test_unresolved_or_future_reference_fails_closed():
 for kind in ('missing','future'):
  b=board()
  if kind=='missing':b.loc[0,'home_availability_evidence']=json.dumps(dict(report_complete=False))
  else:
   r=json.loads(b.loc[0,'home_injury_efficiency_reference']);r['source_max_week']=11;b.loc[0,'home_injury_efficiency_reference']=json.dumps(r)
  out=ie.apply(b)
  assert not out.loc[0,'injury_efficiency_ready'] and not out.loc[0,'ready']
  assert 'blocker' in json.loads(out.loc[0,'injury_efficiency_audit'])


def test_historical_rows_and_pre_adoption_deadlines_untouched():
 b=board();b.loc[0,'result']=7
 pd.testing.assert_frame_equal(ie.apply(b),b)
 b.loc[0,'result']=np.nan;b.loc[0,'kickoff_utc']='2026-11-01T18:00:00Z'
 pd.testing.assert_frame_equal(ie.apply(b),b)
 assert ie.apply(b,replay=True).loc[0,'injury_efficiency_ready']
 assert ie.identity()['training_max_season']==2025


def test_new_complete_report_unblocks_a_previously_unresolved_board():
 b=board();b.loc[0,'home_availability_evidence']=json.dumps(dict(report_complete=False))
 out=ie.apply(b);assert not out.loc[0,'ready']
 out.loc[0,'home_availability_evidence']=board().loc[0,'home_availability_evidence']
 out=ie.apply(out);assert out.loc[0,'ready'] and out.loc[0,'injury_efficiency_ready']


def test_prior_revision_signature_is_exact_and_policy_is_frozen():
 import nfl_model as m
 from pathlib import Path
 original=json.loads((Path(__file__).resolve().parents[1]/'data/frozen_recipe_2026_boxscore-composite-v1.22.json').read_text())
 with m.revision_identity('boxscore-composite-v1.22',m.PRODUCT_RECIPE):
  assert m.config_signature()[0]==original['config_signature']
 assert m.config_signature()[1]['injury_efficiency']==ie.identity()


def test_adjustment_flows_through_win_fit_and_median():
 import nfl_model as m
 import fixed_bands as fb
 b=board();b['q']=.5
 # Leave the passing contexts and QB contribution identical between arms.
 for n in m.PRODUCT_CONTEXT_NAMES:b[n]=0.
 b['qb_context']=.7
 b.loc[0,'home_availability_evidence']=json.dumps(dict(report_complete=True,blockers=[],observations=[dict(field='report_status',gsis_id='p',value='Out')]))
 fit=dict(names=ie.TERMS,scale=[1.]*5,beta=[1.]*5,market_offset=True,recipe={})
 a=ie.apply(b)
 assert a.loc[0,'qb_context']==b.loc[0,'qb_context']
 before=m.implied_spread(m.apply_fit(b,fit));after=m.implied_spread(m.apply_fit(a,fit))
 assert abs(float(before[0])-float(after[0]))>1e-6
 threshold=(abs(float(before[0]))+abs(float(after[0])))/2
 rule=dict(cuts=[threshold,threshold+10,threshold+20],magnitudes=[1,3,7,10])
 assert fb.apply(before,rule)[0]!=fb.apply(after,rule)[0]
