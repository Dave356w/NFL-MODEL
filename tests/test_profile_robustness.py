import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import profile_robustness as r


def test_prior_is_already_present_and_extra_moves_to_league():
    a=r.rate(800.,100.,200.,40.,0.)
    assert a==pytest.approx(1600/260)
    b=r.rate(800.,100.,200.,40.,4.)
    assert 5.<b<a
    assert r.rate(500.,100.,200.,40.,12.)==pytest.approx(5.)
    with pytest.raises(ValueError):r.rate(1.,1.,1.,1.,-1.)


def test_bounded_context_is_symmetric_and_limits_extrapolation():
    cols=['pass_ho','pass_ad','pass_ao','pass_hd']
    f=pd.DataFrame([[3.,-4.,1.2,-.5],[1.2,-.5,3.,-4.]],columns=cols)
    d=r.contexts(f,2.)
    assert abs(d[cols].to_numpy()).max()==2.
    assert d.pass_product.iloc[0]==pytest.approx(-3.4)
    for c in r.s.CONTEXTS:assert d[c].iloc[0]==pytest.approx(-d[c].iloc[1])
    assert d.pass_1sd_pn.iloc[0]==1.
    with pytest.raises(ValueError):r.contexts(f,1.)


def test_no_bound_preserves_formula_and_inactive_hinges():
    f=pd.DataFrame([[.2,.3,-.7,.8]],columns=['pass_ho','pass_ad','pass_ao','pass_hd'])
    d=r.contexts(f)
    assert d.pass_product.iloc[0]==pytest.approx(.62)
    assert (d[r.s.CONTEXTS[1:]]==0.).all().all()


def test_feature_normalization_does_not_see_future_statistics():
    # Alter all sufficient statistics for a future week; earlier features unchanged.
    f=pd.read_csv(r.ROOT/'research/shrinkage_results/frozen_training_features.csv.gz')
    stats=pd.read_csv(r.ROOT/'research/profile_robustness_results/passing_sufficient_statistics.csv.gz')
    subset=f[f.season.between(2021,2023)].reset_index(drop=True)
    ids=subset.loc[(subset.season==2023)&(subset.week>=8),'game_id']
    altered=stats.copy();altered.loc[altered.game_id.isin(ids),'numerator']*=100
    a,_=r.features(subset,stats,4.,2.);b,_=r.features(subset,altered,4.,2.)
    mask=r.m.before(subset,2023,8)
    cols=[f'd__{role}__rates_core__{r.STAT}' for role in ('for','allowed')]+r.s.CONTEXTS
    assert np.allclose(a.loc[mask,cols],b.loc[mask,cols],equal_nan=True)


def test_research_rejects_protected_outputs():
    with pytest.raises(ValueError):r.run(r.ROOT/'data'/'test')


def test_future_box_scores_cannot_change_prior_week_profiles():
    rows=[]
    for week in (1,2,3):
        for team,opp in [('SF','SEA'),('SEA','SF')]:
            rows.append({**{c:10. for c in r.m.COUNTS},'season':2023,'week':week,
                         'game_id':f'2023_{week:02}_SF_SEA','team':team,'opponent':opp})
    box=pd.DataFrame(rows);box['net_yards']=box.net_pass_yards+box.rush_yards
    f=pd.DataFrame([{'game_id':'2023_02_SF_SEA','season':2023,'week':2,'home':'SEA','away':'SF'}])
    changed=box.copy();changed.loc[~r.m.before(changed,2023,2),'net_pass_yards']=9999.;changed['net_yards']=changed.net_pass_yards+changed.rush_yards
    a=r.build_statistics(f,box);b=r.build_statistics(f,changed)
    pd.testing.assert_frame_equal(a,b)
    assert (a.max_source_week==1).all()


def test_frozen_statistics_cutoffs_and_support():
    f=pd.read_csv(r.ROOT/'research/shrinkage_results/frozen_training_features.csv.gz')
    stats=pd.read_csv(r.ROOT/'research/profile_robustness_results/passing_sufficient_statistics.csv.gz')
    cut=stats.merge(f[['game_id','season','week']],on='game_id',validate='many_to_one')
    assert ((cut.max_source_season<cut.season)|((cut.max_source_season==cut.season)&(cut.max_source_week<cut.week))).all()
    assert (cut.effective_games>=0).all() and (cut.effective_pass_mass_games>=0).all()
