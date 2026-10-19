"""v1.19 reproduces the promoted two-stage research fit without changing archives."""
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize
from scipy.special import expit

import nfl_model as m


def fixture():
    rng=np.random.default_rng(9019); n=420
    f=pd.DataFrame(dict(season=np.where(np.arange(n)%2,2021,2022),week=np.arange(n)%18+1,
        ready=True,q=rng.uniform(.2,.8,n),spread_line=rng.normal(0,7,n),total_line=rng.normal(44,5,n)))
    for name in m.feature_names(m.PRODUCT_RECIPE['family'])+list(m.PRODUCT_CONTEXT_NAMES): f[name]=rng.normal(size=n)
    f['site']=1.
    f['home won']=rng.binomial(1,expit(.15+f.spread_line/7+.3*f['d__avail__qb_delta'])).astype(float)
    test=f.iloc[:4].copy().assign(season=2023,week=1,game_id=['a','b','c','d'],home='H',away='A')
    return f,test


def independent(train,test):
    """Separate implementation of the registered mean-weighted two-stage loss."""
    age=(2023-train.season.to_numpy())*19+1-train.week.to_numpy()
    w=np.exp2(-age/38);w/=w.sum(); y=train['home won'].to_numpy()
    def market(frame):
        s=frame.spread_line.to_numpy()/7;t=(frame.total_line.to_numpy()-44)/7
        return np.column_stack([np.ones(len(frame)),s,t,s*t])
    def solve(x,base,penalty):
        def objective(beta):
            eta=base+x@beta
            return w@(np.logaddexp(0,eta)-y*eta)+.5*np.sum(penalty*beta**2),x.T@(w*(expit(eta)-y))+penalty*beta
        return minimize(objective,np.zeros(x.shape[1]),jac=True,method='BFGS',options={'gtol':1e-10}).x
    baseline=solve(market(train),np.zeros(len(train)),np.full(4,.01*np.sum(w*w)))
    names=m.feature_names(m.PRODUCT_RECIPE['family'])+list(m.PRODUCT_CONTEXT_NAMES)
    raw=train[names].to_numpy(); mean=w@raw;scale=np.sqrt(w@((raw-mean)**2));scale[0]=1.
    beta=solve(raw/scale,market(train)@baseline,np.array([.01]+[.1]*(len(names)-1)))
    return expit(market(test)@baseline+(test[names].to_numpy()/scale)@beta),baseline


def test_revision_is_distinct_and_preserves_the_legacy_recipe():
    assert m.REVISION=='boxscore-composite-v1.19' and m.OUTPUT_NAME.endswith('v1_19')
    assert m.PRODUCT_RECIPE['architecture']=='market_spread_total'
    assert 'favorite_penalty' not in m.PRODUCT_RECIPE
    assert m.LEGACY_PRODUCT_RECIPE['architecture']=='market_product_1sd'
    assert m.recipe_key(m.PRODUCT_RECIPE)!=m.recipe_key(m.LEGACY_PRODUCT_RECIPE)
    assert not m.SHADOW_LOCK
    assert m.profile_half_lives('production')==(8.,16.)
    assert 'market_baseline' in m.config_signature()[1]
    with m.revision_identity('boxscore-composite-v1.16',m.LEGACY_PRODUCT_RECIPE):
        assert m.config_signature()[0]=='9dad9b9ad0eda3c043c4227d211e8c1cb460beaac6c649f09787c296a62dcd26'
    assert m.LEGACY_V118_RECIPE['favorite_penalty']==.2


def test_market_baseline_and_feature_fit_match_independent_scipy():
    train,test=fixture(); fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    expected,baseline=independent(train,test)
    np.testing.assert_allclose(m.apply_fit(test,fit),expected,rtol=0,atol=2e-7)
    np.testing.assert_allclose(fit['market_baseline']['beta'],baseline,rtol=0,atol=2e-7)
    assert len(fit['names'])==29 and fit['training_games']==len(train)
    assert fit['market_baseline']['training_max_season']==2022
    assert fit['market_baseline']['ridge_per_coefficient']==pytest.approx(.01/fit['effective_training_games'])


