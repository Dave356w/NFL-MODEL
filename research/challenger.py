"""Test 60: a departure-calibrated challenger to production on every scorecard measure; see CHALLENGER.md.

    python research/challenger.py

Reads only committed files; no network access. Never writes data/ or the ledger. Diagnostic only.
"""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import expit, logit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT/'research'))
import nfl_model as m  # noqa: E402
import fixed_bands as fb  # noqa: E402
import feature_importance as fi  # noqa: E402
import market_implied as mi  # noqa: E402  (Test 51 harness: reproduces v1.19's weekly fits)
import residual_trends as t  # noqa: E402
import slim_model as sm  # noqa: E402

OUT = ROOT/'research/challenger_results'
RETRO = ROOT/'data/latest/retro_ledger.csv'
FIXED = ROOT/'data/latest/fixed_band_ledger.csv'
PRICES = ROOT/'research/spread_price_inputs/spread_odds.csv'
PROTOCOL_COMMIT = '842f1ec'
PRIOR_MEAN, PRIOR_SD, ALPHA_LO, ALPHA_HI = 1., .5, 0., 2.
SEED, BOOT, Z_BAR = 20261105, 2000, 1.96
ARMS = ('P', 'C', 'M')
ARM_NAMES = {'P': 'P production', 'C': 'C challenger', 'M': 'M market only'}
WP_BASES = {'2015-16': (2015, 2016), '2017-22': (2017, 2022), '2023-25': (2023, 2025), '2026 wk1-8': (2026, 2026)}
ATS_BASES = {'2016-22': {'span': (2016, 2022), 'history_from': 2014},
             '2023-26': {'span': (2023, 2026), 'history_from': 2021}}
KEEP = ['game_id', 'season', 'week', 'home won', 'y', 'q', 'p16', 'p', 'spread_line', 'result',
        'home_moneyline', 'away_moneyline', 'cluster']


# --- production ------------------------------------------------------------------------------------

def uninvert_penalty(p, q, lam=m.FAVORITE_PENALTY):
    """Undo `favorite_penalized_wp`: the penalized p stays on the raw side of q, so bull is identifiable."""
    lp, lq = logit(np.asarray(p, float)), logit(np.asarray(q, float))
    bull = ((lq > 0) & (lp > lq)) | ((lq < 0) & (lp < lq))
    return np.where(bull, expit(lq+(lp-lq)/lam), p)


def production():
    """v1.19 replay 2014-25 (Test 51 harness) plus the published 2026 v1.19 replay (weeks 1-8)."""
    hist, _ = mi.forecasts(mi.season_parts(mi.scores()))
    retro = pd.read_csv(RETRO)
    checks = {}
    j = hist[hist.season.between(2021, 2025)].merge(retro[['game_id', 'model_wp']], on='game_id', validate='one_to_one')
    checks['P vs published v1.19 model_wp 2021-25'] = float(np.max(np.abs(j.p-j.model_wp)))
    r = retro[retro.season == 2026].copy()
    r['q'] = m.market_ml_wp(r)
    r['p'] = r.model_wp.astype(float)
    r['p16'] = uninvert_penalty(r.p, r.q)
    k = retro.season.between(2021, 2025)
    inv = uninvert_penalty(retro.loc[k, 'model_wp'], m.market_ml_wp(retro[k]))
    j2 = hist[['game_id', 'p16']].merge(retro.loc[k, ['game_id']].assign(inv=inv), on='game_id', validate='one_to_one')
    checks['penalty inversion vs unpenalized fit 2021-25'] = float(np.max(np.abs(j2.p16-j2.inv)))
    checks['2026 re-penalized vs published model_wp'] = float(np.max(np.abs(
        m.favorite_penalized_wp(r.p16, r.q, m.FAVORITE_PENALTY)-r.p)))
    r['y'] = r['home won'].where(r['home won'].isin([0., 1.]))
    r['cluster'] = r.season.astype(int).astype(str)+'_'+r.week.astype(int).astype(str)
    d = pd.concat([hist[KEEP], r[KEEP]], ignore_index=True)
    d = d[np.isfinite(d.q) & np.isfinite(d.p16)].sort_values(['season', 'week', 'game_id']).reset_index(drop=True)
    pr = pd.read_csv(PRICES)
    d = d.merge(pr[['game_id', 'spread_line', 'result', 'home_spread_odds', 'away_spread_odds']], on='game_id', how='left',
                suffixes=('', '_px'), validate='one_to_one')
    k = d.spread_line_px.notna()
    checks['spread price file: line/result mismatches'] = int(((d.spread_line != d.spread_line_px) | (d.result != d.result_px))[k].sum())
    checks['spread price file: games without prices'] = int((~k).sum())
    d = d.drop(columns=['spread_line_px', 'result_px'])
    for name, v in checks.items():
        if ('mismatch' in name and v) or ('vs' in name and v > 1e-9):
            raise ValueError(f'reproduction failed: {name} = {v}')
    return d, checks


