"""Production peak extraction, prior-game timing and experiment identity."""
import numpy as np
import pandas as pd
import pytest

import nfl_model as m
import build_site as b


def pbp():
    return pd.DataFrame(dict(game_id=['g']*6,play_id=[1,2,3,4,5,999],season_type=['REG']*6,
        qtr=[1,2,3,4,5,2],game_seconds_remaining=[3600,2700,1800,0,600,2500],
        total_home_score=[0,7,7,17,27,0],total_away_score=[0,0,10,17,17,40],
        sp=[0,1,1,1,1,0],play_deleted=[0]*6))


def schedule():
    return pd.DataFrame([dict(game_id='g',home_team='H',away_team='A',result=10,home_score=27,away_score=17)])


def test_scoring_events_include_overtime_and_ignore_stale_admin():
    x=m.aggregate_score_peaks(pbp(),schedule()).set_index('team')
    assert x.loc['H','max_lead']==10 and x.loc['H','max_deficit']==3
    assert x.loc['A','max_lead']==3 and x.loc['A','max_deficit']==10


def test_deleted_scoring_play_does_not_change_peaks():
    p=pbp();p.loc[len(p)]=['g',2.1,'REG',2,2600,99,0,1,1]
    pd.testing.assert_frame_equal(m.aggregate_score_peaks(p,schedule()),m.aggregate_score_peaks(pbp(),schedule()))


@pytest.mark.parametrize('bad',['missing','score','clock','rollback'])
def test_incomplete_or_inconsistent_source_fails(bad):
    p=pbp();s=schedule()
    if bad=='missing':p=p.drop(columns='sp')
    elif bad=='score':s.loc[0,'home_score']=24
    elif bad=='clock':p.loc[1,'game_seconds_remaining']=np.nan
    else:p.loc[2,'total_home_score']=6
    with pytest.raises(ValueError):m.aggregate_score_peaks(p,s)


def boxes_and_schedule():
    rows=[];s=[]
    for week in (1,2,3):
        gid=f'g{week}'
        s.append(dict(game_id=gid,season=2023,week=week,home_team='H',away_team='A',
            gameday=f'2023-09-{week+1:02d}',gametime='13:00',site=1.,result=7.,
            **{'home won':1.,'market WP':.6},spread_line=3.))
        for team,opp,lead,deficit in [('H','A',14.,3.),('A','H',3.,14.)]:
            r=dict(game_id=gid,season=2023,week=week,team=team,opponent=opp,
                   **{c:1. for c in m.COUNTS},max_lead=lead,max_deficit=deficit)
            r['net_yards']=r['net_pass_yards']+r['rush_yards'];r['plays']=60.
            rows.append(r)
    return pd.DataFrame(rows),pd.DataFrame(s)


def test_lagged_peaks_decay_shrink_and_exclude_current_future():
    box,s=boxes_and_schedule();f=m.lagged_features(box,s,8.)
    assert f.loc[0,'d__max_lead']==f.loc[0,'d__max_deficit']==0.
    assert np.isclose(f.loc[1,'d__max_lead'],11/5)
    assert np.isclose(f.loc[1,'d__max_deficit'],-11/5)
    w=2**(-1/8)
    assert np.isclose(f.loc[2,'d__max_lead'],11*(w+1)/(w+1+4))
    changed=box.copy();mask=changed.week.ge(2)
    changed.loc[mask & changed.team.eq('H'),['max_lead','max_deficit']]=[40,1]
    changed.loc[mask & changed.team.eq('A'),['max_lead','max_deficit']]=[1,40]
    ff=m.lagged_features(changed,s,8.)
    np.testing.assert_allclose(f.loc[:1,list(m.PEAK_FEATURES)],ff.loc[:1,list(m.PEAK_FEATURES)])
    assert not np.allclose(f.loc[2,list(m.PEAK_FEATURES)].astype(float),ff.loc[2,list(m.PEAK_FEATURES)].astype(float))
    # Changing final scores alone cannot affect the production peak inputs.
    altered=s.copy();altered['result']=99.
    fff=m.lagged_features(box,altered,8.)
    np.testing.assert_allclose(f[list(m.PEAK_FEATURES)],fff[list(m.PEAK_FEATURES)])


