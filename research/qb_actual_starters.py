"""Outcome-only QB labels from actual play order and same-week roster position.

Never use this game's label to build its own pregame forecast. Schedule QB fields
may retain projected starters and are not accepted as outcome evidence.
"""
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
ORDER=ROOT/'research/qb_saved_pick_audit_inputs/qb_play_order.csv'


def actual_starters(order):
    rows=[]
    for (game,team),g in order.groupby(['game_id','team'],sort=False):
        g=g.copy()
        def position_state(value):
            if pd.isna(value): return 'unknown'
            parts={p.strip().upper() for p in str(value).split('|') if p.strip()}
            if not parts or 'UNKNOWN' in parts: return 'unknown'
            if parts=={'QB'}: return 'QB'
            return 'unknown' if 'QB' in parts else 'other'
        g['_position']=g.position.map(position_state)
        g['_order']=pd.to_numeric(g.first_dropback_id,errors='coerce')
        q=g[g._position.eq('QB')].sort_values('_order')
        unknown=g[g._position.eq('unknown')]
        reason='first actual QB-position passer'
        pid=None;name=None;first=np.nan
        if q.empty:reason='unresolved: no positively identified QB'
        elif g.loc[g._position.ne('other'),'_order'].isna().any():
            reason='unresolved: missing QB or unknown-passer play order'
        else:
            first=q._order.min(); candidates=q[q._order.eq(first)]
            if len(candidates)!=1:reason='unresolved: tied QB play order'
            elif len(unknown) and unknown._order.min()<=first:reason='unresolved: earlier passer position unknown'
            else:pid=candidates.gsis_id.iloc[0];name=candidates.name.iloc[0]
        row=g.iloc[0]
        rows.append(dict(game_id=game,team=team,season=int(row.season),week=int(row.week),
                         actual_id=pid,actual_qb=name,actual_first_dropback_id=first,actual_source=reason))
    return pd.DataFrame(rows)


def corrected_schedules(schedules,order=None):
    order=pd.read_csv(ORDER) if order is None else order
    labels=actual_starters(order).set_index(['game_id','team'])
    out=schedules.copy()
    for side in ('home','away'):
        out['schedule_'+side+'_qb_id']=out[side+'_qb_id']
        for i,r in out[out.result.notna()].iterrows():
            key=(r.game_id,r[side+'_team'])
            if key in labels.index:
                lab=labels.loc[key]
                out.loc[i,side+'_qb_id']=lab.actual_id
                out.loc[i,side+'_qb_name']=lab.actual_qb
                out.loc[i,side+'_actual_source']=lab.actual_source
            else:
                out.loc[i,side+'_qb_id']=None;out.loc[i,side+'_qb_name']=None
                out.loc[i,side+'_actual_source']='unresolved: no play-order coverage'
    return out