# --- the challenger --------------------------------------------------------------------------------

def alpha_mode(y, lq, g):
    """Posterior mode of alpha in logit p = lq + alpha*g with prior N(PRIOR_MEAN, PRIOR_SD^2), clipped."""
    y, lq, g = (np.asarray(v, float) for v in (y, lq, g))
    a, prec = PRIOR_MEAN, 1/PRIOR_SD**2
    for _ in range(50):
        p = expit(lq+a*g)
        grad = np.sum((y-p)*g)-prec*(a-PRIOR_MEAN)
        hess = -np.sum(p*(1-p)*g*g)-prec
        step = grad/hess; a -= step
        if abs(step) < 1e-12: break
    return float(np.clip(a, ALPHA_LO, ALPHA_HI)), float(1/np.sqrt(-hess))


def alpha_at(d, season, week):
    tr = d[m.before(d, season, week) & d.y.notna()]
    if not m.before(tr, season, week).all(): raise ValueError('alpha training includes the current or a later week')
    if not len(tr): return PRIOR_MEAN, PRIOR_SD, 0
    lq = logit(tr.q.to_numpy(float))
    a, se = alpha_mode(tr.y, lq, logit(tr.p.to_numpy(float))-lq)
    return a, se, len(tr)


def challenger(d):
    d = d.copy(); rows = []
    for (y, w) in sorted(set(zip(d.season, d.week))):
        a, se, n = alpha_at(d, y, w); rows.append({'season': y, 'week': w, 'alpha': a, 'alpha_se': se, 'training_games': n})
    al = pd.DataFrame(rows)
    d = d.merge(al[['season', 'week', 'alpha']], on=['season', 'week'], how='left', validate='many_to_one')
    lq = logit(d.q.to_numpy(float))
    d['pC'] = expit(lq+d.alpha.to_numpy(float)*(logit(d.p.to_numpy(float))-lq))
    d['pP'] = d.p; d['pM'] = d.q
    return d, al


def lookahead_check(d):
    """Negative fixture: changing the forecast week's and later outcomes leaves alpha unchanged.
    Positive fixture: changing earlier outcomes moves it."""
    y, w = 2019, 9
    base = alpha_at(d, y, w)[0]
    later = d.copy(); k = ~m.before(later, y, w) & later.y.notna(); later.loc[k, 'y'] = 1-later.loc[k, 'y']
    if alpha_at(later, y, w)[0] != base: raise ValueError('alpha lookahead')
    earlier = d.copy(); lq = logit(earlier.q); g = logit(earlier.p)-lq
    k = m.before(earlier, y, w) & earlier.y.notna() & (np.abs(g) > .2) & earlier.season.eq(y-1)
    earlier.loc[k, 'y'] = 1-earlier.loc[k, 'y']
    if alpha_at(earlier, y, w)[0] == base: raise ValueError('alpha ignores earlier outcomes')
    if abs(alpha_mode([1., 0.], [0., 0.], [0., 0.])[0]-PRIOR_MEAN) > 1e-12: raise ValueError('no information must return the prior mean')
    return True


# --- spreads and maps ------------------------------------------------------------------------------

def mapped(d, arm, history_from, span):
    h = d[d.season >= history_from][['game_id', 'season', 'week', 'result']].copy()
    h['model_spread'] = m.implied_spread(d.loc[h.index, 'p'+arm])
    out = pd.Series(np.nan, index=d.index)
    for (y, w), gm in h[h.season.between(*span)].groupby(['season', 'week']):
        rule = fb.fit_weekly(h, int(y), int(w))
        out.loc[gm.index] = fb.apply(gm.model_spread, rule)
    return out


def american_profit(o):
    o = np.asarray(o, float)
    ok = np.isfinite(o) & (np.abs(o) >= 100)
    return np.where(ok, np.where(o < 0, 100/np.abs(np.where(ok, o, -110)), np.where(ok, o, 110)/100), 1/1.1), ~ok


