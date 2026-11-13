"""Leakage and football-accounting checks for the isolated finishing study."""
import importlib.util
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RESEARCH=Path(__file__).parents[1]/'research'
if str(RESEARCH) not in sys.path:sys.path.insert(0,str(RESEARCH))
import scoring_finishing as s


def test_expected_rate_uses_prior_labels_not_current_labels():
    prior=pd.DataFrame(dict(context=[0,0,1],outcome=[1,0,1]))
    target=pd.DataFrame(dict(context=[0,1,2],outcome=[0,0,0]))
    a=s.expected(target,prior,['context'],'outcome')
    target['outcome']=999
    np.testing.assert_array_equal(a,s.expected(target,prior,['context'],'outcome'))
    assert a[2]==pytest.approx(2/3)
    assert a[0]==pytest.approx((1+20*2/3)/22)


def test_drive_counting_excludes_kneels_and_defensive_touchdowns():
    base=dict(game_id='g',season_type='REG',week=1,posteam='A',defteam='B',play_type='run',play_deleted=0,
              drive=1,fixed_drive=1,pass_attempt=0,rush_attempt=1,sack=0,qb_kneel=0,qb_spike=0,
              two_point_attempt=0,field_goal_attempt=0,field_goal_result=None,punt_attempt=0,
              touchdown=0,td_team=None,return_touchdown=0,extra_point_result=None,two_point_conv_result=None,
              yardline_100=5,down=1,ydstogo=5,fourth_down_converted=0,score_differential=0,qtr=1,quarter_seconds_remaining=500)
    rows=[]
    def add(play_id,**kw):rows.append(dict(base,play_id=play_id,**kw))
    # Three plays, one drive, seven offensive points, one red-zone trip.
    add(1);add(2,touchdown=1,td_team='A');add(3,play_type='extra_point',rush_attempt=0,extra_point_result='good')
    # Kneel-only drive must not count.
    add(4,fixed_drive=2,drive=2,qb_kneel=1)
    # Opposing defensive TD must not count as offensive points.
    add(5,fixed_drive=3,drive=3,touchdown=1,td_team='B',return_touchdown=1,yardline_100=70)
    # Failed fourth-down pass is an attempt and opportunity, no conversion.
    add(6,fixed_drive=4,drive=4,play_type='pass',rush_attempt=0,pass_attempt=1,down=4,ydstogo=2,yardline_100=40)
    drives,rz,fourth=s.events_for_season(pd.DataFrame(rows))
    assert len(drives)==3
    assert drives.points.sum()==7
    assert len(rz)==1 and rz.td.sum()==1
    assert len(fourth)==1 and fourth.go.sum()==1 and fourth.converted.sum()==0


def test_scoring_profiles_ignore_future_and_reverse_on_team_swap():
    rows=[]
    for season,week in [(2023,1),(2024,1),(2024,2),(2024,3)]:
        for t,opp,points in [('A','B',21),('B','A',14)]:
            a=dict(game_id=f'{season}_{week}',season=season,week=week,team=t,opponent=opp,
                   points=points,drives=10,rz_excess=.2,rz_trips=3,go_excess=.1,fourth_opportunities=4,
                   conversion_excess=-.1,fourth_attempts=1)
            for c in s.COUNTS:a['opp_'+c]=a[c]
            rows.append(a)
    g=pd.DataFrame(rows)
    f=pd.DataFrame([dict(game_id='target',season=2024,week=3,home='A',away='B',result=7.)])
    a=s.profiles(f,g,2)
    g.loc[~s.p.eligible(g,2024,3,2),'points']=999
    b=s.profiles(f,g,2)
    pd.testing.assert_frame_equal(a,b)
    f['home']='B';f['away']='A'
    c=s.profiles(f,g,2)
    np.testing.assert_allclose(a[s.EXTRA],-c[s.EXTRA])
