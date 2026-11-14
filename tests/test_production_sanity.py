from pathlib import Path
import json
import shutil
import numpy as np
import pandas as pd
import pytest
from research import production_sanity as s


def test_independent_grading_skip_push_away_missing_and_pending():
    args=([3.,3.+1e-11,4.,-2.,1.,4.,np.nan],[3.,3.,3.,-3.,0.,3.,3.],[3.,4.,3.,0.,0.,np.nan,7.])
    assert s.independent_grades(*args,favorite_on_tie=False).tolist()==['S','S','P','W','P','','']
    # Production: a matching line is a favorite bet, graded like any other.
    assert s.independent_grades(*args).tolist()==['P','W','P','W','P','','']


def test_independent_zero_edge_favorite_away_and_pickem_skip():
    grades=s.independent_grades([-7.,-7.,0.,0.],[-7.,-7.,0.,0.],[-10.,-3.,5.,np.nan])
    assert grades.tolist()==['W','L','S','S']


def test_independent_moneyline_payouts_loss_tie_neutral_and_missing():
    d=pd.DataFrame({'model_wp':[.6,.4,.6,.5,.4,.6], 'home won':[1.,0.,.5,1.,1.,np.nan],
                    'home_moneyline':[-150.]*6,'away_moneyline':[130.]*6})
    grades,units=s.independent_moneyline(d)
    assert grades.tolist()==['W','W','P','','L','']
    np.testing.assert_allclose(units,[2/3,1.3,0.,np.nan,-1.,np.nan],equal_nan=True)


def test_independent_median_uses_losses_ties_and_only_prior_seasons():
    x=np.tile([1.,4.,8.,12.],80)
    d=pd.DataFrame({'season':np.repeat([2021,2022],160),'model_spread':x,'result':x+2})
    rule=s.median_rule(d,2023)
    assert rule['magnitudes']==[3.,6.,10.,14.]
    poison=d.assign(season=2023,result=-1000.)
    assert s.median_rule(pd.concat([d,poison]),2023)==rule
    tied=d.assign(result=0.)
    assert s.median_rule(pd.concat([d,tied]),2023)['magnitudes']==[1.5,3.,5.,7.]


def _replacement_export(home=1., away=0., season=2026):
    history = pd.DataFrame([dict(season=season, week=4)])
    known = np.isfinite(home) and np.isfinite(away)
    adjustment = -2. * home + 2. * away if known else 0.
    row = dict(qb_replacement_policy=s.REPLACEMENT_POLICY, qb_replacement_base_margin=3.,
               qb_replacement_margin_adjustment=adjustment, qb_replacement_applied=known,
               qb_replacement_overlay_status='classified' if known else 'unresolved; original margin retained')
    for side, flag in [('home', home), ('away', away)]:
        resolved = np.isfinite(flag)
        metadata = dict(qb_replacement=flag, qb_replacement_policy=s.REPLACEMENT_POLICY,
            qb_replacement_status=('replacement starter' if flag == 1. else 'incumbent starter')
                if resolved else 'questionable quarterback blend',
            qb_projected_id=('backup' if flag == 1. else 'incumbent') if resolved else np.nan,
            qb_incumbent_id='incumbent' if resolved else np.nan,
            qb_incumbent_starts=3 if resolved else 0, qb_incumbent_last_week=3 if resolved else np.nan,
            qb_replacement_reference_week=3)
        row.update({side + '_' + key: value for key, value in metadata.items()})
    return history, pd.DataFrame([row])


@pytest.mark.parametrize('home,away,expected', [(1., 0., 1.), (0., 1., 5.), (1., 1., 3.),
    (0., 0., 3.), (np.nan, 1., 3.), (1., np.nan, 3.)])
def test_independent_replacement_adjustment_is_post_map_and_preserves_unresolved(home, away, expected):
    history, saved = _replacement_export(home, away)
    before = saved.copy(deep=True)
    mapped = np.array([3.])
    np.testing.assert_array_equal(s.replacement_predictions(history, mapped, saved, s.REPLACEMENT_REVISION), [expected])
    np.testing.assert_array_equal(mapped, [3.])
    pd.testing.assert_frame_equal(saved, before)


@pytest.mark.parametrize('revision,season', [('boxscore-composite-v1.23', 2026), (s.REPLACEMENT_REVISION, 2025)])
def test_replacement_audit_keeps_earlier_revisions_and_seasons_unadjusted(revision, season):
    history, _ = _replacement_export(season=season)
    np.testing.assert_array_equal(s.replacement_predictions(history, [3.], None, revision), [3.])


