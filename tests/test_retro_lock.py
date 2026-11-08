"""Owner-authorized recovery uses committed pregame inputs and the normal result path."""
import copy
import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

import ats_locks as a
import retro_lock as r
import season_ats
import build_site

NOW = dt.datetime(2026, 11, 6, 3, tzinfo=dt.timezone.utc)
REQUEST = dict(game_id='2026_09_JAX_BAL', source_commit='a' * 40, reason='Owner requested retro lock')


@pytest.fixture
def source():
    return dict(commit_sha='a' * 40, committed_utc='2026-11-06T00:10:13+00:00',
                file_sha256={p: 'b' * 64 for p in r.PATHS},
                manifest=dict(revision='boxscore-composite-v1.21', generated_utc='2026-11-06T00:10:03+00:00',
                              season=2026, week=9, config_signature='saved-signature'),
                board_row=dict(game_id='2026_09_JAX_BAL', season='2026', week='9', home='BAL', away='JAX',
                               gameday='2026-11-05', gametime='20:15', ready='True', result='',
                               model_wp='0.182724', spread_line='-10',
                               away_availability_evidence='{"blockers":["unknown inactive player"]}'),
                fixed_rule=dict(season=2026, week=9, training_max_season=2026, training_max_week=8,
                                cuts=[3., 7., 10.], magnitudes=[3., 5., 6., 13.],
                                method=a.POLICY_METHODS[a.POLICY_VERSION]))


def test_retro_lock_joins_normal_journal_idempotently_without_backdating(tmp_path, monkeypatch, source):
    monkeypatch.setattr(r, 'source_snapshot', lambda request: copy.deepcopy(source))
    assert r.apply(tmp_path, [REQUEST], NOW) == 1
    lock, = a.read(tmp_path / a.LOCKS)
    assert (lock['selected_side'], lock['market_spread'], lock['fixed_band_spread']) == ('away', -10., -13.)
    assert lock['observed_utc'] == lock['finalized_utc'] == NOW.isoformat()
    assert lock['source_snapshot']['board_row']['away_availability_evidence'] == source['board_row']['away_availability_evidence']
    assert not (tmp_path / a.CANDIDATES).exists()
    assert a.validate_store(tmp_path) == {'candidates': 0, 'locks': 1}
    before = (tmp_path / a.LOCKS).read_bytes()
    assert r.apply(tmp_path, [REQUEST], NOW + dt.timedelta(minutes=10)) == 0
    assert (tmp_path / a.LOCKS).read_bytes() == before
    # A subsequent normal capture neither changes it nor duplicates it.
    assert a.record(tmp_path, NOW) == {'candidates': 0, 'locks': 0}
    assert (tmp_path / a.LOCKS).read_bytes() == before
    assert 'owner-requested retro lock' in a.report(tmp_path)
    assert a.display_records(tmp_path)[a.key(lock)] == lock

    # Same picks, grading and totals as other saved locks; no separate result pool.
    latest = dict(manifest=source['manifest'], ats_locks={a.key(lock): lock},
                  board=pd.DataFrame([dict(game_id=REQUEST['game_id'], result=-14., home_score=10., away_score=24.)]))
    pool = season_ats.build(latest, pd.DataFrame())
    assert len(pool) == 1
    assert pool.iloc[0].fixed_band_ats_team == 'JAX'
    assert pool.iloc[0].fixed_band_ats_handicap == -10.
    assert pool.iloc[0].fixed_band_ats_result == 'W'
    assert pool.iloc[0].retro_locked
    assert pool.iloc[0].ats_basis == 'Owner-requested retro lock'
    assert pool.iloc[0].ats_basis not in season_ats.TIMED_BASES
    assert season_ats.summary(pool)['bets'] == 1
    public = build_site.public_ats({'pooled_ats': pool})
    assert len(public) == 1  # normal Results/export/headline pool includes the recovery
    assert season_ats.summary(public) == season_ats.summary(pool)
    assert public.iloc[0].ats_basis not in season_ats.TIMED_BASES


@pytest.mark.parametrize('change', ['late_commit', 'late_forecast', 'score', 'not_ready', 'future_rule', 'wrong_week'])
def test_postcutoff_inputs_scores_and_changed_rules_never_authorize_retro_lock(source, change):
    if change == 'late_commit': source['committed_utc'] = '2026-11-06T00:15:01+00:00'
    if change == 'late_forecast': source['manifest']['generated_utc'] = '2026-11-06T00:15:01+00:00'
    if change == 'score': source['board_row']['result'] = '-14'
    if change == 'not_ready': source['board_row']['ready'] = 'False'
    if change == 'future_rule': source['fixed_rule']['training_max_week'] = 9
    if change == 'wrong_week': source['manifest']['week'] = 10
    with pytest.raises(ValueError): r.decision(source)


def test_corrupt_retro_lock_and_changed_selection_are_rejected(tmp_path, monkeypatch, source):
    monkeypatch.setattr(r, 'source_snapshot', lambda request: source)
    r.apply(tmp_path, [REQUEST], NOW)
    lock, = a.read(tmp_path / a.LOCKS)
    lock['market_spread'] = -9.5
    with pytest.raises(ValueError, match='hash mismatch'): r.validate(lock)
    lock['retro_sha256'] = a.digest({k: v for k, v in lock.items() if k != 'retro_sha256'})
    with pytest.raises(ValueError, match='saved pregame inputs'): r.validate(lock)


def test_no_request_creates_no_retro_lock(tmp_path, monkeypatch):
    monkeypatch.setattr(r, 'source_snapshot', lambda request: pytest.fail('unrequested reconstruction'))
    assert r.apply(tmp_path, [], NOW) == 0
    assert not (tmp_path / a.LOCKS).exists()


def test_source_snapshot_reads_pinned_files_not_current_board(tmp_path, monkeypatch, source):
    import csv
    import io
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(source['board_row']))
    writer.writeheader(); writer.writerow(source['board_row'])
    files = {r.PATHS[0]: json.dumps(source['manifest']), r.PATHS[1]: out.getvalue(),
             r.PATHS[2]: json.dumps([source['fixed_rule']])}
    calls = []
    def git(*args):
        calls.append(args)
        if args[0] == 'cat-file': return ''
        if args[1] == '-s': return source['committed_utc']
        ref, path = args[1].split(':', 1)
        assert ref == REQUEST['source_commit']
        return files[path]
    monkeypatch.setattr(r, 'git', git)
    actual = r.source_snapshot(REQUEST)
    assert r.decision(actual)['selected_side'] == 'away'
    assert all('HEAD' not in arg for call in calls for arg in call)
