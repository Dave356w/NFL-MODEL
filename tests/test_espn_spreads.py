"""Settlement, timestamp boundaries, handicap identity and durable evidence."""
import copy
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

import ats_locks
import espn_spreads as e
import season_ats as s


def quote(**changes):
    return dict(game_id='2026_07_TEN_IND', provider_id='100', book='Draft Kings', kind='current',
                captured_utc='2026-10-25T15:59:00Z', quote_utc=None, home_handicap=-3., away_handicap=3.,
                home_odds=-120., away_odds=100., evidence_sha256='test', source_url='https://example.test', **changes)


def pick(**changes):
    row = dict(game_id='2026_07_TEN_IND', selected_side='home', market_spread=3.,
               lock_at_utc='2026-10-25T16:00:00Z', kickoff_utc='2026-10-25T17:00:00Z')
    return row | changes


def evidence():
    def offer(handicap, odds):
        return dict(pointSpread={'american': str(handicap)}, spread={'american': str(odds)},
                    moneyLine={'american': '-999'})
    item = dict(provider={'id': '100', 'name': 'Draft Kings'}, spread=-3.,
                homeTeamOdds=dict(current=offer(-3, -120), close=offer(-3, -125), open=offer(-3.5, -110)),
                awayTeamOdds=dict(current=offer(3, 100), close=offer(3, 105), open=offer(3.5, -110)))
    row = dict(game_id='2026_07_TEN_IND', event_id='123', season=2026, week=7,
               home='IND', away='TEN', completed=True, home_score=23., away_score=20.,
               kickoff_utc='2026-10-25T17:00:00Z', captured_utc='2026-10-26T00:00:00Z',
               odds_url='https://example.test/odds', odds_pages=[{'items': [item]}],
               movements=[dict(provider_id='100', url='https://example.test/movement', pages=[{'items': []}])])
    row['evidence_sha256'] = ats_locks.digest(row)
    return row


@pytest.mark.parametrize('odds,expected', [(-120, 100/120), (105, 1.05), (-100, 1.), (100, 1.)])
def test_american_one_unit_risk(odds, expected):
    assert e.profit(odds) == pytest.approx(expected)


@pytest.mark.parametrize('bad', [0, -99, 99, None, '', np.nan])
def test_invalid_spread_prices_are_unpriced(bad):
    assert np.isnan(e.profit(bad))


def test_home_handicap_sign_and_side_specific_prices_not_moneyline():
    offers = e.quotes([evidence()])
    home = e.match(pick(), offers)
    away = e.match(pick(selected_side='away'), offers)
    assert (home['ats_price'], away['ats_price']) == (-125, 105)
    assert home['ats_price_basis'] == 'closing_estimate'
    assert home['ats_quote_utc'] is None
    assert e.match(pick(market_spread=-3), offers)['ats_price_basis'] == 'unmatched_handicap'


def test_quote_at_cutoff_allowed_one_second_late_rejected():
    q = quote() | {'captured_utc': '2026-10-25T16:00:00Z'}
    assert e.match(pick(), [q])['ats_price_basis'] == 'captured_prelock'
    q['captured_utc'] = '2026-10-25T16:00:01Z'
    assert 'ats_price' not in e.match(pick(), [q])


def test_historical_movement_must_precede_lock_and_not_resurrect_old_line():
    old = quote() | dict(kind='movement', quote_utc='2026-10-25T15:30:00Z',
                         captured_utc='2026-10-26T00:00:00Z')
    newer = old | dict(quote_utc='2026-10-25T15:59:00Z', home_handicap=-3.5, away_handicap=3.5)
    assert e.match(pick(), [old])['ats_price_basis'] == 'historical_prelock'
    assert 'ats_price' not in e.match(pick(), [old, newer])
    newer['quote_utc'] = '2026-10-25T16:00:01Z'
    assert e.match(pick(), [old, newer])['ats_price'] == -120


def test_missing_lock_time_is_not_invented_and_nan_uses_original_forecast_time():
    row = pick(lock_at_utc=np.nan, generated_utc='2026-10-25T16:00:00Z')
    assert e.match(row, [quote()])['ats_price'] == -120
    row.pop('generated_utc')
    assert 'ats_price' not in e.match(row, [quote()])


def test_embedded_candidate_price_takes_precedence_and_never_changes():
    saved = quote()
    row = pick(espn_quote=saved)
    before = copy.deepcopy(row)
    newer = saved | dict(captured_utc='2026-10-25T15:59:59Z', home_odds=-130)
    assert e.match(row, [newer])['ats_price'] == -120
    assert row == before


def test_no_borrowing_other_game_or_handicap_or_moneyline():
    q = quote() | dict(game_id='other')
    assert 'ats_price' not in e.match(pick(), [q])
    q = quote() | dict(home_handicap=-2.5)
    assert 'ats_price' not in e.match(pick(), [q])
    q = quote() | dict(home_odds=0, home_moneyline=-150)
    assert 'ats_price' not in e.match(pick(), [q])


