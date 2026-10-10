"""The adopted stack matches research and rejects missing/future target inputs."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import nfl_model as m
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import margin_total_models as research


def fixture():
    rng=np.random.default_rng(817);n=400
    train=pd.DataFrame({'season':2022,'week':np.arange(n)%18+1,'home won':rng.integers(0,2,n).astype(float),
                       'ready':True,'q':rng.uniform(.2,.8,n),'stage1_through_season':2021,'stage1_through_week':18})
    for name in m.feature_names(m.PRODUCT_RECIPE['family'])+list(m.PRODUCT_CONTEXT_NAMES)+list(m.PASS_TOTAL_NAMES):
        train[name]=rng.normal(size=n)
    train['site']=1.
    test=train.iloc[:3].copy();test['season']=2023;test['week']=1
    test['game_id']=['a','b','c'];test['home']='H';test['away']='A'
    return train,test


def test_exact_research_stack_and_contributions():
    train,test=fixture();expected,_=research.stack_fit(train,test,'pass_total')
    fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    assert np.allclose(m.apply_fit(test,fit),expected,rtol=0,atol=1e-10)
    _,score,_=m.apply_fit(test,fit,True)
    parts=m.contribution_table(test,fit).groupby('game_id')['log-odds contribution'].sum()
    assert np.allclose(parts.loc[test.game_id],score,rtol=0,atol=1e-12)
    assert all(c in fit['names'] for c in m.PASS_TOTAL_NAMES)


def test_missing_forecasts_do_not_silently_become_neutral():
    train,test=fixture();fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    test.loc[test.index[0],'margin_edge']=np.nan;test.loc[test.index[1],'pass_total_interaction']=np.nan
    assert np.isnan(m.apply_fit(test,fit)[:2]).all() and np.isfinite(m.apply_fit(test,fit)[2])
    train.loc[train.index[0],'total_homefield']=np.nan
    assert m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)['training_games']==len(train)-1


def test_future_or_missing_stage_one_cutoff_rejected():
    train,test=fixture()
    train.loc[train.index[0],['stage1_through_season','stage1_through_week']]=[2022,1]
    with pytest.raises(ValueError,match='own/current/future'):m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    train,test=fixture();fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    test.loc[test.index[0],['stage1_through_season','stage1_through_week']]=[2023,1]
    with pytest.raises(ValueError,match='own/current/future'):m.apply_fit(test,fit)
    with pytest.raises(ValueError,match='Missing'):m.apply_fit(test.drop(columns='stage1_through_week'),fit)


def test_pending_outcome_does_not_poison_annual_rule_selection():
    f=pd.DataFrame({'season':[2020,2021,2021,2022],'margin':[0.,0.,np.nan,0.],'total':[45.,45.,np.nan,45.]})
    for target in m.MARKET_TARGETS:
        for arm in ('market_relationships',*m.MARKET_RESIDUAL_RULES):
            f[f'{target}__{arm}__mean']=0. if target=='margin' else 45.
            f[f'{target}__{arm}__sd']=10.
    _,choices=m.select_market_target_forecasts(f)
    assert all(np.isfinite(list(c['prior_scores'].values())).all() for c in choices)
    altered=f.copy();altered.loc[altered.season==2022,['margin','total']]=99999.
    assert choices==m.select_market_target_forecasts(altered)[1]


def test_native_capture_saves_targets_and_rejects_inconsistent_target_inputs(tmp_path,monkeypatch):
    import datetime as dt
    train,board=fixture();board=board.iloc[:1].copy()
    board['gameday']='2023-09-10';board['gametime']='13:00';board['result']=np.nan
    board['home_injury_report']='final';board['away_injury_report']='final';board['homefield_wp']=.55
    board['home_moneyline']=-120.;board['away_moneyline']=100.
    board['q']=m.market_ml_wp(board);board['market_wp']=board.q
    board['spread_line']=3.;board['margin_line']=3.;board['total_line']=45.5
    board['market_cover_q']=.51;board['market_over_q']=.49
    board['margin__selected__mean']=3.2;board['total__selected__mean']=46.
    board['margin_edge']=.02;board['total_homefield']=.1;board['pass_total_interaction']=board.pass_product*.1
    for col in ('pass_ho','pass_ad','pass_ao','pass_hd'):board[col]=.7
    fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    fit['market_target_fit']={'2023_1':'test audit'};fit['market_target_selection']=[{'season':2023,'target':'total','chosen':'market_relationships'}]
    board['model_wp']=m.apply_fit(board,fit)
    monkeypatch.setattr(m,'STATE_DIR',str(tmp_path))
    rec={'recipe':m.PRODUCT_RECIPE,'config_signature':m.config_signature()[0],'season':2023}
    records,n=m.record_forward(board,fit,rec,asof=dt.datetime(2023,9,9,tzinfo=dt.timezone.utc))
    assert n==1 and records[0]['market_target_inputs']['total__selected__mean']==46.
    assert records[0]['market_target_fit']==fit['market_target_fit']
    assert records[0]['revision']==m.REVISION
    board['game_id']='new_game'
    board['total__selected__mean']=99.
    with pytest.raises(ValueError,match='do not match target'):m.record_forward(board,fit,rec,asof=dt.datetime(2023,9,9,tzinfo=dt.timezone.utc))
    board['total__selected__mean']=46.
    with pytest.raises(ValueError,match='missing target prices'):m.record_forward(board.drop(columns='total_line'),fit,rec,asof=dt.datetime(2023,9,9,tzinfo=dt.timezone.utc))


def test_walk_forward_retains_ties_as_pushes_and_names_actual_market(monkeypatch):
    train,test=fixture();test.loc[test.index[0],'home won']=.5
    f=pd.concat([train,test],ignore_index=True)
    f['result']=np.where(f['home won']==.5,0.,np.where(f['home won']==1.,7.,-7.))
    f['market_wp']=f.q;f['home_moneyline']=-120.;f['away_moneyline']=100.;f['spread_line']=3.
    monkeypatch.setattr(m,'BACKTEST_FIRST_SEASON',2023)
    oof=m.walk_forward_product({8.:f},2023)
    assert len(oof)==3 and oof['home won'].eq(.5).sum()==1
    oof['model_wp']=oof['p__'+m.recipe_key(m.PRODUCT_RECIPE)]
    assert m.flat_bets(oof).loc[oof['home won']==.5,'units'].iloc[0]==0.
    card=m.scorecard(oof)
    assert 'no-vig moneyline market' in card.source.to_list()
    assert set(card['games scored'])=={2}


def test_regrade_uses_captured_total_prices_instead_of_changed_schedule(tmp_path,monkeypatch):
    import json
    train,test=fixture();test=test.iloc[:1].copy()
    test['margin_line']=3.;test['total_line']=60.;test['market_cover_q']=.6;test['market_over_q']=.6
    f=pd.concat([train,test],ignore_index=True)
    f.loc[f.game_id.isna(),'game_id']=[f't{i}' for i in range(len(train))]
    record={'experiment':'snapshot','revision':m.REVISION,'generated_utc':'2023-09-09T00:00:00Z',
            'game_id':'a','season':2023,'week':1,'home':'H','away':'A','model_wp':.9,
            'home_moneyline':120.,'away_moneyline':-140.,'spread_line':3.,
            'market_target_inputs':{'total_line':42.,'market_cover_q':.51,'market_over_q':.48}}
    path=tmp_path/'forward_predictions.jsonl';path.write_text(json.dumps(record)+'\n');before=path.read_bytes()
    fits={'2023_1':{'margin:market_relationships':{'names':['intercept','moneyline_logit'],'scale':[1.],'beta':[0.,.01]},
                    'total:market_relationships':{'names':['intercept','total_context_price','over_logit'],'scale':[1.,1.],'beta':[0.,.2,.1]}}}
    features={8.:f,'market_target_fits':fits,'market_target_selections':[{'season':2023,'target':t,'chosen':'market_relationships'} for t in m.MARKET_TARGETS]}
    monkeypatch.setattr(m,'STATE_DIR',str(tmp_path))
    m.regrade_product_ledger(features,pd.DataFrame({'game_id':['a'],'result':[-3.]}),tmp_path)
    actual=pd.read_csv(tmp_path/'regraded_ledger.csv').iloc[0]
    expected=test.copy();expected['q']=m.market_ml_wp(pd.DataFrame([record]))
    for k,v in record['market_target_inputs'].items():expected[k]=v
    expected=m.replay_market_targets(expected,features,2023,1)
    expected_p=m.apply_fit(expected,m.fit_composite(train,m.PRODUCT_RECIPE,2023,1))[0]
    assert actual.model_wp==pytest.approx(expected_p,abs=1e-12)
    assert 'original captured market quotes' in actual.basis and path.read_bytes()==before
