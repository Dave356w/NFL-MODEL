import copy
import numpy as np
import pandas as pd
from research import qb_saved_pick_audit as a


def test_historical_lineup_requires_exact_forecast_and_pre_cutoff_persistence():
    lock=dict(game_id='g',revision='v',generated_utc='2026-10-01T12:00:00Z',
              lock_at_utc='2026-10-01T13:00:00Z',raw_spread=3.,market_spread=2.)
    saved=dict(commit='abc',commit_utc='2026-10-01T12:01:00Z',
               manifest=dict(generated_utc=lock['generated_utc'],revision='v'),
               rows=[dict(game_id='g',model_spread='3',spread_line='2',home_qb_expected='A')])
    assert a.saved_lineup(lock,{},[],[saved])[0]['home_qb_expected']=='A'
    for field,value in [('commit_utc','2026-10-01T13:01:00Z')]:
        bad=copy.deepcopy(saved);bad[field]=value
        assert a.saved_lineup(lock,{},[],[bad])[0] is None
    bad=copy.deepcopy(saved);bad['rows'][0]['spread_line']='2.5'
    assert a.saved_lineup(lock,{},[],[bad])[0] is None
    bad=copy.deepcopy(saved);bad['manifest']['generated_utc']='2026-10-01T12:05:00Z'
    assert a.saved_lineup(lock,{},[],[bad])[0] is None
    assert a.saved_lineup(lock,{},[],[])[0] is None


def test_quality_excludes_same_week_and_future_stats():
    qb=pd.DataFrame([dict(game_id='g1',season=2026,week=1,gsis_id='a',dropbacks=30,net_yards=180.,leader=True),
                     dict(game_id='g1',season=2026,week=1,gsis_id='b',dropbacks=5,net_yards=20.,leader=False)])
    before=a.quality(qb,'a',2026,2)
    future=qb.assign(game_id='g2',week=2,net_yards=99999.)
    assert a.quality(pd.concat([qb,future]),'a',2026,2)==before
    assert np.isclose(before[0],(180+150*4)/(30+150))


def test_ambiguous_names_are_not_forced_to_match_actual_starter():
    idx={'jdaniels':{'jayden','jalon'}}
    assert a.resolve_name('J.Daniels',idx) is None
    assert a.resolve_name('J.Daniels',idx,{'jayden'})=='jayden'
