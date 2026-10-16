"""Full fixed-comparator reports for R002/R003, including negative findings."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

import joint_market_residuals as j
import joint_market_residuals_report as old
import tie_hurdle_report as helpers
import distribution_ablations as d

LOSSES=helpers.LOSSES
INTERVALS=helpers.INTERVALS
METRICS=LOSSES+INTERVALS


def dump(out,name,x):
    (out/name).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')


def settings(experiment):
    if experiment=='R002':return 'R002_ot_transitions','R001_tie_hurdle',['R001_tie_hurdle','A_market']
    if experiment=='R003':return 'R003_score_support','A_market',['A_market']
    raise ValueError('Unknown experiment')


def validate(experiment,f,out):
    pack=np.load(out/'marginal_probabilities.npz',allow_pickle=False)
    ids=list(pack['game_ids']);audit=pd.read_csv(out/'transform_audit.csv')
    provenance=json.loads((out/'provenance.json').read_text())
    io_audit=json.loads((out/'io_integrity.json').read_text())
    checks=dict(no_duplicate_predictions=not f.duplicated(['arm','game_id']).any(),
        game_sets_identical=all(set(g.game_id)==set(ids) for _,g in f.groupby('arm')),
        normalized_nonnegative_marginals=all(np.all(pack[k]>=0) and np.allclose(pack[k].sum(axis=1),1,atol=2e-6) for k in pack.files if '__' in k),
        outcome_probabilities_sum=bool(np.allclose(f.p_home+f.p_tie+f.p_away,1,atol=1e-12)),
        spread_total_probability_sums=bool(np.allclose(f.cover_win+f.cover_push+f.cover_lose,1) and np.allclose(f.over_win+f.over_push+f.over_lose,1)),
        coherent_means=bool(np.allclose(f.total_mean,f.home_mean+f.away_mean) and np.allclose(f.margin_mean,f.home_mean-f.away_mean)),
        pmf_row_alignment=True,
        prior_week_fit_cutoffs=all((x.training_max_season,x.training_max_week)<(x.season,x.week) for x in audit.itertuples()),
        sample_counts=all(len(g)==816 for _,g in f[f.season.between(2023,2025)].groupby('arm')),
        all_game_counts=all(len(g)==2462 for _,g in f.groupby('arm')),
        baseline_reconstruction=provenance['baseline_reconstruction_max_abs_error']<=1e-10,
        protocol_hash_unchanged=provenance['protocol_sha256']==j.sha256(out/'PROTOCOL.md'),
        full_joint_checks_passed=provenance['full_joint_transform_checked_every_game'],
        positive_realized_probability=provenance['realized_score_positive_probability_every_game'],
        complete_prediction_rows=io_audit['gzip_eof_verified'] and io_audit['rows']==len(f),
        serialized_prediction_hash=hashlib.sha256((out/'predictions.csv.gz').read_bytes()).hexdigest()==io_audit['gzip_sha256'])
    for arm,g in f.groupby('arm'):
        g=g.set_index('game_id').loc[ids]
        checks['pmf_row_alignment'] &= bool(np.allclose(pack[arm+'__margin'][:,pack['margin_support']>0].sum(axis=1),g.p_home,atol=1e-6))
    info,primary_base,_=settings(experiment)
    for shape in j.SHAPES:
        b=f[f.arm==shape+'__'+primary_base].set_index('game_id').sort_index()
        c=f[f.arm==shape+'__'+info].set_index('game_id').sort_index()
        if experiment=='R002':
            checks[shape+'_tie_and_winner_invariant']=bool(np.allclose(b.p_tie,c.p_tie,atol=1e-14,rtol=0) and np.allclose(b.p_home_non_tie,c.p_home_non_tie,atol=1e-14,rtol=0))
            checks[shape+'_moneyline_settlements_invariant']=bool(np.allclose(b.model_units,c.model_units,equal_nan=True))
            a=audit[audit['shape']==shape]
            checks[shape+'_all_excess_mass_accounted']=bool(np.allclose(a.excess_tie_mass,a.transported_mass+a.untransportable_mass,atol=1e-14,rtol=0))
        else:
            a=audit[audit['shape']==shape].set_index('game_id').loc[b.index]
            checks[shape+'_analytic_nll_identity']=bool(np.allclose(b.joint_nll-c.joint_nll,-np.log1p(-a.removed_mass),atol=1e-12,rtol=0))
            mask=np.load(out/'support_mask.npy',allow_pickle=False)
            checks[shape+'_observations_supported']=bool(mask[c.home_score.to_numpy(int),c.away_score.to_numpy(int)].all())
    checks={k:bool(v) for k,v in checks.items()}
    dump(out,'verification.json',checks)
    if not all(checks.values()):raise AssertionError(checks)
    return checks


def summaries(sub,sample):
    rows=[]
    for arm,g in sub.groupby('arm'):
        row=dict(sample=sample,arm=arm,n=len(g),winner_n=int(g.win_ll.notna().sum()),
            p_tie=float(g.p_tie.mean()),ties=int((g.home_score==g.away_score).sum()))
        row.update({m:float(g[m].mean()) for m in METRICS})
        row.update({m+'_n':int(g[m].notna().sum()) for m in LOSSES})
        rows.append(row)
    return rows


def run(experiment,out=None):
    out=Path(out or j.ROOT/'research/experiments'/d.EXPERIMENTS[experiment])
    f=pd.read_csv(out/'predictions.csv.gz');checks=validate(experiment,f,out)
    candidate,mainbase,comparators=settings(experiment)
    masks=dict(historical_2023_25=f.season.between(2023,2025),earlier_2017_22=f.season.between(2017,2022),diagnostic_2026=f.season==2026)
    masks.update({f'season_{year}':f.season==year for year in sorted(f.season.unique())})
    metrics=[];pairs=[];stability=[];influence=[];calibration=[];pits=[];returns=[];ml_comparisons=[]
    for sample,mask in masks.items():
        sub=f[mask];metrics.extend(summaries(sub,sample))
        for shape in j.SHAPES:
            c=sub[sub.arm==shape+'__'+candidate].set_index('game_id').sort_index()
            for comparator in comparators:
                b=sub[sub.arm==shape+'__'+comparator].set_index('game_id').sort_index()
                if not c.index.equals(b.index):raise AssertionError('Unpaired comparison')
                differences=b[METRICS].to_numpy()-c[METRICS].to_numpy()
                draws=old.week_bootstrap(differences,b.season,b.week)
                for k,m in enumerate(METRICS):
                    primary=sample=='historical_2023_25' and shape=='empirical' and comparator==mainbase and m=='joint_nll'
                    pairs.append(dict(sample=sample,shape=shape,comparator=comparator,metric=m,primary=primary,
                        n=int(np.isfinite(differences[:,k]).sum()),baseline=float(b[m].mean()),candidate=float(c[m].mean()),
                        gain=float(np.nanmean(differences[:,k])),ci95=old.interval(draws[:,k]),
                        two_contrast_ci=old.interval(draws[:,k],.975) if primary else None,
                        nine_contrast_sensitivity_ci=old.interval(draws[:,k],1-.05/9) if primary else None))
                if sample=='historical_2023_25':
                    gain=b.joint_nll-c.joint_nll
                    weekly=pd.DataFrame(dict(season=b.season,week=b.week,gain=gain)).groupby(['season','week']).gain.agg(['sum','count'])
                    loo=(gain.sum()-weekly['sum'])/(len(gain)-weekly['count'])
                    annual=gain.groupby(b.season).mean()
                    stability.append(dict(shape=shape,comparator=comparator,
                        annual_gain={str(k):float(v) for k,v in annual.items()},
                        positive_game_fraction=float((gain>0).mean()),
                        leave_one_week_out_gain_range=[float(loo.min()),float(loo.max())],
                        leave_one_season_out_gain={str(y):float(gain[b.season!=y].mean()) for y in annual.index},
                        top_ten_absolute_contribution_fraction=float(gain.abs().nlargest(10).sum()/gain.abs().sum()) if gain.abs().sum()>0 else 0.))
                    for gid in gain.abs().nlargest(10).index:
                        influence.append(dict(shape=shape,comparator=comparator,game_id=gid,gain=float(gain.loc[gid]),home_score=int(c.loc[gid,'home_score']),away_score=int(c.loc[gid,'away_score'])))
        if not sample.startswith('season_'):
            calibration.extend(dict(sample=sample,**row) for row in helpers.reliability(sub))
            returns.extend(old.roi_rows(sub,sample))
            for arm,g in sub.groupby('arm'):
                for target in ['home','away','margin','total']:
                    hist,_=np.histogram(g[target+'_pit_mid'],bins=np.linspace(0,1,11))
                    pits.append(dict(sample=sample,arm=arm,target=target,n=len(g),midpoint_pit_deciles=hist.tolist(),note='Discrete midpoint PIT is not exactly uniform.'))
                decisive=g[g.win_ll.notna()&g.market_win_ll.notna()]
                values=np.column_stack([decisive.market_win_ll-decisive.win_ll,decisive.market_win_brier-decisive.win_brier])
                draws=old.week_bootstrap(values,decisive.season,decisive.week)
                ml_comparisons.append(dict(sample=sample,arm=arm,n=len(decisive),
                    market_ll=float(decisive.market_win_ll.mean()),model_ll=float(decisive.win_ll.mean()),
                    ll_gain=float(values[:,0].mean()),ll_ci95=old.interval(draws[:,0]),
                    brier_gain=float(values[:,1].mean()),brier_ci95=old.interval(draws[:,1])))
    for name,x in [('metrics.json',metrics),('paired_comparisons.json',pairs),('stability.json',stability),
        ('influential_games.json',influence),('reliability.json',calibration),('pit_diagnostics.json',pits),
        ('moneyline_diagnostics.json',returns),('moneyline_probability_comparisons.json',ml_comparisons)]:dump(out,name,x)
    pd.DataFrame(metrics).to_csv(out/'metrics.csv',index=False)
    pd.DataFrame(pairs).to_csv(out/'candidate_vs_baseline.csv',index=False)
    primary=next(x for x in pairs if x['primary'])
    primaries=[x for x in pairs if x['sample']=='historical_2023_25' and x['shape']=='empirical' and x['comparator']==mainbase]
    s=next(x for x in stability if x['shape']=='empirical' and x['comparator']==mainbase)
    violations=[x['metric'] for x in primaries if x['metric'].endswith(('_nll','_crps')) and x['metric'] not in ['joint_nll','outcome_nll'] and x['gain']<-.01]
    winner_violations=[x['metric'] for x in primaries if x['metric'] in ['win_ll','win_brier'] and x['gain']<-.001]
    gates=dict(practical_gain=primary['gain']>=.005,adjusted_interval_positive=primary['two_contrast_ci'][0]>0,
        all_seasons_positive=all(v>0 for v in s['annual_gain'].values()),
        secondary_tolerances=not violations and not winner_violations,integrity=all(checks.values()))
    supported=all(gates.values())
    decision=dict(experiment=experiment,historical_hypothesis_supported=supported,gates=gates,
        recommendation='retain for research' if supported else 'reject advancement of this fixed candidate',
        secondary_violations=violations+winner_violations,independent_validation=False,
        production_promotion=False,forward_consideration=supported,
        mechanism_identified=False if experiment=='R002' else None,
        limitations=['Previously exposed historical sample; unknown quote timestamps.',
            'No prospective outcomes or executable-price claims.',
            'No regulation/OT labels to identify a mechanistic overtime process.' if experiment=='R002' else
            'Reachability conditioning alone does not model frequencies of common football scores.'])
    dump(out,'decision.json',decision)
    audit=pd.read_csv(out/'transform_audit.csv');main_audit=audit[audit.season.between(2023,2025)]
    numeric=['raw_tie_mass','target_tie_rate','excess_tie_mass','transported_mass','untransportable_mass','near_cap_renormalized_mass','no_excess'] if experiment=='R002' else ['removed_mass','valid_one_point_mass','excluded_cells']
    transform=[]
    for shape,g in main_audit.groupby('shape'):
        row=dict(shape=shape,n=len(g))
        row.update({m+'_mean':float(g[m].mean()) for m in numeric})
        row.update({m+'_max':float(g[m].max()) for m in numeric})
        transform.append(row)
    dump(out,'transform_summary.json',transform)
    main=pd.DataFrame(metrics).query("sample=='historical_2023_25'")
    annual=pd.DataFrame(metrics).query("sample in ['season_2023','season_2024','season_2025']")
    roi=pd.DataFrame([x for x in returns if x['basis']=='historical_2023_25'])
    description=(
        'Replace R001\'s uniform decisive redistribution of excess raw tie mass with equal-weight +2/+3/+6 terminal score transitions. Prior-week tie rate and conditional winner probability stay equal to R001. No OT frequencies are estimated.'
        if experiment=='R002' else
        'Condition raw market-only PMFs on an additive joint scoring reachability mask. Safety/field-goal/TD/try generators include rare one-point safety points awarded to the opponent after a touchdown. No R001/R002 transform is combined with this candidate.')
    limitation=(
        'The frozen data contain only final scores, so this is an overtime-inspired mass-transport diagnostic, not a fitted regulation-to-OT simulator. The underlying raw PMF already includes overtime. The fixed terminal kernel omits many valid multi-score endings and has deliberately unestimated weights. Cap-boundary mass is explicitly retained in the R001 decisive shape and logged; near-cap representable increments are renormalized.'
        if experiment=='R002' else
        'The support mask comes from a fixed scoring abstraction, not observed score frequency. It keeps valid rare (6,1)/(1,6) outcomes. Conditioning cannot claim a comprehensive possession/clock or administrative-rule model. Any unsupported realized observation would abort the run, with no NLL floor or row deletion. Exact-score improvement on supported outcomes is algebraically -log(1-removed_mass); a tiny positive effect is therefore not evidence of learned scoring patterns.')
    report=f'''# {experiment} - {'Explicit overtime-inspired transitions' if experiment=='R002' else 'Independent football-score support'}

**Recommendation: {decision['recommendation']}.** Narrow historical hypothesis
{'supported' if supported else 'fails the locked advancement rule'}; independent validation absent.

## Research question and specifications

{description}

Primary comparator: empirical {mainbase}; smooth is secondary. See PROTOCOL.md
and registration_record.json for the design committed before either new run.
No hyperparameter search, training-grid selection or ROI-based selection.
No candidate was revised after viewing its historical results.

## Inputs, cutoff and periods

Exactly the R000 frozen schedule/total input and coefficient/history files from
NFL-MODEL base e93b936. No outcomes, lines, quotes or production data changed.
Original means/covariances/empirical neighbors use strictly earlier weeks.
Tie estimation uses a prior-week, six-season unweighted Jeffreys Beta(.5,.5)
rate; the support mask has no fitted parameters. Training begins 2013, original
mean-error prequential fitting begins 2015, evaluated forecasts begin 2017.
2017-22: 1,567 exposed supplementary games per arm; 2023-25: 816 historical
comparison games, 272 per season, 815 decisive winner scores; 2026 W1-5: 79
separate diagnostic games. Every arm has 2,462 predictions. All seasons are
already exposed; no independent validation/test or selection split exists.
The existing prior-week training procedure may fit on earlier weeks within an
evaluation season. Market capture timestamps are unknown: actual pregame
availability cannot be verified. This is conditional-on-input development.

## Primary paired comparison and multiplicity

Joint-NLL gain = **{primary['gain']:.9f} nats/game**, baseline {primary['baseline']:.9f},
candidate {primary['candidate']:.9f}, n={primary['n']}.
95% interval: {primary['ci95']}.
Two-new-contrast adjusted 97.5% interval: **{primary['two_contrast_ci']}**.
Nine-contrast sensitivity interval: {primary['nine_contrast_sensitivity_ci']}.
10,000 paired whole-week resamples within season, seed 20261016; game-weighted
means with the resampled game denominator. Primary advancement requires >=.005
nats/game and an adjusted positive lower bound. Secondary scores, raw-A versus
R002 and smooth results are descriptive. The nine-comparison sensitivity only
covers the enumerated family; no interval eliminates prior research exposure.
The bootstrap holds forecasts fixed, not refitting overlapping training windows.

## Joint, marginal and event predictive scores

{helpers.frame_table(main,['arm','n','joint_nll','home_nll','away_nll','margin_nll','total_nll','home_crps','away_crps','margin_crps','total_crps','win_ll','win_brier','outcome_nll','p_tie'])}

Team NLL/CRPS are also reported as home/away averages. Natural-log losses;
multiclass H/T/A Brier sums three squared errors. Binary winner scores condition
on a decisive outcome; spread/total binary scores condition on a nonpush.
metrics.csv includes all metrics and valid counts, including tie LL/Brier and
derived team-location threshold diagnostics. Those locations are not traded
team-total quotes. candidate_vs_baseline.csv includes paired CIs for every
metric, coverage and width. Positive loss gain favors the candidate; coverage
and width differences are not themselves model rankings.

## Annual stability and influences

{helpers.frame_table(annual,['sample','arm','n','joint_nll','team_crps','margin_crps','total_crps','win_ll','p_tie'])}

Primary stability: `{json.dumps(s,sort_keys=True)}`.
Other shapes/comparators, leave-week/season estimates and largest observations
are retained in stability.json and influential_games.json. {limitation}

## Coverage and calibration

{helpers.frame_table(main,['arm','margin_coverage90','margin_width90','total_coverage90','total_width90','home_coverage90','home_width90','away_coverage90','away_width90'])}

50/80/90% coverage/width and paired differences are in metrics/paired outputs.
Integer equal-tail intervals include endpoint mass. Reliability bins include
counts, predicted/observed frequencies and Wilson binomial intervals for winner,
no-vig moneyline, H/T/A, spread, total and derived team-location thresholds.
Midpoint PIT deciles are descriptive for discrete distributions, not an exact
uniformity test. Only one tie in the primary sample: rare-event calibration
cannot be established. No post-result calibration map is fitted.

## Independent hypothetical moneyline diagnostics

{helpers.frame_table(roi,['arm','bets','units','roi','roi_se','market_null'])}

Flat 1u on the more probable decisive winner, tie pushes, four market pick'ems
excluded identically: 812 primary bets. Favorite/underdog same-row controls,
paired ROI intervals and negative-hold null are in moneyline_diagnostics.json.
No-vig moneyline proper-score comparisons are in a separate JSON. ROI is never
used for candidate selection. Missing timestamp verification prevents execution
claims. Actual spread/total/team-total prices are absent; their ROI is unavailable.

## Reproducibility and failure record

{len(checks)} integrity checks pass: normalized/coherent PMFs, aligned identical
game sets, strict prior-week cutoffs, positive realized probability and unchanged
protocol hash; experiment-specific invariants are in verification.json.
Full joint nonnegativity/normalization is asserted for every transformed game.
Baselines reconstructed to max error {json.loads((out/'provenance.json').read_text())['baseline_reconstruction_max_abs_error']:.3g}.
Source/input/protocol hashes are archived. Tests and independent rerun records
are attached separately; a report is not a claim the full production suite ran.
R003's initial compressed predictions lacked a valid end-of-stream marker, so
its first report and repeat check failed before usable metrics were accepted.
The corrupt output and logs remain under R003/failures/initial_write/. The
root cause was not established. An engineering-only serialization revision now
builds and verifies the full gzip stream, fsyncs and atomically publishes it,
then validates the published bytes. The repaired R003 and its independent
repeat pass; R002 canonical prediction CSV is unchanged after that revision.
This is not a revised candidate, parameter search or independent second test.
No production files, deployed pages or betting ledgers are present in this
isolated workspace. Failures and every negative metric remain in this directory.

Locked decision gates: `{json.dumps(gates,sort_keys=True)}`.
Secondary tolerance violations: {violations+winner_violations}.
No native prospective samples have been collected. No production promotion.

## Commands and next unresolved question

```bash
OPENBLAS_NUM_THREADS=1 python research/distribution_ablations.py {experiment}
OPENBLAS_NUM_THREADS=1 python research/distribution_ablation_report.py {experiment}
OPENBLAS_NUM_THREADS=1 python -m pytest tests -q
```

Rule provenance: research/RULE_SOURCES.json, official NFL Rule 11 (scoring/try)
and Rule 16 (current overtime context), read 2026-10-16. The reachability mask
and kernel are mathematical modeling choices, not tables of NFL probabilities.

Next unresolved hypothesis: {'execute the separately registered R003 ablation; a genuine mechanistic OT model additionally requires regulation/possession labels and a fresh evaluation cohort' if experiment=='R002' else 'test one preregistered football-score frequency model, with adequate rare-event/tail support and fresh independent evaluation; do not tune this mask using the observed gain'}.
'''
    (out/'REPORT.md').write_text(report)
    print(json.dumps(dict(primary=primary,decision=decision),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('experiment',choices=list(d.EXPERIMENTS))
    args=parser.parse_args();run(args.experiment)
