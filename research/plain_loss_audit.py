"""Descriptive audit of frozen plain forecasts; no model fitting or rule selection."""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import schedule_context_empirical as s

m=s.m
b=s.b
INPUT=m.OUT.parent/'R003_pooled_travel/predictions.csv.gz'
OUT=m.j.ROOT/'research/plain_loss_audit_results'


def enrich(frame):
    f=frame.copy()
    if f.game_id.duplicated().any():raise ValueError('Duplicate plain games')
    if not np.isfinite(f.p_home_non_tie).all() or not f.p_home_non_tie.between(0,1).all():
        raise ValueError('Invalid plain probabilities')
    home=f.p_home_non_tie>.5
    margin=f.home_score-f.away_score
    f['picked_team']=np.where(home,f.home_team,f.away_team)
    f['picked_home']=home
    f['picked_probability']=np.where(home,f.p_home_non_tie,1-f.p_home_non_tie)
    f['picked_market_probability']=np.where(home,f.q,1-f.q)
    f['picked_odds']=np.where(home,f.home_moneyline,f.away_moneyline)
    odds=f.picked_odds.to_numpy(float)
    with np.errstate(divide='ignore',invalid='ignore'):
        f['win_profit']=np.where(odds>0,odds/100,100/-odds)
    f['price_breakeven']=1/(1+f.win_profit)
    f['price_probability_edge']=f.picked_probability-f.price_breakeven
    f['fair_probability_edge']=f.picked_probability-f.picked_market_probability
    f['model_expected_units']=f.picked_probability*(1+f.win_profit)-1
    f['picked_won']=np.where(margin==0,np.nan,np.where(home,margin>0,margin<0).astype(float))
    f['bet_eligible']=f.model_units.notna()
    f['disagrees_with_favorite']=np.where(np.abs(f.q-.5)>1e-12,home!=(f.q>.5),False)
    f['units_vs_favorite']=f.model_units-f.favorite_units
    f['ll_gain_vs_market']=f.market_win_ll-f.win_ll
    f['brier_gain_vs_market']=f.market_win_brier-f.win_brier
    # Verify actual settlement independently; ties push and price pick'ems stay excluded.
    expected=np.where(margin==0,0,np.where(f.picked_won.eq(1),f.win_profit,-1))
    if not np.allclose(f.loc[f.bet_eligible,'model_units'],expected[f.bet_eligible]):
        raise ValueError('Stored settlement mismatch')
    if not np.allclose(f.loc[~f.disagrees_with_favorite & f.bet_eligible,'units_vs_favorite'],0):
        raise ValueError('Identical-side return mismatch')
    f['confidence_band']=pd.cut(f.picked_probability,[.5,.55,.6,.65,.7,.75,.8,1],include_lowest=True)
    f['price_band']=pd.cut(f.picked_odds,[-np.inf,-250,-175,-130,0,150,200,np.inf])
    f['ess_band']=pd.cut(f.final_ess,[0,25,50,100,200,400,np.inf])
    f['total_band']=pd.cut(f.total_line,[0,40,45,50,np.inf])
    f['spread_band']=pd.cut(f.spread_line.abs(),[-.01,3,7,10,np.inf])
    f['edge_band']=pd.cut(f.fair_probability_edge,[-np.inf,-.05,0,.02,.05,.10,np.inf])
    f['departure_band']=pd.cut((f.p_home_non_tie-f.q).abs(),[-1e-12,.02,.05,.10,np.inf])
    f['own_ev_positive']=f.model_expected_units>0
    return f


def aggregate(frame):
    bets=frame[frame.bet_eligible]
    decisive=bets[bets.picked_won.notna()]
    return dict(games=len(frame),bets=len(bets),wins=int((bets.model_units>0).sum()),
        losses=int((bets.model_units<0).sum()),pushes=int((bets.model_units==0).sum()),
        units=float(bets.model_units.sum()),roi=float(bets.model_units.mean()),
        roi_se=float(bets.model_units.std(ddof=1)/np.sqrt(len(bets))) if len(bets)>1 else np.nan,
        favorite_units=float(bets.favorite_units.sum()),units_vs_favorite=float(bets.units_vs_favorite.sum()),
        null_units=float(bets.model_null.sum()),null_roi=float(bets.model_null.mean()),
        own_expected_units=float(bets.model_expected_units.sum()),
        negative_own_ev_bets=int((bets.model_expected_units<=0).sum()),
        mean_picked_probability=float(decisive.picked_probability.mean()),
        mean_picked_market_probability=float(decisive.picked_market_probability.mean()),
        mean_price_breakeven=float(decisive.price_breakeven.mean()),
        observed_win_rate=float(decisive.picked_won.mean()),
        win_ll=float(frame.win_ll.mean()),market_win_ll=float(frame.market_win_ll.mean()),
        ll_gain_vs_market=float(frame.ll_gain_vs_market.mean()),
        win_brier=float(frame.win_brier.mean()),market_win_brier=float(frame.market_win_brier.mean()),
        median_ess=float(frame.final_ess.median()),mean_largest_atom=float(frame.largest_atom.mean()))


