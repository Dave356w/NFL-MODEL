"""Run a replay and compare every committed output, allowing numerical noise."""
import gzip
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import numpy as np
import pandas as pd
TOLERANCE=1e-8
NUMBER=re.compile(r'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?')


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


def main():
    root=Path(sys.argv[1]);command=sys.argv[2:]
    if command and command[0]=='--':command=command[1:]
    prior={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    subprocess.run(command,check=True)
    after={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
    if prior.keys()!=after.keys():raise ValueError('Replay output file set changed; regenerate and commit outputs')
    for name,old in prior.items():compare_file(str(name),old,after[name])
    # Restore identical committed bytes after validating platform-level differences.
    for name,old in prior.items():(root/name).write_bytes(old)
    print(f'{len(prior)} replay files agree within absolute {TOLERANCE:g}; integer/text/schema checks exact.')

if __name__=='__main__':main()
