"""Separate scoring-opportunity research arm; see SCORING_FINISHING.md."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

import pressure_margin as p

INPUT = p.ROOT/'research/scoring_inputs'
OUTPUT = p.ROOT/'research/scoring_finishing_results'
RATES = {'points_per_drive':('points','drives'), 'redzone_above_expected':('rz_excess','rz_trips'),
         'fourth_go_above_expected':('go_excess','fourth_opportunities'),
         'fourth_conversion_above_expected':('conversion_excess','fourth_attempts')}
COUNTS = list(dict.fromkeys(c for pair in RATES.values() for c in pair))
EXTRA = [f'd__{role}__{name}' for role in ['offense','defense'] for name in RATES]


def distance_bin(s):
    return pd.cut(s,[0,1,2,4,7,np.inf],labels=False,include_lowest=True).fillna(4).astype(int)


def expected(events, prior, keys, target):
    """Earlier-season, smoothed context rate; current-event outcomes are never read."""
    if prior.empty:
        raise ValueError('No earlier expectation history')
    rate = float(prior[target].mean())
    stats = prior.groupby(keys)[target].agg(['sum','count'])
    idx = pd.MultiIndex.from_frame(events[keys]) if len(keys)>1 else pd.Index(events[keys[0]])
    values = stats.reindex(idx)
    return ((values['sum'].fillna(0).to_numpy()+20*rate)/(values['count'].fillna(0).to_numpy()+20))


def events_for_season(raw):
    f=raw[raw.season_type.eq('REG') & raw.posteam.notna() & ~raw.play_type.eq('no_play')].copy()
    if 'play_deleted' in f:
        f=f[~f.play_deleted.eq(1)].copy()
    for c in ['posteam','defteam','td_team']:
        f[c]=p.normalize(f[c])
    f['fixed_drive']=f.fixed_drive.fillna(f.drive)
    if f.fixed_drive.isna().any():
        raise ValueError('A valid event lacks a drive identifier')
    f=f.sort_values(['game_id','play_id'])
    two=f.two_point_attempt.eq(1)
    scrim=(f.pass_attempt.eq(1)|f.sack.eq(1)|f.rush_attempt.eq(1)) & ~f.qb_kneel.eq(1) & ~f.qb_spike.eq(1) & ~two
    fg=f.field_goal_attempt.eq(1) & ~two
    f['qualifying']=(scrim|fg).astype(int)
    f['off_td']=(f.touchdown.eq(1)&f.td_team.eq(f.posteam)&~f.return_touchdown.eq(1)&~two).astype(int)
    f['points']=6*f.off_td+3*f.field_goal_result.eq('made')+f.extra_point_result.eq('good')+2*f.two_point_conv_result.eq('success')
    keys=['game_id','week','posteam','defteam','fixed_drive']
    drives=f.groupby(keys,as_index=False).agg(qualifying=('qualifying','sum'),points=('points','sum'),td=('off_td','max'))
    drives=drives[drives.qualifying.gt(0)].copy()
    drives['drives']=1
    rz=f[(scrim|fg)&f.yardline_100.le(20)].drop_duplicates(keys).copy()
    rz=rz[keys+['yardline_100','down','ydstogo']].merge(drives[keys+['td']],on=keys,validate='one_to_one')
    rz['entry_bin']=pd.cut(rz.yardline_100,[-1,5,10,20],labels=False).astype(int)
    rz['down_bin']=rz.down.fillna(1).astype(int)
    rz['distance_bin']=distance_bin(rz.ydstogo)
    fourth=f[f.down.eq(4)&(scrim|fg|f.punt_attempt.eq(1))].copy()
    fourth['go']=(fourth.pass_attempt.eq(1)|fourth.sack.eq(1)|fourth.rush_attempt.eq(1)).astype(int)
    fourth['converted']=(fourth.fourth_down_converted.eq(1)|fourth.off_td.eq(1)).astype(int)
    fourth['field_bin']=pd.cut(fourth.yardline_100,[-1,20,40,60,80,101],labels=False).fillna(2).astype(int)
    fourth['distance_bin']=distance_bin(fourth.ydstogo)
    fourth['trailing']=fourth.score_differential.lt(0).astype(int)
    fourth['late_close']=(fourth.qtr.eq(4)&fourth.quarter_seconds_remaining.le(300)&fourth.score_differential.abs().le(8)).astype(int)
    return drives,rz,fourth


def prepare(raw_dir):
    INPUT.mkdir(parents=True,exist_ok=True)
    all_drives=[];all_rz=[];all_fourth=[];audit=[]
    cols=['game_id','play_id','season_type','week','posteam','defteam','play_type','play_deleted',
          'fixed_drive','drive','pass_attempt','rush_attempt','sack','qb_kneel','qb_spike','two_point_attempt',
          'field_goal_attempt','field_goal_result','punt_attempt','touchdown','td_team','return_touchdown',
          'extra_point_result','two_point_conv_result','yardline_100','down','ydstogo',
          'fourth_down_converted','score_differential','qtr','quarter_seconds_remaining']
    for season in range(2018,2027):
        path=raw_dir/f'play_by_play_{season}.csv.gz'
        raw=pd.read_csv(path,usecols=lambda c:c in cols,low_memory=False)
        drives,rz,fourth=events_for_season(raw)
        for a in [drives,rz,fourth]:a['season']=season
        all_drives.append(drives);all_rz.append(rz);all_fourth.append(fourth)
        audit.append(dict(season=season,games=int(drives.game_id.nunique()),drives=len(drives),redzone_trips=len(rz),
                          fourth_opportunities=len(fourth),fourth_attempts=int(fourth.go.sum()),pbp_sha256=p.sha(path)))
    drives=pd.concat(all_drives,ignore_index=True);rz=pd.concat(all_rz,ignore_index=True);fourth=pd.concat(all_fourth,ignore_index=True)
    rz_keys=['entry_bin','down_bin','distance_bin']
    fourth_keys=['field_bin','distance_bin','trailing','late_close']
    parts=[]
    group=['game_id','season','week','posteam','defteam']
    for season in range(2019,2027):
        d=drives[drives.season.eq(season)].copy()
        z=rz[rz.season.eq(season)].copy();v=fourth[fourth.season.eq(season)].copy()
        z['rz_excess']=z.td.to_numpy()-expected(z,rz[rz.season.lt(season)],rz_keys,'td')
        z['rz_trips']=1
        v['go_excess']=v.go.to_numpy()-expected(v,fourth[fourth.season.lt(season)],fourth_keys,'go')
        v['fourth_opportunities']=1
        attempts=v[v.go.eq(1)].copy();prior=fourth[fourth.season.lt(season)&fourth.go.eq(1)]
        attempts['conversion_excess']=attempts.converted.to_numpy()-expected(attempts,prior,fourth_keys,'converted')
        attempts['fourth_attempts']=1
        frame=d.groupby(group,as_index=False)[['points','drives']].sum()
        for a,counts in [(z,['rz_excess','rz_trips']),(v,['go_excess','fourth_opportunities']),(attempts,['conversion_excess','fourth_attempts'])]:
            frame=frame.merge(a.groupby(group,as_index=False)[counts].sum(),on=group,how='left',validate='one_to_one')
            frame[counts]=frame[counts].fillna(0)
        frame=frame.rename(columns={'posteam':'team','defteam':'opponent'})
        if not frame.groupby('game_id').size().eq(2).all():
            raise ValueError('Qualifying drives missing one offense')
        defense=frame[['game_id','team','opponent',*COUNTS]].rename(columns={'team':'opponent','opponent':'team',**{c:'opp_'+c for c in COUNTS}})
        frame=frame.merge(defense,on=['game_id','team','opponent'],validate='one_to_one')
        parts.append(frame)
    pd.concat(parts,ignore_index=True).to_csv(INPUT/'team_games.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    (INPUT/'coverage.json').write_text(json.dumps(audit,indent=2)+'\n')


def profiles(f,g,lag):
    rows=[]
    for (season,week),batch in f.groupby(['season','week'],sort=True):
        hist=g[p.eligible(g,season,week,lag)]
        if hist.empty:raise ValueError('No earlier scoring history')
        league={c:float(hist[c].mean()) for c in COUNTS}
        team={}
        for t in set(batch.home)|set(batch.away):
            h=hist[hist.team.eq(t)].sort_values(['season','week','game_id'])
            if h.empty:raise ValueError(f'No scoring history for {t}')
            age=np.arange(len(h)-1,-1,-1)
            w=np.exp2(-age/8)*.5**(season-h.season.to_numpy())
            rates={}
            for role,pre in [('offense',''),('defense','opp_')]:
                for name,(num,den) in RATES.items():
                    rates[role,name]=(w@h[pre+num]+4*league[num])/(w@h[pre+den]+4*league[den])
            team[t]=rates
        last=hist.sort_values(['season','week']).iloc[-1]
        for r in batch.itertuples():
            out=dict(game_id=r.game_id,lag_weeks=lag,source_max_season=int(last.season),source_max_week=int(last.week))
            for role in ['offense','defense']:
                for name in RATES:
                    out[f'home__{role}__{name}']=team[r.home][role,name]
                    out[f'away__{role}__{name}']=team[r.away][role,name]
                    out[f'd__{role}__{name}']=team[r.home][role,name]-team[r.away][role,name]
            rows.append(out)
    return f.merge(pd.DataFrame(rows),on='game_id',validate='one_to_one')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',action='store_true');parser.add_argument('--raw-dir',type=Path)
    args=parser.parse_args()
    if args.prepare:
        if args.raw_dir is None:parser.error('--prepare requires --raw-dir')
        prepare(args.raw_dir)
    g=pd.read_csv(INPUT/'team_games.csv.gz')
    p.run(frame_builder=lambda f,lag:profiles(f,g,lag),output=OUTPUT,extra_columns=EXTRA,feature_label='scoring')
