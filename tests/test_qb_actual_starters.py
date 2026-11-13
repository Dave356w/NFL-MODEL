"""Outcome labels use actual quarterback play order, never stale schedule IDs."""
import numpy as np
import pandas as pd
import pytest

import nfl_model as m
from research.qb_actual_starters import actual_starters, corrected_schedules, ORDER


def order_fixture():
    return pd.DataFrame([
        dict(game_id='g',season=2026,week=7,team='H',gsis_id='gadget',name='Gadget RB',
             first_dropback_id=1.,position='RB',dropbacks=1),
        dict(game_id='g',season=2026,week=7,team='H',gsis_id='starter',name='True starter',
             first_dropback_id=2.,position='QB',dropbacks=2),
        dict(game_id='g',season=2026,week=7,team='H',gsis_id='replacement',name='Replacement',
             first_dropback_id=3.,position='QB',dropbacks=40),
        dict(game_id='g',season=2026,week=7,team='A',gsis_id='away',name='Away QB',
             first_dropback_id=9.,position='QB',dropbacks=30),
    ])


def test_stale_schedule_is_replaced_by_actual_first_qb_after_gadget_opener():
    order=order_fixture()
    schedules=pd.DataFrame([
        dict(game_id='g',home_team='H',away_team='A',home_qb_id='stale-home',
             home_qb_name='Stale home',away_qb_id='stale-away',away_qb_name='Stale away',result=-3.),
        dict(game_id='pending',home_team='H',away_team='A',home_qb_id='future-home',
             home_qb_name='Future home',away_qb_id='future-away',away_qb_name='Future away',result=np.nan),
    ])
    out=corrected_schedules(schedules,order).set_index('game_id')
    assert out.loc['g','home_qb_id']=='starter'
    assert out.loc['g','home_qb_name']=='True starter'
    assert out.loc['g','away_qb_id']=='away'
    assert out.loc['g','schedule_home_qb_id']=='stale-home'
    assert out.loc['g','home_actual_source']=='first actual QB-position passer'
    # A pending game's schedule projection never becomes an outcome label.
    assert out.loc['pending','home_qb_id']=='future-home'
    assert schedules.loc[0,'home_qb_id']=='stale-home'


def test_early_injury_starter_is_not_replaced_by_dropback_leader():
    out=actual_starters(order_fixture()).set_index('team')
    assert out.loc['H','actual_id']=='starter'
    assert out.loc['H','actual_first_dropback_id']==2.


@pytest.mark.parametrize('position',['unknown','QB|RB',None,np.nan,'','  '])
def test_missing_or_conflicting_position_before_first_qb_remains_unknown(position):
    order=order_fixture()
    order.loc[order.gsis_id.eq('gadget'),'position']=position
    row=actual_starters(order).set_index('team').loc['H']
    assert pd.isna(row.actual_id)
    assert 'unresolved' in row.actual_source


@pytest.mark.parametrize('pid',['starter','replacement'])
def test_missing_qb_play_order_cannot_pick_another_qb(pid):
    order=order_fixture()
    order.loc[order.gsis_id.eq(pid),'first_dropback_id']=np.nan
    row=actual_starters(order).set_index('team').loc['H']
    assert pd.isna(row.actual_id)
    assert 'missing' in row.actual_source


def test_unknown_passer_with_missing_order_cannot_be_assumed_late():
    order=order_fixture()
    mask=order.gsis_id.eq('gadget')
    order.loc[mask,'position']='unknown'
    order.loc[mask,'first_dropback_id']=np.nan
    assert pd.isna(actual_starters(order).set_index('team').loc['H','actual_id'])


def test_unknown_after_first_qb_does_not_erase_observed_starter():
    order=order_fixture()
    order.loc[order.gsis_id.eq('replacement'),'position']='unknown'
    assert actual_starters(order).set_index('team').loc['H','actual_id']=='starter'


def test_absent_game_coverage_and_tied_order_are_not_schedule_fallbacks():
    order=order_fixture();order.loc[order.gsis_id.eq('replacement'),'first_dropback_id']=2.
    schedule=pd.DataFrame([dict(game_id='g',home_team='H',away_team='missing',
        home_qb_id='stale-home',home_qb_name='Stale home',away_qb_id='stale-away',
        away_qb_name='Stale away',result=3.)])
    out=corrected_schedules(schedule,order).iloc[0]
    assert pd.isna(out.home_qb_id) and pd.isna(out.away_qb_id)
    assert 'tied' in out.home_actual_source
    assert out.away_actual_source=='unresolved: no play-order coverage'


def test_research_and_production_agree_on_actual_passer_sample():
    # These samples include the known stale Hurts schedule row, gadget-opening
    # Baltimore game, and multiple actual replacements from the saved-pick audit.
    games=['2026_07_DAL_PHI','2026_09_JAX_BAL','2026_03_SEA_WAS','2025_16_NYJ_NO']
    order=pd.read_csv(ORDER)
    sample=order[order.game_id.isin(games)].copy()
    assert set(sample.game_id)==set(games)
    # Expand the annotated positions into the same weekly roster contract that
    # production consumes; contradictory annotations remain separate positions.
    positions=sample[['season','week','team','gsis_id','position']].copy()
    positions['position']=positions.position.str.split('|',regex=False)
    roster=positions.explode('position')
    production=m.label_qb_starters(sample.drop(columns='position'),roster)
    prod=production[production.starter].set_index(['game_id','team']).gsis_id.to_dict()
    research=actual_starters(sample).set_index(['game_id','team']).actual_id.to_dict()
    assert research==prod
    assert research[('2026_07_DAL_PHI','PHI')]=='00-0038400'  # Tanner McKee, not stale Hurts
    assert research[('2026_09_JAX_BAL','BAL')]=='00-0040981'  # Joe Fagnano, not gadget Henry
