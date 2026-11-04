import sys
import json
import hashlib
import subprocess
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


def test_replay_source_identity_is_audited_but_numeric_checks_stay_strict():
    import nfl_model as m
    before={'revision':'boxscore-composite-v1.19','config_signature':'0'*64,'games':815,'log_loss':.61}
    after=dict(before,revision=m.REVISION,config_signature=m.config_signature()[0])
    changes=[]
    normalized=c.replay_metadata('results.json',json.dumps(before).encode(),json.dumps(after).encode(),changes)
    c.compare_file('results.json',json.dumps(before).encode(),normalized)
    assert {r['field'] for r in changes}=={'revision','config_signature'}
    after['games']=816
    with pytest.raises(ValueError,match='numeric value changed'):
        c.compare_file('results.json',json.dumps(before).encode(),c.replay_metadata(
            'results.json',json.dumps(before).encode(),json.dumps(after).encode(),[]))


def test_only_real_current_source_hash_can_change_and_input_hashes_remain_strict():
    sha=hashlib.sha256((c.ROOT/'nfl_model.py').read_bytes()).hexdigest()
    before={'nfl_model.py':'0'*64,'data.csv':'1'*64}
    after=dict(before,**{'nfl_model.py':sha})
    changes=[]
    c.compare_file('provenance.json',json.dumps(before).encode(),c.replay_metadata(
        'provenance.json',json.dumps(before).encode(),json.dumps(after).encode(),changes))
    assert changes[0]['original']=='0'*64 and changes[0]['replayed']==sha
    after['data.csv']='2'*64
    with pytest.raises(ValueError,match='value changed'):
        c.compare_file('provenance.json',json.dumps(before).encode(),c.replay_metadata(
            'provenance.json',json.dumps(before).encode(),json.dumps(after).encode(),[]))
    after['nfl_model.py']='3'*64
    with pytest.raises(ValueError,match='not the executing source'):
        c.replay_metadata('provenance.json',json.dumps(before).encode(),json.dumps(after).encode(),[])


def test_main_preserves_original_bytes_and_never_leaves_a_stale_pass_audit(tmp_path):
    import nfl_model as m
    path=tmp_path/'results.json'
    original=json.dumps({'model_revision_at_run':'boxscore-composite-v1.19','games':815}).encode()
    path.write_bytes(original)
    replay=json.dumps({'model_revision_at_run':m.REVISION,'games':815})
    command=[str(tmp_path),'--',sys.executable,'-c',
             f'from pathlib import Path; Path({str(path)!r}).write_text({replay!r})']
    c.main(command)
    assert path.read_bytes()==original
    audit=json.loads((tmp_path/c.REPLAY_AUDIT).read_text())
    assert audit['status']=='PASS' and audit['original_outputs_restored']
    assert audit['identity_changes'][0]['replayed']==m.REVISION
    # A second run must not compare the audit to itself, and a failing run must replace PASS.
    c.main(command)
    command[-1]=command[-1].replace('815','816')
    with pytest.raises(ValueError,match='numeric value changed'): c.main(command)
    assert json.loads((tmp_path/c.REPLAY_AUDIT).read_text())['status']=='FAIL'


def test_archived_data_uses_report_commit_without_changing_current_ledger(tmp_path,monkeypatch):
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=tmp_path,text=True).strip()
    git('init','-q')
    git('config','user.name','Replay test')
    git('config','user.email','replay@example.test')
    (tmp_path/'data').mkdir(); (tmp_path/'data/ledger.txt').write_text('28 games\n')
    output=tmp_path/'research/results';output.mkdir(parents=True)
    (output/'results.json').write_text('{"games":28}')
    git('add','.');git('commit','-qm','recorded report')
    recorded=git('rev-parse','HEAD')
    (tmp_path/'data/ledger.txt').write_text('42 games\n')
    git('commit','-qam','more games')
    monkeypatch.setattr(c,'ROOT',tmp_path)
    with c.archived_data(output) as (data,ref,sha):
        assert (data/'ledger.txt').read_text()=='28 games\n'
        assert ref==recorded and len(sha)==64
    assert (tmp_path/'data/ledger.txt').read_text()=='42 games\n'
    assert git('status','--porcelain')==''