def ats_returns(side, margin, home_odds, away_odds):
    edge = side*margin
    win, loss = edge > fb.EPS, edge < -fb.EPS
    r110 = np.where(win, 1/1.1, np.where(loss, -1., 0.))
    prof, assumed = american_profit(np.where(side > 0, home_odds, away_odds))
    rpx = np.where(win, prof, np.where(loss, -1., 0.))
    bet = side != 0
    return r110, rpx, win & bet, loss & bet, bet, assumed & bet


# --- scores ----------------------------------------------------------------------------------------

def ece(y, p, bins=10):
    b = np.minimum((np.asarray(p)*bins).astype(int), bins-1)
    y, p = np.asarray(y, float), np.asarray(p, float); tot = 0.
    for k in range(bins):
        s = b == k
        if s.any(): tot += s.sum()*abs(y[s].mean()-p[s].mean())
    return tot/len(y)


def boot_ece_diff(y, pa, pb, cl):
    rng = np.random.default_rng(SEED)
    y, pa, pb, cl = map(np.asarray, (y, pa, pb, cl))
    groups = pd.Series(np.arange(len(y))).groupby(cl).apply(np.asarray).tolist()
    diffs = []
    for _ in range(BOOT):
        ix = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        diffs.append(ece(y[ix], pa[ix])-ece(y[ix], pb[ix]))
    return float(np.std(diffs, ddof=1))


def ratio_lin(num, den):
    num, den = np.asarray(num, float), np.asarray(den, float)
    r = num.sum()/den.sum()
    return r, (num-r*den)/den.mean()


def cell(measure, basis, arm, vals_arm, vals_p, cl, lower_better, scale=1., se=None, point=None):
    """Arm minus P. `point` overrides the mean difference (ratio and ECE cells)."""
    mu, s = fi.cmean(np.asarray(vals_arm, float)-np.asarray(vals_p, float), cl)
    if point is not None: mu = point
    if se is not None: s = se
    z = mu/s if s and s > 0 else np.nan
    good = -mu if lower_better else mu
    return {'measure': measure, 'basis': basis, 'arm': arm, 'diff': scale*mu, 'se': scale*s if np.isfinite(s) else np.nan,
            'z_in_arm_favour': good/s if s and s > 0 else np.nan, 'z': z,
            'result': 'tie' if abs(mu) < 1e-12 else ('better' if good > 0 else 'worse')}


def wp_scorecard(d):
    cells, levels, ml = [], [], []
    for b, span in WP_BASES.items():
        s = d[d.season.between(*span) & d.y.notna()].reset_index(drop=True)
        y, cl = s.y.to_numpy(float), s.cluster.to_numpy()
        ll = {a: fi.ll(y, s['p'+a].to_numpy(float)) for a in ARMS}
        br = {a: (s['p'+a].to_numpy(float)-y)**2 for a in ARMS}
        ec = {a: ece(y, s['p'+a]) for a in ARMS}
        sb = d[d.season.between(*span)].reset_index(drop=True)
        bets = {a: m.flat_bets(sb.assign(model_wp=sb['p'+a])) for a in ARMS}
        fav = m.flat_bets(sb.assign(model_wp=sb.q))
        ok = fav.units.notna() & np.logical_and.reduce([bets[a].units.notna() for a in ARMS])
        for a in ARMS:
            levels.append({'basis': b, 'arm': ARM_NAMES[a], 'n': len(s), 'log_loss': float(ll[a].mean()),
                           'brier': float(br[a].mean()), 'ece': ec[a]})
            u = bets[a].units[ok].to_numpy(float)
            ml.append({'basis': b, 'arm': ARM_NAMES[a], 'bets': int(ok.sum()), 'units': float(u.sum()),
                       'roi': float(u.mean()), 'roi_se': float(u.std(ddof=1)/np.sqrt(len(u))),
                       'market_null_roi': float(bets[a].null_ev[ok].mean()),
                       'favorite_units': float(fav.units[ok].sum()),
                       'underdog_picks': int((bets[a].side[ok] != fav.side[ok]).sum())})
        for a in ('C', 'M'):
            cells.append(cell('log loss', b, a, ll[a], ll['P'], cl, True, 1000))
            cells.append(cell('Brier', b, a, br[a], br['P'], cl, True, 1000))
            cells.append(cell('calibration error', b, a, np.zeros(len(y)), np.zeros(len(y)), cl, True, 100,
                              se=boot_ece_diff(y, s['p'+a], s.pP, cl), point=ec[a]-ec['P']))
            cells.append(cell('moneyline units', b, a, bets[a].units[ok], bets['P'].units[ok], sb.cluster[ok], False,
                              int(ok.sum())))
    return cells, levels, ml