def test_tracked_feature_pack_matches_archived_spread_total_full_forecasts():
    root=Path(__file__).resolve().parents[1]
    frame=pd.read_csv(root/'research/shrinkage_results/frozen_training_features.csv.gz')
    totals=pd.read_csv(root/'research/residual_trends_inputs/schedule_totals.csv')[['game_id','total_line']]
    frame=frame.merge(totals,on='game_id',validate='one_to_one')
    target=frame.set_index('game_id').loc[['2023_01_ARI_WAS','2023_01_BUF_NYJ','2023_01_CAR_ATL','2023_01_CIN_CLE']].copy()
    fit=m.fit_composite(frame[m.before(frame,2023,1)],m.PRODUCT_RECIPE,2023,1)
    # Frozen independent spread_total::group:full forecasts, generated before
    # promotion. CI needs only the already tracked input pack, not old results.
    expected=[.7070030337224023,.3465464153208,.6456110842834424,.4988452349061527]
    np.testing.assert_allclose(m.apply_fit(target,fit),expected,rtol=0,atol=2e-7)
    assert fit['training_games']==986


@pytest.mark.parametrize('year,week',[(2023,1),(2023,2),(2024,1)])
def test_current_and_future_training_cannot_enter_either_stage(year,week):
    train,_=fixture();train.loc[0,['season','week']]=[year,week]
    with pytest.raises(ValueError,match='current/future'): m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)


def test_finite_moneyline_changes_do_not_change_the_new_baseline_or_forecast():
    train,test=fixture();fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    alternate=m.fit_composite(train.assign(q=.99),m.PRODUCT_RECIPE,2023,1)
    assert fit==alternate
    np.testing.assert_array_equal(m.apply_fit(test,fit),m.apply_fit(test.assign(q=.01),fit))
    test.loc[test.index[0],'total_line']=np.nan; test.loc[test.index[1],'spread_line']=np.nan
    test.loc[test.index[2],'q']=np.nan
    assert np.isnan(m.apply_fit(test,fit)[:3]).all()
    assert np.isfinite(m.apply_fit(test,fit)[3])
    train.loc[0,'total_line']=np.nan
    assert m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)['training_games']==len(train)-1


def test_serialized_fit_responds_to_its_saved_market_quotes_and_contributions_sum():
    train,test=fixture();fit=json.loads(json.dumps(m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)))
    p=m.apply_fit(test,fit)
    changed=m.apply_fit(test.assign(spread_line=test.spread_line+7,total_line=test.total_line+7),fit)
    assert not np.allclose(p,changed)
    assert np.array_equal(p,m.apply_fit(test,fit,raw=True))
    parts=m.contribution_table(test,fit)
    _,scores,_=m.apply_fit(test,fit,contributions=True)
    np.testing.assert_allclose(parts.groupby('game_id')['log-odds contribution'].sum().loc[test.game_id],scores,atol=1e-12)
    assert 'market_context_log_odds' in set(parts.feature)
    assert m.feature_label('market_context_log_odds')=='Fitted spread/total market baseline'
    assert all(np.isnan(values).all() for values in m.offset_band(train,fit,test))
    bad=json.loads(json.dumps(fit));bad['market_baseline']['total_center']=45.
    with pytest.raises(ValueError,match='serialized market baseline'):m.apply_fit(test,bad)


def test_feature_preparation_attaches_schedule_totals_without_row_reordering(monkeypatch):
    _,base=fixture(); base=base.drop(columns=['total_line'])
    features={8.:base.copy(),16.:base.copy()}
    desc=pd.DataFrame(np.ones((4,5)),columns=m.PRODUCT_CONTEXT_NAMES)
    monkeypatch.setattr(m,'pass_contexts',lambda _: (desc,pd.DataFrame()))
    schedule=pd.DataFrame({'game_id':list('dcba'),'home_moneyline':[-150.]*4,'away_moneyline':[130.]*4,
                           'total_line':[48.,47.,46.,45.]})
    m.prepare_product_features(features,schedule)
    assert features[8.].game_id.tolist()==list('abcd')
    assert features[8.].total_line.tolist()==[45.,46.,47.,48.]