@pytest.mark.parametrize('field,value', [
    ('qb_replacement_policy', 'old policy'), ('home_qb_replacement_policy', ''),
    ('home_qb_replacement', 2.), ('home_qb_projected_id', np.nan),
    ('home_qb_projected_id', 'incumbent'), ('home_qb_incumbent_starts', 1),
    ('home_qb_incumbent_last_week', 4), ('home_qb_replacement_reference_week', 4),
    ('qb_replacement_base_margin', 1.), ('qb_replacement_margin_adjustment', -4.),
    ('qb_replacement_margin_adjustment', 0.), ('qb_replacement_margin_adjustment', 2.),
    ('qb_replacement_margin_adjustment', np.nan),
    ('qb_replacement_applied', False), ('qb_replacement_overlay_status', 'unresolved'),
])
def test_replacement_audit_rejects_corrupt_or_postgame_evidence(field, value):
    history, saved = _replacement_export()
    saved.loc[0, field] = value
    with pytest.raises(ValueError):
        s.replacement_predictions(history, [3.], saved, s.REPLACEMENT_REVISION)


@pytest.mark.parametrize('missing', ['home_qb_replacement', 'qb_replacement_margin_adjustment'])
def test_replacement_audit_requires_metadata_even_when_both_replacements_cancel(missing):
    history, saved = _replacement_export(1., 1.)
    with pytest.raises(ValueError, match='missing replacement evidence'):
        s.replacement_predictions(history, [3.], None, s.REPLACEMENT_REVISION)
    with pytest.raises(KeyError):
        s.replacement_predictions(history, [3.], saved.drop(columns=missing), s.REPLACEMENT_REVISION)


@pytest.mark.parametrize('field', ['qb_replacement_margin_adjustment', 'fixed_band_spread', 'fixed_band_ats_result'])
def test_standalone_audit_rejects_replacement_export_tampering(tmp_path, field):
    latest = tmp_path/'latest'; latest.mkdir()
    source = Path(__file__).resolve().parents[1]/'data/latest'
    for name in ['manifest.json', 'retro_ledger.csv', 'fixed_band_ledger.csv', 'fixed_band_rules.json']:
        shutil.copyfile(source/name, latest/name)
    path = latest/'fixed_band_ledger.csv'
    saved = pd.read_csv(path)
    i = saved.index[saved.qb_replacement_margin_adjustment.abs().eq(2.)][0]
    if field == 'fixed_band_ats_result':
        saved.loc[i, field] = 'W' if saved.loc[i, field] != 'W' else 'L'
    else:
        saved.loc[i, field] += 2.
    saved.to_csv(path, index=False)
    before = path.read_bytes()
    audit = s.inspect(tmp_path)
    assert audit['status'] == 'FAIL'
    name = {'qb_replacement_margin_adjustment': 'exported_replacement_margin_evidence',
            'fixed_band_spread': 'exported_median_predictions', 'fixed_band_ats_result': 'exported_ats_grades'}[field]
    assert audit['checks'][name] is False
    assert path.read_bytes() == before


def _native_replacement_export(applied_marker=False):
    """A validated frozen decision in a different band than the replay WP."""
    from scipy.special import ndtr
    history, replay = _replacement_export(0., 0.)
    history = history.assign(game_id='g', week=10, home='H', away='A',
                             gameday='2026-11-15', spread_line=2.5, result=4.)
    _, frozen = _replacement_export(1., 0.)
    lock = frozen.iloc[0].to_dict()
    lock.update(game_id='g', revision=s.REPLACEMENT_REVISION, season=2026, week=10, home='H', away='A',
        model_wp=float(ndtr(8./12.37)), raw_spread=8., market_spread=4.5,
        fixed_rule=dict(cuts=[3., 7., 10.], magnitudes=[3., 4., 7., 14.]),
        qb_replacement_base_margin=7., fixed_band_spread=5.)
    # Runtime locks freeze flags and their source evidence; older v1.24 locks
    # omit the convenience applied/status fields that historical overlays carry.
    lock.pop('qb_replacement_overlay_status')
    if not applied_marker:
        lock.pop('qb_replacement_applied')
    lock.update(s.ats_locks.replacement_payload(lock, 7.))
    assert s.ats_locks.validate_replacement(lock, 7.) == 5.
    replay = replay.assign(fixed_band_spread=5., spread_line=4.5,
        qb_replacement_base_margin=7., qb_replacement_margin_adjustment=-2.,
        qb_replacement_applied=True if applied_marker else np.nan)
    return history, replay, {(s.REPLACEMENT_REVISION, 'g'): lock}


