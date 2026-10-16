"""Descriptive R003 iteration/band comparisons; no fits or strategy selection."""
from pathlib import Path
import json

import numpy as np
import pandas as pd
from scipy.special import xlogy

import plain_ats_110 as a

m=a.m
b=a.s.b
OUT=m.j.ROOT/'research/r003_band_comparison'
PLAIN='MC2:direct_ref_h2_t3_p0'
SOURCES=[('R003','R003_score_support'),('RF1','R003_rare_frequency'),('MC1','R003_market_context'),
         ('MC2','R003_market_context_refinement'),('SC1','R003_schedule_context'),
         ('PT1','R003_pooled_travel'),('AC1','R003_ats_calibration')]
HIGHLIGHTS={
    'R003:empirical__R003_score_support':'Original support mask (legacy)',
    'RF1:empirical__R003_rare_frequency':'RF1 rare-score penalty (legacy)',
    'MC1:selected_all':'MC1 selected, includes translated scores',
    'MC1:selected_direct_kernel':'MC1 selected direct',
    PLAIN:'Plain observed-score model',
    'SC1:selected_all':'SC1 selected schedule context',
    'PT1:selected':'PT1 selected pooled travel',
    'AC1:selected':'AC1 selected calibration',
    'AC1:fair':'Fair 50/50 reference',
}
PROB_LABELS=['50–52.38%','52.38–55%','55–60%','60–65%','65–100%']
SPREAD_LABELS=['0–3','>3–7','>7–10','>10']
VALUE_LABELS=['≤0','>0–1','>1–3','>3–7','>7','Unavailable']
HANDICAP_LABELS=['≤−7','>−7 to −3','>−3 to 0','0','>0–3','>3–7','>7']
AXES={'probability_band':PROB_LABELS,'spread_size_band':SPREAD_LABELS,
      'projected_value_band':VALUE_LABELS,'handicap_band':HANDICAP_LABELS,'common_plain_probability_band':PROB_LABELS}


def probability_band(p):
    return pd.cut(p,[.5,11/21,.55,.6,.65,1],labels=PROB_LABELS,include_lowest=True)


def load():
    frames=[];catalog=[];paths=[]
    for iteration,folder in SOURCES:
        path=m.OUT.parent/folder/'predictions.csv.gz';paths.append(path)
        f=pd.read_csv(path,low_memory=False)
        field='arm' if 'arm' in f else 'configuration'
        if iteration=='R003':f=f[f[field].eq('empirical__R003_score_support')]
        if iteration=='RF1':f=f[f[field].eq('empirical__R003_rare_frequency')]
        if iteration=='MC2':f=f[~f[field].str.startswith('global_')]
        if iteration=='SC1':f=f[~f[field].eq('plain')]
        if iteration=='PT1':f=f[~f[field].isin(['plain','SC1_selected','SC1_travel_k100'])]
        if iteration=='AC1':
            f=f[~f[field].eq('raw')].copy()
            f['cover_conditional']=f.p
            f['cover_win']=(1-f.cover_push)*f.p
            f['cover_lose']=(1-f.cover_push)*(1-f.p)
            shape_path=m.OUT.parent/folder/'distribution_metrics.csv';paths.append(shape_path)
            shape=pd.read_csv(shape_path)[['game_id','configuration','margin_mean']]
            f=f.merge(shape,on=['game_id','configuration'],how='left',validate='one_to_one')
        f=f[f.season>=2019].copy()
        f['model']=iteration+':'+f[field]
        for arm,g in f.groupby(field,sort=False):
            name=iteration+':'+arm
            selected=str(arm).startswith('selected')
            catalog.append(dict(model=name,iteration=iteration,arm=arm,
                label=HIGHLIGHTS.get(name,name),path_type='earlier-season selected' if selected else 'fixed',
                headline=name in HIGHLIGHTS,
                support='legacy score-mask/frequency model' if iteration in ['R003','RF1'] else
                    'line-calibrated observed pairs' if iteration=='AC1' else 'see original iteration protocol'))
        frames.append(f[['model','game_id','season','week','home_score','away_score','spread_line','total_line',
                         'cover_win','cover_push','cover_lose','cover_conditional','margin_mean']])
    result=pd.concat(frames,ignore_index=True)
    if result.duplicated(['model','game_id']).any():raise ValueError('Duplicate model/game forecasts')
    expected=result[result.model.eq(PLAIN)].set_index('game_id').sort_index()
    for _,g in result.groupby('model'):
        g=g.set_index('game_id').sort_index()
        if not g.index.equals(expected.index):raise ValueError('Different iteration populations')
        for col in ['season','week','home_score','away_score','spread_line','total_line']:
            if not np.allclose(g[col],expected[col],atol=0,rtol=0):raise ValueError('Mismatched source context/outcome')
    return result,catalog,paths