def test_native_capture_retains_context_and_never_writes_false_legacy_shadow(tmp_path,monkeypatch):
    train,board=fixture();board=board.iloc[:1].copy()
    board['home_moneyline']=-150.;board['away_moneyline']=130.;board['q']=m.market_ml_wp(board)
    fit=m.fit_composite(train,m.PRODUCT_RECIPE,2023,1)
    board['model_wp']=m.apply_fit(board,fit);board['market_wp']=board.q;board['homefield_wp']=.54
    board['result']=np.nan;board['gameday']='2023-09-10';board['gametime']='13:00'
    board['home_injury_report']=board['away_injury_report']='final'
    for name in ('pass_ho','pass_ad','pass_ao','pass_hd'):board[name]=.2
    monkeypatch.setattr(m,'STATE_DIR',str(tmp_path))
    rec=dict(config_signature=m.config_signature()[0],recipe=m.PRODUCT_RECIPE,season=2023)
    rows,added=m.record_forward(board,fit,rec,dt.datetime(2023,9,9,tzinfo=dt.timezone.utc))
    assert added==1 and rows[0]['revision']==m.REVISION
    assert rows[0]['market_context_inputs']=={'spread_line':float(board.spread_line.iloc[0]),'total_line':float(board.total_line.iloc[0])}
    assert rows[0]['coefficient_fit']['market_baseline']==fit['market_baseline']
    assert m.record_shadow(board,fit,pd.DataFrame(),2023)==0


def test_current_week_completed_games_remain_in_the_retrospective_prediction_view():
    train,targets=fixture();targets=targets.assign(result=[3.,-7.,0.,np.nan])
    frame=pd.concat([train,targets],ignore_index=True)
    view,fit=m.current_predictions({8.:frame},m.PRODUCT_RECIPE,2023,1)
    assert len(view)==4 and view.result.notna().sum()==3
    assert np.isfinite(view.model_wp).all()
    assert 'model_wp_v116' not in view
    assert fit['training_max_season']==2022
    view['home won']=view.result.map(m.won);view['market_wp']=view.q
    oof=pd.DataFrame(columns=m.RETRO_COLS+['p__'+m.recipe_key(m.PRODUCT_RECIPE)])
    schedule=pd.DataFrame({'game_id':list('abcd'),'home_moneyline':[-150.]*4,'away_moneyline':[130.]*4})
    retrospective=m.retrospective_ledger(oof,view,m.PRODUCT_RECIPE,schedule,2023,1)
    assert retrospective.game_id.tolist()==list('abc')


def test_replay_uses_captured_spread_total_without_rewriting_original_snapshots(tmp_path,monkeypatch):
    train,target=fixture();target=target.iloc[:1].copy()
    train=train.assign(game_id=[f't{i}' for i in range(len(train))])
    frame=pd.concat([train,target],ignore_index=True)
    record=dict(experiment='original',revision='old-revision',generated_utc='2023-09-01T00:00:00Z',
        game_id='a',season=2023,week=1,home='H',away='A',model_wp=.7,
        home_moneyline=-150.,away_moneyline=130.,spread_line=2.5,total_line=41.,
        market_context_inputs=dict(spread_line=2.5,total_line=41.))
    archive=tmp_path/'forward_predictions.jsonl';archive.write_text(json.dumps(record)+'\n')
    before=archive.read_bytes();monkeypatch.setattr(m,'STATE_DIR',str(tmp_path))
    m.regrade_product_ledger({8.:frame},pd.DataFrame({'game_id':['a'],'result':[3.]}),tmp_path)
    replay=pd.read_csv(tmp_path/'regraded_ledger.csv')
    q=m.market_ml_wp(pd.DataFrame([record]))[0]
    expected=m.apply_fit(target.assign(spread_line=2.5,total_line=41.,q=q),m.fit_composite(train,m.PRODUCT_RECIPE,2023,1))[0]
    assert replay.model_wp.iloc[0]==pytest.approx(expected)
    assert replay.spread_line.iloc[0]==2.5 and replay.total_line.iloc[0]==41.
    assert 'captured spread/total' in replay.basis.iloc[0]
    assert archive.read_bytes()==before
