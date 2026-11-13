"""Freeze eligible saved injury inputs; never edit the original journals."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import nfl_model as m

INPUT=ROOT/'research/injury_weight_inputs'
GROUPS=['OL','WRTE','RB','DL','LB','DB']
FEATURES=['inj_'+g for g in GROUPS]+['qb_delta']
VECTOR_NAMES=[f'd__avail__{g}_out_cs' for g in GROUPS]+['d__avail__qb_delta']
STATUS={'Out':1.,'Doubtful':1.,'Questionable':.25,'Available':0.}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()] if Path(path).exists() else []


def aware_time(value):
    if not value:return None
    try:
        t=pd.Timestamp(value)
        return t if t.tzinfo is not None and not pd.isna(t) else None
    except (ValueError,TypeError):return None


def choose_vector(records,game,cutoff):
    eligible=[]
    for r in records:
        if r.get('game_id')!=game:continue
        t=aware_time(r.get('generated_utc'))
        inputs=r.get('model_inputs',{})
        if t is None or t>cutoff or not all(k in inputs for k in VECTOR_NAMES):continue
        values=np.asarray([inputs[k] for k in VECTOR_NAMES],float)
        if np.isfinite(values).all():eligible.append(r)
    return max(eligible,key=lambda r:(aware_time(r['generated_utc']),r['revision'])) if eligible else None


def choose_report(records,game,team,cutoff):
    eligible=[]
    for r in records:
        if (r.get('game_id'),r.get('team'),r.get('kind'))!=(game,team,'official_injury_report'):continue
        captured=aware_time(r.get('captured_utc'));published=aware_time(r.get('source_published_utc'))
        if captured is None or captured>cutoff or (published is not None and published>cutoff):continue
        if r.get('source_published_utc') and published is None:continue
        eligible.append(r)
    if not eligible:return None
    latest=max(eligible,key=lambda r:(aware_time(r['captured_utc']),r['source_capture_sha256']))
    parsed=latest.get('parsed',{})
    # A later incomplete/failed report must block, not silently fall back to an
    # older complete report which may omit a new injury designation.
    if not parsed.get('complete') or parsed.get('issues') or not isinstance(parsed.get('rows'),list):return None
    if any(x.get('status') not in STATUS or (STATUS[x['status']]>0 and not x.get('gsis_id')) for x in parsed['rows']):return None
    return latest


class SnapWindows:
    def __init__(self,snaps):
        s=snaps.copy();s['team']=s.team.replace({'LAR':'LA','STL':'LA','SD':'LAC','OAK':'LV'})
        s['unit']=s.position.map(m.POS_GROUP)
        self.teams={t:q for t,q in s.groupby('team')};self.cache={}

    def get(self,team,season,week):
        key=(team,int(season),int(week))
        if key in self.cache:return self.cache[key]
        if team not in self.teams:raise ValueError(f'No earlier snap source for {team}')
        s=self.teams[team]
        h=s[(s.season<season)|((s.season==season)&(s.week<week))]
        games=h[['season','week','game_id']].drop_duplicates().sort_values(['season','week','game_id'])
        current=games[games.season==season]
        use=(current if len(current)>=2 else games).tail(4)
        h=h[h.game_id.isin(use.game_id)].copy()
        h['role_snaps']=np.where(h.unit.isin(['OL','WRTE','RB']),h.offense_snaps,h.defense_snaps)
        counts=h[h.unit.isin(GROUPS)].groupby(['unit','gsis_id']).role_snaps.sum()
        denominator={u:float(counts.get(u,pd.Series(dtype=float)).sum()) for u in GROUPS}
        if any(n<=0 for n in denominator.values()):raise ValueError(f'Missing earlier positional snaps {key}')
        self.cache[key]=(counts,denominator)
        return self.cache[key]


def burden(windows,team,season,week,status_rows):
    counts,den=windows.get(team,season,week)
    severity={}
    for r in status_rows:
        if r.get('status') not in STATUS:continue
        pid=r.get('gsis_id')
        if pid:severity[pid]=max(severity.get(pid,0.),STATUS[r['status']])
    out={u:0. for u in GROUPS}
    known=set()
    for (unit,pid),n in counts.items():
        if pid in severity:
            out[unit]+=float(n)*severity[pid]/den[unit];known.add(pid)
    if any(v<0 or v>1+1e-10 for v in out.values()):raise ValueError('Invalid snap-weighted burden')
    unseen=sum(v>0 and pid not in known for pid,v in severity.items())
    return out,int(unseen)


def prepare():
    INPUT.mkdir(parents=True,exist_ok=True)
    paths=[ROOT/'data/forward_predictions.jsonl',ROOT/'data/availability_sources.jsonl',
           ROOT/'data/lock_runtime/2026_week10/availability_sources.jsonl']
    source_hash={str(p.relative_to(ROOT)):sha(p) for p in paths}
    vectors=read_jsonl(paths[0]);reports=read_jsonl(paths[1])+read_jsonl(paths[2])
    public=pd.read_csv(ROOT/'research/pressure_inputs/ats_2026_results.csv')
    public=public[public.ats_status.eq('graded')].copy()
    base=pd.read_csv(ROOT/'research/pressure_inputs/base_forecasts.csv')
    hist=base[base.season<2026].copy()
    pack=pd.read_csv(ROOT/'research/shrinkage_results/frozen_training_features.csv.gz')
    hv=hist.merge(pack[['game_id',*VECTOR_NAMES]],on='game_id',validate='one_to_one').rename(columns=dict(zip(VECTOR_NAMES,FEATURES)))
    if hv[FEATURES].isna().any().any():raise ValueError('Missing historical production injury input')
    snaps=pd.read_parquet(ROOT/'data/lock_inputs/snaps.parquet');windows=SnapWindows(snaps)
    injuries=pd.read_parquet(ROOT/'data/lock_inputs/inj.parquet')
    injury_map={(int(y),int(w),t):q[['gsis_id','report_status']].rename(columns={'report_status':'status'}).to_dict('records') for (y,w,t),q in injuries.groupby(['season','week','team'])}
    states=pd.read_parquet(ROOT/'data/lock_inputs/availability.parquet')
    state={(int(r.season),int(r.week),r.team):r.injury_report for r in states.itertuples()}
    historical_medical=[];historical_excluded=[]
    for r in hv.to_dict('records'):
        year,week=int(r['season']),int(r['week']);both={}
        if any(state.get((year,week,r[s]))!='final' for s in ['home','away']):
            historical_excluded.append(r['game_id']);continue
        for side in ['home','away']:
            t=r[side];both[side],_=burden(windows,t,year,week,injury_map.get((year,week,t),[]))
        out={k:r[k] for k in ['game_id','season','week','home','away','result','spread_line','prediction','qb_delta']}
        out.update({'inj_'+u:both['home'][u]-both['away'][u] for u in GROUPS});historical_medical.append(out)
    sv=[];sr=[];audit=[];selected_reports=[]
    for r in public.to_dict('records'):
        cutoff=aware_time(r['kickoff_utc'])-pd.Timedelta(minutes=60)
        v=choose_vector(vectors,r['game_id'],cutoff)
        both={s:choose_report(reports,r['game_id'],r[s],cutoff) for s in ['home','away']}
        common={k:r[k] for k in ['game_id','season','week','home','away','result','spread_line']}
        common.update(prediction=r['model_spread'],cutoff_utc=cutoff.isoformat(),kickoff_utc=r['kickoff_utc'])
        a=dict(game_id=r['game_id'],week=r['week'],saved_vector_eligible=v is not None,
               home_report_eligible=both['home'] is not None,away_report_eligible=both['away'] is not None)
        if v:
            x=dict(common,vector_generated_utc=v['generated_utc'],vector_revision=v['revision'])
            x.update({k:float(v['model_inputs'][col]) for k,col in zip(FEATURES,VECTOR_NAMES)})
            sv.append(x)
        if v and all(both.values()):
            units={};unseen=0
            for side in ['home','away']:
                selected_reports.append(both[side]);units[side],n=burden(windows,r[side],r['season'],r['week'],both[side]['parsed']['rows']);unseen+=n
            x=dict(common,qb_delta=float(v['model_inputs']['d__avail__qb_delta']),qb_source_generated_utc=v['generated_utc'],
                   home_report_captured_utc=both['home']['captured_utc'],away_report_captured_utc=both['away']['captured_utc'],
                   home_report_sha256=both['home']['source_capture_sha256'],away_report_sha256=both['away']['source_capture_sha256'],
                   unavailable_players_without_prior_team_snaps=unseen)
            x.update({'inj_'+u:units['home'][u]-units['away'][u] for u in GROUPS});sr.append(x)
        a['official_report_cohort_eligible']=v is not None and all(both.values());audit.append(a)
    for name,rows in [('historical_vectors',hv),('historical_medical',pd.DataFrame(historical_medical)),
                      ('saved_vectors_2026',pd.DataFrame(sv)),('saved_reports_2026',pd.DataFrame(sr)),('coverage_2026',pd.DataFrame(audit))]:
        rows.sort_values(['week','game_id'] if 'week' in rows else ['game_id']).to_csv(INPUT/(name+'.csv'),index=False)
    (INPUT/'selected_reports.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in selected_reports))
    for p in [ROOT/'data/lock_inputs/snaps.parquet',ROOT/'data/lock_inputs/inj.parquet',ROOT/'data/lock_inputs/availability.parquet',
              ROOT/'research/shrinkage_results/frozen_training_features.csv.gz',ROOT/'research/pressure_inputs/base_forecasts.csv',ROOT/'research/pressure_inputs/ats_2026_results.csv']:
        source_hash[str(p.relative_to(ROOT))]=sha(p)
    meta=dict(source_sha256=source_hash,historical_vector_n=len(hv),historical_medical_n=len(historical_medical),
              historical_medical_nonfinal_report_exclusions=historical_excluded,saved_vector_n=len(sv),official_report_n=len(sr),
              missing_2026_not_imputed=True,historical_snap_publication_times_verified=False)
    (INPUT/'provenance.json').write_text(json.dumps(meta,indent=2)+'\n')
    print({k:meta[k] for k in ['historical_vector_n','historical_medical_n','saved_vector_n','official_report_n']},flush=True)
