"""The active spread architecture and saved revision control every ATS surface."""
import datetime as dt
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.special import ndtr

import ats_policy
import build_site as site


CURRENT = 'boxscore-composite-v1.19'
LEGACY = 'boxscore-composite-v1.18'
NOW = dt.datetime(2026, 10, 26, 4, tzinfo=dt.timezone.utc)


def current_fixture():
    row = dict(game_id='2026_07_TEN_IND', season=2026, week=7, home='IND', away='TEN',
               gameday='2026-10-25', gametime='13:00', ready=True,
               model_wp=float(ndtr(8.25/12.37)), model_spread=8.25, spread_line=7.5,
               result=7., home_score=24., away_score=17., **{'home won': 1.})
    older = dict(row, game_id='2025_01_TEN_IND', season=2025, week=1, gameday='2025-09-07',
                 model_spread=1.25, model_wp=float(ndtr(1.25/12.37)), spread_line=3.5)
    # A refreshed board must not replace the completed selection's handicap.
    board = dict(row, model_spread=1.25, model_wp=float(ndtr(1.25/12.37)),
                 spread_line=2.5, result=np.nan, home_score=np.nan, away_score=np.nan)
    return dict(manifest=dict(revision=CURRENT, season=2026, week=7,
                             generated_utc=NOW.isoformat(),
                             recipe=dict(architecture='market_spread_total', family='rates_core_avail_cs')),
                retro_ledger=pd.DataFrame([older, row]), board=pd.DataFrame([board]))


