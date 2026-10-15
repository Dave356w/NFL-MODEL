"""research/forward_monitoring.py: verdict rules and their simulated operating characteristics."""
import sys
from pathlib import Path

import numpy as np

import grade_ledger as g

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import forward_monitoring as fm  # noqa: E402

ADOPTED = fm.RULES['three-way, t(G-1) 97.5% (adopted)']


def test_rules_match_the_written_text():
    old = fm.RULES['as written']
    assert fm.verdict(old, .0, .01, 199, 14) == 'none' and fm.verdict(old, -.0001, .01, 200, 14) == 'falsified'
    assert fm.verdict(old, .03, .01, 200, 14) == 'supported' and fm.verdict(old, .001, .01, 200, 14) == 'unresolved'
    assert fm.verdict(ADOPTED, -.0001, .01, 200, 14) == 'unresolved'      # a small loss does not falsify
    assert fm.verdict(ADOPTED, -.03, .01, 200, 14) == 'falsified'
    assert fm.verdict(ADOPTED, .03, .01, 200, 14) == 'supported'


def test_adopted_rule_is_the_one_the_ledger_applies():
    words = {'supported': 'supported', 'falsified': 'falsified', 'unresolved': 'unresolved', 'none': 'no verdict'}
    for est in (-.006, -.002, 0., .001, .003, .0048, .008):
        for se in (.001, .002, .004):
            for n, weeks in ((199, 14), (206, 14), (478, 32), (1294, 86)):
                want = words[fm.verdict(ADOPTED, est, se, n, weeks)]
                assert g.fp_verdict(est, se, n, weeks).startswith(want), (est, se, n, weeks)


def test_week_block_bootstrap_keeps_both_error_rates_near_five_percent():
    blocks = fm.week_blocks()
    assert len(blocks[0]) == 158 and np.isclose(blocks[0].sum(), 0.)        # recentred historical weeks
    cur = fm.simulate(fm.RULES['as written'], .0023, blocks, reps=4000)
    new = fm.simulate(ADOPTED, .0023, blocks, reps=4000)
    assert cur['Jan 2031']['falsified'] > .4 and new['Jan 2031']['falsified'] < .06
    null = fm.simulate(ADOPTED, 0., blocks, reps=4000)
    assert null['Jan 2031']['supported'] < .05                              # false support stays below 5%
    first_draft = fm.simulate(fm.RULES['three-way, z 2.24 (first addendum)'], .0023, blocks, reps=4000)
    assert first_draft['Jan 2031']['falsified'] > new['Jan 2031']['falsified']


def test_gaussian_known_se_reproduces_the_first_draft_table():
    sd = fm.per_game_sd()['sd_effective']
    r = fm.simulate_gaussian(fm.RULES['three-way, z 2.24 (first addendum)'], .0023, sd, reps=4000)
    assert r['Jan 2031']['falsified'] < .05


def test_given_the_week5_rows_falsification_is_out_of_reach():
    w5 = fm.week5_block()
    assert w5[1] == 13 and abs(w5[0] - 1.9049) < 1e-3                       # the ledger's 13 graded rows
    blocks = fm.week_blocks()
    assert w5[0] > blocks[0].max()                                          # beyond every historical week
    null = fm.simulate(ADOPTED, 0., blocks, reps=4000, fixed=w5)
    assert null['Jan 2031']['falsified'] < .02 and null['Jan 2031']['supported'] < .05
    free = fm.simulate(ADOPTED, 0., blocks, reps=4000)
    assert free['Jan 2031']['falsified'] > .15                              # unconditional power to falsify a 0
