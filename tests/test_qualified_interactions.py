"""Research invariants: no future reference values, shared-product identity."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd

spec=importlib.util.spec_from_file_location('qualified',Path(__file__).resolve().parents[1]/'research/qualified_interactions.py')
q=importlib.util.module_from_spec(spec); spec.loader.exec_module(q)

def fixture():
    f=pd.DataFrame({'season':[2020,2020,2021,2021,2021], 'week':[1,2,1,2,3]})
    for n,(side,role) in enumerate([('home','for'),('away','allowed'),('away','for'),('home','allowed')]):
        f[f'{side}__{role}__rates_core__{q.STAT}']=[5+n*.2,6+n*.3,5.5+n*.4,7-n*.1,6.5+n*.1]
    return f

def test_future_rows_do_not_change_descriptors(tmp_path):
    q.OUT=tmp_path
    f=fixture(); a=q.descriptors(f)
    altered=f.copy(); altered.loc[4,altered.columns[2:]]=1000
    b=q.descriptors(altered)
    assert np.allclose(a.iloc[:4],b.iloc[:4],equal_nan=True)
    audit=pd.read_csv(tmp_path/'reference_audit.csv')
    assert ((audit.max_reference_season<audit.season)|((audit.max_reference_season==audit.season)&(audit.max_reference_week<audit.week))).all()

def test_swapping_teams_reverses_every_interaction(tmp_path):
    q.OUT=tmp_path
    f=fixture(); a=q.descriptors(f)
    swapped=f.copy()
    for role in ('for','allowed'):
        h=f'home__{role}__rates_core__{q.STAT}'; aw=f'away__{role}__rates_core__{q.STAT}'
        swapped[h]=f[aw]; swapped[aw]=f[h]
    b=q.descriptors(swapped)
    cols=['product','q_pp','q_pn','q_np','q_nn','e_pp','e_pn','e_np','e_nn']
    assert np.allclose(a[cols],-b[cols],equal_nan=True)

def test_four_contexts_reconstruct_product(tmp_path):
    q.OUT=tmp_path
    a=q.descriptors(fixture())
    assert np.allclose(a['product'],a.q_pp-a.q_pn-a.q_np+a.q_nn,equal_nan=True)
