"""Locked R002/R003 research ablations; all production paths remain untouched."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

import joint_market_residuals as j
import tie_hurdle as t

EXPERIMENTS={'R002':'R002_ot_transitions','R003':'R003_score_support'}
BASE=j.ROOT/'research/experiments/R000_reproduction'
R001=j.ROOT/'research/experiments/R001_tie_hurdle'
INCREMENTS=(2,3,6)
GENERATORS=((2,0),(3,0),(6,0),(7,0),(8,0),(6,1),(6,2))


def write_predictions(frame,path):
    """Serialize/validate fully, fsync a temporary file, then atomically publish.

    Added after R003's initial CSV gzip failed EOF validation. No forecast
    arithmetic or design parameter changes; never consume a partial CSV.
    """
    path=Path(path)
    csv=frame.to_csv(index=False).encode()
    buffer=io.BytesIO()
    with gzip.GzipFile(filename=path.stem,mode='wb',fileobj=buffer,mtime=0) as stream:
        stream.write(csv)
    encoded=buffer.getvalue()
    if gzip.decompress(encoded)!=csv:raise AssertionError('Gzip serialization incomplete')
    fd,name=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.part',dir=path.parent)
    tmp=Path(name)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(encoded);stream.flush();os.fsync(stream.fileno())
        if tmp.read_bytes()!=encoded:raise AssertionError('Written gzip bytes differ')
        os.replace(tmp,path)
        if gzip.decompress(path.read_bytes())!=csv:raise AssertionError('Published gzip incomplete')
    finally:
        tmp.unlink(missing_ok=True)
    return dict(rows=len(frame),csv_sha256=hashlib.sha256(csv).hexdigest(),
        gzip_sha256=hashlib.sha256(encoded).hexdigest(),gzip_eof_verified=True,
        method='complete in-memory gzip; fsync; atomic replace; readback validation')


def check_joint(p):
    p=np.asarray(p,float)
    if p.ndim!=2 or p.shape[0]!=p.shape[1] or not np.isfinite(p).all() or (p<0).any() or not np.isclose(p.sum(),1,atol=1e-12,rtol=0):
        raise ValueError('Invalid normalized square joint distribution')
    return p


def ot_transport(raw,rate):
    """Move excess tie mass into a fixed terminal kernel; not an OT simulator."""
    p=check_joint(raw)
    b=t.tie_hurdle(p,rate)
    diag=np.diag(p);old=diag.sum();excess=max(old-rate,0.)
    q=np.tril(p,-1).sum()/(1-old)
    n=len(p); additions=np.zeros_like(p)
    moved=0.;untransportable=0.;truncated=0.
    for s,prob in enumerate(diag):
        amount=excess*prob/old
        ds=[d for d in INCREMENTS if s+d<n]
        if not ds:
            untransportable+=amount
            continue
        if len(ds)<len(INCREMENTS):truncated+=amount
        moved+=amount
        for d in ds:
            additions[s+d,s]+=amount*q/len(ds)
            additions[s,s+d]+=amount*(1-q)/len(ds)
    out=b.copy()
    offdiag=~np.eye(n,dtype=bool)
    out[offdiag]*=(1-rate-moved)/(1-rate)
    out+=additions
    check_joint(out)
    if not np.isclose(np.trace(out),rate,atol=1e-12,rtol=0):raise AssertionError('Tie mass changed')
    if not np.isclose(np.tril(out,-1).sum()/(1-rate),q,atol=1e-12,rtol=0):raise AssertionError('Winner changed')
    return out,dict(raw_tie_mass=float(old),target_tie_rate=float(rate),
        excess_tie_mass=float(excess),transported_mass=float(moved),
        untransportable_mass=float(untransportable),near_cap_renormalized_mass=float(truncated),
        no_excess=bool(excess==0),winner_weight=float(q))


def football_support(cap=j.CAP):
    """Joint additive reachability, including opponent points during a TD try."""
    if not isinstance(cap,int) or cap<0:raise ValueError('Nonnegative integer cap required')
    reachable=np.zeros((cap+1,cap+1),dtype=bool);reachable[0,0]=True
    generators=tuple(dict.fromkeys(GENERATORS+tuple((b,a) for a,b in GENERATORS)))
    # Every generator increases h+a, so this is a topological traversal.
    for total in range(2*cap+1):
        for h in range(max(0,total-cap),min(cap,total)+1):
            a=total-h
            if reachable[h,a]:
                for dh,da in generators:
                    if h+dh<=cap and a+da<=cap:reachable[h+dh,a+da]=True
    return reachable


def condition_support(joint,mask):
    p=check_joint(joint)
    if mask.shape!=p.shape or mask.dtype!=bool:raise ValueError('Invalid support mask')
    mass=float(p[mask].sum())
    if mass<=0:raise ValueError('No supported mass')
    out=np.where(mask,p/mass,0.)
    check_joint(out)
    one=np.zeros_like(mask);one[1,:]=True;one[:,1]=True
    return out,dict(removed_mass=float(p[~mask].sum()),retained_mass=mass,
        valid_one_point_mass=float(out[one].sum()),excluded_cells=int((~mask).sum()))


def forecast_pairs(features,fits):
    """Rebuild only frozen market-A joints from saved, prior-week coefficient fits."""
    valid=np.isfinite(features[['home_score','away_score','spread_line','total_line']]).all(axis=1)
    complete=features[valid]
    for (year,week),test in complete[complete.season>=2017].groupby(['season','week'],sort=True):
        train=complete[j.before(complete,year,week)&(complete.season>=year-5)]
        weight=j.time_weights(train,year)
        means=test[['implied_home','implied_away']].to_numpy()+10*j.ridge_predict(fits[year,week,'mean'],test[list(j.BASE)])
        covs,_=j.stable_covariance(100*j.ridge_predict(fits[year,week,'covariance'],test[list(j.BASE)]))
        rate,audit=t.fit_tie_rate(features,year,week)
        for pos,(_,row) in enumerate(test.iterrows()):
            smooth=j.smooth_joint(means[pos],covs[pos])
            empirical,_=j.empirical_joint(smooth,train,row,weight,())
            yield row,rate,audit,{'smooth':smooth,'empirical':empirical}


def run(experiment,out=None):
    if experiment not in EXPERIMENTS:raise ValueError('Unknown experiment')
    out=Path(out or j.ROOT/'research/experiments'/EXPERIMENTS[experiment]).resolve()
    allowed=(j.ROOT/'research/experiments').resolve()
    if not out.is_relative_to(allowed) or out in [BASE.resolve(),R001.resolve()]:raise ValueError('Protected output')
    if not (out/'PROTOCOL.md').is_file():raise ValueError('Register the protocol before executing')
    out.mkdir(parents=True,exist_ok=True)
    f=pd.read_csv(BASE/'features.csv.gz');fits=t.load_fit_index(BASE/'coefficient_audit.jsonl')
    saved=pd.read_csv(BASE/'predictions.csv.gz').set_index(['arm','game_id'])
    saved_hurdle=pd.read_csv(R001/'predictions.csv.gz').set_index(['arm','game_id'])
    mask=football_support() if experiment=='R003' else None
    infos=['A_market','R001_tie_hurdle','R002_ot_transitions'] if experiment=='R002' else ['A_market','R003_score_support']
    arms=[shape+'__'+info for shape in j.SHAPES for info in infos]
    payload={arm+'__'+target:[] for arm in arms for target in ['home','away','margin','total']}
    records=[];audits=[];ids=[];examples={};max_error=0.;kernel_checks=True
    if mask is not None:
        np.save(out/'support_mask.npy',mask,allow_pickle=False)
        (out/'support_definition.json').write_text(json.dumps(dict(generators=GENERATORS,
            include_swaps=True,cap=j.CAP,excluded_pairs=np.argwhere(~mask).tolist(),
            reachable_cells=int(mask.sum()),interpretation='ordinary scoring additive closure; not a frequency or clock model'),indent=2)+'\n')
    for row,rate,audit,joints in forecast_pairs(f,fits):
        ids.append(row.game_id)
        if mask is not None and not mask[int(row.home_score),int(row.away_score)]:
            raise ValueError('Observed outcome outside fixed support: '+row.game_id)
        for shape,raw in joints.items():
            baseline=shape+'__A_market'
            m,_=j.summarize_joint(raw,row)
            original=saved.loc[baseline,row.game_id]
            error=max(abs(m[k]-original[k]) for k in ['joint_nll','p_home','p_tie','home_mean','away_mean','margin_crps','total_crps'])
            max_error=max(max_error,error)
            if error>1e-10:raise AssertionError('Raw baseline reconstruction failed')
            if experiment=='R002':
                hurdle=t.tie_hurdle(raw,rate)
                hm,_=j.summarize_joint(hurdle,row)
                previous=saved_hurdle.loc[shape+'__R001_tie_hurdle',row.game_id]
                error=max(abs(hm[k]-previous[k]) for k in ['joint_nll','p_home','p_tie','home_mean','total_crps'])
                max_error=max(max_error,error)
                if error>1e-10:raise AssertionError('R001 reconstruction failed')
                candidate,diagnostics=ot_transport(raw,rate)
                variants={'A_market':raw,'R001_tie_hurdle':hurdle,'R002_ot_transitions':candidate}
            else:
                candidate,diagnostics=condition_support(raw,mask)
                variants={'A_market':raw,'R003_score_support':candidate}
            for info,p in variants.items():
                metrics,pmfs=j.summarize_joint(p,row)
                if p[int(row.home_score),int(row.away_score)]<=0:raise ValueError('Zero realized probability: '+row.game_id)
                metadata={k:row[k] for k in ['game_id','season','week','gameday','home_team','away_team',
                    'home_score','away_score','spread_line','total_line','home_moneyline','away_moneyline','q']}
                arm=shape+'__'+info
                records.append(dict(arm=arm,**metadata,**metrics,**t.extra_scores(p,row)))
                for target,values in pmfs.items():payload[arm+'__'+target].append(values.astype(np.float32))
                if row.game_id=='2026_05_SF_SEA':examples[row.game_id+'__'+arm]=p.astype(np.float32)
            audits.append(dict(game_id=row.game_id,shape=shape,**audit,**diagnostics))
    result=j.add_binary_and_bet_scores(pd.DataFrame(records))
    io_audit=write_predictions(result,out/'predictions.csv.gz')
    (out/'io_integrity.json').write_text(json.dumps(io_audit,indent=2)+'\n')
    pd.DataFrame(audits).to_csv(out/'transform_audit.csv',index=False)
    np.savez_compressed(out/'marginal_probabilities.npz',game_ids=np.array(ids),score_support=j.SCORE_SUPPORT,
        margin_support=j.MOV_SUPPORT,total_support=j.TOTAL_SUPPORT,**{k:np.asarray(v) for k,v in payload.items()})
    np.savez_compressed(out/'example_joint_probabilities.npz',**examples)
    provenance=dict(experiment=experiment,registration=json.loads((out/'registration_record.json').read_text()),
        protocol_sha256=j.sha256(out/'PROTOCOL.md'),source_files={p:j.sha256(j.ROOT/p) for p in
            ['research/distribution_ablations.py','research/joint_market_residuals.py','research/tie_hurdle.py','research/RULE_SOURCES.json']},
        input_hashes={p:j.sha256(BASE/p) for p in ['frozen_inputs.csv.gz','features.csv.gz','coefficient_audit.jsonl','predictions.csv.gz']},
        numpy=np.__version__,pandas=pd.__version__,baseline_reconstruction_max_abs_error=max_error,
        historical_quote_timestamps='unknown',fresh_validation=False,
        full_joint_transform_checked_every_game=True,realized_score_positive_probability_every_game=True)
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(json.dumps(dict(experiment=experiment,rows=len(result),baseline_max_error=max_error)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment',choices=list(EXPERIMENTS))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();run(args.experiment,args.output)
