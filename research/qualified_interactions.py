"""Research-only chronological test of league-relative pass matchup contexts.

No production settings, frozen recipes, or ledger files are modified.
The protocol is written in qualified_interactions_protocol.md before results.
"""
import concurrent.futures
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import nfl_model as m

OUT = Path(__file__).resolve().parent / 'qualified_output'
CACHE = OUT / 'cache'
YEARS = list(range(2019, 2026))

def prepare():
    OUT.mkdir(exist_ok=True); CACHE.mkdir(exist_ok=True)
    m.CACHE_DIR = str(CACHE); m.OUTPUT_ROOT = OUT; m.UPSTREAM_RETRIES = 2
    gp = OUT / 'schedule.csv'; bp = OUT / 'boxes.csv'; ap = OUT / 'availability.pkl'
    if gp.exists() and bp.exists() and ap.exists():
        return pd.read_csv(gp), pd.read_csv(bp), pd.read_pickle(ap)
    import nflreadpy as nfl
    s = nfl.load_schedules(YEARS).to_pandas()
    s = m.normalize_teams(s[s.game_type == 'REG'].copy())
    s['home won'] = s.result.map(m.won)
    s['site'] = np.where(s.location.str.lower() == 'neutral', 0., 1.)
    from scipy.special import ndtr
    s['market WP'] = ndtr(s.spread_line / m.MARKET_SIGMA)
    s.to_csv(gp, index=False)
    def boxes(y):
        b, q = m.load_boxes(y, s[s.season == y])
        print('boxes ready', y, flush=True)
        return b, q
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        af = pool.submit(m.load_availability, YEARS, 2026)
        bs = list(pool.map(boxes, YEARS))
        a = af.result()
    b = pd.concat([x[0] for x in bs], ignore_index=True)
    q = pd.concat([x[1] for x in bs], ignore_index=True)
    b.to_csv(bp, index=False)
    av = m.availability_table(m.availability_targets(s), q, a['snaps'], a['inj'], a['rost'], depth=a.get('depth'))
    av.to_pickle(ap)
    return s, b, av

ARMS = ('additive', 'product', 'qualified', 'extreme')
PENS = (.01, .1, 1., 10.)
BASE_FAMILY = 'rates_core_avail_cs_peaks_nosacks'
STAT = 'net_pass_yards_per_pass_play'

def descriptors(f):
    """Each row is transformed once with strictly prior-week reference values."""
    z = np.full((len(f), 4), np.nan)
    cols = [f'{side}__{role}__rates_core__{STAT}' for side, role in
            [('home','for'),('away','allowed'),('away','for'),('home','allowed')]]
    audit = []
    for (y, w), g in f.groupby(['season','week'], sort=True):
        earlier = m.before(f, y, w)
        ref = f[earlier & (f.season >= y-4)]
        cur = ref[ref.season == y]
        if cur.empty: cur = ref[ref.season == y-1]
        if cur.empty: continue
        for role, ix in [('for',(0,2)), ('allowed',(1,3))]:
            cc = [cols[i] for i in ix]
            center_values=cur[cc].to_numpy(); scale_values=ref[cc].to_numpy()
            center_values=center_values[np.isfinite(center_values)]
            scale_values=scale_values[np.isfinite(scale_values)]
            if not len(center_values) or len(scale_values)<2: continue
            mu = center_values.mean()
            sd = scale_values.std(ddof=1)
            if not np.isfinite(sd) or sd <= 1e-8: continue
            for i in ix: z[g.index, i] = (g[cols[i]].to_numpy()-mu)/sd
        audit.append({'season':int(y),'week':int(w),'reference_games':len(ref),
                      'max_reference_season':int(ref.season.max()),
                      'max_reference_week':int(ref.loc[ref.season==ref.season.max(),'week'].max())})
    d = pd.DataFrame(z, columns=['ho','ad','ao','hd'], index=f.index)
    d['product'] = z[:,0]*z[:,1]-z[:,2]*z[:,3]
    for threshold, prefix in [(0., 'q'), (1., 'e')]:
        for a, sa in [('p',1.),('n',-1.)]:
            for b, sb in [('p',1.),('n',-1.)]:
                d[f'{prefix}_{a}{b}'] = (np.maximum(sa*z[:,0]-threshold,0)*np.maximum(sb*z[:,1]-threshold,0)
                    -np.maximum(sa*z[:,2]-threshold,0)*np.maximum(sb*z[:,3]-threshold,0))
    ok = np.isfinite(z).all(1)
    assert np.allclose(d.loc[ok,'product'], (d.q_pp-d.q_pn-d.q_np+d.q_nn)[ok])
    pd.DataFrame(audit).to_csv(OUT/'reference_audit.csv',index=False)
    return d

