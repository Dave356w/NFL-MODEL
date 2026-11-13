import numpy as np
import pandas as pd
import pytest

import qb_replacement as q


def inputs(starters=('a','a','a','b'),week=5):
    rows=[]
    for w,pid in enumerate(starters,1):
        for p,name in [('a','A.Starter'),('b','B.Backup')]:
            rows.append(dict(game_id=f'g{w}',season=2026,week=w,team='T',gsis_id=p,
                name=name,starter=p==pid,dropbacks=30 if p==pid else 2))
    qb=pd.DataFrame(rows)
    roster=pd.DataFrame([dict(season=2026,week=week-1,team='T',gsis_id=p,position='QB',
        full_name=name,status='ACT') for p,name in [('a','Aaron Starter'),('b','Bob Backup')]])
    av=pd.DataFrame([dict(season=2026,week=week,team='T',qb_expected='B.Backup',qb_delta=-.7)])
    return av,qb,roster


def annotate(*args):
    return q.annotate_availability(*args).iloc[0]


def test_established_incumbent_replaced_but_injury_status_does_not_remove_membership():
    av,qb,rost=inputs()
    rost.loc[rost.gsis_id.eq('a'),'status']='RES'
    got=annotate(av,qb,rost)
    assert got.qb_replacement==1
    assert got.qb_projected_id=='b' and got.qb_incumbent_id=='a'
    assert got.qb_incumbent_starts==3 and got.qb_incumbent_last_week==3
    assert got.qb_replacement_reference_week==4 and got.qb_delta==-.7
    assert got.qb_replacement_policy==q.POLICY


def test_incumbent_tie_uses_latest_actual_start_and_stops_flagging_new_incumbent():
    av,qb,rost=inputs(starters=('a','a','b','b'))
    got=annotate(av,qb,rost)
    assert got.qb_incumbent_id=='b' and got.qb_replacement==0
    assert got.qb_incumbent_last_week==4


def test_same_game_future_and_other_team_actual_starts_cannot_change_flag():
    av,qb,rost=inputs()
    before=annotate(av,qb,rost)
    leak=qb.assign(game_id=lambda d:'future'+d.game_id,week=5,starter=lambda d:d.gsis_id.eq('b'))
    other=qb.assign(game_id=lambda d:'other'+d.game_id,team='U',starter=lambda d:d.gsis_id.eq('b'))
    after=annotate(av,pd.concat([qb,leak,other],ignore_index=True),rost)
    for col in q.META_COLUMNS:
        assert before[col]==after[col]


def test_latest_earlier_roster_after_bye_and_current_week_departure_rules():
    av,qb,rost=inputs()
    rost['week']=3  # prior game roster omitted during a bye; latest earlier still applies
    current=rost.loc[rost.gsis_id.eq('b')].assign(week=5)
    got=annotate(av,qb,pd.concat([rost,current],ignore_index=True))
    assert got.qb_replacement==1 and got.qb_replacement_reference_week==3
    # A departure already reflected in the earlier roster is not a backup swap.
    departed=annotate(av,qb,rost.loc[rost.gsis_id.eq('b')])
    assert departed.qb_replacement==0
    assert departed.qb_replacement_status=='incumbent no longer rostered at quarterback'


def test_missing_reference_roster_is_unknown_and_blends_never_become_binary_flags():
    av,qb,rost=inputs()
    unresolved=annotate(av,qb,rost.iloc[:0])
    assert np.isnan(unresolved.qb_replacement)
    blend=annotate(av.assign(qb_expected='A.Starter (Q) / B.Backup'),qb,rost)
    assert np.isnan(blend.qb_replacement)
    # Even an explicit identity must not hide an unresolved Questionable blend.
    blend_id=annotate(av.assign(qb_expected='A.Starter (Q) / B.Backup',qb_projected_id='a'),qb,rost)
    assert np.isnan(blend_id.qb_replacement)


def test_unresolved_actual_history_does_not_fabricate_an_incumbent():
    av,qb,rost=inputs()
    qb.loc[qb.week.eq(2),'starter']=False
    assert np.isnan(annotate(av,qb,rost).qb_replacement)
    qb.loc[qb.week.eq(2),'starter']=True
    assert np.isnan(annotate(av,qb,rost).qb_replacement)


def test_unestablished_starter_and_week_one_are_not_offseason_backup_flags():
    av,qb,rost=inputs(starters=('a',),week=2)
    assert annotate(av,qb,rost).qb_replacement==0
    av['week']=1;rost['week']=1
    got=annotate(av,qb.iloc[:0],rost)
    assert got.qb_replacement==0 and got.qb_replacement_reference_week==1


def test_names_disambiguate_on_reference_qb_roster_and_accept_confirmed_identity():
    av,qb,rost=inputs()
    av['qb_expected']='J.Daniels'
    qb.loc[qb.gsis_id.eq('a'),'name']='J.Daniels'
    qb.loc[qb.gsis_id.eq('b'),'name']='J.Daniels'
    rost=rost.loc[rost.gsis_id.eq('b')].copy();rost['full_name']='Jayden Daniels'
    got=annotate(av,qb,rost)
    assert got.qb_projected_id=='b'
    unknown=annotate(av,qb,inputs()[2])
    assert np.isnan(unknown.qb_replacement)
    explicit=annotate(av.assign(qb_projected_id='b'),qb,inputs()[2])
    assert explicit.qb_projected_id=='b' and explicit.qb_replacement==1


def test_overlay_sign_cancel_unknown_idempotence_and_flag_refresh():
    frame=pd.DataFrame(dict(fixed_band_spread=[3.,3.,3.,3.],home_qb_replacement=[1.,0.,1.,np.nan],
        away_qb_replacement=[0.,1.,1.,0.]))
    original=frame.copy(deep=True)
    out=q.overlay(frame)
    np.testing.assert_allclose(out.fixed_band_spread,[1.,5.,3.,3.])
    np.testing.assert_allclose(out[q.BASE_MARGIN],[3.,3.,3.,3.])
    assert out.qb_replacement_applied.tolist()==[True,True,True,False]
    pd.testing.assert_frame_equal(frame,original)
    pd.testing.assert_frame_equal(q.overlay(out),out)
    # Reclassification recomputes from the original margin, never from an already reduced margin.
    changed=q.overlay(out.assign(home_qb_replacement=0.,away_qb_replacement=0.))
    np.testing.assert_allclose(changed.fixed_band_spread,3.)


def test_overlay_rejects_unknown_policies_missing_original_and_invalid_flags():
    frame=pd.DataFrame(dict(fixed_band_spread=[3.],home_qb_replacement=[1.],away_qb_replacement=[0.]))
    with pytest.raises(ValueError):q.overlay(frame.assign(qb_replacement_policy='foreign'))
    with pytest.raises(ValueError):q.overlay(frame.assign(qb_replacement_policy=q.POLICY))
    with pytest.raises(ValueError):q.overlay(frame.assign(home_qb_replacement=.5))