@pytest.mark.parametrize('applied_marker', [False, True])
def test_native_replacement_audit_uses_frozen_band_line_and_team_flags(applied_marker):
    history, saved, records = _native_replacement_export(applied_marker)
    predicted, lines = s.replacement_export_basis(history, [3.], saved, records)
    np.testing.assert_array_equal(predicted, [5.])
    np.testing.assert_array_equal(lines, [4.5])
    # At the replay line this game would win; at the saved handicap it lost.
    assert s.independent_grades(predicted, lines, history.result).tolist() == ['L']
    assert saved.home_qb_replacement.tolist() == [0.]  # replay annotation is deliberately retained


@pytest.mark.parametrize('field,value', [('fixed_band_spread', 3.), ('spread_line', 2.5),
    ('qb_replacement_base_margin', 3.), ('qb_replacement_margin_adjustment', 0.),
    ('qb_replacement_applied', False)])
def test_native_replacement_audit_rejects_altered_export(field, value):
    history, saved, records = _native_replacement_export(applied_marker=True)
    saved.loc[0, field] = value
    with pytest.raises(ValueError):
        s.replacement_export_basis(history, [3.], saved, records)


@pytest.mark.parametrize('gameday,native', [('2026-11-15', False), ('2026-10-04', True)])
def test_missing_native_lock_does_not_authorize_historical_fallback(gameday, native):
    history, saved = _replacement_export()
    history = history.assign(game_id='g', gameday=gameday, spread_line=2.5, result=4.)
    saved = saved.assign(fixed_band_spread=np.nan, spread_line=np.nan)
    predicted, lines = s.replacement_export_basis(history, [3.], saved, {}, {'g'} if native else set())
    assert np.isnan(predicted[0]) and np.isnan(lines[0])
    assert s.independent_grades(predicted, lines, history.result).tolist() == ['']


@pytest.mark.parametrize('time,available', [('19:59', True), ('20:00', False)])
def test_replay_cutoff_uses_known_eastern_kickoff_before_date_only_bound(time, available):
    history, saved = _replacement_export()
    history = history.assign(game_id='g', gameday='2026-11-13', gametime=time, spread_line=2.5, result=4.)
    saved = saved.assign(fixed_band_spread=1. if available else np.nan, spread_line=2.5 if available else np.nan)
    predicted, _ = s.replacement_export_basis(history, [3.], saved, {})
    assert bool(np.isfinite(predicted[0])) == available


def test_current_production_snapshot_passes_independent_audit():
    data=Path(__file__).resolve().parents[1]/'data'
    audit=s.inspect(data)
    assert audit['status']=='PASS' and all(audit['checks'].values())
    assert audit['ats_capture']['candidates'] >= audit['ats_capture']['timed_locks']
    archive=audit['ats_archive']
    assert archive['original_selections']+archive['original_skips']==archive['snapshots']
    assert archive['backfilled_skips']<=archive['original_skips']
    rule=next(x for x in audit['rules'] if x['season']==2026)
    if audit['weekly']:
        assert (rule['training_max_season'],rule['training_max_week']) < (rule['season'],rule['week'])
        assert len([r for r in audit['rules'] if r['season']==2026]) > 1
    else:
        assert rule['magnitudes']==[3.,4.,7.,14.] and rule['training_max_season']==2025
    total=next(x for x in audit['historical'] if x['season']=='All')
    assert total['selected']+total['skips']==total['opportunities']
    if total['opportunities']==895:
        assert (total['wins'],total['losses'],total['pushes'],total['skips'])==(473,397,25,0)
    for r in audit['historical']:
        if r['favorite']:
            assert r['favorite']['bets']==r['common_moneyline']['bets']


def test_missing_data_has_explicit_empty_state(tmp_path):
    assert s.inspect(tmp_path)['status']=='No historical inputs yet'
    assert 'No historical inputs yet' in s.report(tmp_path)


