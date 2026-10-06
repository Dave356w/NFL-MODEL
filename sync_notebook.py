#!/usr/bin/env python3
"""Copy nfl_model.py into the single Colab cell of notebooks/NFL_C_B_MODEL.ipynb.

The notebook is the Colab entry point (paste-and-run, Google Drive storage);
nfl_model.py is the source of truth. tests/test_notebook_sync.py fails if the
two drift, so run this after every model edit:

    python sync_notebook.py
"""
import json
import sys
from pathlib import Path

MODEL = Path("nfl_model.py")
NOTEBOOK = Path("notebooks/NFL_C_B_MODEL.ipynb")


def sync(model=MODEL, notebook=NOTEBOOK):
    """Rewrite the notebook cell from the module; return True if it changed."""
    nb = json.loads(Path(notebook).read_text(encoding="utf-8"))
    cell = nb["cells"][0]
    src = Path(model).read_text(encoding="utf-8")
    new = src.splitlines(keepends=True)
    changed = cell["source"] != new or cell.get("outputs") or cell.get("execution_count") is not None
    if changed:
        cell["source"], cell["outputs"], cell["execution_count"] = new, [], None
        Path(notebook).write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return bool(changed)


if __name__ == "__main__":
    print("notebook updated" if sync() else "notebook already in sync")
    sys.exit(0)
