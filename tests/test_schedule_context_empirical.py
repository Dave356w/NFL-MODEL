"""Known schedule features, sparse-context backoff and exact empirical mixtures."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import schedule_context_empirical as s


def row(**changes):
    return dict(game_id='fixture',season=2023,week=5,gameday='2023-10-08',gametime='13:00',
                home_team='BUF',away_team='SEA',location='Home',home_rest=7,away_rest=7,**changes)


def changed(**changes):
    return row()|changes


def test_west_to_east_early_and_reverse_late_clock():
    keys=s.schedule_keys(row())
    assert keys['travel']=='eastward2plus' and keys['body_clock']=='afternoon|early'
    assert keys['venue']=='Eastern' and keys['slot']=='Sunday_early'
    keys=s.schedule_keys(changed(home_team='SEA',away_team='BUF',gametime='20:20'))
    assert keys['travel']=='westward2plus' and keys['body_clock']=='evening|late'
    assert keys['slot']=='SNF'


def test_phoenix_dst_and_st_louis_relocation():
    september=s.schedule_keys(changed(home_team='ARI',away_team='BUF',gameday='2023-09-10',gametime='14:00'))
    november=s.schedule_keys(changed(home_team='ARI',away_team='BUF',gameday='2023-11-12',gametime='14:00'))
    assert september['body_clock'].startswith('early|')
    assert november['body_clock'].startswith('afternoon|')
    assert s.home_zone('LA',2015)[1]=='Central' and s.home_zone('LA',2016)[1]=='Pacific'
    a=s.schedule_keys(changed(home_team='LA',away_team='BUF',season=2015))
    b=s.schedule_keys(changed(home_team='LA',away_team='BUF',season=2016))
    assert a['travel']=='small_shift' and b['travel']=='westward2plus'
    for team in ['SD','OAK','LV','LAC']:assert s.home_zone(team,2023)[1]=='Pacific'


@pytest.mark.parametrize('date,time,expected',[
    ('2023-10-05','20:15','TNF'),('2023-11-23','12:30','Thursday_day'),
    ('2023-10-09','20:15','MNF'),('2023-10-08','13:00','Sunday_early'),
    ('2023-10-08','16:25','Sunday_late'),('2023-10-08','20:20','SNF')])
def test_kickoff_slots(date,time,expected):
    assert s.schedule_keys(changed(gameday=date,gametime=time))['slot']==expected


def test_both_teams_rest_gap_opener_final_week_and_missing():
    assert s.rest_key(4,4,5)=='short|short|within1'
    assert s.rest_key(14,7,5)=='long|normal|home_plus2'
    assert s.rest_key(6,7,5)=='short|normal|within1'
    assert s.rest_key(None,7,5) is None and s.rest_key(np.nan,7,5) is None
    assert s.rest_key(np.nan,np.nan,1)=='opener'
    assert s.schedule_keys(changed(season=2020,week=17))['phase']=='final'
    assert s.schedule_keys(changed(season=2023,week=17))['phase']=='late'
    assert s.schedule_keys(changed(season=2023,week=18))['phase']=='final'


def test_neutral_and_bad_clock_fall_back_without_inventing_venue():
    for change in [dict(location='Neutral'),dict(gametime='bad')]:
        keys=s.schedule_keys(changed(**change))
        assert all(keys[g] is None for g in ['slot','travel','body_clock','venue'])
        assert keys['rest'] is not None and keys['phase']=='mid'
    with pytest.raises(ValueError,match='Unknown team'):s.home_zone('UNKNOWN',2023)


def test_features_do_not_consume_outcomes_and_rest_join_is_safe():
    f=pd.DataFrame([row()|{'home_score':10,'away_score':20}]).drop(columns=['home_rest','away_rest'])
    rest=pd.DataFrame([dict(game_id='fixture',season=2023,week=5,home_rest=7,away_rest=4)])
    first=s.add_features(f,rest)
    other=s.add_features(f.assign(home_score=999,away_score=0),rest)
    columns=['feature_'+g for g in s.GROUPS+('joint',)]
    assert first[columns].equals(other[columns])
    with pytest.raises(ValueError,match='Duplicate rest'):s.add_features(f,pd.concat([rest,rest]))
    missing=s.add_features(f,rest.iloc[:0]);assert missing.feature_rest.isna().all()
    neutral=f.assign(game_id='neutral',location='Neutral')
    joined=s.add_features(pd.concat([f,neutral]),rest)
    assert pd.isna(joined.loc[joined.game_id.eq('neutral'),'feature_joint'].iloc[0])


def test_sparse_unknown_and_distant_context_fall_back_exactly():
    w=np.ones(200)/200;keys=np.array(['match']*10+['other']*190)
    for key in ['match','absent',None]:
        new,audit=s.shrink_weights(w,keys,key,30)
        assert np.array_equal(new,w) and audit['context_fallback']
    # Numerous equally weighted distant matches have high Kish ESS but tiny
    # probability mass under this target's market context, so still fall back.
    w=np.r_[np.ones(100)*.009999,np.ones(100)*.000001];w/=w.sum()
    keys=np.array(['near']*100+['far']*100)
    new,audit=s.shrink_weights(w,keys,'far',30)
    assert audit['context_kish']>99 and audit['context_support']<1
    assert np.array_equal(new,w)


def test_supported_context_shrinks_coherently_and_more_prior_means_less_change():
    w=np.ones(200)/200;keys=np.array(['match']*60+['other']*140)
    low,a=s.shrink_weights(w,keys,'match',30)
    high,b=s.shrink_weights(w,keys,'match',100)
    assert a['context_support']==pytest.approx(60) and a['context_alpha']==pytest.approx(2/3)
    assert low[:60].sum()==pytest.approx((1-2/3)*.3+2/3)
    assert np.all(low>0) and low.sum()==pytest.approx(1)
    assert b['context_alpha']<a['context_alpha']
    assert np.linalg.norm(high-w)<np.linalg.norm(low-w)
    with pytest.raises(ValueError):s.shrink_weights(w*2,keys,'match',30)


def test_additive_missing_components_remain_plain_and_ids_must_align():
    n=200;h=pd.DataFrame(dict(game_id=[f'g{i}' for i in range(n)]))
    for g in s.GROUPS+('joint',):h['feature_'+g]=None
    base=dict(home=np.arange(n)%30,away=np.arange(n)%17,weights=np.ones(n)/n,
              source_ids=h.game_id.to_numpy(),audit={'final_ess':n})
    target={'feature_'+g:None for g in s.GROUPS+('joint',)}
    result=s.contextual_distribution(base,h,target,s.VARIANT_MAP['additive_k30'])
    assert np.allclose(result['weights'],base['weights'],atol=1e-17)
    assert result['audit']['context_fallback']
    assert np.array_equal(result['home'],base['home']) and np.array_equal(result['away'],base['away'])
    with pytest.raises(ValueError,match='align'):
        s.contextual_distribution(base,h.iloc[::-1],target,s.PLAIN)


def test_plain_can_win_annual_selection_without_using_current_outcomes():
    archive=pd.DataFrame([dict(season=y,arm=v.name,primary_crps=1. if v==s.PLAIN else 2.)
                         for y in [2015,2016,2017] for v in s.VARIANTS])
    name,audit=s.select(archive,2017)
    assert name=='plain' and audit['selection_max_season']==2016
    archive.loc[archive.season.eq(2017),'primary_crps']=-999
    assert s.select(archive,2017)==(name,audit)
    for group in s.GROUPS:assert s.select(archive,2017,group)[0]=='plain'
