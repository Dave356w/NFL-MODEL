"""research/forward_monitoring.py: verdict rules and their simulated operating characteristics."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'research'))
import forward_monitoring as fm  # noqa: E402


def test_rules_match_the_written_text():
    assert fm.verdict_current(.0, .01, 199) == 'none' and fm.verdict_current(-.0001, .01, 200) == 'falsified'
    assert fm.verdict_current(.03, .01, 200) == 'supported' and fm.verdict_current(.001, .01, 200) == 'unresolved'
    assert fm.verdict_proposed(-.0001, .01, 200, z=2.24) == 'unresolved'     # a small loss does not falsify
    assert fm.verdict_proposed(-.03, .01, 200, z=2.24) == 'falsified'
    assert fm.verdict_proposed(.03, .01, 200, z=2.24) == 'supported'


def test_proposed_rule_cuts_false_falsification_at_the_adopted_gain():
    sd = .084
    cur = fm.simulate(fm.verdict_current, .0023, sd, reps=4000)
    new = fm.simulate(fm.verdict_proposed, .0023, sd, reps=4000, z=2.24)
    assert cur['Jan 2031']['falsified'] > .4 and new['Jan 2031']['falsified'] < .06
    null = fm.simulate(fm.verdict_proposed, 0., sd, reps=4000, z=2.24)
    assert null['Jan 2031']['supported'] < .06                              # false support stays near 5%
