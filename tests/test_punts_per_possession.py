"""Counting and chronology checks for the simple punt-rate research arm."""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

RESEARCH=Path(__file__).parents[1]/'research'
if str(RESEARCH) not in sys.path:sys.path.insert(0,str(RESEARCH))
import punts_per_possession as q


def raw_fixture():
    base=dict(game_id='g',season_type='REG',week=1,posteam='A',defteam='B',play_type='run',play_deleted=0,
              fixed_drive=1,drive=1,pass_attempt=0,sack=0,rush_attempt=1,qb_kneel=0,qb_spike=0,
              field_goal_attempt=0,punt_attempt=0,two_point_attempt=0)
    rows=[]
    def add(**kw):rows.append(dict(base,**kw))
    add();add(play_type='punt',rush_attempt=0,punt_attempt=1)
    # Clock-killing possession does not count.
    add(fixed_drive=2,drive=2,qb_kneel=1)
    # A turnover/failed-fourth-down possession still counts in the denominator.
    add(fixed_drive=3,drive=3)
    # A punt-only possession counts; a no-play punt and a try do not.
    add(fixed_drive=4,drive=4,play_type='punt',rush_attempt=0,punt_attempt=1)
    add(fixed_drive=5,drive=5,play_type='no_play',punt_attempt=1)
    add(fixed_drive=6,drive=6,two_point_attempt=1)
    add(posteam='B',defteam='A',fixed_drive=7,drive=7)
    return pd.DataFrame(rows)


def test_punts_and_possessions_counted_once_and_mirrored():
    g,a=q.team_games(raw_fixture(),2023)
    own=g[g.team.eq('A')].iloc[0];other=g[g.team.eq('B')].iloc[0]
    assert (own.punts,own.possessions)==(2,3)
    assert (other.punts,other.possessions)==(0,1)
    assert (other.forced_punts,other.opponent_possessions)==(2,3)
    assert (own.forced_punts,own.opponent_possessions)==(0,1)
    assert a['multi_punt_possessions']==0


def test_multiple_punts_in_same_possession_do_not_add_possessions():
    f=raw_fixture();f=pd.concat([f,f.iloc[[1]]],ignore_index=True)
    g,a=q.team_games(f,2023)
    assert g[g.team.eq('A')].iloc[0].punts==3
    assert g[g.team.eq('A')].iloc[0].possessions==3
    assert a['multi_punt_possessions']==1


def test_missing_possession_or_opponent_is_rejected():
    f=raw_fixture();f.loc[0,['fixed_drive','drive']]=np.nan
    with pytest.raises(ValueError,match='identifier'):q.team_games(f,2023)
    f=raw_fixture();f.loc[0,'defteam']=None
    with pytest.raises(ValueError,match='opposing'):q.team_games(f,2023)


def test_punt_features_ignore_labels_recent_and_future_sources_and_reverse_on_swap():
    rows=[]
    for season,week in [(2023,1),(2024,1),(2024,2),(2024,3)]:
        for t,opp,punts,forced in [('A','B',6,2),('B','A',2,6)]:
            rows.append(dict(game_id=f'{season}_{week}',season=season,week=week,team=t,opponent=opp,
                             punts=punts,possessions=10,forced_punts=forced,opponent_possessions=10))
    g=pd.DataFrame(rows)
    f=pd.DataFrame([dict(game_id='target',season=2024,week=3,home='A',away='B',result=0.)])
    a=q.profiles(f,g,2)
    g.loc[~q.p.eligible(g,2024,3,2),'punts']=999
    f['result']=99.
    b=q.profiles(f,g,2)
    np.testing.assert_array_equal(a[q.EXTRA],b[q.EXTRA])
    assert a.offensive_punt_rate_diff.iloc[0]>0
    assert a.defensive_forced_punt_rate_diff.iloc[0]<0
    f['home']='B';f['away']='A'
    c=q.profiles(f,g,2)
    np.testing.assert_allclose(a[q.EXTRA],-c[q.EXTRA])
    assert a.source_max_week.iloc[0]==1


def test_missing_team_and_zero_possession_counts_are_rejected():
    g,a=q.team_games(raw_fixture(),2023)
    f=pd.DataFrame([dict(game_id='target',season=2024,week=3,home='A',away='B')])
    with pytest.raises(ValueError,match='No punt history'):
        q.profiles(f,g[g.team.eq('A')],2)
    g.loc[g.team.eq('A'),'possessions']=0
    with pytest.raises(ValueError,match='Nonpositive'):
        q.profiles(f,g,2)