def prepare(f):
    f=f.copy()
    probs=f[['cover_win','cover_push','cover_lose']].to_numpy()
    if not np.isfinite(probs).all() or (probs<0).any() or not np.allclose(probs.sum(axis=1),1,atol=2e-6,rtol=0):
        raise ValueError('Invalid cover probabilities')
    p=f.cover_conditional
    if not p.between(0,1).all():raise ValueError('Invalid conditional probability')
    f['home_side']=p>=.5
    f['confidence']=np.maximum(p,1-p)
    margin=f.home_score-f.away_score
    f['label_home']=np.where(margin==f.spread_line,np.nan,(margin>f.spread_line).astype(float))
    f['label']=np.where(f.home_side,f.label_home,1-f.label_home)
    f['cover_ll']=-xlogy(f.label_home,p)-xlogy(1-f.label_home,1-p)
    f['cover_brier']=(f.label_home-p)**2
    f['expected_units']=(1-f.cover_push)*(f.confidence*(1+a.PROFIT)-1)
    f['bet']=f.expected_units>1e-12
    forced=np.where(margin==f.spread_line,0,np.where(f.label.eq(1),a.PROFIT,-1))
    f['units']=np.where(f.bet,forced,0.)
    favorite_home=f.spread_line>=0
    f['favorite_units']=np.where(margin==f.spread_line,0,np.where(np.where(favorite_home,margin>f.spread_line,margin<f.spread_line),a.PROFIT,-1))
    f['chosen_handicap']=np.where(f.home_side,-f.spread_line,f.spread_line)
    f['projected_value']=np.where(f.home_side,1,-1)*(f.margin_mean-f.spread_line)
    f['probability_band']=probability_band(f.confidence)
    f['spread_size_band']=pd.cut(f.spread_line.abs(),[-1e-12,3,7,10,np.inf],labels=SPREAD_LABELS)
    f['projected_value_band']=pd.cut(f.projected_value,[-np.inf,0,1,3,7,np.inf],labels=VALUE_LABELS[:-1]).cat.add_categories(['Unavailable']).fillna('Unavailable')
    f['handicap_band']=pd.cut(f.chosen_handicap,[-np.inf,-7,-3,-1e-12,1e-12,3,7,np.inf],labels=HANDICAP_LABELS)
    plain=f[f.model.eq(PLAIN)].set_index('game_id')
    if plain.index.has_duplicates:raise ValueError('Duplicate plain reference')
    if not f.game_id.isin(plain.index).all():raise ValueError('Missing plain reference games')
    f['common_plain_probability_band']=f.game_id.map(plain.probability_band)
    plain_home=f.game_id.map(plain.home_side).to_numpy(bool)
    f['common_probability']=np.where(plain_home,p,1-p)
    f['common_label']=np.where(plain_home,f.label_home,1-f.label_home)
    return f


def wilson(wins,n):
    if not n:return [np.nan,np.nan]
    z=1.959963984540054;p=wins/n;denom=1+z*z/n
    center=(p+z*z/(2*n))/denom
    radius=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
    return [float(center-radius),float(center+radius)]


def summary(g,common=False):
    label=g.common_label if common else g.label
    probability=g.common_probability if common else g.confidence
    valid=label.notna();bets=g[g.bet]
    win=int((bets.units>0).sum());loss=int((bets.units<0).sum());push=int((bets.units==0).sum())
    n=int(valid.sum());success=int(label.eq(1).sum());ci=wilson(success,n)
    return dict(games=len(g),decisive=n,mean_probability=float(probability[valid].mean()),
        actual_cover=float(label[valid].mean()),calibration_gap=float((label-probability).mean()),
        cover_rate_wilson_low=ci[0],cover_rate_wilson_high=ci[1],
        cover_ll=float(g.cover_ll.mean()),cover_brier=float(g.cover_brier.mean()),
        bets=len(bets),passes=len(g)-len(bets),wins=win,losses=loss,pushes=push,
        units=float(bets.units.sum()),roi=float(bets.units.mean()),
        roi_se=float(bets.units.std(ddof=1)/np.sqrt(len(bets))) if len(bets)>1 else np.nan,
        favorite_units=float(bets.favorite_units.sum()),
        fair_null_roi=-(win+loss)/len(bets)/22 if len(bets) else np.nan,
        predicted_bet_cover=float(bets.loc[bets.label.notna(),'confidence'].mean()),
        actual_bet_cover=win/(win+loss) if win+loss else np.nan,
        expected_units=float(bets.expected_units.sum()),
        calendar_return=float(g.units.mean()),mean_projected_value=float(g.projected_value.mean()))


