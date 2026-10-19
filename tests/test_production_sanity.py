from pathlib import Path
import json
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


def test_committed_exports_pass_independent_audit_under_their_saved_identity():
    data=Path(__file__).resolve().parents[1]/'data'
    audit=s.inspect(data)
    assert audit['status']=='PASS' and all(audit['checks'].values())
    assert audit['historical_revision']==json.loads((data/'latest/manifest.json').read_text())['revision']
    assert audit['export_mode']=='median'  # old exports stay valid before the first v1.19 build
    assert audit['ats_capture']['candidates'] >= audit['ats_capture']['timed_locks']
    archive=audit['ats_archive']
    assert archive['original_selections']+archive['original_skips']==archive['snapshots']
    assert archive['backfilled_skips']<=archive['original_skips']
    rule=next(x for x in audit['rules'] if x['season']==2026)
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
    row=dict(revision='boxscore-composite-v1.18', game_id='2026_07_TEN_IND', season=2026,
        generated_utc='2026-10-25T15:58:00+00:00', observed_utc='2026-10-25T15:59:00+00:00',
        kickoff_utc='2026-10-25T17:00:00+00:00', lock_at_utc='2026-10-25T16:00:00+00:00',
        policy_version=legacy if original_skip else a.MEDIAN_POLICY_VERSION, lock_lead_minutes=60,
        fixed_rule=dict(training_max_season=2025,cuts=[3.,7.,10.],magnitudes=[3.,4.,7.,14.]),
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
    assert capture['by_revision_policy']==[dict(revision='boxscore-composite-v1.18',
        policy=json.loads((tmp_path/s.ats_locks.LOCKS).read_text())['policy_version'], timed_locks=1)]
    assert capture['current_revision_locks']==int(s.m.REVISION=='boxscore-composite-v1.18')
    report=s.report(tmp_path)
    assert 'Primary 60-minute ATS capture' in report
    assert 'backfilled favorite bets are excluded from forward evidence' in report
    assert [p.read_bytes() for p in paths]==before


def _continuous_exports(data):
    """Small raw replay where a median map cannot be fit or silently substituted."""
    from scipy.special import ndtr
    latest=data/'latest';latest.mkdir()
    spreads=np.array([3.,-3.,0.,4.])
    d=pd.DataFrame(dict(game_id=list('abcd'),season=[2026]*4,week=[6]*4,
        model_wp=ndtr(spreads/12.37),market_wp=[.6,.4,.5,.6],
        spread_line=[3.,-3.,0.,3.],result=[7.,-7.,0.,3.],
        home_moneyline=[-120.]*4,away_moneyline=[100.]*4))
    d['home won']=[1.,0.,.5,1.]
    d.to_csv(latest/'retro_ledger.csv',index=False)
    (latest/'manifest.json').write_text(json.dumps(dict(revision='boxscore-composite-v1.19',
        recipe=dict(architecture='market_spread_total'))))
    saved=d.assign(fixed_band_spread=spreads,selection_version=s.fixed_bands.SELECTION_VERSION,
        fixed_band_ats_result=['W','W','S','P'])
    saved.to_csv(latest/'fixed_band_ledger.csv',index=False)
    (latest/'fixed_band_rules.json').write_text('[]')
    return latest


def test_new_raw_replay_needs_no_medians_and_is_checked_independently(tmp_path):
    latest=_continuous_exports(tmp_path)
    before={p.name:p.read_bytes() for p in latest.iterdir()}
    audit=s.inspect(tmp_path)
    assert audit['status']=='PASS' and audit['export_mode']=='continuous'
    assert audit['rules']==[] and audit['checks']['exported_continuous_predictions']
    total=next(r for r in audit['historical'] if r['season']=='All')
    assert (total['wins'],total['losses'],total['pushes'],total['skips'])==(2,0,1,1)
    assert 'continuous margin = 12.37' in s.report(tmp_path)
    assert before=={p.name:p.read_bytes() for p in latest.iterdir()}
    (latest/'fixed_band_rules.json').write_text('[{"season":2026}]')
    assert s.inspect(tmp_path)['checks']['continuous_export_has_no_median_maps'] is False


def test_new_raw_replay_rejects_a_median_value_in_compatibility_export(tmp_path):
    latest=_continuous_exports(tmp_path)
    saved=pd.read_csv(latest/'fixed_band_ledger.csv');saved.loc[0,'fixed_band_spread']=7.
    saved.to_csv(latest/'fixed_band_ledger.csv',index=False)
    audit=s.inspect(tmp_path)
    assert audit['status']=='FAIL' and not audit['checks']['exported_continuous_predictions']


def test_legacy_archive_completion_uses_original_revision_after_promotion(monkeypatch):
    data=Path(__file__).resolve().parents[1]/'data'
    monkeypatch.setattr(s.m,'REVISION','boxscore-composite-v1.19')
    audit=s.inspect(data)
    rows=[r for r in s.ats_locks.read(data/'ats_forward_shadow.jsonl')
          if r.get('policy_version')==s.fixed_bands.POLICY_VERSION]
    graded=pd.read_csv(data/'forward_ledger.csv')
    completed=set(graded.loc[graded.status.isin(['graded','tie']),['revision','game_id']]
        .itertuples(index=False,name=None))
    expected=sum((r['revision'],r['game_id']) in completed for r in rows)
    assert expected>0 and audit['ats_archive']['completed']==expected
    assert audit['native']['snapshots']==0  # old forecasts do not become v1.19 evidence


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
