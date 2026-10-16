"""R003 plain ATS replay at user-assumed -110 on both sides; no price search."""
from pathlib import Path

import numpy as np
import pandas as pd

import schedule_context_empirical as s

m=s.m
OUT=m.j.ROOT/'research/plain_ats_110_results'
INPUT=m.OUT.parent/'R003_pooled_travel/predictions.csv.gz'
POLICY='R003-PLAIN-ATS-110-v1'
PROFIT=10/11


def choose(home_cover,push,away_cover):
    """Outcome-free decision at the forecast line, 1u risk, pushes refunded."""
    probabilities=np.asarray([home_cover,push,away_cover],float)
    if (not np.isfinite(probabilities).all() or (probabilities<0).any()
            or not np.isclose(probabilities.sum(),1,atol=1e-12,rtol=0)):
        raise ValueError('Cover/push/loss probabilities must sum to one')
    home_ev=PROFIT*home_cover-away_cover
    away_ev=PROFIT*away_cover-home_cover
    side=('home' if home_ev>=away_ev else 'away') if max(home_ev,away_ev)>1e-12 else 'pass'
    return dict(side=side,home_ev=float(home_ev),away_ev=float(away_ev),
                selected_ev=float(max(home_ev,away_ev)) if side!='pass' else 0.)


def settle(side,home_margin,line):
    if side not in ['home','away','pass']:raise ValueError('Unknown side')
    if not np.isfinite([home_margin,line]).all():raise ValueError('Finite result and line required')
    if side=='pass' or home_margin==line:return 0.
    covered=home_margin>line if side=='home' else home_margin<line
    return PROFIT if covered else -1.


