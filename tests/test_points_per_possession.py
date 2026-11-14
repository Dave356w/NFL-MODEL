"""Offensive scoring accounting and chronology for the isolated PPP study."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RESEARCH=Path(__file__).parents[1]/'research'
if str(RESEARCH) not in sys.path:sys.path.insert(0,str(RESEARCH))
import points_per_possession as q


def raw_fixture():
    base=dict(game_id='g',season_type='REG',week=1,posteam='A',defteam='B',play_type='pass',play_deleted=0,
              fixed_drive=1,drive=1,pass_attempt=1,sack=0,rush_attempt=0,qb_kneel=0,qb_spike=0,
              field_goal_attempt=0,punt_attempt=0,two_point_attempt=0,touchdown=0,td_team=None,return_touchdown=0,
              field_goal_result=None,extra_point_result=None,two_point_conv_result=None)
    rows=[]
    def add(**kw):rows.append(dict(base,**kw))
    add(touchdown=1,td_team='A')
    add(play_type='extra_point',pass_attempt=0,extra_point_result='good')
    add(fixed_drive=3,drive=3,play_type='field_goal',pass_attempt=0,field_goal_attempt=1,field_goal_result='made')
    add(fixed_drive=5,drive=5,play_type='run',pass_attempt=0,rush_attempt=1,qb_kneel=1)
    add(posteam='B',defteam='A',fixed_drive=2,drive=2,touchdown=1,td_team='B')
    add(posteam='B',defteam='A',fixed_drive=2,drive=2,two_point_attempt=1,two_point_conv_result='success')
    # Defensive return TD plus PAT is not offensive drive production for A.
    add(posteam='B',defteam='A',fixed_drive=4,drive=4,touchdown=1,td_team='A',return_touchdown=1)
    add(fixed_drive=4,drive=4,play_type='extra_point',pass_attempt=0,extra_point_result='good')
    return pd.DataFrame(rows)


def test_points_for_allowed_and_possessions_mirror_without_nonoffensive_scores():
    g,a=q.team_games(raw_fixture(),2023)
    own=g[g.team.eq('A')].iloc[0];other=g[g.team.eq('B')].iloc[0]
    assert (own.points,own.possessions,own.points_allowed,own.opponent_possessions)==(10,2,8,2)
    assert (other.points,other.possessions,other.points_allowed,other.opponent_possessions)==(8,2,10,2)
    assert a['offensive_points']==18


def test_points_and_punt_study_use_identical_qualifying_possessions():
    raw=raw_fixture()
    a=q.punts.qualifying_possessions(raw,include_points=False)
    b=q.punts.qualifying_possessions(raw,include_points=True)
    cols=['game_id','posteam','defteam','fixed_drive','possessions']
    pd.testing.assert_frame_equal(a[cols].reset_index(drop=True),b[cols].reset_index(drop=True))


def test_profiles_ignore_current_future_labels_and_reverse_on_swap():
    rows=[]
    for season,week in [(2023,1),(2024,1),(2024,2),(2024,3)]:
        for t,opp,points,allowed in [('A','B',30,10),('B','A',10,30)]:
            rows.append(dict(game_id=f'{season}_{week}',season=season,week=week,team=t,opponent=opp,
                             points=points,possessions=10,points_allowed=allowed,opponent_possessions=10))
    g=pd.DataFrame(rows);f=pd.DataFrame([dict(game_id='target',season=2024,week=3,home='A',away='B',result=0.)])
    a=q.profiles(f,g,2)
    g.loc[~q.p.eligible(g,2024,3,2),'points']=999;f['result']=100.
    b=q.profiles(f,g,2)
    np.testing.assert_array_equal(a[q.EXTRA],b[q.EXTRA])
    assert a.offensive_points_per_possession_diff.iloc[0]>0
    assert a.defensive_points_allowed_per_possession_diff.iloc[0]<0
    f['home']='B';f['away']='A'
    c=q.profiles(f,g,2)
    np.testing.assert_allclose(a[q.EXTRA],-c[q.EXTRA])
    assert a.source_max_week.iloc[0]==1


def test_missing_team_and_nonpositive_possessions_rejected():
    g,a=q.team_games(raw_fixture(),2023)
    f=pd.DataFrame([dict(game_id='target',season=2024,week=3,home='A',away='B')])
    with pytest.raises(ValueError,match='No points-per-possession history'):
        q.profiles(f,g[g.team.eq('A')],2)
    g.loc[g.team.eq('A'),'possessions']=0
    with pytest.raises(ValueError,match='Nonpositive'):q.profiles(f,g,2)