def intervals(frame):
    bets=frame.bet_eligible
    cols=dict(roi=frame.model_units,paired_favorite_gain=frame.units_vs_favorite,
        excess_over_null=frame.model_units-frame.model_null,
        return_minus_own_expectation=(frame.model_units-frame.model_expected_units).where(bets),
        ll_gain_vs_market=frame.ll_gain_vs_market,brier_gain_vs_market=frame.brier_gain_vs_market,
        picked_calibration_residual=(frame.picked_won-frame.picked_probability).where(bets),
        picked_market_calibration_residual=(frame.picked_won-frame.picked_market_probability).where(bets))
    boot=b.week_bootstrap(np.column_stack(list(cols.values())),frame.season,frame.week)
    return {key:b.interval(boot[:,i]) for i,key in enumerate(cols)}


def source_influence(dist,history,target):
    if not np.array_equal(dist['source_ids'],history.game_id.to_numpy()):
        raise ValueError('Misaligned history/atoms')
    w=dist['weights'];margin=dist['home']-dist['away']
    h=float(w[margin>0].sum());d=float(w[margin!=0].sum())
    if d<=0:raise ValueError('No decisive historical mass')
    denominator=d-w*(margin!=0)
    valid=denominator>1e-14
    without=(h-w[valid]*(margin[valid]>0))/denominator[valid]
    lo,hi=float(without.min()),float(without.max())
    p=h/d
    blur=float(w@history.spread_line.to_numpy()-target['spread_line'])
    residual=float(w@(history.home_score-history.away_score-history.spread_line).to_numpy())
    return dict(game_id=target['game_id'],single_source_min_p_home=lo,single_source_max_p_home=hi,
        single_source_can_flip=bool(lo<=.5 if p>.5 else hi>.5),
        largest_source_id=str(history.iloc[int(w.argmax())].game_id),largest_source_weight=float(w.max()),
        spread_kernel_blur=blur,total_kernel_blur=float(w@history.total_line.to_numpy()-target['total_line']),
        weighted_historical_margin_residual=residual,
        predicted_margin_minus_line=blur+residual,
        recomputed_p_home=p,recomputed_ess=m.effective(w))


