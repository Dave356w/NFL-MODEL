import json

import pytest

import validate_data_files as v


def rec(gid, gen="2026-10-10T12:00:00+00:00", ko="2026-10-11T17:00:00+00:00", exp="e"):
    return json.dumps({"experiment": exp, "game_id": gid, "generated_utc": gen, "kickoff_utc": ko, "model_wp": .6})


def test_csv_conflict_marker_and_ragged_rows(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("a,b\n1,2\n<<<<<<< HEAD\n")
    with pytest.raises(ValueError, match="conflict"):
        v.validate_csv(p)
    p.write_text("a,b\n1,2,3\n")
    with pytest.raises(ValueError, match="columns"):
        v.validate_csv(p)


def test_ledger_invariants(tmp_path):
    p = tmp_path / "forward_predictions.jsonl"
    p.write_text(rec("g1") + "\n" + rec("g2") + "\n" + rec("g1", exp="other") + "\n")
    assert v.validate_ledger(p) == 3
    p.write_text(rec("g1") + "\n" + rec("g1") + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        v.validate_ledger(p)
    p.write_text(rec("g1", gen="2026-10-11T17:00:00+00:00") + "\n")
    with pytest.raises(ValueError, match="before kickoff"):
        v.validate_ledger(p)


def test_validate_data_dir_recurses(tmp_path):
    (tmp_path / "latest").mkdir()
    (tmp_path / "latest" / "x.csv").write_text("a\n1\n")
    (tmp_path / "forward_predictions.jsonl").write_text(rec("g1") + "\n")
    assert len(v.validate_data_dir(tmp_path)) == 2
