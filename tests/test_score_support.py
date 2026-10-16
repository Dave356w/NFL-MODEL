import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import distribution_ablations as d
import joint_market_residuals as j


def test_joint_support_matches_independent_small_score_oracle():
    mask=d.football_support()
    expected=np.ones_like(mask)
    for h in range(81):
        for a in range(81):
            if h==1:expected[h,a]=a>=6 and a!=7
            if a==1:expected[h,a]=h>=6 and h!=7
    assert np.array_equal(mask,expected)
    assert np.array_equal(mask,mask.T)
    assert (~mask).sum()==13


@pytest.mark.parametrize('pair',[(6,1),(1,6),(8,1),(1,8),(9,1),(1,80),(0,0),(2,0),(0,3)])
def test_preserves_valid_rare_and_ordinary_scores(pair):
    assert d.football_support()[pair]


@pytest.mark.parametrize('pair',[(0,1),(1,0),(1,1),(1,2),(5,1),(7,1),(1,7)])
def test_excludes_unreachable_pairs(pair):
    assert not d.football_support()[pair]


def test_normalization_swap_idempotence_and_log_loss_identity():
    p=j.smooth_joint([24.,21.],[81.,100.,10.]);mask=d.football_support()
    q,a=d.condition_support(p,mask)
    assert q.sum()==pytest.approx(1) and (q[~mask]==0).all()
    assert (q[mask]>0).all()
    assert np.allclose(d.condition_support(p.T,mask)[0],q.T)
    assert np.allclose(d.condition_support(q,mask)[0],q)
    assert a['valid_one_point_mass']>0
    assert np.log(q[24,21]/p[24,21])==pytest.approx(-np.log1p(-a['removed_mass']))
    assert np.log(q[6,1]/p[6,1])==pytest.approx(-np.log1p(-a['removed_mass']))


def test_all_derived_probabilities_are_coherent():
    p=j.smooth_joint([24.,21.],[81.,100.,10.]);q,_=d.condition_support(p,d.football_support())
    m=j.marginals(q)
    assert m['total']@j.TOTAL_SUPPORT==pytest.approx(m['home']@j.SCORE_SUPPORT+m['away']@j.SCORE_SUPPORT)
    assert m['margin']@j.MOV_SUPPORT==pytest.approx(m['home']@j.SCORE_SUPPORT-m['away']@j.SCORE_SUPPORT)
    for support,pmf,line in [(j.MOV_SUPPORT,m['margin'],3),(j.TOTAL_SUPPORT,m['total'],45.5)]:
        assert sum(j.event_probabilities(pmf,support,line))==pytest.approx(1)


def test_zero_supported_mass_and_invalid_masks_fail():
    p=np.zeros((81,81));p[1,1]=1
    with pytest.raises(ValueError,match='No supported mass'):d.condition_support(p,d.football_support())
    p=np.ones((81,81))/81**2
    with pytest.raises(ValueError):d.condition_support(p,np.ones((2,2),bool))
    with pytest.raises(ValueError):d.condition_support(p,np.ones((81,81),float))


def test_no_future_or_observed_scores_used_to_build_mask():
    before=d.football_support();after=d.football_support()
    assert np.array_equal(before,after)
    assert d.football_support(0).tolist()==[[True]]
    with pytest.raises(ValueError):d.football_support(-1)
