"""Descriptive loss audit must preserve settlement, denominators and influence."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import plain_loss_audit as a


def records():
    f=pd.DataFrame(dict(game_id=['a','b','c','d'],season=2023,week=[1,2,3,4],
        home_team='HOME',away_team='AWAY',home_score=[24,20,17,21],away_score=[10,14,17,10],
        spread_line=3.,total_line=44.,p_home_non_tie=[.6,.49,.55,.6],q=[.65,.6,.55,.5],
        home_moneyline=[-200,-170,-125,-110],away_moneyline=[170,150,105,-110],
        cover_conditional=.5,over_conditional=.5,final_ess=100.,largest_atom=.03))
    return a.enrich(a.m.j.add_binary_and_bet_scores(f))


def test_more_likely_winner_is_not_necessarily_positive_ev():
    f=records().set_index('game_id')
    assert f.loc['a','picked_team']=='HOME'
    assert f.loc['a','price_breakeven']==pytest.approx(2/3)
    assert f.loc['a','model_expected_units']==pytest.approx(-.1)
    assert f.loc['b','picked_team']=='AWAY'
    assert f.loc['b','model_expected_units']==pytest.approx(.51*2.5-1)
    assert f.loc['b','units_vs_favorite']==pytest.approx(-1-100/170)


def test_ties_push_pickems_excluded_and_calibration_uses_decisive_bets():
    f=records();result=a.aggregate(f)
    assert result['games']==4 and result['bets']==3
    assert (result['wins'],result['losses'],result['pushes'])==(1,1,1)
    assert result['units']==pytest.approx(-.5)
    assert result['roi']==pytest.approx(-.5/3)
    assert result['observed_win_rate']==.5
    assert result['mean_picked_probability']==pytest.approx((.6+.51)/2)
    assert not f.set_index('game_id').loc['d','bet_eligible']


def test_corrupted_settlement_duplicate_and_probability_rejected():
    f=records()
    with pytest.raises(ValueError,match='Duplicate'):a.enrich(pd.concat([f,f]))
    with pytest.raises(ValueError,match='probabilities'):a.enrich(f.assign(p_home_non_tie=1.01))
    f.loc[0,'model_units']=-1
    with pytest.raises(ValueError,match='settlement'):a.enrich(f)


def influence_fixture():
    h=pd.DataFrame(dict(game_id=['one','two','three'],home_score=[24.,10.,13.],away_score=[10.,21.,20.],
                        spread_line=[7.,-3.,-7.],total_line=[45.,42.,40.]))
    dist=dict(home=h.home_score.to_numpy(),away=h.away_score.to_numpy(),weights=np.array([.4,.35,.25]),source_ids=h.game_id.to_numpy())
    return dist,h,dict(game_id='new',spread_line=0.,total_line=44.)


def test_single_source_flip_and_mean_decomposition_are_exact():
    d,h,t=influence_fixture();r=a.source_influence(d,h,t)
    assert r['single_source_can_flip']
    assert r['single_source_min_p_home']==pytest.approx(0)
    assert r['single_source_max_p_home']==pytest.approx(.4/.65)
    assert r['largest_source_id']=='one'
    assert r['spread_kernel_blur']==pytest.approx(0)
    assert r['predicted_margin_minus_line']==pytest.approx(d['weights']@(d['home']-d['away']))


def test_influence_rejects_misalignment_and_handles_tie_atoms():
    d,h,t=influence_fixture()
    with pytest.raises(ValueError,match='Misaligned'):a.source_influence(d,h.iloc[::-1],t)
    h.loc[2,'home_score']=h.loc[2,'away_score'];d['home']=h.home_score.to_numpy()
    r=a.source_influence(d,h,t)
    assert r['recomputed_p_home']==pytest.approx(.4/.75)
    assert r['single_source_max_p_home']==pytest.approx(1)
