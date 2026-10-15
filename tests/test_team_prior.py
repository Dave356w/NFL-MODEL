"""Test 45 (research/TEAM_PRIOR.md): the alternative-prior builders reproduce production and never look ahead."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'/'team_prior_study'))
import build_profiles as bp  # noqa: E402
import retention_build as rb  # noqa: E402

VARIANTS = bp.VARIANTS
YEAR = 2014


@pytest.fixture(scope='module')
def small():
    """2013 history plus 2014 weeks 1-4."""
    sched = bp.schedule_frame(pd.read_csv(bp.SCHED))
    sched = sched[(sched.season == 2013) | ((sched.season == YEAR) & (sched.week <= 4))]
    box = pd.read_csv(bp.BOXES)
    box = box[box.game_id.isin(sched.game_id)]
    tg, _, _ = bp.team_games(bp.GAMES)
    return box, sched, tg


def build(box, sched, tg, check=True):
    return bp.build(box, sched, tg, bp.pregame_lookups(tg), years={YEAR}, check_production=check)


def test_league_variant_reproduces_production_profiles(small):
    box, sched, tg = small
    prof, _, _, maxdiff = build(box, sched, tg)
    assert maxdiff <= 1e-12                      # metric_profile, every team-week
    mine = bp.game_frame(prof, sched, 'league', years={YEAR}).set_index('game_id')
    ref = bp.m.lagged_features(box, sched, bp.HALF, profile_families=['rates_core']).set_index('game_id')
    cols = [c for c in bp.RATE_FEATURES+list(bp.m.PEAK_FEATURES)]
    j = mine[cols].join(ref[cols], rsuffix='_p', how='inner')
    assert len(j) == len(mine) > 0
    assert np.allclose(j[cols].to_numpy(float), j[[c+'_p' for c in cols]].to_numpy(float), rtol=0, atol=1e-12, equal_nan=True)


def test_variants_change_only_the_target_and_none_drops_it(small):
    box, sched, tg = small
    prof, _, _, _ = build(box, sched, tg, check=False)
    key = next(k for k in prof if k[1] == 4)
    out = prof[key]
    col = 'for__rates_core__net_pass_yards_per_pass_play'
    assert len({round(out[v][col], 12) for v in VARIANTS}) > 1   # targets differ, so profiles differ
    assert out['league'][col] == out['league_level'][col]        # rates share the league target
    assert out['none']['target_source'] == 'none' and out['league']['target_source'] == 'league'


def test_profiles_ignore_same_week_and_later_games_coaches_and_starters(small):
    box, sched, tg = small
    base, _, _, _ = build(box, sched, tg, check=False)
    # Week-3 stats and every later game's coach and starter change. A game's own head coach is public
    # pregame and keys the coach/continuity targets, so coaches are shocked only from week 4.
    stats = (box.season == YEAR) & (box.week >= 3)
    ident = (tg.season == YEAR) & (tg.week >= 4)
    box2 = box.copy(); box2.loc[stats, 'penalty_yards'] = box2.loc[stats, 'penalty_yards']*3+50
    tg2 = tg.copy(); tg2.loc[ident, 'coach'] = 'Someone Else'; tg2.loc[ident, 'qb_id'] = 'NOBODY'
    shocked, _, _, _ = build(box2, sched, tg2, check=False)
    cols = ['for__rates_core__penalty_yards_per_game', 'for__rates_core__net_pass_yards_per_pass_play']
    for key, out in base.items():
        if key[1] > 3: continue
        for v in VARIANTS:
            for c in cols:
                assert np.isclose(out[v][c], shocked[key][v][c], equal_nan=True), (key, v, c)
            assert out[v]['target_source'] == shocked[key][v]['target_source'], (key, v)
    col = cols[0]
    assert any(not np.isclose(out['league'][col], shocked[k]['league'][col]) for k, out in base.items() if k[1] == 4)


def test_continuity_target_requires_same_coach_and_same_recent_starter(small):
    box, sched, tg = small
    prof, info, _, _ = build(box, sched, tg, check=False)
    for key, out in prof.items():
        gate = info[key]['coach_change'] is False and info[key]['qb_change'] is False and info[key]['prior_season_window_games'] > 0
        src = out['continuity']['target_source']
        assert (src == 'team_prior') == gate, key


def test_retention_multipliers_reduce_to_production_and_compound_by_boundary():
    assert rb.season_multipliers(2020, {2020: .5, 2019: .5, 2018: .5}) == {2020: 1., 2019: .5, 2018: .25, 2017: .125}
    r = rb.boundary_factors({2020: True, 2019: False, 2018: None}, .75, .25)
    assert r == {2020: .75, 2019: .25, 2018: rb.P0}               # unknown continuity keeps production's 0.5
    assert rb.season_multipliers(2020, r) == {2020: 1., 2019: .75, 2018: .1875, 2017: .09375}
