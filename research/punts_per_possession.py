"""Simple punt-rate addition; see PUNTS_PER_POSSESSION.md.

python research/punts_per_possession.py --prepare --raw-dir work/pressure_raw
python research/punts_per_possession.py
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import pressure_margin as p

INPUT=p.ROOT/'research/punt_inputs'
OUTPUT=p.ROOT/'research/punt_results'
EXTRA=['offensive_punt_rate_diff','defensive_forced_punt_rate_diff']


def qualifying_possessions(raw,include_points=False):
    f=raw[raw.season_type.eq('REG') & raw.posteam.notna() & ~raw.play_type.eq('no_play')].copy()
    if not include_points:f=f[~f.two_point_attempt.eq(1)].copy()
    if 'play_deleted' in f:f=f[~f.play_deleted.eq(1)].copy()
    for col in ['posteam','defteam']:f[col]=p.normalize(f[col])
    f['fixed_drive']=f.fixed_drive.fillna(f.drive)
    if f.fixed_drive.isna().any():raise ValueError('Missing possession identifier')
    if f.defteam.isna().any():raise ValueError('Missing opposing team')
    scrim=(f.pass_attempt.eq(1)|f.sack.eq(1)|f.rush_attempt.eq(1)) & ~f.qb_kneel.eq(1) & ~f.qb_spike.eq(1)
    two=f.two_point_attempt.eq(1)
    f['qualifying']=((scrim|f.field_goal_attempt.eq(1)|f.punt_attempt.eq(1)) & ~two).astype(int)
    f['punts']=(f.punt_attempt.eq(1)&~two).astype(int)
    if include_points:
        f['td_team']=p.normalize(f.td_team)
        off_td=f.touchdown.eq(1)&f.td_team.eq(f.posteam)&~f.return_touchdown.eq(1)&~two
        f['points']=6*off_td+3*f.field_goal_result.eq('made')+f.extra_point_result.eq('good')+2*f.two_point_conv_result.eq('success')
    keys=['game_id','week','posteam','defteam','fixed_drive']
    agg=dict(qualifying=('qualifying','max'),punts=('punts','sum'))
    if include_points:agg['points']=('points','sum')
    possessions=f.groupby(keys,as_index=False).agg(**agg)
    possessions=possessions[possessions.qualifying.eq(1)].copy()
    possessions['possessions']=1
    return possessions


def team_games(raw,season):
    possessions=qualifying_possessions(raw)
    count_keys=['game_id','week','posteam','defteam']
    g=possessions.groupby(count_keys,as_index=False)[['punts','possessions']].sum()
    g=g.rename(columns={'posteam':'team','defteam':'opponent'})
    g['season']=season
    if g.empty or not g.groupby('game_id').size().eq(2).all():
        raise ValueError('A source game is missing a qualifying offense')
    other=g[['game_id','team','opponent','punts','possessions']].rename(columns={
        'team':'opponent','opponent':'team','punts':'forced_punts','possessions':'opponent_possessions'})
    g=g.merge(other,on=['game_id','team','opponent'],validate='one_to_one')
    audit=dict(season=season,games=int(g.game_id.nunique()),team_games=len(g),
               possessions=int(g.possessions.sum()),punt_attempts=int(g.punts.sum()),
               multi_punt_possessions=int(possessions.punts.gt(1).sum()),max_week=int(g.week.max()))
    return g,audit


def prepare(raw_dir):
    INPUT.mkdir(parents=True,exist_ok=True)
    parts=[];audit=[]
    cols=['game_id','season_type','week','posteam','defteam','play_type','play_deleted','fixed_drive','drive',
          'pass_attempt','sack','rush_attempt','qb_kneel','qb_spike','field_goal_attempt','punt_attempt','two_point_attempt']
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
        if hist.empty:raise ValueError('No earlier punt history')
        prior_punts=float(hist.punts.mean());prior_possessions=float(hist.possessions.mean())
        team={}
        for t in set(batch.home)|set(batch.away):
            h=hist[hist.team.eq(t)].sort_values(['season','week','game_id'])
            if h.empty:raise ValueError(f'No punt history for {t}')
            if (h[['possessions','opponent_possessions']]<=0).any().any():raise ValueError('Nonpositive possession count')
            age=np.arange(len(h)-1,-1,-1)
            w=np.exp2(-age/8)*.5**(season-h.season.to_numpy())
            offense=(w@h.punts+4*prior_punts)/(w@h.possessions+4*prior_possessions)
            defense=(w@h.forced_punts+4*prior_punts)/(w@h.opponent_possessions+4*prior_possessions)
            team[t]=(offense,defense,len(h))
        last=hist.sort_values(['season','week']).iloc[-1]
        for r in batch.itertuples():
            ho,hd,hn=team[r.home];ao,ad,an=team[r.away]
            rows.append(dict(game_id=r.game_id,lag_weeks=lag,source_max_season=int(last.season),source_max_week=int(last.week),
                             home_offensive_punt_rate=ho,away_offensive_punt_rate=ao,
                             home_defensive_forced_punt_rate=hd,away_defensive_forced_punt_rate=ad,
                             offensive_punt_rate_diff=ho-ao,defensive_forced_punt_rate_diff=hd-ad,
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
    p.run(frame_builder=lambda f,lag:profiles(f,g,lag),output=OUTPUT,extra_columns=EXTRA,feature_label='punts')
