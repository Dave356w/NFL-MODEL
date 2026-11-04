"""notebooks/NFL_C_B_MODEL.ipynb is the Colab copy of nfl_model.py and must not drift."""
import json
from pathlib import Path

import sync_notebook

ROOT = Path(__file__).resolve().parents[1]


def test_notebook_cell_matches_module():
    nb = json.loads((ROOT / "notebooks/NFL_C_B_MODEL.ipynb").read_text())
    assert "".join(nb["cells"][0]["source"]) == sync_notebook.source(ROOT / "nfl_model.py"), \
        "run: python sync_notebook.py"
    assert not nb["cells"][0]["outputs"]


def test_sync_is_idempotent(tmp_path):
    nb = tmp_path / "nb.ipynb"
    nb.write_text((ROOT / "notebooks/NFL_C_B_MODEL.ipynb").read_text())
    assert not sync_notebook.sync(ROOT / "nfl_model.py", nb)


def test_colab_embeds_the_exact_collector_without_running_the_model():
    import sys
    import types
    src=sync_notebook.source(ROOT/'nfl_model.py')
    prelude=src[:-len((ROOT/'nfl_model.py').read_text())]
    compile(src,'Colab','exec')
    scope={}
    original=sys.modules.get('availability_collect')
    try:
        exec(prelude,scope)
        import availability_collect as ac
        assert isinstance(ac,types.ModuleType) and len(ac.TEAMS)==32
        assert ac.POLICY=='official-availability-collection-2026-11-04-v1'
    finally:
        if original is None:sys.modules.pop('availability_collect',None)
        else:sys.modules['availability_collect']=original
