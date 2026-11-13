"""Owner-authorized replacement-starter margin overlay (2026-11-13).

This is an ATS margin policy, separate from the fitted QB efficiency term. The
projected passer is a replacement when he differs from a still-rostered QB with
at least two actual starts earlier in this season and the most prior starts
(latest start breaks ties). Current/future game outcomes never enter the flag.
"""
import re

import numpy as np
import pandas as pd

POLICY='replacement-team-margin-minus2-2026-11-13-v1'
PENALTY_POINTS=2.
BASE_MARGIN='qb_replacement_base_margin'
ADJUSTMENT='qb_replacement_margin_adjustment'
POLICY_FIELD='qb_replacement_policy'

AVAILABILITY_COLUMNS=('qb_replacement','qb_replacement_status','qb_projected_id',
    'qb_incumbent_id','qb_incumbent_starts','qb_incumbent_last_week',
    'qb_replacement_reference_week',POLICY_FIELD)
META_COLUMNS=AVAILABILITY_COLUMNS


def _present(value):
    return value is not None and pd.notna(value) and str(value).strip()!=''


def _normal(value):
    text=str(value).lower().strip()
    text=re.sub(r'\s+(?:jr\.?|sr\.?|ii|iii|iv|v)$','',text)
    return re.sub('[^a-z0-9]','',text)


def _aliases(value):
    if not _present(value): return set()
    text=re.sub(r'\s+(?:jr\.?|sr\.?|ii|iii|iv|v)$','',str(value).strip(),flags=re.I)
    pieces=text.split()
    out={_normal(text)}
    if len(pieces)>1: out.add(_normal(pieces[0][0]+'.'+' '.join(pieces[1:])))
    return out-{''}


def _true(value):
    return value is True or isinstance(value,(bool,np.bool_)) and bool(value) or str(value).lower() in ('true','1')


def _projected_id(row,history,reference):
    """Resolve identities from only pregame passer/roster names.

    A caller-provided gsis ID is the resolved model identity, including sourced
    game eligibility corrections; the model's separate eligibility gate remains
    authoritative. Name-only legacy records must resolve without guessing.
    """
    name=row.get('qb_expected')
    if not _present(name): return None,'projected quarterback missing'
    if ' (Q) / ' in str(name): return None,'questionable quarterback blend'
    for col in ('qb_projected_id','qb_expected_id'):
        if _present(row.get(col)): return str(row[col]),None
    names={}
    def add(pid,nm):
        if not _present(pid): return
        for alias in _aliases(nm): names.setdefault(alias,set()).add(str(pid))
    if history is not None and len(history):
        for r in history.itertuples(index=False): add(r.gsis_id,getattr(r,'name',None))
    if reference is not None:
        for r in reference.itertuples(index=False):
            if str(r.position).upper()!='QB': continue
            for col in ('full_name','football_name','name'):
                add(r.gsis_id,getattr(r,col,None))
            first,last=getattr(r,'first_name',None),getattr(r,'last_name',None)
            if _present(first) and _present(last): add(r.gsis_id,str(first)+' '+str(last))
    matches=names.get(_normal(name),set())
    if len(matches)>1 and reference is not None:
        roster_qbs=set(reference.loc[reference.position.astype(str).str.upper().eq('QB'),'gsis_id'].astype(str))
        matches=matches&roster_qbs
    return (next(iter(matches)),None) if len(matches)==1 else (None,'projected quarterback identity unresolved')


