"""Fixed user-requested two-point 2026 backup margin overlay; see protocol."""
from pathlib import Path
import json,hashlib,sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import nfl_model as m
from research.qb_actual_starters import corrected_schedules,ORDER
from research.qb_backup_residuals import incumbent,mean_ci
from research.qb_saved_pick_audit import name_index,resolve_name
from research import qb_minus2_grade as grade
OUT=ROOT/'research/qb_minus2_2026_results'
INPUT=ROOT/'research/qb_minus2_2026_inputs'


def prepare():
    INPUT.mkdir(exist_ok=True)
    p=ROOT/'data/latest/ats_pricing_results.csv'
    published=pd.read_csv(p);published=published[published.season.eq(2026)&published.result.notna()].copy()
    published['pool']='published 2026';published['revision']=published.forecast_revision.fillna('historical replay')
    archived=pd.read_csv(ROOT/'research/qb_saved_pick_audit_results/games.csv').rename(columns={'model_spread':'fixed_band_spread','raw_spread':'model_spread','market_spread':'spread_line','actual_home_margin':'result'})
    archived['pool']='archived saved decisions';archived['ats_basis']=archived.basis
    archived['original_selected_side']=archived.selected_side
    published['original_selected_side']=published.fixed_band_ats_side
    # Exact lineup evidence from the earlier immutable saved-pick audit.
    saved=pd.read_csv(ROOT/'research/qb_saved_pick_audit_results/team_qbs.csv')
    saved=saved.set_index(['game_id','revision','side'])
    schedule=corrected_schedules(pd.read_parquet(ROOT/'data/lock_inputs/schedules.parquet'))
    schedule=schedule[schedule.season.eq(2026)]
    sch=schedule.set_index('game_id')
    availability=pd.read_parquet(ROOT/'data/lock_inputs/availability.parquet').set_index(['season','week','team'])
    roster=pd.read_parquet(ROOT/'data/lock_inputs/rost.parquet');qb=pd.read_parquet(ROOT/'data/lock_inputs/qb.parquet')
    index=name_index(qb,schedule,roster)
    depth=pd.read_parquet(ROOT/'data/lock_inputs/depth.parquet');depth['_t']=pd.to_datetime(depth.dt,utc=True)
    records=[];teams=[];incs={}
    all_=pd.concat([published,archived],ignore_index=True)
    for r in all_.to_dict('records'):
        s=sch.loc[r['game_id']]
        raw=r.get('model_spread',np.nan)
        if pd.isna(raw):
            old=archived[archived.game_id.eq(r['game_id'])&archived.revision.eq(r['revision'])]
            if len(old):raw=float(old.model_spread.iloc[0])
        record=dict(pool=r['pool'],game_id=r['game_id'],revision=r['revision'],season=2026,week=int(r['week']),
                    home=r['home'],away=r['away'],result=float(r['result']),spread_line=float(r['spread_line']),
                    fixed_band_spread=float(r['fixed_band_spread']),model_spread=raw,
                    original_selected_side=r['original_selected_side'],ats_basis=r['ats_basis'],
                    ats_home_odds=r.get('ats_home_odds'),ats_away_odds=r.get('ats_away_odds'),ats_price_basis=r.get('ats_price_basis'))
        for side in ('home','away'):
            team=r[side];key=(r['game_id'],r['revision'],side)
            lineup_source='frozen replay availability';stamp=None
            if key in saved.index:
                x=saved.loc[key];name=x.saved_qb;pid=x.projected_id;state=x.selection
                # Recover exact original forecast cutoff for the archived rows, or the published saved metadata.
                if pd.notna(r.get('generated_utc')):stamp=pd.Timestamp(r['generated_utc'])
                if stamp is None:
                    # team evidence chart cutoff was frozen in prior audit; journal retains exact forecast time.
                    from research.qb_saved_pick_audit import journal
                    import ats_locks
                    stores=[ROOT/'data']+ats_locks.runtime_stores(ROOT/'data')
                    matches=[z for store in stores for z in journal(store/'ats_locks.jsonl') if z['game_id']==r['game_id'] and z['revision']==r['revision']]
                    if matches:stamp=pd.Timestamp(matches[0]['generated_utc'])
                lineup_source=x.evidence
            else:
                k=(2026,int(r['week']),team)
                name=availability.loc[k,'qb_expected'] if k in availability.index else None
                eligible=set(roster.loc[roster.season.eq(2026)&roster.team.eq(team)&(roster.week<=r['week'])&roster.position.eq('QB'),'gsis_id'])
                blend=isinstance(name,str) and ' (Q) / ' in name
                pid=resolve_name(name,index,eligible) if not blend else None
                state='blend' if blend else 'unknown' if pid is None else 'correct' if pid==s[side+'_qb_id'] else 'wrong'
            if state=='blend' or pd.isna(pid):pid=None
            inc_key=(2026,int(r['week']),team)
            if inc_key not in incs:incs[inc_key]=incumbent(schedule,roster,team,2026,int(r['week']))
            inc=incs[inc_key]
            proxy=(np.nan if inc=='__unknown_roster__' or pid is None else float(pid!=inc) if inc is not None else 0.)
            ko=m.kickoff_utc(s);rank=np.nan;chart_stamp=None
            if ko is not None and pid is not None:
                cut=pd.Timestamp(ko)-pd.Timedelta(hours=24)
                if stamp is not None:cut=min(cut,stamp)
                h=depth[depth.season.eq(2026)&depth.team.eq(team)&(depth._t<=cut)]
                if len(h):
                    chart_stamp=h._t.max()
                    if cut-chart_stamp<=pd.Timedelta(days=7):
                        ranks=h.loc[h._t.eq(chart_stamp)&h.gsis_id.eq(pid),'pos_rank']
                        if len(ranks):rank=float(ranks.min())
            chart=float(rank>1) if np.isfinite(rank) else np.nan
            record[side+'_chart']=chart;record[side+'_replacement']=proxy;record[side+'_correct']=state=='correct'
            record[side+'_qb']=name
            teams.append(dict(pool=r['pool'],game_id=r['game_id'],revision=r['revision'],week=r['week'],side=side,team=team,
                projected_qb=name,projected_id=pid,actual_qb=s[side+'_qb_name'],actual_id=s[side+'_qb_id'],selection=state,
                lineup_source=lineup_source,forecast_cutoff=stamp,chart_rank=rank,chart_timestamp=chart_stamp,
                chart_backup=chart,replacement=proxy,incumbent_id=inc))
        records.append(record)
    games=pd.DataFrame(records);teams=pd.DataFrame(teams)
    games.to_csv(INPUT/'games.csv',index=False);teams.to_csv(INPUT/'team_qbs.csv',index=False)
    import ats_locks
    paths=[p,ROOT/'research/qb_saved_pick_audit_results/games.csv',ROOT/'research/qb_saved_pick_audit_results/team_qbs.csv',ORDER,
           *[ROOT/'data/lock_inputs'/f'{x}.parquet' for x in ['schedules','availability','rost','qb','depth']]]
    paths += [store/'ats_locks.jsonl' for store in [ROOT/'data']+ats_locks.runtime_stores(ROOT/'data') if (store/'ats_locks.jsonl').exists()]
    (INPUT/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')


def overlay(frame,cohort):
    """Carry unresolved decisions unchanged without classifying them as healthy."""
    h=frame['home_'+cohort];a=frame['away_'+cohort]
    known=h.notna()&a.notna()
    adjusted=grade.apply_penalty(frame,h,a)
    return adjusted.where(known,frame.fixed_band_spread),known


def metric(d,pred):
    k=d.result.notna()&pred.notna();e=d.loc[k,'result']-pred[k]
    return dict(n=int(k.sum()),mean_home_residual=float(e.mean()),MAE=float(e.abs().mean()),MSE=float((e**2).mean()))


def run():
    OUT.mkdir(exist_ok=True)
    games=pd.read_csv(INPUT/'games.csv');team=pd.read_csv(INPUT/'team_qbs.csv')
    all_grades=[];summaries=[];flips=[];team_residuals=[]
    for pool,d in games.groupby('pool',sort=False):
        d=d.reset_index(drop=True)
        base=grade.grade(d,d.fixed_band_spread)
        if not (base.selected_side.fillna('')==d.original_selected_side.fillna('')).all():raise AssertionError('original selection not reproduced')
        for cohort in ('chart','replacement'):
            h=d['home_'+cohort];a=d['away_'+cohort]
            adjusted_full,known=overlay(d,cohort)
            after=grade.grade(d,adjusted_full)
            sets={'all completed':np.ones(len(d),dtype=bool),'known lineups':known,
                  'backup involved':known&((h+a)>0),
                  'correct starters, backup involved':known&((h+a)>0)&d.home_correct.eq(True)&d.away_correct.eq(True)}
            for label,k in sets.items():
                if not np.asarray(k).any():continue
                summary=dict(pool=pool,cohort=cohort,subset=label,known_games=int(known.sum()),unknown_unchanged=int((~known).sum()),
                             before=grade.summary(base.loc[k]),after=grade.summary(after.loc[k]),
                             favorite=grade.summary(grade.grade(d.loc[k],d.loc[k,'spread_line']*2)),
                             home=grade.summary(grade.grade(d.loc[k],d.loc[k,'spread_line']+1)),
                             paired=grade.paired_summary(base.loc[k],after.loc[k]),
                             before_margin=metric(d.loc[k],d.loc[k,'fixed_band_spread']),after_margin=metric(d.loc[k],adjusted_full[k]),market_margin=metric(d.loc[k],d.loc[k,'spread_line']))
                paired=pd.DataFrame({'season':2026,'week':d.loc[k,'week'],'gain':after.loc[k,'units']-base.loc[k,'units']})
                summary['paired_gain_ci95']=mean_ci(paired,'gain') if len(paired)>1 else None
                priced_before=grade.grade(d.loc[k],d.loc[k,'fixed_band_spread'],price_mode='side_specific')
                priced_after=grade.grade(d.loc[k],adjusted_full[k],price_mode='side_specific')
                priced=priced_before.units.notna()&priced_after.units.notna()
                summary['paired_side_prices']=dict(n=int(priced.sum()),before=grade.summary(priced_before.loc[priced]),after=grade.summary(priced_after.loc[priced]))
                raw=d.loc[k,'model_spread'];raw_k=raw.notna()
                if raw_k.any():
                    sub=d.loc[k].loc[raw_k];raw_adj=grade.apply_penalty(sub,sub['home_'+cohort],sub['away_'+cohort],margin_column='model_spread').where(known.loc[sub.index],sub.model_spread)
                    summary['raw_sensitivity']=dict(n=len(sub),before=grade.summary(grade.grade(sub,sub.model_spread)),after=grade.summary(grade.grade(sub,raw_adj)),before_margin=metric(sub,sub.model_spread),after_margin=metric(sub,raw_adj))
                summaries.append(summary)
            oriented=[]
            for i,r in d.loc[known].iterrows():
                for side,sign in [('home',1.),('away',-1.)]:
                    if r[side+'_'+cohort]!=1:continue
                    row=dict(pool=pool,cohort=cohort,game_id=r.game_id,revision=r.revision,team=r[side],qb=r[side+'_qb'],
                        both_backups=bool(r['home_'+cohort]+r['away_'+cohort]==2),
                        before_residual=(r.result-r.fixed_band_spread)*sign,
                        after_residual=(r.result-adjusted_full.loc[i])*sign,market_residual=(r.result-r.spread_line)*sign)
                    oriented.append(row);team_residuals.append(row)
            if oriented:
                oo=pd.DataFrame(oriented)
                summaries.append(dict(pool=pool,cohort=cohort,subset='backup-team oriented residuals',n=len(oo),
                    before_mean=float(oo.before_residual.mean()),after_mean=float(oo.after_residual.mean()),market_mean=float(oo.market_residual.mean())))
            detail=d.copy();detail['cohort']=cohort;detail['known_lineup']=known;detail['adjusted_margin']=adjusted_full
            detail['before_side']=base.selected_side;detail['after_side']=after.selected_side
            detail['before_grade']=base.grade;detail['after_grade']=after.grade
            detail['before_units']=base.units;detail['after_units']=after.units
            detail['flipped']=base.side!=after.side
            all_grades.append(detail)
            flips.append(detail[detail.flipped])
            # Backend source distinctions, on the same after/before rows.
            for source,k in d.groupby('ats_basis').groups.items():
                summaries.append(dict(pool=pool,cohort=cohort,subset='source: '+str(source),before=grade.summary(base.loc[k]),after=grade.summary(after.loc[k]),paired=grade.paired_summary(base.loc[k],after.loc[k])))
    pd.DataFrame(team_residuals).to_csv(OUT/'team_residuals.csv',index=False)
    pd.concat(all_grades,ignore_index=True).to_csv(OUT/'per_game.csv',index=False)
    pd.concat(flips,ignore_index=True).to_csv(OUT/'flips.csv',index=False)
    (OUT/'results.json').write_text(json.dumps(summaries,indent=2,allow_nan=False)+'\n')
    print(json.dumps([s for s in summaries if s['subset'] in ('all completed','backup involved')],indent=2))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--prepare-inputs',action='store_true');args=p.parse_args()
    if args.prepare_inputs:prepare()
    run()
