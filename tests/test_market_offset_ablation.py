import sys
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import context_shrinkage as s
import market_offset_ablation as a
from test_context_shrinkage import fixture


def test_no_offset_predictions_and_fit_are_invariant_to_prices():
    f=fixture();f['q']=np.linspace(.2,.8,len(f))
    no=s.fit(f,2023,1,market_offset=False)
    assert no['market_offset'] is False
    changed=f.copy();changed['q']=.9
    assert np.allclose(s.predict(f,no),s.predict(changed,no),atol=0,rtol=0)
    refit=s.fit(changed,2023,1,market_offset=False)
    assert np.allclose(no['beta'],refit['beta'],atol=0,rtol=0)
    yes=s.fit(f,2023,1)
    assert not np.allclose(s.predict(f,yes),s.predict(changed,yes))
    assert no['names']==yes['names'] and no['scale']==yes['scale']
    assert no['training_games']==yes['training_games']
    assert no['penalty_multiplier']==yes['penalty_multiplier']


def test_no_offset_still_rejects_future_training():
    with pytest.raises(ValueError,match='current/future'):s.fit(fixture(),2022,11,market_offset=False)


def test_ablation_cannot_write_production():
    with pytest.raises(ValueError,match='production outputs'):a.run(s.ROOT/'data'/'ablation')
