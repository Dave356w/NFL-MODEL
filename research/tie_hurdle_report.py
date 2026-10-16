"""Reports every R001 arm, including unfavorable secondary metrics."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

import joint_market_residuals as j
import joint_market_residuals_report as r

OUT=j.ROOT/'research/experiments/R001_tie_hurdle'
BASE=j.ROOT/'research/experiments/R000_reproduction'
LOSSES=['joint_nll','home_nll','away_nll','team_nll','margin_nll','total_nll',
        'home_crps','away_crps','team_crps','margin_crps','total_crps',
        'win_ll','win_brier','outcome_nll','outcome_brier','tie_ll','tie_brier',
        'cover_ll','cover_brier','over_ll','over_brier',
        'home_location_over_ll','away_location_over_ll','home_location_over_brier','away_location_over_brier']
INTERVALS=[f'{t}_{m}{level}' for t in ['home','away','margin','total']
           for level in [50,80,90] for m in ['coverage','width']]


def dump(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def frame_table(frame,columns):
    z=frame[columns].copy()
    for c in columns:
        if pd.api.types.is_float_dtype(z[c]):z[c]=z[c].map(lambda x:f'{x:.6f}')
    return r.table(columns,z.to_numpy().tolist())


def reliability(frame):
    rows=[]
    for arm,g in frame.groupby('arm'):
        decisive=g.home_score!=g.away_score
        margin=g.home_score-g.away_score;total=g.home_score+g.away_score
        events=[('winner_non_tie',g.p_home_non_tie,(margin>0),decisive),
                ('moneyline_non_tie',g.q,(margin>0),decisive),
                ('tie',g.p_tie,(margin==0),np.ones(len(g),bool)),
                ('home_win_unconditional',g.p_home,(margin>0),np.ones(len(g),bool)),
                ('away_win_unconditional',g.p_away,(margin<0),np.ones(len(g),bool)),
                ('spread_nonpush',g.cover_conditional,(margin>g.spread_line),(margin!=g.spread_line)),
                ('total_nonpush',g.over_conditional,(total>g.total_line),(total!=g.total_line)),
                ('home_location_nonpush',g.home_location_over_prob,(g.home_score>(g.total_line+g.spread_line)/2),
                 g.home_score!=(g.total_line+g.spread_line)/2),
                ('away_location_nonpush',g.away_location_over_prob,(g.away_score>(g.total_line-g.spread_line)/2),
                 g.away_score!=(g.total_line-g.spread_line)/2)]
        for event,prob,y,mask in events:
            edges=np.array([0,.0025,.005,.01,.02,.04,1.0000001]) if event=='tie' else np.linspace(0,1.0000001,11)
            a=pd.DataFrame(dict(prob=prob,y=np.asarray(y,float))).loc[np.asarray(mask)&np.isfinite(prob)]
            a['bin']=np.clip(np.searchsorted(edges,a.prob,side='right')-1,0,len(edges)-2)
            for index,c in a.groupby('bin'):
                n=len(c);mean=float(c.y.mean());z=1.959963984540054
                center=(mean+z*z/(2*n))/(1+z*z/n)
                radius=z*np.sqrt(mean*(1-mean)/n+z*z/(4*n*n))/(1+z*z/n)
                rows.append(dict(arm=arm,event=event,bin=int(index),n=n,positive_count=int(c.y.sum()),
                    predicted=float(c.prob.mean()),observed=mean,observed_ci95=[center-radius,center+radius]))
    return rows


def validate(f):
    p=np.load(OUT/'marginal_probabilities.npz');ids=list(p['game_ids'])
    a=pd.read_csv(OUT/'tie_fit_audit.csv')
    checks=dict(prior_week_tie_fit=all((x.training_max_season,x.training_max_week)<(x.season,x.week) for x in a.itertuples()),
        no_duplicate_arm_games=not f.duplicated(['arm','game_id']).any(),
        normalized_marginals=all(np.all(p[k]>=0) and np.allclose(p[k].sum(axis=1),1,atol=2e-6) for k in p.files if '__' in k),
        win_loss_tie_normalized=bool(np.allclose(f.p_home+f.p_tie+f.p_away,1,atol=1e-12)),
        spread_total_event_sums=bool(np.allclose(f.cover_win+f.cover_push+f.cover_lose,1,atol=1e-12) and np.allclose(f.over_win+f.over_push+f.over_lose,1,atol=1e-12)),
        coherent_means=bool(np.allclose(f.total_mean,f.home_mean+f.away_mean) and np.allclose(f.margin_mean,f.home_mean-f.away_mean)),
        primary_n_816=all(len(g)==816 for _,g in f[f.season.between(2023,2025)].groupby('arm')),
        all_probabilities_finite=bool(np.isfinite(f[['p_home','p_tie','p_away','p_home_non_tie']]).all().all()),
        conditional_winner_invariant=True,moneyline_choices_and_settlements_invariant=True,
        analytic_nll_gain_identity=True,pmf_row_alignment=True,identical_games=True,
        candidate_tie_matches_prior_fit=True)
    for arm,g in f.groupby('arm'):
        checks['identical_games'] &= set(ids)==set(g.game_id)
        g=g.set_index('game_id').loc[ids]
        checks['pmf_row_alignment'] &= bool(np.allclose(p[arm+'__margin'][:,p['margin_support']>0].sum(axis=1),g.p_home,atol=1e-6))
    for shape in j.SHAPES:
        b=f[f.arm==shape+'__A_market'].set_index('game_id').sort_index()
        c=f[f.arm==shape+'__R001_tie_hurdle'].set_index('game_id').sort_index()
        checks['conditional_winner_invariant'] &= bool(np.allclose(b.p_home_non_tie,c.p_home_non_tie,rtol=0,atol=1e-14))
        checks['moneyline_choices_and_settlements_invariant'] &= bool(np.allclose(b.model_units,c.model_units,equal_nan=True))
        checks['analytic_nll_gain_identity'] &= bool(np.allclose(b.joint_nll-c.joint_nll,b.tie_ll-c.tie_ll,atol=1e-12))
        rates=c.reset_index().merge(a,on=['season','week'],validate='many_to_one')
        checks['candidate_tie_matches_prior_fit'] &= bool(np.allclose(rates.p_tie,rates.rate,atol=1e-14))
    checks={k:bool(v) for k,v in checks.items()}
    dump('verification.json',checks)
    if not all(checks.values()):raise AssertionError(checks)
    return checks


def run():
    f=pd.read_csv(OUT/'predictions.csv.gz')
    checks=validate(f)
    samples=dict(historical_2023_25=f.season.between(2023,2025),earlier_2017_22=f.season.between(2017,2022),diagnostic_2026=f.season==2026)
    samples.update({f'season_{y}':f.season==y for y in sorted(f.season.unique())})
    summaries=[];comparisons=[];reliabilities=[];pits=[];stability=[];influences=[];rois=[]
    for sample,mask in samples.items():
        sub=f[mask]
        for arm,g in sub.groupby('arm'):
            row=dict(sample=sample,arm=arm,n=len(g),winner_n=int(g.win_ll.notna().sum()),
                p_tie=float(g.p_tie.mean()),ties=int((g.home_score==g.away_score).sum()))
            for col in LOSSES+INTERVALS:row[col]=float(g[col].mean())
            for col in ['win_ll','cover_ll','over_ll','home_location_over_ll','away_location_over_ll']:
                row[col+'_n']=int(g[col].notna().sum())
            summaries.append(row)
        for shape in j.SHAPES:
            b=sub[sub.arm==shape+'__A_market'].set_index('game_id').sort_index()
            c=sub[sub.arm==shape+'__R001_tie_hurdle'].set_index('game_id').sort_index()
            if not b.index.equals(c.index):raise AssertionError('Unpaired samples')
            metrics=LOSSES+INTERVALS
            diff=b[metrics].to_numpy()-c[metrics].to_numpy()
            draws=r.week_bootstrap(diff,b.season,b.week)
            for col,metric in enumerate(metrics):
                primary=sample=='historical_2023_25' and shape=='empirical' and metric=='joint_nll'
                comparisons.append(dict(sample=sample,shape=shape,metric=metric,
                    primary=primary,n=int(np.isfinite(diff[:,col]).sum()),
                    baseline=float(b[metric].mean()),candidate=float(c[metric].mean()),
                    baseline_minus_candidate=float(np.nanmean(diff[:,col])),
                    ci95=r.interval(draws[:,col]),
                    seven_contrast_sensitivity_ci=r.interval(draws[:,col],1-.05/7) if primary else None,
                    interpretation='positive favors lower candidate loss; coverage/width differences are not quality rankings'))
            if sample=='historical_2023_25':
                gain=b.joint_nll-c.joint_nll
                weekly=pd.DataFrame(dict(season=b.season,week=b.week,gain=gain)).groupby(['season','week']).gain.agg(['sum','count'])
                loo=(gain.sum()-weekly['sum'])/(len(gain)-weekly['count'])
                annual=gain.groupby(b.season).mean()
                stability.append(dict(shape=shape,positive_game_fraction=float((gain>0).mean()),
                    annual_gain={str(k):float(v) for k,v in annual.items()},
                    leave_one_week_out_gain_range=[float(loo.min()),float(loo.max())],
                    leave_one_season_out_gain={str(y):float(gain[b.season!=y].mean()) for y in annual.index},
                    tie_game_gain_sum=float(gain[b.home_score==b.away_score].sum()),
                    decisive_game_gain_sum=float(gain[b.home_score!=b.away_score].sum())))
                for gid in gain.abs().nlargest(10).index:
                    influences.append(dict(shape=shape,game_id=gid,joint_nll_gain=float(gain.loc[gid]),tie=bool(b.loc[gid,'home_score']==b.loc[gid,'away_score'])))
        if not sample.startswith('season_'):
            for row in reliability(sub):reliabilities.append(dict(sample=sample,**row))
            for arm,g in sub.groupby('arm'):
                for target in ['home','away','margin','total']:
                    hist,_=np.histogram(g[target+'_pit_mid'],bins=np.linspace(0,1,11))
                    pits.append(dict(sample=sample,arm=arm,target=target,n=len(g),midpoint_pit_decile_counts=hist.tolist(),note='Discrete midpoint PIT is not exactly uniform; diagnostic only.'))
            rois.extend(r.roi_rows(sub,sample))
    for name,rows in [('metrics.json',summaries),('paired_comparisons.json',comparisons),('reliability.json',reliabilities),
                      ('pit_diagnostics.json',pits),('stability.json',stability),('influential_games.json',influences),('moneyline_diagnostics.json',rois)]:dump(name,rows)
    pd.DataFrame(summaries).to_csv(OUT/'metrics.csv',index=False)
    pd.DataFrame(comparisons).to_csv(OUT/'candidate_vs_baseline.csv',index=False)
    primary=next(x for x in comparisons if x['primary'])
    main=pd.DataFrame(summaries).query("sample=='historical_2023_25'")
    selected=[x for x in comparisons if x['sample']=='historical_2023_25' and x['shape']=='empirical']
    violations=[x['metric'] for x in selected if x['metric'] in ['home_nll','away_nll','team_nll','margin_nll','total_nll','home_crps','away_crps','team_crps','margin_crps','total_crps'] and x['baseline_minus_candidate']<-.01]
    emp_stability=next(x for x in stability if x['shape']=='empirical')
    supported=(primary['baseline_minus_candidate']>=.005 and primary['ci95'][0]>0 and
        all(x>0 for x in emp_stability['annual_gain'].values()) and not violations)
    decision=dict(historical_hypothesis_supported=bool(supported),recommendation='retain for research',
        independent_validation=False,production_promotion=False,
        forward_consideration='planned, locked comparative assessment only; no qualification claim',
        secondary_tolerance_violations=violations,
        next_experiment='R002: explicit tie resolution with score transitions; register a single rule before fresh evaluation')
    dump('decision.json',decision)
    # Rare-event count uncertainty is reported explicitly; no tuning uses it.
    from scipy.stats import beta
    n=816;k=int(f[(f.arm=='empirical__A_market')&f.season.between(2023,2025)].eval('home_score == away_score').sum())
    tie_ci=[float(beta.ppf(.025,k,n-k+1)) if k else 0.,
            float(beta.ppf(.975,k+1,n-k)) if k<n else 1.]
    dump('tie_rate_uncertainty.json',dict(n=n,ties=k,observed_rate=k/n,
         clopper_pearson_ci95=tie_ci,note='Binomial count interval assumes independent equal-rate trials; descriptive with changing NFL contexts.'))
    a=pd.read_csv(OUT/'tie_fit_audit.csv')
    annual=pd.DataFrame(summaries).query("sample in ['season_2023','season_2024','season_2025']")
    mainroi=pd.DataFrame([x for x in rois if x['basis']=='historical_2023_25'])
    columns=['arm','n','joint_nll','team_nll','margin_nll','total_nll','team_crps','margin_crps','total_crps','win_ll','win_brier','outcome_nll','p_tie']
    report=f'''# R001 - Tie mass calibration

**Recommendation: retain for research.** Historical hypothesis {'supported' if supported else 'not supported under the locked rule'}.
No independent validation or production qualification. Quote timestamps are unknown.

## Hypothesis, baseline and candidate

See PROTOCOL.md for the specification committed before execution. The primary
comparator is empirical market-only A; smooth A is a secondary transportability
check. Jeffreys Beta(0.5,0.5) tie frequency uses complete eligible games in the
current and five earlier seasons, strictly before each forecast week. The
diagonal and off-diagonal cells are each scaled to the new stratum probability;
their conditional shapes are unchanged. No hyperparameter search, validation
selection, test tuning, or ROI selection occurred. This is mass calibration,
not an overtime scoring model. Baseline coefficients and covariances are frozen
to R000; reconstruction is asserted against its forecasts to 1e-10.

## Sources, cutoffs and samples

Frozen committed schedule/total files from base e93b936, SHA-256 recorded in
R000. Scores include overtime. Integer scores 0-80; no outcome reaches 80.
Fit/covariance history uses the original prior-week procedure. Tie estimation
uses prior eligible realized ties only; no current-week updates. Logical week
cutoffs are proven; actual market timestamps and their pregame availability
cannot be proven from these files. This is a conditional-on-input historical
simulation. No new data, quote edits or outcome repairs.

Training begins in 2013; means start prequential fitting in 2015, scored forecasts
in 2017. 2017-22 has 1,567 exposed development games per arm; 2023-25 has 816
historical evaluation games (272 per season; 815 decisive outcomes); 2026 W1-5
has 79 separate diagnostic games. All four arms contain 2,462 games. No unseen
validation/test split exists; earlier weeks of an evaluation season can enter
later weekly fits. Four original information sets remain unchanged in R000.

## Primary comparison

Baseline-minus-candidate joint NLL = **{primary['baseline_minus_candidate']:.6f} nats/game**,
paired week-bootstrap 95% interval **{primary['ci95']}**.
Seven-contrast sensitivity interval: {primary['seven_contrast_sensitivity_ci']}.
10,000 whole-week resamples, within season, seed 20261016. One new primary
contrast; smooth and every secondary metric are descriptive. The seven-contrast
interval only adds this contrast to the original six; neither interval erases
earlier unrecorded selection or the fact this hypothesis was inspired by the
reported outcomes. Bootstrap conditions on the forecast path and does not
refit histories; overlap across training windows and rare ties limit inference.

## Historical evaluation scores

{frame_table(main,columns)}

Team NLL/CRPS are home/away averages; full individual marginals, conditional
nonpush spread/total scores, unconditional H/T/A scores, tie scores and counts
are in metrics.csv. Multiclass Brier is the sum of all three squared errors.
Winner LL/Brier condition on a decisive result; they remain unchanged by design.

## Season stability

{frame_table(annual,['sample','arm','n','joint_nll','team_crps','margin_crps','total_crps','p_tie'])}

Empirical stability: `{json.dumps(emp_stability,sort_keys=True)}`.
The exact joint NLL gain equals the tie-event Bernoulli gain: all improvement
comes from reweighting tie versus decisive mass, not better conditional exact
score prediction. Influential games and all leave-one-week/season checks are
archived. A single tie means unconditional tie calibration remains uncertain.
The observed tie-rate binomial 95% interval is {tie_ci}; this interval is
descriptive under independent equal-rate trials, not a calibrated rare-event model.

## Coverage and calibration

{frame_table(main,['arm','margin_coverage90','margin_width90','total_coverage90','total_width90','home_coverage90','home_width90','away_coverage90','away_width90'])}

All 50/80/90% interval coverage and width values and paired differences are in
the machine-readable files. Equal-tail integer intervals include endpoint mass.
Reliability bins (winner, moneyline, unconditional H/T/A, spread, total and
derived team-location thresholds) include counts and Wilson binomial intervals.
Midpoint PIT deciles are descriptive for discrete distributions; they are not
randomized uniform PIT tests. No calibration map was fitted to evaluation labels.

## Independent betting diagnostics

{frame_table(mainroi,['arm','bets','units','roi','roi_se','market_null'])}

Flat 1u on the most probable decisive winner, ties push; four pick'ems excluded
identically, n=812. Candidate side choices and settlements equal baseline by
construction. Favorite/underdog controls and paired intervals are archived.
Unknown quote timestamps invalidate executable-price or native-forward claims.
Spread/total and actual team-total prices are absent: their ROI is not estimated.
Derived team locations are only diagnostic thresholds, not traded team totals.
No-vig moneyline winner comparisons are included in R000 and unchanged by R001.

## Integrity, failures and limitations

{len(checks)} output checks passed. Focused and capture-test logs are recorded in
research/VALIDATION.md after execution. No silent fallback is introduced.
Baseline covariance warm-up is inherited, logged, and absent in reported years.
Tie fit uses {int(a.training_games.min())}-{int(a.training_games.max())} prior games.
The constant within-week tie rate omits spread/total dependence and rule regimes;
the six-season window may mix overtime eras. Prior-week features are logical,
not proof the historical market inputs were available. The smooth lattice still
permits unusual football score pairs. Score cap and empirical sparsity remain.
This archive is not a full repository checkout; prior 517-test claims are not
reasserted as newly verified. No production files or external ledgers changed.

## Reproduce and next step

From the bundle root:

```bash
OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals.py --output-dir research/experiments/R000_reproduction
OPENBLAS_NUM_THREADS=1 python research/joint_market_residuals_report.py --output-dir research/experiments/R000_reproduction
OPENBLAS_NUM_THREADS=1 python research/tie_hurdle.py
OPENBLAS_NUM_THREADS=1 python research/tie_hurdle_report.py
OPENBLAS_NUM_THREADS=1 python -m pytest tests -q
```

Highest-priority unresolved hypothesis: explicitly resolve tied score states
into plausible overtime final scores using a fixed transition model, preserving
joint coherence. Register it as R002 and obtain fresh evaluation. Do not optimize
transition rules on these results. Phase 2 residual experiments remain queued.
The forward capture implementation is offline infrastructure only; no genuine
provider quotes or prospective outcomes have been collected by this run.
'''
    (OUT/'REPORT.md').write_text(report)
    print(json.dumps(dict(primary=primary,decision=decision),indent=2))


if __name__=='__main__':run()
