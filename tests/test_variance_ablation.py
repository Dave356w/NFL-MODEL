import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import variance_ablation as v
import variance_inputs as vi
from test_score_peaks import boxes_and_schedule
from test_product_production import fixture


def test_bootstrap_reproduces_profiles_and_excludes_same_future_games():
    box, schedule = boxes_and_schedule()
    pack = v.m.lagged_features(box, schedule, 8., profile_families=('rates_core',))
    pack = pack.rename(columns={'home': 'home', 'away': 'away'})
    a, audit = vi.bootstrap_pack(box, pack, draws=32)
    assert audit.max_abs_error.max() < 1e-12 and audit.missing_mismatch.sum() == 0
    shock = box.copy()
    for team, lead, deficit in [('H', 40., 1.), ('A', 1., 40.)]:
        shock.loc[(shock.team == team)&(shock.week >= 2), ['max_lead', 'max_deficit']] = [lead, deficit]
    changed = v.m.lagged_features(shock, schedule, 8., profile_families=('rates_core',))
    b, _ = vi.bootstrap_pack(shock, changed, draws=32)
    np.testing.assert_allclose(a.iloc[:2][vi.MAIN], b.iloc[:2][vi.MAIN], equal_nan=True)
    assert not np.allclose(a.iloc[2][vi.MAIN].to_numpy(float), b.iloc[2][vi.MAIN].to_numpy(float), equal_nan=True)
    # Shared whole-game draws preserve the exact opposing peak relation.
    np.testing.assert_allclose(a.d__max_lead, a.d__max_deficit)


def reliability_fixture():
    pack = pd.DataFrame({'game_id': ['g'+str(i) for i in range(8)], 'season': 2020,
                         'week': np.arange(1, 9), 'ready': True, 'q': .6})
    for c in v.m.PRODUCT_CONTEXT_NAMES: pack[c] = 0.
    for c in vi.MAIN: pack[c] = np.arange(1, 9, dtype=float)
    noise = pd.DataFrame({'game_id': pack.game_id})
    for c in vi.MAIN: noise[c] = np.linspace(.1, 3., len(pack))
    return pack, noise


def test_reliability_is_point_in_time_row_specific_and_preserves_other_inputs():
    pack, noise = reliability_fixture()
    a, audit = vi.reliability(pack, noise, minimum=2)
    shock = pack.copy(); shock.loc[shock.week >= 4, vi.MAIN] += 1000
    _, changed = vi.reliability(shock, noise, minimum=2)
    early = audit.week <= 4
    np.testing.assert_array_equal(audit.loc[early, 'reliability'], changed.loc[early, 'reliability'])
    assert audit.reliability.between(0, 1).all()
    assert audit[audit.reference_max_season > 0].reference_max_week.lt(audit[audit.reference_max_season > 0].week).all()
    assert audit[audit.feature == vi.MAIN[0]].reliability.nunique() > 1
    other = [c for c in pack if c not in vi.MAIN]
    pd.testing.assert_frame_equal(a[other], pack[other])
    # A fixed multiplier would cancel under SD scaling; these time-varying factors do not.
    x, z = pack[vi.MAIN[0]].to_numpy(), a[vi.MAIN[0]].to_numpy()
    assert not np.allclose(x/x.std(), z/z.std())


def pruning_fixture():
    base = pd.DataFrame([{'game_id': f'{y}_{w}', 'season': y, 'week': w, 'y': float(w % 2),
                          'p': .5, 'cluster': f'{y}_{w}'} for y in (2021, 2022, 2023) for w in range(1, 9)])
    grid = {'production': base.copy(), **{name: base.copy() for name in v.GROUPS}}
    for name in ('drop_offense_box_rates', 'drop_unit_absences'):
        grid[name]['p'] = np.where(base.y == 1., .8, .2)
    return grid


def test_pruning_uses_only_earlier_years_and_chooses_simplest_eligible_group():
    grid = pruning_fixture()
    selected, audit, _ = v.select_group(grid, 2023)
    assert selected == 'drop_offense_box_rates' and audit['selection_max_season'] == 2022
    for frame in grid.values(): frame.loc[frame.season == 2023, 'p'] = .99999
    assert v.select_group(grid, 2023)[0] == selected
    assert v.select_group(grid, 2022)[0] == 'production'   # only one completed OOF season
    for name in ('drop_offense_box_rates', 'drop_unit_absences'):
        grid[name]['p'] = np.where(grid[name].y == 1., .1, .9)
    assert v.select_group(grid, 2023)[0] == 'production'   # no earlier-season benefit


def test_group_drop_refits_without_removed_inputs():
    train, board = fixture()
    for frame in (train, board):
        frame['home_moneyline'] = -120.; frame['away_moneyline'] = 100.
        frame['q'] = v.m.market_ml_wp(frame)
    group = 'drop_lead_deficit_peaks'
    a, audit = v.weekly(train, board, group)
    changed = train.assign(**{c: 1e9 for c in v.GROUPS[group]})
    b, _ = v.weekly(changed, board.assign(**{c: -1e9 for c in v.GROUPS[group]}), group)
    np.testing.assert_array_equal(a.p, b.p)
    assert audit[v.GROUPS[group]].eq(0.).all().all()
    assert audit.training_max_season.max() == 2022


def test_frozen_sources_cannot_be_silently_reused_after_change(tmp_path, monkeypatch):
    import json
    (tmp_path/'manifest.json').write_text(json.dumps({'sources': {'nfl_model.py': 'wrong'}, 'frozen': {}}))
    monkeypatch.setattr(vi, 'INPUTS', tmp_path)
    with pytest.raises(ValueError, match='hash changed'):
        vi.load()


def test_groups_and_shrinkage_scope_are_fixed():
    assert len(vi.MAIN) == 16 and len(v.GROUPS) == 8
    assert not any('avail' in n or n.startswith('pass_') or n == 'site' for n in vi.MAIN)
    assert set().union(*map(set, v.GROUPS.values())) == set(v.fi.FEATURES)
    with pytest.raises(ValueError, match='protected'):
        v.run(v.ROOT/'data/invalid')


def test_compressed_export_is_complete_and_deterministic(tmp_path):
    import gzip
    frame = pd.DataFrame({'game_id': ['a', 'b'], 'value': [.2, .3]})
    path = tmp_path/'audit.csv.gz'
    v.write_compressed(frame, path)
    first = path.read_bytes()
    assert gzip.decompress(first).decode().startswith('game_id,value\n')
    pd.testing.assert_frame_equal(pd.read_csv(path), frame)
    v.write_compressed(frame, path)
    assert first == path.read_bytes() and not path.with_name(path.name+'.tmp').exists()


def test_calibration_is_stable_to_platform_level_probability_noise():
    rng = np.random.default_rng(4)
    p = rng.uniform(.15, .85, 500)
    y = rng.binomial(1, p)
    a = np.array(v.calibration(y, p))
    b = np.array(v.calibration(y, p+1e-12*np.sin(np.arange(len(p)))))
    np.testing.assert_allclose(a, b, rtol=0, atol=1e-9)
