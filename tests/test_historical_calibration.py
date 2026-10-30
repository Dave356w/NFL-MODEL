import datetime as dt
import hashlib
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import build_site as b
import historical_calibration as c


def game(gid, year=2026, week=7, result=6., line=6.5, mapped=4., p=.6, q=.65):
    return dict(game_id=gid, season=year, week=week, home='H', away='A',
                result=result, spread_line=line, fixed_band_spread=mapped,
                model_wp=p, market_wp=q)


def latest(history, board=(), season=2026, week=8):
    return dict(manifest=dict(season=season, week=week),
                fixed_band_ledger=pd.DataFrame(history), board=pd.DataFrame(board))


def select(rows, view, band, side='both'):
    return next(r for r in rows if (r['view'], r['band'], r['side']) == (view, band, side))


def test_current_week_only_enters_when_every_board_game_is_final():
    partial = game('early', week=8)
    other = game('late', week=8, result=np.nan)
    source = latest([game('old', 2023), game('prior'), partial,
                     game('future', week=9), game('too-old', 2022)], [partial, other])
    before = source['fixed_band_ledger'].copy(deep=True)
    assert set(c.history(source).game_id) == {'old', 'prior'}
    assert c.build(source)['coverage'] == {2023: 7, 2026: 7}
    pd.testing.assert_frame_equal(source['fixed_band_ledger'], before)
    source['board'].loc[source['board'].game_id.eq('late'), 'result'] = -3.
    ready = c.history(source)
    assert set(ready.game_id) == {'old', 'prior', 'early', 'late'}
    assert not ready.game_id.duplicated().any()
    assert c.build(source)['coverage'][2026] == 8


def test_probabilities_use_decided_games_but_mov_includes_losses_and_ties():
    frame = pd.DataFrame([game('win', result=7., p=.65),
                          game('loss', result=-10., p=.65),
                          game('tie', result=0., p=.65)])
    rows = c.wp_rows(frame, 'model_wp', 'model_wp')
    home = select(rows, 'model_wp', '60–<70%', 'home')
    assert home['observations'] == 3 and home['decided'] == 2 and home['ties'] == 1
    assert home['actual_wp'] == .5 and home['implied_wp'] == .65
    assert home['gap_pp'] == pytest.approx(-15.)
    assert home['median_mov'] == 0.  # median of +7, -10 and 0, not winners only
    away = select(rows, 'model_wp', '30–<40%', 'away')
    assert away['actual_wp'] == .5 and away['median_mov'] == 0.


def test_probability_boundaries_and_paired_side_uncertainty():
    frame = pd.DataFrame([game('edge', p=.2), game('even', p=.5), game('certain', p=1.)])
    rows = c.wp_rows(frame, 'model_wp', 'model_wp')
    assert select(rows, 'model_wp', '20–<30%', 'home')['observations'] == 1
    assert select(rows, 'model_wp', '80–100%', 'home')['observations'] == 1
    even = select(rows, 'model_wp', '50–<60%')
    assert even['observations'] == even['decided'] == 2
    assert even['actual_wp'] == even['implied_wp'] == .5
    assert even['se_pp'] is None  # two sides of one game are not two independent games
    assert c.standard_error([.5, -.5, .5, -.5], ['a', 'a', 'b', 'b']) == 0.
    complement = c.wp_rows(pd.DataFrame([game('complement', p=.8)]), 'model_wp', 'model_wp')
    assert select(complement, 'model_wp', '20–<30%', 'away')['observations'] == 1


def test_margin_calibration_uses_forecast_favorite_and_own_forecast():
    frame = pd.DataFrame([game('dog'),  # ATS pick is away, but model favorite is home
                          game('exact', result=3., line=3., mapped=3.),
                          game('model-away', result=10., line=12., mapped=-4.)])
    market = c.margin_rows(frame, 'spread_line', 'market_spread')
    model = c.margin_rows(frame, 'fixed_band_spread', 'model_spread')
    mr = select(market, 'market_spread', '3–<7 points', 'forecast_favorite')
    pr = select(model, 'model_spread', '3–<7 points', 'forecast_favorite')
    assert mr['observations'] == 2
    assert (mr['above_forecast'], mr['at_forecast'], mr['below_forecast']) == (0, 1, 1)
    # Model's own 3–<7 band also contains its away favorite in the market's 10+ band.
    assert pr['observations'] == 3
    assert (pr['above_forecast'], pr['at_forecast'], pr['below_forecast']) == (1, 1, 1)
    assert pr['median_mov'] == 3.  # median of +6, +3, -10 toward model favorites
    assert pr['implied_mov'] == pytest.approx(11/3)  # all projections positive
    assert pr['median_error'] == 0.  # median of +2, 0, -14; not median MOV - mean forecast
    assert mr['median_error'] == -.25
    tied = c.margin_rows(pd.DataFrame([game('tie', result=0., line=3., mapped=4.)]),
                         'fixed_band_spread', 'model_spread')
    tie = select(tied, 'model_spread', '3–<7 points', 'forecast_favorite')
    assert tie['below_forecast'] == 1 and tie['median_mov'] == 0. and tie['median_error'] == -4.


