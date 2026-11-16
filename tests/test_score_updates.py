import copy
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

import score_updates as scores
import season_ats
import validate_data_files


NOW = dt.datetime(2026, 11, 16, 7, tzinfo=dt.timezone.utc)


def event(home=24, away=17, completed=True):
    return dict(id='123456', season={'type': 2, 'year': 2026}, week={'number': 10},
        date='2026-11-15T18:00:00Z',
        status={'type': {'completed': completed, 'state': 'post' if completed else 'in',
                         'name': 'STATUS_FINAL' if completed else 'STATUS_IN_PROGRESS'}},
        competitions=[{'competitors': [
            {'homeAway': 'home', 'team': {'abbreviation': 'IND'}, 'score': str(home)},
            {'homeAway': 'away', 'team': {'abbreviation': 'TEN'}, 'score': str(away)}]}])


def refresh(tmp_path, events):
    return scores.refresh(tmp_path, now=NOW, get=lambda url: {'events': events})


def test_final_score_poll_never_needs_odds_and_is_idempotent(tmp_path):
    calls = []
    def get(url):
        calls.append(url)
        assert '/scoreboard?' in url and 'odds' not in url
        return {'events': [event()]}
    result = scores.refresh(tmp_path, now=NOW, get=get)
    assert result == {'saved': 1, 'finals': 1, 'errors': []}
    assert len(calls) == 1
    row = scores.read(tmp_path)[0]
    assert (row['game_id'], row['home_score'], row['away_score']) == ('2026_10_TEN_IND', 24, 17)
    before = (tmp_path / scores.STORE).read_bytes()
    assert scores.refresh(tmp_path, now=NOW + dt.timedelta(minutes=15), get=get)['saved'] == 0
    assert (tmp_path / scores.STORE).read_bytes() == before


def test_live_tie_and_cancelled_scoreboard_values_are_not_finals(tmp_path):
    live = event(21, 21, completed=False)
    cancelled = event()
    cancelled['status']['type']['name'] = 'STATUS_CANCELED'
    assert refresh(tmp_path, [live, cancelled])['saved'] == 0
    assert not (tmp_path / scores.STORE).exists()
    assert refresh(tmp_path, [event(21, 21)])['saved'] == 1
    assert scores.read(tmp_path)[0]['home_score'] == 21


@pytest.mark.parametrize('change', [
    lambda e: e['competitions'][0]['competitors'][0].update(score=None),
    lambda e: e['competitions'][0]['competitors'][0].update(score='nan'),
    lambda e: e['competitions'][0]['competitors'][0].update(score='-1'),
    lambda e: e['competitions'][0]['competitors'][0].update(score='24.5'),
    lambda e: e['competitions'][0]['competitors'][0]['team'].update(abbreviation='UNKNOWN'),
    lambda e: e['competitions'][0]['competitors'][0].update(homeAway='away'),
    lambda e: e.update(date='2026-11-17T18:00:00Z'),
    lambda e: e.update(date='2026-11-15T18:00:00'),
    lambda e: e['week'].update(number=19),
])
def test_malformed_finals_fail_closed_and_preserve_saved_final(tmp_path, change):
    refresh(tmp_path, [event()])
    before = (tmp_path / scores.STORE).read_bytes()
    broken = event(31, 17)
    change(broken)
    result = refresh(tmp_path, [broken])
    assert result['saved'] == 0 and len(result['errors']) == 1
    assert (tmp_path / scores.STORE).read_bytes() == before


def test_wrong_season_and_preseason_are_ignored(tmp_path):
    wrong = event()
    wrong['season']['year'] = 2025
    preseason = event()
    preseason['season']['type'] = 1
    assert refresh(tmp_path, [wrong, preseason])['saved'] == 0


def test_provider_failure_or_missing_events_preserves_prior_scores(tmp_path):
    refresh(tmp_path, [event()])
    before = (tmp_path / scores.STORE).read_bytes()
    for response in ({}, {'events': None}):
        with pytest.raises(RuntimeError, match='retained saved scores'):
            scores.refresh(tmp_path, now=NOW, get=lambda url: response)
    def unavailable(url):
        raise OSError('offline')
    with pytest.raises(RuntimeError, match='offline'):
        scores.refresh(tmp_path, now=NOW, get=unavailable)
    assert (tmp_path / scores.STORE).read_bytes() == before


