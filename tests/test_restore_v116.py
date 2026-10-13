"""Production restoration preserves identity, coverage and original evidence."""
import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import nfl_model as m
from test_product_production import fixture


def test_restored_configuration_matches_original_frozen_recipe():
    # v1.18 (owner decision 2026-10-13) is v1.16 plus the favorite penalty; v1.16's own identity must
    # still reproduce exactly, because the shadow lock and research replays run under it.
    original=json.loads((Path(__file__).resolve().parents[1]/'data/frozen_recipe_2026_boxscore-composite-v1.16.json').read_text())
    with m.revision_identity(m.SHADOW_REVISION,m.SHADOW_RECIPE):
        assert m.REVISION=='boxscore-composite-v1.16'
        assert m.PRODUCT_RECIPE==original['recipe']
        assert m.config_signature()[0]==original['config_signature']
    assert m.REVISION=='boxscore-composite-v1.18' and m.OUTPUT_NAME=='nfl_boxscore_output_v1_18'
    assert {k:v for k,v in m.PRODUCT_RECIPE.items() if k!='favorite_penalty'}==original['recipe']
    assert m.PRODUCT_RECIPE['favorite_penalty']==m.FAVORITE_PENALTY
    assert m.config_signature()[0]!=original['config_signature']


def test_v116_walk_forward_does_not_require_v117_targets(monkeypatch):
    train,test=fixture();test.loc[test.index[0],'home won']=.5
    f=pd.concat([train,test],ignore_index=True)
    f['result']=np.where(f['home won']==.5,0.,np.where(f['home won']==1.,7.,-7.))
    f['market_wp']=f.q;f['home_moneyline']=-120.;f['away_moneyline']=100.;f['spread_line']=3.
    monkeypatch.setattr(m,'BACKTEST_FIRST_SEASON',2023)
    out=m.walk_forward_product({8.:f},2023)
    assert len(out)==4 and out['home won'].eq(.5).sum()==1
    assert np.isfinite(out['p__'+m.recipe_key(m.PRODUCT_RECIPE)]).all()


def test_v116_preparation_skips_market_target_dependencies(monkeypatch):
    frame=pd.DataFrame({'game_id':['a'],'home_moneyline':[-120.],'away_moneyline':[100.]})
    features={8.:frame.copy(),16.:frame.copy()}
    monkeypatch.setattr(m,'pass_contexts',lambda f:(pd.DataFrame({k:[0.] for k in m.PRODUCT_CONTEXT_NAMES}),pd.DataFrame()))
    monkeypatch.setattr(m,'attach_moneylines',lambda f,s:f)
    def forbidden(*args):raise AssertionError('v1.16 must not require target prices')
    monkeypatch.setattr(m,'attach_market_target_forecasts',forbidden)
    m.prepare_product_features(features,pd.DataFrame())
    assert np.isfinite(features[8.].q).all()
    assert 'market_target_fits' not in features


def test_unique_snapshot_summary_does_not_duplicate_or_grade_pending():
    rows=[]
    for rev,game,day,result,won in [('old','a','01',7.,1.),('new','a','02',7.,1.),('new','b','02',0.,.5),('new','c','02',np.nan,np.nan)]:
        rows.append({'original_revision':rev,'game_id':game,'original_generated_utc':f'2026-10-{day}T00:00:00Z',
                     'result':result,'home won':won,'model_wp':.6,'market_wp':.55,
                     'home_moneyline':-120.,'away_moneyline':100.})
    summary=m.snapshot_replay_summary(pd.DataFrame(rows)).set_index('group')
    assert summary.loc['All unique games','games']==3
    assert summary.loc['All unique games','pending']==1
    assert summary.loc['All unique games','wins']==1
    assert summary.loc['All unique games','pushes']==1
    assert summary.loc['All unique games','binary_games']==1
    assert summary.loc['All unique games','units']==1/1.2


def test_original_binary_only_cache_is_not_reused_for_push_reporting(tmp_path,monkeypatch):
    frame=pd.DataFrame({'season':[2022,2022],'game_id':['win','tie'],'pass_product':[0.,0.]})
    features={half:frame.copy() for half in m.TEAM_HALF_LIVES}
    h=hashlib.sha256(m.config_signature()[0].encode())
    for half in m.TEAM_HALF_LIVES:h.update(m.data_hash(features[half]).encode())
    old=tmp_path/f'walk_forward_{h.hexdigest()[:16]}.csv'
    pd.DataFrame({'game_id':['win']}).to_csv(old,index=False)
    old.with_suffix('.json').write_text(json.dumps({'sha256':hashlib.sha256(old.read_bytes()).hexdigest()}))
    monkeypatch.setattr(m,'CACHE_DIR',str(tmp_path))
    monkeypatch.setattr(m,'walk_forward_product',lambda f,s:pd.DataFrame({'game_id':['win','tie']}))
    assert m.cached_grid(features,2023).game_id.tolist()==['win','tie']