def _timed_store(data, original_skip=False):
    """One valid pre-cutoff candidate and matching pregame finalization."""
    from scipy.special import ndtr
    a=s.ats_locks
    wp=float(ndtr(8./12.37))
    legacy=next(policy for policy,favorite in a.POLICIES.items() if not favorite)
    # The legacy v1 skip keeps its annual rule; a current (v3) lock carries the weekly rule for its week.
    annual=dict(training_max_season=2025,cuts=[3.,7.,10.],magnitudes=[3.,4.,7.,14.])
    weekly=dict(season=2026,week=7,training_max_season=2026,training_max_week=6,cuts=[3.,7.,10.],
                magnitudes=[3.,4.,7.,14.],method=a.POLICY_METHODS[a.POLICY_VERSION])
    row=dict(revision='boxscore-composite-v1.22', game_id='2026_07_TEN_IND', season=2026, week=7,
        generated_utc='2026-10-25T15:58:00+00:00', observed_utc='2026-10-25T15:59:00+00:00',
        kickoff_utc='2026-10-25T17:00:00+00:00', lock_at_utc='2026-10-25T16:00:00+00:00',
        policy_version=legacy if original_skip else a.POLICY_VERSION, lock_lead_minutes=60,
        fixed_rule=annual if original_skip else weekly,
        model_wp=wp, raw_spread=float(s.m.implied_spread([wp])[0]),
        market_spread=7. if original_skip else 6.5, fixed_band_spread=7.,
        selected_side='' if original_skip else 'home', skip_reason='zero_edge' if original_skip else None)
    row['candidate_sha256']=a.digest(row)
    (data/a.CANDIDATES).write_text(json.dumps(row)+'\n')
    lock=dict(row,finalized_utc='2026-10-25T16:01:00+00:00')
    (data/a.LOCKS).write_text(json.dumps(lock)+'\n')
    return lock


@pytest.mark.parametrize('original_skip',[False,True])
def test_primary_capture_inventory_keeps_saved_skips_separate_and_read_only(tmp_path,original_skip):
    _timed_store(tmp_path,original_skip)
    paths=[tmp_path/s.ats_locks.CANDIDATES,tmp_path/s.ats_locks.LOCKS]
    before=[p.read_bytes() for p in paths]
    audit=s.inspect(tmp_path)
    assert audit['checks']['primary_ats_store_integrity']
    capture=audit['ats_capture']
    assert (capture['candidates'],capture['timed_locks'])==(1,1)
    assert capture['original_selections']==int(not original_skip)
    assert capture['original_skips']==capture['backfilled_skips']==int(original_skip)
    report=s.report(tmp_path)
    assert 'Primary 60-minute ATS capture' in report
    assert 'backfilled favorite bets are excluded from forward evidence' in report
    assert [p.read_bytes() for p in paths]==before


def test_recovered_saved_forecast_is_not_counted_as_a_pregame_finalization(tmp_path):
    a=s.ats_locks
    lock=_timed_store(tmp_path)
    lock.update(finalized_utc='2026-10-25T21:00:00+00:00', recovered_after_kickoff=True,
                finalization_policy_version=a.RECOVERY_POLICY)
    (tmp_path/a.LOCKS).write_text(json.dumps(lock)+'\n')
    audit=s.inspect(tmp_path)
    assert audit['checks']['primary_ats_store_integrity']
    capture=audit['ats_capture']
    assert (capture['timed_locks'],capture['recovered_saved_forecasts'])==(0,1)


@pytest.mark.parametrize('with_history',[False,True])
def test_corrupt_primary_lock_fails_standalone_sanity_with_or_without_history(tmp_path,with_history):
    lock=_timed_store(tmp_path)
    if with_history:
        latest=tmp_path/'latest';latest.mkdir()
        source=Path(__file__).resolve().parents[1]/'data/latest/retro_ledger.csv'
        (latest/'retro_ledger.csv').write_bytes(source.read_bytes())
    lock['fixed_band_spread']=14.  # diverges from the unchanged, hashed candidate
    path=tmp_path/s.ats_locks.LOCKS
    path.write_text(json.dumps(lock)+'\n')
    before=path.read_bytes()
    audit=s.inspect(tmp_path)
    assert audit['status']=='FAIL'
    assert audit['checks']['primary_ats_store_integrity'] is False
    assert 'differs from its saved candidate' in audit['ats_capture']['error']
    assert 'FAIL primary_ats_store_integrity' in s.report(tmp_path)
    assert path.read_bytes()==before
