"""Isolated points-per-possession for/allowed study; see POINTS_PER_POSSESSION.md."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import pressure_margin as p
import punts_per_possession as punts

INPUT=p.ROOT/'research/ppp_inputs'
OUTPUT=p.ROOT/'research/ppp_results'
EXTRA=['offensive_points_per_possession_diff','defensive_points_allowed_per_possession_diff']


def team_games(raw,season):
    possessions=punts.qualifying_possessions(raw,include_points=True)
    g=possessions.groupby(['game_id','week','posteam','defteam'],as_index=False)[['points','possessions']].sum()
    g=g.rename(columns={'posteam':'team','defteam':'opponent'});g['season']=season
    if g.empty or not g.groupby('game_id').size().eq(2).all():raise ValueError('Missing qualifying offense')
    other=g[['game_id','team','opponent','points','possessions']].rename(columns={
        'team':'opponent','opponent':'team','points':'points_allowed','possessions':'opponent_possessions'})
    g=g.merge(other,on=['game_id','team','opponent'],validate='one_to_one')
    audit=dict(season=season,games=int(g.game_id.nunique()),team_games=len(g),
               possessions=int(g.possessions.sum()),offensive_points=int(g.points.sum()),max_week=int(g.week.max()))
    return g,audit


def prepare(raw_dir):
    INPUT.mkdir(parents=True,exist_ok=True)
    parts=[];audit=[]
    cols=['game_id','season_type','week','posteam','defteam','play_type','play_deleted','fixed_drive','drive',
          'pass_attempt','sack','rush_attempt','qb_kneel','qb_spike','field_goal_attempt','punt_attempt','two_point_attempt',
          'touchdown','td_team','return_touchdown','field_goal_result','extra_point_result','two_point_conv_result']
    for season in range(2018,2027):
        path=raw_dir/f'play_by_play_{season}.csv.gz'
        raw=pd.read_csv(path,usecols=lambda c:c in cols,low_memory=False)
        g,a=team_games(raw,season);a['pbp_sha256']=p.sha(path)
        parts.append(g);audit.append(a)
    pd.concat(parts,ignore_index=True).sort_values(['season','week','game_id','team']).to_csv(
        INPUT/'team_games.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    (INPUT/'coverage.json').write_text(json.dumps(audit,indent=2)+'\n')


def profiles(f,g,lag):
    rows=[]
    for (season,week),batch in f.groupby(['season','week'],sort=True):
        hist=g[p.eligible(g,season,week,lag)]
        if hist.empty:raise ValueError('No earlier points-per-possession history')
        prior_points=float(hist.points.mean());prior_possessions=float(hist.possessions.mean())
        team={}
        for t in set(batch.home)|set(batch.away):
            h=hist[hist.team.eq(t)].sort_values(['season','week','game_id'])
            if h.empty:raise ValueError(f'No points-per-possession history for {t}')
            if (h[['possessions','opponent_possessions']]<=0).any().any():raise ValueError('Nonpositive possession count')
            age=np.arange(len(h)-1,-1,-1);w=np.exp2(-age/8)*.5**(season-h.season.to_numpy())
            offense=(w@h.points+4*prior_points)/(w@h.possessions+4*prior_possessions)
            defense=(w@h.points_allowed+4*prior_points)/(w@h.opponent_possessions+4*prior_possessions)
            team[t]=(offense,defense,len(h))
        last=hist.sort_values(['season','week']).iloc[-1]
        for r in batch.itertuples():
            ho,hd,hn=team[r.home];ao,ad,an=team[r.away]
            rows.append(dict(game_id=r.game_id,lag_weeks=lag,source_max_season=int(last.season),source_max_week=int(last.week),
                             home_offensive_points_per_possession=ho,away_offensive_points_per_possession=ao,
                             home_defensive_points_allowed_per_possession=hd,away_defensive_points_allowed_per_possession=ad,
                             offensive_points_per_possession_diff=ho-ao,defensive_points_allowed_per_possession_diff=hd-ad,
                             home_history_n=hn,away_history_n=an))
    return f.merge(pd.DataFrame(rows),on='game_id',validate='one_to_one')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--raw-dir',type=Path)
    args=parser.parse_args()
    if args.prepare:
        if args.raw_dir is None:parser.error('--prepare requires --raw-dir')
        prepare(args.raw_dir)
    g=pd.read_csv(INPUT/'team_games.csv.gz')
    p.run(frame_builder=lambda f,lag:profiles(f,g,lag),output=OUTPUT,extra_columns=EXTRA,feature_label='ppp')
