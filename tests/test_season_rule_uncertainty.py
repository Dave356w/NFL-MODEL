"""Paired seasonal inference preserves stakes and the fixed family definition."""
import numpy as np
import pandas as pd
import pytest

from research import season_rule_uncertainty as u


def test_ratio_roi_uses_both_stake_denominators_and_paired_week_covariance():
    left=np.array([1/1.1,np.nan,-1.,0.,1/1.1,np.nan])[:,None]
    right=np.array([0.,1/1.1,np.nan,-1.,1/1.1,0.])[:,None]
    weeks=np.array([1,1,2,2,3,3])
    pack=u.prepare_pack(left,right,weeks,[dict(variant_id='x')],2026)
    row=pack['rows'].iloc[0]
    ml,mr=np.nanmean(left),np.nanmean(right)
    influence=[]
    for week in [1,2,3]:
        a,b=left[weeks==week],right[weeks==week]
        influence.append((np.nansum(a)-ml*np.isfinite(a).sum())/4
                         -(np.nansum(b)-mr*np.isfinite(b).sum())/5)
    assert row.gain==pytest.approx(ml-mr)
    assert row.candidate_stakes==4 and row.benchmark_stakes==5 and row.common_stakes==3
    assert row.cluster_se==pytest.approx(np.sqrt(3/2*np.sum(np.square(influence))))
    assert row.gain!=pytest.approx(np.nansum(left-right)/6)


def test_zero_empirical_variance_and_missing_policy_cannot_certify_improvement():
    left=np.array([[1.,np.nan],[1.,np.nan],[1.,np.nan]])
    right=np.array([[0.,np.nan],[0.,np.nan],[0.,np.nan]])
    pack=u.prepare_pack(left,right,[1,2,3],[dict(variant_id='x'),dict(variant_id='missing')],2026)
    rows=pack['rows']
    assert rows.available.tolist()==[True,False]
    assert not rows.inference_available.any()
    assert rows.pointwise_95_lower.isna().all()


def test_duplicate_frozen_contrast_does_not_create_independent_evidence():
    left=np.array([.2,-.3,.5,-.1,.8,-.4])[:,None]
    right=np.zeros_like(left)
    weeks=[1,1,2,2,3,3]
    one=u.prepare_pack(left,right,weeks,[dict(variant_id='a')],2025)
    two=u.prepare_pack(np.repeat(left,2,axis=1),np.repeat(right,2,axis=1),weeks,
        [dict(variant_id='a'),dict(variant_id='same')],2025)
    _,a=u.simultaneous_intervals([one],repetitions=199,seed=91)
    rows,b=u.simultaneous_intervals([two],repetitions=199,seed=91)
    assert a['simultaneous_critical']==pytest.approx(b['simultaneous_critical'])
    assert rows.simultaneous_95_lower.nunique()==1


def test_missing_median_seasons_remain_coverage_failures():
    rows=[]
    for year in u.YEARS:
        for metric in ['log_loss','brier']:
            for benchmark in ['moneyline','spread_total']:
                rows.append(dict(variant_id='x',metric=metric,path='probability',benchmark=benchmark,
                    season=year,gate=True,available=True,full_coverage=True,
                    gain=.01,simultaneous_95_lower=-.01,weeks=6 if year==2026 else 18))
        for benchmark in ['zero','own_anchor','market_favorite']:
            rows.append(dict(variant_id='x',metric='ats_roi',path='raw',benchmark=benchmark,
                season=year,gate=True,available=True,full_coverage=True,
                gain=.01,simultaneous_95_lower=-.01,weeks=6 if year==2026 else 18))
    variants=pd.DataFrame([dict(id='x',is_control=False)])
    evidence=u.candidate_evidence(pd.DataFrame(rows),variants)
    raw=evidence.loc[evidence.path.eq('raw')].iloc[0]
    median=evidence.loc[evidence.path.eq('own_median')].iloc[0]
    assert raw.point_gate_pass and not raw.simultaneous_gate_pass
    assert not median.point_gate_pass and median.unavailable_comparisons==18
    assert raw.limited_week_seasons=='2026'
    tied=pd.DataFrame(rows)
    tied.loc[tied.metric.eq('ats_roi') & tied.season.eq(2023) & tied.benchmark.eq('market_favorite'),'gain']=1e-18
    checked=u.candidate_evidence(tied,variants)
    assert not checked.loc[checked.path.eq('raw'),'ats_point_gate_pass'].any()


def test_loading_export_uses_side_arrays_to_exclude_zero_unit_skips(tmp_path):
    games=pd.DataFrame(dict(game_id=[f'g{i}' for i in range(12)],
        season=np.repeat(u.YEARS,2),week=[1,2]*6,result=[7.,-3.]*6,spread_line=[0.,3.]*6))
    variants=pd.DataFrame(dict(id=['market:moneyline','market:spread_total','x'],
        is_control=[True,True,False],own_anchor_control_id=['market:moneyline','market:spread_total','market:moneyline']))
    games.to_csv(tmp_path/'games.csv',index=False);variants.to_csv(tmp_path/'variants.csv',index=False)
    units=np.tile([[0.,0.,1/1.1],[-1.,-1.,-1.]],(6,1))
    sides=np.tile([[0.,0.,1.],[1.,1.,1.]],(6,1))
    arrays={}
    for path in u.PATHS:
        arrays['units_'+path]=units.copy();arrays['sides_'+path]=sides.copy()
        if path!='raw':
            arrays['units_'+path][:4]=np.nan;arrays['sides_'+path][:4]=np.nan
    np.savez(tmp_path/'predictions.npz',probabilities=np.tile([.6,.55,.58],(12,1)),
        variant_ids=variants.id.to_numpy(str),game_ids=games.game_id.to_numpy(str),
        favorite_units=np.tile([0.,-1.],6),home_units=np.tile([1/1.1,-1.],6),**arrays)
    packs,_,_=u.load_packs(tmp_path)
    first=packs[0]['rows']
    row=first.loc[first.path.eq('raw')&first.benchmark.eq('own_anchor')].iloc[0]
    assert row.candidate_stakes==2 and row.benchmark_stakes==1 and row.common_stakes==1
    assert row.gain==pytest.approx((1/1.1-1)/2+1)
    favorite=first.loc[first.path.eq('raw')&first.benchmark.eq('market_favorite')].iloc[0]
    assert favorite.benchmark_stakes==1 and favorite.benchmark_value==-1
    assert not first.loc[first.path.eq('own_median'),'full_coverage'].any()