def ats_scorecard(d):
    cells, recs = [], []
    for b, spec in ATS_BASES.items():
        mp = {a: mapped(d, a, spec['history_from'], spec['span']) for a in ARMS}
        s = d[d.season.between(*spec['span'])].copy()
        for a in ARMS: s['map'+a] = mp[a].loc[s.index]
        s = s[np.isfinite(s.result) & np.isfinite(s.spread_line) &
              np.logical_and.reduce([np.isfinite(s['map'+a]) for a in ARMS])].reset_index(drop=True)
        line, res = s.spread_line.to_numpy(float), s.result.to_numpy(float); margin = res-line
        cl = s.cluster.to_numpy(); ho, ao = s.home_spread_odds.to_numpy(float), s.away_spread_odds.to_numpy(float)
        out = {}
        for a in ARMS:
            side = fb.pick(s['map'+a].to_numpy(float), line)
            out[a] = (side, *ats_returns(side, margin, ho, ao))
            raw = m.implied_spread(s['p'+a])
            out[a] += (np.abs(s['map'+a].to_numpy(float)-res), np.abs(raw-res))
        base = {'always favorite': np.sign(line), 'always home': np.ones(len(s))}
        for name, side in base.items(): out[name] = (side, *ats_returns(side, margin, ho, ao), None, None)
        for name, o in out.items():
            side, r110, rpx, w, l, bet, assumed = o[:7]
            n = int(bet.sum()); w_, l_ = int(w.sum()), int(l.sum())
            recs.append({'basis': b, 'arm': ARM_NAMES.get(name, name), 'games': len(s), 'W': w_, 'L': l_, 'P': n-w_-l_,
                         'skips': int((~bet).sum()), 'bets': n, 'units_110': float(r110[bet].sum()),
                         'roi_110': float(r110[bet].mean()), 'roi_se_110': float(r110[bet].std(ddof=1)/np.sqrt(n)),
                         'units_price': float(rpx[bet].sum()), 'roi_price': float(rpx[bet].mean()),
                         'roi_se_price': float(rpx[bet].std(ddof=1)/np.sqrt(n)), 'assumed_prices': int(assumed.sum()),
                         'cover': w_/(w_+l_), 'flips_vs_P': int((side != out['P'][0]).sum()) if name != 'P' else 0,
                         'underdog_share': float((side[bet] != np.sign(line[bet])).mean()),
                         'mae_mapped': float(o[7].mean()) if o[7] is not None else np.nan,
                         'mae_raw': float(o[8].mean()) if o[8] is not None else np.nan})
        p = out['P']
        for a in ('C', 'M'):
            o = out[a]; n = len(s)
            cells.append(cell('ATS units at -110', b, a, o[1], p[1], cl, False, n))
            cells.append(cell('ATS units at actual prices', b, a, o[2], p[2], cl, False, n))
            rA, linA = ratio_lin(o[3], o[3] | o[4]); rP, linP = ratio_lin(p[3], p[3] | p[4])
            cells.append(cell('ATS cover rate', b, a, linA, linP, cl, False, 100, point=rA-rP))
            cells.append(cell('mapped spread abs error', b, a, o[7], p[7], cl, True))
            cells.append(cell('raw spread abs error', b, a, o[8], p[8], cl, True))
        # fidelity: P's 2023-26 map is production's published fixed_band_spread
        if b == '2023-26':
            f = pd.read_csv(FIXED)[['game_id', 'fixed_band_spread']]
            j = s[['game_id', 'mapP']].merge(f, on='game_id', validate='one_to_one')
            err = float(np.max(np.abs(j.mapP-j.fixed_band_spread)))
            if err > 1e-9 or len(j) != len(s): raise ValueError(f'P map does not reproduce fixed_band_spread ({err})')
            map_err = err
    return cells, recs, map_err


