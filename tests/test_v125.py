"""v1.25 (owner decision 2026-11-16): v1.24 without the replacement-QB margin adjustment."""
import copy
import datetime as dt
import json

import pandas as pd
import pytest

import ats_locks as locks
import build_site
import nfl_model as m
import season_ats as ats
from test_replacement_production import latest as v124_latest

V124 = 'boxscore-composite-v1.24'


def test_identity_signature_and_lock_policy():
    assert m.REVISION == 'boxscore-composite-v1.25' and m.OUTPUT_NAME == 'nfl_boxscore_output_v1_25'
    sig, cfg = m.config_signature()
    assert 'replacement_margin' not in cfg
    with m.revision_identity(V124, m.PRODUCT_RECIPE):
        old_sig, old_cfg = m.config_signature()
    assert 'replacement_margin' in old_cfg and sig != old_sig
    assert locks.policy_for_revision(m.REVISION) == locks.NO_REPLACEMENT_POLICY
    assert locks.policy_for_revision(V124) == locks.REPLACEMENT_POLICY
    assert locks.NO_REPLACEMENT_POLICY in locks.DURABLE_POLICIES
    assert m.REVISION in locks.REGRADE_REVISIONS


def v125_latest():
    x = v124_latest()
    x['manifest'] = dict(revision=m.REVISION, season=2026)
    return x


def test_replay_keeps_the_median_map_without_the_two_point_adjustment():
    # Same fixture where v1.24 moves the home replacement's margin from 3 to 1 (team A).
    old = v124_latest(); ats.prepare_replacement_views(old, remapped=True)
    assert ats.build(old, pd.DataFrame()).iloc[0].fixed_band_spread == 1.
    x = v125_latest(); ats.prepare_replacement_views(x, remapped=True)
    pool = ats.build(x, pd.DataFrame())
    assert (pool.iloc[0].fixed_band_spread, pool.iloc[0].fixed_band_ats_team) == (3., 'H')
    assert pool.iloc[0].lock_policy_version == ats.LOCK_POLICY_VERSION


def test_v124_lock_is_replaced_by_the_v125_regrade_but_still_counts_for_capture():
    x = v125_latest()
    saved = dict(revision=V124, game_id='g', season=2026, week=4, home='H', away='A', market_spread=2.5,
                 fixed_band_spread=1., selected_side='away', lock_at_utc='2026-10-04T16:00:00Z',
                 kickoff_utc='2026-10-04T17:00:00Z', generated_utc='2026-10-04T15:55:00Z', model_wp=.6)
    x['ats_locks'] = {locks.key(saved): saved}
    pool = ats.build(x, pd.DataFrame())
    assert (pool.iloc[0].fixed_band_spread, pool.iloc[0].ats_basis) == (3., 'Historical replay')
    assert locks.public_records(x['ats_locks'], m.REVISION) == {}
    assert locks.current_records(x['ats_locks'], m.REVISION)[(m.REVISION, 'g')] is saved
    own = dict(saved, revision=m.REVISION, fixed_band_spread=3., selected_side='home')
    x['ats_locks'][locks.key(own)] = own
    pool = ats.build(x, pd.DataFrame())
    assert (pool.iloc[0].fixed_band_spread, pool.iloc[0].ats_basis) == (3., '60-minute lock')


def test_week_10_is_replayed_and_week_11_needs_its_own_lock():
    cutoff = ats.replay_cutoff(m.REVISION)
    assert ats.historical_before_adoption(dict(kickoff_utc='2026-11-17T01:15:00Z'), cutoff)
    assert not ats.historical_before_adoption(dict(kickoff_utc='2026-11-20T01:15:00Z'), cutoff)


def crafted(revision, policy, **changes):
    """A hash-valid pre-cutoff candidate that reaches the revision/policy checks."""
    from statistics import NormalDist
    wp = .6
    raw = 12.37 * NormalDist().inv_cdf(wp)
    rule = dict(season=2026, week=11, training_max_season=2026, training_max_week=10, cuts=[3., 7., 10.],
                magnitudes=[3., 5., 7., 13.], method='weighted_median_signed_mov_weekly_decay')
    row = dict(revision=revision, game_id='2026_11_A_H', season=2026, week=11, home='H', away='A',
               generated_utc='2026-11-22T16:55:00+00:00', observed_utc='2026-11-22T16:56:00+00:00',
               kickoff_utc='2026-11-22T18:00:00+00:00', lock_at_utc='2026-11-22T17:00:00+00:00',
               lock_lead_minutes=locks.LEAD_MINUTES, policy_version=policy, fixed_rule=rule,
               model_wp=wp, raw_spread=raw, market_spread=2.5, fixed_band_spread=3.,
               selected_side='home', skip_reason=None, **changes)
    row['candidate_sha256'] = locks.digest(row)
    return row


@pytest.mark.parametrize('revision,policy,message', [
    (m.REVISION, locks.REPLACEMENT_POLICY, 'Replacement lock policy requires v1.24'),
    (m.REVISION, locks.WATCHER_POLICY, 'v1.25 requires lock policy v6'),
    (m.REVISION, locks.NO_REPLACEMENT_POLICY, 'v1.25 requires lock policy v6 and availability evidence'),
    ('boxscore-composite-v1.22', locks.NO_REPLACEMENT_POLICY, 'Lock policy v6 requires v1.25'),
])
def test_store_rejects_v125_policy_mismatches(tmp_path, revision, policy, message):
    (tmp_path / locks.CANDIDATES).write_text(json.dumps(crafted(revision, policy)) + '\n')
    with pytest.raises(ValueError, match=message):
        locks.validate_store(tmp_path)


def test_pages_only_waits_for_a_fresh_v125_snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, 'DATA', tmp_path)
    (tmp_path / 'latest').mkdir()
    (tmp_path / 'latest/manifest.json').write_text(json.dumps(dict(revision=V124)))
    with pytest.raises(ValueError, match='fresh v1.25'):
        build_site.main(['--pages-only'])
