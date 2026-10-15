"""Test 46: moneyline vs spread disagreement on 2006-2012 (market only); see ML_SPREAD_2006_12.md.

    python research/ml_spread_2006_12.py --freeze GAMES_CSV   # freeze 2006-2012 inputs from nflverse games.csv
    python research/ml_spread_2006_12.py                      # run once on the frozen inputs (no network)

Never writes data/ or the ledger. Market prices only; no model is fit.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import nfl_model as m  # noqa: E402

INPUTS = ROOT/'research/ml_spread_inputs'
GAMES = INPUTS/'games_2006_2012.csv'
LATER = ROOT/'research/form_windows_inputs/schedule.csv'     # 2013-2026 schedule prices (Test 43 freeze)
OUT = ROOT/'research/ml_spread_results'
PROTOCOL = 'research/ML_SPREAD_2006_12.md'
PROTOCOL_COMMIT = 'f6d90a8'
SEASONS = range(2006, 2013)
SIGMA = m.MARKET_SIGMA          # 12.37
T = 0.11133                     # 75th percentile of |dis| on 2013-2026, outcome-free (protocol)
SD_LATER = 0.09912              # SD(dis) on 2013-2026, outcome-free (protocol)
CLIP = 1e-4
COLS = ['game_id', 'season', 'week', 'game_type', 'home_team', 'away_team', 'result',
        'spread_line', 'home_moneyline', 'away_moneyline']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def freeze(games_csv):
    g = pd.read_csv(games_csv, low_memory=False)
    g = g[(g.game_type == 'REG') & g.season.isin(list(SEASONS))][COLS]
    INPUTS.mkdir(parents=True, exist_ok=True)
    g.to_csv(GAMES, index=False)
    (INPUTS/'provenance.json').write_text(json.dumps({
        'source': 'https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',
        'downloaded_utc': '2026-10-14T22:17Z', 'source_sha256': sha(games_csv),
        'frozen': str(GAMES.relative_to(ROOT)), 'frozen_sha256': sha(GAMES), 'rows': int(len(g)),
        'note': 'All 2006-2012 regular-season games, priced or not; the script filters to priced, decided games.'},
        indent=2)+'\n')
    print(f'froze {len(g)} games to {GAMES.relative_to(ROOT)}')


def disagreement(d):
    """Home no-vig moneyline probability q, spread probability q_s and dis = logit(q) - logit(q_s).
    Spread sign: positive = home favored (nflverse spread_line)."""
    d = d.copy()
    d['q'] = m.market_ml_wp(d)
    d['q_s'] = norm.cdf(pd.to_numeric(d.spread_line, errors='coerce')/SIGMA)
    d['dis'] = logit(np.clip(d.q, CLIP, 1-CLIP))-logit(np.clip(d.q_s, CLIP, 1-CLIP))
    return d


def priced(d):
    """Games with both moneylines, a spread and a result; dis computed."""
    d = disagreement(d)
    ok = d.home_moneyline.notna() & d.away_moneyline.notna() & d.spread_line.notna() & d.result.notna() & np.isfinite(d.q)
    out = d[ok].copy()
    out['y'] = np.where(out.result > 0, 1., np.where(out.result < 0, 0., np.nan))
    out['cluster'] = out.season.astype(int).astype(str)+'_'+out.week.astype(int).astype(str)
    return out.reset_index(drop=True)


def logistic(X, y, offset=None, clusters=None, iters=100):
    """Newton logistic regression with an optional fixed offset; cluster-robust sandwich SEs."""
    X = np.asarray(X, float); y = np.asarray(y, float)
    off = np.zeros(len(y)) if offset is None else np.asarray(offset, float)
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = expit(off+X@b)
        H = X.T@(X*(p*(1-p))[:, None])
        step = np.linalg.solve(H, X.T@(y-p))
        b += step
        if np.max(np.abs(step)) < 1e-12: break
    else:
        raise RuntimeError('logistic fit did not converge')
    p = expit(off+X@b)
    S = X*(y-p)[:, None]
    if clusters is not None:
        S = pd.DataFrame(S).groupby(np.asarray(clusters)).sum().to_numpy()
    Hi = np.linalg.inv(X.T@(X*(p*(1-p))[:, None]))
    return b, np.sqrt(np.diag(Hi@(S.T@S)@Hi))


def fit_free(d):
    """Primary: home win ~ 1 + logit(q) + dis (free slopes); returns b on dis and its SE."""
    d = d[d.y.notna()]
    X = np.column_stack([np.ones(len(d)), logit(np.clip(d.q, CLIP, 1-CLIP)), d.dis])
    b, se = logistic(X, d.y, clusters=d.cluster)
    return {'n': int(len(d)), 'b': float(b[2]), 'se': float(se[2]), 'b_logit_q': float(b[1]), 'se_logit_q': float(se[1]),
            'b_per_sd': float(b[2]*SD_LATER), 'z': float(b[2]/se[2])}


def fit_offset(d):
    """Secondary: logit P(home) = logit(q) + a + b'*dis."""
    d = d[d.y.notna()]
    X = np.column_stack([np.ones(len(d)), d.dis])
    b, se = logistic(X, d.y, offset=logit(np.clip(d.q, CLIP, 1-CLIP)), clusters=d.cluster)
    return {'n': int(len(d)), 'b': float(b[1]), 'se': float(se[1]), 'z': float(b[1]/se[1])}


