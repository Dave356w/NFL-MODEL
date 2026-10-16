"""Future iteration gates reject hindsight, proxy records and incomplete cohorts."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import market_increment_gate as g


def forecasts():
    return pd.DataFrame([dict(game_id=f'game{i}',season=2027,week=i+1,iteration='fixture-only',recipe_sha256='a'*64,
        margin_mean=3.,p_home_win=.6,p_home_cover=.56,p_push=.05,spread_line=3.,total_line=44.,
        home_moneyline=-150.,away_moneyline=130.,home_spread_odds=-110.,away_spread_odds=-110.,
        market_spread_win=.6,market_spread_total_win=.6,forecast_utc='2027-09-01T16:00:00Z',
        kickoff_utc='2027-09-01T17:00:00Z',quote_utc='2027-09-01T15:59:00Z',
        feature_available_utc='2027-09-01T15:50:00Z',benchmark_available_utc='2027-09-01T15:55:00Z',
        retained_utc='2027-09-01T16:00:01Z',training_cutoff_utc='2027-08-30T00:00:00Z',
        training_max_season=2026,training_max_week=18,snapshot_sha256='b'*64,
        retention_url='https://example.test/fixture',book='fixture book') for i in range(3)])


def outcomes():
    return pd.DataFrame(dict(game_id=['game0','game1','game2'],home_score=[24,14,20],away_score=[17,21,17]))


def test_price_and_push_mechanics_and_development_never_qualifies():
    result,rows=g.evaluate(forecasts(),outcomes(),'development')
    assert result['ATS']['bets']==3 and result['ATS']['units']==pytest.approx(10/11-1)
    assert rows.ATS_units.tolist()==pytest.approx([10/11,-1,0])
    assert result['gates']['forward_declared'] is False and result['production_promotion'] is False
    assert result['comparisons']['winner_LL_vs_spread']['gain']==pytest.approx(0)


@pytest.mark.parametrize('field,value',[
    ('quote_utc','2027-09-01T15:00:00Z'),('feature_available_utc','2027-09-01T16:01:00Z'),
    ('benchmark_available_utc','2027-09-01T16:01:00Z'),('retained_utc','2027-09-01T17:01:00Z'),
    ('forecast_utc','2027-09-01T16:00:00'),('training_max_season',2028),
    ('snapshot_sha256','invalid'),('retention_url',''),('book','')])
def test_forward_contract_rejects_stale_late_or_unretained_records(field,value):
    with pytest.raises(ValueError):g.validate(forecasts().assign(**{field:value}),'forward_declared')


def test_forward_declared_records_still_need_full_checkpoint_and_external_review():
    result,_=g.evaluate(forecasts(),outcomes(),'forward_declared')
    assert result['gates']['forward_declared'] and not result['gates']['sample_size']
    assert result['verdict']=='incremental ATS edge not established'
    assert 'externally' in result['evidence']


def test_pending_outcomes_and_forecast_labels_rejected():
    with pytest.raises(ValueError,match='Pending'):g.evaluate(forecasts(),outcomes().iloc[:2])
    with pytest.raises(ValueError,match='Outcomes'):g.validate(forecasts().assign(home_score=30),'development')
    with pytest.raises(ValueError):g.validate(pd.concat([forecasts(),forecasts().iloc[:1]]),'development')
    f=forecasts();f.loc[0,'recipe_sha256']='c'*64
    with pytest.raises(ValueError,match='frozen'):g.validate(f,'development')


def test_actual_offered_prices_change_selection_without_roi_search():
    assert g.choose(.52,0,-110,-110)[0]=='pass'
    assert g.choose(.52,0,100,-110)[0]=='home'
    assert g.choose(.48,0,-110,100)[0]=='away'
    assert g.choose(.6,1,-110,-110)[0]=='pass'
