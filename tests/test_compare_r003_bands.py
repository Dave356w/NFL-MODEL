"""Band comparisons preserve probability semantics, cohorts and push settlement."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import compare_r003_bands as c


def forecasts():
    rows=[]
    for model,p in [(c.PLAIN,.6),('other',.4),('fair',.5)]:
        for game,home,line,push,mean in [('a',24,3,0.,4.),('b',21,4,.1,2.)]:
            rows.append(dict(model=model,game_id=game,season=2023,week=1,home_score=home,away_score=17,
                spread_line=line,total_line=44,cover_conditional=p,cover_win=(1-push)*p,
                cover_push=push,cover_lose=(1-push)*(1-p),margin_mean=mean))
    return pd.DataFrame(rows)


def test_probability_band_endpoints_include_break_even_in_pass_band():
    bands=c.probability_band([.5,11/21,.55,.6,.65,.9])
    assert list(bands)==[c.PROB_LABELS[i] for i in [0,0,1,2,3,4]]


def test_common_cohort_keeps_plain_side_when_other_model_reverses():
    f=c.prepare(forecasts());other=f[(f.model=='other')&(f.game_id=='a')].iloc[0]
    assert other.label==0 and other.common_label==1
    assert other.confidence==.6 and other.common_probability==.4
    assert other.common_plain_probability_band==c.PROB_LABELS[2]
    own=c.summary(f[f.model=='other']);common=c.summary(f[f.model=='other'],True)
    assert own['actual_cover']==0 and common['actual_cover']==1
    assert own['cover_ll']==common['cover_ll']


def test_push_and_pass_denominators_and_price_profit():
    f=c.prepare(forecasts());plain=c.summary(f[f.model==c.PLAIN]);fair=c.summary(f[f.model=='fair'])
    assert plain['games']==2 and plain['decisive']==1
    assert (plain['bets'],plain['wins'],plain['losses'],plain['pushes'])==(2,1,0,1)
    assert plain['units']==pytest.approx(10/11)
    assert plain['fair_null_roi']==pytest.approx(-1/44)
    assert fair['bets']==0 and np.isnan(fair['roi']) and fair['units']==0


def test_projected_value_uses_probability_side_and_missing_means_are_explicit():
    raw=forecasts();raw.loc[(raw.model=='other')&(raw.game_id=='b'),'margin_mean']=np.nan
    f=c.prepare(raw)
    row=f[(f.model=='other')&(f.game_id=='a')].iloc[0]
    assert row.chosen_handicap==3 and row.projected_value==-1
    assert row.projected_value_band=='≤0'
    assert f[(f.model=='other')&(f.game_id=='b')].iloc[0].projected_value_band=='Unavailable'


def test_invalid_mass_and_missing_reference_fail():
    raw=forecasts();bad=raw.copy();bad.loc[0,'cover_win']=.9
    with pytest.raises(ValueError,match='probabilities'):c.prepare(bad)
    with pytest.raises(ValueError,match='Missing plain'):c.prepare(raw[~((raw.model==c.PLAIN)&(raw.game_id=='a'))])


def test_wilson_interval_and_empty_sample():
    lo,hi=c.wilson(50,100)
    assert lo<.5<hi and lo==pytest.approx(1-hi)
    assert np.isnan(c.wilson(0,0)).all()
