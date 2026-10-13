import copy
import datetime as dt
import json
import sys
from pathlib import Path
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import forward_v116_assessment as a


def fixture():
    rules,_=a.load_protocol();start=a.utc(rules['start_utc'])
    def record(game,minutes=1):
        return {'game_id':game,'season':2026,'week':6,'home':'A','away':'B',
            'generated_utc':(start+dt.timedelta(minutes=minutes)).isoformat(),
            'kickoff_utc':(start+dt.timedelta(days=2,minutes=minutes)).isoformat(),
            'revision':rules['revision'],'experiment':rules['config_signature']+':recipe:2026',
            'recipe':copy.deepcopy(rules['recipe']),'home_moneyline':-150.,'away_moneyline':130.,
            'model_wp':.65,'market_wp':.999,'injury_report':{'home':'final','away':'final'},
            'coefficient_fit':{'training_max_season':2026,'training_max_week_in_latest_season':5}}
    return rules,start,record


def grades(rows):return pd.DataFrame(rows,columns=['game_id','status','result'])


def test_first_lock_before_freeze_cannot_be_rescued():
    rules,start,record=fixture();records=[record('old',-1),record('old',1),record('new',2)]
    f,ex,stop=a.cohort(records,grades([['new','graded',3]]),rules,(start+dt.timedelta(days=3)).isoformat())
    assert f.game_id.tolist()==['new'] and stop is None
    assert set(x['reason'] for x in ex)=={'locked_before_freeze','later_duplicate_lock'}
    assert f.q.iloc[0]==pytest.approx(a.prices(-150,130)) and f.q.iloc[0]!=.999


def test_change_stops_enrollment_and_conflicting_grades_fail():
    rules,start,record=fixture();change=record('changed',2);change['revision']='another_revision'
    f,ex,stop=a.cohort([record('early'),change,record('late',3)],grades([]),rules,(start+dt.timedelta(days=3)).isoformat())
    assert f.game_id.tolist()==['early'] and stop is not None
    assert 'enrollment_stopped_after_recipe_change' in [x['reason'] for x in ex]
    with pytest.raises(ValueError,match='Conflicting'):
        a.cohort([record('x')],grades([['x','graded',3],['x','graded',-3]]),rules,(start+dt.timedelta(days=3)).isoformat())


def test_pending_prefix_blocks_checkpoint_and_interim_has_no_verdict():
    rules,start,record=fixture();rules['monitoring_counts']=[2];rules['formal_count']=3;rules['bootstrap_reps']=30
    f,_,_=a.cohort([record(str(i),i+1) for i in range(3)],grades([['0','graded',3],['2','graded',-3]]),rules,(start+dt.timedelta(days=3)).isoformat())
    prefix,ready=a.checkpoints(f,rules,(start+dt.timedelta(days=3)).isoformat())
    assert prefix==1 and ready==[]
    f.loc[1,'status']='tie';f.loc[1,'result']=0.
    prefix,ready=a.checkpoints(f,rules,(start+dt.timedelta(days=3)).isoformat())
    assert prefix==3 and [r['formal'] for r in ready]==[False,True]
    assessment=a.assess(f,rules,False)
    assert assessment['financial_assessment']=='descriptive_only'
    assert assessment['probability']['games']==2 and assessment['ties']==1
    assert assessment['financial']['pushes']==1


def test_invalid_prices_fit_and_injury_gate_are_excluded():
    rules,start,record=fixture();badprice=record('price');badprice['home_moneyline']=0.
    future=record('future');future['coefficient_fit']['training_max_week_in_latest_season']=6
    gate=record('gate');gate['injury_report']={'home':'practice','away':'practice'}
    f,ex,_=a.cohort([badprice,future,gate],grades([]),rules,(start+dt.timedelta(days=3)).isoformat())
    assert len(f)==0
    assert {x['reason'] for x in ex}=={'invalid_price_or_probability','missing_or_nonprior_fit_cutoff','injury_gate_not_met'}


def test_protocol_tampering_and_checkpoint_overwrite_rejected(tmp_path):
    envelope=json.loads(a.PROTOCOL.read_text());envelope['rules']['formal_count']=10
    p=tmp_path/'bad.json';p.write_text(json.dumps(envelope))
    with pytest.raises(ValueError,match='hash mismatch'):a.load_protocol(p)
    p=tmp_path/'checkpoint.json';a.save_checkpoint(p,{'n':100});a.save_checkpoint(p,{'n':100})
    with pytest.raises(ValueError,match='Checkpoint changed'):a.save_checkpoint(p,{'n':101})


def test_empty_cohort_is_pending_with_no_decision():
    rules,_,_=fixture();r=a.assess(pd.DataFrame(),rules)
    assert r['unique_games']==0 and r['financial_assessment']=='descriptive_only'