def run(out=OUT):
    out=Path(out).resolve()
    if out.parent!=m.j.ROOT/'research' or not out.name.startswith('plain_loss_audit_results'):
        raise ValueError('Use a separate plain_loss_audit_results directory')
    out.mkdir(exist_ok=True)
    raw=pd.read_csv(INPUT,low_memory=False)
    raw=raw[raw.arm.eq('plain')].copy()
    feature_path=s.OUT/'feature_table.csv.gz'
    features=pd.read_csv(feature_path)
    extra=[c for c in features if c.startswith('feature_') and c not in raw]
    raw=raw.merge(features[['game_id']+extra],on='game_id',validate='one_to_one')
    f=enrich(raw)
    summaries=[];slices=[];value_claims=[]
    bases=[('2023-25',f.season.between(2023,2025)),('2017-22',f.season.between(2017,2022)),
           ('2026 diagnostic',f.season.eq(2026))]
    bases += [(str(y),f.season.eq(y)) for y in sorted(f.season.unique())]
    groups=['price_band','confidence_band','ess_band','total_band','spread_band','edge_band','departure_band',
            'own_ev_positive','disagrees_with_favorite','picked_home']+['feature_'+g for g in s.GROUPS]
    for basis,mask in bases:
        g=f[mask]
        summaries.append(dict(basis=basis,**aggregate(g),intervals95=intervals(g)))
        if basis in ['2023-25','2017-22','2026 diagnostic']:
            for positive in [False,True]:
                z=g[g.own_ev_positive.eq(positive)&g.bet_eligible]
                value_claims.append(dict(basis=basis,own_ev_positive=positive,**aggregate(z),intervals95=intervals(z)))
        for feature in groups:
            for key,z in g.groupby(feature,observed=True,dropna=False):
                slices.append(dict(basis=basis,feature=feature,category=str(key),**aggregate(z)))
    m.dump(out/'summary.json',summaries)
    m.dump(out/'value_claim_audit.json',value_claims)
    pd.DataFrame(slices).to_csv(out/'slices.csv',index=False)
    # Reconstruct plain weights only to inspect source leverage, not change forecasts.
    source=m.load_inputs();influences=[]
    main=f[f.season.between(2023,2025)].copy()
    for _,row in main.iterrows():
        history=m.prior(source,row)
        dist=m.distribution(m.prepare_pool(history,row),s.PLAIN_CONFIG)
        influences.append(source_influence(dist,history,row))
    influence=pd.DataFrame(influences)
    main=main.merge(influence,on='game_id',validate='one_to_one')
    if not np.allclose(main.p_home_non_tie,main.recomputed_p_home,atol=1e-14,rtol=0):
        raise AssertionError('Plain source reconstruction mismatch')
    if not np.allclose(main.margin_mean-main.spread_line,main.predicted_margin_minus_line,atol=1e-12):
        raise AssertionError('Margin decomposition mismatch')
    influence.to_csv(out/'source_influence.csv',index=False)
    selected=['game_id','season','week','home_team','away_team','home_score','away_score','picked_team',
        'picked_odds','picked_probability','picked_market_probability','price_breakeven','model_expected_units',
        'fair_probability_edge','model_units','favorite_units','units_vs_favorite','win_ll','market_win_ll',
        'll_gain_vs_market','final_ess','largest_atom','total_line','spread_line']
    f.loc[f.bet_eligible,selected].sort_values(['season','week','game_id']).to_csv(out/'bet_ledger.csv',index=False)
    main.loc[main.model_units<0,selected].sort_values('picked_probability',ascending=False).to_csv(out/'loss_cases.csv',index=False)
    main.loc[main.bet_eligible&main.disagrees_with_favorite,selected+list(influence.columns[1:])].to_csv(out/'disagreements.csv',index=False)
    main[selected].sort_values('ll_gain_vs_market').to_csv(out/'proper_score_contributions.csv',index=False)
    concentration={}
    for label,mask in [('agree',~main.disagrees_with_favorite),('disagree',main.disagrees_with_favorite),
                       ('all',np.ones(len(main),bool))]:
        g=main[mask&main.bet_eligible]
        concentration[label]=dict(n=len(g),single_source_pick_flips=int(g.single_source_can_flip.sum()),
            median_ess=float(g.final_ess.median()),median_absolute_spread_blur=float(g.spread_kernel_blur.abs().median()),
            max_source_weight=float(g.largest_source_weight.max()))
    # Do not rank individual -1u losses as if some cost more than others.
    # Proper-score contributions, rather than raw loss count, measure model-specific errors.
    total=main.ll_gain_vs_market.sum()
    negative=main[main.ll_gain_vs_market<0].sort_values('ll_gain_vs_market')
    concentration['proper_score']=dict(total_gain=float(total),gross_negative=float(-negative.ll_gain_vs_market.sum()),
        worst_10_share_of_gross_negative=float(negative.head(10).ll_gain_vs_market.sum()/negative.ll_gain_vs_market.sum()),
        annual_gains={str(y):float(g.ll_gain_vs_market.mean()) for y,g in main.groupby('season')},
        leave_one_season_gain={str(y):float(main.loc[main.season!=y,'ll_gain_vs_market'].mean()) for y in sorted(main.season.unique())})
    m.dump(out/'concentration.json',concentration)
    shape={}
    for target in ['home','away','margin','total']:
        shape[target]={f'coverage{level}':float(main[f'{target}_coverage{level}'].mean()) for level in [50,80,90]}
    shape.update(predicted_tie=float(main.p_tie.mean()),observed_tie=float((main.home_score==main.away_score).mean()),
        predicted_margin3=float(main.margin3_probability.mean()),observed_margin3=float(((main.home_score-main.away_score).abs()==3).mean()),
        predicted_margin7=float(main.margin7_probability.mean()),observed_margin7=float(((main.home_score-main.away_score).abs()==7).mean()))
    m.dump(out/'distribution_shape.json',shape)
    paths=[INPUT,feature_path,m.INPUT,Path(__file__),Path(m.__file__),Path(s.__file__),
           m.j.ROOT/'data/forward_predictions.jsonl',m.j.ROOT/'data/ledger_report.txt']
    m.dump(out/'provenance.json',dict(basis='Exposed retrospective plain MC2 walk-forward records; not native forward ledger',
        configuration='direct_ref_h2_t3_p0',selection='None; frozen plain arm only',
        all_slices_posthoc=True,models_fitted=False,rules_adopted=False,production_changed=False,
        bootstrap='10000 paired whole-week draws within season, seed 20261016; conditional on existing forecasts',
        hashes={str(p.resolve().relative_to(m.j.ROOT)):m.j.sha256(p) for p in paths},
        caveats=['Conditional decisive-game probabilities and quote-null convention; ties push in returns',
                 'Historical quote and schedule availability timestamps are unaudited',
                 'Many descriptive slices; no subgroup is an independently validated rule',
                 'Removing one source game is an influence diagnostic, not a confidence interval']))
    print(m.safe_json(summaries[:3]))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=OUT)
    run(parser.parse_args().output_dir)
