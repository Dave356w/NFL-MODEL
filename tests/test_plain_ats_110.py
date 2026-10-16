"""Price-aware observed-cover decisions and correct handicap/push settlement."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import plain_ats_110 as a


def test_break_even_and_no_edge_pass():
    assert a.choose(.5,0,.5)['side']=='pass'
    assert a.choose(11/21,0,10/21)['side']=='pass'
    assert a.choose(.524,0,.476)['side']=='home'
    assert a.choose(.476,0,.524)['side']=='away'


def test_pushes_use_conditional_probability_not_raw_cover_rate():
    result=a.choose(.49,.10,.41)
    assert result['side']=='home'
    assert result['selected_ev']==pytest.approx(.49*10/11-.41)
    assert a.choose(0,1,0)['side']=='pass'


def test_settlement_respects_line_sign_half_points_and_pass():
    assert a.settle('home',3,3)==0
    assert a.settle('away',3,3)==0
    assert a.settle('home',3,2.5)==pytest.approx(10/11)
    assert a.settle('away',3,2.5)==-1
    assert a.settle('home',-2,-3)==pytest.approx(10/11)
    assert a.settle('away',-2,-3)==-1
    assert a.settle('pass',-2,-3)==0


def test_invalid_inputs_fail():
    for values in [(-.1,.1,1),(.5,.1,.5),(float('nan'),0,1)]:
        with pytest.raises(ValueError):a.choose(*values)
    with pytest.raises(ValueError):a.settle('bad',3,3)
