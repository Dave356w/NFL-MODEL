import numpy as np
import pandas as pd
import nfl_model as m
from test_availability_observations import inputs, STARTER, NOW


def test_confirmed_questionable_starter_is_not_blended():
    target, _, qb, snaps, inj, rost=inputs()
    inj.loc[len(inj)]=dict(season=2026,week=9,team='BAL',gsis_id=STARTER,
                          report_status='Questionable',date_modified='2026-11-04T18:00:00Z')
    args=(target,qb,snaps,inj,rost)
    confirmed={(2026,9,'BAL'):{'gsis_id':STARTER,'player':'Starter'}}
    mixed=m.availability_table(*args).set_index('team')
    full=m.availability_table(*args,qb_starters=confirmed).set_index('team')
    healthy=m.availability_table(target,qb,snaps,inj.loc[inj.gsis_id.ne(STARTER)],rost).set_index('team')
    assert '(Q)' in mixed.loc['BAL','qb_expected']
    assert full.loc['BAL','qb_expected']=='Starter'
    assert full.loc['BAL','qb_source']=='confirmed_starter'
    assert np.isclose(full.loc['BAL','qb_delta'],healthy.loc['BAL','qb_delta'])
    assert full.loc['JAX','qb_delta']==mixed.loc['JAX','qb_delta']
    with m.revision_identity('boxscore-composite-v1.22',m.PRODUCT_RECIPE):
        legacy=m.availability_table(*args,qb_starters=confirmed).set_index('team')
    assert '(Q)' in legacy.loc['BAL','qb_expected']


def historical_fixture():
    q=pd.DataFrame([dict(game_id='g',season=2026,week=1,team='H',gsis_id=p,
                        first_dropback_id=i,dropbacks=n,starter=p=='rb')
                    for p,i,n in [('rb',1,1),('starter',2,2),('backup',3,30)]])
    rost=pd.DataFrame([dict(season=2026,week=1,team='H',gsis_id=p,position=pos)
                       for p,pos in [('rb','RB'),('starter','QB'),('backup','QB')]])
    return q,rost


def test_first_actual_qb_survives_gadget_opener_and_early_injury():
    q,rost=historical_fixture()
    out=m.label_qb_starters(q,rost)
    assert out.loc[out.starter,'gsis_id'].tolist()==['starter']
    assert out.loc[out.starter_first_dropback,'gsis_id'].tolist()==['rb']
    assert out.starter_label_source.eq('first_qb_dropback').all()
    assert q.loc[q.starter,'gsis_id'].tolist()==['rb']


def test_missing_or_conflicting_position_data_is_unresolved():
    q,rost=historical_fixture()
    # The first passer could be a real QB when his position is missing.
    assert not m.label_qb_starters(q,rost[rost.gsis_id.ne('rb')]).starter.any()
    conflict=pd.concat([rost,rost[rost.gsis_id.eq('rb')].assign(position='QB')],ignore_index=True)
    assert not m.label_qb_starters(q,conflict).starter.any()
    assert not m.label_qb_starters(q,rost.assign(week=2)).starter.any()
    # A missing/tied play ID cannot conceal an earlier QB.
    assert not m.label_qb_starters(q.assign(first_dropback_id=np.nan),rost).starter.any()
    tied=q.copy();tied.loc[tied.gsis_id.eq('backup'),'first_dropback_id']=2
    assert not m.label_qb_starters(tied,rost).starter.any()


def test_legacy_audit_cache_requires_unambiguous_actual_qb():
    q,rost=historical_fixture();q=q.drop(columns='first_dropback_id')
    # Two QBs after the gadget opener, with no play order: unresolved.
    assert not m.label_qb_starters(q,rost).starter.any()
    # A sole actual QB after a positively identified gadget passer is safe.
    only=q[q.gsis_id.ne('backup')]
    assert m.label_qb_starters(only,rost).loc[lambda d:d.starter,'gsis_id'].tolist()==['starter']
    # The recorded first passer is positively a QB; later replacements do not change him.
    q['starter']=q.gsis_id.eq('starter')
    assert m.label_qb_starters(q,rost).loc[lambda d:d.starter,'gsis_id'].tolist()==['starter']