def primary_verdict(c):
    ll = [r for r in c if r['arm'] == 'C' and r['measure'] == 'log loss']
    if any(r['z_in_arm_favour'] <= -Z_BAR for r in ll): return 'stop'
    lower = sum(r['result'] == 'better' for r in ll)
    if lower == 4 and any(r['z_in_arm_favour'] >= Z_BAR for r in ll): return 'better'
    if lower >= 3: return 'forward candidate'
    return 'unresolved'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(out=OUT):
    out.mkdir(parents=True, exist_ok=True)
    d, checks = production()
    lookahead_check(d)
    d, al = challenger(d)
    wc, levels, ml = wp_scorecard(d)
    ac, recs, map_err = ats_scorecard(d)
    checks['P map vs published fixed_band_spread 2023-26'] = map_err
    cells = pd.DataFrame(wc+ac)
    cnt = cells[cells.arm == 'C'].result.value_counts().to_dict()
    sig = cells[cells.arm == 'C']
    season_ll = pd.DataFrame([{'season': int(y), 'n': int(len(g)), **{ARM_NAMES[a]: float(fi.ll(g.y, g['p'+a]).mean()) for a in ARMS}}
                              for y, g in d[d.y.notna() & d.season.ge(2015)].groupby('season')])
    alpha_season = al[al.season >= 2015].groupby('season').agg(alpha_first=('alpha', 'first'), alpha_last=('alpha', 'last'),
                                                               alpha_min=('alpha', 'min'), alpha_max=('alpha', 'max'),
                                                               se_last=('alpha_se', 'last')).reset_index()
    res = {'protocol': 'research/CHALLENGER.md', 'protocol_commit': PROTOCOL_COMMIT, 'reproduction': checks,
           'cells': int(len(sig)), 'challenger_cells': {k: int(v) for k, v in cnt.items()},
           'challenger_reliably_better': int((sig.z_in_arm_favour >= Z_BAR).sum()),
           'challenger_reliably_worse': int((sig.z_in_arm_favour <= -Z_BAR).sum()),
           'challenge_met': bool(cnt.get('better', 0) == len(sig)), 'primary_verdict': primary_verdict(wc)}
    cells.to_csv(out/'scorecard.csv', index=False, float_format='%.6g')
    pd.DataFrame(levels).to_csv(out/'wp_levels.csv', index=False, float_format='%.6g')
    pd.DataFrame(ml).to_csv(out/'moneyline.csv', index=False, float_format='%.6g')
    pd.DataFrame(recs).to_csv(out/'ats.csv', index=False, float_format='%.6g')
    al.to_csv(out/'alpha.csv', index=False, float_format='%.6g')
    season_ll.to_csv(out/'season_log_loss.csv', index=False, float_format='%.6g')
    d[['game_id', 'season', 'week', 'y', 'q', 'pP', 'pC', 'alpha']].to_csv(
        out/'forecasts.csv.gz', index=False, float_format='%.6g', compression={'method': 'gzip', 'mtime': 0})
    (out/'results.json').write_text(json.dumps(res, indent=2))
    (out/'provenance.json').write_text(json.dumps({str(p.relative_to(ROOT)): sha(p) for p in (
        Path(__file__), ROOT/'research/CHALLENGER.md', ROOT/'nfl_model.py', ROOT/'fixed_bands.py', RETRO, FIXED, PRICES,
        mi.SCORES, t.OOS_PACK, t.T36_PACK)}, indent=2))
    write_report(res, cells, pd.DataFrame(levels), pd.DataFrame(ml), pd.DataFrame(recs), alpha_season, season_ll, out)
    return res


