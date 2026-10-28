"""H13 strictly-earlier-week signal, lock cutoff, lock-line grading and verdict gate."""
import numpy as np
import pandas as pd

from research import h13_shadow as h


def hist(weeks=9, margin=10.):
    return pd.DataFrame([dict(game_id=f'2026_{w:02d}_B_A', season=2026, week=w, home_team='A', away_team='B',
                              result=margin, spread_line=0., fixed_band_spread=3.) for w in range(1, weeks + 1)])


def test_signal_uses_strictly_earlier_weeks():
    g = hist()
    assert np.isnan(h.signal(g, 2026, 8, 'A', 'B'))  # only 7 earlier weeks
    assert h.signal(g, 2026, 9, 'A', 'B') == 6.  # capped +3 vs -3
    g.loc[g.week == 9, 'result'] = -40.  # the target week's own result never enters
    assert h.signal(g, 2026, 9, 'A', 'B') == 6.


def test_shadow_side_fades_and_respects_the_threshold():
    assert h.shadow_side(6.) == -1. and h.shadow_side(-2.51) == 1.
    assert h.shadow_side(2.5) == 0. and h.shadow_side(np.nan) == 0.


def lock(week, lock_at, revision=h.REVISION, recovered=False):
    return dict(revision=revision, season=2026, week=week, home='A', away='B', game_id=f'2026_{week:02d}_B_A',
                lock_at_utc=lock_at, market_spread=1.5, fixed_band_spread=3., recovered_after_kickoff=recovered)


def test_forward_rows_apply_cutoff_revision_and_grade_at_the_lock_line():
    g = hist(9)
    rows = h.forward_rows(g, [lock(9, '2026-10-27T23:00:00Z'), lock(9, '2026-11-01T16:00:00Z'),
                              lock(9, '2026-11-01T16:00:00Z', revision='other')])
    assert len(rows) == 1
    r = rows.iloc[0]
    # Home covered every earlier week, so the fade takes the away side and loses here.
    assert r.side == -1. and r.production == 1. and r.margin == 10. - 1.5
    res = h.arms(rows)
    assert res['shadow']['losses'] == 1 and res['favorite']['wins'] == 1 and res['production']['wins'] == 1


def test_pending_lock_is_not_graded():
    rows = h.forward_rows(hist(8), [lock(9, '2026-11-01T16:00:00Z')])
    assert rows.margin.isna().all() and h.arms(rows)['shadow']['bets'] == 0


def rec(bets, cover, roi, se):
    return dict(bets=bets, cover=cover, roi=roi, roi_se=se)


def test_verdict_gate():
    assert h.verdict(rec(299, .6, .2, .05)).startswith('interim')
    assert h.verdict(rec(300, .52, -.01, .05)) == 'falsified'
    assert h.verdict(rec(300, .58, .11, .05)).startswith('supported')
    assert h.verdict(rec(300, .54, .03, .05)) == 'unresolved'
