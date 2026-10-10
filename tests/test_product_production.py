"""Adopted recipe reproduces independent research math and preserves evidence."""
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import nfl_model as m
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import production_qualification as research
import qualified_interactions as contexts


def fixture():
    rng=np.random.default_rng(921)
    n=max(m.MIN_TRAIN_GAMES+30,400)
    train=pd.DataFrame({'season':np.where(np.arange(n)%2,2021,2022),'week':np.arange(n)%18+1,
                        'home won':rng.integers(0,2,n).astype(float),'ready':True,'q':rng.uniform(.15,.85,n)})
    for name in m.feature_names(m.PRODUCT_RECIPE['family'])+list(m.PRODUCT_CONTEXT_NAMES):
        train[name]=rng.normal(size=n)
    train['site']=1.
    test=train.iloc[:4].copy();test['season']=2023;test['week']=1
    test['game_id']=['a','b','c','d'];test['home']='H';test['away']='A'
    return train,test


def test_production_matches_independent_market_offset_research_fit():
    train,test=fixture()
    mapping=dict(zip(m.PRODUCT_CONTEXT_NAMES,['product','e_pp','e_pn','e_np','e_nn']))
    expected,_=research.fit_predict(train.rename(columns=mapping),test.rename(columns=mapping),
        m.feature_names(m.PRODUCT_RECIPE['family']),list(mapping.values()),.1,.1,True)
    fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    actual=m.apply_fit(test,fit)
    assert np.allclose(actual,expected,rtol=0,atol=1e-10)
    parts=m.contribution_table(test,fit).groupby('game_id')['log-odds contribution'].sum()
    _,scores,_=m.apply_fit(test,fit,True)
    assert np.allclose(parts.loc[test.game_id],scores,atol=1e-12)
    assert fit['training_max_season']==2022 and fit['market_offset']


def test_quotes_and_contexts_are_required_without_fallback():
    train,test=fixture();fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    test.loc[test.index[0],'q']=np.nan
    test.loc[test.index[1],'pass_product']=np.nan
    actual=m.apply_fit(test,fit)
    assert np.isnan(actual[:2]).all() and np.isfinite(actual[2:]).all()
    assert np.isnan(m.market_ml_wp(pd.DataFrame({'home_moneyline':[0,np.nan],'away_moneyline':[-120,-120]}))).all()
    train.loc[train.index[:5],'q']=np.nan
    assert m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)['training_games']==len(train)-5


def test_training_rejects_current_week():
    train,test=fixture();train.loc[train.index[0],['season','week']]=[2023,1]
    with pytest.raises(ValueError,match='current/future'):
        m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)


def test_normalization_exactly_matches_research_and_ignores_future(tmp_path):
    f=pd.DataFrame({'season':[2020,2020,2021,2021,2021],'week':[1,2,1,2,3]})
    for n,(side,role) in enumerate([('home','for'),('away','allowed'),('away','for'),('home','allowed')]):
        f[f'{side}__{role}__rates_core__{contexts.STAT}']=[5+n*.2,6+n*.3,5.5+n*.4,7-n*.1,6.5+n*.1]
    old=contexts.OUT;contexts.OUT=tmp_path
    try: expected=contexts.descriptors(f)
    finally: contexts.OUT=old
    actual,audit=m.pass_contexts(f)
    assert np.allclose(actual[list(m.PRODUCT_CONTEXT_NAMES)],expected[['product','e_pp','e_pn','e_np','e_nn']],equal_nan=True)
    f.loc[4,f.columns[2:]]=10000
    altered,_=m.pass_contexts(f)
    assert np.allclose(actual.iloc[:4],altered.iloc[:4],equal_nan=True)
    assert ((audit.max_reference_season<audit.season)|((audit.max_reference_season==audit.season)&(audit.max_reference_week<audit.week))).all()