def test_missing_peak_boxes_cannot_silently_become_zero():
    box,s=boxes_and_schedule()
    with pytest.raises(ValueError,match='requires max_lead and max_deficit'):
        m.lagged_features(box.drop(columns=list(m.PEAK_COLUMNS)),s,8.)
    with pytest.raises(ValueError,match='both max_lead and max_deficit'):
        m.validate_boxes(box.drop(columns='max_deficit'))


def test_family_features_signature_and_display_labels():
    for fam in m.FEATURE_FAMILIES:
        names=m.feature_names(fam)
        assert set(m.PEAK_FEATURES)<=set(names) and m.MARGIN_FEATURE not in names
    assert m.REVISION=='boxscore-composite-v1.14'
    assert m.OUTPUT_NAME=='nfl_boxscore_output_v1_14'
    assert m.frozen_recipe_name(2026)=='frozen_recipe_2026_boxscore-composite-v1.14.json'
    sig,cfg=m.config_signature()
    assert cfg['score_peaks']['features']==list(m.PEAK_FEATURES)
    assert sig!='cfacc42e9143fdda8e2568cc4be208708ea6c086a9229fff08fb9421d42095fe'
    assert b.factor_label('d__max_lead')=='Largest lead'
    assert b.factor_label('d__max_deficit')=='Largest deficit'


def test_v114_excludes_only_separate_sack_rates():
    assert len(m.candidates())==24
    for family in m.FEATURE_FAMILIES:
        legacy=family.removesuffix('_nosacks')
        old=m.feature_names(legacy)
        new=m.feature_names(family)
        removed=[c for c in old if c.endswith('__sacks_taken_pct')]
        assert len(removed)==2 and len(old)==26 and len(new)==24
        assert new==[c for c in old if c not in removed]
        assert set(m.PEAK_FEATURES)<=set(new)
        assert 'd__avail__qb_delta' in new
        assert sum(c.endswith('__net_pass_yards_per_pass_play') for c in new)==2
        assert sum(c.endswith('__first_down_rate') for c in new)==2
    # Source sacks and legacy families retain their definitions and behavior.
    assert m.RATES_CORE['net_pass_yards_per_pass_play']==('net_pass_yards','pass_plays',1.)
    assert m.RATES_CORE['sacks_taken_pct']==('sacks_taken','pass_plays',100.)
    assert 'sacks_taken' in m.COUNTS
    sig,cfg=m.config_signature()
    assert cfg['regressor_exclusions']['families']==list(m.FEATURE_FAMILIES)
    assert set(cfg['regressor_exclusions']['features'])==set(m.NO_SACK_FEATURES)
    assert sig!='f60cc7a964979f3345f05bc7a2d1d5952e79ca5c991649da414443517209d920'


def test_finals_without_pbp_are_skipped_like_boxes_but_present_games_stay_strict():
    s=pd.concat([schedule(),pd.DataFrame([dict(game_id='nopbp',home_team='X',away_team='Y',
        result=3,home_score=10,away_score=7)])],ignore_index=True)
    with pytest.raises(ValueError,match='nopbp: score peaks missing PBP'):m.aggregate_score_peaks(pbp(),s)
    box=pd.DataFrame(dict(game_id=['g','g'],team=['H','A']))
    x=m.merge_score_peaks(box,pbp(),s).set_index('team')
    assert x.loc['H','max_lead']==10 and x.loc['A','max_deficit']==10
    # A game that has a box row but a broken scoring history still fails.
    bad=pbp();bad.loc[2,'total_home_score']=6
    with pytest.raises(ValueError,match='not monotone'):m.merge_score_peaks(box,bad,s)
    assert m.merge_score_peaks(box.iloc[:0],pbp(),s).empty