def fit_predict(tr, te, names, extra, penalty, offset):
    X = tr[names+extra].to_numpy(float); T = te[names+extra].to_numpy(float)
    X = np.where(np.isfinite(X),X,0.); T = np.where(np.isfinite(T),T,0.)
    y, w = int(te.season.iloc[0]), int(te.week.iloc[0])
    assert m.before(tr,y,w).all()
    age = ((y-tr.season.to_numpy())*19+w-tr.week.to_numpy())/(19*m.FIT_HALF_LIFE_SEASONS)
    weights = np.exp2(-age); weights /= weights.sum()
    mu = weights@X
    sc = np.sqrt(weights@((X-mu)**2)); sc[sc<1e-8]=1.; sc[0]=1.
    X /= sc; T /= sc
    pen = np.r_[np.full(len(names),.1), np.full(len(extra),penalty)]; pen[0]*=.1
    o = logit(np.clip(tr.q.to_numpy(),1e-5,1-1e-5)) if offset else np.zeros(len(tr))
    ot = logit(np.clip(te.q.to_numpy(),1e-5,1-1e-5)) if offset else np.zeros(len(te))
    target = tr['home won'].to_numpy()
    def obj(beta):
        eta = o+X@beta
        return np.sum(weights*(np.logaddexp(0,eta)-target*eta))+.5*np.sum(pen*beta**2), X.T@(weights*(expit(eta)-target))+pen*beta
    beta = m.checked_optimize(obj,len(pen))
    return expit(ot+T@beta)

def losses(y,p):
    p = np.clip(p,1e-12,1-1e-12)
    return -(y*np.log(p)+(1-y)*np.log1p(-p))

def boot_ci(values, weeks, level=.975):
    vals = np.asarray(values,float); good=np.isfinite(vals)
    a = pd.DataFrame({'v':vals[good],'g':np.asarray(weeks)[good]}).groupby('g').v.agg(['sum','count'])
    rng = np.random.default_rng(20261010)
    idx = rng.integers(0,len(a),(4000,len(a)))
    means=a['sum'].to_numpy()[idx].sum(1)/a['count'].to_numpy()[idx].sum(1)
    tail=(1-level)/2
    return np.quantile(means,[tail,1-tail]).tolist()

def evaluate(f, desc):
    d = pd.concat([f, desc],axis=1)
    d['q']=m.market_ml_wp(d)
    d=d[d.ready & d['home won'].isin([0.,1.]) & np.isfinite(d['product']) & np.isfinite(d.q)].copy()
    extras={'additive':[], 'product':['product'], 'qualified':['q_pp','q_pn','q_np','q_nn'],
            'extreme':['product','e_pp','e_pn','e_np','e_nn']}
    names=m.feature_names(BASE_FAMILY)
    out=d[d.season>=2021].copy()
    for (yr,wk),te in out.groupby(['season','week'],sort=True):
        tr=d[m.before(d,yr,wk)]
        for mode in ('model','market_offset'):
            for arm in ARMS:
                for r in ([.1] if arm=='additive' else PENS):
                    col=f'{mode}__{arm}__{r:g}'
                    out.loc[te.index,col]=fit_predict(tr,te,names,extras[arm],r,mode=='market_offset')
        if wk==1: print('fits',yr,flush=True)
    prediction_cols=[c for c in out if c.startswith(('model__','market_offset__'))]
    assert np.isfinite(out[prediction_cols]).all().all()
    out.to_csv(OUT/'candidate_predictions.csv',index=False)
    held=out[out.season.between(2023,2025)].copy()
    selection=[]
    for yr in (2023,2024,2025):
        prior=out[out.season<yr]; mask=held.season==yr
        for mode in ('model','market_offset'):
            for arm in ARMS:
                cols=[c for c in prediction_cols if c.startswith(f'{mode}__{arm}__')]
                best=min(cols,key=lambda c:losses(prior['home won'].to_numpy(),prior[c].to_numpy()).mean())
                held.loc[mask,f'p__{mode}__{arm}']=held.loc[mask,best]
                selection.append({'season':yr,'mode':mode,'arm':arm,'selected':best,'validation_games':len(prior)})
    held.to_csv(OUT/'heldout_predictions.csv',index=False)
    pd.DataFrame(selection).to_csv(OUT/'selection.csv',index=False)
    return held, selection

