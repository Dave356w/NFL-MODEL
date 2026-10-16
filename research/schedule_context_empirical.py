"""R003-SC1: shrunk schedule/location contexts for observed-score distributions."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from scipy.special import xlogy

import market_context_empirical as m
import joint_market_residuals_report as b
import distribution_ablations as serialization

OUT=m.OUT.parent/'R003_schedule_context'
REST=m.j.ROOT/'research/disjoint_features_inputs/schedule_context.csv'
GROUPS=('slot','rest','travel','body_clock','venue','phase')
MIN_SUPPORT=20.
PLAIN_CONFIG=m.CONFIGS['direct_ref_h2_t3_p0']
ET=ZoneInfo('America/New_York')
EAST=set('ATL BAL BUF CAR CIN CLE DET IND JAX MIA NE NYG NYJ PHI PIT TB WAS'.split())
CENTRAL=set('CHI DAL GB HOU KC MIN NO TEN STL'.split())
PACIFIC=set('SEA SF OAK LV SD LAC'.split())


@dataclass(frozen=True)
class Variant:
    name: str
    family: str
    pseudo_games: int=0


PLAIN=Variant('plain','plain')
VARIANTS=(PLAIN,)+tuple(Variant(f'{group}_k{k}',group,k)
    for group in GROUPS+('joint','additive') for k in [30,100])
VARIANT_MAP={v.name:v for v in VARIANTS}


def home_zone(team,season):
    if team in EAST:return 'America/New_York','Eastern'
    if team in CENTRAL or (team=='LA' and int(season)<=2015):return 'America/Chicago','Central'
    if team in PACIFIC or team=='LA':return 'America/Los_Angeles','Pacific'
    if team=='DEN':return 'America/Denver','Mountain'
    if team=='ARI':return 'America/Phoenix','Phoenix'
    raise ValueError(f'Unknown team home zone: {team}')


def clock_band(hour):
    return 'early' if hour<12 else 'afternoon' if hour<17 else 'evening' if hour<20 else 'late'


def rest_key(home,away,week):
    if int(week)==1:return 'opener'
    try:home,away=float(home),float(away)
    except (ValueError,TypeError):return None
    if not np.isfinite([home,away]).all() or min(home,away)<=0:return None
    def band(days):return 'short' if days<=6 else 'normal' if days<10 else 'long'
    gap='home_plus2' if home-away>=2 else 'away_plus2' if away-home>=2 else 'within1'
    return '|'.join([band(home),band(away),gap])


def schedule_keys(row):
    """Use calendar, rest and home-base zones only; no result/price consumption."""
    year,week=int(row['season']),int(row['week'])
    final_week=17 if year<=2020 else 18
    phase='final' if week==final_week else 'early' if week<=4 else 'mid' if week<=13 else 'late'
    keys=dict(slot=None,rest=rest_key(row['home_rest'],row['away_rest'],week),
              travel=None,body_clock=None,venue=None,phase=phase)
    # Neutral site location/clock may be ambiguous; don't invent venue coordinates.
    if str(row['location']).lower()!='home':return keys
    try:
        kickoff=datetime.strptime(str(row['gameday'])+' '+str(row['gametime']),'%Y-%m-%d %H:%M').replace(tzinfo=ET)
    except (ValueError,TypeError):return keys
    home_tz,venue=home_zone(str(row['home_team']),year)
    away_tz,_=home_zone(str(row['away_team']),year)
    home_time=kickoff.astimezone(ZoneInfo(home_tz));away_time=kickoff.astimezone(ZoneInfo(away_tz))
    hour=kickoff.hour+kickoff.minute/60
    day=kickoff.weekday()
    slot=('TNF' if hour>=18 else 'Thursday_day') if day==3 else (
        'MNF' if day==0 and hour>=18 else 'SNF' if day==6 and hour>=18 else
        'Sunday_early' if day==6 and hour<14.5 else 'Sunday_late' if day==6 else 'other')
    shift=(home_time.utcoffset()-away_time.utcoffset()).total_seconds()/3600
    travel='eastward2plus' if shift>=2 else 'westward2plus' if shift<=-2 else 'small_shift'
    keys.update(slot=slot,travel=travel,venue=venue,
        body_clock=clock_band(home_time.hour+home_time.minute/60)+'|'+clock_band(away_time.hour+away_time.minute/60))
    return keys


def add_features(frame,rest):
    if rest.duplicated(['game_id','season','week']).any():raise ValueError('Duplicate rest rows')
    z=frame.merge(rest[['game_id','season','week','home_rest','away_rest']],
                  on=['game_id','season','week'],how='left',validate='one_to_one')
    features=pd.DataFrame([schedule_keys(row) for row in z.to_dict('records')],index=z.index)
    for name in GROUPS:z['feature_'+name]=features[name]
    z['feature_joint']=[None if any(pd.isna(value) for value in values) else '||'.join(values)
                        for values in features[list(GROUPS)].itertuples(index=False,name=None)]
    return z


def shrink_weights(base,source_keys,target_key,pseudo_games):
    """Sparse or market-irrelevant contexts fall back exactly to plain weights."""
    w=np.asarray(base,float)
    if (not np.isfinite(w).all() or (w<0).any() or not np.isclose(w.sum(),1,atol=1e-12,rtol=0)
            or len(w)!=len(source_keys) or pseudo_games<=0):
        raise ValueError('Invalid source weights, keys or shrinkage')
    empty=dict(context_mass=0.,context_kish=0.,context_support=0.,context_alpha=0.,context_fallback=True)
    if not isinstance(target_key,str) or not target_key:return w.copy(),dict(empty,fallback_reason='unknown_target')
    match=pd.Series(source_keys,dtype=object).eq(target_key).fillna(False).to_numpy(bool)
    mass=float(w[match].sum())
    if mass<=0:return w.copy(),dict(empty,fallback_reason='no_matching_mass')
    kish=mass**2/float(w[match]@w[match]);support=min(kish,m.effective(w)*mass)
    audit=dict(context_mass=mass,context_kish=kish,context_support=support)
    if support<MIN_SUPPORT:
        return w.copy(),dict(audit,context_alpha=0.,context_fallback=True,fallback_reason='small_relevant_support')
    alpha=support/(support+pseudo_games)
    contextual=np.where(match,w/mass,0.)
    result=(1-alpha)*w+alpha*contextual
    if not np.isclose(result.sum(),1,atol=1e-12,rtol=0):raise AssertionError('Context mixture not normalized')
    return result,dict(audit,context_alpha=float(alpha),context_fallback=False,fallback_reason='shrunk_context')


def contextual_distribution(base,history,target,variant):
    # Caller uses the exact same sorted history as the baseline's source atoms.
    if not np.array_equal(base['source_ids'],history.game_id.to_numpy()):
        raise ValueError('Context rows must align with baseline source IDs')
    if variant.family=='plain':
        weights=base['weights'].copy()
        audit=dict(context_mass=1.,context_kish=m.effective(weights),context_support=m.effective(weights),
                   context_alpha=0.,context_fallback=True,fallback_reason='plain')
    elif variant.family=='additive':
        components=[shrink_weights(base['weights'],history['feature_'+group].to_numpy(),
                                  target['feature_'+group],variant.pseudo_games) for group in GROUPS]
        weights=np.mean([x[0] for x in components],axis=0)
        audit={name:float(np.mean([x[1][name] for x in components])) for name in
               ['context_mass','context_kish','context_support','context_alpha']}
        audit.update(context_fallback=all(x[1]['context_fallback'] for x in components),fallback_reason='additive_average')
    else:
        weights,audit=shrink_weights(base['weights'],history['feature_'+variant.family].to_numpy(),
                                    target['feature_'+variant.family],variant.pseudo_games)
    return dict(base,weights=weights,audit=dict(base['audit'],**audit,final_ess=m.effective(weights)))


def select(archive,year,family=None):
    choices=VARIANTS if family is None else tuple(v for v in VARIANTS if v.family in ['plain',family])
    chosen,audit=m.select_names(archive,year,candidates=choices)
    audit['family']=family or 'all'
    return chosen,audit


def exact_scores(frame):
    f=m.j.add_binary_and_bet_scores(frame)
    margin=f.home_score-f.away_score;total=f.home_score+f.away_score
    for prefix,prob,y,valid in [('win','p_home_non_tie',margin>0,margin!=0),
        ('cover','cover_conditional',margin>f.spread_line,margin!=f.spread_line),
        ('over','over_conditional',total>f.total_line,total!=f.total_line)]:
        p=f[prob].to_numpy();labels=y.to_numpy(float)
        f[prefix+'_ll']=np.where(valid,-xlogy(labels,p)-xlogy(1-labels,1-p),np.nan)
    return f


def run(out=OUT):
    out=m.guarded_output(out)
    if out in [m.OUT.resolve(),(m.OUT.parent/'R003_market_context_refinement').resolve()]:
        raise ValueError('Earlier context experiments are protected')
    registered=json.loads((out/'registration_record.json').read_text())
    if registered['protocol_sha256']!=m.j.sha256(out/'PROTOCOL.md'):raise ValueError('Protocol changed')
    frame=add_features(m.load_inputs(),pd.read_csv(REST))
    feature_cols=['game_id','season','week','home_rest','away_rest']+['feature_'+x for x in GROUPS+('joint',)]
    frame[feature_cols].to_csv(out/'feature_table.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    baseline_path=m.OUT.parent/'R003_market_context_refinement/predictions.csv.gz'
    saved=pd.read_csv(baseline_path);saved=saved[saved.arm.eq('direct_ref_h2_t3_p0')].set_index('game_id')
    records=[];error=0.
    for (year,week),test in frame[frame.season>=2015].groupby(['season','week'],sort=True):
        history=m.prior(frame,test.iloc[0])
        for _,row in test.iterrows():
            base=m.distribution(m.prepare_pool(history,row),PLAIN_CONFIG)
            meta={k:row[k] for k in ['game_id','season','week','home_team','away_team','home_score','away_score',
                                   'spread_line','total_line','home_moneyline','away_moneyline']}
            for variant in VARIANTS:
                dist=contextual_distribution(base,history,row,variant)
                metrics=m.grade(dist,row)
                if variant==PLAIN and year>=2017:
                    old=saved.loc[row.game_id]
                    error=max(error,max(abs(metrics[k]-old[k]) for k in
                              ['primary_crps','win_brier','cover_win','cover_push','p_home_non_tie']))
                    if error>1e-10:raise AssertionError('Plain model reproduction failed')
                records.append(dict(arm=variant.name,**meta,**metrics))
    raw=pd.DataFrame(records);selections=[];selected=[]
    for year in sorted(raw.loc[raw.season>=2017,'season'].unique()):
        for family in [None,*GROUPS,'joint','additive']:
            name,audit=select(raw,int(year),family);selections.append(audit)
            z=raw[raw.season.eq(year)&raw.arm.eq(name)].copy()
            z['configuration']=name;z['arm']='selected_'+(family or 'all');selected.append(z)
    raw=raw[raw.season>=2017].copy();raw['configuration']=raw.arm
    result=pd.concat([raw,*selected],ignore_index=True)
    result['q']=m.j.fair_moneyline(result.home_moneyline.to_numpy(),result.away_moneyline.to_numpy())
    result=exact_scores(result)
    if result.duplicated(['arm','game_id']).any():raise AssertionError('Duplicate predictions')
    if result.groupby('arm').size().nunique()!=1:raise AssertionError('Mismatched populations')
    if not all(len(g)==816 for _,g in result[result.season.between(2023,2025)].groupby('arm')):
        raise AssertionError('Main cohort mismatch')
    if not all((r.training_max_season,r.training_max_week)<(r.season,r.week) for r in result.itertuples()):
        raise AssertionError('Future input cutoff')
    if not all(s['selection_max_season']<s['target_season'] for s in selections):raise AssertionError('Future selector')
    for a,c,d in [('p_home','p_tie','p_away'),('cover_win','cover_push','cover_lose'),('over_win','over_push','over_lose')]:
        if not np.allclose(result[a]+result[c]+result[d],1,atol=1e-12):raise AssertionError('Bad event probabilities')
    serialization.write_predictions(result,out/'predictions.csv.gz')
    m.dump(out/'annual_selections.json',selections)
    m.dump(out/'provenance.json',dict(experiment='R003-SC1',registration=registered,
        input_hashes={str(p.relative_to(m.j.ROOT)):m.j.sha256(p) for p in [m.INPUT,REST,baseline_path]},
        source_hashes={str(p.relative_to(m.j.ROOT)):m.j.sha256(p) for p in
            [Path(__file__).resolve(),m.j.ROOT/'research/market_context_empirical.py']},
        baseline_reproduction_max_error=error,variants=[asdict(v) for v in VARIANTS],
        feature_availability={g:int(frame['feature_'+g].notna().sum()) for g in GROUPS},
        independent_validation=False,production_changed=False))
    write_report(result,frame,selections,out)
    print((out/'REPORT.md').read_text())
    return result


def write_report(frame,features,selections,out):
    rows=[];comparisons=[];returns=[];support=[];slices=[]
    bases=[('2023-25',frame.season.between(2023,2025)),('2017-22',frame.season.between(2017,2022)),
           ('2026 diagnostic',frame.season.eq(2026))]+[(str(y),frame.season.eq(y)) for y in sorted(frame.season.unique())]
    for basis,mask in bases:
        sub=frame[mask]
        plain=sub[sub.arm.eq('plain')].set_index('game_id').sort_index()
        for name,g in sub.groupby('arm'):
            g=g.set_index('game_id').sort_index()
            if not g.index.equals(plain.index):raise AssertionError('Unpaired comparison')
            values={col:float(g[col].mean()) for col in m.LOSSES}
            for target in ['home','away','margin','total']:
                for level in [50,80,90]:
                    for metric in ['coverage','width']:
                        col=f'{target}_{metric}{level}';values[col]=float(g[col].mean())
            rows.append(dict(basis=basis,arm=name,games=len(g),**values))
            if basis in ['2023-25','2017-22','2026 diagnostic']:
                cols=['primary_crps','margin_crps','total_crps','win_ll','cover_ll','over_ll']
                delta=plain[cols].to_numpy()-g[cols].to_numpy()
                finite=~np.isinf(delta).any(axis=0)
                boot=b.week_bootstrap(delta[:,finite],g.season,g.week)
                positions={col:i for i,col in enumerate(np.flatnonzero(finite))}
                for ix,col in enumerate(cols):
                    comparisons.append(dict(basis=basis,arm=name,metric=col,gain=float(np.nanmean(delta[:,ix])),
                        ci95=b.interval(boot[:,positions[ix]]) if ix in positions else None,
                        sensitivity_ci=b.interval(boot[:,positions[ix]],1-.05/16) if ix in positions else None))
                support.append(dict(basis=basis,arm=name,mean_alpha=float(g.context_alpha.mean()),
                    fallback_fraction=float(g.context_fallback.mean()),mean_relevant_support=float(g.context_support.mean()),
                    median_relevant_support=float(g.context_support.median()),mean_final_ess=float(g.final_ess.mean())))
        if basis in ['2023-25','2017-22','2026 diagnostic']:
            returns.extend(b.roi_rows(sub,basis))
            joined=sub.merge(features[['game_id']+['feature_'+g for g in GROUPS]],on='game_id',validate='many_to_one')
            for group in GROUPS:
                f=joined[joined.arm.isin(['plain','selected_all','selected_'+group])]
                for (arm,key),g in f.groupby(['arm','feature_'+group],dropna=False):
                    slices.append(dict(basis=basis,feature=group,category=None if pd.isna(key) else key,arm=arm,n=len(g),
                        primary_crps=float(g.primary_crps.mean()),win_ll=float(g.win_ll.mean()),cover_ll=float(g.cover_ll.mean()),
                        over_ll=float(g.over_ll.mean()),units=float(g.model_units.sum()),mean_alpha=float(g.context_alpha.mean())))
    pd.DataFrame(rows).to_csv(out/'metrics.csv',index=False)
    pd.DataFrame(support).to_csv(out/'support.csv',index=False)
    m.dump(out/'comparisons.json',comparisons);m.dump(out/'moneyline.json',returns);m.dump(out/'feature_slices.json',slices)
    main=frame[frame.season.between(2023,2025)]
    plain=main[main.arm.eq('plain')].set_index('game_id');selected=main[main.arm.eq('selected_all')].set_index('game_id').loc[plain.index]
    delta=plain.primary_crps-selected.primary_crps;annual=delta.groupby(plain.season).mean()
    primary=next(x for x in comparisons if x['basis']=='2023-25' and x['arm']=='selected_all' and x['metric']=='primary_crps')
    secondary={k:float(plain[k].mean()-selected[k].mean()) for k in ['margin_crps','total_crps','win_ll','cover_ll','over_ll']}
    gates=dict(practical_gain=primary['gain']>=.01,positive_interval=primary['ci95'][0]>0,
        annual_consistency=bool((annual>0).all()),secondary_scores=all(np.isfinite(v) and v>=-.002 for v in secondary.values()),integrity=True)
    m.dump(out/'decision.json',dict(experiment='R003-SC1',gates=gates,recommendation='retain for research' if all(gates.values()) else 'no qualified improvement',independent_validation=False,production_promotion=False))
    weekly=pd.DataFrame(dict(s=plain.season,w=plain.week,d=delta)).groupby(['s','w']).d.agg(['sum','count'])
    loo=(delta.sum()-weekly['sum'])/(len(delta)-weekly['count'])
    m.dump(out/'stability.json',dict(annual_primary_gain={str(k):float(v) for k,v in annual.items()},
        leave_one_season_out={str(y):float(delta[plain.season!=y].mean()) for y in annual.index},
        leave_one_week_range=[float(loo.min()),float(loo.max())],secondary_gains=secondary))
    main_metrics=pd.DataFrame(rows).query("basis=='2023-25'")
    lines=['| Arm | Primary CRPS ↓ | Gain vs plain | Win LL ↓ | Cover LL ↓ | Total LL ↓ |','|---|---:|---:|---:|---:|---:|']
    plain_loss=float(plain.primary_crps.mean())
    for r in main_metrics.sort_values('primary_crps').itertuples():
        lines.append(f'| {r.arm} | {r.primary_crps:.6f} | {plain_loss-r.primary_crps:+.6f} | {r.win_ll:.6f} | {r.cover_ll:.6f} | {r.over_ll:.6f} |')
    money=['| Basis | Policy | Bets | W–L–P | Units | ROI ± SE | Favorite | Null |','|---|---|---:|---|---:|---:|---:|---:|']
    for r in returns:
        if r['arm'] not in ['plain','selected_all']:continue
        favorite=next(x['units'] for x in returns if x['basis']==r['basis'] and x['arm']=='control_favorite')
        money.append(f"| {r['basis']} | {r['arm']} | {r['bets']} | {r['wins']}–{r['losses']}–{r['pushes']} | {r['units']:+.3f} | {100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} pp | {favorite:+.3f}u | {100*r['market_null']:.2f}% |")
    selected_names=[(x['target_season'],x['chosen']) for x in selections if x['family']=='all']
    supp=pd.DataFrame(support).query("basis=='2023-25'")
    slines=['| Variant | Mean support | Mean context weight | Fallback |','|---|---:|---:|---:|']
    for r in supp[supp.arm.isin([g+'_k100' for g in GROUPS+('joint','additive')])].itertuples():
        slines.append(f'| {r.arm} | {r.mean_relevant_support:.1f} | {100*r.mean_alpha:.1f}% | {100*r.fallback_fraction:.1f}% |')
    report=f'''# R003-SC1 — schedule, rest, travel and clock context

**Decision: {'retain for research' if all(gates.values()) else 'no qualified improvement'}.**
Exposed historical development, not independent confirmation. Plain is the
observed-score MC2 kernel (spread bandwidth 2, total bandwidth 3, no global backoff).
All added distributions retain those same observed score atoms.

## Flat 1u moneyline results (not used to fit or select)

{chr(10).join(money)}

Identical eligible moneyline games, ties push, market pick'ems excluded. Full
fixed-arm returns and paired week intervals are in moneyline.json. No historical
spread/total ROI: actual two-sided prices are absent.

## All fixed variants and earlier-season selected paths, 816 games 2023–25

{chr(10).join(lines)}

Primary loss is 0.5*(margin CRPS+total CRPS), lower better. Single new primary
comparison: selected_all minus plain policy, positive gain = plain loss minus
selected loss. Gain **{primary['gain']:+.6f}**, 95% interval **{primary['ci95']}**;
16-challenger sensitivity interval {primary['sensitivity_ci']}. Bootstrap:
10,000 paired whole-week draws within season, seed 20261016, conditional on
fixed forecast/selection paths, without removing historical design exposure.
Other arms/slices are descriptive; no best-arm historical rank is qualification.

Annual all-family choices: {selected_names}. Plain is an explicit first-choice
tie-break/control in every selector. Selection uses strictly earlier OOF seasons,
min two seasons, never ROI. Annual primary gains: {dict((int(k),float(v)) for k,v in annual.items())}.
Gates: {gates}. A zero-gain plain selection cannot establish improvement.

## Shrinking sparse contexts to the plain distribution

For matching context rows, support=min(Kish ESS_subset, ESS_plain*context_mass).
Below 20 relevant games, on unknown features or empty matching mass, weights
equal plain exactly. Otherwise context weight alpha=support/(support+K), K=30
or 100. Final weights are (1-alpha)*plain+alpha*matching_context. No outcome-driven
strength fit; no unrelated context is fabricated. Additive averages six coherent
shrunk distributions; joint requires all six keys to match. These are separately
tested combinations, not extra independent samples.

{chr(10).join(slines)}

Full support/alpha/fallback and feature-category scores are saved. A subgroup's
sample size is not the same as its market-relevant support. Many historical TNF
games can still leave few comparable spread/total games for a particular TNF.

## Feature definitions and limits

Slot distinguishes TNF/Thursday daytime/MNF/SNF/Sunday early/Sunday late/other.
Rest uses both teams (short <=6 days, normal 7–9, long >=10) and rest-gap class;
week 1 is opener. Travel is a home-base to home-venue >=2-hour east/west proxy.
Body clock uses home/away local kickoff bins and venue uses home time-zone region.
Phase separates early/mid/late/final week. ZoneInfo handles Arizona DST and
historical LA/St. Louis location. Neutral sites fall back for slot/venue/travel/
clock; rest and phase remain usable. No itinerary, actual sleep, acclimation,
weather or rested-starter outcome is inferred.

Schedule fields are frozen retrospective records, not timestamp-certified feeds.
Neutral-site kickoff ambiguities are not silently corrected. Inputs have the
same historical price-time limitations as the plain model. Earlier standalone
schedule diagnostics found mostly unresolved market residuals; these results
test empirical distribution context, not a claim those old tests were untouched.

## Reproduction

`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/schedule_context_empirical.py`

The protocol and local registration hash precede scoring. Feature table,
per-game full-precision results, all arms, annual selections, cutoffs, source/
input hashes, stability and independent repeat accompany the report. Original
experiments, prior user changes, production models and ledger are preserved.
No live forecast, price-provider connection, deployment or wager occurred.
'''
    (out/'REPORT.md').write_text(report)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=OUT)
    run(parser.parse_args().output_dir)
