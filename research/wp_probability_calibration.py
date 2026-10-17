"""Reproduce PROTOCOL.md without network access. No production mutations."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import shutil
import sys
import numpy as np
import pandas as pd
import scipy
from scipy.special import expit, logit

CUTS=np.array([.55,.60,.65,.70,.75,.80])
LABELS=['50-55','55-60','60-65','65-70','70-75','75-80','80+']
PARENTS=['v116','v118']
CANDIDATES=[p+'_'+m for p in PARENTS for m in ['bands','isotonic']]
METHODS=['market','v116','v118']+CANDIDATES
SEED=20261017
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/wp_probability_calibration_results'
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
import nfl_model as model


class IsotonicRegression:
    """Weighted pool-adjacent-violators calibration without a runtime dependency.

    Equal forecast values are pooled first. Interior points on flat fitted
    segments are redundant; their endpoints retain linear interpolation.
    This reproduces the independently checked scikit-learn calibration maps.
    """
    def __init__(self, increasing=True, y_min=.005, y_max=.995, out_of_bounds='clip'):
        if not increasing or out_of_bounds != 'clip':
            raise ValueError('Only increasing, clipped calibration is supported')
        self.y_min, self.y_max = y_min, y_max

    def fit(self, x, y, sample_weight):
        x, y, w = (np.asarray(v, float) for v in (x, y, sample_weight))
        if not len(x) or not np.isfinite(np.r_[x,y,w]).all() or (w <= 0).any():
            raise ValueError('Finite observations with positive weights required')
        order = np.argsort(x, kind='stable'); x,y,w=x[order],y[order],w[order]
        unique, starts = np.unique(x, return_index=True)
        weights=np.add.reduceat(w,starts); values=np.add.reduceat(w*y,starts)/weights
        blocks=[]
        for k,(v,weight) in enumerate(zip(values,weights)):
            blocks.append([k,k+1,float(weight),float(weight*v)])
            while len(blocks)>1 and blocks[-2][3]/blocks[-2][2] > blocks[-1][3]/blocks[-1][2]:
                last=blocks.pop();prev=blocks[-1]
                prev[1]=last[1];prev[2]+=last[2];prev[3]+=last[3]
        fitted=np.empty(len(unique))
        for start,end,weight,total in blocks:fitted[start:end]=total/weight
        fitted=np.clip(fitted,self.y_min,self.y_max)
        keep=(np.r_[True,(fitted[1:-1]!=fitted[:-2])|(fitted[1:-1]!=fitted[2:]),True]
              if len(unique)>1 else np.array([True]))
        self.X_thresholds_,self.y_thresholds_=unique[keep],fitted[keep]
        return self

    def predict(self, x):
        return np.interp(np.asarray(x,float),self.X_thresholds_,self.y_thresholds_)

def forward(p,q):
    p,q=np.asarray(p,float),np.asarray(q,float)
    lp,lq=logit(p),logit(q)
    bullish=((lq>0)&(lp>lq))|((lq<0)&(lp<lq))
    return np.where(bullish,expit(lq+.2*(lp-lq)),p)

def invert(p,q):
    p,q=np.asarray(p,float),np.asarray(q,float)
    lp,lq=logit(p),logit(q)
    bullish=((lq>0)&(lp>lq))|((lq<0)&(lp<lq))
    return np.where(bullish,expit(lq+(lp-lq)/.2),p)

def get_data(path):
    d=pd.read_csv(path)
    assert not d.game_id.duplicated().any()
    assert d.groupby('season').week.max().loc[2026]<=5
    assert np.allclose(d.market_wp,d.market_ml_wp,atol=1e-12)
    d=d[d['home won'].isin([0.,1.])].copy().reset_index(drop=True)
    d['y']=d['home won']
    d['market']=d.market_wp
    d['v118']=d.model_wp
    d['v116']=invert(d.v118,d.market)
    assert np.allclose(forward(d.v116,d.market),d.v118,atol=1e-12,rtol=0)
    assert np.isfinite(d[METHODS[:3]+['y']]).all().all()
    assert ((d[METHODS[:3]]>0)&(d[METHODS[:3]]<1)).all().all()
    return d

def fit(parent_p,y):
    p,y=np.asarray(parent_p,float),np.asarray(y,float)
    confidence=np.maximum(p,1-p)
    correct=np.where(p>=.5,y,1-y)
    band=np.digitize(confidence,CUTS)
    n=np.bincount(band,minlength=7)
    wins=np.bincount(band,weights=correct,minlength=7)
    rates=(wins+.5)/(n+1)
    iso=IsotonicRegression(increasing=True,y_min=.005,y_max=.995,out_of_bounds='clip')
    iso.fit(np.r_[p,1-p],np.r_[y,1-y],sample_weight=np.full(2*len(p),.5))
    grid=np.linspace(0,1,1001)
    assert np.all(np.diff(iso.predict(grid))>=-1e-12)
    assert np.allclose(iso.predict(grid)+iso.predict(1-grid),1,atol=1e-11)
    return dict(counts=n.tolist(),wins=wins.tolist(),rates=rates.tolist(),iso=iso)

def predict(p,f):
    p=np.asarray(p,float)
    r=np.array(f['rates'])[np.digitize(np.maximum(p,1-p),CUTS)]
    return np.where(p==.5,.5,np.where(p>=.5,r,1-r)),f['iso'].predict(p)

def walk(d):
    frames=[];fits=[];objects={}
    for year in [2023,2024,2025,2026]:
        train=d[d.season<year].copy()
        test=d[d.season==year].copy()
        assert train.season.nunique()>=2 and len(train)>=300
        for parent in PARENTS:
            f=fit(train[parent],train.y)
            b,i=predict(test[parent],f)
            test[parent+'_bands']=b;test[parent+'_isotonic']=i
            objects[(year,parent)]=f
            fits.append(dict(year=year,parent=parent,training_games=len(train),training_max_season=int(train.season.max()),counts=f['counts'],wins=f['wins'],rates=f['rates'],isotonic_x=f['iso'].X_thresholds_.tolist(),isotonic_y=f['iso'].y_thresholds_.tolist()))
        frames.append(test)
    return pd.concat(frames,ignore_index=True),fits,objects

def loss(y,p):
    y,p=np.asarray(y,float),np.clip(np.asarray(p,float),1e-12,1-1e-12)
    return -(y*np.log(p)+(1-y)*np.log1p(-p)),(y-p)**2

def calibration(g,method,cohort):
    p=g[method].to_numpy(); y=g.y.to_numpy()
    confidence=np.maximum(p,1-p);correct=np.where(p>=.5,y,1-y)
    band=np.digitize(confidence,CUTS)
    rows=[]
    for k,label in enumerate(LABELS):
        mask=band==k;n=int(mask.sum())
        rows.append(dict(cohort=cohort,method=method,confidence_band=label,n=n,mean_confidence=float(confidence[mask].mean()) if n else None,win_rate=float(correct[mask].mean()) if n else None))
    return rows

def metrics(g,cohort):
    out={};curves=[]
    for method in METHODS:
        ll,bs=loss(g.y,g[method]);c=calibration(g,method,cohort);curves+=c
        ece=sum(x['n']*abs(x['mean_confidence']-x['win_rate']) for x in c if x['n'])/len(g)
        out[method]=dict(n=len(g),log_loss=float(ll.mean()),brier=float(bs.mean()),confidence_ece=float(ece),mean_confidence=float(np.maximum(g[method],1-g[method]).mean()),accuracy=float(((g[method]>=.5)==g.y).mean()))
        bets=model.flat_bets(g,method)
        baseline=model.flat_bets(g,'market')
        common=bets.units.notna()&baseline.units.notna()
        roi=model.roi_summary(bets);same=model.roi_summary(bets[common]);fav=model.roi_summary(baseline[common])
        out[method].update(ml_bets=roi['bets'],ml_units=roi['units'],ml_roi=roi['roi'],ml_roi_se=roi['roi_se'],
                           ml_null_roi=roi['null_roi'],common_bets=fav['bets'],common_model_roi=same['roi'],
                           common_favorite_roi=fav['roi'],common_model_units=same['units'],common_favorite_units=fav['units'])
    return out,curves

def paired(g):
    blocks=[];season_sizes=[]
    for year,t in g.groupby('season'):
        groups=list(t.groupby('week').groups.values())
        season_sizes.append(len(groups));blocks+=groups
    rng=np.random.default_rng(SEED)
    w=np.zeros((10000,len(blocks)),dtype=np.int16);off=0
    for n in season_sizes:
        samples=rng.integers(0,n,size=(10000,n))
        for k in range(n):w[:,off+k]=(samples==k).sum(axis=1)
        off+=n
    den=w@np.array([len(b) for b in blocks])
    rows=[]
    for candidate in CANDIDATES:
        for ref in ['v118','market',candidate.split('_')[0]]:
            if any(x['candidate']==candidate and x['reference']==ref for x in rows):continue
            for m,index in [('log_loss',0),('brier',1)]:
                gain=pd.Series(loss(g.y,g[ref])[index]-loss(g.y,g[candidate])[index],index=g.index)
                means=(w@np.array([gain.loc[b].sum() for b in blocks]))/den
                rows.append(dict(candidate=candidate,reference=ref,metric=m,gain=float(gain.mean()),ci95=np.quantile(means,[.025,.975]).tolist(),ci99375=np.quantile(means,[.003125,.996875]).tolist(),week_blocks=len(blocks)))
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,default=OUT/'input.csv');p.add_argument('--board',type=Path,default=OUT/'board_input.csv');p.add_argument('--output',type=Path,default=OUT);a=p.parse_args()
    target=a.output.resolve()
    if any(target==base or base in target.parents for base in [ROOT/'data',ROOT/'public']):
        raise ValueError('Research output cannot overwrite production data or pages')
    a.output.mkdir(parents=True,exist_ok=True)
    d=get_data(a.input);e,fits,objects=walk(d)
    curves=[];scores={}
    groups=[('primary_2023_2025',e[e.season<=2025]),('diagnostic_2026_w1_w5',e[e.season==2026])]+[(str(y),g) for y,g in e.groupby('season')]
    for label,g in groups:
        scores[label],c=metrics(g,label);curves+=c
    primary=paired(e[e.season<=2025]);diagnostic=paired(e[e.season==2026])
    supported=[]
    for candidate in CANDIDATES:
        comps=[x for x in primary if x['candidate']==candidate and x['reference'] in ['v118','market'] and x['metric']=='log_loss']
        if len(comps)==2 and all(x['ci99375'][0]>0 for x in comps):supported.append(candidate)
    result=dict(primary=scores['primary_2023_2025'],diagnostic2026=scores['diagnostic_2026_w1_w5'],annual={str(y):scores[str(y)] for y in [2023,2024,2025,2026]},paired_primary=primary,paired_2026=diagnostic,nomination_candidates=supported,decision='research_nomination_only' if supported else 'no_replacement_supported')
    e[['game_id','season','week','y']+METHODS].to_csv(a.output/'per_game.csv',index=False)
    pd.DataFrame(curves).to_csv(a.output/'calibration.csv',index=False)
    summary=[dict(cohort=c,method=m,**v) for c,rows in scores.items() for m,v in rows.items()]
    pd.DataFrame(summary).to_csv(a.output/'scores.csv',index=False)
    (a.output/'fits.json').write_text(json.dumps(fits,indent=2)+'\n')
    (a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    board=pd.read_csv(a.board);board=board[board.result.isna()].copy();board['v118']=board.model_wp;board['market']=board.market_wp;board['v116']=invert(board.v118,board.market)
    for parent in PARENTS:
        b,i=predict(board[parent],objects[(2026,parent)]);board[parent+'_bands']=b;board[parent+'_isotonic']=i
    board[['game_id','away','home','away_injury_report','home_injury_report']+METHODS].to_csv(a.output/'current_counterfactuals.csv',index=False)
    paths=[a.input,a.board,Path(__file__),ROOT/'research/WP_PROBABILITY_CALIBRATION.md']
    provenance=dict(source_commit='690c0c6740f7a5a6c4ef3c2abe244cc0df0dca2d',source_url='https://github.com/Dave356w/NFL-MODEL/blob/690c0c6740f7a5a6c4ef3c2abe244cc0df0dca2d/data/latest/fixed_band_ledger.csv',sha256={x.name:hashlib.sha256(x.read_bytes()).hexdigest() for x in paths},python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,scipy=scipy.__version__,isotonic_implementation='weighted PAV plus linear interpolation',scope='Previously examined historical data; no production changes; ties excluded from binary target',raw_games=len(pd.read_csv(a.input)),decisive_games=len(d),scored_games=len(e),round_trip_max_error=float(abs(forward(d.v116,d.market)-d.v118).max()))
    (a.output/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(json.dumps(dict(primary=result['primary'],diagnostic2026=result['diagnostic2026'],nomination_candidates=supported,decision=result['decision']),indent=2))

if __name__=='__main__':main()