def verdict(b, se):
    if b >= 0: return 'falsified for 2006-2012'
    if b <= -2*se: return 'replicated'
    return 'consistent sign, unresolved'


def payout(ml):
    ml = np.asarray(ml, float)
    return np.where(ml < 0, 100/-ml, ml/100)


def rule_bets(d, t=T):
    """1u at the moneyline on the side the spread favors more (away if dis > 0, home if dis < 0)."""
    x = d[d.dis.abs() >= t].copy()
    home = (x.dis < 0).to_numpy()
    price = np.where(home, x.home_moneyline, x.away_moneyline)
    qside = np.where(home, x.q, 1-x.q)
    win = np.where(home, x.result > 0, x.result < 0); tie = (x.result == 0).to_numpy()
    pay = payout(price)
    x['side'] = np.where(home, 'home', 'away')
    x['units'] = np.where(tie, 0., np.where(win, pay, -1.))
    x['null_ev'] = qside*pay-(1-qside)
    fav = m.flat_bets(x.assign(**{'home won': np.where(x.result > 0, 1., np.where(x.result < 0, 0., .5)), 'fwp': x.q}), 'fwp')
    x['fav_units'] = fav.units.to_numpy()
    return x


def rule_summary(x):
    n = len(x); u = x.units.to_numpy()
    return {'bets': int(n), 'wins': int((u > 0).sum()), 'losses': int((u < 0).sum()), 'pushes': int((u == 0).sum()),
            'units': float(u.sum()), 'roi': float(u.mean()) if n else np.nan,
            'roi_se': float(u.std(ddof=1)/np.sqrt(n)) if n > 1 else np.nan,
            'null_roi': float(x.null_ev.mean()) if n else np.nan,
            'fav_units': float(np.nansum(x.fav_units)), 'share_underdog_side': float(((x.side == 'home') & (x.q < .5) | (x.side == 'away') & (x.q > .5)).mean()) if n else np.nan}


def run(out=OUT):
    g = pd.read_csv(GAMES)
    allg = disagreement(g)
    d = priced(g)
    later = priced(pd.read_csv(LATER))
    later = later[later.week <= 18]
    res = {'protocol': PROTOCOL, 'protocol_commit': PROTOCOL_COMMIT, 'T': T, 'sd_dis_2013_2026': SD_LATER, 'sigma': SIGMA,
           'coverage': {str(s): {'games': int((allg.season == s).sum()), 'priced_decided': int((d.season == s).sum())} for s in SEASONS}}
    res['primary'] = fit_free(d)
    res['primary']['verdict'] = verdict(res['primary']['b'], res['primary']['se'])
    pooled = pd.concat([d, later], ignore_index=True)
    res['pooled_2006_2026'] = fit_free(pooled)
    lo, hi = res['pooled_2006_2026']['b']-1.96*res['pooled_2006_2026']['se'], res['pooled_2006_2026']['b']+1.96*res['pooled_2006_2026']['se']
    res['pooled_2006_2026']['ci95'] = [lo, hi]
    res['lead_closed'] = bool(res['primary']['b'] >= 0 and lo <= 0 <= hi)
    res['secondary_offset'] = fit_offset(d)
    res['eras'] = {'2006-2009': fit_free(d[d.season <= 2009]), '2010-2012': fit_free(d[d.season >= 2010])}
    rb = rule_bets(d)
    res['rule'] = rule_summary(rb)
    res['rule']['verdict'] = 'fails (ROI <= null)' if res['rule']['roi'] <= res['rule']['null_roi'] else 'ROI above its null'
    res['rule_eras'] = {e: rule_summary(rb[rb.season.between(a, b)]) for e, (a, b) in (('2006-2009', (2006, 2009)), ('2010-2012', (2010, 2012)))}
    res['dis_outcome_free'] = {'sd': float(d.dis.std(ddof=1)), 'p75_abs': float(d.dis.abs().quantile(.75)),
                               'corr_with_logit_q': float(np.corrcoef(d.dis, logit(np.clip(d.q, CLIP, 1-CLIP)))[0, 1])}
    out.mkdir(parents=True, exist_ok=True)
    (out/'results.json').write_text(json.dumps(res, indent=2)+'\n')
    rb[['game_id', 'season', 'week', 'dis', 'q', 'side', 'units', 'null_ev', 'fav_units']].to_csv(out/'rule_bets.csv', index=False, float_format='%.6g')
    prov = {k: sha(ROOT/k) for k in ('research/ml_spread_2006_12.py', PROTOCOL, 'nfl_model.py',
                                     str(GAMES.relative_to(ROOT)), str(LATER.relative_to(ROOT)))}
    (out/'provenance.json').write_text(json.dumps(prov, indent=2)+'\n')
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--freeze', metavar='GAMES_CSV')
    a = ap.parse_args()
    if a.freeze: freeze(a.freeze); return
    print(json.dumps(run(), indent=2))


if __name__ == '__main__':
    main()