def test_owner_recipe_does_not_reselect_from_historical_outcomes():
    col='p__'+m.recipe_key(m.PRODUCT_RECIPE)
    o=pd.DataFrame({'season':[2021,2022],'home won':[1.,0.],col:[.6,.4]})
    assert m.select_recipe(o)[0]==m.PRODUCT_RECIPE
    o['home won']=1-o['home won']
    assert m.select_recipe(o)[0]==m.PRODUCT_RECIPE
    assert m.REVISION=='boxscore-composite-v1.16'
    assert m.config_signature()[1]['production_recipe']==m.PRODUCT_RECIPE


def test_replay_preserves_original_snapshot_and_uses_snapshot_quotes(tmp_path,monkeypatch):
    train,test=fixture();test=test.iloc[:1].copy()
    test['q']=.8
    frame=pd.concat([train,test],ignore_index=True)
    # A separate game key on historical training rows avoids ambiguous replay lookup.
    frame.loc[frame.game_id.isna(),'game_id']=[f't{i}' for i in range(len(train))]
    record={'experiment':'old','revision':'old-revision','generated_utc':'2023-09-01T00:00:00Z',
            'game_id':'a','season':2023,'week':1,'home':'H','away':'A','model_wp':.7,
            'home_moneyline':120.,'away_moneyline':-140.}
    path=tmp_path/'forward_predictions.jsonl';path.write_text(json.dumps(record)+'\n');before=path.read_bytes()
    monkeypatch.setattr(m,'STATE_DIR',str(tmp_path))
    schedules=pd.DataFrame({'game_id':['a'],'result':[-3.]})
    m.regrade_product_ledger({8.:frame},schedules,tmp_path)
    replay=pd.read_csv(tmp_path/'regraded_ledger.csv')
    assert path.read_bytes()==before and replay.original_model_wp.iloc[0]==.7
    assert replay.home_moneyline.iloc[0]==120
    assert replay.market_wp.iloc[0]==pytest.approx(m.market_ml_wp(pd.DataFrame([record]))[0])
    altered=test.copy();altered['q']=replay.market_wp.iloc[0]
    expected=m.apply_fit(altered,m.fit_composite(train,m.PRODUCT_RECIPE,2023,1))[0]
    assert replay.model_wp.iloc[0]==pytest.approx(expected)


def test_native_capture_requires_forecast_and_saves_replay_inputs(tmp_path,monkeypatch):
    import datetime as dt
    train,board=fixture();fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    board=board.iloc[:2].copy()
    board['model_wp']=m.apply_fit(board,fit);board.loc[board.index[0],'model_wp']=np.nan
    board['result']=np.nan;board['gameday']='2023-09-10';board['gametime']='13:00'
    board['homefield_wp']=.54;board['market_wp']=board.q;board['spread_line']=1.
    board['home_moneyline']=-120.;board['away_moneyline']=100.
    board['q']=m.market_ml_wp(board);board['market_wp']=board.q
    board['model_wp']=m.apply_fit(board,fit);board.loc[board.index[0],'model_wp']=np.nan
    board['home_injury_report']='final';board['away_injury_report']='final'
    for col in ('pass_ho','pass_ad','pass_ao','pass_hd'): board[col]=.7
    monkeypatch.setattr(m,'STATE_DIR',str(tmp_path))
    rec={'config_signature':m.config_signature()[0],'recipe':m.PRODUCT_RECIPE,'season':2023}
    records,n=m.record_forward(board,fit,rec,asof=dt.datetime(2023,9,9,tzinfo=dt.timezone.utc))
    assert n==1 and records[0]['game_id']=='b'
    assert records[0]['revision']=='boxscore-composite-v1.16'
    assert records[0]['market_no_vig_wp']==board.q.iloc[1]
    assert set(records[0]['model_inputs'])==set(fit['names'])
    assert set(records[0]['pass_context_inputs'])=={'pass_ho','pass_ad','pass_ao','pass_hd'}
    assert m.record_forward(board,fit,rec,asof=dt.datetime(2023,9,9,tzinfo=dt.timezone.utc))[1]==0

    board.loc[board.index[0],'model_wp']=.7
    board.loc[board.index[0],'q']=.1
    with pytest.raises(ValueError,match='offset does not match'):
        m.record_forward(board,fit,rec,asof=dt.datetime(2023,9,9,tzinfo=dt.timezone.utc))
