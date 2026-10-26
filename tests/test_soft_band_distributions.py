"""SB1 chronology, coherent PMF interpolation, exact quotes and reproducibility."""
import copy
import json

import numpy as np
import pandas as pd
import pytest

from research import soft_band_distributions as s


def history():
    rows = []
    magnitudes = [1.5, 2.5, 4.5, 5.5, 8.5, 9.5, 11.5, 13.5]
    for year in (2021, 2022, 2023):
        for week in range(1, 17):
            for i in range(16):
                magnitude = magnitudes[i % 8]
                sign = 1 if i % 2 == 0 else -1
                band = np.digitize(magnitude, s.CUTS)
                y = [-14, -7, -3, 0, 3, 7, 14, 21][(i+week) % 8]+2*band
                rows.append(dict(game_id=f'{year}_{week}_{i}', season=year, week=week,
                    raw_spread=sign*magnitude, spread_line=sign*(round(magnitude)+(.5 if i%3 else 0)),
                    result=sign*y, home_spread_odds=-110., away_spread_odds=-110.,
                    paired_price_basis='synthetic', input_basis='synthetic'))
    return pd.DataFrame(rows)


@pytest.fixture
def fitted():
    f = history()
    return s.fit_prior(f[f.season < 2023], 2023)


def test_fit_has_strict_prior_season_support_and_empirical_counts(fitted):
    assert fitted['training_games'] == 512
    assert fitted['training_max_season'] == 2022
    assert sum(fitted['band_counts']) == 512
    s.validate_fit(fitted)
    f = history().query('season < 2023')
    signed = np.sign(f.raw_spread)*f.result
    for k in range(4):
        mask = np.digitize(abs(f.raw_spread), s.CUTS) == k
        expected = np.bincount((signed[mask]+100).astype(int), minlength=201)
        np.testing.assert_array_equal(fitted['counts'][k], expected)
    with pytest.raises(ValueError, match='own/future'):
        s.fit_prior(history(), 2023)
    with pytest.raises(ValueError, match='two earlier seasons'):
        s.fit_prior(history().query('season == 2021'), 2023)
    with pytest.raises(ValueError, match='30 observations'):
        s.fit_prior(f[abs(f.raw_spread) < 10], 2023)


def test_soft_weights_are_convex_adjacent_and_endpoint_clamped(fitted):
    c = fitted['centers']
    np.testing.assert_array_equal(s.weights(0, c), [1,0,0,0])
    np.testing.assert_array_equal(s.weights(100, c), [0,0,0,1])
    for k in range(3):
        w = s.weights((c[k]+c[k+1])/2, c)
        expected = np.zeros(4);expected[k:k+2] = .5
        np.testing.assert_allclose(w, expected)
    for x in np.linspace(0, 30, 100):
        w = s.weights(x, c)
        assert (w >= 0).all() and w.sum() == pytest.approx(1)
        assert np.count_nonzero(w) <= 2
    for bad in (-1, np.nan, np.inf):
        with pytest.raises(ValueError):s.weights(bad, c)
    with pytest.raises(ValueError):s.weights(3, [1,4,4,12])


def test_soft_mixture_preserves_observed_margin_atoms_and_key_number_mass(fitted):
    c = fitted['centers'];raw=(c[1]+c[2])/2
    p,w = s.forecast(raw, fitted)
    counts = np.asarray(fitted['counts'])
    normalized = counts/counts.sum(1, keepdims=True)
    np.testing.assert_allclose(p, .5*normalized[1]+.5*normalized[2])
    assert p.sum() == pytest.approx(1)
    assert not p[(counts[1]+counts[2]) == 0].any()
    for margin in (3,7,14):
        ix=int(margin+100)
        assert p[ix] == pytest.approx(.5*normalized[1,ix]+.5*normalized[2,ix])