def write_report(res, cells, levels, ml, recs, alpha_season, season_ll, out):
    fmt = {'log loss': ('×1000', 2), 'Brier': ('×1000', 2), 'calibration error': ('points', 2), 'moneyline units': ('u', 1),
           'ATS units at -110': ('u', 1), 'ATS units at actual prices': ('u', 1), 'ATS cover rate': ('points', 2),
           'mapped spread abs error': ('points', 3), 'raw spread abs error': ('points', 3)}
    L = ['# Test 60: a departure-calibrated challenger to production', '',
         f'Protocol: [CHALLENGER.md](../CHALLENGER.md), committed and pushed (`{res["protocol_commit"]}`) before any arm was scored. '
         'Diagnostic only; production and the ledger are unchanged. Every basis was exposed earlier (see protocol).', '',
         'Reproduction: ' + ', '.join(f'{k} {v:.1e}' if isinstance(v, float) else f'{k} {v}' for k, v in res['reproduction'].items()) + '.', '',
         f'**Challenge (better than production in all {res["cells"]} cells): {"met" if res["challenge_met"] else "not met"}.** '
         f'C is better in {res["challenger_cells"].get("better", 0)}, worse in {res["challenger_cells"].get("worse", 0)} '
         f'and tied in {res["challenger_cells"].get("tie", 0)}; reliably better (z ≥ 1.96) in {res["challenger_reliably_better"]}, '
         f'reliably worse in {res["challenger_reliably_worse"]}. Primary verdict (log loss): **{res["primary_verdict"]}**.', '',
         '## Scorecard: arm minus production (± 1 SE; z in the arm\'s favour)', '',
         '| Measure | Basis | C challenger − P | | M market only − P |', '|---|---|---|---|---|']
    for (meas, b), g in cells.groupby(['measure', 'basis'], sort=False):
        unit, dp = fmt[meas]; c, mm = g[g.arm == 'C'].iloc[0], g[g.arm == 'M'].iloc[0]
        L.append(f'| {meas} ({unit}) | {b} | {c["diff"]:+.{dp}f} ± {c.se:.{dp}f} (z {c.z_in_arm_favour:+.1f}) | {c.result} | '
                 f'{mm["diff"]:+.{dp}f} ± {mm.se:.{dp}f} (z {mm.z_in_arm_favour:+.1f}) |')
    L += ['', 'Signs: log loss, Brier, calibration error and absolute errors are arm − P (negative = arm better); '
          'units and cover rate are arm − P (positive = arm better).', '',
          '## Win-probability levels', '', '| Basis | Arm | n | Log loss | Brier | Calibration error |', '|---|---|---:|---:|---:|---:|']
    for _, r in levels.iterrows():
        L.append(f'| {r.basis} | {r.arm} | {r.n} | {r.log_loss:.5f} | {r.brier:.5f} | {100*r.ece:.2f} pts |')
    L += ['', '## Moneyline flat 1u (legacy basis, same bets)', '',
          '| Basis | Arm | Bets | Units | ROI ± SE | Market-correct null | Same-row favorite | Picks against the market favorite |',
          '|---|---|---:|---:|---:|---:|---:|---:|']
    for _, r in ml.iterrows():
        L.append(f'| {r.basis} | {r.arm} | {r.bets} | {r.units:+.1f} | {100*r.roi:+.1f}% ± {100*r.roi_se:.1f} | '
                 f'{100*r.market_null_roi:+.1f}% | {r.favorite_units:+.1f}u | {r.underdog_picks} |')
    L += ['', '## ATS, flat 1u (same rows for every arm; each arm uses map policy v2 on its own spreads)', '',
          'Break-even cover rate 52.4% at −110. ROI SE has pushes in the denominator.', '',
          '| Basis | Arm | W-L-P | Skips | Units −110 | ROI −110 ± SE | Units at price | ROI at price ± SE | Cover | Underdog share | Flips vs P | MAE mapped | MAE raw |',
          '|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for _, r in recs.iterrows():
        mae = '' if pd.isna(r.mae_mapped) else f'{r.mae_mapped:.3f}'; maer = '' if pd.isna(r.mae_raw) else f'{r.mae_raw:.3f}'
        L.append(f'| {r.basis} | {r.arm} | {r.W}-{r.L}-{r.P} | {r.skips} | {r.units_110:+.1f} | {100*r.roi_110:+.1f}% ± {100*r.roi_se_110:.1f} | '
                 f'{r.units_price:+.1f} | {100*r.roi_price:+.1f}% ± {100*r.roi_se_price:.1f} | {100*r.cover:.1f}% | '
                 f'{100*r.underdog_share:.0f}% | {r.flips_vs_P} | {mae} | {maer} |')
    L += ['', f'Prices assumed at −110: {", ".join(f"{r.basis} {r.arm} {r.assumed_prices}" for _, r in recs[recs.arm.str.startswith("P")].iterrows())}.',
          '', '## C\'s departure weight α (1 = production)', '', '| Season | First week | Last week | Min | Max | SE at last week |',
          '|---|---:|---:|---:|---:|---:|']
    for _, r in alpha_season.iterrows():
        L.append(f'| {int(r.season)} | {r.alpha_first:.3f} | {r.alpha_last:.3f} | {r.alpha_min:.3f} | {r.alpha_max:.3f} | {r.se_last:.3f} |')
    L += ['', '## Log loss by season', '', '| Season | n | P | C | M |', '|---|---:|---:|---:|---:|']
    for _, r in season_ll.iterrows():
        L.append(f'| {int(r.season)} | {int(r.n)} | {r[ARM_NAMES["P"]]:.5f} | {r[ARM_NAMES["C"]]:.5f} | {r[ARM_NAMES["M"]]:.5f} |')
    (out/'REPORT.md').write_text('\n'.join(L) + '\n')


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
