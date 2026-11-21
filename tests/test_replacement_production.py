import copy
import datetime as dt
import json
import numpy as np
import pandas as pd
import pytest
import ats_locks as locks
import qb_replacement as qr
import nfl_model as m

V124='boxscore-composite-v1.24'  # these tests pin v1.24's replacement-QB overlay
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
    candidate=dict(raw,revision=V124,**{k:v for k,v in p.items() if k not in raw})
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
    assert locks.policy_for_revision(V124)==locks.REPLACEMENT_POLICY
    assert locks.REPLACEMENT_POLICY in locks.DURABLE_POLICIES
    assert locks.policy_for_revision('boxscore-composite-v1.22')==locks.WATCHER_POLICY


def latest():
    history=pd.DataFrame([dict(row(),gameday='2026-10-04')]).drop(columns=[c for c in row() if c.startswith(('home_qb_','away_qb_'))])
    table=pd.DataFrame([dict(game_id='g',season=2026,week=4,team=t,**team_metadata(flag)) for t,flag in [('H',1.),('A',0.)]])
    return dict(manifest=dict(revision=V124,season=2026),fixed_band_ledger=history,
                replacement_adjustments=table,board=pd.DataFrame(),ats_locks={})


def test_old_version_saved_lock_is_replaced_by_current_model_regrade():
    # Owner decision 2026-11-16: public pages show the current model's regrade. The
    # v1.22 lock stays in its journal but the game shows v1.24's replay (A, adjusted 1.0).
    x=latest();old=dict(revision='boxscore-composite-v1.22',game_id='g',season=2026,week=4,home='H',away='A',
        market_spread=2.5,fixed_band_spread=13.,selected_side='home',lock_at_utc='2026-10-04T16:00:00Z',
        kickoff_utc='2026-10-04T17:00:00Z',generated_utc='2026-10-04T15:55:00Z',model_wp=.7)
    x['ats_locks']={locks.key(old):old};before=copy.deepcopy(x['ats_locks'])
    ats.prepare_replacement_views(x,remapped=True)
    pool=ats.build(x,pd.DataFrame())
    assert len(pool)==1
    assert (pool.iloc[0].fixed_band_spread,pool.iloc[0].fixed_band_ats_team)==(1.,'A')
    assert pool.iloc[0].fixed_band_ats_result=='W'
    assert pool.iloc[0].ats_basis=='Historical replay'
    assert x['ats_locks']==before
    # Capture coverage still sees the saved lock, so the game is never relocked.
    assert locks.current_records(x['ats_locks'],V124)[(V124,'g')] is old
    assert locks.public_records(x['ats_locks'],V124)=={}
    ats.align_calibration_2026(x,pool)
    assert x['fixed_band_ledger'].iloc[0].fixed_band_spread==1.
    assert x['fixed_band_ledger'].iloc[0].lock_policy_version==ats.LOCK_POLICY_VERSION


def test_current_revision_own_lock_stays_the_public_bet():
    x=latest();own=dict(revision=V124,game_id='g',season=2026,week=4,home='H',away='A',
        market_spread=2.5,fixed_band_spread=13.,selected_side='home',lock_at_utc='2026-10-04T16:00:00Z',
        kickoff_utc='2026-10-04T17:00:00Z',generated_utc='2026-10-04T15:55:00Z',model_wp=.7)
    x['ats_locks']={locks.key(own):own}
    ats.prepare_replacement_views(x,remapped=True)
    pool=ats.build(x,pd.DataFrame())
    assert (pool.iloc[0].fixed_band_spread,pool.iloc[0].fixed_band_ats_team)==(13.,'H')
    assert pool.iloc[0].ats_basis=='60-minute lock'


def test_earlier_manifests_keep_their_recorded_display_rule():
    old=dict(revision='boxscore-composite-v1.21',game_id='g')
    records={locks.key(old):old}
    assert locks.public_records(records,'boxscore-composite-v1.22')==locks.current_records(records,'boxscore-composite-v1.22')


def test_replay_without_any_saved_lock_still_uses_current_model():
    x=latest()
    ats.prepare_replacement_views(x,remapped=True)
    pool=ats.build(x,pd.DataFrame())
    assert (pool.iloc[0].fixed_band_spread,pool.iloc[0].fixed_band_ats_team)==(1.,'A')
    assert pool.iloc[0].ats_basis=='Historical replay'


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
    saved=dict(adjusted,revision=V124,model_wp=.6,raw_spread=3.,market_spread=2.5,
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
    with pytest.raises(ValueError,match='fresh v1.25'):build_site.main(['--pages-only'])


def test_public_downloads_list_only_the_current_revisions_saved_locks():
    x=latest();old=dict(revision='boxscore-composite-v1.22',game_id='old')
    x['ats_locks']={locks.key(old):old}
    assert not build_site.has_public_saved_picks(x)  # replaced by the regrade (2026-11-16)
    own=dict(revision=V124,game_id='new')
    x['ats_locks'][locks.key(own)]=own
    assert build_site.has_public_saved_picks(x)
    legacy=dict(revision='boxscore-composite-v1.16',game_id='legacy',legacy_lock=True)
    x['ats_locks']={locks.key(legacy):legacy}
    assert not build_site.has_public_saved_picks(x)   # archived shadow rows are never inherited
