"""notebooks/NFL_C_B_MODEL.ipynb is the Colab copy of nfl_model.py and must not drift."""
import json
from pathlib import Path

import sync_notebook

ROOT = Path(__file__).resolve().parents[1]


def test_notebook_cell_matches_module():
    nb = json.loads((ROOT / "notebooks/NFL_C_B_MODEL.ipynb").read_text())
    assert "".join(nb["cells"][0]["source"]) == (ROOT / "nfl_model.py").read_text(), \
        "run: python sync_notebook.py"
    assert not nb["cells"][0]["outputs"]


def test_sync_is_idempotent(tmp_path):
    nb = tmp_path / "nb.ipynb"
    nb.write_text((ROOT / "notebooks/NFL_C_B_MODEL.ipynb").read_text())
    assert not sync_notebook.sync(ROOT / "nfl_model.py", nb)
