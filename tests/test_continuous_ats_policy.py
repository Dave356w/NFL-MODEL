"""Continuous v1.19 decisions coexist with untouched legacy median evidence."""
import copy
import csv
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.special import ndtr

import ats_locks as a
import nfl_model as m
import season_ats as s


UTC = dt.timezone.utc
KO = dt.datetime(2026,10,25,17,tzinfo=UTC)
CUTOFF = KO-dt.timedelta(hours=1)
LEGACY_REVISION = 'boxscore-composite-v1.18'


def write_board(data, when, *, revision=a.CONTINUOUS_REVISION, architecture='market_spread_total', **changes):
    latest = data/'latest';latest.mkdir(exist_ok=True)
    manifest = dict(revision=revision,season=2026,week=7,generated_utc=when.isoformat(),
                    config_signature='fixture',recipe=dict(family='fixture',architecture=architecture))
    (latest/'manifest.json').write_text(json.dumps(manifest))
    row = dict(game_id='2026_07_TEN_IND',season=2026,week=7,home='IND',away='TEN',
               gameday='2026-10-25',gametime='13:00',result='',ready=True,
               model_wp=float(ndtr(8/12.37)),spread_line=7.5)
    row.update(changes)
    with (latest/'board.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(row));writer.writeheader();writer.writerow(row)
    return row


def legacy_rule(data):
    rule=dict(season=2026,training_max_season=2025,training_games=1359,
              cuts=[3.,7.,10.],magnitudes=[3.,4.,7.,14.],method='median_signed_mov')
    (data/'latest/fixed_band_rules.json').write_text(json.dumps([rule]))
    return rule


def test_continuous_lock_ignores_stale_median_rules_and_saves_its_real_raw_selection(tmp_path):
    row=write_board(tmp_path,CUTOFF)
    legacy_rule(tmp_path)
    assert a.record(tmp_path,CUTOFF) == dict(candidates=1,locks=1)
    saved=a.read(tmp_path/a.LOCKS)[0]
    expected=float(m.implied_spread([row['model_wp']])[0])
    assert saved['policy_version'] == a.POLICY_VERSION
    assert saved['selection_method'] == 'continuous_spread'
    assert saved['raw_spread'] == saved['model_spread'] == saved['fixed_band_spread'] == expected
    assert saved['selected_side'] == 'home'  # Legacy mapped7 versus7.5 would select away.
    assert saved['fixed_rule'] is None
    assert a.validate_store(tmp_path) == dict(candidates=1,locks=1)


def test_continuous_capture_observes_t60_and_never_changes_earlier_or_locked_bytes(tmp_path):
    first=CUTOFF-dt.timedelta(minutes=2)
    write_board(tmp_path,first)
    a.record(tmp_path,first)
    before=(tmp_path/a.CANDIDATES).read_bytes()
    write_board(tmp_path,CUTOFF+dt.timedelta(seconds=1),model_wp=.1,spread_line=-20.)
    assert a.record(tmp_path,CUTOFF+dt.timedelta(minutes=3)) == dict(candidates=0,locks=1)
    saved=a.read(tmp_path/a.LOCKS)[0]
    assert saved['generated_utc'] == first.isoformat() and saved['selected_side'] == 'home'
    assert (tmp_path/a.CANDIDATES).read_bytes() == before
    locked=(tmp_path/a.LOCKS).read_bytes()
    a.record(tmp_path,CUTOFF+dt.timedelta(minutes=4))
    assert (tmp_path/a.LOCKS).read_bytes() == locked


@pytest.mark.parametrize('case',['before_adoption','first_seen_late','after_kickoff'])
def test_continuous_capture_does_not_fabricate_eligible_time(case,tmp_path):
    if case == 'before_adoption':
        when=a.CONTINUOUS_ADOPTED_UTC-dt.timedelta(seconds=1)
        now=a.CONTINUOUS_ADOPTED_UTC
    elif case == 'first_seen_late':
        when=CUTOFF-dt.timedelta(seconds=1);now=CUTOFF+dt.timedelta(seconds=1)
    else:
        when=KO;now=KO
    write_board(tmp_path,when)
    assert a.record(tmp_path,now) == dict(candidates=0,locks=0)


@pytest.mark.parametrize('margin,line,side',[(7.,7.,'home'),(-7.,-7.,'away'),(0.,0.,'')])
def test_continuous_zero_edge_takes_favorite_except_zero_pickem(tmp_path,margin,line,side):
    write_board(tmp_path,CUTOFF,model_wp=float(ndtr(margin/12.37)),spread_line=line)
    a.record(tmp_path,CUTOFF)
    saved=a.read(tmp_path/a.LOCKS)[0]
    assert saved['selected_side'] == side
    assert saved['skip_reason'] == ('zero_edge' if not side else None)
    assert not a.backfilled(saved)


@pytest.mark.parametrize('field,value',[
    ('raw_spread',4.),('model_spread',4.),('fixed_band_spread',7.),('model_wp',.9),
    ('selection_method','median_signed_mov'),('fixed_rule',{'training_max_season':2025}),
    ('model_spread','nan'),('fixed_band_spread','nan'),
    ('revision',LEGACY_REVISION),('policy_version',a.MEDIAN_POLICY_VERSION)])
def test_rehashed_continuous_formula_or_method_tampering_is_rejected(tmp_path,field,value):
    write_board(tmp_path,CUTOFF);a.record(tmp_path,CUTOFF)
    row=a.read(tmp_path/a.CANDIDATES)[0];row[field]=value;row.pop('candidate_sha256')
    row['candidate_sha256']=a.digest(row)
    (tmp_path/a.CANDIDATES).write_text(json.dumps(row)+'\n')
    (tmp_path/a.LOCKS).unlink()
    with pytest.raises(ValueError):a.validate_store(tmp_path)


def test_legacy_and_continuous_candidates_validate_together_without_rewriting_old_records(tmp_path):
    write_board(tmp_path,CUTOFF,revision=LEGACY_REVISION,architecture='market_product_1sd')
    legacy_rule(tmp_path);a.record(tmp_path,CUTOFF)
    old_candidate=(tmp_path/a.CANDIDATES).read_bytes();old_lock=(tmp_path/a.LOCKS).read_bytes()
    old_row=a.read(tmp_path/a.LOCKS)[0]
    assert old_row['policy_version'] == a.MEDIAN_POLICY_VERSION
    assert old_row['selected_side'] == 'away' and old_row['fixed_band_spread'] == 7.
    write_board(tmp_path,CUTOFF)
    a.record(tmp_path,CUTOFF)
    assert (tmp_path/a.CANDIDATES).read_bytes().startswith(old_candidate)
    assert (tmp_path/a.LOCKS).read_bytes().startswith(old_lock)
    assert a.read(tmp_path/a.LOCKS)[0] == old_row
    assert a.validate_store(tmp_path) == dict(candidates=2,locks=2)


def test_original_legacy_skip_policy_keeps_its_validation_semantics(tmp_path):
    write_board(tmp_path,CUTOFF,revision=LEGACY_REVISION,architecture='market_product_1sd',spread_line=7.)
    legacy_rule(tmp_path);a.record(tmp_path,CUTOFF)
    row=a.read(tmp_path/a.CANDIDATES)[0]
    row.update(policy_version='median-mov-ats-t60-2026-10-19-v1',selected_side='',skip_reason='zero_edge')
    row.pop('candidate_sha256');row['candidate_sha256']=a.digest(row)
    (tmp_path/a.CANDIDATES).write_text(json.dumps(row)+'\n');(tmp_path/a.LOCKS).unlink()
    before=(tmp_path/a.CANDIDATES).read_bytes()
    assert a.validate_store(tmp_path) == dict(candidates=1,locks=0)
    assert a.backfilled(row)
    assert (tmp_path/a.CANDIDATES).read_bytes() == before


def test_promoted_manifest_does_not_finalize_a_pending_old_revision_candidate(tmp_path):
    first=CUTOFF-dt.timedelta(minutes=2)
    write_board(tmp_path,first,revision=LEGACY_REVISION,architecture='market_product_1sd')
    legacy_rule(tmp_path);a.record(tmp_path,first)
    before=(tmp_path/a.CANDIDATES).read_bytes()
    # The new forecast is too late for a new lock; the old experiment cannot
    # acquire a new lock as a side effect of the promoted model's run.
    write_board(tmp_path,CUTOFF+dt.timedelta(seconds=1))
    assert a.record(tmp_path,CUTOFF+dt.timedelta(minutes=2)) == dict(candidates=0,locks=0)
    assert (tmp_path/a.CANDIDATES).read_bytes() == before
    assert a.read(tmp_path/a.LOCKS) == []


def season_fixture():
    history=pd.DataFrame([
        dict(game_id='old',season=2026,week=6,home='IND',away='TEN',gameday='2026-10-18',
             model_spread=8.,spread_line=6.5,result=7.,home_score=24.,away_score=17.),
        dict(game_id='post',season=2026,week=7,home='IND',away='TEN',gameday='2026-10-25',
             model_spread=8.,spread_line=6.5,result=7.,home_score=24.,away_score=17.),
        dict(game_id='pending',season=2026,week=8,home='IND',away='TEN',gameday='2026-11-01',
             model_spread=8.,spread_line=6.5,result=np.nan,home_score=np.nan,away_score=np.nan)])
    old_lock=dict(game_id='old',revision=LEGACY_REVISION,season=2026,week=6,
        home='IND',away='TEN',model_wp=.4,raw_spread=-3.,fixed_band_spread=-7.,market_spread=10.,
        selected_side='away',skip_reason=None,generated_utc='2026-10-17T12:00:00Z',
        kickoff_utc='2026-10-18T17:00:00Z',lock_at_utc='2026-10-17T12:00:00Z',legacy_lock=True)
    latest=dict(manifest=dict(revision=a.CONTINUOUS_REVISION,season=2026,recipe=dict(architecture='market_spread_total')),
                retro_ledger=history,ats_locks={(LEGACY_REVISION,'old'):old_lock},board=pd.DataFrame())
    native=pd.DataFrame([dict(game_id='post',revision=a.CONTINUOUS_REVISION,season=2026,week=7,
        home='IND',away='TEN',model_wp=.1,spread_line=20.,result=7.,home_score=24.,away_score=17.,
        generated_utc='2026-10-25T15:00:00Z',kickoff_utc='2026-10-25T17:00:00Z')])
    return latest,native


def test_authorized_new_replay_includes_post_adoption_history_without_faking_native_locks():
    latest,native=season_fixture();before=copy.deepcopy(latest['ats_locks'])
    frame=s.build(latest,native).set_index('game_id')
    assert frame.loc['old'].ats_basis == frame.loc['post'].ats_basis == 'Retrospective v1.19'
    assert frame.loc['old'].fixed_band_ats_team == frame.loc['post'].fixed_band_ats_team == 'IND'
    assert frame.loc['old'].fixed_band_ats_result == frame.loc['post'].fixed_band_ats_result == 'W'
    assert frame.loc['post'].spread_line == 6.5  # Native snapshot's line20 cannot replace rebuilt retro.
    assert not frame.index.duplicated().any()
    assert latest['ats_locks'] == before
    assert 'not native forward evidence' in s.report(frame.reset_index())
    assert frame.loc['pending'].ats_basis == 'Awaiting ATS lock'
    assert frame.loc['pending'].ats_status == 'pending'
    assert frame.loc['pending'].fixed_band_ats_side == ''
    assert np.isnan(frame.loc['pending'].fixed_band_spread)


def test_new_replay_uses_board_outcomes_only_without_live_predictor_or_price_reconstruction():
    latest,native=season_fixture()
    latest['board']=pd.DataFrame([dict(game_id='post',result=5.,home_score=22.,away_score=17.,
                                       model_wp=.01,model_spread=-30.,spread_line=50.)])
    row=s.build(latest,native).set_index('game_id').loc['post']
    assert (row.result,row.spread_line,row.fixed_band_spread,row.fixed_band_ats_team,row.fixed_band_ats_result)==(5.,6.5,8.,'IND','L')


def test_continuous_replay_zero_edges_pushes_and_pending_skip_denominators():
    latest,_=season_fixture();latest['ats_locks']={}
    latest['retro_ledger']=pd.DataFrame([
        dict(game_id='favorite',season=2026,week=6,home='IND',away='TEN',model_spread=7.,spread_line=7.,result=8.),
        dict(game_id='push',season=2026,week=6,home='IND',away='TEN',model_spread=8.,spread_line=7.,result=7.),
        dict(game_id='skip',season=2026,week=6,home='IND',away='TEN',model_spread=0.,spread_line=0.,result=0.),
        dict(game_id='pending',season=2026,week=7,home='IND',away='TEN',model_spread=0.,spread_line=0.,result=np.nan)])
    frame=s.build(latest,pd.DataFrame()).set_index('game_id')
    assert frame.loc['favorite'].fixed_band_ats_side == 'home'
    assert frame.loc['favorite'].fixed_band_ats_result == 'W'
    assert frame.loc['push'].fixed_band_ats_result == 'P'
    assert frame.loc['skip'].fixed_band_ats_result == 'S'
    assert frame.loc['pending'].fixed_band_ats_result == ''
    totals=s.summary(frame)
    assert (totals['bets'],totals['skips'],totals['pending']) == (2,1,1)
    assert totals['units'] == pytest.approx(10/11)
    assert totals['roi'] == pytest.approx(5/11)


def test_genuine_same_revision_continuous_lock_overrides_new_replay_and_can_capture_pending_selection():
    latest,native=season_fixture()
    saved=dict(game_id='post',revision=a.CONTINUOUS_REVISION,season=2026,week=7,home='IND',away='TEN',
        model_wp=float(ndtr(3/12.37)),raw_spread=3.,model_spread=3.,fixed_band_spread=3.,market_spread=6.5,
        selection_method='continuous_spread',policy_version=a.POLICY_VERSION,selected_side='away',skip_reason=None,
        generated_utc='2026-10-25T15:50:00Z',kickoff_utc='2026-10-25T17:00:00Z',lock_at_utc='2026-10-25T16:00:00Z')
    latest['ats_locks'][(a.CONTINUOUS_REVISION,'post')]=saved
    latest['ats_locks'][(a.CONTINUOUS_REVISION,'pending')]=dict(saved,game_id='pending',week=8,
        kickoff_utc='2026-11-01T18:00:00Z',lock_at_utc='2026-11-01T17:00:00Z')
    before=copy.deepcopy(latest['ats_locks'])
    frame=s.build(latest,native).set_index('game_id')
    row=frame.loc['post']
    assert (row.ats_basis,row.fixed_band_ats_team,row.fixed_band_ats_result,row.fixed_band_spread)==('60-minute lock','TEN','L',3.)
    assert frame.loc['pending'].ats_basis == '60-minute lock'
    assert frame.loc['pending'].ats_status == 'pending' and frame.loc['pending'].fixed_band_ats_result == ''
    assert frame.loc['pending'].fixed_band_ats_team == 'TEN'
    assert before == latest['ats_locks']


def test_old_model_manifest_and_old_rebuilt_data_cannot_be_relabelled_as_v119():
    latest,native=season_fixture()
    latest['retro_ledger']['revision']=LEGACY_REVISION
    with pytest.raises(ValueError,match='rebuilt'):s.build(latest,native)
    latest['manifest']['recipe']['architecture']='market_product_1sd'
    with pytest.raises(ValueError,match='v1.19 requires'):s.build(latest,native)
    # The old v1.18 manifest follows its legacy path even after m.REVISION changes.
    latest['manifest']['revision']=LEGACY_REVISION
    latest['fixed_band_ledger']=latest['retro_ledger'].iloc[[0]].assign(fixed_band_spread=4.)
    latest['ats_locks']={}
    frame=s.build(latest,pd.DataFrame())
    assert set(frame.ats_basis)=={'Historical replay'}


def test_new_model_never_reuses_old_precomputed_median_history_as_rebuilt_predictions():
    latest,native=season_fixture()
    latest['fixed_band_ledger']=latest.pop('retro_ledger').assign(fixed_band_spread=-20.)
    frame=s.build(latest,native)
    assert set(frame.ats_basis)=={'Awaiting ATS lock'}
    assert s.summary(frame)['bets']==0


def test_real_existing_legacy_store_still_validates_without_writes():
    data=Path(__file__).resolve().parents[1]/'data'
    paths=[data/name for name in (a.CANDIDATES,a.LOCKS,'ats_forward_shadow.jsonl')]
    before={p:p.read_bytes() for p in paths if p.exists()}
    a.validate_store(data)
    assert all(p.read_bytes()==value for p,value in before.items())