def interactive(out,catalog,rows):
    payload=json.dumps(m.safe_json(dict(catalog=catalog,rows=rows,axes=AXES)),ensure_ascii=False,allow_nan=False).replace('</','<\\/')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><title>R003 iteration bands</title>
<style>body{font:15px system-ui;margin:30px;color:#17212b}select{margin:8px;padding:6px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #d3dce3;padding:10px;text-align:right}th:first-child{text-align:left;min-width:210px}small{display:block;color:#425466}p{max-width:1000px}.scroll{overflow:auto}</style>
<h1>R003 iteration comparison</h1><p>Historical development at assumed −110 per side. No band is a validated betting rule. Model probability bands contain different games; the common-plain bands hold the games and calibration side fixed. Return cells use each model’s positive-EV bets only.</p>
<label>Period<select id="basis"><option>2023-25</option><option>2019-22</option><option>2026 diagnostic</option><option>2023</option><option>2024</option><option>2025</option></select></label>
<label>Band<select id="axis"></select></label><label>Measure<select id="metric"><option value="calibration_gap">Actual minus predicted cover</option><option value="roi">ATS ROI</option><option value="cover_ll">Cover log loss</option><option value="units">ATS units</option></select></label>
<label>Models<select id="scope"><option value="headline">Iteration highlights</option><option value="all">All fixed and selected models</option></select></label>
<p id="note"></p><div class="scroll"><table id="table"></table></div>
<script>const data=PAYLOAD;const $=id=>document.getElementById(id);for(const key of Object.keys(data.axes)){let o=document.createElement('option');o.value=key;o.textContent=key.replaceAll('_',' ');$('axis').append(o)}
function render(){let axis=$('axis').value,metric=$('metric').value,basis=$('basis').value;let cols=data.axes[axis];let table=$('table');table.replaceChildren();let tr=document.createElement('tr');for(let text of ['Model',...cols]){let th=document.createElement('th');th.textContent=text;tr.append(th)}table.append(tr);
for(let model of data.catalog.filter(x=>$('scope').value==='all'||x.headline)){let row=document.createElement('tr'),name=document.createElement('th');name.textContent=model.label;let sub=document.createElement('small');sub.textContent=model.path_type;name.append(sub);row.append(name);for(let band of cols){let td=document.createElement('td');let r=data.rows.find(x=>x.basis===basis&&x.model===model.model&&x.axis===axis&&x.band===band);let v=r?.[metric];td.textContent=v==null?'—':metric==='roi'||metric==='calibration_gap'?(100*v).toFixed(2)+(metric==='roi'?'%':' pp'):v.toFixed(metric==='cover_ll'?4:2);if(r){let small=document.createElement('small');small.textContent=`${r.games} games · ${r.bets} bets · ${r.wins}–${r.losses}–${r.pushes}`;td.append(small);if(v!=null&&(metric==='roi'||metric==='calibration_gap')){let magnitude=Math.min(Math.abs(v)*4,.35);td.style.background=metric==='roi'?(v>0?`rgba(15,140,90,${magnitude})`:`rgba(200,60,50,${magnitude})`):`rgba(200,110,30,${magnitude})`}}row.append(td)}table.append(row)}$('note').textContent='ROI is undefined with no bets. Small bands have large uncertainty. Calibration excludes actual pushes. Projected value is the model mean margin beyond the line, oriented to its probability-selected side; older AC1 mean margins are unavailable.'}
for(let id of ['axis','metric','basis','scope'])$(id).addEventListener('change',render);render();</script></html>'''.replace('PAYLOAD',payload)
    (out/'comparison.html').write_text(html)


def run():
    OUT.mkdir(exist_ok=True)
    f,catalog,paths=load();f=prepare(f)
    totals=[];bands=[];pairs=[]
    bases=[('2023-25',f.season.between(2023,2025)),('2019-22',f.season.between(2019,2022)),
           ('2026 diagnostic',f.season.eq(2026))]+[(str(y),f.season.eq(y)) for y in [2023,2024,2025]]
    for basis,mask in bases:
        subset=f[mask];plain=subset[subset.model.eq(PLAIN)].set_index('game_id').sort_index()
        for model,g in subset.groupby('model',sort=False):
            g=g.set_index('game_id').sort_index()
            if not g.index.equals(plain.index):raise AssertionError('Unmatched comparison population')
            row=dict(basis=basis,model=model,**summary(g))
            if len(g[g.bet]):
                z=g[g.bet];boot=b.week_bootstrap(z.units,z.season,z.week)[:,0];row['roi_ci95']=b.interval(boot)
            else:row['roi_ci95']=None
            totals.append(row)
            delta=np.column_stack([plain.cover_ll-g.cover_ll,g.units-plain.units])
            boot=b.week_bootstrap(delta,g.season,g.week)
            pairs.append(dict(basis=basis,model=model,cover_ll_gain_vs_plain=float(np.nanmean(delta[:,0])),
                cover_ll_gain_ci95=b.interval(boot[:,0]),calendar_return_gain_vs_plain=float(delta[:,1].mean()),
                calendar_return_gain_ci95=b.interval(boot[:,1])))
            for axis,labels in AXES.items():
                for label in labels:
                    z=g[g[axis].eq(label)]
                    bands.append(dict(basis=basis,model=model,axis=axis,band=label,
                        calibration_side='plain chosen side' if axis.startswith('common_') else 'model chosen side',
                        **summary(z,axis.startswith('common_'))))
    pd.DataFrame(bands).to_csv(OUT/'band_metrics.csv',index=False)
    m.dump(OUT/'overall.json',totals);m.dump(OUT/'paired_comparisons.json',pairs);m.dump(OUT/'model_catalog.json',catalog)
    cross=[]
    main=f[f.season.between(2023,2025)]
    for model,g in main.groupby('model',sort=False):
        for probability in PROB_LABELS:
            for spread in SPREAD_LABELS:
                z=g[g.probability_band.eq(probability)&g.spread_size_band.eq(spread)]
                cross.append(dict(model=model,probability_band=probability,spread_size_band=spread,**summary(z)))
    pd.DataFrame(cross).to_csv(OUT/'probability_spread_cross.csv',index=False)
    ledger_cols=['model','game_id','season','week','cover_conditional','cover_push','confidence','label','cover_ll',
        'spread_line','chosen_handicap','projected_value','bet','units','favorite_units']+list(AXES)
    f[ledger_cols].to_csv(OUT/'per_game.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    interactive(OUT,catalog,bands)
    paths+=[Path(__file__),Path(a.__file__),m.j.ROOT/'research/joint_market_residuals_report.py']
    m.dump(OUT/'provenance.json',dict(basis='Exposed historical development; no new fits or model/threshold selection',
        all_models=len(catalog),main_games_per_model=816,odds_assumption='Both sides -110, not verified historical quotes',
        rule='At most one 1u risk bet at positive EV; otherwise pass. Home tie-break for forecast bands only.',
        axes=AXES,bin_endpoints='Upper endpoint included; first lower endpoint included',
        uncertainty='Overall paired whole-week bootstrap 10000 draws within season seed20261016; band cover intervals Wilson iid descriptive; ROI SE per-bet sample SE',
        caveats=['Post-hoc multi-model/multi-band slices; no multiplicity-corrected edge claim',
            'Own probability bands change membership; common-plain bands hold games and calibration side fixed',
            'ROI uses model-selected subsets; paired calendar comparisons count passes as zero',
            'No-bet ROI and empty-band calibration undefined; projected means unavailable for older AC1 records',
            'Legacy R003/RF1 differ from owner-intent direct empirical model; translated MC1 paths are labeled separately'],
        hashes={str(p.resolve().relative_to(m.j.ROOT)):m.j.sha256(p) for p in paths},production_changed=False))
    print(f'{len(catalog)} models; {len(bands)} band rows; {len(cross)} probability/spread cells')


if __name__=='__main__':run()