def annotate_availability(availability,qb,roster):
    """Annotate team projections without changing any fitted availability input.

    `qb.starter` must identify the actual first QB-position passer of completed
    games, as produced by nfl_model.label_qb_starters. Only earlier weeks in the
    target season count. Week-one roster rows are usable for name resolution;
    later games use the most recent roster strictly before the target week.
    Injury/reserve status does not remove an incumbent's roster membership.
    """
    out=availability.copy()
    q=pd.DataFrame() if qb is None else qb.copy()
    rost=pd.DataFrame() if roster is None else roster.copy()
    required={'season','week','team','gsis_id','starter','game_id'}
    history_ok=required.issubset(q.columns)
    roster_ok={'season','week','team','gsis_id','position'}.issubset(rost.columns)
    roster_groups={key:g for key,g in rost.groupby(['season','week','team'])} if roster_ok else {}
    roster_weeks={}
    for y,w,t in roster_groups: roster_weeks.setdefault((int(y),t),[]).append(int(w))
    records=[]
    for row in out.to_dict('records'):
        y,w,t=int(row['season']),int(row['week']),row['team']
        earlier=[rw for rw in roster_weeks.get((y,t),()) if rw<w or w==1 and rw==1]
        rw=max(earlier) if earlier else None
        ref=roster_groups.get((y,rw,t)) if rw is not None else None
        before=q[(q.season<y)|((q.season==y)&(q.week<w))] if history_ok else pd.DataFrame()
        pid,why=_projected_id(row,before,ref)
        rec=dict(qb_replacement=np.nan,qb_replacement_status=why,
            qb_projected_id=pid,qb_incumbent_id=None,qb_incumbent_starts=0,
            qb_incumbent_last_week=np.nan,qb_replacement_reference_week=rw,
            qb_replacement_policy=POLICY)
        if why is not None:
            records.append(rec);continue
        if not history_ok:
            rec['qb_replacement_status']='starting-quarterback history unavailable'
            records.append(rec);continue
        past=before[before.season.eq(y)&before.team.eq(t)]
        if past.empty and w>1:
            rec['qb_replacement_status']='earlier team quarterback history unavailable'
            records.append(rec);continue
        starts=past[past.starter.map(_true)].copy()
        # Incomplete actual labels could change the incumbent ranking. Do not
        # silently count the dropback leader as a substitute for those labels.
        if len(past):
            per_game=starts.groupby('game_id').gsis_id.nunique()
            if len(per_game)!=past.game_id.nunique() or not per_game.eq(1).all():
                rec['qb_replacement_status']='earlier actual quarterback labels unresolved'
                records.append(rec);continue
        counts=starts.groupby('gsis_id').agg(n=('game_id','nunique'),last_week=('week','max'))
        if counts.empty or counts.n.max()<2:
            rec.update(qb_replacement=0.,qb_replacement_status='no established incumbent')
            records.append(rec);continue
        counts=counts.assign(_id=counts.index.astype(str)).sort_values(['n','last_week','_id'],ascending=[False,False,True])
        inc=counts.index[0]
        rec.update(qb_incumbent_id=str(inc),qb_incumbent_starts=int(counts.n.iloc[0]),
                   qb_incumbent_last_week=int(counts.last_week.iloc[0]))
        if ref is None:
            rec['qb_replacement_status']='earlier reference roster unavailable'
            records.append(rec);continue
        incumbent_positions=set(ref.loc[ref.gsis_id.astype(str).eq(str(inc)),'position'].dropna().astype(str).str.upper())
        if 'QB' in incumbent_positions and incumbent_positions!={'QB'}:
            rec['qb_replacement_status']='incumbent roster position conflicting'
            records.append(rec);continue
        if incumbent_positions!={'QB'}:
            rec.update(qb_replacement=0.,qb_replacement_status='incumbent no longer rostered at quarterback')
        else:
            flag=float(str(pid)!=str(inc))
            rec.update(qb_replacement=flag,qb_replacement_status='replacement starter' if flag else 'incumbent starter')
        records.append(rec)
    ann=pd.DataFrame(records,index=out.index,columns=AVAILABILITY_COLUMNS)
    for col in AVAILABILITY_COLUMNS: out[col]=ann[col]
    return out


def overlay(frame,margin_column='fixed_band_spread'):
    """Apply the final-margin policy exactly once, preserving its original base.

    Missing either flag retains the original margin and records unresolved
    classification. Two replacements cancel. A repeated call uses the saved
    base, so changed flags can be rescored without compounding the penalty.
    """
    out=frame.copy()
    base=pd.to_numeric(out[margin_column],errors='coerce')
    policy=out.get(POLICY_FIELD,pd.Series(None,index=out.index,dtype=object))
    has=policy.notna()&policy.astype(str).ne('')
    if (has&policy.ne(POLICY)).any(): raise ValueError('unknown replacement margin policy')
    marked=policy.eq(POLICY)
    if marked.any():
        old=pd.to_numeric(out.get(BASE_MARGIN,pd.Series(np.nan,index=out.index)),errors='coerce')
        if (marked&base.notna()&old.isna()).any(): raise ValueError('replacement overlay is missing its original base margin')
        base=base.where(~marked,old)
    flags=[]
    for side in ('home','away'):
        f=pd.to_numeric(out.get(side+'_qb_replacement',pd.Series(np.nan,index=out.index)),errors='coerce')
        if (~f.isna()&~f.isin([0.,1.])).any(): raise ValueError('replacement flag must be zero, one or missing')
        flags.append(f)
    home,away=flags;known=home.notna()&away.notna()
    adjustment=(-PENALTY_POINTS*home+PENALTY_POINTS*away).where(known,0.)
    out[BASE_MARGIN]=base
    out[ADJUSTMENT]=adjustment
    out[POLICY_FIELD]=POLICY
    out['qb_replacement_applied']=known&base.notna()
    out['qb_replacement_overlay_status']=np.where(known,'classified','unresolved; original margin retained')
    out[margin_column]=base+adjustment
    return out


apply_margin=overlay