def test_pagination_reads_all_pages_despite_server_page_size():
    seen = []
    def get(url):
        seen.append(url)
        return dict(pageCount=3, items=[len(seen)])
    assert len(e.pages('https://example.test/movement?limit=1000', get)) == 3
    assert 'page=2' in seen[1] and 'page=3' in seen[2]


def test_evidence_tampering_detected(tmp_path):
    row = evidence()
    path = tmp_path / e.STORE
    ats_locks.append(path, [row])
    assert e.validate(tmp_path) == 1
    row['home_score'] = 30.
    path.write_text(json.dumps(row)+'\n')
    with pytest.raises(ValueError, match='hash mismatch'):
        e.validate(tmp_path)


def test_returns_roi_and_cumulative_share_priced_stakes_and_pushes():
    frame = pd.DataFrame([dict(game_id='2026_07_TEN_IND', spread_line=3., fixed_band_ats_side='home',
         fixed_band_ats_result=grade, fixed_band_ats_units=proxy)
         for grade, proxy in [('W', 10/11), ('L', -1), ('P', 0), ('S', 0)]])
    frame.loc[1, 'game_id'] = 'missing_price_loss'
    out = s.price(frame, [evidence()])
    result = s.summary(out)
    assert result['bets'] == 3 and result['priced_bets'] == 2
    assert result['closing_estimates'] == 2 and result['unpriced'] == 1
    assert result['units'] == pytest.approx(.8)
    assert result['roi'] == pytest.approx(.4)  # 1u win + 1u push
    assert np.isnan(out.loc[1, 'fixed_band_ats_units'])
    assert out.ats_cumulative_units.tolist() == pytest.approx([.8, .8, .8, .8])
    assert frame.loc[0, 'fixed_band_ats_units'] == 10/11  # input untouched


def test_unpriced_cohort_has_no_profit_or_roi_even_when_losses_known():
    frame = pd.DataFrame([dict(game_id='x', spread_line=3., fixed_band_ats_side='home',
        fixed_band_ats_result='L', fixed_band_ats_units=-1.)])
    out = s.price(frame, [])
    summary = s.summary(out)
    assert summary['bets'] == summary['unpriced'] == 1
    assert summary['priced_bets'] == 0
    assert np.isnan(summary['units']) and np.isnan(summary['roi'])


def test_explicit_minus110_pool_includes_all_missing_wins_losses_and_pushes():
    frame = pd.DataFrame([dict(game_id='missing', spread_line=3., fixed_band_ats_side='home',
        fixed_band_ats_result=grade, fixed_band_ats_units=proxy)
        for grade, proxy in [('W', 10/11), ('L', -1.), ('P', 0.)]])
    out = s.price(frame, [], assume_unmatched=True)
    result = s.summary(out)
    assert out.ats_price.tolist() == [-110.] * 3
    assert set(out.ats_price_basis) == {'assumed_minus110'}
    assert set(out.ats_match_status) == {'missing_quote'}
    assert result['priced_bets'] == result['assumed_prices'] == 3
    assert result['quoted_bets'] == result['unpriced'] == 0
    assert result['units'] == pytest.approx(10/11-1)
    assert result['roi'] == pytest.approx((10/11-1)/3)
    assert out.ats_home_odds.isna().all()  # no invented provider price for baselines
    assert out.ats_cumulative_units.iloc[-1] == pytest.approx(result['units'])


def test_pooled_price_fallback_never_replaces_a_matched_espn_price():
    frame = pd.DataFrame([dict(game_id=game, spread_line=3., fixed_band_ats_side='home',
        fixed_band_ats_result='W', fixed_band_ats_units=10/11)
        for game in ['2026_07_TEN_IND', 'missing']])
    out = s.price(frame, [evidence()], assume_unmatched=True)
    result = s.summary(out)
    assert out.ats_price.tolist() == [-125., -110.]
    assert result['closing_estimates'] == result['assumed_prices'] == 1
    assert result['units'] == pytest.approx(.8 + 10/11)
    assert result['roi'] == pytest.approx((.8 + 10/11)/2)


def test_espn_final_score_cannot_create_selection():
    latest = dict(manifest={'revision': 'test'}, espn_archive=[evidence()])
    out = s.build(latest, pd.DataFrame())
    assert out.iloc[0].result == 3
    assert out.iloc[0].ats_status == 'unavailable'
    assert out.iloc[0].fixed_band_ats_side == ''
    assert np.isnan(out.iloc[0].fixed_band_ats_units)


def test_candidate_capture_does_not_backdate_later_received_movement(tmp_path):
    raw = evidence()
    item = raw['odds_pages'][0]['items'][0]
    raw['movements'][0]['pages'][0]['items'] = [dict(timestamp='2026-10-25T15:30:00Z',
        homeTeamOdds=item['homeTeamOdds']['current'], awayTeamOdds=item['awayTeamOdds']['current'])]
    ats_locks.append(tmp_path / e.STORE, [raw])
    row = pick(observed_utc='2026-10-25T15:59:30Z')
    assert e.candidate_quote(row, tmp_path) is None
    parsed = e.quotes([raw])
    assert e.match(row, parsed)['ats_price_basis'] == 'historical_prelock'