def test_previous_revision_signatures_remain_frozen():
    for version,expected in [('1.22','4e60b8110e719b1388a7ef57e53a72ed373e761eeb0a965d4fc13121994ac1c1'),
                             ('1.21','9eb27acbe2f14789d9a4b90b214122354d1fee7bf1d15fa736d5138af88d1c67')]:
        with m.revision_identity('boxscore-composite-v'+version,m.PRODUCT_RECIPE):
            assert m.config_signature()[0]==expected
    assert m.config_signature()[1]['qb_starter_policy']['confirmed']=='no Questionable blend'


def test_repaired_training_features_do_not_change_legacy_shadow():
    from test_product_production import fixture
    train,test=fixture()
    old={8.:pd.concat([train,test],ignore_index=True)}
    baseline_shadow={}; repaired_shadow={}
    m.current_predictions(old,m.PRODUCT_RECIPE,2023,1,baseline_shadow)
    new={8.:old[8.].copy()}
    new[8.]['d__avail__qb_delta']+=np.linspace(-3,3,len(new[8.]))
    m.current_predictions(new,m.PRODUCT_RECIPE,2023,1,repaired_shadow,shadow_features=old)
    assert baseline_shadow['fit']==repaired_shadow['fit']
    pd.testing.assert_frame_equal(baseline_shadow['board'],repaired_shadow['board'])


def test_aggregate_keeps_legacy_gadget_label_separate():
    plays=pd.DataFrame([dict(game_id='g',season_type='REG',two_point_attempt=0,posteam='H',
        passer_player_id=p,passer_player_name=p,play_id=i,play_type='pass',yards_gained=5,pass_attempt=1,sack=0)
        for i,p in enumerate(['rb','starter','backup','backup'],1)])
    schedule=pd.DataFrame([dict(game_id='g',season=2026,week=1,result=3.,home_team='H',home_qb_id='starter')])
    # A stale schedule ID pointing to a different player cannot override pbp.
    schedule['home_qb_id']='absent stale starter'
    raw=m.aggregate_qb(plays,schedule)
    assert not raw.starter.any()
    _,rost=historical_fixture()
    fixed=m.label_qb_starters(raw,rost)
    assert fixed.loc[fixed.starter,'gsis_id'].tolist()==['starter']
    assert fixed.loc[fixed.starter_first_dropback,'gsis_id'].tolist()==['rb']
    with m.revision_identity('boxscore-composite-v1.22',m.PRODUCT_RECIPE):
        old=m.aggregate_qb(plays,schedule)
    assert old.loc[old.starter,'gsis_id'].tolist()==['rb']


def test_full_shadow_preparation_builds_main_and_pass_profile_windows(monkeypatch):
    base=pd.DataFrame(dict(game_id=['a','b','c','d'],season=[2020,2020,2021,2021],week=[1,2,1,2],home='H',away='A'))
    cols=[f'{side}__{role}__rates_core__net_pass_yards_per_pass_play' for side,role in
          [('home','for'),('away','allowed'),('away','for'),('home','allowed')]]
    calls=[]
    def lagged(box,schedule,half,availability,profile_families=None):
        calls.append(half);f=base.copy()
        for i,c in enumerate(cols):f[c]=np.array([5.,6.,7.,8.])+(i*half/16.)
        return f
    schedules=base.rename(columns={'home':'home_team','away':'away_team'}).assign(home_moneyline=-130.,away_moneyline=110.)
    monkeypatch.setattr(m,'lagged_features',lagged)
    with m.revision_identity(m.SHADOW_REVISION,m.SHADOW_RECIPE):
        out=m.prepare_legacy_shadow_features(None,schedules,None)
    assert calls==[8.,16.]
    assert set(out)=={8.,16.}
    expected,_=m.pass_contexts(out[16.])
    np.testing.assert_allclose(out[8.].pass_product,expected.pass_product,equal_nan=True)
    assert out[8.].q.notna().all()
