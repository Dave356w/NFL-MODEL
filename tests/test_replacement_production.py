import copy
import datetime as dt
import json
import numpy as np
import pandas as pd
import pytest
import ats_locks as locks
import qb_replacement as qr
import nfl_model as m
import season_ats as ats
import build_site


def team_metadata(flag,pid='backup'):
    return dict(qb_replacement=flag,qb_replacement_status='replacement starter' if flag else 'incumbent starter',
        qb_projected_id=pid,qb_incumbent_id='incumbent' if flag else pid,qb_incumbent_starts=3,
        qb_incumbent_last_week=3,qb_replacement_reference_week=3,qb_replacement_policy=qr.POLICY)


def row():
    r=dict(game_id='g',season=2026,week=4,home='H',away='A',fixed_band_spread=3.,spread_line=2.5,result=-4.)
    for side,flag in [('home',1.),('away',0.)]:
        r.update({side+'_'+k:v for k,v in team_metadata(flag,pid=side+'qb').items()})
    return r


def test_candidate_freezes_exactly_one_post_map_adjustment():
    raw=qr.overlay(pd.DataFrame([row()])).iloc[0].to_dict()
    p=locks.replacement_payload(raw,3.)
    candidate=dict(raw,revision=m.REVISION,**{k:v for k,v in p.items() if k not in raw})
    assert locks.validate_replacement(candidate,3.)==1.
    for field,value in [('fixed_band_spread',-1.),('qb_replacement_base_margin',1.),('qb_replacement_margin_adjustment',-4.)]:
        bad=copy.deepcopy(candidate);bad[field]=value
        with pytest.raises(ValueError):locks.validate_replacement(bad,3.)
    bad=copy.deepcopy(candidate);bad['qb_replacement']['home']=0.
    with pytest.raises(ValueError):locks.validate_replacement(bad,3.)
    bad=copy.deepcopy(candidate)
    bad['home_qb_incumbent_last_week']=4.
    bad['qb_replacement']['home_metadata']['qb_incumbent_last_week']=4.
    with pytest.raises(ValueError,match='strictly before'):locks.validate_replacement(bad,3.)
    assert locks.policy_for_revision(m.REVISION)==locks.REPLACEMENT_POLICY
    assert locks.REPLACEMENT_POLICY in locks.DURABLE_POLICIES
    assert locks.policy_for_revision('boxscore-composite-v1.22')==locks.WATCHER_POLICY


def latest():
    history=pd.DataFrame([dict(row(),gameday='2026-10-04')]).drop(columns=[c for c in row() if c.startswith(('home_qb_','away_qb_'))])
    table=pd.DataFrame([dict(game_id='g',season=2026,week=4,team=t,**team_metadata(flag)) for t,flag in [('H',1.),('A',0.)]])
    return dict(manifest=dict(revision=m.REVISION,season=2026),fixed_band_ledger=history,
                replacement_adjustments=table,board=pd.DataFrame(),ats_locks={})


def test_public_current_model_replay_replaces_old_version_and_regrades_once():
    x=latest();old=dict(revision='boxscore-composite-v1.22',game_id='g',season=2026,week=4,home='H',away='A',
        market_spread=2.5,fixed_band_spread=13.,selected_side='home',lock_at_utc='2026-10-04T16:00:00Z')
    x['ats_locks']={locks.key(old):old};before=copy.deepcopy(x['ats_locks'])
    ats.prepare_replacement_views(x,remapped=True)
    pool=ats.build(x,pd.DataFrame())
    assert len(pool)==1
    assert pool.iloc[0].fixed_band_spread==1.
    assert pool.iloc[0].fixed_band_ats_team=='A'
    assert pool.iloc[0].fixed_band_ats_result=='W'
    assert pool.iloc[0].ats_basis=='Historical replay'
    pd.testing.assert_frame_equal(ats.replacement_overlay(pool,x),pool)
    assert x['ats_locks']==before
    assert not locks.current_records(x['ats_locks'],m.REVISION)
    ats.align_calibration_2026(x,pool)
    assert x['fixed_band_ledger'].iloc[0].fixed_band_spread==pool.iloc[0].fixed_band_spread


def test_current_week_completed_replay_is_included_before_adoption():
    x=latest();x['board']=x['fixed_band_ledger'].assign(game_id='current',week=10,gameday='2026-11-12',gametime='20:15',fixed_band_spread=5.,result=3.)
    pool=ats.build(x,pd.DataFrame())
    assert set(pool.game_id)=={'g','current'}
    assert pool.loc[pool.game_id.eq('current'),'ats_status'].iloc[0]=='graded'


def test_own_live_lock_stays_adjusted_and_no_future_replay_is_created():
    x=latest();r=row();r.update(game_id='future',week=10,gameday='2026-11-15',gametime='13:00')
    x['fixed_band_ledger']=pd.DataFrame([r])
    no=ats.build(x,pd.DataFrame())
    assert no.iloc[0].ats_status=='unavailable'
    adjusted=qr.overlay(pd.DataFrame([r])).iloc[0].to_dict()
    saved=dict(adjusted,revision=m.REVISION,model_wp=.6,raw_spread=3.,market_spread=2.5,
        selected_side='away',generated_utc='2026-11-15T16:55:00Z',kickoff_utc='2026-11-15T18:00:00Z',
        lock_at_utc='2026-11-15T17:00:00Z',policy_version=locks.REPLACEMENT_POLICY)
    x['ats_locks']={locks.key(saved):saved}
    pool=ats.build(x,pd.DataFrame())
    assert pool.iloc[0].fixed_band_spread==1.
    assert pool.iloc[0].ats_basis=='60-minute lock'


def test_replacement_policy_does_not_change_earlier_season_margin():
    x=latest();x['fixed_band_ledger']['season']=2025
    ats.prepare_replacement_views(x,remapped=True)
    assert x['fixed_band_ledger'].fixed_band_spread.iloc[0]==3.


def test_pages_only_rejects_old_snapshot_under_new_code(tmp_path,monkeypatch):
    monkeypatch.setattr(build_site,'DATA',tmp_path)
    (tmp_path/'latest').mkdir()
    (tmp_path/'latest/manifest.json').write_text(json.dumps(dict(revision='boxscore-composite-v1.22')))
    with pytest.raises(ValueError,match='fresh v1.24'):build_site.main(['--pages-only'])