def test_valid_final_correction_replaces_scores_but_empty_response_does_not(tmp_path):
    refresh(tmp_path, [event()])
    assert refresh(tmp_path, [event(23, 17)])['saved'] == 1
    assert refresh(tmp_path, [])['saved'] == 0
    assert scores.read(tmp_path)[0]['home_score'] == 23
    assert not (tmp_path / (scores.STORE + '.tmp')).exists()


def test_conflicting_finals_in_one_response_keep_the_prior_result(tmp_path):
    refresh(tmp_path, [event()])
    result = refresh(tmp_path, [event(31, 17), event(30, 17)])
    assert result['saved'] == 0 and 'conflicting' in result['errors'][0]
    assert scores.read(tmp_path)[0]['home_score'] == 24


def test_overlay_only_changes_outcomes_and_rejects_identity_mismatch(tmp_path):
    refresh(tmp_path, [event()])
    frame = pd.DataFrame([dict(game_id='2026_10_TEN_IND', home='IND', away='TEN',
        model_wp=.7, spread_line=3., fixed_band_spread=7., home_moneyline=-150.,
        home_score=np.nan, away_score=np.nan, result=np.nan, status='pending')])
    before = frame.copy(deep=True)
    result = scores.overlay(frame, scores.read(tmp_path))
    pd.testing.assert_frame_equal(frame, before)
    assert (result.loc[0, 'home_score'], result.loc[0, 'away_score'], result.loc[0, 'result']) == (24, 17, 7)
    for name in ('model_wp', 'spread_line', 'fixed_band_spread', 'home_moneyline'):
        assert result.loc[0, name] == frame.loc[0, name]
    with pytest.raises(ValueError, match='teams do not match'):
        scores.overlay(frame.assign(home='TEN', away='IND'), scores.read(tmp_path))


def test_independent_finals_grade_saved_decision_over_stale_espn_archive(tmp_path):
    refresh(tmp_path, [event()])
    row = scores.read(tmp_path)[0]
    lock = dict(game_id=row['game_id'], season=2026, week=10, revision='boxscore-composite-v1.24',
        home='IND', away='TEN', model_wp=.7, market_spread=3., fixed_band_spread=7.,
        selected_side='home', generated_utc='2026-11-15T16:55:00Z',
        kickoff_utc=row['kickoff_utc'], lock_at_utc='2026-11-15T17:00:00Z', policy_version='v5')
    latest = dict(manifest={'revision': lock['revision']}, fixed_band_ledger=pd.DataFrame(),
        ats_locks={(lock['revision'], row['game_id']): lock},
        espn_archive=[dict(row, home_score=17, away_score=24, odds_pages=[], movements=[])], final_scores=[row])
    before = copy.deepcopy(lock)
    graded = season_ats.build(latest, pd.DataFrame()).iloc[0]
    assert graded.fixed_band_ats_result == 'W' and graded.result == 7
    assert graded.spread_line == 3 and graded.fixed_band_spread == 7
    assert graded.fixed_band_ats_side == 'home' and graded.ats_status == 'graded'
    assert lock == before
    latest['ats_locks'] = {}
    unavailable = season_ats.build(latest, pd.DataFrame()).iloc[0]
    assert unavailable.ats_status == 'unavailable' and unavailable.fixed_band_ats_result == ''
    assert np.isnan(unavailable.fixed_band_spread)


def test_data_validator_checks_final_store_schema_and_game_identity(tmp_path):
    refresh(tmp_path, [event()])
    assert tmp_path / scores.STORE in validate_data_files.validate_data_dir(tmp_path)
    valid = scores.read(tmp_path)[0]
    for changes in ({'home_score': '24'}, {'away_score': 17.0}, {'home_score': True},
                    {'week': '10'}, {'game_id': '2026_10_IND_TEN'}, {'home': []}):
        (tmp_path / scores.STORE).write_text(json.dumps([dict(valid, **changes)]))
        with pytest.raises(ValueError):
            validate_data_files.validate_data_dir(tmp_path)
    (tmp_path / scores.STORE).write_text(json.dumps([{'game_id': valid['game_id']}]))
    with pytest.raises(ValueError, match='missing required'):
        validate_data_files.validate_data_dir(tmp_path)
