"""Read-only settlement helpers for the fixed backup-team margin overlay.

Signed margins are home minus away. A home backup subtracts two points, an
away backup adds two, and two backups cancel. This is a final-margin overlay;
no median-map refit or remapping occurs here.
"""
import numpy as np
import pandas as pd

import fixed_bands as fb


def _vector(value, index):
    if isinstance(value,pd.Series):
        return pd.to_numeric(value.reindex(index),errors='coerce').to_numpy(float)
    if np.isscalar(value):return np.full(len(index),float(value))
    out=np.asarray(value,float)
    if out.ndim!=1 or len(out)!=len(index):raise ValueError('one value per game required')
    return out


def apply_penalty(frame,home_flag,away_flag,margin_column='fixed_band_spread',penalty=2.):
    """Return adjusted margins; missing backup flags stay unresolved, never zero."""
    if not np.isfinite(penalty) or penalty<0:raise ValueError('penalty must be finite and nonnegative')
    home=_vector(home_flag,frame.index);away=_vector(away_flag,frame.index)
    for value in (home,away):
        if np.isinf(value).any() or not np.isin(value[np.isfinite(value)],[0.,1.]).all():raise ValueError('backup flags must be zero, one or missing')
    raw=pd.to_numeric(frame[margin_column],errors='coerce').to_numpy(float)
    return pd.Series(raw-penalty*home+penalty*away,index=frame.index,name='adjusted_margin')


def _profit(price):
    price=np.asarray(price,float)
    out=np.full(price.shape,np.nan)
    positive=np.isfinite(price)&(price>0);negative=np.isfinite(price)&(price<0)
    out[positive]=price[positive]/100.;out[negative]=100./(-price[negative])
    return out


def grade(frame,predictions,line_column='spread_line',result_column='result',price_mode='minus110'):
    """Grade unchanged handicaps with -110 or the selected side's matched price.

    side_specific assumes ats_home_odds/ats_away_odds already refer to this row's
    saved handicap. An unavailable side price remains missing, even for losses;
    it never borrows the price originally attached to the other side.
    """
    if price_mode not in ('minus110','side_specific'):raise ValueError('unknown price mode')
    pred=_vector(predictions,frame.index)
    line=pd.to_numeric(frame[line_column],errors='coerce').to_numpy(float)
    actual=pd.to_numeric(frame[result_column],errors='coerce').to_numpy(float)
    sides=fb.pick(pred,line)
    temp=pd.DataFrame({'spread_line':line,'result':actual})
    grades,_=fb.grade(temp,pred)
    if price_mode=='minus110':
        price=np.where(np.isin(sides,[-1.,1.]),-110.,np.nan)
        basis=np.where(np.isfinite(price),'assumed_minus110','no_selection')
    else:
        home=pd.to_numeric(frame.get('ats_home_odds',pd.Series(np.nan,index=frame.index)),errors='coerce').to_numpy(float)
        away=pd.to_numeric(frame.get('ats_away_odds',pd.Series(np.nan,index=frame.index)),errors='coerce').to_numpy(float)
        price=np.where(sides>0,home,np.where(sides<0,away,np.nan))
        valid=np.isfinite(price)&(price!=0)
        price=np.where(valid,price,np.nan)
        source=frame.get('ats_price_basis',pd.Series('matched_side_price',index=frame.index)).fillna('matched_side_price').astype(str).to_numpy()
        basis=np.where(valid,source,np.where(sides==0,'no_selection','unavailable_side_price'))
    payout=_profit(price)
    units=np.where(grades=='W',payout,np.where(grades=='L',-1.,np.where(np.isin(grades,['P','S']),0.,np.nan)))
    # A missing price cannot enter only on losses; use the same priced cohort.
    units=np.where(np.isin(grades,['W','L','P'])&~np.isfinite(price),np.nan,units)
    return pd.DataFrame(dict(prediction=pred,side=sides,
        selected_side=np.where(sides>0,'home',np.where(sides<0,'away',np.where(sides==0,'skip','unknown'))),
        grade=grades,units=units,price=price,price_basis=basis),index=frame.index)


def summary(grades):
    """Flat-stake returns; ROI denominator includes pushes and excludes skips."""
    g=grades['grade'];bets=g.isin(['W','L','P']);priced=bets&grades.units.notna()
    ret=grades.loc[priced,'units'].to_numpy(float)
    counts={key:int(g.eq(key).sum()) for key in ['W','L','P','S']}
    decided=counts['W']+counts['L']
    return dict(n=int(bets.sum()),priced_n=len(ret),WLP=f"{counts['W']}-{counts['L']}-{counts['P']}",
        wins=counts['W'],losses=counts['L'],pushes=counts['P'],skips=counts['S'],unresolved=int(g.eq('').sum()),
        cover_rate=counts['W']/decided if decided else None,
        units=float(ret.sum()) if len(ret) else None,roi=float(ret.mean()) if len(ret) else None,
        roi_se=float(ret.std(ddof=1)/np.sqrt(len(ret))) if len(ret)>1 else None)


def paired_summary(before,after):
    """Compare the same completed decisions; keep missing-price games symmetric."""
    if not before.index.equals(after.index):raise ValueError('paired rows must have identical indices and order')
    completed=before['grade'].isin(['W','L','P','S'])&after['grade'].isin(['W','L','P','S'])
    priced=completed&before.units.notna()&after.units.notna()
    diff=(after.loc[priced,'units']-before.loc[priced,'units']).to_numpy(float)
    flips=completed&before.side.ne(after.side)
    return dict(n=int(completed.sum()),priced_n=len(diff),flips=int(flips.sum()),
        flip_before=summary(before.loc[flips]),flip_after=summary(after.loc[flips]),
        units_gain=float(diff.sum()) if len(diff) else None,
        mean_gain_per_game=float(diff.mean()) if len(diff) else None,
        mean_gain_se=float(diff.std(ddof=1)/np.sqrt(len(diff))) if len(diff)>1 else None)
