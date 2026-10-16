import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import forward_capture as c


def fixture(tmp_path):
    root=tmp_path/'root';root.mkdir()
    (root/'code.py').write_text('fixed source\n');(root/'params.json').write_text('{}\n')
    store=tmp_path/'capture'
    spec=dict(model_name='R001',config={'tie_prior':[.5,.5]},source_files=['code.py'],parameter_files=['params.json'],training_input_sha256='a'*64)
    version=c.register_model(store,spec,root)
    request=dict(game_id='future_fixture',kickoff_utc='2027-09-12T17:00:00Z',
        max_training_season_week=[2027,1],forecast_season_week=[2027,2],
        week_data_cutoff_utc='2027-09-09T00:00:00Z',training_available_through_utc='2027-09-08T23:00:00Z',
        forecast_market_inputs=dict(spread_line=3.,total_line=45.),
        quote=dict(game_id='future_fixture',kickoff_utc='2027-09-12T17:00:00Z',
            source='TEST ONLY',book='TEST ONLY',provider_event_utc='2027-09-12T15:59:00Z',
            received_utc='2027-09-12T15:59:01Z',spread_line=3.,total_line=45.,home_moneyline=-150.,away_moneyline=130.))
    now=datetime(2027,9,12,16,tzinfo=timezone.utc)
    p=np.ones((81,81))/81**2
    return root,store,spec,version,request,now,p


def test_first_snapshot_hashes_and_no_overwrite(tmp_path):
    root,store,spec,v,request,now,p=fixture(tmp_path)
    path=c.capture(store,v,request,p,root,_now=now)
    original=path.read_bytes()
    assert c.verify_store(store)['snapshots']==1
    assert json.loads(path.read_text())['request']['quote']==request['quote']
    with pytest.raises(FileExistsError):c.capture(store,v,request,p,root,_now=now)
    with pytest.raises(FileExistsError):c.register_model(store,spec,root)
    assert path.read_bytes()==original


@pytest.mark.parametrize('kind',['same_week','stale','future_quote','naive','price_mismatch','postkick','bad_pmf'])
def test_invalid_requests_fail_without_snapshot(tmp_path,kind):
    root,store,spec,v,request,now,p=fixture(tmp_path)
    if kind=='same_week':request['max_training_season_week']=[2027,2]
    elif kind=='stale':request['quote']['provider_event_utc']='2027-09-12T15:50:00Z'
    elif kind=='future_quote':request['quote']['provider_event_utc']='2027-09-12T16:01:00Z'
    elif kind=='naive':request['kickoff_utc']='2027-09-12T17:00:00'
    elif kind=='price_mismatch':request['forecast_market_inputs']['spread_line']=-3
    elif kind=='postkick':now=datetime(2027,9,12,17,1,tzinfo=timezone.utc)
    elif kind=='bad_pmf':p[0,0]=np.nan
    with pytest.raises(ValueError):c.capture(store,v,request,p,root,_now=now)
    assert not list((store/'snapshots').glob('*/*.json'))


def test_source_changes_require_new_model_version(tmp_path):
    root,store,spec,v,request,now,p=fixture(tmp_path)
    (root/'params.json').write_text('{"new":1}')
    with pytest.raises(ValueError,match='changed'):c.capture(store,v,request,p,root,_now=now)
    new=c.register_model(store,spec,root)
    assert new!=v


def test_tampering_is_detected(tmp_path):
    root,store,spec,v,request,now,p=fixture(tmp_path)
    path=c.capture(store,v,request,p,root,_now=now)
    row=json.loads(path.read_text());row['joint'][0][0]=1
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError,match='hash'):c.verify_store(store)


def test_production_output_is_protected(tmp_path):
    root,store,spec,v,request,now,p=fixture(tmp_path)
    for output in [root,root/'data',root/'data/capture',root/'public/snapshots']:
        with pytest.raises(ValueError,match='Protected'):c.register_model(output,spec,root)