def test_margin_boundaries_exclusions_and_same_game_cohort():
    frame = pd.DataFrame([game('three', line=3., mapped=-3.),
                          game('seven', line=-7., mapped=-7., result=-10.),
                          game('ten', line=10., mapped=10.),
                          game('missing', mapped=np.nan), game('infinite', line=np.inf),
                          game('market-pickem', line=0.), game('model-pickem', mapped=0.)])
    for column in ['spread_line', 'fixed_band_spread']:
        rows = c.margin_rows(frame, column, 'test')
        seven = select(rows, 'test', '7–<10 points', 'forecast_favorite')
        assert seven['observations'] == 1 and seven['median_mov'] == 10.
        assert seven['median_error'] == 3. and seven['above_forecast'] == 1
        assert select(rows, 'test', '3–<7 points', 'forecast_favorite')['observations'] == 1
        assert select(rows, 'test', '10+ points', 'forecast_favorite')['observations'] == 1
        empty = select(rows, 'test', '<3 points', 'forecast_favorite')
        assert empty['observations'] == 0 and empty['median_error'] is None
        assert sum(r['observations'] for r in rows) == 3


def test_history_filters_invalid_probabilities_and_rejects_duplicates():
    source = latest([game('ok'), game('bad-p', p=1.1), game('missing-q', q=np.nan)])
    assert list(c.history(source).game_id) == ['ok']
    with pytest.raises(ValueError, match='Duplicate'):
        c.history(latest([game('same'), game('same')]))


def test_render_has_four_views_season_filter_and_aggregate_only_download():
    source = latest([game('a', 2023), game('b', 2024), game('c', 2025), game('d')])
    pack = c.build(source)
    html = b.render_historical_calibration(source, 'test', pack)
    assert "href='historical-calibration.html' aria-current=\"page\"" in html
    assert 'Market implied vs actual WP' in html and 'Model implied vs actual WP' in html
    assert 'Market spread vs actual MOV' in html and 'Model spread vs actual MOV' in html
    assert 'Median forecast error' in html and 'Above / at / below forecast' in html
    assert 'Avg implied MOV' not in html and '>Units<' not in html and '>ROI<' not in html
    assert 'Median MOV' in html and 'Median actual MOV' in html
    assert "id='cal-season'" in html and "select.addEventListener('change'" in html
    assert all(f"data-cal-season='{year}'" in html for year in ['all', '2023', '2024', '2025', '2026'])
    assert '2026 through Week 7' in html and 'full weekly slate' in html
    visible = re.sub(r'<style>.*?</style>|<script>.*?</script>', '', html, flags=re.S)
    assert not re.search(r'\bnan\b|\bNaN\b|\bNone\b', visible)
    table = c.export(pack)
    assert len(table) == 5 * (8*3*2 + 4*2)
    assert set(table.view) == {'market_wp', 'model_wp', 'market_spread', 'model_spread'}
    assert {'median_error', 'above_forecast', 'at_forecast', 'below_forecast'} <= set(table.columns)
    assert not {'units', 'roi', 'cover_rate'} & set(table.columns)
    assert not {'game_id', 'home_moneyline', 'away_moneyline', 'model_wp'} & set(table.columns)


def test_empty_history_renders_and_download_has_stable_headers():
    for source in [None, latest([]), latest([], [game('pending', result=np.nan, week=8)])]:
        pack = c.build(source)
        assert pack['panels'] == []
        assert c.export(pack).empty and list(c.export(pack).columns) == c.EXPORT_COLUMNS
        assert 'No completed weeks' in b.render_historical_calibration(source, 'test', pack)


def test_committed_history_stops_at_completed_week_and_render_keeps_archives(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = b.load_latest(root/'data/latest')
    pack = c.build(source)
    assert set(pack['coverage']) == {2023, 2024, 2025, 2026}
    assert all(p['season'] == 'all' or int(p['season']) >= 2023 for p in pack['panels'])
    all_rows = pack['panels'][0]['rows']
    assert sum(r['observations'] for r in all_rows if r['view'] == 'model_wp' and r['side'] == 'both') == 2*pack['panels'][0]['games']
    board = source['board']
    if board.result.isna().any():
        assert pack['coverage'][int(source['manifest']['season'])] < int(source['manifest']['week'])
    paths = [root/'data'/name for name in ['forward_predictions.jsonl', 'ats_locks.jsonl', 'ats_lock_candidates.jsonl']]
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    b.render_historical_calibration(source, 'test', pack)
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