@pytest.mark.parametrize('cut', [3,7,10])
def test_soft_pmf_and_cover_are_continuous_across_original_cuts(cut, fitted):
    lo,_ = s.forecast(cut-1e-8, fitted)
    hi,_ = s.forecast(cut+1e-8, fitted)
    assert abs(lo-hi).sum() < 1e-7
    np.testing.assert_allclose(s.event(lo, 3.5), s.event(hi, 3.5), atol=1e-7)


def test_hard_control_uses_identical_empirical_distributions(fitted):
    counts=np.asarray(fitted['counts'])
    for k,x in enumerate([1.,4.,8.,11.]):
        p,w=s.forecast(x,fitted,soft=False)
        np.testing.assert_allclose(p,counts[k]/counts[k].sum())
        np.testing.assert_array_equal(w,np.eye(4)[k])


def test_away_orientation_reverses_outcome_margins_and_cover_sides(fitted):
    home,_=s.forecast(8.,fitted);away,_=s.forecast(-8.,fitted)
    np.testing.assert_allclose(home,away[::-1])
    h,p,a=s.event(home,7.);ar,pr,hr=s.event(away,-7.)
    np.testing.assert_allclose([h,p,a],[hr,pr,ar])
    with pytest.raises(ValueError,match='nonzero'):s.forecast(0,fitted)


def test_event_uses_exact_integer_push_mass_and_half_points():
    p=np.zeros(201);p[103]=.3;p[107]=.2;p[93]=.5
    np.testing.assert_allclose(s.event(p,3.),[.2,.3,.5])
    np.testing.assert_allclose(s.event(p,3.5),[.2,0.,.8])
    for bad in [p*2, p*np.nan, p[:-1]]:
        with pytest.raises(ValueError,match='PMF'):s.event(bad,3)
    with pytest.raises(ValueError):s.event(p,np.inf)


def test_price_aware_ev_passes_break_even_and_refunds_pushes():
    assert s.choose([.5,0,.5],-110,-110)==('pass',0.)
    assert s.choose([11/21,0,10/21],-110,-110)==('pass',0.)
    assert s.choose([.53,0,.47],-110,-110)[0]=='home'
    assert s.choose([.53,0,.47],-120,-110)[0]=='pass'
    assert s.choose([.47,0,.53],120,-120)[0]=='home'
    assert s.choose([0,1,0],-110,-110)==('pass',0.)
    assert s.choose([.48,.1,.42],-110,-110)[0]=='home'
    assert s.settle('home',3,3,-120,105)==('P',0.)
    assert s.settle('home',4,3,-120,105)==('W',100/120)
    assert s.settle('away',2,3,-120,105)==('W',1.05)
    assert s.settle('home',2,3,-120,105)==('L',-1.)
    assert s.settle('pass',4,3,-120,105)==('S',0.)
    with pytest.raises(ValueError):s.choose([.6,0,.6],-110,-110)
    for bad in (0,99,-99,np.nan,None):
        with pytest.raises(ValueError):s.payout(bad)


def test_own_season_outcome_poisoning_never_changes_forecasts_or_fits():
    f=history();pred,fits=s.evaluate(f)
    poison=f.copy();poison.loc[poison.season.eq(2023),'result']=50
    changed,changed_fits=s.evaluate(poison)
    assert fits==changed_fits
    fields=['soft_home_cover','soft_push','soft_away_cover','hard_home_cover',
            'soft_weight_0','soft_weight_1','soft_weight_2','soft_weight_3',
            'assumed110_soft_ev_side','paired_soft_ev_side','fit_sha256']
    pd.testing.assert_frame_equal(pred[fields],changed[fields])


def test_prices_change_selection_inputs_only_not_forecast_distribution():
    f=history();base,_=s.evaluate(f)
    f.loc[f.season.eq(2023),['home_spread_odds','away_spread_odds']]=[-120.,100.]
    changed,_=s.evaluate(f)
    for field in ['soft_home_cover','soft_push','soft_away_cover','fit_sha256']:
        pd.testing.assert_series_equal(base[field],changed[field])
    assert not np.allclose(base.market_conditional_home,changed.market_conditional_home)


