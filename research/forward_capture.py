"""Research-only immutable-version, first-snapshot capture; no network/deployment.

Each snapshot embeds the joint PMF and unmodified provider quote JSON. Provider
timestamps are declarations; local exclusive writes are not remote notarization.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import numpy as np


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def digest(x):return hashlib.sha256(canonical(x)).hexdigest()


def utc(x):
    d=datetime.fromisoformat(x.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('Timezone required')
    return d.astimezone(timezone.utc)


def exclusive_json(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    # Build/validate all bytes before creating the target; never replace.
    data=canonical(payload)+b'\n'
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        import os
        os.fsync(stream.fileno())


def guard_store(store,root):
    store,root=Path(store).resolve(),Path(root).resolve()
    if store==root or any(store==root/p or (root/p) in store.parents for p in ['data','public']):
        raise ValueError('Protected production/root output')
    return store


def register_model(store,spec,root):
    store=guard_store(store,root)
    required={'model_name','config','source_files','parameter_files','training_input_sha256'}
    if set(spec)!=required or not spec['source_files'] or not spec['parameter_files']:
        raise ValueError('Model spec needs config, source files, parameter files and input hash')
    if not re.fullmatch('[0-9a-f]{64}',spec['training_input_sha256']):raise ValueError('Invalid input hash')
    hashes={}
    root=Path(root).resolve()
    for name in spec['source_files']+spec['parameter_files']:
        p=(root/name).resolve()
        if not p.is_relative_to(root):raise ValueError('File outside code root')
        hashes[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=dict(spec=spec,file_hashes=hashes)
    version=digest(manifest)
    path=Path(store)/'versions'/f'{version}.json'
    exclusive_json(path,manifest)
    return version


def capture(store,version,request,joint,root,*,_now=None):
    store=guard_store(store,root)
    if not re.fullmatch('[0-9a-f]{64}',version):raise ValueError('Invalid version ID')
    manifest=json.loads((Path(store)/'versions'/f'{version}.json').read_text())
    if digest(manifest)!=version:raise ValueError('Model manifest changed')
    root=Path(root).resolve()
    for name,expected in manifest['file_hashes'].items():
        p=(root/name).resolve()
        if not p.is_relative_to(root) or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise ValueError('Model source or parameters changed after registration')
    now=_now or datetime.now(timezone.utc)
    if now.tzinfo is None:raise ValueError('Timezone required')
    gid=request['game_id']
    if not re.fullmatch('[A-Za-z0-9_-]+',gid):raise ValueError('Unsafe game ID')
    kickoff=utc(request['kickoff_utc'])
    # The locked forward protocol captures first eligible snapshot T-60 +/-5 min.
    if not 55*60 <= (kickoff-now).total_seconds() <= 65*60:
        raise ValueError('Outside locked 55-65 minute pregame window')
    if tuple(request['max_training_season_week'])>=tuple(request['forecast_season_week']):
        raise ValueError('Training must exclude the entire forecast week')
    cutoff=utc(request['week_data_cutoff_utc'])
    if not utc(request['training_available_through_utc'])<=cutoff<=now:
        raise ValueError('Training availability/cutoff order invalid')
    quote=request['quote']
    if not quote['source'] or not quote['book'] or quote['game_id']!=gid:
        raise ValueError('Quote identity/source missing or mismatched')
    if utc(quote['kickoff_utc'])!=kickoff:raise ValueError('Quote kickoff mismatch')
    event=utc(quote['provider_event_utc']);received=utc(quote['received_utc'])
    if not event<=received<=now or (now-event).total_seconds()>300:
        raise ValueError('Quote stale, future dated, or receipt order invalid')
    for name in ['spread_line','total_line']:
        if not np.isfinite(quote[name]) or quote[name]!=request['forecast_market_inputs'][name]:
            raise ValueError('Forecast and quote inputs mismatch')
    for name in ['home_moneyline','away_moneyline']:
        if not np.isfinite(quote[name]) or abs(quote[name])<100:raise ValueError('Invalid American odds')
    p=np.asarray(joint,float)
    if p.shape!=(81,81) or not np.isfinite(p).all() or (p<0).any() or not np.isclose(p.sum(),1,atol=1e-10,rtol=0):
        raise ValueError('A normalized joint 0..80 PMF is required')
    record=dict(schema='nfl-research-forward-v1',model_version=version,
        generated_utc=now.astimezone(timezone.utc).isoformat(),request=request,
        provider_payload_sha256=digest(quote),joint=p.tolist(),
        timestamp_verification='provider-declared event time; local receipt; not independently authenticated')
    record['record_sha256']=digest(record)
    target=Path(store)/'snapshots'/version/f'{gid}.json'
    exclusive_json(target,record)
    return target


def verify_store(store):
    versions={}
    for path in (Path(store)/'versions').glob('*.json'):
        m=json.loads(path.read_text())
        if digest(m)!=path.stem:raise ValueError('Version hash mismatch')
        versions[path.stem]=m
    count=0
    for path in (Path(store)/'snapshots').glob('*/*.json'):
        row=json.loads(path.read_text());expected=row.pop('record_sha256')
        if digest(row)!=expected:raise ValueError('Snapshot hash mismatch')
        if row['model_version'] not in versions or path.parent.name!=row['model_version']:
            raise ValueError('Snapshot version mismatch')
        if path.stem!=row['request']['game_id']:raise ValueError('Snapshot game mismatch')
        if digest(row['request']['quote'])!=row['provider_payload_sha256']:raise ValueError('Provider payload changed')
        count+=1
    return dict(model_versions=len(versions),snapshots=count,
        evidence='Local hashes detect modifications, not deletion or authorized recomputation; external retention required.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store',type=Path,required=True)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    sub=parser.add_subparsers(dest='action',required=True)
    reg=sub.add_parser('register');reg.add_argument('spec',type=Path)
    cap=sub.add_parser('capture');cap.add_argument('version');cap.add_argument('request',type=Path);cap.add_argument('joint_npz',type=Path)
    sub.add_parser('verify')
    args=parser.parse_args()
    if args.action=='register':print(register_model(args.store,json.loads(args.spec.read_text()),args.root))
    elif args.action=='capture':print(capture(args.store,args.version,json.loads(args.request.read_text()),np.load(args.joint_npz,allow_pickle=False)['joint'],args.root))
    else:print(json.dumps(verify_store(args.store),indent=2))
