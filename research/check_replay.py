"""Run a replay and compare every committed output, allowing numerical noise."""
import gzip
import hashlib
import io
import json
import datetime as dt
import os
import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path
import re
import subprocess
import sys
import numpy as np
import pandas as pd
TOLERANCE=1e-8
NUMBER=re.compile(r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?')
REPLAY_AUDIT='_replay_validation.json'
ROOT=Path(__file__).resolve().parents[1]


@contextmanager
def archived_data(output):
    """Export data from the commit that wrote the report, leaving today's ledger untouched."""
    relative=(Path(output).resolve()/'results.json').relative_to(ROOT)
    shallow=subprocess.check_output(['git','rev-parse','--is-shallow-repository'],cwd=ROOT,text=True).strip()
    if shallow=='true': raise ValueError('Frozen report replay requires checkout fetch-depth: 0')
    ref=subprocess.check_output(['git','log','-1','--format=%H','--',str(relative)],cwd=ROOT,text=True).strip()
    if not re.fullmatch(r'[0-9a-f]{40}',ref): raise ValueError('Cannot identify the report input commit')
    archive=subprocess.check_output(['git','archive','--format=tar',ref,'data'],cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix='nfl-frozen-replay-') as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as src:
            src.extractall(tmp,filter='data')
        yield Path(tmp)/'data',ref,hashlib.sha256(archive).hexdigest()


def replay_metadata(name,old,new,changes):
    """Separate verified runner identity from experimental results, without editing origin files.

    Only current model revision/signature labels and the hashes of model/grading source may
    change. Dataset hashes, recipes, outcomes, reports and all other fields remain strict.
    Every accepted identity change is preserved in a separate replay audit artifact.
    """
    if name not in ('results.json','provenance.json'): return new
    a,b=json.loads(old),json.loads(new)
    if not isinstance(a,dict) or not isinstance(b,dict): return new
    permitted={}
    if name=='provenance.json':
        for key in ('nfl_model.py','grade_ledger.py'):
            permitted[key]=hashlib.sha256((ROOT/key).read_bytes()).hexdigest()
    else:
        sys.path.insert(0,str(ROOT)) if str(ROOT) not in sys.path else None
        import nfl_model as m
        permitted={'revision':m.REVISION,'model_revision_at_run':m.REVISION,'config_signature':m.config_signature()[0]}
    for key,current in permitted.items():
        if key not in a or key not in b or a[key]==b[key]: continue
        if b[key]!=current: raise ValueError(f'{name}.{key}: replay identity is not the executing source')
        if key in ('revision','model_revision_at_run'):
            if not isinstance(a[key],str) or not re.fullmatch(r'boxscore-composite-v\d+\.\d+',a[key]):
                raise ValueError(f'{name}.{key}: not a production identity field')
        elif not isinstance(a[key],str) or not re.fullmatch(r'[0-9a-f]{64}',a[key]):
            raise ValueError(f'{name}.{key}: invalid original source fingerprint')
        changes.append({'file':name,'field':key,'original':a[key],'replayed':b[key]})
        b[key]=a[key]
    return json.dumps(b).encode()


def compare_json(a,b,path='value'):
    if isinstance(a,bool) or isinstance(b,bool):
        if type(a)!=type(b) or a!=b:raise ValueError(f'{path}: boolean changed')
    elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
        if isinstance(a,int) and isinstance(b,int):equal=a==b
        else:equal=np.isclose(a,b,rtol=0,atol=TOLERANCE,equal_nan=True)
        if not equal:raise ValueError(f'{path}: numeric value changed: {a} → {b}')
    elif isinstance(a,dict) and isinstance(b,dict):
        if a.keys()!=b.keys():raise ValueError(f'{path}: keys changed')
        for k in a:compare_json(a[k],b[k],path+'.'+k)
    elif isinstance(a,list) and isinstance(b,list):
        if len(a)!=len(b):raise ValueError(f'{path}: length changed')
        for i,(x,y) in enumerate(zip(a,b)):compare_json(x,y,f'{path}[{i}]')
    elif type(a)!=type(b) or a!=b:raise ValueError(f'{path}: value changed')


def compare_file(name,old,new):
    if old==new:return
    if name.endswith('.json'):
        compare_json(json.loads(old),json.loads(new),name)
    elif name.endswith(('.csv','.csv.gz')):
        if name.endswith('.gz'):old,new=gzip.decompress(old),gzip.decompress(new)
        a,b=pd.read_csv(io.BytesIO(old)),pd.read_csv(io.BytesIO(new))
        if not a.columns.equals(b.columns) or a.shape!=b.shape:raise ValueError(f'{name}: CSV schema/row count changed')
        for c in a:
            if not a[c].isna().equals(b[c].isna()):raise ValueError(f'{name}:{c}: missingness changed')
            if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]):
                if not np.allclose(a[c],b[c],rtol=0,atol=TOLERANCE,equal_nan=True):raise ValueError(f'{name}:{c}: numeric values changed')
            elif not a[c].fillna('').equals(b[c].fillna('')):raise ValueError(f'{name}:{c}: values changed')
    elif name.endswith('.md'):
        a,b=old.decode(),new.decode()
        if NUMBER.sub('#',a)!=NUMBER.sub('#',b):raise ValueError(f'{name}: report text changed')
        ax,bx=NUMBER.findall(a),NUMBER.findall(b)
        if len(ax)!=len(bx):raise ValueError(f'{name}: numeric token count changed')
        for x,y in zip(ax,bx):
            if x==y:continue
            if x.lstrip('+-').isdigit() and y.lstrip('+-').isdigit():equal=int(x)==int(y)
            else:equal=np.isclose(float(x),float(y),rtol=0,atol=TOLERANCE)
            if not equal:raise ValueError(f'{name}: report number changed: {x} → {y}')
    else:raise ValueError(f'{name}: bytes changed')


def main(argv=None):
    args=sys.argv[1:] if argv is None else argv
    root=Path(args[0]);command=args[1:]
    freeze=bool(command and command[0]=='--frozen-data-at-report')
    if freeze: command=command[1:]
    if command and command[0]=='--':command=command[1:]
    prior={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file() and p.name!=REPLAY_AUDIT}
    metadata=[]
    audit=dict(status='RUNNING',observed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),command=command,
               files_checked=len(prior),absolute_tolerance=TOLERANCE,identity_changes=metadata,
               checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),original_outputs_restored=False)
    (root/REPLAY_AUDIT).write_text(json.dumps(audit,indent=2)+'\n')
    try:
        if freeze:
            with archived_data(root) as (data,ref,sha):
                audit.update(input_commit=ref,input_archive_sha256=sha)
                subprocess.run(command,check=True,env=dict(os.environ,NFL_RESEARCH_DATA_DIR=str(data)))
        else:
            subprocess.run(command,check=True)
        after={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file() and p.name!=REPLAY_AUDIT}
        if prior.keys()!=after.keys():raise ValueError('Replay output file set changed; regenerate and commit outputs')
        for name,old in prior.items():compare_file(str(name),old,replay_metadata(str(name),old,after[name],metadata))
        # Restore identical committed bytes only after validating every output.
        for name,old in prior.items():(root/name).write_bytes(old)
        audit.update(status='PASS',original_outputs_restored=True)
    except Exception as exc:
        audit.update(status='FAIL',error=str(exc))
        raise
    finally:
        (root/REPLAY_AUDIT).write_text(json.dumps(audit,indent=2)+'\n')
    print(f'{len(prior)} replay files agree within absolute {TOLERANCE:g}; integer/text/schema checks exact.')

if __name__=='__main__':main()