def test_duplicate_missing_noninteger_and_zero_inputs_are_rejected():
    f=history()
    with pytest.raises(ValueError,match='duplicate'):s.clean(pd.concat([f,f.iloc[:1]]))
    for field,value in [('raw_spread',0),('raw_spread',np.nan),('result',1.5),('result',101),('result',np.nan),('week',1.5)]:
        changed=f.copy();changed[field]=changed[field].astype(float);changed.loc[0,field]=value
        with pytest.raises(ValueError):s.clean(changed)


def test_saved_fit_tampering_future_metadata_and_count_corruption_are_rejected(fitted):
    bad=copy.deepcopy(fitted);bad['counts'][0][103]+=1
    with pytest.raises(ValueError,match='hash'):s.forecast(3,bad)
    bad['fit_sha256']=s.digest({k:v for k,v in bad.items() if k!='fit_sha256'})
    with pytest.raises(ValueError,match='count totals'):s.forecast(3,bad)
    bad=copy.deepcopy(fitted);bad['training_max_season']=2023
    with pytest.raises(ValueError,match='future'):s.forecast(3,bad)


def test_missing_paired_prices_stay_out_of_paired_scenario(monkeypatch):
    monkeypatch.setattr(s,'REPEATS',128)
    f=history();f['home_spread_odds']=np.nan
    pred,fits=s.evaluate(f);result=s.report(pred,fits)
    assert not pred.paired_prices.any()
    main=result['bases']['2023-25']
    assert main['gains']['soft_vs_market_cover']['n']==0
    assert main['scenarios']['paired']['soft_ev']['bets']==0
    assert main['scenarios']['assumed110']['soft_ev']['games']==256
    assert 'failed' in result['status']
    assert 'Unavailable' in s.markdown(result)


def test_all_push_outcomes_have_no_binary_score_or_decisive_calibration(monkeypatch):
    monkeypatch.setattr(s,'REPEATS',128)
    f=history();f['spread_line']=np.rint(f.spread_line)
    f.loc[f.season.eq(2023),'result']=f.loc[f.season.eq(2023),'spread_line']
    pred,fits=s.evaluate(f);result=s.report(pred,fits)
    assert not pred.binary_scored.any()
    assert pred.soft_cover_ll.isna().all()
    assert result['bases']['2023-25']['scores']['soft_cover_ll'] is None
    assert result['bases']['2023-25']['gains']['soft_vs_market_cover']['n']==0
    assert result['bases']['2023-25']['scenarios']['paired']['soft_ev']['cover_rate'] is None
    assert 'Unavailable' in s.markdown(result)


def test_replay_is_deterministic_and_rejects_production_output_paths(tmp_path,monkeypatch):
    monkeypatch.setattr(s,'REPEATS',128)
    source=tmp_path/'input.csv';history().to_csv(source,index=False)
    out=tmp_path/'results';s.run(source,out)
    before={p.name:p.read_bytes() for p in out.iterdir()}
    s.run(source,out)
    assert before=={p.name:p.read_bytes() for p in out.iterdir()}
    pred=pd.read_csv(out/'predictions.csv');result=json.loads((out/'results.json').read_text())
    assert pred.game_id.nunique()==len(pred)==256
    assert (pred.training_max_season<pred.season).all()
    r=result['bases']['2023-25']['scenarios']['assumed110']['soft_ev']
    assert r['bets']+r['passes']==len(pred)
    assert r['wins']+r['losses']+r['pushes']==r['bets']
    assert r['units']==pytest.approx(pred.assumed110_soft_ev_units.sum())
    for path in (s.ROOT/'data',s.ROOT/'data/latest/evil.csv',s.ROOT/'public/evil.csv'):
        with pytest.raises(ValueError,match='cannot write'):s.writable(path)
