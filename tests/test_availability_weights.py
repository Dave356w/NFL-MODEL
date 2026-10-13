"""Availability weighting candidates: practice-based Questionable weights and split units."""
import json
import numpy as np
import pandas as pd
import pytest
from research import availability_weights as a

m = a.m
DNP, LIM, FULL = 'Did Not Participate In Practice', 'Limited Participation in Practice', 'Full Participation in Practice'


def test_questionable_weight_follows_final_practice():
    assert a.practice_weight('Questionable', FULL) == .06
    assert a.practice_weight('Questionable', LIM) == .26
    assert a.practice_weight('Questionable', DNP) == .55
    assert a.practice_weight('Questionable', None) == .25 and a.practice_weight('Questionable', '\n') == .25
    assert a.practice_weight('Out', FULL) == 1. and a.practice_weight('Doubtful', None) == 1.
    assert a.practice_weight(None, DNP) == 0. and a.practice_weight(np.nan, None) == 0.  # practice-only rows


def test_practice_injuries_keep_production_rows():
    inj = pd.DataFrame({'season': 2020, 'week': 3, 'team': 'T', 'gsis_id': ['q1', 'q2', 'o1'],
                        'report_status': ['Questionable', 'Questionable', 'Out']})
    detail = pd.DataFrame({'season': 2020, 'week': 3, 'team': 'T', 'gsis_id': ['q1', 'o1'], 'practice_status': [DNP, DNP]})
    out = a.practice_injuries(inj, detail)
    assert len(out) == 3 and list(out.weight) == [.55, .25, 1.] and 'practice_status' not in out


def test_split_units_inside_the_block_only():
    before = m.POS_GROUP, m.OFFENSE_GROUPS, m.DEFENSE_GROUPS, m.AVAIL_FAMILY_COLS[a.FAMILY]
    with a.unit_groups(True):
        assert (m.POS_GROUP['TE'], m.POS_GROUP['FS'], m.POS_GROUP['DB'], m.POS_GROUP['T']) == ('TE', 'S', 'CB', 'OL')
        names = m.feature_names(a.FAMILY)
        assert 'd__avail__WR_out_cs' in names and 'd__avail__S_out_cs' in names and 'd__avail__WRTE_out_cs' not in names
    assert (m.POS_GROUP, m.OFFENSE_GROUPS, m.DEFENSE_GROUPS, m.AVAIL_FAMILY_COLS[a.FAMILY]) == before
    with pytest.raises(RuntimeError):
        with a.unit_groups(True): raise RuntimeError
    assert m.OFFENSE_GROUPS == before[1] and 'd__avail__WRTE_out_cs' in m.feature_names(a.FAMILY)


def team():
    players = [('wr1', 'WR', 60.), ('wr2', 'WR', 40.), ('te', 'TE', 50.), ('cb', 'CB', 60.), ('fs', 'FS', 60.), ('db', 'DB', 30.)]
    off = {'WR', 'TE'}
    snaps = pd.DataFrame([{'season': 2020, 'week': w, 'game_id': f'g{w}', 'team': 'T', 'gsis_id': g, 'position': p,
                           'offense_snaps': s if p in off else 0., 'defense_snaps': 0. if p in off else s}
                          for w in (1, 2) for g, p, s in players])
    rost = pd.DataFrame([{'season': 2020, 'week': 2, 'team': 'T', 'gsis_id': g, 'position': p, 'status': 'ACT'} for g, p, _ in players])
    inj = pd.DataFrame({'season': 2020, 'week': 3, 'team': 'T', 'gsis_id': ['te', 'cb'], 'report_status': ['Questionable', 'Out']})
    detail = pd.DataFrame({'season': 2020, 'week': 3, 'team': 'T', 'gsis_id': ['te'], 'practice_status': [DNP]})
    return pd.DataFrame({'season': [2020], 'week': [3], 'team': ['T']}), snaps, inj, rost, detail


def test_candidates_flow_through_production_availability_table():
    targets, snaps, inj, rost, detail = team()
    ctrl = a.unit_table(targets, snaps, inj, rost).iloc[0]
    assert np.isclose(ctrl.WRTE_out_cs, .25*100/300) and np.isclose(ctrl.DB_out_cs, 120/300)
    prac = a.unit_table(targets, snaps, a.practice_injuries(inj, detail), rost).iloc[0]
    assert np.isclose(prac.WRTE_out_cs, .55*100/300) and np.isclose(prac.DB_out_cs, ctrl.DB_out_cs)
    split = a.unit_table(targets, snaps, inj, rost, split=True).iloc[0]
    assert np.isclose(split.WR_out_cs, 0.) and np.isclose(split.TE_out_cs, .25)
    assert np.isclose(split.CB_out_cs, 120/180) and np.isclose(split.S_out_cs, 0.)
    assert m.OFFENSE_GROUPS == ('OL', 'WRTE', 'RB')  # restored after the split rebuild


def test_differences_are_home_minus_away():
    table = pd.DataFrame({'season': 2020, 'week': 3, 'team': ['H', 'A'], 'OL_out_cs': [.3, .1]}).set_index(['season', 'week', 'team'])
    pack = pd.DataFrame({'season': [2020, 2020], 'week': [3, 3], 'home': ['H', 'X'], 'away': ['A', 'A']})
    d = a.differences(pack, table, ['d__avail__OL_out_cs'])
    assert np.isclose(d.iloc[0, 0], .2) and np.isnan(d.iloc[1, 0])


def test_decision_rule():
    pos = {'ll_gain': 1e-4}
    assert a.verdict([pos, pos], {'ll_gain': 1e-4, 'll_interval': [1e-5, 2e-4]}) == 'supported'
    assert a.verdict([pos, {'ll_gain': -1e-5}], {'ll_gain': 1e-4, 'll_interval': [1e-5, 2e-4]}) == 'unresolved'
    assert a.verdict([pos, pos], {'ll_gain': 1e-4, 'll_interval': [-1e-5, 2e-4]}) == 'unresolved'
    assert a.verdict([pos, pos], {'ll_gain': 0., 'll_interval': [-1e-5, 1e-5]}) == 'falsified'


@pytest.mark.parametrize('target', ['data', 'public', 'data/latest'])
def test_research_cannot_write_production_outputs(target):
    with pytest.raises(ValueError, match='production outputs'):
        a.run(a.ROOT/target)
    with pytest.raises(ValueError, match='production outputs'):
        a.prepare(a.ROOT/target)


def test_committed_results_follow_the_protocol():
    info = json.loads((a.OUT/'results.json').read_text())
    assert info['questionable_practice_weights'] == a.Q_PRACTICE and info['confidence_level'] == a.LEVEL
    for arm in a.ARMS[1:]:
        assert info['verdicts'][arm] == a.verdict([info['bases'][b]['paired'][arm] for b in a.BASES], info['pooled'][arm])
    for b in info['bases'].values():
        if b['pipeline_check']['exact']:
            assert b['control_vs_committed_v116_max_abs'] < 1e-9