def run():
    OUT.mkdir(exist_ok=True)
    source=pd.read_csv(INPUT,low_memory=False)
    f=source[source.arm.eq('plain')].copy()
    if f.game_id.duplicated().any():raise ValueError('Duplicate forecasts')
    decisions=pd.DataFrame([choose(r.cover_win,r.cover_push,r.cover_lose) for r in f.itertuples()],index=f.index)
    f=pd.concat([f,decisions],axis=1)
    margin=f.home_score-f.away_score
    f['ats_units']=[settle(side,result,line) for side,result,line in zip(f.side,margin,f.spread_line)]
    f['home_control_units']=[settle('home',result,line) for result,line in zip(margin,f.spread_line)]
    f['favorite_control_units']=[settle('home' if line>=0 else 'away',result,line) for result,line in zip(margin,f.spread_line)]
    f['selected_cover_probability']=np.where(f.side.eq('home'),f.cover_win,np.where(f.side.eq('away'),f.cover_lose,np.nan))
    f['selected_conditional_probability']=np.where(f.side.ne('pass'),f.selected_cover_probability/(1-f.cover_push),np.nan)
    f['selected_handicap']=np.where(f.side.eq('home'),-f.spread_line,np.where(f.side.eq('away'),f.spread_line,np.nan))
    f['selected_team']=np.where(f.side.eq('home'),f.home_team,np.where(f.side.eq('away'),f.away_team,''))
    f['odds']=-110
    summaries=[]
    bases=[('2023-25',f.season.between(2023,2025)),('2017-22',f.season.between(2017,2022)),
           ('2026 diagnostic',f.season.eq(2026))]+[(str(y),f.season.eq(y)) for y in sorted(f.season.unique())]
    for basis,mask in bases:
        cohort=f[mask];g=cohort[cohort.side.ne('pass')]
        values=np.column_stack([g.ats_units,g.ats_units-g.favorite_control_units])
        boot=s.b.week_bootstrap(values,g.season,g.week)
        wins=int((g.ats_units>0).sum());losses=int((g.ats_units<0).sum());pushes=int((g.ats_units==0).sum())
        summaries.append(dict(basis=basis,games=len(cohort),bets=len(g),passes=int(cohort.side.eq('pass').sum()),
            wins=wins,losses=losses,pushes=pushes,units=float(g.ats_units.sum()),roi=float(g.ats_units.mean()),
            roi_se=float(g.ats_units.std(ddof=1)/np.sqrt(len(g))),roi_ci95=s.b.interval(boot[:,0]),
            favorite_control_units=float(g.favorite_control_units.sum()),home_control_units=float(g.home_control_units.sum()),
            paired_favorite_gain_ci95=s.b.interval(boot[:,1]),
            fair_ats_null_roi=-1/22*(wins+losses)/len(g),
            model_expected_units=float(g.selected_ev.sum()),
            mean_conditional_cover_probability=float(g.selected_conditional_probability.mean()),
            realized_decisive_cover_rate=wins/(wins+losses),cover_ll=float(g.cover_ll.mean()),
            fair_50pct_cover_ll=float(np.log(2))))
    cols=['game_id','season','week','home_team','away_team','spread_line','cover_win','cover_push','cover_lose',
        'home_ev','away_ev','side','selected_team','selected_handicap','odds','selected_ev',
        'selected_conditional_probability','home_score','away_score','ats_units','favorite_control_units','final_ess']
    f[cols].to_csv(OUT/'decisions.csv',index=False)
    m.dump(OUT/'summary.json',summaries)
    paths=[INPUT,Path(__file__),Path(s.__file__),m.j.ROOT/'research/joint_market_residuals_report.py']
    m.dump(OUT/'provenance.json',dict(policy=POLICY,plain_configuration='direct_ref_h2_t3_p0',
        odds_basis='User-specified -110 on both sides; assumed uniformly in retrospective replay, not independently archived quotes',
        strategy='At most one 1u risk bet at forecast line; highest strictly positive model EV, otherwise pass',
        thresholds_searched=False,model_refitted=False,production_changed=False,independent_validation=False,
        favorite_control='Spread favorite on identical selected games; home at zero spread',
        null='Fair 50/50 conditional ATS probability, -4.545% per decisive bet; scaled by observed non-push fraction',
        bootstrap='10000 paired whole-week draws within season, seed 20261016',
        hashes={str(p.resolve().relative_to(m.j.ROOT)):m.j.sha256(p) for p in paths}))
    lines=['# R003 plain ATS at assumed −110 each side','',
        '**Retrospective scenario, not verified historical spread quotes or forward evidence.**',
        'Plain probabilities are unchanged. No thresholds are searched or fitted.', '',
        'Risk 1u; a win earns 10/11u, a loss costs 1u, a push refunds the stake.',
        'EV(home)=(10/11)*P(home cover)−P(away cover); reverse for away.',
        'Bet only if the selected conditional-on-no-push cover probability exceeds 11/21 = 52.38095%; otherwise pass.', '',
        '| Basis | Bets | Passes | W–L–P | Units | ROI ± SE | Same-row spread favorite | Fair ATS null |',
        '|---|---:|---:|---|---:|---:|---:|---:|']
    for r in summaries[:3]:
        lines.append(f"| {r['basis']} | {r['bets']} | {r['passes']} | {r['wins']}–{r['losses']}–{r['pushes']} | {r['units']:+.3f} | {100*r['roi']:+.2f}% ±{100*r['roi_se']:.2f} pp | {r['favorite_control_units']:+.3f}u | {100*r['fair_ats_null_roi']:.2f}% |")
    main=summaries[0]
    lines+=['',f"Main ROI 95% week-bootstrap interval: {main['roi_ci95']}. Mean predicted conditional cover probability {100*main['mean_conditional_cover_probability']:.2f}%; realized {100*main['realized_decisive_cover_rate']:.2f}%.",
        f"Selected-game cover log loss {main['cover_ll']:.6f}, versus {np.log(2):.6f} for a fair 50/50 ATS forecast.",
        '', 'Capability to choose a side does not establish calibrated cover probabilities or profitable value. Frozen retrospective line timestamps remain unaudited. This extends the user-specified price scenario to historical lines; it does not certify that both historical offers were available together at -110.',
        '', 'Moneyline records, original experiments, production and the forward ledger are unchanged. No wagers or live predictions are emitted.',
        '', 'Reproduce: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python research/plain_ats_110.py`','']
    (OUT/'REPORT.md').write_text('\n'.join(lines))
    print('\n'.join(lines))


if __name__=='__main__':run()