def test_continuous_adapter_never_fits_or_applies_median_map(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Current continuous forecasts must not use median-map fitting')

    monkeypatch.setattr(ats_policy.fixed_bands, 'fit', forbidden)
    monkeypatch.setattr(ats_policy.fixed_bands, 'apply', forbidden)
    latest = current_fixture()
    ats_policy.prepare(latest)
    row = latest['ats_ledger'].set_index('game_id').loc['2026_07_TEN_IND']
    assert np.allclose([row.model_spread, row.raw_spread, row.ats_spread, row.fixed_band_spread], 8.25, atol=1e-12, rtol=0)
    # Raw 8.25 selects IND -7.5 and loses. The retired map's 7 would select TEN.
    assert (row.ats_side, row.ats_team, row.ats_handicap, row.ats_result, row.ats_units) == (
        'home', 'IND', -7.5, 'L', -1.)
    assert latest['fixed_band_rules'] == []
    assert latest['board'].iloc[0].fixed_band_spread == pytest.approx(1.25, abs=1e-12)
    assert row.selection_version == ats_policy.fixed_bands.SELECTION_VERSION
    assert set(ats_policy.summary(latest).method) == {'Continuous spread'}


def test_architecture_dispatch_keeps_saved_legacy_behavior_despite_current_code(monkeypatch):
    calls = []

    def legacy_prepare(latest):
        calls.append(latest['manifest']['revision'])
        latest['legacy_prepared'] = True

    monkeypatch.setattr(ats_policy.fixed_bands, 'prepare', legacy_prepare)
    monkeypatch.setattr(site.m, 'REVISION', CURRENT)
    latest = dict(manifest=dict(revision=LEGACY, recipe={}))
    ats_policy.prepare(latest)
    assert not ats_policy.is_continuous(latest)
    assert latest['legacy_prepared'] and calls == [LEGACY]


def test_active_lock_downloads_exclude_other_revisions_and_retired_selection_methods(monkeypatch):
    latest = current_fixture()
    old = dict(selection_method='median_signed_mov')
    new = dict(selection_method='continuous_spread')
    saved = {(LEGACY, 'old'): old, (CURRENT, 'new'): new, (CURRENT, 'wrong_method'): old}
    monkeypatch.setattr(site.ats_locks, 'display_records', lambda data: saved)
    assert site.active_ats_locks(latest, Path('unused')) == {(CURRENT, 'new'): new}


def test_saved_continuous_lock_uses_canonical_raw_margin_not_retired_alias():
    latest = current_fixture()
    ats_policy.prepare(latest)
    row = latest['board'].iloc[0].to_dict()
    latest['ats_locks'] = {(CURRENT, row['game_id']): dict(
        model_spread=8.25, raw_spread=8.25, fixed_band_spread=99., market_spread=7.5,
        selection_method='continuous_spread', lock_at_utc='2026-10-25T16:00:00Z',
        generated_utc='2026-10-25T15:59:00Z', selected_side='home')}
    state = site.ats_card_state(latest, row, NOW)
    assert (state['status'], state['model_spread'], state['spread_line'], state['selected_team']) == (
        'locked', 8.25, 7.5, 'IND')


def test_public_revision_badge_follows_manifest_on_every_page(monkeypatch):
    monkeypatch.setattr(site.m, 'REVISION', CURRENT)
    legacy = dict(manifest=dict(revision=LEGACY, season=2026, week=7, recipe={}),
                  board=pd.DataFrame())
    pages = [site.render_index(legacy, pd.DataFrame(), 'test', NOW),
             site.render_grades(pd.DataFrame(), legacy, 'test'),
             site.render_calibration(legacy, pd.DataFrame(), 'test')]
    for html in pages:
        assert "class='brand-version'>v1.18</span>" in html
        assert "class='brand-version'>v1.19</span>" not in html


def test_current_board_and_pool_work_before_a_historical_export_exists():
    latest = current_fixture()
    ats_policy.prepare(latest)
    latest['pooled_ats'] = latest['ats_ledger'].loc[latest['ats_ledger'].season.eq(2026)].assign(
        ats_basis='Retrospective v1.19')
    latest['ats_ledger'] = pd.DataFrame()
    history = site.public_ats_history(latest)
    assert history.game_id.tolist() == ['2026_07_TEN_IND']
    latest = current_fixture()
    latest['retro_ledger'] = pd.DataFrame()
    ats_policy.prepare(latest)
    assert latest['board'].iloc[0].fixed_band_spread == pytest.approx(1.25, abs=1e-12)
    assert latest['fixed_band_rules'] == []


def test_canonical_probability_conversion_prevents_rounded_column_side_change_near_equality():
    latest = current_fixture()
    latest['retro_ledger'] = pd.DataFrame()
    line = -3.
    margin = line + 4*ats_policy.fixed_bands.EPS
    latest['board'] = latest['board'].assign(model_wp=float(ndtr(margin/12.37)),
                                            model_spread=line, spread_line=line)
    ats_policy.prepare(latest)
    row = latest['board'].iloc[0]
    assert row.model_spread > line + ats_policy.fixed_bands.EPS
    # The rounded -3-vs- -3 column would choose the away favorite. The canonical
    # saved-probability conversion selects home, exactly as future locks do.
    assert row.ats_side == 'home'
    state = site.ats_card_state(latest, row.to_dict(), NOW-dt.timedelta(days=2))
    assert state['selected_side'] == 'home'
    missing = current_fixture()
    missing['board'] = missing['board'].drop(columns='model_wp').assign(model_spread=1.25)
    ats_policy.prepare(missing)
    assert missing['board'].iloc[0].model_spread == 1.25


def test_rebuilt_current_results_cards_and_csvs_all_use_continuous_policy(tmp_path, monkeypatch):
    latest = current_fixture()
    data = tmp_path/'data'
    folder = data/'latest'
    folder.mkdir(parents=True)
    (folder/'manifest.json').write_text(json.dumps(latest['manifest']))
    latest['retro_ledger'].to_csv(folder/'retro_ledger.csv', index=False)
    latest['board'].to_csv(folder/'board.csv', index=False)
    old_archive = data/'ats_forward_shadow.jsonl'
    old_archive.write_bytes(b'{"original":"v1.18 archive remains unchanged"}\n')
    original = old_archive.read_bytes()
    # Legacy selections must not override the new revision, including downloads.
    old_lock = dict(model_wp=.9, fixed_band_spread=3., market_spread=2.5,
                    selected_side='home', game_id='2026_07_TEN_IND')
    monkeypatch.setattr(site.ats_locks, 'display_records', lambda path: {(LEGACY, old_lock['game_id']): old_lock})
    monkeypatch.setattr(site, 'published_report', lambda path: 'Backend report handled separately.\n')
    out = tmp_path/'public'
    site.render_all(out, data, now=NOW)
    season = pd.read_csv(out/'ats_2026_results.csv', keep_default_na=False).set_index('game_id')
    board = pd.read_csv(out/'fixed_band_board.csv', keep_default_na=False).set_index('game_id')
    history = pd.read_csv(out/'ats_history_results.csv', keep_default_na=False)
    selected = season.loc['2026_07_TEN_IND']
    shown = board.loc['2026_07_TEN_IND']
    assert selected.model_spread == pytest.approx(8.25, abs=1e-12)
    assert shown.model_spread == pytest.approx(8.25, abs=1e-12)
    assert (selected.spread_line, selected.fixed_band_ats_result) == (7.5, 'L')
    assert (shown.spread_line, shown.ats_result, shown.selected_team) == (7.5, 'L', 'IND')
    assert set(history.season) == {2025, 2026} and not history.game_id.duplicated().any()
    assert not (out/'ats_locked_picks.csv').exists()
    assert old_archive.read_bytes() == original
    assert json.loads((folder/'fixed_band_rules.json').read_text()) == []
    for page in ['index.html', 'grades.html', 'market-calibration.html']:
        html = (out/page).read_text()
        assert "class='brand-version'>v1.19</span>" in html
        assert 'median' not in html.lower()
        for hidden in ['moneyline', 'win probability', 'no-vig']:
            assert hidden not in html.lower()
    assert 'ATS result · L' in (out/'index.html').read_text()
    assert '0.8-point difference from market' in (out/'index.html').read_text()
    performance = (out/'market-calibration.html').read_text()
    assert 'By season' in performance and '2025' in performance
    assert 'market spread and total' in performance
    for path in out.glob('*.csv'):
        columns = pd.read_csv(path).columns
        assert not any('moneyline' in c or 'model_wp' in c or c == 'ats_basis' for c in columns)
