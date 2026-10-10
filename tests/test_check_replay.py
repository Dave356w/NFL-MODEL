import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'research'))
import check_replay as c


def test_float_noise_accepted_in_csv_json_and_report():
    c.compare_file('x.csv',b'game,p\na,0.6\n',b'game,p\na,0.60000000001\n')
    c.compare_file('x.json',b'{"p":0.6,"n":1}',b'{"p":0.60000000001,"n":1}')
    c.compare_file('x.md',b'Error: 1.03e-10. Games 816.',b'Error: 1.94e-10. Games 816.')


def test_substantive_stale_output_rejected():
    with pytest.raises(ValueError):c.compare_file('x.csv',b'game,p\na,0.6\n',b'game,p\na,0.61\n')
    with pytest.raises(ValueError):c.compare_file('x.json',b'{"n":1}',b'{"n":2}')
    with pytest.raises(ValueError):c.compare_file('x.md',b'Error: 1e-10. Games 816.',b'Error: 1e-10. Games 817.')


def test_row_identity_missingness_and_schema_rejected():
    for altered in (b'game,p\nb,0.6\n',b'game,p\na,\n',b'game,p,q\na,0.6,0.5\n'):
        with pytest.raises(ValueError):c.compare_file('x.csv',b'game,p\na,0.6\n',altered)
