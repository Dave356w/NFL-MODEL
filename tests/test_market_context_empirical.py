"""Empirical atoms, chronological selection, distributions and quoted settlement."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import market_context_empirical as m


def history():
    return pd.DataFrame(dict(game_id=[f'g{i}' for i in range(8)],season=[2015]*8,week=list(range(1,9)),
        home_score=[20,24,30,17,21,14,10,7],away_score=[17,21,10,20,21,28,24,7],
        spread_line=[3,3,10,-3,0,-7,-10,0],total_line=[40,44,45,40,42,45,40,30]))


def target():
    return dict(game_id='target',season=2016,week=1,spread_line=3.,total_line=42.)


def test_direct_distribution_uses_only_observed_paired_games():
    h=history();p=m.forecast(h,target(),m.CANDIDATES[0])
    assert p['weights'].sum()==pytest.approx(1)
    assert (p['weights']>0).all()
    observed=set(zip(h.home_score,h.away_score))
    assert set(zip(p['home'],p['away']))==observed
    assert len(p['weights'])==len(h) and p['audit']['removed_mass']==0
    assert set(p['source_ids'])==set(h.game_id)
    assert 1<=p['audit']['final_ess']<=len(h)


def test_similar_context_gets_more_weight_and_backoff_is_explicit():
    pool=m.prepare_pool(m.prior(history(),target()),target())
    narrow=m.distribution(pool,m.Config('narrow',spread_bandwidth=2,total_bandwidth=3,pseudo_games=1))
    by_id=dict(zip(narrow['source_ids'],narrow['weights']))
    assert by_id['g0']>by_id['g6']
    global_=m.distribution(pool,m.Config('global',global_only=True))
    strong=m.distribution(pool,m.Config('strong',pseudo_games=1e12))
    assert np.allclose(strong['weights'],global_['weights'],atol=1e-10)
    assert narrow['audit']['local_fraction']==pytest.approx(narrow['audit']['local_ess']/(narrow['audit']['local_ess']+1))


def test_neighbor_ties_use_source_id_and_do_not_duplicate_games():
    h=history().assign(spread_line=3.,total_line=42.)
    p=m.forecast(h.sample(frac=1,random_state=7),target(),m.Config('knn',neighbors=2,pseudo_games=1))
    # Equal distances choose g0,g1 despite input shuffle and recency weighting.
    weights=dict(zip(p['source_ids'],p['weights']))
    assert weights['g1']>weights['g7'] and weights['g0']>weights['g7']
    assert len(set(p['source_ids']))==8


def test_no_current_future_expired_or_target_labels_enter_forecast():
    h=history();config=m.CANDIDATES[1]
    original=m.forecast(h,target(),config)
    for year,week in [(2016,1),(2017,1),(2010,1)]:
        extra=h.assign(season=year,week=week,game_id=h.game_id+'extra',home_score=999,away_score=0)
        p=m.forecast(pd.concat([h,extra]),target()|{'home_score':999,'away_score':0},config)
        assert np.array_equal(p['weights'],original['weights'])
        assert np.array_equal(p['home'],original['home'])
    with pytest.raises(ValueError,match='prior-week'):
        m.prepare_pool(h.assign(season=2016),target())


def test_crps_matches_pairwise_oracle_and_endpoints_are_not_floored():
    x=np.array([-7.,0.,3.,10.]);w=np.array([.1,.2,.4,.3]);y=4.
    oracle=np.sum(w*abs(x-y))-.5*np.sum(w[:,None]*w[None,:]*abs(x[:,None]-x[None,:]))
    assert m.empirical_crps(x,w,y)==pytest.approx(oracle)
    assert m.binary_loss(0,0)==0 and m.binary_loss(1,1)==0
    assert np.isinf(m.binary_loss(1,0)) and np.isinf(m.binary_loss(0,1))
    win,push,lose,conditional=m.event(x,3.,w)
    assert [win,push,lose,conditional]==pytest.approx([.3,.4,.3,.5])


def test_residual_translation_logs_negative_atoms_without_clipping():
    h=pd.DataFrame(dict(game_id=['low','high'],season=2015,week=1,
        spread_line=0.,total_line=50.,home_score=[3,35],away_score=[40,30]))
    p=m.forecast(h,target()|{'spread_line':0.,'total_line':10.},m.Config('residual',translated=True,global_only=True))
    assert p['source_ids'].tolist()==['high']
    assert p['home'].tolist()==[15.] and p['away'].tolist()==[10.]
    assert p['audit']['removed_mass']==pytest.approx(.5)
    assert p['audit']['removed_atoms']==1
    assert p['weights'].tolist()==[1.]
    with pytest.raises(ValueError,match='No valid'):
        m.forecast(h.assign(home_score=0,away_score=0),target()|{'total_line':1.},m.Config('r',translated=True))


def test_direct_score_quantiles_coverages_and_joint_means():
    row=pd.Series(target()|{'home_score':24,'away_score':21})
    p=m.forecast(history(),target(),m.CONTROLS[0]);r=m.grade(p,row)
    assert r['margin_mean']==pytest.approx(r['home_mean']-r['away_mean'])
    assert r['total_mean']==pytest.approx(r['home_mean']+r['away_mean'])
    assert r['primary_crps']==pytest.approx(.5*(r['margin_crps']+r['total_crps']))
    assert r['cover_win']+r['cover_push']+r['cover_lose']==pytest.approx(1)
    assert set(m.quantiles(p['home'],p['weights'],[.05,.5,.95])).issubset(set(history().home_score))


def selection_archive():
    return pd.DataFrame([dict(game_id=f'{y}_g',season=y,arm=c.name,primary_crps=float(i+1))
                         for y in [2015,2016,2017] for i,c in enumerate(m.CANDIDATES)])


def test_selection_uses_only_earlier_seasons_with_two_year_warmup():
    a=selection_archive();name,audit=m.select_names(a,2017)
    assert name==m.CANDIDATES[0].name and audit['selection_max_season']==2016
    a.loc[a.season.eq(2017),'primary_crps']=-999
    assert m.select_names(a,2017)==(name,audit)
    with pytest.raises(ValueError,match='two earlier'):
        m.select_names(a,2016)
    with pytest.raises(ValueError,match='Incomplete'):
        m.select_names(a.drop(index=0),2017)
    family,_=m.select_names(a,2017,'residual')
    assert family.startswith('residual')


def test_quote_cli_uses_observed_margin_atoms_and_rejects_labels(tmp_path,capsys):
    h=history();request=dict(target=target(),offers=[dict(side='home',handicap=-3,american_odds=-110)])
    result=m.evaluate_request(h,request,m.CONTROLS[0].name)
    p=m.forecast(h,target(),m.CONTROLS[0]);margin=p['home']-p['away']
    expected=p['weights'][margin>3].sum()/1.1-p['weights'][margin<3].sum()
    assert result['offers'][0]['expected_units']==pytest.approx(expected)
    assert result['policy']=='R003-MC1-SPREAD-EV-v1'
    assert result['implied_home']==22.5 and result['implied_away']==19.5
    with pytest.raises(ValueError,match='Target needs only'):
        m.evaluate_request(h,request|{'target':target()|{'home_score':24}},m.CONTROLS[0].name)
    csv=tmp_path/'inputs.csv';h.to_csv(csv,index=False)
    req=tmp_path/'request.json';req.write_text(json.dumps(request))
    m.main(['--input',str(csv),'--forecast',str(req),'--arm','global_direct'])
    assert json.loads(capsys.readouterr().out)['arm']=='global_direct'


def test_protected_outputs_and_invalid_or_duplicate_inputs_fail(tmp_path):
    for path in ['data','research/experiments/R003_score_support','research/experiments/R003_rare_frequency']:
        with pytest.raises(ValueError):m.guarded_output(m.j.ROOT/path)
    h=history();csv=tmp_path/'source.csv'
    pd.concat([h,h]).to_csv(csv,index=False)
    with pytest.raises(ValueError,match='Duplicate'):m.load_inputs(csv)
    h.assign(home_score=-1).to_csv(csv,index=False)
    with pytest.raises(ValueError,match='nonnegative'):m.load_inputs(csv)
    with pytest.raises(ValueError,match='positive total'):
        m.forecast(h,target()|{'total_line':0},m.CANDIDATES[0])


def test_refinement_is_entirely_observed_and_can_use_zero_backoff():
    c=next(c for c in m.REFINEMENTS if c.name=='direct_ref_h2_t3_p0')
    h=history();p=m.forecast(h,target(),c)
    assert p['audit']['local_fraction']==1 and not c.translated
    assert set(zip(p['home'],p['away']))==set(zip(h.home_score,h.away_score))
    archive=pd.DataFrame([dict(season=y,arm=c.name,primary_crps=float(i))
        for y in [2015,2016] for i,c in enumerate(m.REFINEMENTS)])
    chosen,_=m.select_names(archive,2017,candidates=m.REFINEMENTS)
    assert chosen==m.REFINEMENTS[0].name
    assert len(m.REFINEMENTS)==10 and all(not x.translated for x in m.REFINEMENTS)