def summarize(h, selection):
    y=h['home won'].to_numpy(); groups=(h.season.astype(str)+'_'+h.week.astype(str)).to_numpy()
    results=[]; vec={}
    allp=['q']+[c for c in h if c.startswith('p__')]
    fav=m.flat_bets(h,'q')
    # One common priced sample, excluding tied market probabilities.
    common=fav.units.notna().to_numpy()
    for col in allp:
        b=m.flat_bets(h,col); keep=common & b.units.notna().to_numpy()
        s=m.roi_summary(b[keep]); l=losses(y,h[col].to_numpy())
        results.append({'arm':col,'n':int(keep.sum()),'wins':s['wins'],'losses':s['losses'],'pushes':s['pushes'],
                        'units':s['units'],'roi':s['roi'], 'roi_se':s['roi_se'],
                        'null':float(b.null_ev[keep].mean()),'log_loss':float(l.mean()),
                        'brier':float(np.mean((h[col].to_numpy()-y)**2))})
        vec[col]=(l,b.units.where(common).to_numpy())
    comparisons=[]
    for mode in ('model','market_offset'):
        for arm in ('product','qualified','extreme'):
            for base in (['additive'] if arm=='product' else ['product','additive']):
                a=f'p__{mode}__{arm}'; b=f'p__{mode}__{base}'
                gain=vec[b][0]-vec[a][0]; du=vec[a][1]-vec[b][1]
                comparisons.append({'mode':mode,'arm':arm,'baseline':base,'ll_gain':float(gain.mean()),
                    'll_ci_97_5':boot_ci(gain,groups),'roi_diff':float(np.nanmean(du)),
                    'roi_ci_97_5':boot_ci(du,groups),
                    'flips':int(((h[a]>.5)!=(h[b]>.5)).sum())})
    by=[]
    for yr,g in h.groupby('season'):
        for col in allp:
            bet=m.flat_bets(g,col); s=m.roi_summary(bet[bet.units.notna() & m.flat_bets(g,'q').units.notna()])
            by.append({'season':int(yr),'arm':col,'n':s['bets'],'roi':s['roi'],'log_loss':float(losses(g['home won'].to_numpy(),g[col].to_numpy()).mean())})
    counts=[]
    for side,o,de in [('home','ho','ad'),('away','ao','hd')]:
        for a,sa in [('strong',1),('weak',-1)]:
            for b,sb in [('permissive',1),('restrictive',-1)]:
                k=(sa*h[o]>0)&(sb*h[de]>0)
                counts.append({'side':side,'offense':a,'defense':b,'games':int(k.sum()),
                               'both_beyond_1sd':int(((sa*h[o]>1)&(sb*h[de]>1)).sum())})
    report={'basis':'development reconstructions; weekly earlier-game fits, 2023-25 evaluation',
            'base_commit':'966b308bb1be06ecaa9b0ec81f9897345dd4ac60','results':results,
            'comparisons':comparisons,'by_season':by,'context_counts':counts,'selection':selection}
    (OUT/'results.json').write_text(json.dumps(report,indent=2))
    for r in results: print(r,flush=True)
    for c in comparisons: print(c,flush=True)
    return report

def main():
    s,b,av=prepare()
    fp=OUT/'features_h8.pkl'; dp=OUT/'pass_descriptors.pkl'
    if fp.exists() and dp.exists():
        f=pd.read_pickle(fp); desc=pd.read_pickle(dp)
    else:
        print('building profiles',flush=True)
        f=m.attach_moneylines(m.lagged_features(b,s,8.,av),s)
        f.to_pickle(fp)
        f16=m.lagged_features(b,s,16.,av)
        assert f.game_id.tolist()==f16.game_id.tolist()
        desc=descriptors(f16); desc.to_pickle(dp)
    h,selection=evaluate(f,desc)
    summarize(h,selection)

if __name__ == '__main__':
    main()
