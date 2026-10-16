import gzip
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import distribution_ablations as d


def test_complete_multimegabyte_csv_roundtrip_and_repeated_byte_identity(tmp_path):
    rng=np.random.default_rng(73)
    frame=pd.DataFrame(rng.normal(size=(12000,24)))
    path=tmp_path/'predictions.csv.gz'
    first=d.write_predictions(frame,path);raw=path.read_bytes()
    assert first['rows']==12000 and first['gzip_eof_verified']
    assert len(gzip.decompress(raw))>5_000_000
    restored=pd.read_csv(path)
    assert restored.shape==frame.shape
    assert np.allclose(restored.to_numpy(),frame.to_numpy(),atol=1e-14)
    assert d.write_predictions(frame,path)==first
    assert path.read_bytes()==raw


def test_failed_publish_keeps_existing_file_and_removes_temporary(tmp_path,monkeypatch):
    path=tmp_path/'predictions.csv.gz';path.write_bytes(b'previous intact file')
    def fail(*args):raise OSError('synthetic atomic publish failure')
    monkeypatch.setattr(d.os,'replace',fail)
    with pytest.raises(OSError,match='synthetic'):d.write_predictions(pd.DataFrame({'x':[1]}),path)
    assert path.read_bytes()==b'previous intact file'
    assert not list(tmp_path.glob('*.part'))
