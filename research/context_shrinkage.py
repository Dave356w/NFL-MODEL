"""Prior-week support-aware ridge experiment; see CONTEXT_SHRINKAGE.md."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit
import qualified_interactions as q
import production_qualification as p

m = q.m
ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = {'active_10': ('active', 10.), 'active_30': ('active', 30.),
              'active_100': ('active', 100.), 'information_30': ('information', 30.)}
CONTEXTS = list(m.PRODUCT_CONTEXT_NAMES)


def effective_support(raw, weights, mode):
    """Scale-invariant Kish support, with zero support for an inactive column."""
    x, w = np.asarray(raw, float), np.asarray(weights, float)
    if x.ndim != 2 or w.shape != (len(x),) or not np.isfinite(x).all():
        raise ValueError('Invalid support inputs')
    if not np.isfinite(w).all() or (w < 0).any() or w.sum() <= 0:
        raise ValueError('Invalid support weights')
    if mode == 'active': mass = w[:, None] * (x != 0)
    elif mode == 'information': mass = w[:, None] * x*x
    else: raise ValueError('Unknown support method')
    den = (mass*mass).sum(axis=0)
    return np.divide(mass.sum(axis=0)**2, den, out=np.zeros(x.shape[1]), where=den > 0)


def fit(train, year, week, mode='active', strength=0., product_only=False, market_offset=True):
    if not np.isfinite(strength) or strength < 0: raise ValueError('Invalid strength')
    if not m.before(train, year, week).all(): raise ValueError('Training includes current/future week')
    extras = CONTEXTS[:1] if product_only else CONTEXTS
    names = m.feature_names(q.BASE_FAMILY) + extras
    t = train[train.ready & train['home won'].isin([0., 1.]) & np.isfinite(train.q)
              & np.isfinite(train[CONTEXTS]).all(axis=1)].copy()
    if len(t) < m.MIN_TRAIN_GAMES: raise ValueError('Insufficient eligible training')
    raw = np.nan_to_num(t[names].to_numpy(float), nan=0., posinf=0., neginf=0.)
    age = ((year-t.season.to_numpy())*19 + week-t.week.to_numpy()) / (19*m.FIT_HALF_LIFE_SEASONS)
    w = np.exp2(-age); w /= w.sum()
    mu = w@raw; scale = np.sqrt(w@((raw-mu)**2)); scale[scale<=1e-8] = 1.; scale[0] = 1.
    X = raw/scale
    penalty = np.full(len(names), .1); penalty[0] *= .1
    support = effective_support(raw[:, -len(extras):], w, mode)
    # Only sparse hinge coefficients get extra shrinkage; retain product baseline.
    multipliers = np.ones(len(extras))
    multipliers[1:] += strength/np.maximum(support[1:], 1.)
    penalty[-len(extras):] *= multipliers
    base = logit(np.clip(t.q.to_numpy(), 1e-5, 1-1e-5)) if market_offset else np.zeros(len(t))
    y = t['home won'].to_numpy()
    def objective(beta):
        eta = base + X@beta
        return (np.sum(w*(np.logaddexp(0, eta)-y*eta))+.5*np.sum(penalty*beta**2),
                X.T@(w*(expit(eta)-y))+penalty*beta)
    beta = m.checked_optimize(objective, len(names))
    return {'names': names, 'scale': scale.tolist(), 'beta': beta.tolist(), 'market_offset': bool(market_offset),
            'mode': mode, 'strength': strength, 'support': dict(zip(extras, support.tolist())),
            'penalty_multiplier': dict(zip(extras, multipliers.tolist())),
            'training_games': len(t), 'training_max_season': int(t.season.max()),
            'training_max_week': int(t.loc[t.season==t.season.max(), 'week'].max())}


def predict(frame, fitted):
    return m.apply_fit(frame, fitted)


def loss(y, prob):
    prob = np.clip(np.asarray(prob), 1e-12, 1-1e-12)
    return -(y*np.log(prob)+(1-y)*np.log1p(-prob))


def analyze(held, arms):
    bets = {a: m.flat_bets(held, a) for a in arms}
    common = np.logical_and.reduce([b.units.notna().to_numpy() for b in bets.values()])
    proper = held['home won'].isin([0.,1.]).to_numpy()
    groups = (held.season.astype(str)+'_'+held.week.astype(str)).to_numpy()
    rows, pairs, annual, slices = [], [], [], []
    for a in arms:
        b = bets[a].loc[common]; ll = loss(held['home won'].to_numpy(), held[a])
        rows.append({'arm': a, **m.roi_summary(b),
                     'roi_cluster_ci95': p.cluster_interval(b.units, groups[common], .95),
                     'log_loss': float(ll[proper].mean()),
                     'brier': float(((held[a]-held['home won'])**2).to_numpy()[proper].mean())})
        if a in (*CANDIDATES, 'selected'):
            du = (bets[a].units-bets['production'].units).to_numpy()[common]
            dl = loss(held['home won'].to_numpy(), held.production)-ll
            level = .95 if a=='selected' else .9875
            pairs.append({'arm': a, 'confidence_level': level,
                          'roi_delta': float(du.mean()), 'roi_delta_ci': p.cluster_interval(du, groups[common], level),
                          'll_gain': float(dl[proper].mean()), 'll_gain_ci': p.cluster_interval(dl[proper], groups[proper], level),
                          'side_flips': int(((held[a]>.5)!=(held.production>.5)).to_numpy()[common].sum())})
        for year in sorted(held.season.unique()):
            mask = (held.season==year).to_numpy()
            annual.append({'arm': a, 'season': int(year), **m.roi_summary(bets[a].loc[common&mask]),
                           'log_loss': float(ll[proper&mask].mean())})
        for label, mask in [('any hinge active', (held[CONTEXTS[1:]]!=0).any(axis=1).to_numpy()),
                            ('PN active', (held.pass_1sd_pn!=0).to_numpy()),
                            ('production >=90%', (np.maximum(held.production, 1-held.production)>=.9).to_numpy())]:
            ps = proper&mask
            if ps.any():
                slices.append({'arm': a, 'slice': label, 'games': int(ps.sum()),
                               'log_loss': float(ll[ps].mean()),
                               'brier': float(((held[a]-held['home won'])**2).to_numpy()[ps].mean()),
                               **m.roi_summary(bets[a].loc[common&mask])})
    return {'results': rows, 'comparisons': pairs, 'by_season': annual, 'slices': slices,
            'bets': int(common.sum()), 'proper_games': int(proper.sum()),
            'excluded_bets': held.loc[~common, 'game_id'].tolist()}


def run(input_dir, output_dir, rebuild_inputs=False):
    for target in (input_dir, output_dir):
        for protected in (ROOT/'data', ROOT/'public'):
            if target.resolve()==protected or protected in target.resolve().parents:
                raise ValueError('Research cannot write production outputs')
    input_dir.mkdir(parents=True, exist_ok=True)
    pack=output_dir/'frozen_training_features.csv.gz'
    ref_path=output_dir/'normalization_references.csv'
    snapshot_path=output_dir/'archived_current_inputs.jsonl'
    if pack.exists() and ref_path.exists() and snapshot_path.exists() and not rebuild_inputs:
        f=pd.read_csv(pack);refs=pd.read_csv(ref_path)
        print('Using frozen pregame training features',flush=True)
    else:
        q.OUT=input_dir.resolve(); q.CACHE=q.OUT/'cache'; q.YEARS=list(range(2019,2027))
        schedules, boxes, av = q.prepare()
        print('Building prior-game h8 and h16 profiles',flush=True)
        f8=m.lagged_features(boxes,schedules,8.,av); f16=m.lagged_features(boxes,schedules,16.,av)
        if f8.game_id.tolist()!=f16.game_id.tolist(): raise ValueError('Profile alignment mismatch')
        desc, refs=m.pass_contexts(f16)
        f=m.attach_moneylines(f8,schedules); f['q']=m.market_ml_wp(f); f=pd.concat([f,desc],axis=1)
        cols=list(dict.fromkeys(p.BASE_COLS+['ready']+m.feature_names(q.BASE_FAMILY)+CONTEXTS))
        f=f[cols].copy()
        output_dir.mkdir(parents=True,exist_ok=True)
        f.to_csv(pack,index=False,compression={'method':'gzip','mtime':0})
        refs.to_csv(ref_path,index=False)
        raw=[json.loads(x) for x in (ROOT/'data/forward_predictions.jsonl').read_text().splitlines()]
        raw=[r for r in raw if r['revision']=='boxscore-composite-v1.16' and 'model_inputs' in r]
        snapshot_path.write_text(''.join(json.dumps(r)+'\n' for r in raw))
    # Normalize column naming for binary scoring and evaluation output.
    eligible=f.ready & f['home won'].isin([0.,1.]) & np.isfinite(f.q) & np.isfinite(f[CONTEXTS]).all(axis=1)
    evaluation=f.ready & f['home won'].isin([0.,.5,1.]) & np.isfinite(f.q) & np.isfinite(f[CONTEXTS]).all(axis=1) & f.season.between(2021,2025)
    out=f.loc[evaluation, p.BASE_COLS+CONTEXTS].copy(); audit=[]
    arms=['production','product_only',*CANDIDATES]
    for (year,week), rows in out.groupby(['season','week'],sort=True):
        train=f[eligible&m.before(f,year,week)]; test=f.loc[rows.index]
        for arm in arms:
            mode,k=CANDIDATES.get(arm,('active',0.))
            fitted=fit(train,int(year),int(week),mode,k,product_only=arm=='product_only')
            out.loc[rows.index,arm]=predict(test,fitted)
            audit.append({'arm':arm,'evaluation_season':int(year),'evaluation_week':int(week),
                          **{k:v for k,v in fitted.items() if k not in ('names','scale','beta')}})
            if arm=='production':
                reference=m.fit_composite(train,m.LEGACY_PRODUCT_RECIPE,int(year),int(week))
                if not np.allclose(out.loc[rows.index,arm],m.apply_fit(test,reference),atol=1e-10,rtol=0):
                    raise ValueError('Zero-shrinkage production math failed')
        if week==1: print(f'Fit season {year}',flush=True)
    if not np.isfinite(out[arms]).all().all(): raise ValueError('Incomplete predictions')
    held=out[out.season.between(2023,2025)].copy(); selections=[]
    for year in (2023,2024,2025):
        prior=out[out.season<year]; binary=prior['home won'].isin([0.,1.])
        scores={a:float(loss(prior.loc[binary,'home won'].to_numpy(),prior.loc[binary,a]).mean()) for a in ['production',*CANDIDATES]}
        choice=min(scores,key=lambda a:(scores[a],a))
        held.loc[held.season==year,'selected']=held.loc[held.season==year,choice]
        selections.append({'evaluation_season':year,'selection_through_season':int(prior.season.max()),'chosen':choice,'prior_losses':scores})
    held['market']=held.q
    expected=pd.read_csv(ROOT/'research/production_adoption_results/historical_reproduction.csv').set_index('game_id')
    matched=held.set_index('game_id').join(expected.production_probability)
    if matched.production_probability.isna().any(): raise ValueError('Historical coverage differs')
    err=float(abs(matched.production-matched.production_probability).max())
    if err>=1e-7: raise ValueError('Committed historical production reproduction failed')
    info=analyze(held,['production','product_only','market',*CANDIDATES,'selected'])
    reference_ok=((refs.max_reference_season<refs.season)|((refs.max_reference_season==refs.season)&(refs.max_reference_week<refs.week))).all()
    if not reference_ok: raise ValueError('Future normalization reference')
    # Refit on earlier rows and replay archived current-week inputs and prices.
    snapshots=[json.loads(x) for x in snapshot_path.read_text().splitlines()]
    current=[]; current_fits={}
    for r in snapshots:
        year,week=r['season'],r['week']; train=f[eligible&m.before(f,year,week)]
        row=pd.DataFrame([{**r['model_inputs'],'q':r['market_no_vig_wp']}])
        item={'game_id':r['game_id'],'generated_utc':r['generated_utc'],'archived_probability':r['model_wp'],
              'market_probability':r['market_no_vig_wp']}
        for arm in arms:
            key=(year,week,arm)
            if key not in current_fits:
                mode,k=CANDIDATES.get(arm,('active',0.));current_fits[key]=fit(train,year,week,mode,k,arm=='product_only')
            item[arm]=float(predict(row,current_fits[key])[0])
        current.append(item)
    info.update({'basis':'Exposed historical development; prior-week fits, 2023-2025',
                 'revision':m.REVISION,'protocol':'research/CONTEXT_SHRINKAGE.md',
                 'selections':selections,'historical_max_probability_error':err,
                 'historical_comparator_reproduced':err<1e-7,
                 'all_references_prior_week':bool(reference_ok),'fits':len(audit),
                 'current_max_probability_error':max((abs(r['production']-r['archived_probability']) for r in current),default=None)})
    info['production_extreme_games']=int((np.maximum(held.production,1-held.production)>=.9).sum())
    tail=held[np.maximum(held.production,1-held.production)>=.9]
    info['production_extreme_wins']=int(((tail.production>.5)==(tail['home won']==1.)).sum())
    if info['current_max_probability_error'] is not None and info['current_max_probability_error']>=1e-7:
        raise ValueError('Archived current production reproduction failed')
    output_dir.mkdir(parents=True,exist_ok=True)
    held.to_csv(output_dir/'heldout_predictions.csv',index=False)
    pd.DataFrame(current).to_csv(output_dir/'current_counterfactuals.csv',index=False)
    (output_dir/'fit_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    (output_dir/'current_fits.json').write_text(json.dumps({str(k):v for k,v in current_fits.items()},indent=2)+'\n')
    (output_dir/'results.json').write_text(json.dumps(info,indent=2,allow_nan=False)+'\n')
    sources=[Path(__file__),ROOT/'research/CONTEXT_SHRINKAGE.md',ROOT/'nfl_model.py',pack,ref_path,snapshot_path]
    sources += [x for x in [input_dir/'schedule.csv',input_dir/'boxes.csv',input_dir/'availability.pkl'] if x.exists()]
    (output_dir/'provenance.json').write_text(json.dumps({str(x.relative_to(ROOT)) if x.is_relative_to(ROOT) else str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},indent=2)+'\n')
    write_report(info,current,output_dir)
    print(json.dumps(info['results'],indent=2),flush=True)


def write_report(info,current,out):
    lines=['# Context shrinkage backtest','','Basis: '+info['basis']+'. Recipe design used this history; not forward evidence.',
           f"\n{info['bets']} common flat 1u bets; {info['proper_games']} binary proper scores.",
           '\n| Arm | W-L-P | Units | ROI ± SE | Market-null ROI | Log loss | Brier |',
           '|---|---:|---:|---:|---:|---:|---:|']
    for r in info['results']:
        lines.append(f"| {r['arm']} | {r['wins']}-{r['losses']}-{r['pushes']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% ± {100*r['roi_se']:.2f} | {100*r['null_roi']:+.2f}% | {r['log_loss']:.6f} | {r['brier']:.6f} |")
    lines+=['','Paired prior-week-cluster bootstrap; four fixed candidate comparisons use 98.75% intervals. Positive LL gain favors shrinkage.',
            '\n| Arm | ROI delta vs production [CI], pp | LL gain [CI] | Side flips |','|---|---:|---:|---:|']
    for r in info['comparisons']:
        lo,hi=r['roi_delta_ci'];ll,lh=r['ll_gain_ci']
        lines.append(f"| {r['arm']} | {100*r['roi_delta']:+.2f} [{100*lo:+.2f}, {100*hi:+.2f}] | {r['ll_gain']:+.6f} [{ll:+.6f}, {lh:+.6f}] | {r['side_flips']} |")
    lines+=['','## Annual selection','']+[f"- {r['evaluation_season']}: {r['chosen']}; selection through {r['selection_through_season']}." for r in info['selections']]
    lines+=['','## Annual results','','| Arm | Season | Units | ROI | Log loss |','|---|---:|---:|---:|---:|']
    for r in info['by_season']:lines.append(f"| {r['arm']} | {r['season']} | {r['units']:+.2f} | {100*r['roi']:+.2f}% | {r['log_loss']:.6f} |")
    lines+=['','## Diagnostic slices','','| Arm | Slice | Binary games | Log loss | Brier |','|---|---|---:|---:|---:|']
    for r in info['slices']:lines.append(f"| {r['arm']} | {r['slice']} | {r['games']} | {r['log_loss']:.6f} | {r['brier']:.6f} |")
    lines+=['','## Current SF at SEA counterfactual','','Probabilities are Seattle/home; joint prior-week refits at archived inputs. Not new forward snapshots.']
    for r in current:
        if r['game_id']=='2026_05_SF_SEA':lines += ['']+[f'- {a}: {100*r[a]:.2f}%' for a in ['archived_probability','production','product_only',*CANDIDATES]]
    lines+=['','## Reproduction and limits','',f"Historical max probability error vs committed production: {info['historical_max_probability_error']:.3g}.",
            f"Current max probability error vs archived production: {info['current_max_probability_error']}.",
            f"Production >=90% slice: {info['production_extreme_wins']} wins from {info['production_extreme_games']} games; small exposed sample, not confirmation of calibrated tail probabilities.",
            'Full timing/support audit and input/source hashes accompany this report. Historical input revisions can affect reproduction.',
            'Shrinking coefficients does not bound an extreme current input or independently validate 94% confidence. Intervals omit model-design selection uncertainty.',
            'Production and its ledger were not modified. Run: `python research/context_shrinkage.py`.','']
    (out/'REPORT.md').write_text('\n'.join(lines))


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input-dir',type=Path,default=ROOT/'.nfl_cache/shrinkage_inputs')
    ap.add_argument('--output-dir',type=Path,default=ROOT/'research/shrinkage_results')
    ap.add_argument('--rebuild-inputs',action='store_true',help='Rebuild and replace the frozen research feature pack')
    args=ap.parse_args();run(args.input_dir,args.output_dir,args.rebuild_inputs)
